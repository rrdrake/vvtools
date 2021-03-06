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


class Batch_output_file:

    def setUp(self):
        ""
        util.setup_test()

        self.bat = self.makeBatchInterface()
        self.bat.setTimeout( 'script', 5 )
        self.bat.setTimeout( 'logcheck', 1 )
        self.job = BatchJob()

    def test_job_output_always_goes_to_a_file(self):
        ""
        out = run_batch_job_with_stdouterr_capture( self.bat, self.job,
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

        self.job.setLogFileName( 'odir/bat.log' )

        out = run_batch_job_with_stdouterr_capture( self.bat, self.job,
                'echo "grep for this statement"' )

        assert 'grep for this statement' not in out

        L = util.filegrep( 'odir/bat.log', 'grep for this statement' )
        assert len(L) == 1


class Batch_work_directory:

    def setUp(self):
        ""
        util.setup_test()

        self.bat = self.makeBatchInterface()
        self.bat.setTimeout( 'script', 5 )
        self.bat.setTimeout( 'logcheck', 1 )
        self.job = BatchJob()

    def grepLogFileFor_mycwd(self):
        ""
        fL = glob.glob( 'job_*.log' )
        assert len(fL) == 1

        L = util.filegrep( fL[0], 'mycwd=' )
        assert len(L) == 1

        d = L[0].split('mycwd=',1)[1].strip()

        return d

    def test_default_work_dir_is_current_dir(self):
        ""
        os.mkdir( 'wdir' )
        time.sleep(1)

        curdir = os.getcwd()
        os.chdir( 'wdir' )

        # construct job after changing directory
        self.job = BatchJob()

        out = run_batch_job_with_stdouterr_capture( self.bat, self.job,
                'echo "mycwd=`pwd`"' )

        d = self.grepLogFileFor_mycwd()
        assert os.path.samefile( curdir+'/wdir', d )

    def test_setting_work_dir_explicitely(self):
        ""
        os.mkdir( 'wdir' )
        time.sleep(1)

        curdir = os.getcwd()

        self.job.setRunDirectory( 'wdir' )

        out = run_batch_job_with_stdouterr_capture( self.bat, self.job,
                'echo "mycwd=`pwd`"' )

        os.path.samefile( curdir, os.getcwd() )
        d = self.grepLogFileFor_mycwd()
        assert os.path.samefile( curdir+'/wdir', d )


class Batch_submit:

    def setUp(self):
        ""
        util.setup_test()

        self.bat = self.makeBatchInterface()
        self.bat.setTimeout( 'script', 5 )
        self.bat.setTimeout( 'logcheck', 1 )
        self.job = BatchJob()

    def test_jobid_gets_defined_and_is_a_string(self):
        ""
        write_and_submit_batch_job( self.bat, self.job )

        jobid = self.job.getJobId()

        wait_on_job( self.bat, self.job, 5 )

        assert jobid != None and jobid.strip()

    def test_submit_stdout_stderr_gets_set(self):
        ""
        write_and_submit_batch_job( self.bat, self.job )

        subout,suberr = self.job.getSubmitOutput()

        wait_on_job( self.bat, self.job, 5 )

        assert subout.strip()
        assert not suberr.strip()


class Batch_queue_dates:

    def setUp(self):
        ""
        util.setup_test()

        self.bat = self.makeBatchInterface()
        self.bat.setTimeout( 'script', 5 )
        self.bat.setTimeout( 'logcheck', 1 )
        self.job = BatchJob()

    def test_submit_date_gets_set(self):
        ""
        curdate = time.time()

        write_and_submit_batch_job( self.bat, self.job, 'sleep 5' )
        time.sleep(1)
        self.bat.poll()

        sub1,pend1,run1,comp1,done1 = self.job.getQueueDates()

        wait_on_job( self.bat, self.job, 10 )

        sub2,pend2,run2,comp2,done2 = self.job.getQueueDates()

        assert sub1 and sub1 == sub2
        assert run1 and abs( curdate - run1 ) < 5
        assert run1 == run2
        assert not done1

    def test_batch_failure_always_has_done_date(self):
        ""
        write_and_submit_batch_job( self.bat, self.job,
            'sleep 2',
            'exit 1' )

        wait_on_job( self.bat, self.job, 10 )

        sub,pend,run,comp,done = self.job.getQueueDates()

        assert done and abs( done - time.time() ) < 10

    def test_a_running_job_has_a_run_date_but_no_done_date(self):
        ""
        write_and_submit_batch_job( self.bat, self.job, 'sleep 4' )

        self.bat.poll()
        time.sleep(1)
        self.bat.poll()

        dt,dt,run,dt,done = self.job.getQueueDates()

        wait_on_job( self.bat, self.job, 5 )

        assert ( time.time() - run ) < 10
        assert not done

    def test_a_finished_job_has_a_done_date(self):
        ""
        write_and_submit_batch_job( self.bat, self.job, 'sleep 1' )

        wait_on_job( self.bat, self.job, 5 )

        dt,dt,dt,dt,done = self.job.getQueueDates()
        assert ( time.time() - done ) < 10

    def test_a_failed_job_has_a_done_date(self):
        ""
        write_and_submit_batch_job( self.bat, self.job,
            'sleep 1',
            'exit 1' )

        wait_on_job( self.bat, self.job, 10 )

        dt,dt,dt,dt,done = self.job.getQueueDates()
        assert ( time.time() - done ) < 10


class Batch_start_stop_dates:

    def setUp(self):
        ""
        util.setup_test()

        self.bat = self.makeBatchInterface()
        self.bat.setTimeout( 'script', 5 )
        self.bat.setTimeout( 'logcheck', 1 )
        self.job = BatchJob()

    def test_queue_run_and_done_dates(self):
        ""
        write_and_submit_batch_job( self.bat, self.job, 'sleep 5' )

        self.bat.poll()
        time.sleep(1)
        self.bat.poll()

        sub1,pend1,run1,comp1,done1 = self.job.getQueueDates()

        wait_on_job( self.bat, self.job, 10 )

        sub2,pend2,run2,comp2,done2 = self.job.getQueueDates()

        assert run1 and run2 and run1 == run2
        assert done1 == None
        assert done2
        assert done2-run1 > 4 and done2-run1 < 10

    def test_run_start_and_stop_dates(self):
        ""
        write_and_submit_batch_job( self.bat, self.job, 'sleep 5' )

        wait_on_job( self.bat, self.job, 10 )

        start,stop,done = self.job.getScriptDates()

        assert start and stop
        assert stop-start > 4 and stop-start < 10

    def test_batch_failure_will_still_have_start_date(self):
        ""
        write_and_submit_batch_job( self.bat, self.job,
            'sleep 2',
            'exit 1' )

        wait_on_job( self.bat, self.job, 10 )

        start,stop,done = self.job.getScriptDates()

        assert start
        assert abs( start - time.time() ) < 10


class Batch_timeout:

    def setUp(self):
        ""
        util.setup_test()

        self.bat = self.makeBatchInterface()
        self.bat.setTimeout( 'script', 5 )
        self.bat.setTimeout( 'logcheck', 1 )
        self.job = BatchJob()

    def test_a_job_whose_runtime_takes_too_long(self):
        ""
        self.job.setRunTime( 4 )

        write_and_submit_batch_job( self.bat, self.job, 'sleep 30' )
        wait_on_job( self.bat, self.job, 10 )

        sub,pend,run,comp,done = self.job.getQueueDates()

        assert sub and run and done
        assert done-run >= 4 and done-run < 10


class Batch_cancel:

    def setUp(self):
        ""
        util.setup_test()

        self.bat = self.makeBatchInterface()
        self.bat.setTimeout( 'script', 5 )
        self.bat.setTimeout( 'logcheck', 1 )
        self.job = BatchJob()

    def test_cancel_a_running_job(self):
        ""
        t0 = time.time()

        write_and_submit_batch_job( self.bat, self.job, 'sleep 30' )

        time.sleep(2)
        self.bat.poll()

        self.bat.cancel( self.job )

        poll_and_sleep( self.bat, 4 )

        t1 = time.time()

        sub,pend,run,comp,qdone = self.job.getQueueDates()
        start,stop,sdone = self.job.getScriptDates()
        assert sub and run and qdone
        assert start
        assert qdone > run and qdone-run < 5
        assert t1-t0 < 10

    def test_cancel_one_of_two_running_jobs(self):
        ""
        job2 = BatchJob()
        t0 = time.time()

        write_and_submit_batch_job( self.bat, self.job, 'sleep 30' )
        write_and_submit_batch_job( self.bat, job2, 'sleep 10' )

        time.sleep(2)
        self.bat.poll()

        self.bat.cancel( self.job, verbose=True )

        poll_and_sleep( self.bat, 4 )

        t1 = time.time()

        sub,pend,run,comp,qdone = self.job.getQueueDates()
        start,stop,sdone = self.job.getScriptDates()

        wait_on_job( self.bat, job2, 10 )

        start2,stop2,sdone2 = job2.getScriptDates()

        assert sub and run and qdone
        assert start
        assert qdone > run and qdone-run < 5
        assert t1-t0 < 10

        assert job2.isFinished()
        assert start2 and stop2 and stop2-start2 > 5 and stop2-start2 < 14

    def test_cancel_all_running_jobs(self):
        ""
        job2 = BatchJob()
        t0 = time.time()

        write_and_submit_batch_job( self.bat, self.job, 'sleep 30' )
        write_and_submit_batch_job( self.bat, job2, 'sleep 40' )

        time.sleep(2)
        self.bat.poll()

        self.bat.cancel()

        poll_and_sleep( self.bat, 4 )

        sub1,pend1,run1,comp1,qdone1 = self.job.getQueueDates()
        start1,stop1,sdone1 = self.job.getScriptDates()
        assert sub1 and run1 and qdone1
        assert start1
        assert qdone1 > run1 and qdone1-run1 < 5

        sub2,pend2,run2,comp2,qdone2 = self.job.getQueueDates()
        start2,stop2,sdone2 = self.job.getScriptDates()
        assert sub2 and run2 and qdone2
        assert start2
        assert qdone2 > run2 and qdone2-run2 < 5


############################################################################

def run_batch_job_with_stdouterr_capture( batchobj, job, *lines ):
    """
    Write batch script with the given command lines, submit the job, then
    wait on the job.  All output written to stdout and stderr during submit
    and job wait is captured and returned as a string.
    """
    job.setRunCommands( '\n'.join(lines)+'\n' )

    batchobj.writeJob( job )

    redir = util.Redirect( 'job.log' )
    try:
        batchobj.submit( job )
        assert job.getJobId() != None
        wait_on_job( batchobj, job, 5 )

    except Exception:
        redir.close()
        sys.stderr.write( job.getSubmitOutput()[0] + '\n' )
        sys.stderr.write( job.getSubmitOutput()[1] + '\n' )
        sys.stderr.flush()
        raise
    else:
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
    batchobj.writeJob( job )
    batchobj.submit( job )

    assert job.getJobId() != None, \
        "Got None for a job id\n\n" + \
        job.getSubmitOutput()[0]+'\n'+ \
        job.getSubmitOutput()[1]+'\n'


def wait_on_job( batchobj, jobobj, maxwait=60 ):
    ""
    tstart = time.time()

    while True:

        batchobj.poll()

        if jobobj.isFinished():
            break

        if time.time() - tstart > maxwait:
            raise Exception( 'max wait time exceeded: '+str(maxwait) )

        time.sleep(1)


def poll_and_sleep( batchobj, num_seconds ):
    ""
    for i in range( int(num_seconds+0.5) ):
        batchobj.poll()
        time.sleep(1)
