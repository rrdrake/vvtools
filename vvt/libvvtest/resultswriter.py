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

    def __init__(self, conobj, htmlobj, junitobj, gitlabobj, wlistobj ):
        ""
        self.conobj = conobj
        self.htmlobj = htmlobj
        self.junitobj = junitobj
        self.gitlabobj = gitlabobj
        self.wlistobj = wlistobj

        self.runattrs = {}

    ### prerun, info, postrun, final, setRunAttr are the interface functions

    def setRunAttr(self, **kwargs):
        ""
        self.runattrs.update( kwargs )

    def prerun(self, atestlist, abbreviate=True):
        ""
        if abbreviate:
            level = 0
        else:
            level = 1
        self.write_console( atestlist, False, level )

        self.check_write_testlist( atestlist, inprogress=True )

    def info(self, atestlist):
        ""
        if not self.htmlobj and not self.junitobj and not self.gitlabobj:
            self.write_console( atestlist, True, 2 )

        self.check_write_html( atestlist )
        self.check_write_junit( atestlist )
        self.check_write_gitlab( atestlist )
        self.check_write_testlist( atestlist )

    def postrun(self, atestlist):
        ""
        self.write_console( atestlist, True, 1 )
        self.check_write_testlist( atestlist )

    def final(self, atestlist):
        ""
        tm = time.time()
        self.runattrs['finishdate'] = str(tm) + ' / ' + time.ctime(tm)
        self.setElapsedTime( tm )

        self.check_write_html( atestlist )
        self.check_write_junit( atestlist )
        self.check_write_gitlab( atestlist )

    ###

    def write_console(self, atestlist, is_postrun, detail_level):
        ""
        self.conobj.writeTestList( atestlist, is_postrun, detail_level )

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

    def check_write_testlist(self, atestlist, inprogress=False):
        ""
        if self.wlistobj:
            self.wlistobj.writeList( atestlist, self.runattrs, inprogress )

    def setElapsedTime(self, finishtime):
        ""
        start = self.runattrs.get( 'startdate', None )
        if start:
            nsecs = finishtime - float( start.split()[0] )
            self.runattrs['elapsed'] = outpututils.pretty_time( nsecs )
