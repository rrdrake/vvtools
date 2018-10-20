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
import unittest

# this file is expected to be imported from a script that was run
# within the tests directory (which is how all the tests are run)

test_filename = None
working_directory = None
vvtest = None
resultspy = None

testsrcdir = os.path.dirname( os.path.abspath( sys.argv[0] ) )
sys.path.insert( 0, os.path.dirname( os.path.dirname( testsrcdir ) ) )


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


def shell_escape( cmd ):
    """
    Returns a string with shell special characters escaped so they are not
    interpreted by the shell.

    The 'cmd' can be a string or a python list.
    """
    if type(cmd) == type(''):
        return ' '.join( [ pipes.quote(s) for s in shlex.split( cmd ) ] )
    return ' '.join( [ pipes.quote(s) for s in cmd ] )


def launch_vvtest_then_terminate_it( *cmd_args, **options ):
    ""
    signum = options.pop( 'signum', signal.SIGTERM )
    seconds_before_signaling = options.pop( 'seconds_before_signaling',4 )
    logfilename = options.pop( 'logfilename', 'run.log' )
    batch = options.pop( 'batch', False )

    cmd = vvtest_command_line( *cmd_args, batch=batch )

    fp = open( logfilename, 'w' )
    try:
        print3( cmd )
        pop = subprocess.Popen( cmd, shell=True,
                    stdout=fp.fileno(), stderr=fp.fileno(),
                    preexec_fn=lambda:os.setpgid(os.getpid(),os.getpid()) )

        time.sleep( seconds_before_signaling )

        os.kill( -pop.pid, signum )

        pop.wait()

    finally:
        fp.close()

        return readfile( logfilename )


def interrupt_test_hook( batch=False, count=None, signum=None, qid=None ):
    ""
    valL = []
    if count != None:
        valL.append( "count="+str(count) )
    if signum != None:
        valL.append( "signum="+signum )
    if qid != None:
        valL.append( "qid="+str(qid) )

    if batch:
        spec = "batch:" + ','.join( valL )
    else:
        spec = "run:" + ','.join( valL )

    return spec


def interrupt_vvtest_run( vvtest_args, count=None, signum=None, qid=None ):
    ""
    spec = interrupt_test_hook( count=count, signum=signum, qid=qid )
    return run_vvtest_with_hook( vvtest_args, spec )


def interrupt_vvtest_batch( vvtest_args, count=None, signum=None ):
    ""
    spec = interrupt_test_hook( batch=True, count=count, signum=signum )
    return run_vvtest_with_hook( vvtest_args, spec, batch=True )


def run_vvtest_with_hook( vvtest_args, envspec, batch=False ):
    ""
    cmd = vvtest_command_line( vvtest_args, batch=batch )

    os.environ['VVTEST_UNIT_TEST_SPEC'] = envspec
    try:
        x,out = runcmd( cmd, raise_on_error=False )
    finally:
        del os.environ['VVTEST_UNIT_TEST_SPEC']

    return x, out


def rmallfiles( not_these=None ):
    for f in os.listdir("."):
        if not_these == None or not fnmatch.fnmatch( f, not_these ):
            fault_tolerant_remove( f )


def remove_results():
    """
    Removes all TestResults from the current working directory.
    If a TestResults directory is a soft link, the link destination is
    removed as well.
    """
    for f in os.listdir('.'):
        if f.startswith( 'TestResults.' ):
            if os.path.islink(f):
                dest = os.readlink(f)
                print3( 'rm -rf ' + dest )
                fault_tolerant_remove( dest )
                print3( 'rm ' + f )
                os.remove(f)
            else:
                print3( 'rm -rf ' + f )
                fault_tolerant_remove( f )


def random_string( numchars=8 ):
    ""
    seq = string.ascii_uppercase + string.digits
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


def grepfiles( pattern, *paths ):
    ""
    pattern = adjust_shell_pattern_to_work_with_fnmatch( pattern )

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


class VvtestCommandRunner:

    def __init__(self, cmd):
        ""
        self.cmd = cmd

    def run(self, **options):
        ""
        quiet          = options.get( 'quiet',          False )
        raise_on_error = options.get( 'raise_on_error', True )
        chdir          = options.get( 'chdir',          None )

        x,out = runcmd( self.cmd, chdir=chdir, raise_on_error=False )

        if not quiet:
            print3( out )

        self.x = x
        self.out = out
        self.cntD = parse_vvtest_counts( out )
        self.testdates = None

        self.plat = get_platform_name( out )

        self.rdir = get_results_dir( out )
        if self.rdir:
            if not os.path.isabs( self.rdir ):
                if chdir:
                    self.rdir = os.path.abspath( os.path.join( chdir, self.rdir ) )
                else:
                    self.rdir = os.path.abspath( self.rdir )
        elif chdir:
            self.rdir = os.path.abspath( chdir )
        else:
            self.rdir = os.getcwd()

        assert x == 0 or not raise_on_error, \
            'vvtest command returned nonzero exit status: '+str(x)

    def assertCounts(self, total=None, finish=None,
                           npass=None, diff=None,
                           fail=None, timeout=None,
                           notrun=None, notdone=None ):
        ""
        if total   != None: assert total   == self.cntD['total']
        if npass   != None: assert npass   == self.cntD['npass']
        if diff    != None: assert diff    == self.cntD['diff']
        if fail    != None: assert fail    == self.cntD['fail']
        if timeout != None: assert timeout == self.cntD['timeout']
        if notrun  != None: assert notrun  == self.cntD['notrun']
        if notdone != None: assert notdone == self.cntD['notdone']

        if finish != None:
            assert finish == self.cntD['npass'] + \
                             self.cntD['diff'] + \
                             self.cntD['fail']

    def resultsDir(self):
        ""
        return self.rdir

    def platformName(self):
        ""
        return self.plat

    def grepTestLines(self, regex):
        ""
        repat = re.compile( regex )
        matchL = []

        for line in testlines( self.out ):
            if repat.search( line ):
                matchL.append( line )

        return matchL

    def countTestLines(self, regex):
        ""
        return len( self.grepTestLines( regex ) )

    def grep(self, regex):
        ""
        return grep( self.out, regex )

    def countGrepLines(self, regex):
        ""
        return len( self.grep( regex ) )

    def greplogs(self, shell_pattern, testid_pattern=None):
        ""
        xL = findfiles( 'execute.log', self.rdir )
        if testid_pattern != None:
            xL = filter_logfile_list_by_testid( xL, testid_pattern )
        return grepfiles( shell_pattern, *xL )

    def countGrepLogs(self, shell_pattern, testid_pattern=None):
        ""
        return len( self.greplogs( shell_pattern, testid_pattern ) )

    def getTestIds(self):
        ""
        return parse_test_ids( self.out, self.resultsDir() )

    def startedTestIds(self):
        ""
        return parse_started_tests( self.out, self.resultsDir() )

    def startDate(self, testpath):
        ""
        if self.testdates == None:
            self.parseTestDates()

        return self.testdates[ testpath ][0]

    def endDate(self, testpath):
        ""
        if self.testdates == None:
            self.parseTestDates()

        return self.testdates[ testpath ][1]

    def parseTestDates(self):
        ""
        tdir = os.path.basename( self.resultsDir() )

        self.testdates = {}
        for xpath,start,end in testtimes( self.out ):

            # do not include the test results directory name
            pL = xpath.split( tdir+os.sep, 1 )
            if len(pL) == 2:
                xdir = pL[1]
            else:
                xdir = xpath

            self.testdates[ xdir ] = ( start, end )


def runvvtest( *cmd_args, **options ):
    """
    Options:  batch=True (default=False)
              quiet=True (default=False)
              raise_on_error=False (default=True)
              chdir=some/path (default=None)
              addplatform=True
    """
    cmd = vvtest_command_line( *cmd_args, **options )
    vrun = VvtestCommandRunner( cmd )
    vrun.run( **options )
    return vrun


def vvtest_command_line( *cmd_args, **options ):
    """
    Options:  batch=True (default=False)
              addplatform=True
    """
    argstr = ' '.join( cmd_args )
    argL = shlex.split( argstr )

    cmdL = [ sys.executable, vvtest ]

    if options.get( 'addplatform', True ) and '--plat' not in argL:
        cmdL.extend( [ '--plat', core_platform_name() ] )

    if options.get( 'batch', False ):

        cmdL.append( '--batch' )

        if '--qsub-limit' not in argL:
            cmdL.extend( [ '--qsub-limit', '5' ] )

        if '--qsub-length' not in argL:
            cmdL.extend( [ '--qsub-length', '0' ] )

    else:
        if '-n' not in argL:
            cmdL.extend( [ '-n', '8' ] )

    cmd = ' '.join( cmdL )
    if argstr:
        cmd += ' ' + argstr

    return cmd


def parse_vvtest_counts( out ):
    ""
    ntot = 0
    np = 0 ; nf = 0 ; nd = 0 ; nn = 0 ; nt = 0 ; nr = 0

    for line in testlines( out ):

        lineL = line.strip().split()

        ntot += 1

        if   check_pass   ( lineL ): np += 1
        elif check_fail   ( lineL ): nf += 1
        elif check_diff   ( lineL ): nd += 1
        elif check_notrun ( lineL ): nn += 1
        elif check_timeout( lineL ): nt += 1
        elif check_notdone( lineL ): nr += 1
        else:
            raise Exception( 'unable to parse test line: '+line )

    cntD = { 'total'  : ntot,
             'npass'  : np,
             'fail'   : nf,
             'diff'   : nd,
             'notrun' : nn,
             'timeout': nt,
             'notdone': nr }

    return cntD


def parse_test_ids( vvtest_output, results_dir ):
    ""
    tdir = os.path.basename( results_dir )

    tlist = []
    for line in testlines( vvtest_output ):
        s = line.strip().split()[-1]
        d1 = first_path_segment( s )+os.sep
        if d1.startswith( 'TestResults.' ):
            tid = s.split(d1)[1]
        else:
            tid = s
        tlist.append( tid )

    return tlist


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


def parse_started_tests( vvtest_output, results_dir ):
    ""
    tdir = os.path.basename( results_dir )

    startlist = []
    for line in vvtest_output.splitlines():
        if line.startswith( 'Starting: ' ):
            s = line.split( 'Starting: ' )[1].strip()
            if s.startswith( tdir+os.sep ):
                startlist.append( s.split( tdir+os.sep )[1] )

    return startlist


def filter_logfile_list_by_testid( logfiles, testid_pattern ):
    ""
    pat = adjust_shell_pattern_to_work_with_fnmatch( testid_pattern )

    newL = []

    for pn in logfiles:
        d,b = os.path.split( pn )
        assert b == 'execute.log'
        if fnmatch.fnmatch( os.path.basename( d ), pat ):
            newL.append( pn )

    return newL


def get_platform_name( vvtest_output ):
    ""
    platname = None

    for line in vvtest_output.splitlines():
        line = line.strip()
        if line.startswith( 'Test directory:' ):
            L1 = line.split( 'Test directory:', 1 )
            if len(L1) == 2:
                L2 = os.path.basename( L1[1].strip() ).split('.')
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


# these have to be modified if/when the output format changes in vvtest
def check_pass(L): return len(L) >= 5 and L[2] == 'pass'
def check_fail(L): return len(L) >= 5 and L[2][:4] == 'fail'
def check_diff(L): return len(L) >= 5 and L[2] == 'diff'
def check_notrun(L): return len(L) >= 3 and L[1] == 'NotRun'
def check_timeout(L): return len(L) >= 5 and L[1] == 'TimeOut'
def check_notdone(L): return len(L) >= 3 and L[1] == 'Running'

def numtotal(out):
    ""
    cnt = 0
    mark = 0
    for line in out.split( os.linesep ):
        if mark:
            if line[:10] == "==========":
                mark = 0
            else:
                L = line.split()
                if len(L) > 2:
                    cnt += 1
        elif line[:10] == "==========":
            mark = 1
            cnt = 0  # reset count so only the last cluster is considered

    return cnt

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
    ""
    lineL = []
    mark = False
    for line in out.split( os.linesep ):
        if mark:
            if line.startswith( "==========" ):
                mark = False
            else:
                lineL.append( line.rstrip() )

        elif line.startswith( "==========" ):
            mark = True
            del lineL[:]  # reset list so only last cluster is considered

    return lineL


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
        except Exception:
            pass

    return timesL
