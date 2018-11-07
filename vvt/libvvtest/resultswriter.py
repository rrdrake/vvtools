#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time

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
            printHTMLResults( tohtml, sumstr, self.test_dir, self.perms,
                              Lfail, Ltime, Ldiff, Lpass, Lnrun, Lndone )

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
            write_JUnit_file( self.test_dir, rawlist, tojunit, datestamp )


def printHTMLResults( filename, sumstr, test_dir, perms,
                      Lfail, Ltime, Ldiff, Lpass, Lnrun, Lndone ):
    """
    Opens and writes an HTML summary file in the test directory.
    """
    
    if test_dir == ".":
      test_dir = os.getcwd()
    if not os.path.isabs(test_dir):
      test_dir = os.path.abspath(test_dir)
    
    fp = open( filename, "w" )
    try:
        perms.set( os.path.abspath( filename ) )

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
        writeHTMLTestList( fp, test_dir, Lfail )
        fp.write( '<h1>Tests that showed "timeout"</h1>\n' )
        writeHTMLTestList( fp, test_dir, Ltime )
        fp.write( '<h1>Tests that showed "diff"</h1>\n' )
        writeHTMLTestList( fp, test_dir, Ldiff )
        fp.write( '<h1>Tests that showed "notdone"</h1>\n' )
        writeHTMLTestList( fp, test_dir, Lndone )
        fp.write( '<h1>Tests that showed "pass"</h1>\n' )
        writeHTMLTestList( fp, test_dir, Lpass )
        fp.write( '<h1>Tests that showed "notrun"</h1>\n' )
        writeHTMLTestList( fp, test_dir, Lnrun )
        
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
      
      if isinstance(atest, TestExec.TestExec): ref = atest.atest
      else:                            ref = atest
      
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


def write_JUnit_file( test_dir, rawlist, filename, datestamp ):
    """
    This collects information from the given test list (a python list of
    TestExec objects), then writes a file in the format of JUnit XML files.
    
    The purpose is to be able to pull vvtest results into Jenkins jobs so it
    can display them in some form.  The format was determined starting with
    this link
        https://stackoverflow.com/questions/4922867/
                    junit-xml-format-specification-that-hudson-supports
    then just trial and error until Jenkins showed something reasonable.
    """
    tdir = os.path.basename( test_dir )
    tdir = tdir.replace( '.', '_' )  # a dot is a Java class separator
    
    datestr = time.strftime( "%Y-%m-%dT%H:%M:%S", time.localtime( datestamp ) )

    npass = nwarn = nfail = 0
    tsum = 0.0
    for t in rawlist:
        state = t.getAttr( 'state' )
        if state == "done":
            res = t.getAttr( 'result' )
            if res == "pass":
                npass += 1
            elif res == "diff":
                nwarn += 1
            else:
                nfail += 1
            
            xt = t.getAttr( 'xtime' )
            if xt > 0:
                tsum += xt
        else:
            nwarn += 1
    
    s = '''
<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
   <testsuite name="vvtest"
              errors="0" tests="0" failures="0"
              time="0" timestamp="DATESTAMP"/>
   <testsuite name="vvtest.TESTDIRNAME"
              errors="0" skipped="NUMWARN" tests="NUMTESTS" failures="NUMFAIL"
              time="TIMESUM" timestamp="DATESTAMP">
'''.strip()
    
    s = s.replace( 'TESTDIRNAME', tdir )
    s = s.replace( 'DATESTAMP', datestr )
    s = s.replace( 'NUMTESTS', str(npass+nwarn+nfail) )
    s = s.replace( 'NUMWARN', str(nwarn) )
    s = s.replace( 'NUMFAIL', str(nfail) )
    s = s.replace( 'TIMESUM', str(tsum) )

    for t in rawlist:
        
        xt = 0.0
        fail = ''
        warn = ''

        state = t.getAttr( 'state' )
        if state == "notrun":
            warn = 'Test was not run'
        else:
            if state == "done":
                xt = t.getAttr( 'xtime' )
                if xt < 0:
                    xt = 0.0
                
                res = t.getAttr( 'result' )
                if res == "pass":
                    pass
                elif res == "diff":
                    warn = 'Test diffed'
                elif res == "timeout":
                    fail = 'Test timed out'
                else:
                    fail = 'Test failed'
            else:
                warn = "Test did not finish"
        
        s += '\n      <testcase name="'+t.xdir+'" time="'+str(xt)+'">'
        if warn:
            s += '\n        <skipped message="'+warn+'"/>'
        elif fail:
            s += '\n        <failure message="'+fail+'"/>'
        s += '\n      </testcase>'
    
    s += '\n   </testsuite>'
    s += '\n</testsuites>\n'
    
    fp = open( filename, 'w' )
    fp.write(s)
    fp.close()


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


def print3( *args ):
    sys.stdout.write( ' '.join( [ str(arg) for arg in args ] ) + '\n' )
    sys.stdout.flush()
