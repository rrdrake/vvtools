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
        self.jobs = []

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
        job.setJobId( jid )
        job.setStatus( state='queue' )
        job.setQueueDates( sub=time.time() )
        job.setSubmitOutput( out='Job ID: '+jid, err='' )

        self.jobs.append( [ job, sproc ] )

    def poll(self):
        """
        """
        self.runr.poll()

        L = []
        for job,sproc in self.jobs:

            t0,t1 = sproc.getDates()
            job.setQueueDates( run=t0, done=t1 )

            t0,t1 = self.parseScriptDates( job )
            job.setRunDates( start=t0, stop=t1 )

            st,x = sproc.getStatus()

            assert st
            if st == 'running':
                job.setStatus( state='running' )
            elif st:
                job.setStatus( state='done' )

            if x == None:
                L.append( [ job, sproc ] )
            else:
                if t1: xs = 'ok'
                else:  xs = 'fail'
                job.setStatus( exit=xs )

        self.jobs = L

    def cancel(self, job_list=None):
        ""
        pass


############################################################################

