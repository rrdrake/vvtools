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


class BatchSLURM( batchitf.BatchInterface ):

    def __init__(self):
        ""
        batchitf.BatchInterface.__init__(self)

        # the function that issues shell batch commands
        self.runcmd = run_batch_command

    def computeNumNodes(self, num_cores, cores_per_node=None):
        ""
        assert cores_per_node != None or self.getProcessorsPerNode() != None, \
            "Processors per node must set if 'cores_per_node' is not"
        superfunc = batchitf.BatchInterface.computeNumNodes
        n = superfunc( self, num_cores, cores_per_node )
        return n

    def writeScriptHeader(self, job, fileobj):
        ""
        qtime = batchitf.format_time_to_HMS( job.getRunTime() )

        batchitf.lineprint( fileobj,
            '#SBATCH --nodes=' + str( job.getNumNodes() ),
            '#SBATCH --time=' + qtime,
            '#SBATCH --output=' + job.getLogFileName() )

        qname = job.getQueueName()
        if qname != None:
            fileobj.write( '#SBATCH --partition='+str(qname)+'\n' )

        accnt = job.getAccount()
        if accnt != None:
            fileobj.write( '#SBATCH --account='+str(accnt)+'\n' )

        batchitf.lineprint( fileobj, '' )

    def submit(self, job):
        """
        """
        x,out,err = self.runcmd( 'sbatch '+job.getBatchFileName() )

        job.setSubmitOutput( out=out, err=err )

        jid = parse_submit_output_for_job_id( out, err )

        job.setJobId( jid )

        job.setQueueDates( submit=time.time() )

        self.addJob( job )

    def queryQueue(self, jobtable):
        """
        Some squeue -o format codes:

            %i job or job step id
            %t job state: PD (pending), R (running), CA (cancelled),
                          CF(configuring), CG (completing), CD (completed),
                          F (failed), TO (timeout), NF (node failure),
                          RV (revoked), SE (special exit state)
            %V job's submission time
            %S actual or expected start time
            %M time used by the job (an INVALID is possible)

        - timeouts: waiting too long to show up in the queue, waiting
                    too long for the log file to be created, waiting too
                    long for the "finished" date to appear in the log file
        - avoid excessive file system activity by pausing in between job log
          fstat and reads (to get run dates)

            statL is [ state string, subdate, startdate, timeused ]
        """
        cmd = 'squeue --noheader -o "%i _ %t _ %V _ %S _ %M"'
        x,out,err = self.runcmd( cmd )

        parse_queue_table_output( jobtable, out )

    def cancel(self, job_list=None):
        ""
        raise NotImplementedError( "Method cancel()" )

    def setBatchCommandRunner(self, func):
        """
        The function that is used to execute shell batch commands.  Should
        return tuple ( exit status, stdout output, stderr output ).
        """
        self.runcmd = func


def run_batch_command( cmd ):
    ""
    p = subprocess.Popen( cmd, shell=True,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE )

    out,err = p.communicate()

    return p.returncode, out, err


def parse_submit_output_for_job_id( out, err ):
    """
    output should contain something like the following
       Submitted batch job 291041
    """
    jobid = None

    L1 = out.split( "Submitted batch job", 1 )
    if len(L1) == 2:
        L2 = L1[1].strip().split()
        if len(L2) > 0 and L2[0]:
            jobid = L2[0]

    return jobid


def parse_queue_table_output( jqtab, out ):
    """
    The 'out' string is something like

    7291680 _ R _ 2018-04-21T12:57:34 _ 2018-04-21T12:57:38 _ 7:37
    7291807 _ PD _ 2018-04-21T13:05:09 _ N/A _ 0:00
    7254586 _ CG _ 2018-04-20T21:05:53 _ 2018-04-20T21:05:58 _ 2:00:25

    job states: PD (pending), R (running), CA (cancelled),
                CF(configuring), CG (completing), CD (completed),
                F (failed), TO (timeout), NF (node failure),
                RV (revoked), SE (special exit state)
    """
    for line in out.strip().split( os.linesep ):

        sL = line.strip().split( ' _ ' )

        if len(sL) == 5:

            jid = sL[0].strip()
            st = sL[1].strip()

            if jid and st in ['PD','R','CG','CD',
                              'CA','CF','F','TO',
                              'NF','RV','SE']:

                if st in ['PD','CF']:
                    st = 'pending'
                elif st in ['R','CG']:
                    st = 'running'
                elif st in ['CD']:
                    st = 'complete'
                else:
                    st = 'done'

                subdate = parse_date_string( sL[2].strip() )
                startdate = parse_date_string( sL[3].strip() )
                timeused = parse_elapsed_time_string( sL[4].strip() )

                jqtab.setJobInfo( jid, st, subdate, startdate, timeused )


def parse_date_string( dstr ):
    """
    Such as 2018-04-20T22:20:30
    """
    tm = None

    dt = dstr.split('T')
    if len(dt) == 2:
        dL = dt[0].split('-')
        tL = dt[1].split(':')
        if len(dL) == 3 and len(tL) == 3:
            try:
                tup = time.strptime( dstr, "%Y-%m-%dT%H:%M:%S" )
                tm = time.mktime( tup )
            except:
                pass

    return tm


def parse_elapsed_time_string( dstr ):
    """
    Such as 11:27 or 21:42:39 or 1-20:21:50
    """
    dy = 0
    hr = 0
    mn = 0
    sc = 0

    sL = dstr.split('-',1)

    if len(sL) == 1:
        hms = dstr
    else:
        try:
            dy = int( sL[0] )
            hms = sL[1]
        except:
            return None

    nL = hms.split(':')

    try:
        sc = int( nL[-1] )
        if sc < 0 or sc >= 60:
            return None
    except:
        return None

    if len(nL) > 1:
        try:
            mn = int( nL[-2] )
            if mn < 0 or mn >= 60:
                return None
        except:
            return None

    if len(nL) > 2:
        try:
            hr = int( nL[-3] )
            if hr < 0 or hr > 24:
                return None
        except:
            return None

    return dy*24*60*60 + hr*60*60 + mn*60 + sc
