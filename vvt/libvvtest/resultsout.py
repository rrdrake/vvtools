#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time

from . import outpututils


class ResultsWriters:

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

    def midrun(self, atestlist):
        ""
        for wr in self.writers:
            wr.midrun( atestlist, self.runattrs )

    def postrun(self, atestlist):
        ""
        self._mark_finished()

        for wr in self.writers:
            wr.postrun( atestlist, self.runattrs )

    def info(self, atestlist):
        ""
        for wr in self.writers:
            wr.info( atestlist, self.runattrs )

    def _mark_finished(self):
        ""
        tm = time.time()
        self.runattrs['finishepoch'] = tm
        self.runattrs['finishdate'] = time.ctime(tm)
        self._set_elapsed_time( tm )

    def _set_elapsed_time(self, finishtime):
        ""
        start = self.runattrs.get( 'startepoch', None )
        if start:
            nsecs = finishtime - float( start )
            self.runattrs['elapsed'] = outpututils.pretty_time( nsecs )
