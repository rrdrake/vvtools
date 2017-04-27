#!/usr/bin/env python

import os, sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import traceback
import stat
import binascii
import subprocess


# this code is sent to the remote side along with the users remote script;
# it receives then carries out requests from the local side


try:
  import StringIO
  class_StringIO = StringIO.StringIO
except:
  import io
  class_StringIO = io.StringIO


def _ping():
    return 'pong'


def _listener():
    "The remote side entry point.  It reads from sys.stdin to handle requests."
    
    while True:
        byteline = sys.stdin.readline()
        if not byteline:
            break
        line = _STRING_( byteline )
        sw,val = line.strip().split( ':', 1 )
        if sw in [ 'CAL', 'WOK', 'PUT', 'FSZ', 'GET' ]:
            fp = None
            try:
                if sw == 'CAL':
                    # make a function call
                    nm,args,kwargs = eval( val.strip() )
                    rtn = eval( nm+'( *args, **kwargs )' )
                
                elif sw == 'WOK':
                    # check write ok;  open file for write then close
                    fname = eval( val.strip() )
                    fp = open( fname, 'wb' )
                    fp.close() ; fp = None
                    rtn = True
                
                elif sw == 'PUT':
                    # recv file from local side, and stream into a file
                    nreads, fname, mt, at, fm = eval( val.strip() )
                    fp = open( fname, 'wb' )
                    i = 0 ; sz = 0
                    while i < nreads:
                        buf = sys.stdin.read( int( sys.stdin.readline() ) )
                        #fp.write( binascii.rledecode_hqx(
                        #            binascii.a2b_hqx( _STRING_( buf ) ) ) )
                        # python 3.2.5 a2b_hex does not like strings
                        #fp.write( binascii.a2b_hex( _STRING_( buf ) ) )
                        fp.write( binascii.a2b_hex( _BYTES_(buf) ) )
                        sz += len(buf)
                        i += 1
                    fp.close() ; fp = None
                    if mt != None:
                        os.utime( fname, (at,mt) )
                        os.chmod( fname, fm )
                    rtn = sz
                
                elif sw == 'FSZ':
                    # send back file size prior to file get
                    fname, preserve = eval( val.strip() )
                    mt = at = fm = None
                    if preserve:
                        mt = os.path.getmtime( fname )
                        at = os.path.getatime( fname )
                        fm = stat.S_IMODE( os.stat(fname)[stat.ST_MODE] )
                    sz = os.path.getsize( fname )
                    fp = open( fname, 'rb' )
                    fp.close() ; fp = None
                    rtn = [ sz, mt, at, fm ]
                
                elif sw == 'GET':
                    # send file from here to the local side
                    bufsize, n, r, fname = eval( val.strip() )
                    nreads = n
                    if r > 0: nreads += 1
                    fp = open( fname, 'rb' )
                    i = 0
                    while i < n:
                        buf = binascii.b2a_hex( fp.read( bufsize ) )
                        stdout_write( _BYTES_( '%10d'%(len(buf),) ) )
                        stdout_write( buf )
                        i += 1
                    if r > 0:
                        buf = binascii.b2a_hex( fp.read( r ) )
                        stdout_write( _BYTES_( '%10d'%(len(buf),) ) )
                        stdout_write( buf )
                    fp.close() ; fp = None
                    rtn = None
            
            except KeyboardInterrupt:
                raise
            except:
                sio = class_StringIO()
                traceback.print_exc( file=sio )
                if fp != None:
                    try: fp.close()
                    except: pass
                msg = 'EXC: '+repr( sio.getvalue() )
                stdout_write( _BYTES_( msg + os.linesep ) )
                sys.stdout.flush()
                sio.close()
            else:
                stdout_write( _BYTES_( 'RTN: '+repr( rtn ) + os.linesep ) )
                sys.stdout.flush()
        
        elif sw == 'XIT':
            break


_background_template = '''

import os, sys, time, subprocess, signal

cmd = COMMAND
timeout = TIMEOUT_VALUE

nl=os.linesep
ofp=sys.stdout
ofp.write( "Start Date: " + time.ctime() + nl )
ofp.write( "Parent PID: " + str(os.getpid()) + nl )
ofp.write( "Subcommand: " + str(cmd) + nl+nl )
ofp.flush()

argD = {}

if type(cmd) == type(''):
  argD['shell'] = True

if sys.platform.lower().startswith('win'):
  def kill_process( po ):
    po.terminate()

else:
  # use preexec_fn to put the child into its own process group
  # (to more easily kill it and all its children)
  argD['preexec_fn'] = lambda: os.setpgid( os.getpid(), os.getpid() )

  def kill_process( po ):
    # send all processes in the process group a SIGTERM
    os.kill( -po.pid, signal.SIGTERM )
    # wait for child process to complete
    for i in range(10):
      x = po.poll()
      if x != None:
        break
      time.sleep(1)
    if x == None:
      # child did not die - try to force it
      os.kill( po.pid, signal.SIGKILL )
      time.sleep(1)
      po.poll()

t0=time.time()

p = subprocess.Popen( cmd, **argD )

try:
  if timeout != None:
    while True:
      x = p.poll()
      if x != None:
        break
      if time.time() - t0 > timeout:
        kill_process(p)
        x = None  # mark as timed out
        break
      time.sleep(5)
  else:
    x = p.wait()

except:
  kill_process(p)
  raise

ofp.write( nl + "Subcommand exit: " + str(x) + nl )
ofp.write( "Finish Date: " + time.ctime() + nl )
ofp.flush()
'''.lstrip()


def background_command( cmd, redirect, timeout=None, workdir=None ):
    "Run command (list or string) in the background and redirect to a file."
    pycode = _background_template.replace( 'COMMAND', repr(cmd) )
    pycode = pycode.replace( 'TIMEOUT_VALUE', repr(timeout) )
    cmdL = [ sys.executable, '-c', pycode ]
    
    # hexifying the code avoids newlines, but increases the size
    #pycmd = 'import sys, binascii; ' + \
    #        's = "' + binascii.b2a_hex(pycode) + '"; ' + \
    #        'eval( compile( binascii.a2b_hex(s), "<string>", "exec" ) )'
    #cmdL = [ sys.executable, '-c', pycmd ]

    if workdir != None:
        cwd = os.getcwd()
        os.chdir( workdir )

    fpout = open( redirect, 'w' )
    try:
        fpin = open( os.devnull, 'r' )
    except:
        fpout.close()
        raise

    try:
        argD = { 'stdin':  fpin.fileno(),
                 'stdout': fpout.fileno(),
                 'stderr': subprocess.STDOUT }
        if not sys.platform.lower().startswith('win'):
            # place child in its own process group to help avoid getting
            # killed when the parent process exits
            argD['preexec_fn'] = lambda: os.setpgid( os.getpid(), os.getpid() )
        p = subprocess.Popen( cmdL, **argD )
    except:
        fpout.close()
        fpin.close()
        raise

    fpout.close()
    fpin.close()

    if workdir != None:
        os.chdir( cwd )

    return p.pid


def runout( cmd, include_stderr=False ):
    "Run a command and return the exit status & output as a pair."
    
    argD = {}

    if type(cmd) == type(''):
        argD['shell'] = True

    fp = None
    argD['stdout'] = subprocess.PIPE
    if include_stderr:
        argD['stderr'] = subprocess.STDOUT
    else:
        fp = open( os.devnull, 'w' )
        argD['stderr'] = fp.fileno()

    try:
        p = subprocess.Popen( cmd, **argD )
        out,err = p.communicate()
    except:
        fp.close()
        raise
    
    if fp != None:
        fp.close()

    x = p.returncode

    if type(out) != type(''):
        out = out.decode()  # convert bytes to a string

    return x, out


def processes( pid=None, user=None, showall=False, fields=None, noheader=True ):
    "The 'fields' defaults to 'user,pid,ppid,etime,pcpu,vsz,args'."
    
    plat = sys.platform.lower()
    if fields == None:
        fields = 'user,pid,ppid,etime,pcpu,vsz,args'
    if plat.startswith( 'darwin' ):
        cmd = 'ps -o ' + fields.replace( 'args', 'command' )
    elif plat.startswith( 'sunos' ):
        cmd = '/usr/bin/ps -o ' + fields
    else:
        cmd = 'ps -o ' + fields
    
    if pid != None:
        cmd += ' -p '+str(pid)
    elif user:
        cmd += ' -u '+user
    elif showall:
        cmd += ' -e'

    x,out = runout( cmd )

    if noheader:
        # strip off first non-empty line
        out = out.strip() + os.linesep
        i = 0
        while i < len(out):
            if out[i:].startswith( os.linesep ):
                out = out[i:].lstrip()
                break
            i += 1
    
    out = out.strip()
    if out:
        out += os.linesep

    return out


def get_user_id():
    return os.getuid()

def get_user_name():
    import getpass
    return getpass.getuser()


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


def DEBUG( *args ):
    dbgfp = open( 'debug.log', 'ab' )
    dbgfp.write( _BYTES_( repr(args) + os.linesep ) )
    dbgfp.close()
