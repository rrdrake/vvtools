#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys


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
