#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import traceback
import stat
import binascii
import subprocess


# This code is sent to the remote side along with the users remote script.
# It receives then carries out requests from the local side.
#
# It also defines utility functions:
#
#   print3             : a Python 2.x and 3.x compatible print function
#   background_command : run a shell command in the background
#   runout             : run a shell command and return its output
#   processes          : gather process information
#   evaluate           : execute a list of python statements
#   save_object,
#   get_object,
#   pop_object         : object persistence mechanism
#   _BYTES_, _STRING_  : convert to bytes or strings (Python 2 vs. 3)


try:
  import StringIO
  class_StringIO = StringIO.StringIO
except:
  import io
  class_StringIO = io.StringIO

#############################################################################

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
                    fp = open( os.path.expanduser(fname), 'wb' )
                    fp.close() ; fp = None
                    rtn = True
                
                elif sw == 'PUT':
                    # recv file from local side, and stream into a file
                    nreads, fname, mt, at, fm = eval( val.strip() )
                    fname = os.path.expanduser(fname)
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
                    fname = os.path.expanduser( fname )
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
                    fname = os.path.expanduser( fname )
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

#############################################################################

_background_template = '''

import os, sys, time, subprocess, signal

cmd = COMMAND
timeout = TIMEOUT_VALUE

nl=os.linesep
ofp=sys.stdout
ofp.write( "Start Date: " + time.ctime() + nl )
ofp.write( "Parent PID: " + str(os.getpid()) + nl )
ofp.write( "Subcommand: " + str(cmd) + nl )
ofp.write( "Directory : " + os.getcwd() + nl+nl )
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


def background_command( cmd, redirect, timeout=None, chdir=None ):
    "Run command (list or string) in the background and redirect to a file."
    pycode = _background_template.replace( 'COMMAND', repr(cmd) )
    pycode = pycode.replace( 'TIMEOUT_VALUE', repr(timeout) )
    cmdL = [ sys.executable, '-c', pycode ]
    
    # hexifying the code avoids newlines, but increases the size
    #pycmd = 'import sys, binascii; ' + \
    #        's = "' + binascii.b2a_hex(pycode) + '"; ' + \
    #        'eval( compile( binascii.a2b_hex(s), "<string>", "exec" ) )'
    #cmdL = [ sys.executable, '-c', pycmd ]

    if chdir != None:
        cwd = os.getcwd()
        os.chdir( os.path.expanduser(chdir) )

    try:
        fpout = open( os.path.expanduser(redirect), 'w' )
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

    finally:
        if chdir != None:
            os.chdir( cwd )

    fpout.close()
    fpin.close()

    return p.pid

#############################################################################

def get_machine_info():
    "Return user name, system name, network name, and uptime as a string."
    usr = os.getuid()
    try:
        import getpass
        usr = getpass.getuser()
    except:
        pass
    rtn = 'user='+usr

    L = os.uname()
    rtn += ' sysname='+L[0]+' nodename='+L[1]

    upt = '?'
    try:
        x,out = runout( 'uptime' )
        upt = out.strip()
    except:
        pass
    rtn += ' uptime='+upt

    return rtn


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

#############################################################################

def evaluate( *statements ):
    "Issue a list of python statements.  Cannot have embedded newlines."
    if len(statements) > 0:
        global _evaluate_function_
        cs = 'def _evaluate_function_():\n'
        cs += '\n'.join( [ '  '+s for s in statements ] ) + '\n'
        cobj = compile( cs, '<remote evaluate>', 'exec' )
        eval( cobj, globals() )
        return _evaluate_function_()

#############################################################################

_objmap_ = {}

def save_object( obj ):
    "Saves the given object in a global map and returns the object id."
    global _objmap_
    _objmap_[ id(obj) ] = obj
    return id(obj)

def get_object( obj_id ):
    "Retrieves an object given its id.  Unknown ids raise an Exception."
    global _objmap_
    if obj_id in _objmap_:
        return _objmap_[obj_id]
    raise Exception( 'Object id "'+str(obj_id)+'" not saved in object map' )

def pop_object( obj_id ):
    "Gets an object given its id, removes it from the map, and returns it."
    global _objmap_
    obj = _objmap_.pop( obj_id )
    return obj

#############################################################################

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
