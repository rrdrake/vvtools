#!/usr/bin/env python

"""
The remotepython module uses ssh to connect to a remote machine and run python
commands.  The commands are issued on the local side but executed on the remote
side.  No script is necessary on the remote side, but a python must be
available.  All python versions from 2.4 to 3.5 have been tested.

See http://rpyc.readthedocs.io/ for a full featured remote python execution
framework.  The current module provides remote python code execution over ssh
with just the basic features.

To use it, a python file must first be created that will be executed on the
remote side (although in memory).  For example, suppose this is remote.py:

    import os, sys
    def myfunc( myarg='' ):
        if myarg == '-a': return os.uname()
        return os.uname()[1]

Supoose the local code is contained in a file called local.py with contents

    import os, sys
    from remotepython import RemotePython, RemoteException, LocalException
    from remotepython import print3
    rpy = RemotePython( "machinename", "remote.py" )
    rpy.connect()
    print3( 'call one:', rpy.xcall( "myfunc" ) )
    print3( 'call two:', rpy.xcall( "myfunc", '-a' ) )
    rpy.shutdown()

Running local.py will result in an ssh call to "machinename" followed by two
calls to myfunc() on the remote side.  Note that the print3() function is
defined by remotepython.py and is just a print function usable with both
Python 2.x and Python 3.x.

If an exception occurs during a remote function execution, a RemoteException
is raised on the local side.  An exception that occurs on the local side will
raise a LocalException.

There are two ways to call a function: xcall() and rcall().  They are the same
except that the first will shutdown the connection upon a RemoteException,
whereas the second will not.  A LocalException always causes the connection
to be shutdown.

For convenience, there is an alternative way to call remote functions.  They
can be called using the syntax

    rpy.x_myfunc( '-a' )

or

    rpy.r_myfunc( '-a' )

The first is the same as rpy.xcall( "myfunc", '-a' ) and the second is the
same as rpy.rcall( "myfunc", '-a' ).

A RemotePython object can be shutdown() and reconnected using connect() any
number of times.

Files can be transferred using putFile() and getFile(), which are called from
the local side.  But note that the transfer speed is less than ideal because
encoding/decoding is performed in order to avoid Unicode issues and to avoid
any possible issues with sending binary data across ssh stdin & stdout.
"""

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import subprocess
import time
import traceback
import stat
import binascii
import threading
import signal

# CStringIO for both python 2 & 3
try:
  import StringIO
  class_StringIO = StringIO.StringIO
except:
  import io
  class_StringIO = io.StringIO


class RemoteException(Exception):
    """
    An exception on the remote side is propagated back to the local side and
    raised as a RemoteException.  The connection is shutdown if xcall() is
    used but not if rcall() is used.
    """
    pass

class LocalException(Exception):
    """
    A LocalException indicates an error on the local side, and will cause a
    shutdown of the connection before being raised.
    """
    pass


class RemotePython:

    def __init__(self, machine, remote_filename,
                       sshexe=None, remotepy='/usr/bin/python' ):
        """
        If 'sshexe' is given, it should be the path to an ssh executable.
        If it is not given, the current PATH is searched.

        If 'remotepy' is specified, it is the python executable on the remote
        side that will be run.
        """
        assert machine and machine.strip() == machine
        self.mach = machine
        self.rfname = remote_filename
        self.sshexe = sshexe
        self.remotepy = remotepy
        self.pssh = None
        self.pid = None  # process id of ssh command
        self.timer = None
        self.tlock = threading.Lock()

    def startTimeout(self, numseconds):
        """
        Call this right before calling a function of this class to impose a
        time limit on the duration of the function.  If the call times out,
        the ssh subprocess is killed, and the function will (usually) raise
        a LocalException.
        """
        assert numseconds > 0
        self.tlock.acquire()
        try:
            if self.timer != None:
                self.timer.cancel()
                self.timer = None
            t = threading.Timer( numseconds, self._timerKill )
            t.start()
        except:
            self.tlock.release()
            raise
        self.timer = t
        self.tlock.release()

    def connect(self):
        """
        Runs ssh in a subprocess to connect to the remote machine, and checks
        the connection with a ping-pong test.  A connection failure causes an
        exception to be raised.  If a connection is still active, nothing is
        done.
        """
        if self.pssh != None:
            self._cancelTimer()
            return
        
        try:
            fp = None

            # the remote script is the user's script plus utility coding
            fp = open( self.rfname, 'rb' )
            scr = fp.read()
            fp.close() ; fp = None
            scr += _BYTES_( remote_utils )

            # create pipe to send commands to python (to ssh stdin)
            self.cmdin_r, self.send_pipe = os.pipe()
            # create pipe to recv output from python (from ssh stdout)
            fd, self.cmdout_w = os.pipe()
            self.recv_pipe = os.fdopen( fd, 'rb' )

            # start the ssh command that runs python on the remote end
            self._sshconnect( self.cmdin_r, self.cmdout_w )
            os.close( self.cmdin_r )  # parent does not read from command pipe
            os.close( self.cmdout_w )  # parent does not write to output pipe

            # bootstrap the remote end by sending the python script
            os.write( self.send_pipe, _BYTES_( str(len(scr))+'\n' ) )
            os.write( self.send_pipe, scr )
            
            # check the connection
            assert self.pssh.poll() == None
            val = repr( [ '_ping', (), {} ] )
            os.write( self.send_pipe, _BYTES_( 'CAL:' + val + '\n' ) )
            rtn = self._read_return()
            assert rtn == 'pong'
        
        except:
            self._cancelTimer()
            sio = class_StringIO()
            traceback.print_exc( file=sio )
            if fp != None: fp.close()
            self.shutdown()
            raise LocalException( sio.getvalue() + \
                                  "\nConnection failed to '"+self.mach+"'" )
        
        self._cancelTimer()

    def isConnected(self):
        """
        Returns True if an ssh connection has been made.
        """
        return self.pssh != None

    def shutdown(self):
        """
        Close the connection and wait for the ssh subprocess to finish.  Can
        be called more than once without side effects.
        """
        try: os.write( self.send_pipe, _BYTES_( 'XIT:\n' ) )
        except: pass

        self._cancelTimer()
        self._close()

        self.pid = self.pssh = None

    def rcall(self, funcname, *args, **kwargs):
        """
        This will call the function named 'funcname' on the remote side with
        the given arguments and return the result.  If an exception occurs on
        the remote side, the connection is left open and a RemoteException is
        raised locally.
        """

        try:
            assert self.pssh != None, "connection lost or never started"

            val = repr( [ funcname, args, kwargs ] )
            os.write( self.send_pipe, _BYTES_( 'CAL:' + val + '\n' ) )

            rtn = self._read_return()
        
        except RemoteException:
            self._cancelTimer()
            raise
        except:
            self._cancelTimer()
            sio = class_StringIO()
            traceback.print_exc( file=sio )
            self.shutdown()
            raise LocalException( "Exception during write: "+ sio.getvalue() )
        
        self._cancelTimer()

        return rtn

    def xcall(self, funcname, *args, **kwargs):
        """
        Same as rcall() except if an exception occurs on the remote side, the
        connection is shutdown before raising RemoteException.
        """
        try:
            # Note: rcall will always cancel the timer
            rtn = self.rcall( funcname, *args, **kwargs )
        except RemoteException:
            self.shutdown()
            raise

        return rtn

    def __getattr__(self, attr_name):
        """
        This is called when an unknown class attribute is requested.  If
        'attr_name' is "r_<name>" then rcall() is returned for <name>.  If
        it is "x_<name>" then xcall() is returned for <name>.  Otherwise an
        exception is raised.
        """
        if len( attr_name ) > 2 and attr_name.startswith( 'r_' ):
            return lambda *args, **kwargs: self.rcall(
                                            attr_name[2:], *args, **kwargs )
        elif len( attr_name ) > 2 and attr_name.startswith( 'x_' ):
            return lambda *args, **kwargs: self.xcall(
                                            attr_name[2:], *args, **kwargs )
        raise LocalException( 'Unknown attribute "'+attr_name+'"' )

    def putFile(self, local_name, remote_name, bufsize=1024, preserve=False):
        """
        Transfer a file from the local side to the remote side.  The 'bufsize'
        is the chunk size used to read/write the file and send across the
        connection.  A LocalException will cause the connection to be closed,
        but other exceptions do not.  If 'preserve' is True, the time stamp
        and permission bits are also copied.

        Returns the number of bulk bytes sent, which will be greater than
        the file size due to the data encoding used during transfer.
        """
        try:
            fp = None
            exc = "Exception preparing for file put: "

            assert self.pssh != None, "connection lost or never started"

            mtime = atime = fmode = None
            if preserve:
                mtime = os.path.getmtime( local_name )
                atime = os.path.getatime( local_name )
                fmode = stat.S_IMODE( os.stat(local_name)[stat.ST_MODE] )
            sz = os.path.getsize( local_name )
            
            bufsize = max( 16, min( bufsize, 524288 ) )
            n,r = int(sz/bufsize), sz%bufsize
            nreads = n
            if r > 0: nreads += 1

            # check ability to open and read the file
            fp = open( local_name, 'rb' ) ; fp.close() ; fp = None

            os.write( self.send_pipe,
                      _BYTES_( 'WOK:' + repr(remote_name) + '\n' ) )
            
            ok = self._read_return()
            assert ok

            exc = "Exception during file read / pipe write: "

            fp = open( local_name, 'rb' )

            msg = [ nreads, remote_name, mtime, atime, fmode ]
            os.write( self.send_pipe, _BYTES_( 'PUT:' + repr(msg) + '\n' ) )

            i = 0
            while i < n:
                #buf = binascii.b2a_hqx( binascii.rlecode_hqx(
                #                                    fp.read( bufsize ) ) )
                buf = binascii.b2a_hex( fp.read( bufsize ) )
                os.write( self.send_pipe, _BYTES_( str(len(buf))+'\n' ) )
                os.write( self.send_pipe, buf )
                i += 1
            if r > 0:
                #buf = binascii.b2a_hqx( binascii.rlecode_hqx(
                #                                    fp.read( r ) ) )
                buf = binascii.b2a_hex( fp.read( r ) )
                os.write( self.send_pipe, _BYTES_( str(len(buf))+'\n' ) )
                os.write( self.send_pipe, buf )
            
            fp.close() ; fp = None

            rtn = self._read_return()
        
        except RemoteException:
            self._cancelTimer()
            if fp != None: fp.close()
            raise
        except:
            self._cancelTimer()
            sio = class_StringIO()
            traceback.print_exc( file=sio )
            if fp != None: fp.close()
            self.shutdown()
            raise LocalException( exc + sio.getvalue() )

        self._cancelTimer()
        
        return rtn

    def getFile(self, remote_name, local_name, bufsize=1024, preserve=False):
        """
        Transfer a file from the remote side to the local side.  The 'bufsize'
        is the chunk size used to read/write the file and send across the
        connection.  A LocalException will cause the connection to be closed,
        but other exceptions do not.  If 'preserve' is True, the time stamp
        and permission bits are also copied.

        Returns the number of bulk bytes received, which will be greater than
        the file size due to the data encoding used during transfer.
        """
        try:
            sz = 0
            fp = None
            exc = "Exception preparing for file get: "

            assert self.pssh != None, "connection lost or never started"

            maxbuf = 524288
            bufsize = max( 16, min( bufsize, maxbuf ) )
            assert len(str(maxbuf)) < 10

            msg = [ remote_name, preserve ]
            os.write( self.send_pipe, _BYTES_( 'FSZ:' + repr(msg) + '\n' ) )
        
            sz, mtime, atime, fmode = self._read_return()

            fp = open( local_name, 'wb' )
            n,r = int(sz/bufsize), sz%bufsize
            nreads = n
            if r > 0: nreads += 1

            exc = "Exception during pipe read / file write: "

            msg = [ bufsize, n, r, remote_name ]
            os.write( self.send_pipe, _BYTES_( 'GET: '+ repr(msg) +'\n' ) )

            i = 0
            while i < nreads:
                buf = self.recv_pipe.read( int( self.recv_pipe.read( 10 ) ) )
                fp.write( binascii.a2b_hex( _BYTES_( buf ) ) )
                sz += len(buf)
                i += 1
            
            fp.close() ; fp = None
            
            if preserve:
                os.utime( local_name, (atime,mtime) )
                os.chmod( local_name, fmode )

            self._read_return()
        
        except RemoteException:
            self._cancelTimer()
            if fp != None: fp.close()
            raise
        except:
            self._cancelTimer()
            sio = class_StringIO()
            traceback.print_exc( file=sio )
            if fp != None: fp.close()
            self.shutdown()
            raise LocalException( exc + sio.getvalue() )
        
        self._cancelTimer()
        
        return sz

    def _read_return(self):
        """
        Internal function to wait for a return value from the remote side.
        Note that the timer is not (and should not be) canceled in this
        function.
        """
        try:
            byteline = self.recv_pipe.readline()
            while byteline:
                line = _STRING_( byteline ).rstrip()
                L = line.split( ':', 1 )
                if L[0] == 'RTN':
                    return eval( L[1].strip() )
                elif L[0] == 'EXC':
                    raise RemoteException( eval( L[1].strip() ) )
                else:
                    stdout_write( byteline )
                byteline = self.recv_pipe.readline()
        except RemoteException:
            raise
        except:
            sio = class_StringIO()
            traceback.print_exc( file=sio )
            self.shutdown()
            raise LocalException( "Exception during read: "+ sio.getvalue() )

        self.shutdown()
        raise LocalException( "Unexpected end of input during read" )

    def _sshconnect(self, pipein, pipeout):
        """
        This executes ssh as a subprocess to connect to another machine and
        run python.  The current process can then talk to the remote python
        process to execute functions.

        Note that the timer should not be touched in this function.
        """
        assert self.pssh == None

        if self.sshexe:
            cmdL = [ self.sshexe ]
        else:
            ssh = which('ssh')
            assert ssh, "No ssh in PATH"
            cmdL = [ ssh ]

        # ssh -x means do not forward X11 display
        # ssh -T means disable pseudo-tty allocation
        # ssh -v means add verbosity when making the connection
        cmdL.extend( [ '-x', '-T', self.mach ] )

        # the -u option means unbuffer the stdio streams
        # the -E option means ignore python environment variables
        cmdL.extend( [ self.remotepy, '-u', '-E', '-c' ] )
        #cmdL.extend( [ '/usr/bin/env', 'PYTHONIOENCODING=ascii:error',
        #               self.remotepy, '-u', '-E', '-c' ] )

        # this python one-liner reads from sys.stdin an integer for the number
        # of bytes contained in an incoming script, then reads that number of
        # bytes to obtain the script, executes the script using eval, then
        # runs the _listener function (which the incoming script must define)
        pycmd = \
            'import sys; ' + \
            'eval( ' + \
                'compile( sys.stdin.read( ' + \
                            'int( sys.stdin.readline().rstrip() ) ), ' + \
                '"<stdin>", "exec" ) ); ' + \
            '_listener()'
        # add single quotes around the python command to keep the shell
        # from interpreting special characters, like parens
        cmdL.append( "'"+pycmd+"'" )

        #print3( 'magic: ssh cmdL', cmdL )

        self.pssh = subprocess.Popen( cmdL,
                                      stdin=pipein,
                                      stdout=pipeout,
                                      bufsize=0 )
        self.pid = self.pssh.pid

    def _close(self):
        """
        Close the send & recv pipes and wait on the ssh subprocess to finish.
        If ssh does not quit fairly quickly, it is killed.

        This function is called by the threading Timer mechanism to kill the
        ssh process, and so no calls should be made to timer methods or data.
        """
        # close the ssh stdin pipe
        try: os.close( self.send_pipe )
        except: pass

        # close read end of the ssh output pipe
        try: self.recv_pipe.close()
        except: pass
        
        self.send_pipe = None
        self.recv_pipe = None
        
        try:
            if self.pssh != None and self.pssh.returncode == None:
                # give the ssh process a little time to exit
                for i in range(10):
                    x = self.pssh.poll()
                    if x != None:
                        break
                    time.sleep( 0.5 )
                if x == None:
                    # taking too long, so force it
                    if sys.platform.lower().startswith( 'win' ):
                        self.pssh.terminate()
                    else:
                        os.kill( self.pid, signal.SIGTERM )
                        self.pssh.wait()
        except:
            pass

        self.pid = self.pssh = None

    def __del__(self):
        """
        Implement the "destructor" to help avoid orphaned ssh subprocesses.
        """
        try:
            if self.pssh != None:
                if sys.platform.lower().startswith( 'win' ):
                    self.pssh.terminate()
                else:
                    os.kill( self.pid, signal.SIGTERM )
        except:
            pass

        self.pid = self.pssh = None

    def _cancelTimer(self):
        """
        Internal method to cancel the timer (if active) in a thread safe way.
        """
        self.tlock.acquire()
        if self.timer != None:
            try: self.timer.cancel()
            except: pass
            self.timer = None
        self.tlock.release()

    def _timerKill(self):
        """
        This method is triggered by the timer thread when a timeout occurs.
        """
        if sys.platform.lower().startswith( 'win' ):
            self.pssh.terminate()
        else:
            os.kill( self.pid, signal.SIGTERM )
        self.tlock.acquire()
        self.timer = None
        self.tlock.release()


# code is read from a file and sent to the remote side along with the users
# remote script; it receives then carries out requests from the local side
mydir = os.path.dirname( os.path.abspath( __file__ ) )
fp = open( os.path.join( mydir, 'remotepython_utils.py' ), 'r' )
remote_utils = fp.read()
fp.close()


def which( program ):
    """
    Returns the absolute path to the given program name if found in PATH.
    If not found, None is returned.
    """
    if os.path.isabs( program ):
        return program

    pth = os.environ.get( 'PATH', None )
    if pth:
        for d in pth.split(':'):
            f = os.path.join( d, program )
            if not os.path.isdir(f) and os.access( f, os.X_OK ):
                return os.path.abspath( f )

    return None

if sys.version_info[0] < 3:
    # with python 2.x, files, pipes, and sockets work naturally
    
    def _BYTES_(s): return s
    def _STRING_(b): return b
    
    def print3( *args ):
        sys.stdout.write( ' '.join( [ str(x) for x in args ] ) + os.linesep )
        sys.stdout.flush()

    def stdout_write( s ):
        sys.stdout.write( s )

else:
    # with python 3.x, read/write to files, pipes, and sockets is tricky

    bytes_type = type( ''.encode() )

    def _BYTES_(s):
        if type(s) == bytes_type:
            return s
        return s.encode( 'ascii' )
    
    def _STRING_(b):
        if type(b) == bytes_type:
            return b.decode()
        return b
    
    def print3( *args ):
        eval( 'print( *args )' )
        sys.stdout.flush()

    def stdout_write( b ):
        sys.stdout.buffer.write( b )

