#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import re
import shutil
import stat
import fnmatch
import time
import subprocess
import signal
import shlex
import pipes
import getopt
import random
import string
import glob
import traceback
import unittest


working_directory = None
use_this_ssh = 'fake'
remotepy = sys.executable


def initialize( argv ):
    ""
    global working_directory
    global use_this_ssh
    global remotepy

    test_filename = os.path.abspath( argv[0] )
    working_directory = make_working_directory( test_filename )

    optL,argL = getopt.getopt( argv[1:], 'p:sSr:' )

    optD = {}
    for n,v in optL:
        if n == '-p':
            pass
        elif n == '-s':
            use_this_ssh = 'fake'
        elif n == '-S':
            use_this_ssh = 'ssh'
        elif n == '-r':
            remotepy = v
        optD[n] = v


    return optD, argL


def run_test_cases( argv, test_module ):
    """
    """
    optD, argL = initialize( argv )

    loader = unittest.TestLoader()

    tests = TestSuiteAccumulator( loader, test_module )

    if len(argL) == 0:
        tests.addModuleTests()

    else:
        test_classes = get_TestCase_classes( test_module )
        for arg in argL:
            if not tests.addTestCase( arg ):
                # not a TestClass name; look for individual tests
                count = 0
                for name in test_classes.keys():
                    if tests.addTestCase( name+'.'+arg ):
                        count += 1
                if count == 0:
                    raise Exception( 'No tests found for "'+arg+'"' )

    # it would be nice to use the 'failfast' argument (defaults to False), but
    # not all versions of python have it
    runner = unittest.TextTestRunner( stream=sys.stdout,
                                      verbosity=2 )

    results = runner.run( tests.getTestSuite() )
    if len(results.errors) + len(results.failures) > 0:
        sys.exit(1)


class TestSuiteAccumulator:

    def __init__(self, loader, test_module):
        self.loader = loader
        self.testmod = test_module
        self.suite = unittest.TestSuite()

    def getTestSuite(self):
        ""
        return self.suite

    def addModuleTests(self):
        ""
        suite = self.loader.loadTestsFromModule( self.testmod )
        self.suite.addTest( suite )

    def addTestCase(self, test_name):
        ""
        haserrors = hasattr( self.loader, 'errors' )
        if haserrors:
            # starting in Python 3.5, the loader will not raise an exception
            # if a test class or test case is not found; rather, the loader
            # accumulates erros in a list; clear it first...
            del self.loader.errors[:]

        try:
            suite = self.loader.loadTestsFromName( test_name, module=self.testmod )
        except Exception:
            return False

        if haserrors and len(self.loader.errors) > 0:
            return False

        self.suite.addTest( suite )
        return True


def get_TestCase_classes( test_module ):
    """
    Searches the given module for classes that derive from unittest.TestCase,
    and returns a map from the class name as a string to the class object.
    """
    tcD = {}
    for name in dir(test_module):
        obj = getattr( test_module, name )
        try:
            if issubclass( obj, unittest.TestCase ):
                tcD[name] = obj
        except Exception:
            pass

    return tcD


def setup_test( cleanout=True ):
    """
    """
    print3()
    os.chdir( working_directory )

    if cleanout:
        rmallfiles()
        time.sleep(1)


def make_working_directory( test_filename ):
    """
    directly executing a test script can be done but rm -rf * is performed;
    to avoid accidental removal of files, cd into a working directory
    """
    d = os.path.join( 'tmpdir_'+os.path.basename( test_filename ) )
    if not os.path.exists(d):
        os.mkdir(d)
        time.sleep(1)
    return os.path.abspath(d)


##########################################################################

def print3( *args ):
    sys.stdout.write( ' '.join( [ str(x) for x in args ] ) + os.linesep )
    sys.stdout.flush()


def writefile( fname, content, header=None ):
    """
    Open and write 'content' to file 'fname'.  The content is modified to
    remove leading spaces on each line.  The first non-empty line is used
    to determine how many spaces to remove.
    """
    # determine indent pad of the given content
    pad = None
    lineL = []
    for line in content.split( '\n' ):
        line = line.strip( '\r' )
        lineL.append( line )
        if pad == None and line.strip():
            for i in range(len(line)):
                if line[i] != ' ':
                    pad = i
                    break
    # make the directory to contain the file, if not already exist
    d = os.path.dirname( fname )
    if os.path.normpath(d) not in ['','.']:
        if not os.path.exists(d):
          os.makedirs(d)
    # open and write contents
    fp = open( fname, 'w' )
    if header != None:
        fp.write( header.strip() + os.linesep + os.linesep )
    for line in lineL:
        if pad != None: fp.write( line[pad:] + os.linesep )
        else:           fp.write( line + os.linesep )
    fp.close()


def writescript( fname, content ):
    """
    """
    if content[0] == '\n':
        # remove the first line if it is empty
        content = content[1:]
    writefile( fname, content )
    perm = stat.S_IMODE( os.stat(fname)[stat.ST_MODE] )
    perm = perm | stat.S_IXUSR
    try: os.chmod(fname, perm)
    except Exception: pass


def runcmd( cmd, chdir=None, raise_on_error=True, print_output=True ):
    ""
    dstr = ''
    if chdir:
        dstr = 'cd '+chdir+' && '
        cwd = os.getcwd()

    print3( 'RUN: '+dstr+cmd )

    if chdir:
        os.chdir( chdir )

    try:
        pop = subprocess.Popen( cmd, shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT )

        out,err = pop.communicate()

        x = pop.returncode

        if sys.version_info[0] >= 3:
            out = out.decode()

    finally:
        if chdir:
            os.chdir( cwd )

    if print_output:
        print3( out )

    assert x == 0 or not raise_on_error, 'runcmd failed: exit='+str(x)

    return x,out


def run_redirect( cmd, redirect_filename ):
    """
    Executes the given command as a child process, waits for it, and returns
    True if the exit status is zero.
    
    The 'redirect_filename' string is the filename to redirect the output.

    If 'cmd' is a string, then the /bin/sh shell is used to interpret the
    command.  If 'cmd' is a python list, then the shell is not used and each
    argument is sent verbatim to the program being executed.
    """
    append = False

    outfp = None
    fdout = None
    if type(redirect_filename) == type(2):
        fdout = redirect_filename
    elif type(redirect_filename) == type(''):
        if append:
            outfp = open( redirect_filename, "a" )
        else:
            outfp = open( redirect_filename, "w" )
        fdout = outfp.fileno()

    if type(cmd) == type(''):
        scmd = cmd
    else:
        scmd = shell_escape( cmd )
    if outfp == None:
        sys.stdout.write( scmd + '\n' )
    else:
        sys.stdout.write( scmd + ' > ' + redirect_filename + '\n' )
    sys.stdout.flush()
    
    # build the arguments for subprocess.Popen()
    argD = {}

    if type(cmd) == type(''):
        argD['shell'] = True
    
    argD['bufsize'] = -1  # use system buffer size (is this needed?)

    if fdout != None:
        argD['stdout'] = fdout
        argD['stderr'] = subprocess.STDOUT

    p = subprocess.Popen( cmd, **argD )

    x = p.wait()

    if outfp != None:
        outfp.close()
    outfp = None
    fdout = None

    return x == 0


class RedirectStdout:
    """
    A convenience class to redirect the current process's stdout to a file.
    Constructor initiates the redirection, close() stops it.
    """

    def __init__(self, filename, stderr_filename=None):
        """
        If 'stderr_filename' is not None, stderr goes to that filename.
        """
        self.filep = open( filename, 'w' )
        self.save_stdout_fd = os.dup(1)
        os.dup2( self.filep.fileno(), 1 )
        self.filep2 = None
        if stderr_filename:
            self.filep2 = open( stderr_filename, 'w' )
            self.save_stderr_fd = os.dup(2)
            os.dup2( self.filep2.fileno(), 2 )

    def close(self):
        ""
        sys.stdout.flush()
        os.dup2( self.save_stdout_fd, 1 )
        os.close( self.save_stdout_fd )
        self.filep.close()
        if self.filep2 != None:
            sys.stderr.flush()
            os.dup2( self.save_stderr_fd, 2 )
            os.close( self.save_stderr_fd )
            self.filep2.close()


call_capture_id = 0

def call_capture_output( func, *args, **kwargs ):
    """
    Redirect current process stdout & err to files, call the given function
    with the given arguments, return

        ( output of the function, all stdout, all stderr )

    Exceptions are caught and the traceback is captured in the stderr output.
    This includes SystemExit, but not KeyboardInterrupt.
    """
    global call_capture_id
    outid = call_capture_id
    call_capture_id += 1

    of = 'stdout'+str(outid)+'.log'
    ef = 'stderr'+str(outid)+'.log'

    redir = RedirectStdout( of, ef )
    rtn = None
    try:
        rtn = func( *args, **kwargs )
    except Exception:
        traceback.print_exc()
    except SystemExit:
        traceback.print_exc()
    except:
        redir.close()
        raise

    redir.close()
    time.sleep(1)

    return rtn, readfile(of), readfile(ef)


def shell_escape( cmd ):
    """
    Returns a string with shell special characters escaped so they are not
    interpreted by the shell.

    The 'cmd' can be a string or a python list.
    """
    if type(cmd) == type(''):
        return ' '.join( [ pipes.quote(s) for s in shlex.split( cmd ) ] )
    return ' '.join( [ pipes.quote(s) for s in cmd ] )


def get_ssh_pair( fake_ssh_pause=None, connect_failure=False, uptime=None ):
    """
    Returns a pair ( ssh program, ssh machine ).
    """
    if use_this_ssh == 'ssh' and fake_ssh_pause == None and \
                                 connect_failure == False and \
                                 uptime == None:
        sshprog = which( 'ssh' )
        import socket
        sshmach = socket.gethostname()

    elif uptime != None:
        # make the fake ssh session to die after 'uptime' seconds
        writescript( 'fakessh', """
            #!"""+sys.executable+""" -E
            import os, sys, getopt, time, subprocess, signal
            optL,argL = getopt.getopt( sys.argv[1:], 'xTv' )
            mach = argL.pop(0)  # remove the machine name
            time.sleep( 1 )
            p = subprocess.Popen( ['/bin/bash', '-c', ' '.join( argL )] )
            t0 = time.time()
            while time.time() - t0 < """+str(uptime)+""":
                x = p.poll()
                if x != None:
                    break
                time.sleep(1)
            if x == None:
                if hasattr( p, 'terminate' ):
                    p.terminate()
                else:
                    os.kill( p.pid, signal.SIGTERM )
                    x = p.wait()
                x = 1
            sys.exit( x )
            """ )
        sshprog = os.path.abspath( 'fakessh' )
        sshmach = 'sparky'

    else:
        st = str(1)
        if fake_ssh_pause != None:
            st = str(fake_ssh_pause)
        writescript( 'fakessh', """
            #!"""+sys.executable+""" -E
            import os, sys, getopt, time, pipes
            optL,argL = getopt.getopt( sys.argv[1:], 'xTv' )
            mach = argL.pop(0)  # remove the machine name
            time.sleep( """+st+""" )
            if """+repr(connect_failure)+""":
                sys.stderr.write( "Fake connection falure to "+mach+os.linesep )
                sys.exit(1)
            os.execl( '/bin/bash', '/bin/bash', '-c', ' '.join( argL ) )
            """ )
        sshprog = os.path.abspath( 'fakessh' )
        sshmach = 'sparky'

    return sshprog, sshmach


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


def rmallfiles( not_these=None ):
    ""
    for f in os.listdir("."):
        if not_these == None or not fnmatch.fnmatch( f, not_these ):
            fault_tolerant_remove( f )


def random_string( numchars=8 ):
    ""
    seq = string.ascii_letters + string.digits
    cL = [ random.choice( seq ) for _ in range(numchars) ]
    return ''.join( cL )


def fault_tolerant_remove( path, num_attempts=5 ):
    ""
    dn,fn = os.path.split( path )

    rmpath = os.path.join( dn, 'remove_'+fn + '_'+ random_string() )

    os.rename( path, rmpath )

    for i in range( num_attempts ):
        try:
            if os.path.islink( rmpath ):
                os.remove( rmpath )
            elif os.path.isdir( rmpath ):
                shutil.rmtree( rmpath )
            else:
                os.remove( rmpath )
            break
        except Exception:
            pass

        time.sleep(1)


def readfile( filename ):
    ""
    fp = open( filename, 'r' )
    try:
        buf = fp.read()
    finally:
        fp.close()
    return buf


def adjust_shell_pattern_to_work_with_fnmatch( pattern ):
    """
    slight modification to the ends of the pattern in order to use
    fnmatch to simulate basic shell style matching
    """
    if pattern.startswith('^'):
        pattern = pattern[1:]
    else:
        pattern = '*'+pattern

    if pattern.endswith('$'):
        pattern = pattern[:-1]
    else:
        pattern += '*'

    return pattern


def grepfiles( shell_pattern, *paths ):
    ""
    pattern = adjust_shell_pattern_to_work_with_fnmatch( shell_pattern )

    matchlines = []

    for path in paths:

        for gp in glob.glob( path ):

            fp = open( gp, "r" )

            try:
                for line in fp:
                    line = line.rstrip( os.linesep )
                    if fnmatch.fnmatch( line, pattern ):
                        matchlines.append( line )

            finally:
                fp.close()

    return matchlines


def greplines( shell_pattern, string_output ):
    ""
    pattern = adjust_shell_pattern_to_work_with_fnmatch( shell_pattern )

    matchlines = []

    for line in string_output.splitlines():
        if fnmatch.fnmatch( line, pattern ):
            matchlines.append( line )

    return matchlines


def globfile( shell_pattern ):
    ""
    fL = glob.glob( shell_pattern )
    assert len( fL ) == 1, 'expected one file, not '+str(fL)
    return fL[0]


def findfiles( pattern, topdir, *topdirs ):
    ""
    fS = set()

    dL = []
    for top in [topdir]+list(topdirs):
        dL.extend( glob.glob( top ) )

    for top in dL:
        for dirpath,dirnames,filenames in os.walk( top ):
            for f in filenames:
                if fnmatch.fnmatch( f, pattern ):
                    fS.add( os.path.join( dirpath, f ) )

    fL = list( fS )
    fL.sort()

    return fL


def first_path_segment( path ):
    ""
    if os.path.isabs( path ):
        return os.sep
    else:
        p = path
        while True:
            d,b = os.path.split( p )
            if d and d != '.':
                p = d
            else:
                return b


def list_all_paths( rootpath ):
    ""
    pathset = set()

    for dirpath,dirnames,filenames in os.walk( rootpath ):

        pathset.add( dirpath )

        for f in filenames:
            p = os.path.join( dirpath, f )
            if not os.path.islink(p):
                pathset.add(p)

    pL = list( pathset )
    pL.sort()

    return pL


def list_all_directories( rootpath ):
    ""
    pathset = set()

    for dirpath,dirnames,filenames in os.walk( rootpath ):
        pathset.add( dirpath )

    pL = list( pathset )
    pL.sort()

    return pL


class change_directory:
    """
    with change_directory( 'subdir' ):
        pass
    """

    def __init__(self, directory):
        ""
        self.cwd = os.getcwd()
        self.directory = directory

    def __enter__(self):
        ""
        if self.directory:
            assert os.path.isdir( self.directory )
            os.chdir( self.directory )

    def __exit__(self, type, value, traceback):
        ""
        os.chdir( self.cwd )


def has_owner_execute( path ):
    ""
    fm = stat.S_IMODE( os.stat(path)[stat.ST_MODE] )
    return int( fm & stat.S_IXUSR ) != 0


def has_no_group_permissions( path ):
    ""
    fm = stat.S_IMODE( os.stat(path)[stat.ST_MODE] )
    return int( fm & stat.S_IRWXG ) == 0

def has_group_sticky( path ):
    ""
    fm = stat.S_IMODE( os.stat(path)[stat.ST_MODE] )
    return int( fm & stat.S_ISGID ) != 0

def has_group_read( path ):
    ""
    fm = stat.S_IMODE( os.stat(path)[stat.ST_MODE] )
    return int( fm & stat.S_IRGRP ) != 0

def has_group_write( path ):
    ""
    fm = stat.S_IMODE( os.stat(path)[stat.ST_MODE] )
    return int( fm & stat.S_IWGRP ) != 0

def has_group_execute( path ):
    ""
    fm = stat.S_IMODE( os.stat(path)[stat.ST_MODE] )
    return int( fm & stat.S_IXGRP ) != 0


def has_no_world_permissions( path ):
    ""
    fm = stat.S_IMODE( os.stat(path)[stat.ST_MODE] )
    return int( fm & stat.S_IRWXO ) == 0

def has_world_read( path ):
    ""
    fm = stat.S_IMODE( os.stat(path)[stat.ST_MODE] )
    return int( fm & stat.S_IROTH ) != 0

def has_world_write( path ):
    ""
    fm = stat.S_IMODE( os.stat(path)[stat.ST_MODE] )
    return int( fm & stat.S_IWOTH ) != 0

def has_world_execute( path ):
    ""
    fm = stat.S_IMODE( os.stat(path)[stat.ST_MODE] )
    return int( fm & stat.S_IXOTH ) != 0


def probe_for_two_different_groups():
    ""
    x,out = runcmd( 'groups' )
    grp1,grp2 = out.strip().split()[:2]
    assert grp1 and grp2 and grp1 != grp2
    return grp1,grp2


def get_file_group( path ):
    ""
    import grp
    gid = os.stat( path ).st_gid
    ent = grp.getgrgid( gid )
    return ent[0]


module_uniq_id = 0
filename_to_module_map = {}

def create_module_from_filename( fname ):
    ""
    global module_uniq_id

    fname = os.path.normpath( os.path.abspath( fname ) )

    if fname in filename_to_module_map:

        mod = filename_to_module_map[fname]

    else:

        modname = os.path.splitext(os.path.basename(fname))[0]+str(module_uniq_id)
        module_uniq_id += 1

        if sys.version_info[0] < 3 or sys.version_info[1] < 5:
            import imp
            fp = open( fname, 'r' )
            try:
                spec = ('.py','r',imp.PY_SOURCE)
                mod = imp.load_module( modname, fp, fname, spec )
            finally:
                fp.close()
        else:
            import importlib
            import importlib.machinery as impmach
            import importlib.util as imputil
            loader = impmach.SourceFileLoader( modname, fname )
            spec = imputil.spec_from_file_location( modname, fname, loader=loader )
            mod = imputil.module_from_spec(spec)
            spec.loader.exec_module(mod)

        filename_to_module_map[ fname ] = mod

    return mod


if sys.version_info[0] < 3:
    # with python 2.x, files, pipes, and sockets work naturally
    def _BYTES_(s): return s
    def _STRING_(b): return b

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
