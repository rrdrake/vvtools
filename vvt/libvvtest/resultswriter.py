#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time

from . import outpututils


# magic: better name here (this is a container class with info) dispatch?
class ResultsWriter:

    def __init__(self):
        ""
        self.writers = []
        self.runattrs = {}

    def addWriter(self, writer):
        ""
        self.writers.append( writer )

    def setRunAttr(self, **kwargs):
        ""
        self.runattrs.update( kwargs )

    def prerun(self, atestlist, abbreviate=True):
        ""
        for wr in self.writers:
            wr.prerun( atestlist, self.runattrs, abbreviate )

    def info(self, atestlist):
        ""
        for wr in self.writers:
            wr.info( atestlist, self.runattrs )

    def postrun(self, atestlist):
        ""
        for wr in self.writers:
            wr.postrun( atestlist, self.runattrs )

    def final(self, atestlist):
        ""
        self._mark_finished()

        for wr in self.writers:
            wr.final( atestlist, self.runattrs )

    def _mark_finished(self):
        ""
        tm = time.time()
        self.runattrs['finishdate'] = str(tm) + ' / ' + time.ctime(tm)
        self._set_elapsed_time( tm )

    def _set_elapsed_time(self, finishtime):
        ""
        start = self.runattrs.get( 'startdate', None )
        if start:
            nsecs = finishtime - float( start.split()[0] )
            self.runattrs['elapsed'] = outpututils.pretty_time( nsecs )
