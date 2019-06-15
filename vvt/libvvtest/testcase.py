#!/usr/bin/env python 

import os, sys

from . import depend
from .teststatus import TestStatusHandler


class TestCase:

    def __init__(self, testspec=None, testexec=None):
        ""
        self.tspec = testspec
        self.texec = testexec
        self.tstat = TestStatusHandler()

        self.depset = None
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

    def setStatusHandler(self, tstat):
        ""
        self.tstat = tstat

    def getDependencySet(self):
        ""
        if self.depset == None:
            self.depset = depend.DependencySet( self.tstat )
        return self.depset

    def setHasDependent(self):
        ""
        self.has_dependent = True

    def hasDependent(self):
        ""
        return self.has_dependent

