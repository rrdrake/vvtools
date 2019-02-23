#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time
import traceback

from os.path import join as pjoin

from . import TestExec
from . import pathutil


class ResultsWriter:

    def __init__(self, test_dir, perms, optsort, optrdate,
                       htmlfile, junitfile, gitlabdir ):
        ""
        self.test_dir = test_dir
        self.perms = perms
        self.optsort = optsort
        self.optrdate = optrdate

        self.htmlfile = htmlfile
        self.junitfile = junitfile
        self.gitlabdir = gitlabdir

        self.runattrs = {}

    ### prerun, info, postrun, final, setRunAttr are the interface functions

    def setRunAttr(self, **kwargs):
        ""
        self.runattrs.update( kwargs )

    def prerun(self, atestlist, short=True):
        ""
        self.write_console( atestlist, short )

    def info(self, atestlist):
        ""
        if not self.htmlfile and not self.junitfile and not self.gitlabdir:
            self.write_console( atestlist )

        self.check_write_html( atestlist )
        self.check_write_junit( atestlist )
        self.check_write_gitlab( atestlist )

    def postrun(self, atestlist):
        ""
        self.write_console( atestlist )

    def final(self, atestlist):
        ""
        tm = time.time()
        self.runattrs['finishdate'] = str(tm) + ' / ' + time.ctime(tm)
        self.setElapsedTime( tm )

        self.check_write_html( atestlist )
        self.check_write_junit( atestlist )
        self.check_write_gitlab( atestlist )

    ###

    def write_console(self, atestlist, short=False):
        ""
        rawlist = atestlist.getActiveTests( self.optsort )
        write_to_console( rawlist, self.test_dir, short )

    def check_write_html(self, atestlist):
        ""
        if self.htmlfile:
            printHTMLResults( atestlist, self.htmlfile, self.test_dir )
            self.perms.set( os.path.abspath( self.htmlfile ) )

    def check_write_junit(self, atestlist):
        ""
        if self.junitfile:

            datestamp = atestlist.getDateStamp( time.time() )
            datestr = make_date_stamp( datestamp, self.optrdate,
                                       "%Y-%m-%dT%H:%M:%S" )

            testL = atestlist.getActiveTests()
            print3( "Writing", len(testL), "tests to JUnit file", self.junitfile )
            write_JUnit_file( testL, self.test_dir, self.junitfile, datestr )
            self.perms.set( os.path.abspath( self.junitfile ) )

    def check_write_gitlab(self, atestlist):
        ""
        if self.gitlabdir:

            testL = atestlist.getActiveTests( self.optsort )

            if not os.path.isdir( self.gitlabdir ):
                os.mkdir( self.gitlabdir )

            try:
                print3( "Writing", len(testL),
                        "tests in GitLab format to", self.gitlabdir )

                conv = GitLabMarkDownConverter( self.test_dir, self.gitlabdir )
                conv.setRunAttr( **self.runattrs )
                conv.saveResults( testL )

            finally:
                self.perms.recurse( self.gitlabdir )

    def setElapsedTime(self, finishtime):
        ""
        start = self.runattrs.get( 'startdate', None )
        if start:
            nsecs = finishtime - float( start.split()[0] )
            self.runattrs['elapsed'] = pretty_time( nsecs )


def make_date_stamp( testdate, optrdate, timefmt="%Y_%m_%d" ):
    ""
    if optrdate != None:
        if type( optrdate ) == type(''):
            datestr = optrdate
        else:
            tup = time.localtime( optrdate )
            datestr = time.strftime( timefmt, tup )
    else:
        tup = time.localtime( testdate )
        datestr = time.strftime( timefmt, tup )

    return datestr


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


def write_to_console( testL, test_dir, short=False ):
    ""
    parts = partition_tests_by_result( testL )

    sumstr = results_summary_string( parts )

    cwd = os.getcwd()
    print3( "==================================================" )
    if short and len(testL) > 16:
        for atest in testL[:8]:
            print3( XstatusString( atest, test_dir, cwd ) )
        print3( "..." )
        for atest in testL[-8:]:
            print3( XstatusString( atest, test_dir, cwd ) )
    else:
        for atest in testL:
            print3( XstatusString( atest, test_dir, cwd ) )
    print3( "==================================================" )
    print3( "Summary:", sumstr )


def printHTMLResults( tlist, filename, test_dir ):
    """
    Opens and writes an HTML summary file in the test directory.
    """
    datestamp = tlist.getDateStamp( time.time() )
    datestr = make_date_stamp( datestamp, None, "%Y-%m-%d %H:%M:%S" )

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
        fp.write( "  <li> Test date: " + datestr + " </li>\n" )
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

        ref = ensure_TestSpec( atest )

        tdir = pjoin( test_dir, ref.getExecuteDirectory() )
        assert cwd == tdir[:len(cwd)]
        reltdir = tdir[len(cwd)+1:]

        fp.write( "<ul>\n" )
        thome = atest.getRootpath()
        xfile = pjoin( thome, atest.getFilepath() )
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
                fp.write( ' <a href="file:' + pjoin(reltdir,f) + \
                          '" type="text/plain">' + f + '</a>' )
        fp.write( '</li>\n' )
        fp.write( "</ul>\n" )
        fp.write( "</li>\n" )

    fp.write( '  </ul>\n' )


def XstatusString( t, test_dir, cwd ):
    """
    Returns a formatted string containing the job and its status.
    """
    ref = ensure_TestSpec( t )
    s = "%-20s " % ref.getName()

    state = ref.getAttr('state','notrun')  # magic: ugly: default "notrun"
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

            s += ' %-4s' % format_test_run_time( ref )
        else:
            s = s + "%-7s %-8s     " % ("Running", "")

    else:
        s = s + "%-7s %-8s     " % ("NotRun", "")

    s += " %14s" % format_test_run_date( ref )

    xdir = ref.getExecuteDirectory()
    s += ' ' + pathutil.relative_execute_directory( xdir, test_dir, cwd )

    return s


def format_test_run_date( tspec ):
    ""
    xdate = tspec.getAttr( 'xdate', 0 )
    if xdate > 0:
        return time.strftime( "%m/%d %H:%M:%S", time.localtime(xdate) )
    else:
        return ''


def format_test_run_time( tspec ):
    ""
    xtime = tspec.getAttr( 'xtime', -1 )
    if xtime >= 0:
        return pretty_time( xtime )
    else:
        return '-'


def XstatusResult(t):
    ""
    ref = ensure_TestSpec( t )

    # magic: ugly here is state defaults to "notrun"
    state = ref.getAttr('state','notrun')
    if state == "notrun" or state == "notdone":
        return state

    return ref.getAttr('result')


def write_JUnit_file( testL, test_dir, filename, datestr ):
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
    parts = partition_tests_by_result( testL )

    npass = len( parts['pass'] )
    nwarn = len( parts['diff'] ) + len( parts['notdone'] ) + len( parts['notrun'] )
    nfail = len( parts['fail'] ) + len( parts['timeout'] )

    tsum = 0.0
    for tst in testL:
        tsum += max( 0.0, tst.getAttr( 'xtime', 0.0 ) )

    tdir = os.path.basename( test_dir )
    tdir = tdir.replace( '.', '_' )  # a dot is a Java class separator

    fp = open( filename, 'w' )
    try:
        fp.write(
            '<?xml version="1.0" encoding="UTF-8"?>\n' + \
            '<testsuites>\n' + \
            '<testsuite name="vvtest"' + \
                      ' tests="'+str(npass+nwarn+nfail)+'"' + \
                      ' errors="0"' + \
                      ' skipped="'+str(nwarn)+'"' + \
                      ' failures="'+str(nfail)+'"' + \
                      ' time="'+str(tsum)+'"' + \
                      ' timestamp="'+datestr+'">\n' )

        pkgclass = 'vvtest.'+tdir

        for result in [ 'pass', 'fail', 'diff', 'timeout', 'notdone', 'notrun' ]:
            for tst in parts[result]:
                write_testcase( fp, tst, result, test_dir, pkgclass, 10 )

        fp.write( '</testsuite>\n' + \
                  '</testsuites>\n' )

    finally:
        fp.close()


def write_testcase( fp, tst, result, test_dir, pkgclass, max_KB ):
    ""
    xt = max( 0.0, tst.getAttr( 'xtime', 0.0 ) )

    fp.write( '<testcase name="'+tst.xdir+'"' + \
                       ' classname="'+pkgclass+'" time="'+str(xt)+'">\n' )

    if result == 'fail' or result == 'timeout':
        fp.write( '<failure message="'+result.upper()+'"/>\n' )
        buf = make_execute_log_section( tst, test_dir, max_KB )
        fp.write( buf + '\n' )
    elif result == 'diff':
        fp.write( '<skipped message="DIFF"/>\n' )
        buf = make_execute_log_section( tst, test_dir, max_KB )
        fp.write( buf + '\n' )
    elif result == 'notdone' or result == 'notrun':
        fp.write( '<skipped message="'+result.upper()+'"/>\n' )

    fp.write( '</testcase>\n' )


def make_execute_log_section( tspec, test_dir, max_KB ):
    ""
    logdir = pjoin( test_dir, tspec.getExecuteDirectory() )
    logfile = pjoin( logdir, 'execute.log' )

    try:
        sysout = file_read_with_limit( logfile, max_KB )
    except Exception:
        xs,tb = capture_traceback( sys.exc_info() )
        sysout = '*** error reading log file: '+str(logfile)+'\n' + tb

    return '<system-out><![CDATA[' + sysout + '\n]]></system-out>'


def file_read_with_limit( filename, max_KB ):
    ""
    maxsize = max( 128, max_KB * 1024 )
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


class GitLabFileSelector:
    def include(self, filename):
        ""
        bn,ext = os.path.splitext( filename )
        return ext in [ '.vvt', '.xml', '.log', '.txt', '.py', '.sh' ]


class GitLabMarkDownConverter:

    def __init__(self, test_dir, destdir,
                       max_KB=10,
                       big_table_size=100,
                       max_links_per_table=200 ):
        ""
        self.test_dir = test_dir
        self.destdir = destdir
        self.max_KB = max_KB
        self.big_table = big_table_size
        self.max_links = max_links_per_table

        self.selector = GitLabFileSelector()

        self.runattrs = {}

    def setRunAttr(self, **kwargs):
        ""
        self.runattrs.update( kwargs )

    def saveResults(self, testL):
        ""
        parts = partition_tests_by_result( testL )

        basepath = pjoin( self.destdir, 'TestResults' )
        fname = basepath + '.md'

        with open( fname, 'w' ) as fp:

            write_run_attributes( fp, self.runattrs )

            for result in [ 'fail', 'diff', 'timeout',
                            'pass', 'notrun', 'notdone' ]:
                altname = basepath + '_' + result + '.md'
                write_gitlab_results( fp, result, parts[result], altname,
                                      self.big_table, self.max_links )

        for result in [ 'fail', 'diff', 'timeout' ]:
            for i,tst in enumerate( parts[result] ):
                if i < self.max_links:
                    self.createTestFile( ensure_TestSpec( tst ) )

    def createTestFile(self, tspec):
        ""
        xdir = tspec.getExecuteDirectory()
        base = xdir.replace( os.sep, '_' )
        fname = pjoin( self.destdir, base+'.md' )

        srcdir = pjoin( self.test_dir, xdir )

        result = XstatusString( tspec, self.test_dir, os.getcwd() )
        preamble = 'Name: '+tspec.getName()+'  \n' + \
                   'Result: <code>'+result+'</code>  \n' + \
                   'Run directory: ' + os.path.abspath(srcdir) + '  \n'

        self.createGitlabDirectoryContents( fname, preamble, srcdir )

    def createGitlabDirectoryContents(self, filename, preamble, srcdir):
        ""
        with open( filename, 'w' ) as fp:

            fp.write( preamble + '\n' )

            try:
                stream_gitlab_files( fp, srcdir, self.selector, self.max_KB )

            except Exception:
                xs,tb = capture_traceback( sys.exc_info() )
                fp.write( '\n```\n' + \
                    '*** error collecting files: '+srcdir+'\n'+tb + \
                    '```\n' )


def write_run_attributes( fp, attrs ):
    ""
    nvL = list( attrs.items() )
    nvL.sort()
    for name,value in nvL:
        fp.write( '* '+name+' = '+str(value)+'\n' )
    fp.write( '\n' )


def write_gitlab_results( fp, result, testL, altname,
                              maxtablesize, max_path_links ):
    ""
    hdr = '## Tests that '+result+' = '+str( len(testL) ) + '\n\n'
    fp.write( hdr )

    if len(testL) == 0:
        pass

    elif len(testL) <= maxtablesize:
        write_gitlab_results_table( fp, result, testL, max_path_links )

    else:
        bn = os.path.basename( altname )
        fp.write( 'Large table contained in ['+bn+']('+bn+').\n\n' )
        with open( altname, 'w' ) as altfp:
            altfp.write( hdr )
            write_gitlab_results_table( altfp, result, testL, max_path_links )


def write_gitlab_results_table( fp, result, testL, max_path_links ):
    ""
    fp.write( '| Result | Date   | Time   | Path   |\n' + \
              '| ------ | ------ | -----: | :----- |\n' )

    for i,tst in enumerate(testL):
        add_link = ( i < max_path_links )
        fp.write( format_gitlab_table_line( tst, add_link ) + '\n' )

    fp.write( '\n' )


def format_gitlab_table_line( tst, add_link ):
    ""
    tspec = ensure_TestSpec( tst )

    result = XstatusResult( tspec )
    dt = format_test_run_date( tspec )
    tm = format_test_run_time( tspec )
    path = tspec.getExecuteDirectory()

    makelink = ( add_link and result in ['diff','fail','timeout'] )

    s = '| '+result+' | '+dt+' | '+tm+' | '
    s += format_test_path_for_gitlab( path, makelink ) + ' |'

    return s


def format_test_path_for_gitlab( path, makelink ):
    ""
    if makelink:
        repl = path.replace( os.sep, '_' )
        return '['+path+']('+repl+'.md)'
    else:
        return path


def stream_gitlab_files( fp, srcdir, selector, max_KB ):
    ""

    files,namewidth = get_directory_file_list( srcdir )

    for fn in files:
        fullfn = pjoin( srcdir, fn )

        incl = selector.include( fullfn )
        meta = get_file_meta_data_string( fullfn, namewidth )

        fp.write( '\n' )
        write_gitlab_formatted_file( fp, fullfn, incl, meta, max_KB )


def get_directory_file_list( srcdir ):
    ""
    maxlen = 0
    fL = []
    for fn in os.listdir( srcdir ):
        fL.append( ( os.path.getmtime( pjoin( srcdir, fn ) ), fn ) )
        maxlen = max( maxlen, len(fn) )
    fL.sort()
    files = [ tup[1] for tup in fL ]

    namewidth = min( 30, max( 10, maxlen ) )

    return files, namewidth


def write_gitlab_formatted_file( fp, filename, include_content, label, max_KB ):
    ""
    fp.write( '<details>\n' + \
              '<summary><code>'+label+'</code></summary>\n' + \
              '\n' + \
              '```\n' )

    if include_content:
        try:
            buf = file_read_with_limit( filename, max_KB )
        except Exception:
            xs,tb = capture_traceback( sys.exc_info() )
            buf = '*** error reading file: '+str(filename)+'\n' + tb

        if buf.startswith( '```' ):
            buf = buf.replace( '```', "'''", 1 )
        buf = buf.replace( '\n```', "\n'''" )

    else:
        buf = '*** file not archived ***'

    fp.write( buf )

    if not buf.endswith( '\n' ):
        fp.write( '\n' )

    fp.write( '```\n' + \
              '\n' + \
              '</details>\n' )


def get_file_meta_data_string( filename, namewidth ):
    ""
    bn = os.path.basename( filename )

    try:

        fmt = "%-"+str(namewidth)+'s'
        if os.path.islink( filename ):
            fname = os.readlink( filename )
            meta = fmt % ( bn + ' -> ' + fname )
            if not os.path.isabs( fname ):
                d = os.path.dirname( os.path.abspath( filename ) )
                fname = pjoin( d, fname )
        else:
            fname = filename
            meta = fmt % bn

        fsize = os.path.getsize( fname )
        meta += " %-12s" % ( ' size='+str(fsize) )

        fmod = os.path.getmtime( fname )
        meta += ' ' + time.ctime( fmod )

    except Exception:
        meta += ' *** error: '+str( sys.exc_info()[1] )

    return meta


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


def ensure_TestSpec( testobj ):
    ""
    if isinstance( testobj, TestExec.TestExec ):
        return testobj.atest
    else:
        return testobj


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
