#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import fnmatch

from . import TestSpec


class TestDependency:

    def __init__(self, testobj, matchpat, wordexpr):
        ""
        self.testobj = testobj
        self.matchpat = matchpat
        self.wordexpr = wordexpr

    def getTestSpec(self):
        ""
        return self.testobj

    def hasSameExecuteDirectory(self, testdep):
        ""
        xdir1 = self.testobj.getExecuteDirectory()
        xdir2 = testdep.testobj.getExecuteDirectory()

        return xdir1 == xdir2

    def satisfiesResult(self, result):
        ""
        if self.wordexpr == None:
            if result not in ['pass','diff']:
                return False

        elif not self.wordexpr.evaluate( lambda word: word == result ):
            return False

        return True

    def getMatchDirectory(self):
        ""
        return self.matchpat, self.testobj.getExecuteDirectory()


class DependencySet:

    def __init__(self, statushandler):
        ""
        self.statushandler = statushandler
        self.deps = []

    def addDependency(self, testdep):
        ""
        append = True
        for i,tdep in enumerate( self.deps ):
            if tdep.hasSameExecuteDirectory( testdep ):
                self.deps[i] = testdep
                append = False
                break

        if append:
            self.deps.append( testdep )

    def numDependencies(self):
        ""
        return len( self.deps )

    def getBlocking(self):
        """
        If one or more dependencies did not run, did not finish, or failed,
        then that offending TestSpec is returned.  Otherwise, None is returned.
        """
        for tdep in self.deps:
            tspec = tdep.getTestSpec()

            if not self.statushandler.isDone( tspec ):
                return tspec

            result = self.statushandler.getResultStatus( tspec )

            if not tdep.satisfiesResult( result ):
                return tspec

        return None

    def getMatchDirectories(self):
        ""
        L = []

        for tdep in self.deps:
            L.append( tdep.getMatchDirectory() )

        return L


def connect_dependency( from_test, to_test, pattrn=None, expr=None ):
    ""
    assert not isinstance( from_test, TestSpec.TestSpec )

    if isinstance( to_test, TestSpec.TestSpec ):
        ref = to_test
    else:
        ref = to_test.atest

    tdep = TestDependency( ref, pattrn, expr )
    from_test.getDependencySet().addDependency( tdep )

    if not isinstance( to_test, TestSpec.TestSpec ):
        to_test.setHasDependent()


def find_tests_by_execute_directory_match( xdir, pattern, xdir2tspec ):
    """
    Given 'xdir' dependent execute directory, the shell glob 'pattern' is
    matched against the execute directories in the 'xdir2tspec', in this order:

        1. basename(xdir)/pat
        2. basename(xdir)/*/pat
        3. pat
        4. *pat

    The first of these that matches at least one test will be returned.

    A python set of xdir is returned.
    """
    tbase = os.path.dirname( xdir )
    if tbase == '.':
        tbase = ''
    elif tbase:
        tbase += '/'

    L1 = [] ; L2 = [] ; L3 = [] ; L4 = []

    for xdir in xdir2tspec.keys():

        p1 = os.path.normpath( tbase+pattern )
        if fnmatch.fnmatch( xdir, p1 ):
            L1.append( xdir )

        if fnmatch.fnmatch( xdir, tbase+'*/'+pattern ):
            L2.append( xdir )

        if fnmatch.fnmatch( xdir, pattern ):
            L3.append( xdir )

        if fnmatch.fnmatch( xdir, '*'+pattern ):
            L4.append( xdir )

    for L in [ L1, L2, L3, L4 ]:
        if len(L) > 0:
            return set(L)

    return set()


def connect_analyze_dependencies( analyze, tspecL, xdir2testexec ):
    ""
    for gt in tspecL:
        if not gt.isAnalyze():
            connect_dependency( analyze, gt )
            gxt = xdir2testexec.get( gt.getExecuteDirectory(), None )
            if gxt != None:
                gxt.setHasDependent()


def check_connect_dependencies( testexec, xdir2tspec, xdir2testexec ):
    ""
    for dep_pat,expr in testexec.atest.getDependencies():
        xdir = testexec.atest.getExecuteDirectory()
        depL = find_tests_by_execute_directory_match(
                                        xdir, dep_pat, xdir2tspec )
        for dep_xdir in depL:
            dep_obj = xdir2testexec.get(
                            dep_xdir,
                            xdir2tspec.get( dep_xdir, None ) )
            if dep_obj != None:
                connect_dependency( testexec, dep_obj, dep_pat, expr )
