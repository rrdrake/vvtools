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

from os.path import dirname, abspath
from os.path import join as pjoin

import testutils as util
from testutils import print3


testsrcdir = dirname( abspath( sys.argv[0] ) )

# all imports for vvtest should be done relative to the "vvt" directory
vvtdir = dirname( dirname( testsrcdir ) )
sys.path.insert( 0, vvtdir )

vvtest_file = pjoin( vvtdir, 'vvtest' )
resultspy = pjoin( vvtdir, 'results.py' )


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

        x,out = util.runcmd( self.cmd, chdir=chdir, raise_on_error=False )

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
    """
    argstr = ' '.join( cmd_args )
    argL = shlex.split( argstr )

    cmdL = [ sys.executable, vvtest_file ]

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


# these have to be modified if/when the output format changes in vvtest
def check_pass(L): return len(L) >= 5 and L[2] == 'pass'
def check_fail(L): return len(L) >= 5 and L[2][:4] == 'fail'
def check_diff(L): return len(L) >= 5 and L[2] == 'diff'
def check_notrun(L): return len(L) >= 3 and L[1] == 'NotRun'
def check_timeout(L): return len(L) >= 5 and L[1] == 'TimeOut'
def check_notdone(L): return len(L) >= 3 and L[1] == 'Running'


def parse_test_ids( vvtest_output, results_dir ):
    ""
    tdir = os.path.basename( results_dir )

    tlist = []
    for line in testlines( vvtest_output ):
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


def greptestlist( shell_pattern, vvtest_output ):
    ""
    pattern = util.adjust_shell_pattern_to_work_with_fnmatch( shell_pattern )

    matchlines = []
    for line in testlines( vvtest_output ):
        if fnmatch.fnmatch( line, pattern ):
            matchlines.append( line )

    return matchlines


def testlines( vvtest_output ):
    ""
    lineL = []
    mark = False
    for line in vvtest_output.splitlines():
        if mark:
            if line.startswith( "==========" ):
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
