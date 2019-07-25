#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
import os
import shlex
import time
import fnmatch
import signal
import subprocess
import unittest

from os.path import dirname, abspath
from os.path import join as pjoin

import testutils as util
from testutils import print3


testsrcdir = dirname( abspath( sys.argv[0] ) )

# all imports for vvtest should be done relative to the "vvt" directory
vvtdir = dirname( dirname( testsrcdir ) )
sys.path.insert( 0, vvtdir )

cfgdir = os.path.join( vvtdir, 'config' )

vvtest_file = pjoin( vvtdir, 'vvtest' )
resultspy = pjoin( vvtdir, 'results.py' )

import libvvtest.TestSpec as TestSpec
import libvvtest.testcase as testcase
import libvvtest.teststatus as teststatus
from libvvtest.RuntimeConfig import RuntimeConfig
from libvvtest.userplugin import UserPluginBridge, import_module_by_name
import libvvtest.paramset as ParameterSet


##########################################################################

class vvtestTestCase( unittest.TestCase ):

    def setUp(self, cleanout=True):
        ""
        util.setup_test( cleanout )

        # for batch tests
        os.environ['VVTEST_BATCH_READ_INTERVAL'] = '5'
        os.environ['VVTEST_BATCH_READ_TIMEOUT'] = '15'
        os.environ['VVTEST_BATCH_SLEEP_LENGTH'] = '1'

        # force the results files to be written locally for testing;
        # it is used in vvtest when handling the --save-results option
        os.environ['TESTING_DIRECTORY'] = os.getcwd()

    def tearDown(self):
        ""
        pass


nonqueued_platform_names = [ 'ceelan', 'Linux', 'iDarwin', 'Darwin' ]

def core_platform_name():
    """
    Returns either Darwin or Linux, depending on the current platform.
    """
    if os.uname()[0].lower().startswith( 'darwin' ):
        return 'Darwin'
    else:
        return 'Linux'


def launch_vvtest_then_terminate_it( *cmd_args, **options ):
    ""
    signum = options.pop( 'signum', signal.SIGTERM )
    seconds_before_signaling = options.pop( 'seconds_before_signaling', 4 )
    logfilename = options.pop( 'logfilename', 'run.log' )
    batch = options.pop( 'batch', False )
    addverbose = options.pop( 'addverbose', True )

    cmd = vvtest_command_line( *cmd_args, batch=batch, addverbose=addverbose )

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

    return util.readfile( logfilename )


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
        x,out = util.runcmd( cmd, raise_on_error=False )
    finally:
        del os.environ['VVTEST_UNIT_TEST_SPEC']

    return x, out


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
                util.fault_tolerant_remove( dest )
                print3( 'rm ' + f )
                os.remove(f)
            else:
                print3( 'rm -rf ' + f )
                util.fault_tolerant_remove( f )


class VvtestCommandRunner:

    def __init__(self, cmd):
        ""
        self.cmd = cmd

    def run(self, **options):
        ""
        quiet          = options.get( 'quiet',          False )
        raise_on_error = options.get( 'raise_on_error', True )
        chdir          = options.get( 'chdir',          None )

        x,out = util.runcmd( self.cmd, chdir=chdir,
                             raise_on_error=False, print_output=False )

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
                    self.rdir = abspath( pjoin( chdir, self.rdir ) )
                else:
                    self.rdir = abspath( self.rdir )
        elif chdir:
            self.rdir = abspath( chdir )
        else:
            self.rdir = os.getcwd()

        assert x == 0 or not raise_on_error, \
            'vvtest command returned nonzero exit status: '+str(x)

    def assertCounts(self, total=None, finish=None,
                           npass=None, diff=None,
                           fail=None, timeout=None,
                           notrun=None, notdone=None,
                           skip=None ):
        ""
        if total   != None: assert total   == self.cntD['total']
        if npass   != None: assert npass   == self.cntD['npass']
        if diff    != None: assert diff    == self.cntD['diff']
        if fail    != None: assert fail    == self.cntD['fail']
        if timeout != None: assert timeout == self.cntD['timeout']
        if notrun  != None: assert notrun  == self.cntD['notrun']
        if notdone != None: assert notdone == self.cntD['notdone']
        if skip    != None: assert skip    == self.cntD['skip']

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

    def grepTestLines(self, shell_pattern):
        ""
        return greptestlist( shell_pattern, self.out )

    def countTestLines(self, shell_pattern):
        ""
        return len( self.grepTestLines( shell_pattern ) )

    def grepLines(self, shell_pattern):
        ""
        return util.greplines( shell_pattern, self.out )

    def countLines(self, shell_pattern):
        ""
        return len( self.grepLines( shell_pattern ) )

    def greplogs(self, shell_pattern, testid_pattern=None):
        ""
        xL = util.findfiles( 'execute.log', self.rdir )
        if testid_pattern != None:
            xL = filter_logfile_list_by_testid( xL, testid_pattern )
        return util.grepfiles( shell_pattern, *xL )

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
              addverbose=True
    """
    argstr = ' '.join( cmd_args )
    argL = shlex.split( argstr )

    cmdL = [ sys.executable, vvtest_file ]

    if need_to_add_verbose_flag( argL, options ):
        # add -v when running in order to extract the full test list
        cmdL.append( '-v' )

    if options.get( 'addplatform', True ) and '--plat' not in argL:
        cmdL.extend( [ '--plat', core_platform_name() ] )

    if options.get( 'batch', False ):

        cmdL.append( '--batch' )

        if '--batch-limit' not in argL:
            cmdL.extend( [ '--batch-limit', '5' ] )

        if '--batch-length' not in argL:
            cmdL.extend( [ '--batch-length', '0' ] )

    else:
        if '-n' not in argL:
            cmdL.extend( [ '-n', '8' ] )

    cmd = ' '.join( cmdL )
    if argstr:
        cmd += ' ' + argstr

    return cmd


def need_to_add_verbose_flag( vvtest_args, options ):
    ""
    if options.get( 'addverbose', True ):
        if '-i' in vvtest_args: return False
        if '-g' in vvtest_args: return False
        if '-v' in vvtest_args: return False
        if '-vv' in vvtest_args: return False
        return True
    else:
        return False


def parse_vvtest_counts( out ):
    ""
    ntot = 0
    np = 0 ; nf = 0 ; nd = 0 ; nn = 0 ; nt = 0 ; nr = 0 ; ns = 0

    for line in extract_testlines( out ):

        lineL = line.strip().split()

        if   check_pass   ( lineL ): np += 1
        elif check_fail   ( lineL ): nf += 1
        elif check_diff   ( lineL ): nd += 1
        elif check_notrun ( lineL ): nn += 1
        elif check_timeout( lineL ): nt += 1
        elif check_notdone( lineL ): nr += 1
        elif check_skip   ( lineL ): ns += 1
        elif lineL[0] == '...':
            break  # a truncated test listing message starts with "..."
        else:
            raise Exception( 'unable to parse test line: '+line )

        ntot += 1

    cntD = { 'total'  : ntot,
             'npass'  : np,
             'fail'   : nf,
             'diff'   : nd,
             'notrun' : nn,
             'timeout': nt,
             'notdone': nr,
             'skip'   : ns }

    return cntD


# these have to be modified if/when the output format changes in vvtest
def check_pass(L): return len(L) >= 5 and L[1] == 'pass'
def check_fail(L): return len(L) >= 5 and L[1] == 'fail'
def check_diff(L): return len(L) >= 5 and L[1] == 'diff'
def check_notrun(L): return len(L) >= 3 and L[1] == 'notrun'
def check_timeout(L): return len(L) >= 4 and L[1] == 'timeout'
def check_notdone(L): return len(L) >= 3 and L[1] == 'notdone'
def check_skip(L): return len(L) >= 4 and L[1] == 'skip'


def parse_test_ids( vvtest_output, results_dir ):
    ""
    tdir = os.path.basename( results_dir )

    tlist = []
    for line in extract_testlines( vvtest_output ):
        s = line.strip().split()[-1]
        d1 = util.first_path_segment( s )+os.sep
        if d1.startswith( 'TestResults.' ):
            tid = s.split(d1)[1]
        else:
            tid = s
        tlist.append( tid )

    return tlist


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
    pat = util.adjust_shell_pattern_to_work_with_fnmatch( testid_pattern )

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


def get_results_dir( out ):
    """
    """
    tdir = None

    for line in out.split( os.linesep ):
        if line.strip().startswith( 'Test directory:' ):
            tdir = line.split( 'Test directory:', 1 )[1].strip()

    return tdir


def greptestlist( shell_pattern, vvtest_output ):
    ""
    pattern = util.adjust_shell_pattern_to_work_with_fnmatch( shell_pattern )

    matchlines = []
    for line in extract_testlines( vvtest_output ):
        if fnmatch.fnmatch( line, pattern ):
            matchlines.append( line )

    return matchlines


def extract_testlines( vvtest_output ):
    ""
    lineL = []
    mark = False
    for line in vvtest_output.splitlines():
        if mark:
            if line.startswith( "==========" ) or \
               line.startswith( 'Test list:' ) or \
               line.startswith( 'Summary:' ):  # happens if test list is empty
                mark = False
            else:
                lineL.append( line )

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
    for line in extract_testlines(out):
        L = line.strip().split()
        try:
            s = time.strftime('%Y ')+L[3]+' '+L[4]
            t = time.mktime( time.strptime( s, fmt ) )
            e = t + int( L[2][:-1] )
            timesL.append( [ L[-1], t, e ] )
        except Exception:
            pass

    return timesL


def parse_summary_string( summary_string ):
    """
    Parses the summary string from vvtest output, such as

        Summary: pass=0, fail=1, diff=0, timeout=0, notdone=0, notrun=1, skip=0

    Returns dictionary of these names to their values.
    """
    valD = {}

    for spec in summary_string.split():
        spec = spec.strip(',')
        if '=' in spec:
            nv = spec.split('=')
            assert len(nv) == 2
            valD[ nv[0] ] = int( nv[1] )

    return valD


def assert_summary_string( summary_string,
                           npass=None, fail=None, diff=None,
                           timeout=None, notdone=None, notrun=None,
                           skip=None ):
    """
    Parses the summary string and asserts any given values.
    """
    valD = parse_summary_string( summary_string )

    if npass   != None: assert valD['pass']    == npass
    if fail    != None: assert valD['fail']    == fail
    if diff    != None: assert valD['diff']    == diff
    if timeout != None: assert valD['timeout'] == timeout
    if notdone != None: assert valD['notdone'] == notdone
    if notrun  != None: assert valD['notrun']  == notrun
    if skip    != None: assert valD['skip']    == skip


def make_fake_TestSpec( name='atest', keywords=['key1','key2'] ):
    ""
    ts = TestSpec.TestSpec( name, os.getcwd(), 'sdir/'+name+'.vvt' )
    ts.setKeywords( keywords )
    ts.setParameters( { 'np':'4' } )
    return ts


def make_fake_TestCase( result=None, runtime=None, name='atest',
                        keywords=['key1','key2'] ):
    ""
    tcase = testcase.TestCase( make_fake_TestSpec( name, keywords ) )

    tstat = tcase.getStat()

    tstat.resetResults()

    if result:
        tm = time.time()
        if result == 'skip':
            tstat.markSkipByPlatform()
        elif result == 'skippass':
            tstat.markStarted( tm )
            tstat.markDone( 0 )
            tstat.markSkipByPlatform()
        elif result == 'skipfail':
            tstat.markStarted( tm )
            tstat.markDone( 1 )
            tstat.markSkipByPlatform()
        elif result == 'timeout':
            tstat.markStarted( tm )
            tstat.markTimedOut()
        elif result == 'pass':
            tstat.markStarted( tm )
            tstat.markDone( 0 )
        elif result == 'diff':
            tstat.markStarted( tm )
            tstat.markDone( teststatus.DIFF_EXIT_STATUS )
        elif result == 'notdone':
            tstat.markStarted( tm )
        elif result == 'notrun':
            pass
        elif result == 'running':
            tstat.markStarted( tm )
        else:
            assert result == 'fail', '*** error (value='+str(result)+')'
            tstat.markStarted( tm )
            tstat.markDone( 1 )

    if runtime != None:
        tstat.setRuntime( runtime )

    return tcase


def make_fake_staged_TestCase( stage_index=0 ):
    ""
    tcase = make_fake_TestCase()
    tspec = tcase.getSpec()

    pset = ParameterSet.ParameterSet()
    pset.addParameterGroup( ('stage','np'), [ ('1','1'), ('2','4'), ('3','1') ] )

    if stage_index == 0:
        tspec.setParameters( { 'stage':'1', 'np':'1' } )
        tspec.setStagedParameters( True, False, 'stage', 'np' )
    elif stage_index == 1:
        tspec.setParameters( { 'stage':'2', 'np':'4' } )
        tspec.setStagedParameters( False, False, 'stage', 'np' )
    elif stage_index == 2:
        tspec.setParameters( { 'stage':'3', 'np':'1' } )
        tspec.setStagedParameters( False, True, 'stage', 'np' )

    return tcase


# python imports can get confused when importing the same module name more
# than once, so use a counter to make a new name for each plugin
plugin_count = 0

def make_plugin_filename():
    ""
    global plugin_count
    plugin_count += 1

    return 'plugin'+str(plugin_count)


def make_user_plugin( content=None, platname=None, options=None ):
    ""
    plugname = make_plugin_filename()

    subdir = 'adir'
    if content != None:
        util.writefile( subdir+'/'+plugname+'.py', content )
    time.sleep(1)

    rtconfig = make_RuntimeConfig( platname, options )

    sys.path.insert( 0, os.path.abspath(subdir) )
    try:
        plug = UserPluginBridge( rtconfig, import_module_by_name( plugname ) )
    finally:
        sys.path.pop( 0 )

    return plug


def make_RuntimeConfig( platname, options ):
    ""
    rtconfig = RuntimeConfig()

    if platname:
        rtconfig.setAttr( 'platform_name', platname )
    if options:
        rtconfig.setAttr( 'option_list', options )

    return rtconfig
