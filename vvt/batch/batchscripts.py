#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import time

import batchitf

from scriptrunner import ScriptProcess


class BatchScripts( batchitf.BatchInterface ):

    def __init__(self):
        ""
        batchitf.BatchInterface.__init__(self)

        self.sprocs = batchitf.ThreadSafeStore()  # proc id -> ScriptProcess

    def writeScriptHeader(self, job, fileobj):
        ""
        pass  # no header necessary

    def submitJobScript(self, job):
        """
        """
        batname = job.getBatchFileName()
        logname = job.getLogFileName()

        sproc = ScriptProcess( batname, redirect=logname, timeout=None )
        sproc.run()

        jid = str( sproc.getId() )
        out = 'Job ID: '+jid
        err = ''

        self.sprocs.set( jid, sproc )

        return jid,out,err

    def queryQueue(self, jqtab):
        """
        """
        for jid,sproc in self.sprocs.asList():

            sproc.poll()

            st,x = sproc.getStatus()

            if not st:
                state = 'pending'
            elif st == 'running':
                state = 'running'
            else:
                # must be one of timeout, killed, exit
                state = 'done'

            startdate,stopdate = sproc.getDates()

            if stopdate:
                timeused = stopdate-startdate
            else:
                timeused = None

            jqtab.setJobInfo( jid, state, startdate, timeused )

            if state == 'done':
                self.sprocs.pop( jid )

    def cancel(self, job_list=None):
        ""
        pass

