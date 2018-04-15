#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import time
import subprocess as sub

import batchitf

from scriptrunner import ScriptRunner


class BatchUNIX( batchitf.BatchInterface ):

    def __init__(self):
        ""
        batchitf.BatchInterface.__init__(self)

        self.runr = ScriptRunner()
        self.jobs = []

    def computeNumNodes(self, num_cores, cores_per_node=None):
        ""
        ppn = int( self.attrs.get( 'ppn', 2**31 ) )
        return batchitf.compute_num_nodes( num_cores, cores_per_node, ppn )

    def writeBatchFile(self, job):
        ""
        batname = os.path.abspath( job.getBatchFileName() )

        fp = open( batname, 'w' )
        try:
            self._writeHeader( job, fp )
            fp.write( '\n' + job.getRunCommands() + '\n' )
            self._writeTail( job, fp )

        finally:
            fp.close()

    def submit(self, job):
        """
        """
        batname = os.path.abspath( job.getBatchFileName() )
        logname = os.path.abspath( job.getLogFileName() )

        sproc = self.runr.submit( batname, redirect=logname )

        jid = str( sproc.getId() )
        job.setJobId( jid )
        job.setStatus( state='queue' )
        job.setQueueDates( sub=time.time() )
        job.setSubmitOutput( out='Job ID: '+jid, err='' )

        self.jobs.append( [ job, sproc, logname ] )

    def poll(self):
        """
        """
        self.runr.poll()

        L = []
        for job,sproc,logname in self.jobs:

            t0,t1 = sproc.getDates()
            job.setQueueDates( run=t0, done=t1 )

            t0,t1 = self._parse_log_file( logname )
            job.setRunDates( start=t0, stop=t1 )

            st,x = sproc.getStatus()

            assert st
            if st == 'running':
                job.setStatus( state='running', exit=x )
            elif st:
                job.setStatus( state='done', exit=x )

            if x == None:
                L.append( [ job, sproc, logname ] )
            else:
                if t1: xs = 'ok'
                else:  xs = 'fail'
                job.setStatus( exit=xs )

        self.jobs = L

    def cancel(self, job_list=None):
        ""
        pass

    ###########################

    def _writeHeader(self, job, fileobj):
        """
        """
        batchitf.lineprint( fileobj,
            'echo "BATCH START DATE: `date`"',
            'env',
            'echo "UNAME: `uname -a`"' )

        rdir = job.getRunDirectory()
        if rdir:
            batchitf.lineprint( fileobj,
                'echo "cd '+rdir+'"',
                'cd "'+rdir+'" || exit 1' )

        batchitf.lineprint( fileobj, '' )

    def _writeTail(self, job, fileobj):
        """
        """
        batchitf.lineprint( fileobj,
            '',
            'echo "BATCH STOP DATE: `date`"' )

    def _parse_log_file(self, logname):
        ""
        start = None
        stop = None

        if os.path.exists( logname ):

            fp = open( logname, 'r' )
            try:
                started = False
                line = fp.readline()
                while line:

                    if not started:
                        L = line.split( 'BATCH START DATE:', 1 )
                        if len(L) == 2:
                            tm = batchitf.parse_date_string( L[1].strip() )
                            if tm:
                                start = tm
                            started = True

                    L = line.split( 'BATCH STOP DATE:', 1 )
                    if len(L) == 2:
                        tm = batchitf.parse_date_string( L[1].strip() )
                        if tm:
                            stop = tm

                    line = fp.readline()

            finally:
                fp.close()

        return start, stop


############################################################################

