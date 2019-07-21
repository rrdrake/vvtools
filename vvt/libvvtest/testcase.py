#!/usr/bin/env python 

import os, sys

from . import depend
from .teststatus import TestStatus


class TestCase:

    def __init__(self, testspec, testexec=None):
        ""
        self.tspec = testspec
        self.texec = testexec

        self.tstat = TestStatus( testspec )
        self.deps = []
        self.depdirs = {}  # xdir -> match pattern
        self.has_dependent = False

    def getSpec(self):
        ""
        return self.tspec

    def getExec(self):
        ""
        return self.texec

    def getStat(self):
        ""
        return self.tstat

    def setExec(self, texec):
        ""
        self.texec = texec

    def setHasDependent(self):
        ""
        self.has_dependent = True

    def hasDependent(self):
        ""
        return self.has_dependent

    def addDependency(self, testcase, match_pattern=None, result_expr=None):
        ""
        testdep = depend.TestDependency( testcase, match_pattern, result_expr )

        append = True
        for i,tdep in enumerate( self.deps ):
            if tdep.hasSameTestID( testdep ):
                # if same test ID, prefer the one with a TestExec
                if not self.deps[i].hasTestExec():
                    self.deps[i] = testdep
                append = False
                break

        if append:
            self.deps.append( testdep )
            self.addDepDirectory( *testdep.getMatchDirectory() )

    def numDependencies(self):
        ""
        return len( self.deps )

    def getBlockingDependency(self):
        ""
        for tdep in self.deps:
            if tdep.isBlocking():
                return tdep.getTestCase()

        return None

    def willNeverRun(self):
        ""
        for tdep in self.deps:
            if tdep.willNeverRun():
                return True

        return False

    def addDepDirectory(self, match_pattern, exec_dir):
        ""
        self.depdirs[ exec_dir ] = match_pattern

    def getDepDirectories(self):
        ""
        matchL = [ (T[1],T[0]) for T in self.depdirs.items() ]
        return matchL
