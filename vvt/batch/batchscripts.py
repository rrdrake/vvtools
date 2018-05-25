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

from scriptrunner import ScriptRunner


class BatchScripts( batchitf.BatchInterface ):

    def __init__(self):
        ""
        batchitf.BatchInterface.__init__(self)

        self.runr = ScriptRunner()
        self.sprocs = {}  # runr job id -> runr job

    def writeScriptHeader(self, job, fileobj):
        ""
        pass

    def submit(self, job):
        """
        """
        batname = job.getBatchFileName()
        logname = job.getLogFileName()

        sproc = self.runr.submit( batname, redirect=logname )

        jid = str( sproc.getId() )
        subdate = time.time()

        job.setJobId( jid )
        job.setQueueDates( submit=subdate )
        job.setSubmitOutput( out='Job ID: '+jid, err='' )

        self.addJob( job )
        self.sprocs[ jid ] = sproc

    def queryQueue(self, jqtab):
        """
        """
        self.runr.poll()

        for jid,sproc in list( self.sprocs.items() ):

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


############################################################################

