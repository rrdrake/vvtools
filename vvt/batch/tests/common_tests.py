#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time
import glob

import testutils as util
from testutils import print3

from batchjob import BatchJob


class Method_computeNumNodes:

    def setUp(self):
        ""
        util.setup_test( cleanout=False )

    def test_with_default_cores_per_node(self):
        ""
        bat = self.makeBatchInterface()

        assert bat.computeNumNodes( 1 ) == 1
        assert bat.computeNumNodes( 0 ) == 1
        assert bat.computeNumNodes( 2 ) == 1

    def test_with_ppn_variant(self):
        ""
        bat = self.makeBatchInterface()
        bat.setProcessorsPerNode( 2 )

        assert bat.computeNumNodes( 0 ) == 1
        assert bat.computeNumNodes( 1 ) == 1
        assert bat.computeNumNodes( 2 ) == 1
        assert bat.computeNumNodes( 3 ) == 2
        assert bat.computeNumNodes( 4 ) == 2
        assert bat.computeNumNodes( 5 ) == 3

    def test_with_cores_per_node_given(self):
        ""
        bat = self.makeBatchInterface()
        self.check_cores_per_node( bat )

        bat = self.makeBatchInterface()
        bat.setProcessorsPerNode( 2 )
        self.check_cores_per_node( bat )

    def check_cores_per_node(self, bat):
        ""
        assert bat.computeNumNodes( 1, 1 ) == 1
        assert bat.computeNumNodes( 0, 1 ) == 1
        assert bat.computeNumNodes( 2, 1 ) == 2

        assert bat.computeNumNodes( 0, 2 ) == 1
        assert bat.computeNumNodes( 1, 2 ) == 1
        assert bat.computeNumNodes( 2, 2 ) == 1
        assert bat.computeNumNodes( 3, 2 ) == 2
        assert bat.computeNumNodes( 4, 2 ) == 2
        assert bat.computeNumNodes( 5, 2 ) == 3


class Batch_output_file:

    def setUp(self):
        ""
        util.setup_test()

    def test_job_output_always_goes_to_a_file(self):
        ""
        bat = self.makeBatchInterface()

        job = BatchJob()

        out = run_batch_job_with_stdouterr_capture( bat, job,
                'echo "grep for this statement"' )

        assert 'grep for this statement' not in out

        fL = glob.glob( 'job_*.log' )
        assert len(fL) == 1
        L = util.filegrep( fL[0], 'grep for this statement' )
        assert len(L) == 1

    def test_specify_log_file(self):
        ""
        os.mkdir( 'odir' )
        time.sleep(1)

        bat = self.makeBatchInterface()

        job = BatchJob()
        job.setLogFileName( 'odir/bat.log' )

        out = run_batch_job_with_stdouterr_capture( bat, job,
                'echo "grep for this statement"' )

        assert 'grep for this statement' not in out

        L = util.filegrep( 'odir/bat.log', 'grep for this statement' )
        assert len(L) == 1


class Batch_work_directory:

    def setUp(self):
        ""
        util.setup_test()

    def test_default_work_dir_is_current_dir(self):
        ""
        os.mkdir( 'wdir' )
        time.sleep(1)

        curdir = os.getcwd()
        os.chdir( 'wdir' )

        bat = self.makeBatchInterface()

        job = BatchJob()

        out = run_batch_job_with_stdouterr_capture( bat, job,
                'echo "mycwd=`pwd`"' )

        fL = glob.glob( 'job_*.log' )
        assert len(fL) == 1
        L = util.filegrep( fL[0], 'mycwd=' )
        assert len(L) == 1
        d = L[0].split('mycwd=',1)[1].strip()
        assert os.path.samefile( curdir+'/wdir', d )

    def test_setting_work_dir_explicitely(self):
        ""
        os.mkdir( 'wdir' )
        time.sleep(1)

        curdir = os.getcwd()

        bat = self.makeBatchInterface()

        job = BatchJob()
        job.setRunDirectory( 'wdir' )

        out = run_batch_job_with_stdouterr_capture( bat, job,
                'echo "mycwd=`pwd`"' )

        os.path.samefile( curdir, os.getcwd() )
        fL = glob.glob( 'job_*.log' )
        assert len(fL) == 1
        L = util.filegrep( fL[0], 'mycwd=' )
        assert len(L) == 1
        d = L[0].split('mycwd=',1)[1].strip()
        assert os.path.samefile( curdir+'/wdir', d )


class Batch_submit:

    def setUp(self):
        ""
        util.setup_test()

    def test_jobid_gets_defined(self):
        ""
        bat = self.makeBatchInterface()
        job = BatchJob()

        write_and_submit_batch_job( bat, job )

        jobid = job.getJobId()

        wait_on_job( bat, job, 5 )

        # this also tests that the jobid is a string
        assert jobid != None and jobid.strip()

    def test_submit_stdout_stderr_gets_set(self):
        ""
        bat = self.makeBatchInterface()
        job = BatchJob()

        write_and_submit_batch_job( bat, job )

        subout,suberr = job.getSubmitOutput()

        wait_on_job( bat, job, 5 )

        assert subout.strip()
        assert not suberr.strip()

    def test_submit_date_gets_set(self):
        ""
        bat = self.makeBatchInterface()
        job = BatchJob()
        curdate = time.time()

        write_and_submit_batch_job( bat, job, 'sleep 5' )

        time.sleep(1)
        bat.poll()
        sub1,run1,done1 = job.getQueueDates()

        wait_on_job( bat, job, 5 )

        assert sub1
        assert abs( curdate - run1 ) < 5
        assert not done1

        sub2,run2,done2 = job.getQueueDates()
        assert sub1 == sub2
        assert run1 == run2
        print 'magic:', done2, curdate
        assert done2 and done2-curdate > 2

    def test_batch_failure_will_still_have_done_date(self):
        ""
        bat = self.makeBatchInterface()
        job = BatchJob()

        write_and_submit_batch_job( bat, job,
            'sleep 2',
            'exit 1' )

        wait_on_job( bat, job, 10 )

        sub,run,done = job.getQueueDates()

        assert done
        assert abs( done - time.time() ) < 10


class Batch_start_stop_dates:

    def setUp(self):
        ""
        util.setup_test()

    def test_queue_run_and_done_dates(self):
        ""
        bat = self.makeBatchInterface()
        job = BatchJob()

        write_and_submit_batch_job( bat, job, 'sleep 5' )

        bat.poll()
        time.sleep(1)
        bat.poll()

        sub1,run1,done1 = job.getQueueDates()

        wait_on_job( bat, job, 10 )

        sub2,run2,done2 = job.getQueueDates()

        assert run1 and run2 and run1 == run2
        assert done1 == None
        assert done2  # magic: this one will fail sometimes but pass when rerun
        assert done2-run1 > 4 and done2-run1 < 10

    def test_run_start_and_stop_dates(self):
        ""
        bat = self.makeBatchInterface()
        job = BatchJob()

        write_and_submit_batch_job( bat, job, 'sleep 5' )

        wait_on_job( bat, job, 10 )

        start,stop = job.getRunDates()

        assert start and stop
        assert stop-start > 4 and stop-start < 10

    def test_batch_failure_will_still_have_start_date(self):
        ""
        bat = self.makeBatchInterface()
        job = BatchJob()

        write_and_submit_batch_job( bat, job,
            'sleep 2',
            'exit 1' )

        wait_on_job( bat, job, 10 )

        start,stop = job.getRunDates()

        assert start
        assert abs( start - time.time() ) < 10


class Batch_job_status:

    def setUp(self):
        ""
        util.setup_test()

    def test_a_running_job_is_marked_running(self):
        ""
        bat = self.makeBatchInterface()
        job = BatchJob()

        write_and_submit_batch_job( bat, job, 'sleep 4' )

        bat.poll()
        time.sleep(1)
        bat.poll()

        st,x = job.getStatus()

        wait_on_job( bat, job, 5 )

        assert st == 'running'

    def test_a_finished_job_is_marked_done(self):
        ""
        bat = self.makeBatchInterface()
        job = BatchJob()

        write_and_submit_batch_job( bat, job, 'sleep 1' )

        wait_on_job( bat, job, 5 )

        st,x = job.getStatus()
        assert st == 'done'

    def test_a_failed_job_is_still_marked_done(self):
        ""
        bat = self.makeBatchInterface()
        job = BatchJob()

        write_and_submit_batch_job( bat, job,
            'sleep 1',
            'exit 1' )

        wait_on_job( bat, job, 10 )

        st,x = job.getStatus()
        assert st == 'done'


class Batch_exit_values:

    def setUp(self):
        ""
        util.setup_test()

    def test_exit_value_is_ok_in_nominal_case(self):
        ""
        bat = self.makeBatchInterface()
        job = BatchJob()

        write_and_submit_batch_job( bat, job, 'sleep 1' )

        wait_on_job( bat, job, 5 )

        st,x = job.getStatus()
        assert x == 'ok'

    def test_script_exit_results_in_a_fail_exit_value(self):
        ""
        bat = self.makeBatchInterface()
        job = BatchJob()

        write_and_submit_batch_job( bat, job,
            'sleep 1',
            'exit 1' )

        wait_on_job( bat, job, 10 )

        st,x = job.getStatus()
        assert x == 'fail'

    def test_a_running_job_does_not_have_an_exit_value(self):
        ""
        bat = self.makeBatchInterface()
        job = BatchJob()

        write_and_submit_batch_job( bat, job,
            'sleep 5',
            'exit 1' )

        bat.poll()
        time.sleep(1)
        bat.poll()

        st,x1 = job.getStatus()

        wait_on_job( bat, job, 10 )

        assert x1 == None
        st,x2 = job.getStatus()
        assert x2 == 'fail'


############################################################################

def run_batch_job_with_stdouterr_capture( batchobj, job, *lines ):
    """
    Write batch script with the given command lines, submit the job, then
    wait on the job.  All output written to stdout and stderr during submit
    and job wait is captured and returned as a string.
    """
    job.setRunCommands( '\n'.join(lines)+'\n' )

    batchobj.writeScriptFile( job )

    redir = util.Redirect( 'job.log' )
    try:
        batchobj.submit( job )
        wait_on_job( batchobj, job, 5 )

    finally:
        redir.close()

    fp = open( 'job.log', 'r' )
    out = fp.read()
    fp.close()

    return out


def write_and_submit_batch_job( batchobj, job, *lines ):
    """
    Write batch script and submit the job.
    """
    job.setRunCommands( '\n'.join(lines)+'\n' )
    batchobj.writeScriptFile( job )
    batchobj.submit( job )


def wait_on_job( batchobj, jobobj, maxwait=60 ):
    ""
    tstart = time.time()

    while True:

        batchobj.poll()

        st,x = jobobj.getStatus()
        if x != None:
            break

        if time.time() - tstart > maxwait:
            raise Exception( 'max wait time exceeded: '+str(maxwait) )

        time.sleep(1)
