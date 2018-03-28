#!/usr/bin/env python

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
import unittest

# this file is expected to be imported from a script that was run
# within the tests directory (which is how all the tests are run)

test_filename = None
working_directory = None
vvtest = None
resultspy = None

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

    test_filename = os.path.abspath( argv[0] )

    optL,argL = getopt.getopt( argv[1:], 'p:sS' )

    optD = {}
    for n,v in optL:
        if n == '-p':
            pass
        elif n == '-s':
            use_this_ssh = 'fake'
        elif n == '-S':
            use_this_ssh = 'ssh'
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
        except:
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
        except:
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

nonqueued_platform_names = [ 'ceelan', 'Linux', 'iDarwin', 'Darwin' ]

def core_platform_name():
    """
    Returns either Darwin or Linux, depending on the current platform.
    """
    if os.uname()[0].lower().startswith( 'darwin' ):
        return 'Darwin'
    else:
        return 'Linux'


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
    except: pass


def run_cmd( cmd, directory=None ):
    """
    """
    if type(cmd) == type(''):
        print3( 'RUN:', cmd )
        cmdL = cmd.split()
    else:
        print3( 'RUN:', ' '.join( cmd ) )
        cmdL = cmd
    
    saved = None
    if directory:
        saved = os.getcwd()
        os.chdir( directory )

    pread, pwrite = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(pread)  # child does not read from parent
        os.dup2(pwrite, sys.stdout.fileno())
        os.dup2(pwrite, sys.stderr.fileno())
        os.execvpe( cmdL[0], cmdL, os.environ )
    os.close(pwrite)   # parent does not write to child
    out = ''
    while 1:
        buf = os.read(pread, 1024)
        if len(buf) == 0: break;
        out = out + buf
    os.close(pread)  # free up file descriptor
    pid,x = os.waitpid(pid,0)
    print3( out )
    
    if saved:
        os.chdir( saved )

    if os.WIFEXITED(x) and os.WEXITSTATUS(x) == 0:
        return True, out
    return False, out


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

def grep(out, pat):
    L = []
    repat = re.compile(pat)
    for line in out.split( os.linesep ):
        line = line.rstrip()
        if repat.search(line):
            L.append(line)
    return L

class vvtestRunner:
    """
    This runs a vvtest command line then captures the results as data
    members of this class.  They are

        out          : the stdout from running vvtest
        num_pass
        num_fail
        num_diff
        num_notrun
        num_timeout
        testdir      : such as TestResults.Linux
        platname     : such as Linux
    """

    def __init__(self, *args, **kwargs):
        ""
        cmd = vvtest
        for arg in args:
            cmd += ' '+arg

        self.run( cmd, **kwargs )

    def run(self, cmd, **kwargs):
        ""
        self.out = ''
        self.num_pass = 0
        self.num_fail = 0
        self.num_diff = 0
        self.num_notrun = 0
        self.num_timeout = 0
        self.testdir = ''
        self.platname = ''

        if 'directory' in kwargs:
            curdir = os.getcwd()
            os.chdir( kwargs['directory'] )

            ignore = kwargs.get( 'ignore_errors', False )

        try:
            ok,out = run_cmd( cmd )

            if not ok and not ignore:
                print3( out )
                raise Exception( 'vvtest command failed: '+cmd )

            self.out         = out
            self.num_pass    = numpass( out )
            self.num_fail    = numfail( out )
            self.num_diff    = numdiff( out )
            self.num_notrun  = numnotrun( out )
            self.num_timeout = numtimeout( out )
            self.testdir     = get_results_dir( out )
            self.platname    = platform_name( out )

        finally:
            if 'directory' in kwargs:
                os.chdir( curdir )


def run_vvtest( args='', ignore_errors=0, directory=None ):
    """
    Runs vvtest with the given argument string and returns
      ( command output, num pass, num diff, num fail, num notrun )
    The 'args' can be either a string or a list.
    If the exit status is not zero, an assertion is raised.
    """
    if directory:
        curdir = os.getcwd()
        os.chdir( directory )
    if type(args) == type(''):
        cmd = vvtest + ' ' + args
        x,out = run_cmd( cmd )
    else:
        cmd = ' '.join( [vvtest]+args )
        x,out = run_cmd( [vvtest]+args )
    if directory:
        os.chdir( curdir )
    if not x and not ignore_errors:
        raise Exception( "vvtest command failed: " + cmd )
    return out,numpass(out),numdiff(out),numfail(out),numnotrun(out)


def platform_name( test_out ):
    """
    After running the 'run_vvtest' command, give the output (the first return
    argument) to this function and it will return the platform name.  It
    throws an exception if the platform name cannot be determined.
    """
    platname = None
    for line in test_out.split( os.linesep ):
        line = line.strip()
        if line.startswith( 'Test directory:' ):
            L = line.split()
            if len(L) >= 3:
                L2 = L[2].split('.')
                if len(L2) >= 2:
                    platname = L2[1]

    return platname


def results_dir( pat=None ):
    """
    After running vvtest, this will return the TestResults directory.  If 'pat'
    is given, then the test results directory name that contains that pattern
    will be chosen.
    """
    for f in os.listdir('.'):
        if f[:12] == 'TestResults.':
            if pat == None or f.find( pat ) >= 0:
                return f
    return ''

def get_results_dir( out ):
    """
    """
    tdir = None

    for line in out.split( os.linesep ):
        if line.strip().startswith( 'Test directory:' ):
            tdir = line.split( 'Test directory:', 1 )[1].strip()

    return tdir


def remove_results():
    """
    Removes all TestResults from the current working directory.
    If a TestResults directory is a soft link, the link destination is
    removed as well.
    """
    for f in os.listdir('.'):
        if f[:12] == 'TestResults.':
            if os.path.islink(f):
                dest = os.readlink(f)
                print3( 'rm -r ' + dest )
                shutil.rmtree(dest)
                print3( 'rm ' + f )
                os.remove(f)
            else:
                print3( 'rm -r ' + f )
                shutil.rmtree( f, 1 )

# these have to be modified if/when the output format changes in vvtest
def check_pass(L): return len(L) >= 5 and L[2] == 'pass'
def check_fail(L): return len(L) >= 5 and L[2][:4] == 'fail'
def check_diff(L): return len(L) >= 5 and L[2] == 'diff'
def check_notrun(L): return len(L) >= 3 and L[1] == 'NotRun'
def check_timeout(L): return len(L) >= 5 and L[1] == 'TimeOut'

def numpass(out):
    cnt = 0
    mark = 0
    for line in out.split( os.linesep ):
        if mark:
            if line[:10] == "==========":
                mark = 0
            else:
                L = line.split()
                if check_pass(L):
                    cnt = cnt + 1
        elif line[:10] == "==========":
            mark = 1
            cnt = 0  # reset count so only the last cluster is considered
    return cnt

def numfail(out):
    cnt = 0
    mark = 0
    for line in out.split( os.linesep ):
        if mark:
            if line[:10] == "==========":
                mark = 0
            else:
                L = line.split()
                if check_fail(L):
                    cnt = cnt + 1
        elif line[:10] == "==========":
            mark = 1
            cnt = 0  # reset count so only the last cluster is considered
    return cnt

def numdiff(out):
    cnt = 0
    mark = 0
    for line in out.split( os.linesep ):
        if mark:
            if line[:10] == "==========":
                mark = 0
            else:
                L = line.split()
                if check_diff(L):
                    cnt = cnt + 1
        elif line[:10] == "==========":
            mark = 1
            cnt = 0  # reset count so only the last cluster is considered
    return cnt

def numnotrun(out):
    cnt = 0
    mark = 0
    for line in out.split( os.linesep ):
        if mark:
            if line[:10] == "==========":
                mark = 0
            else:
                L = line.split()
                if check_notrun(L):
                    cnt = cnt + 1
        elif line[:10] == "==========":
            mark = 1
            cnt = 0  # reset count so only the last cluster is considered
    return cnt

def numtimeout(out):
    cnt = 0
    mark = 0
    for line in out.split( os.linesep ):
        if mark:
            if line[:10] == "==========":
                mark = 0
            else:
                L = line.split()
                if check_timeout(L):
                    cnt = cnt + 1
        elif line[:10] == "==========":
            mark = 1
            cnt = 0  # reset count so only the last cluster is considered
    return cnt

def testlist(out):
    L = []
    mark = 0
    for line in out.split( os.linesep ):
        if mark:
            if line[:10] == "==========":
                mark = 0
            else:
                L.append( line.split() )
        elif line[:10] == "==========":
            mark = 1
            L = []  # reset list so only last cluster is considered
    return L

def greptestlist(out, pat):
    repat = re.compile(pat)
    L = []
    mark = 0
    for line in out.split( os.linesep ):
        if mark:
            if line[:10] == "==========":
                mark = 0
            elif repat.search( line.rstrip() ):
                L.append( line.rstrip() )
        elif line[:10] == "==========":
            mark = 1
            L = []  # reset list so only last cluster is considered
    return L

def testlines(out):
    L = []
    mark = 0
    for line in out.split( os.linesep ):
        if mark:
            if line.startswith( "==========" ):
                mark = 0
            else:
                L.append( line.rstrip() )
        elif line.startswith( "==========" ):
            mark = 1
            L = []  # reset list so only last cluster is considered
    return L

def testtimes(out):
    """
    Parses the test output and obtains the start time (seconds since epoch)
    and finish time of each test.  Returns a list of
          [ test execute dir, start time, end time ]
    """
    timesL = []

    fmt = '%Y %m/%d %H:%M:%S'
    for line in testlines(out):
        L = line.strip().split()
        try:
            s = time.strftime('%Y ')+L[4]+' '+L[5]
            t = time.mktime( time.strptime( s, fmt ) )
            e = t + int( L[3][:-1] )
            timesL.append( [ L[-1], t, e ] )
        except:
            pass

    return timesL
