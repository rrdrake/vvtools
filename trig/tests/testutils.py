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
import glob
import getopt
import unittest

# this file is expected to be imported from a script that was run
# within the tests directory (which is how all the tests are run)

test_filename = None
working_directory = None
vvtest = None
resultspy = None
use_this_ssh = 'fake'
remotepy = sys.executable

testsrcdir = os.path.dirname( os.path.abspath( sys.argv[0] ) )
sys.path.insert( 0, os.path.dirname( testsrcdir ) )


def initialize( argv ):
    """
    """
    global test_filename
    global working_directory
    global use_this_ssh
    global vvtest
    global resultspy
    global remotepy

    test_filename = os.path.abspath( argv[0] )

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

    working_directory = make_working_directory( test_filename )

    testdir = os.path.dirname( test_filename )

    srcdir = os.path.normpath( os.path.join( testdir, '..' ) )
    topdir = os.path.normpath( os.path.join( srcdir, '..' ) )

    vvtest = os.path.join( topdir, 'vvtest' )
    resultspy = os.path.join( topdir, 'results.py' )

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

    # for batch tests
    os.environ['VVTEST_BATCH_READ_INTERVAL'] = '5'
    os.environ['VVTEST_BATCH_READ_TIMEOUT'] = '15'
    os.environ['VVTEST_BATCH_SLEEP_LENGTH'] = '1'

    # force the results files to be written locally for testing;
    # it is used in vvtest when handling the --save-results option
    os.environ['TESTING_DIRECTORY'] = os.getcwd()



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
        line = line.rstrip( '\r' )
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
        fp.write( header.strip() + '\n' )
    for line in lineL:
        if pad != None: fp.write( line[pad:] + '\n' )
        else:           fp.write( line + '\n' )
    fp.close()

def writescript( fname, header, content ):
    """
    The 'header' is something like "#!/bin/sh" and 'content' is the same as
    for writefile().
    """
    writefile( fname, content, header )
    perm = stat.S_IMODE( os.stat(fname)[stat.ST_MODE] )
    perm = perm | stat.S_IXUSR
    try: os.chmod(fname, perm)
    except Exception: pass


def runout( cmd, raise_on_failure=False ):
    """
    """
    opts = {}
    if type(cmd) == type(''):
        opts['shell'] = True

    p = subprocess.Popen( cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               **opts )
    out = p.communicate()[0]
    try:
        s = out.decode()
        if sys.version_info[0] < 3:
            if isinstance( out, unicode ):
                out = out.encode( 'ascii', 'ignore' )
        else:
            out = out.decode()
    except Exception:
        pass

    x = p.returncode
    if raise_on_failure and x != 0:
        print3(out)
        raise Exception( 'command failed: ' + str(cmd) )

    return out

    # the below method redirects output to a file rather than a pipe;
    # sometimes the pipe method will hang if the child does not go away;
    # however, we would rather know if the child is being left around, so
    # this redirect method should only be used for debugging
    
    #fpout = open( 'runout.log', 'wb' )
    #opts = {}
    #if type(cmd) == type(''):
    #    opts['shell'] = True
    #p = subprocess.Popen( cmd, stdout=fpout.fileno(),
    #                           stderr=subprocess.STDOUT,
    #                           **opts )
    #p.wait()
    #fpout.close()
    #fpout = open( 'runout.log', 'rb' )
    #out = fpout.read()
    #fpout.close()
    #os.remove( 'runout.log' )
    #try:
    #    s = out.decode()
    #    out = s
    #except Exception:
    #    pass
    #return out


class Background:

    def __init__(self, cmd, outfile=None):
        """
        """
        self.cmd = cmd
        if outfile != None:
            fp = open( outfile, 'w' )
            self.p = subprocess.Popen( cmd, shell=True,
                                       stdout=fp.fileno(), 
                                       stderr=fp.fileno() )
            fp.close()
        else:
            self.p = subprocess.Popen( cmd, shell=True )

    def wait(self, timeout=30):
        """
        """
        if timeout == None:
            x = self.p.wait()
            return x
        for i in range(timeout):
            x = self.p.poll()
            if x != None:
                return x
            time.sleep(1)
        self.stop()
        return None
    
    def stop(self):
        try:
            os.kill( self.p.pid, signal.SIGINT )
            self.p.wait()
        except Exception:
            if hasattr( self.p, 'terminate' ):
                try: self.p.terminate()
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
    Redirect current process stdout & err to files, calls the given function
    with the given arguments, returns

        ( the output of the function, all stdout, all stderr )
    """
    global call_capture_id
    outid = call_capture_id
    call_capture_id += 1

    of = 'stdout'+str(outid)+'.log'
    ef = 'stderr'+str(outid)+'.log'

    redir = RedirectStdout( of, ef )
    try:
        rtn = func( *args, **kwargs )
    finally:
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


def rmallfiles( not_these=None ):
    for f in os.listdir("."):
        if not_these == None or not fnmatch.fnmatch( f, not_these ):
            if os.path.islink(f):
                os.remove(f)
            elif os.path.isdir(f):
                shutil.rmtree(f)
            else:
                os.remove(f)

def filegrep(fname, pat):
    L = []
    fp = open(fname,"r")
    repat = re.compile(pat)
    for line in fp.readlines():
        line = line.rstrip()
        if repat.search(line):
            L.append(line)
    fp.close()
    return L


def grepfiles( pattern, *paths ):
    ""
    # slight modification to the ends of the pattern in order to use
    # fnmatch to simulate basic shell style matching
    if pattern.startswith('^'):
        pattern = pattern[1:]
    else:
        pattern = '*'+pattern
    if pattern.endswith('$'):
        pattern = pattern[:-1]
    else:
        pattern += '*'

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


def grep(out, pat):
    L = []
    repat = re.compile(pat)
    for line in out.split( os.linesep ):
        line = line.rstrip()
        if repat.search(line):
            L.append(line)
    return L


def globfile( shell_pattern ):
    ""
    fL = glob.glob( shell_pattern )
    assert len( fL ) == 1, 'expected one file, not '+str(fL)
    return fL[0]


def readfile( fname ):
    """
    Read and return the contents of the given filename.
    """
    fp = open(fname,'r')
    try:
        s = fp.read()
    finally:
        fp.close()
    return _STRING_(s)


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


def get_process_list():
    """
    Return a python list of all processes on the current machine, where each
    entry is a length three list of form

        [ user, pid, ppid ]
    """
    plat = sys.platform.lower()
    if plat.startswith( 'darwin' ):
        cmd = 'ps -o user,pid,ppid'
    else:
        cmd = 'ps -o user,pid,ppid'
    cmd += ' -e'

    p = subprocess.Popen( 'ps -o user,pid,ppid -e',
                          shell=True, stdout=subprocess.PIPE )
    sout,serr = p.communicate()

    sout = _STRING_(sout)

    # strip off first non-empty line (the header)

    first = True
    lineL = []
    for line in sout.split( os.linesep ):
        line = line.strip()
        if line:
            if first:
                first = False
            else:
                L = line.split()
                if len(L) == 3:
                    try:
                        L[1] = int(L[1])
                        L[2] = int(L[2])
                    except Exception:
                        pass
                    else:
                        lineL.append( L )

    return lineL


def find_process_in_list( proclist, pid ):
    """
    Searches for the given 'pid' in 'proclist' (which should be the output
    from get_process_list().  If not found, None is returned.  Otherwise a
    list

        [ user, pid, ppid ]
    """
    for L in proclist:
        if pid == L[1]:
            return L
    return None


uniq_id = 0
filename_to_module_map = {}

def create_module_from_filename( fname ):
    ""
    global uniq_id

    fname = os.path.normpath( os.path.abspath( fname ) )

    if fname in filename_to_module_map:

        mod = filename_to_module_map[fname]

    else:

        modname = os.path.splitext(os.path.basename(fname))[0]+str(uniq_id)
        uniq_id += 1

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
