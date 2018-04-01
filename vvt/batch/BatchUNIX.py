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


class BatchUNIX( BatchInterface ):

    def __init__(self, variant=''):
        ""
        self.attrs = parse_variant( variant )

        if 'ppn' in self.attrs:
            ppn = int( self.attrs['ppn'] )
            assert ppn > 0
            self.attrs['ppn'] = ppn

        self.subprocs = {}

    def computeNumNodes(self, num_cores, cores_per_node=None):
        ""
        ppn = self.attrs.get( 'ppn', 2**31 )
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
        self._submitJob( job, batname )

    def poll(self, job_list=None):
        """
        """
        doneL = []

        for jobid,L in self.subprocs.items():

            proc,job = L

            self._parse_log_file( job )

            x = proc.poll()

            if x != None:
                job.setResult( 'state', 'C' )
                job.setResult( 'done date', time.time() )
                job.setResult( 'state', 'done' )
                doneL.append( (jobid,x) )

                if x == 0:
                    job.setResult( 'exit', 'success' )
                else:
                    job.setResult( 'exit', 'fail' )

        for jobid,x in doneL:
            self.subprocs.pop( jobid )

        return doneL

    def cancel(self, job_list=None):
        ""
        pass

    ###########################

    def _writeHeader(self, job, fileobj):
        """
        """
        lineprint( fileobj,
            'echo "BATCH START DATE: `date`"',
            'env' )

        wdir = job.getSpec( 'work dir', None )
        if wdir:
            lineprint( fileobj, 'cd '+wdir+' || exit 1' )

        lineprint( fileobj, '' )

    def _writeTail(self, job, fileobj):
        """
        """
        lineprint( fileobj,
            '',
            'echo "BATCH STOP DATE: `date`"' )

    def _submitJob(self, job, script_filename):
        """
        """
        logname = construct_log_filename( job )
        job.setResult( '_logname', logname )

        fp = open( logname, 'w' )
        try:
            proc = sub.Popen( ['/bin/bash', script_filename ],
                              stdout=fp, stderr=sub.STDOUT )

            jobid = proc.pid
            job.setResult( 'jobid', str(jobid) )
            self.subprocs[ jobid ] = [ proc, job ]

            job.setResult( 'submit out', 'Submitted subprocess '+str(jobid) )
            job.setResult( 'submit err', '' )

            tm = time.time()
            job.setResult( 'submit date', tm )
            job.setResult( 'run date', tm )

            job.setResult( 'state', 'running' )

        finally:
            fp.close()

    def _parse_log_file(self, job):
        ""
        fn = job.getResult( '_logname' )

        if os.path.exists( fn ):

            fp = open( fn, 'r' )
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

