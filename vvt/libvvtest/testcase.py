#!/usr/bin/env python 

import os, sys


class TestCase:

    def __init__(self, testspec=None, testexec=None, statushandler=None):
        ""
        self.tspec = testspec
        self.texec = testexec
        self.tstat = statushandler

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
