#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time
import traceback

from . import TestExec
from . import pathutil


class ResultsWriter:

    def __init__(self, test_dir, perms, optsort, optrdate,
                       htmlfile, junitfile ):
        ""
        self.test_dir = test_dir
        self.perms = perms
        self.optsort = optsort
        self.optrdate = optrdate

        self.htmlfile = htmlfile
        self.junitfile = junitfile

    def prerun(self, atestlist, short=True):
        ""
        self.write( atestlist, short=short )

    def info(self, atestlist):
        ""
        self.write( atestlist, no_console=self.htmlfile or self.junitfile,
                               tohtml=self.htmlfile,
                               tojunit=self.junitfile )

    def postrun(self, atestlist):
        ""
        self.write( atestlist, tohtml=self.htmlfile,
                               tojunit=self.junitfile )

    def final(self, atestlist):
        ""
        self.write( atestlist, no_console=True,
                               tohtml=self.htmlfile,
                               tojunit=self.junitfile )

    def write(self, atestlist, short=False,
                    no_console=False, tohtml=None, tojunit=None):
        ""
        rawlist = atestlist.getActiveTests( self.optsort )

        Lfail = []; Ltime = []; Ldiff = []; Lpass = []; Lnrun = []; Lndone = []
        for atest in rawlist:
            statr = XstatusResult(atest)
            if   statr == "fail":    Lfail.append(atest)
            elif statr == "timeout": Ltime.append(atest)
            elif statr == "diff":    Ldiff.append(atest)
            elif statr == "pass":    Lpass.append(atest)
            elif statr == "notrun":  Lnrun.append(atest)
            elif statr == "notdone": Lndone.append(atest)
        sumstr = str(len(Lpass)) + " pass, " + \
                 str(len(Ltime)) + " timeout, " + \
                 str(len(Ldiff)) + " diff, " + \
                 str(len(Lfail)) + " fail, " + \
                 str(len(Lnrun)) + " notrun, " + \
                 str(len(Lndone)) + " notdone"

        if not no_console:
            cwd = os.getcwd()
            print3( "==================================================" )
            if short and len(rawlist) > 16:
                for atest in rawlist[:8]:
                    print3( XstatusString( atest, self.test_dir, cwd ) )
                print3( "..." )
                for atest in rawlist[-8:]:
                    print3( XstatusString( atest, self.test_dir, cwd ) )
            else:
                for atest in rawlist:
                    print3( XstatusString( atest, self.test_dir, cwd ) )
            print3( "==================================================" )
            print3( "Summary:", sumstr )

        if tohtml:
            printHTMLResults( atestlist, tohtml, self.test_dir )
            self.perms.set( os.path.abspath( tohtml ) )

        if tojunit:

            if self.optrdate != None:
                try:
                    datestamp = float(self.optrdate)
                except Exception:
                    print3( '*** vvtest error: --results-date must be seconds ' + \
                            'since epoch for use with --junit option' )
                    sys.exit(1)
            else:
                datestamp = atestlist.getDateStamp( time.time() )

            print3( "Writing", len(rawlist), "tests to JUnit file", tojunit )
            write_JUnit_file( atestlist, self.test_dir, tojunit, datestamp )
            self.perms.set( os.path.abspath( tojunit ) )


def partition_tests_by_result( tlist ):
    ""
    parts = { 'fail':[], 'timeout':[], 'diff':[],
              'pass':[], 'notrun':[], 'notdone':[] }

    for tst in tlist:
        result = XstatusResult( tst )
        parts[ result ].append( tst )

    return parts


def results_summary_string( testparts ):
    ""
    sumL = []

    for result in [ 'pass', 'fail', 'diff', 'timeout', 'notdone', 'notrun' ]:
        sumL.append( result+'='+str( len( testparts[result] ) ) )

    return ', '.join( sumL )


def printHTMLResults( tlist, filename, test_dir ):
    """
    Opens and writes an HTML summary file in the test directory.
    """
    parts = partition_tests_by_result( tlist.getActiveTests() )

    sumstr = results_summary_string( parts )

    test_dir = os.path.normpath( os.path.abspath( test_dir ) )

    fp = open( filename, "w" )
    try:
        fp.write( "<html>\n<head>\n<title>Test Results</title>\n" )
        fp.write( "</head>\n<body>\n" )

        # a summary section

        fp.write( "<h1>Summary</h1>\n" )
        fp.write( "  <ul>\n" )
        fp.write( "  <li> Directory: " + test_dir + " </li>\n" )
        fp.write( "  <li> " + sumstr + "</li>\n" )
        fp.write( "  </ul>\n" )

        # segregate the tests into implicit keywords, such as fail and diff

        fp.write( '<h1>Tests that showed "fail"</h1>\n' )
        writeHTMLTestList( fp, test_dir, parts['fail'] )
        fp.write( '<h1>Tests that showed "timeout"</h1>\n' )
        writeHTMLTestList( fp, test_dir, parts['timeout'] )
        fp.write( '<h1>Tests that showed "diff"</h1>\n' )
        writeHTMLTestList( fp, test_dir, parts['diff'] )
        fp.write( '<h1>Tests that showed "notdone"</h1>\n' )
        writeHTMLTestList( fp, test_dir, parts['notdone'] )
        fp.write( '<h1>Tests that showed "pass"</h1>\n' )
        writeHTMLTestList( fp, test_dir, parts['pass'] )
        fp.write( '<h1>Tests that showed "notrun"</h1>\n' )
        writeHTMLTestList( fp, test_dir, parts['notrun'] )

        fp.write( "</body>\n</html>\n" )

    finally:
        fp.close()


def writeHTMLTestList( fp, test_dir, tlist ):
    """
    Used by printHTMLResults().  Writes the HTML for a list of tests to the
    HTML summary file.
    """
    cwd = os.getcwd()

    fp.write( '  <ul>\n' )

    for atest in tlist:

        fp.write( '  <li><code>' + XstatusString(atest, test_dir, cwd) + '</code>\n' )

        if isinstance(atest, TestExec.TestExec):
            ref = atest.atest
        else:
            ref = atest

        tdir = os.path.join( test_dir, ref.getExecuteDirectory() )
        assert cwd == tdir[:len(cwd)]
        reltdir = tdir[len(cwd)+1:]

        fp.write( "<ul>\n" )
        thome = atest.getRootpath()
        xfile = os.path.join( thome, atest.getFilepath() )
        fp.write( '  <li>XML: <a href="file://' + xfile + '" ' + \
                         'type="text/plain">' + xfile + "</a></li>\n" )
        fp.write( '  <li>Parameters:<code>' )
        for (k,v) in atest.getParameters().items():
            fp.write( ' ' + k + '=' + v )
        fp.write( '</code></li>\n' )
        fp.write( '  <li>Keywords: <code>' + ' '.join(atest.getKeywords()) + \
                   ' ' + ' '.join( atest.getResultsKeywords() ) + \
                   '</code></li>\n' )
        fp.write( '  <li>Status: <code>' + XstatusString(atest, test_dir, cwd) + \
                   '</code></li>\n' )
        fp.write( '  <li> Files:' )
        if os.path.exists(reltdir):
            for f in os.listdir(reltdir):
                fp.write( ' <a href="file:' + os.path.join(reltdir,f) + \
                          '" type="text/plain">' + f + '</a>' )
        fp.write( '</li>\n' )
        fp.write( "</ul>\n" )
        fp.write( "</li>\n" )

    fp.write( '  </ul>\n' )


def XstatusString( t, test_dir, cwd ):
    """
    Returns a formatted string containing the job and its status.
    """
    if isinstance(t, TestExec.TestExec):
        ref = t.atest
        s = "%-20s " % ref.getName()
    else:
        ref = t
        s = "%-20s " % t.getName()

    state = ref.getAttr('state')
    if state != "notrun":

        if state == "done":
            result = ref.getAttr('result')
            if result == 'diff':
                s = s + "%-7s %-8s" % ("Exit", "diff")
            elif result ==  'pass':
                s = s + "%-7s %-8s" % ("Exit", "pass")
            elif result == "timeout":
                s = s + "%-7s %-8s" % ("TimeOut", 'SIGINT')
            else:
                s = s + "%-7s %-8s" % ("Exit", "fail(1)")

            xtime = ref.getAttr('xtime')
            if xtime >= 0: s = s + (" %-4s" % (str(xtime)+'s'))
            else:          s = s + "     "
        else:
            s = s + "%-7s %-8s     " % ("Running", "")

    else:
        s = s + "%-7s %-8s     " % ("NotRun", "")

    xdate = ref.getAttr('xdate')
    if xdate > 0:
        s = s + time.strftime( " %m/%d %H:%M:%S", time.localtime(xdate) )
    else:
        s = s + "               "

    xdir = ref.getExecuteDirectory()
    s += ' ' + pathutil.relative_execute_directory( xdir, test_dir, cwd )

    return s


def XstatusResult(t):
    ""
    if isinstance(t, TestExec.TestExec):
        ref = t.atest
    else:
        ref = t

    state = ref.getAttr('state')
    if state == "notrun" or state == "notdone":
        return state

    return ref.getAttr('result')


def write_JUnit_file( tlist, test_dir, filename, datestamp ):
    """
    This collects information from the given test list (a python list of
    TestExec objects), then writes a file in the format of JUnit XML files.
    
    The purpose is to be able to pull vvtest results into Jenkins jobs so it
    can display them in some form.  The format was determined starting with
    this link
        https://stackoverflow.com/questions/4922867/
                    junit-xml-format-specification-that-hudson-supports
    then just trial and error until Jenkins showed something reasonable.

    Update Nov 2018: This link is a nice summary of junit in Jenkins
        http://nelsonwells.net/2012/09/
                    how-jenkins-ci-parses-and-displays-junit-output/
    And the junit source repo on GitHub has nice examples in
        https://github.com/jenkinsci/junit-plugin/
                    tree/master/src/test/resources/hudson/tasks/junit
    """
    testL = tlist.getActiveTests()
    parts = partition_tests_by_result( testL )

    npass = len( parts['pass'] )
    nwarn = len( parts['diff'] ) + len( parts['notdone'] ) + len( parts['notrun'] )
    nfail = len( parts['fail'] ) + len( parts['timeout'] )

    tsum = 0.0
    for tst in testL:
        tsum += max( 0.0, tst.getAttr( 'xtime', 0.0 ) )

    tdir = os.path.basename( test_dir )
    tdir = tdir.replace( '.', '_' )  # a dot is a Java class separator

    datestr = time.strftime( "%Y-%m-%dT%H:%M:%S", time.localtime( datestamp ) )

    fp = open( filename, 'w' )
    try:
        fp.write(
            '<?xml version="1.0" encoding="UTF-8"?>\n' + \
            '<testsuites>\n' + \
            '<testsuite name="vvtest"' + \
                      ' tests="'+str(npass+nwarn+nfail)+'"' + \
                      ' skipped="'+str(nwarn)+'"' + \
                      ' failures="'+str(nfail)+'"' + \
                      ' time="'+str(tsum)+'"' + \
                      ' timestamp="'+datestr+'">\n' )

        pkgclass = 'vvtest.'+tdir

        for result in [ 'pass', 'fail', 'diff', 'timeout', 'notdone', 'notrun' ]:
            for tst in parts[result]:
                write_testcase( fp, tst, result, test_dir, pkgclass )

        fp.write( '</testsuite>\n' + \
                  '</testsuites>\n' )

    finally:
        fp.close()


def write_testcase( fp, tst, result, test_dir, pkgclass ):
    ""
    xt = max( 0.0, tst.getAttr( 'xtime', 0.0 ) )

    fp.write( '<testcase name="'+tst.xdir+'"' + \
                       ' classname="'+pkgclass+'" time="'+str(xt)+'">\n' )

    if result == 'fail' or result == 'timeout':
        fp.write( '<failure message="'+result.upper()+'"/>\n' )
        fp.write( make_execute_log_section( tst, test_dir ) + '\n' )
    elif result == 'diff':
        fp.write( '<skipped message="DIFF"/>\n' )
        fp.write( make_execute_log_section( tst, test_dir ) + '\n' )
    elif result == 'notdone' or result == 'notrun':
        fp.write( '<skipped message="'+result.upper()+'"/>\n' )

    fp.write( '</testcase>\n' )


def make_execute_log_section( tspec, test_dir, max_kilobytes=10 ):
    ""
    logdir = os.path.join( test_dir, tspec.getExecuteDirectory() )
    logfile = os.path.join( logdir, 'execute.log' )

    try:
        sysout = file_read_with_limit( logfile, max_kilobytes )
    except Exception:
        xs,tb = capture_traceback( sys.exc_info() )
        sysout = '*** error reading log file: '+str(logfile)+'\n' + tb

    return '<system-out><![CDATA[' + sysout + '\n]]></system-out>'


def file_read_with_limit( filename, max_kilobytes ):
    ""
    maxsize = max( 128, max_kilobytes * 1024 )
    fsz = os.path.getsize( filename )

    buf = ''
    if fsz < maxsize:
        with open( filename, 'r' ) as fp:
            buf = fp.read()
    else:
        hdr = int( float(maxsize) * 0.20 + 0.5 )
        bot = fsz - int( float(maxsize) * 0.70 + 0.5 )
        with open( filename, 'r' ) as fp:
            buf = fp.read( hdr )
            buf += '\n\n*** the middle of this file has been removed ***\n\n'
            fp.seek( bot )
            buf += fp.read()

    return buf


def pretty_time( nseconds ):
    """
    Returns a string with the given number of seconds written in a human
    readable form.
    """
    h = int( nseconds / 3600 )
    sh = str(h)+'h'

    m = int( ( nseconds - 3600*h ) / 60 )
    sm = str(m)+'m'

    s = int( ( nseconds - 3600*h - 60*m ) )
    if h == 0 and m == 0 and s == 0: s = 1
    ss = str(s) + 's'

    if h > 0: return sh+' '+sm+' '+ss
    if m > 0: return sm+' '+ss
    return ss


def capture_traceback( excinfo ):
    """
    This should be called in an except block of a try/except, and the argument
    should be sys.exc_info().  It extracts and formats the traceback for the
    exception.  Returns a pair ( the exception string, the full traceback ).
    """
    xt,xv,xtb = excinfo
    xs = ''.join( traceback.format_exception_only( xt, xv ) )
    tb = 'Traceback (most recent call last):\n' + \
         ''.join( traceback.format_list(
                        traceback.extract_stack()[:-2] +
                        traceback.extract_tb( xtb ) ) ) + xs
    return xs,tb


def print3( *args ):
    sys.stdout.write( ' '.join( [ str(arg) for arg in args ] ) + '\n' )
    sys.stdout.flush()
