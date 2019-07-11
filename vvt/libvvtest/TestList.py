#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time
import glob

from .errors import TestSpecError
from .testcase import TestCase
from . import testlistio
from .groups import ParameterizeAnalyzeGroups
from .teststatus import copy_test_results


class TestList:
    """
    Stores a set of TestCase objects.  Has utilities to read/write to a text
    file and to read from a test XML file.
    """

    def __init__(self, filename,
                       runtime_config=None,
                       testcreator=None,
                       testfilter=None):
        ""
        if filename:
            self.filename = os.path.normpath( filename )
        else:
            # use case: scanning tests, but never reading or writing
            self.filename = None

        self.results_suffix = None
        self.results_file = None

        self.datestamp = None
        self.finish = None

        self.groups = None  # a ParameterizeAnalyzeGroups class instance

        self.xdirmap = {}  # TestSpec xdir -> TestCase object
        self.tcasemap = {}  # TestSpec ID -> TestCase object

        self.rtconfig = runtime_config
        self.creator = testcreator
        self.testfilter = testfilter

    def setResultsSuffix(self, suffix=None):
        ""
        if suffix:
            self.results_suffix = suffix
        elif not self.results_suffix:
            self.results_suffix = time.strftime( "%Y-%m-%d_%H:%M:%S" )

        return self.results_suffix

    def getResultsSuffix(self):
        ""
        return self.results_suffix

    def stringFileWrite(self, include_results_suffix=False):
        """
        Writes all the tests in this container to the test list file.  If
        'include_results_suffix' is True, the results suffix is written as
        an attribute in the file.
        """
        assert self.filename

        check_make_directory_containing_file( self.filename )

        tlw = testlistio.TestListWriter( self.filename )

        if include_results_suffix:
            assert self.results_suffix
            tlw.start( results_suffix=self.results_suffix )
        else:
            tlw.start()

        for tcase in self.tcasemap.values():
            tlw.append( tcase )

        tlw.finish()

    def initializeResultsFile(self):
        ""
        self.setResultsSuffix()

        rfile = self.filename + '.' + self.results_suffix
        
        self.results_file = testlistio.TestListWriter( rfile )

        self.results_file.start()

        return rfile

    def addIncludeFile(self, testlist_path):
        """
        Appends the given filename to the test results file.
        """
        assert self.results_suffix, 'suffix must have already been set'
        inclf = testlist_path + '.' + self.results_suffix
        self.results_file.addIncludeFile( inclf )

    def appendTestResult(self, tcase):
        """
        Appends the results file with the name and attributes of the given
        TestCase object.
        """
        self.results_file.append( tcase )

    def writeFinished(self):
        """
        Appends the results file with a finish marker that contains the
        current date.
        """
        self.results_file.finish()

    def readTestList(self):
        ""
        assert self.filename

        if os.path.exists( self.filename ):

            tlr = testlistio.TestListReader( self.filename )
            tlr.read()

            self.results_suffix = tlr.getAttr( 'results_suffix', None )

            for xdir,tcase in tlr.getTests().items():
                if xdir not in self.tcasemap:
                    self.tcasemap[ xdir ] = tcase

    def readTestResults(self, resultsfilename=None):
        ""
        if resultsfilename == None:
            self._read_file_list( self.getResultsFilenames() )
        else:
            self._read_file_list( [ resultsfilename ] )

    def getResultsFilenames(self):
        ""
        assert self.filename
        fileL = glob.glob( self.filename+'.*' )
        fileL.sort()
        return fileL

    def _read_file_list(self, files):
        ""
        for fn in files:

            tlr = testlistio.TestListReader( fn )
            tlr.read()

            self.datestamp = tlr.getStartDate()
            self.finish = tlr.getFinishDate()

            for xdir,tcase in tlr.getTests().items():

                t = self.tcasemap.get( xdir, None )
                if t != None:
                    copy_test_results( t, tcase )

    def ensureInlinedTestResultIncludes(self):
        ""
        fL = self.getResultsFilenames()
        if len(fL) > 0:
            # only the most recent is checked
            testlistio.inline_include_files( fL[-1] )

    def inlineIncludeFiles(self):
        ""
        rfile = self.filename + '.' + self.results_suffix
        testlistio.inline_include_files( rfile )

    def getDateStamp(self, default=None):
        """
        Return the start date from the last test results file read using the
        readTestResults() function.  If a read has not been done, the 'default'
        argument is returned.
        """
        if self.datestamp:
            return self.datestamp
        return default

    def getFinishDate(self, default=None):
        """
        Return the finish date from the last test results file read using the
        readTestResults() function.  If a read has not been done, or vvtest is
        still running, or vvtest got killed in the middle of running, the
        'default' argument is returned.
        """
        if self.finish:
            return self.finish
        return default

    def getTests(self):
        """
        Returns, in a list, all tests either scanned or read from a file.
        """
        return self.tcasemap.values()

    def getTestMap(self):
        """
        Returns a map of xdir to TestCase containing all tests.
        """
        return self.tcasemap

    def getGroupMap(self):
        ""
        return self.groups

    def applyPermanentFilters(self):
        ""
        self._check_create_parameterize_analyze_group_map()

        self.testfilter.applyPermanent( self.tcasemap )

        finalize_analyze_tests( self.groups )

        self.numactive = count_active( self.tcasemap )

    def determineActiveTests(self, filter_dir=None,
                                   analyze_only=False,
                                   baseline=False):
        ""
        self._check_create_parameterize_analyze_group_map()

        self.testfilter.applyRuntime( self.tcasemap, filter_dir )

        if not baseline:
            finalize_analyze_tests( self.groups )

        refresh_active_tests( self.tcasemap, self.creator )

        if baseline:
            # baseline marking must come after TestSpecs are refreshed
            mark_skips_for_baselining( self.tcasemap )

        self.numactive = count_active( self.tcasemap )

    def numActive(self):
        """
        Return the total number of active tests (the tests that are to be run).
        """
        return self.numactive

    def getActiveTests(self, sorting=''):
        """
        Get a list of the active tests (after filtering).  If 'sorting' is
        not an empty string, it should be a set of characters that control the
        way the test sorting is performed.
                n : test name (the default)
                x : execution directory name
                t : test run time
                d : execution date
                s : test status (such as pass, fail, diff, etc)
                r : reverse the order
        """
        if not sorting:
            sorting = 'nx'

        tL = []

        for tcase in self.tcasemap.values():
            t = tcase.getSpec()
            if not tcase.getStat().skipTest():
                subL = []
                for c in sorting:
                    if c == 'n':
                        subL.append( t.getName() )
                    elif c == 'x':
                        # magic: add in stage here
                        subL.append( t.getExecuteDirectory_magik() )
                    elif c == 't':
                        tm = tcase.getStat().getRuntime( None )
                        if tm == None: tm = 0
                        subL.append( tm )
                    elif c == 'd':
                        subL.append( tcase.getStat().getStartDate( 0 ) )
                    elif c == 's':
                        subL.append( tcase.getStat().getResultStatus() )

                subL.append( tcase )
                tL.append( subL )
        tL.sort()
        if 'r' in sorting:
            tL.reverse()
        tL = [ L[-1] for L in tL ]

        return tL

    def encodeIntegerWarning(self):
        ""
        ival = 0
        for tcase in self.tcasemap.values():
            if not tcase.getStat().skipTest():
                result = tcase.getStat().getResultStatus()
                if   result == 'diff'   : ival |= ( 2**1 )
                elif result == 'fail'   : ival |= ( 2**2 )
                elif result == 'timeout': ival |= ( 2**3 )
                elif result == 'notdone': ival |= ( 2**4 )
                elif result == 'notrun' : ival |= ( 2**5 )
        return ival

    def readTestFile(self, basepath, relfile, force_params):
        """
        Initiates the parsing of a test file.  XML test descriptions may be
        skipped if they don't appear to be a test file.  Attributes from
        existing tests will be absorbed.
        """
        assert basepath
        assert relfile
        assert os.path.isabs( basepath )
        assert not os.path.isabs( relfile )

        basepath = os.path.normpath( basepath )
        relfile  = os.path.normpath( relfile )

        assert relfile

        try:
            testL = self.creator.fromFile( basepath, relfile, force_params )
        except TestSpecError:
          print3( "*** skipping file " + os.path.join( basepath, relfile ) + \
                  ": " + str( sys.exc_info()[1] ) )
          testL = []

        for tspec in testL:

            xdir = tspec.getExecuteDirectory_magik()

            # ignore tests with duplicate execution directories
            if xdir in self.xdirmap:  # magic: and no stages or same stage
                tcase = self.xdirmap[ xdir ]
                tspec1 = tcase.getSpec()
                print3( '*** warning:',
                    'ignoring test with duplicate execution directory\n',
                    '      first   :', tspec1.getFilename() + '\n',
                    '      second  :', tspec.getFilename() + '\n',
                    '      exec dir:', xdir )
            else:
                testid = tspec.getID()
                tcase = TestCase( tspec )
                self.tcasemap[testid] = tcase
                self.xdirmap[xdir] = tcase

    def addTest(self, tcase):
        """
        Add/overwrite a test in the list.
        """
        self.tcasemap[ tcase.getSpec().getID() ] = tcase

    def _check_create_parameterize_analyze_group_map(self):
        ""
        if self.groups == None:
            self.groups = ParameterizeAnalyzeGroups()
            self.groups.rebuild( self.tcasemap )


def check_make_directory_containing_file( filename ):
    ""
    d,b = os.path.split( filename )
    if d and d != '.':
        if not os.path.exists(d):
            os.mkdir( d )


def mark_skips_for_baselining( tcase_map ):
    ""
    for xdir,tcase in tcase_map.items():
        tspec = tcase.getSpec()
        if not tcase.getStat().skipTest():
            if not tspec.hasBaseline():
                tcase.getStat().markSkipByBaselineHandling()


def finalize_analyze_tests( groups ):
    ""
    for analyze, tcaseL in groups.iterateGroups():

        skip_analyze = False
        paramsets = []

        for tcase in tcaseL:
            if tcase.getStat().skipTestCausingAnalyzeSkip():
                skip_analyze = True
            else:
                paramsets.append( tcase.getSpec().getParameters() )

        if skip_analyze:
            if not analyze.getStat().skipTest():
                analyze.getStat().markSkipByAnalyzeDependency()
        else:
            def evalfunc( paramD ):
                for D in paramsets:
                    if paramD == D:
                        return True
                return False
            pset = analyze.getSpec().getParameterSet()
            pset.applyParamFilter( evalfunc )


def count_active( tcase_map ):
    ""
    cnt = 0
    for tcase in tcase_map.values():
        if not tcase.getStat().skipTest():
            cnt += 1
    return cnt


def refresh_active_tests( tcase_map, creator ):
    ""
    for xdir,tcase in tcase_map.items():
        tspec = tcase.getSpec()
        if not tcase.getStat().skipTest():
            if not tspec.constructionCompleted():
                creator.reparse( tspec )


###########################################################################

def print3( *args ):
    sys.stdout.write( ' '.join( [ str(arg) for arg in args ] ) + '\n' )
    sys.stdout.flush()
