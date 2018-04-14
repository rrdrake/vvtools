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

from batchinterface import BatchInterface
from batchinterface import lineprint
from batchinterface import parse_variant
from batchinterface import compute_num_nodes
from batchinterface import BatchJob
from batchinterface import construct_batch_filename
from batchinterface import construct_log_filename
from batchinterface import parse_date_string

import scriptrunner


class BatchUNIX( BatchInterface ):

    def __init__(self):
        ""
        BatchInterface.__init__(self)

        self.runq = scriptrunner.ScriptRunQueue()
        self.jobs = []

    def computeNumNodes(self, num_cores, cores_per_node=None):
        ""
        ppn = int( self.attrs.get( 'ppn', 2**31 ) )
        return compute_num_nodes( num_cores, cores_per_node, ppn )

    def writeBatchFile(self, job):
        ""
        batname = construct_batch_filename( job )

        fp = open( batname, 'w' )
        try:
            self._writeHeader( job, fp )
            fp.write( '\n' + job.getSpec( 'commands', '' ) + '\n' )
            self._writeTail( job, fp )

        finally:
            fp.close()

    def submit(self, job):
        """
        """
        batname = construct_batch_filename( job )
        logname = construct_log_filename( job )
        jobid = self.runq.submit( batname, redirect=logname )
        job.setResult( 'jobid', jobid )
        job.setResult( 'submit date', time.time() )
        self.jobs.append( [ job, logname ] )

    def poll(self):
        """
        """
        self.runq.poll()

        L = []
        for job,logname in self.jobs:

            jobid = job.getResult('jobid')

            st,x = self.runq.getStatusPair( jobid )

            # <empty> : the run() method has not been called
            # running : the subprocess was launched
            # timeout : the subprocess timed out and was killed
            # killed  : the terminate() method was called
            # exit    : the subprocess completed on its own
            if not st:
                job.setResult( 'state', 'queue' )
            elif st == 'running':
                job.setResult( 'state', 'running' )
                self._parse_log_file( job, logname )
            else:
                job.setResult( 'state', 'done' )
                self._parse_log_file( job, logname )

            if x == None:
                L.append( [ job, logname ] )
            elif x == 0:
                job.setResult( 'exit', 'success' )
            else:
                job.setResult( 'exit', 'fail' )

            trun,tdone = self.runq.getStartStopTimes( jobid )
            if trun != None:
                job.setResult( 'run date', trun )
            if tdone != None:
                job.setResult( 'done date', tdone )

        self.jobs = L

    def cancel(self, job_list=None):
        ""
        pass

    ###########################

    def _writeHeader(self, job, fileobj):
        """
        """
        lineprint( fileobj,
            'echo "BATCH START DATE: `date`"',
            'env',
            'echo "UNAME: `uname -a`"' )

        wdir = job.getSpec( 'work dir', None )
        if wdir:
            lineprint( fileobj,
                'echo "cd '+wdir+'"',
                'cd "'+wdir+'" || exit 1' )

        lineprint( fileobj, '' )

    def _writeTail(self, job, fileobj):
        """
        """
        lineprint( fileobj,
            '',
            'echo "BATCH STOP DATE: `date`"' )

    def _parse_log_file(self, job, logname):
        ""
        if os.path.exists( logname ):

            fp = open( logname, 'r' )
            try:
                started = False
                line = fp.readline()
                while line:

                    if not started:
                        L = line.split( 'BATCH START DATE:', 1 )
                        if len(L) == 2:
                            tm = parse_date_string( L[1].strip() )
                            if tm:
                                started = True
                                job.setResult( 'start date', tm )

                    L = line.split( 'BATCH STOP DATE:', 1 )
                    if len(L) == 2:
                        tm = parse_date_string( L[1].strip() )
                        if tm:
                            job.setResult( 'stop date', tm )

                    line = fp.readline()

            finally:
                fp.close()


############################################################################

