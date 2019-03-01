#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time
import traceback

from os.path import join as pjoin

from . import outpututils


class ResultsWriter:

    def __init__(self, conobj, htmlobj, junitobj, gitlabobj ):
        ""
        self.conobj = conobj
        self.htmlobj = htmlobj
        self.junitobj = junitobj
        self.gitlabobj = gitlabobj

        self.runattrs = {}

    ### prerun, info, postrun, final, setRunAttr are the interface functions

    def setRunAttr(self, **kwargs):
        ""
        self.runattrs.update( kwargs )

    def prerun(self, atestlist, short=True):
        ""
        self.write_console( atestlist, short )

    def info(self, atestlist):
        ""
        if not self.htmlobj and not self.junitobj and not self.gitlabobj:
            self.write_console( atestlist )

        self.check_write_html( atestlist )
        self.check_write_junit( atestlist )
        self.check_write_gitlab( atestlist )

    def postrun(self, atestlist):
        ""
        self.write_console( atestlist )

    def final(self, atestlist):
        ""
        tm = time.time()
        self.runattrs['finishdate'] = str(tm) + ' / ' + time.ctime(tm)
        self.setElapsedTime( tm )

        self.check_write_html( atestlist )
        self.check_write_junit( atestlist )
        self.check_write_gitlab( atestlist )

    ###

    def write_console(self, atestlist, short=False):
        ""
        self.conobj.writeTests( atestlist, abbreviate=short )

    def check_write_html(self, atestlist):
        ""
        if self.htmlobj:
            self.htmlobj.writeDocument( atestlist )

    def check_write_junit(self, atestlist):
        ""
        if self.junitobj:
            self.junitobj.writeFile( atestlist )

    def check_write_gitlab(self, atestlist):
        ""
        if self.gitlabobj:
            self.gitlabobj.writeFiles( atestlist, self.runattrs )

    def setElapsedTime(self, finishtime):
        ""
        start = self.runattrs.get( 'startdate', None )
        if start:
            nsecs = finishtime - float( start.split()[0] )
            self.runattrs['elapsed'] = outpututils.pretty_time( nsecs )
