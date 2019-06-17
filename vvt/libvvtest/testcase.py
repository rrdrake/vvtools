#!/usr/bin/env python 

import os, sys

from . import depend
from .teststatus import TestStatusHandler


class TestCase:

    def __init__(self, testspec, testexec=None):
        ""
        self.tspec = testspec
        self.texec = testexec
        self.tstat = TestStatusHandler( testspec )

        self.depset = depend.DependencySet()
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

    def getDependencySet(self):
        ""
        return self.depset

    def setHasDependent(self):
        ""
        self.has_dependent = True

    def hasDependent(self):
        ""
        return self.has_dependent

