#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time
from os.path import join as pjoin

from . import outpututils
print3 = outpututils.print3


class JUnitWriter:

    def __init__(self, statushandler, permsetter,
                       output_filename, results_test_dir):
        ""
        self.statushandler = statushandler
        self.permsetter = permsetter
        self.filename = os.path.normpath( os.path.abspath( output_filename ) )
        self.testdir = results_test_dir

        self.datestamp = None

    def setOutputDate(self, datestamp):
        ""
        self.datestamp = datestamp

    def writeFile(self, atestlist):
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
        datestamp = atestlist.getDateStamp( time.time() )
        datestr = outpututils.make_date_stamp( datestamp, self.datestamp,
                                               "%Y-%m-%dT%H:%M:%S" )

        testL = atestlist.getActiveTests()

        print3( "Writing", len(testL), "tests to JUnit file", self.filename )


        parts = outpututils.partition_tests_by_result( self.statushandler,
                                                       testL )

        npass = len( parts['pass'] )
        nwarn = len( parts['diff'] ) + len( parts['notdone'] ) + len( parts['notrun'] )
        nfail = len( parts['fail'] ) + len( parts['timeout'] )

        tsum = 0.0
        for tst in testL:
            tsum += max( 0.0, self.statushandler.getRuntime( tst, 0.0 ) )

        tdir = os.path.basename( self.testdir )
        tdir = tdir.replace( '.', '_' )  # a dot is a Java class separator

        fp = open( self.filename, 'w' )
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
                    self.write_testcase( fp, tst, result, pkgclass, 10 )

            fp.write( '</testsuite>\n' + \
                      '</testsuites>\n' )

        finally:
            fp.close()
            self.permsetter.set( self.filename )

    def write_testcase(self, fp, tst, result, pkgclass, max_KB):
        ""
        xt = max( 0.0, self.statushandler.getRuntime( tst, 0.0 ) )

        fp.write( '<testcase name="'+tst.xdir+'"' + \
                           ' classname="'+pkgclass+'" time="'+str(xt)+'">\n' )

        if result == 'fail' or result == 'timeout':
            fp.write( '<failure message="'+result.upper()+'"/>\n' )
            buf = self.make_execute_log_section( tst, max_KB )
            fp.write( buf + '\n' )
        elif result == 'diff':
            fp.write( '<skipped message="DIFF"/>\n' )
            buf = self.make_execute_log_section( tst, max_KB )
            fp.write( buf + '\n' )
        elif result == 'notdone' or result == 'notrun':
            fp.write( '<skipped message="'+result.upper()+'"/>\n' )

        fp.write( '</testcase>\n' )

    def make_execute_log_section(self, tspec, max_KB):
        ""
        logdir = pjoin( self.testdir, tspec.getExecuteDirectory() )
        logfile = pjoin( logdir, 'execute.log' )

        try:
            sysout = outpututils.file_read_with_limit( logfile, max_KB )
        except Exception:
            xs,tb = outpututils.capture_traceback( sys.exc_info() )
            sysout = '*** error reading log file: '+str(logfile)+'\n' + tb

        return '<system-out><![CDATA[' + sysout + '\n]]></system-out>'