#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
import os
import time
import glob

from . import TestList
from . import testlistio


class BatchScheduler:

    def __init__(self, test_dir, tlist, statushandler,
                       accountant, namer, perms,
                       plat, maxjobs, clean_exit_marker):
        self.test_dir = test_dir
        self.tlist = tlist
        self.statushandler = statushandler
        self.accountant = accountant
        self.namer = namer
        self.perms = perms
        self.plat = plat
        self.maxjobs = maxjobs
        self.clean_exit_marker = clean_exit_marker

    def numInFlight(self):
        """
        Returns the number of batch jobs are still running or stopped but
        whose results have not been read yet.
        """
        return self.accountant.numInFlight()

    def numPastQueue(self):
        ""
        return self.accountant.numPastQueue()

    def numStarted(self):
        """
        Number of batch jobs currently running (those that have been started
        and still appear to be in the batch queue).
        """
        return self.accountant.numStarted()

    def numDone(self):
        """
        Number of batch jobs that ran and completed.
        """
        return self.accountant.numDone()

    def checkstart(self):
        """
        Launches a new batch job if possible.  If it does, the batch id is
        returned.
        """
        if self.accountant.numStarted() < self.maxjobs:
            for qid,bjob in self.accountant.getNotStarted():
                if self.getBlockingDependency( bjob ) == None:
                    pin = self.namer.getBatchScriptName( qid )
                    jobid = self.plat.Qsubmit( self.test_dir, bjob.outfile, pin )
                    self.accountant.markJobStarted( qid, jobid )
                    return qid
        return None

    def checkdone(self):
        """
        Uses the platform to find batch jobs that ran but are now no longer
        in the batch queue.  These jobs are moved from the started list to
        the stopped list.

        Then the jobs in the "stopped" list are visited and their test
        results are read.  When a job is successfully read, the job is moved
        from the "stopped" list to the "read" list.

        Returns a list of job ids that were removed from the batch queue,
        and a list of tests that were successfully read in.
        """
        qdoneL = []
        startlist = self.accountant.getStarted()
        if len(startlist) > 0:
            jobidL = [ jb.jobid for qid,jb in startlist ]
            statusD = self.plat.Qquery( jobidL )
            tnow = time.time()
            for qid,bjob in list( startlist ):
                if self.checkJobDone( bjob, statusD[ bjob.jobid ], tnow ):
                    self.accountant.markJobStopped( qid )
                    qdoneL.append( qid )

        tnow = time.time()
        tdoneL = []
        for qid,bjob in list( self.accountant.getStopped() ):
            if bjob.timeToCheckIfFinished( tnow ):
                if self.checkJobFinished( bjob.outfile, bjob.resultsfile ):
                    # load the results into the TestList
                    tdoneL.extend( self.finalizeJob( qid, bjob, 'clean' ) )
                else:
                    if not bjob.extendFinishCheck( tnow ):
                        # too many attempts to read; assume the queue job
                        # failed somehow, but force a read anyway
                        tdoneL.extend( self.finalizeJob( qid, bjob ) )

        return qdoneL, tdoneL

    def checkJobDone(self, bjob, queue_status, current_time):
        """
        If either the output file exists or enough time has elapsed since the
        job was submitted, then mark the BatchJob as having started.

        Returns true if the job was started.
        """
        started = False
        elapsed = current_time - bjob.tstart

        if not queue_status:
            if elapsed > 30 or os.path.exists( bjob.outfile ):
                started = True

        if os.path.exists( bjob.outfile ):
            self.perms.set( bjob.outfile )

        return started

    def checkJobFinished(self, outfilename, resultsname):
        """
        """
        finished = False
        if self.scanBatchOutput( outfilename ):
            finished = self.testListFinished( resultsname )
        return finished

    def scanBatchOutput(self, outfile):
        """
        Tries to read the batch output file, then looks for the marker
        indicating a clean job script finish.  Returns true for a clean finish.
        """
        clean = False

        try:
            # compute file seek offset, and open the file
            sz = os.path.getsize( outfile )
            off = max(sz-512, 0)
            fp = open( outfile, 'r' )
        except Exception:
            pass
        else:
            try:
                # only read the end of the file
                fp.seek(off)
                buf = fp.read(512)
            except Exception:
                pass
            else:
                if self.clean_exit_marker in buf:
                    clean = True
            try:
                fp.close()
            except Exception:
                pass

        return clean

    def testListFinished(self, resultsname):
        """
        Opens the test list file produced by a batch job and looks for the
        finish date mark.  Returns true if found.
        """
        finished = False

        try:
            tlr = testlistio.TestListReader( resultsname )
            if tlr.scanForFinishDate() != None:
                finished = True
        except Exception:
            pass

        return finished

    def flush(self):
        """
        Remove any remaining jobs from the "todo" list, add them to the "read"
        list, but mark them as not run.

        Returns a triple
            - a list of batch ids that were not run
            - a list of batch ids that did not finish
            - a list of the tests that did not run, each of which is a
              pair (a test, failed dependency test)
        """
        # should not be here if there are jobs currently running
        assert self.accountant.numInFlight() == 0

        # force remove the rest of the jobs that were not run and gather
        # the list of tests that were not run
        notrunL = []
        for qid,bjob in list( self.accountant.getNotStarted() ):
            tx1 = self.getBlockingDependency( bjob )
            assert tx1 != None  # otherwise checkstart() should have ran it
            for tx0 in bjob.testL:
                notrunL.append( (tx0,tx1) )
            self.accountant.markJobDone( qid, 'notrun' )
        
        # TODO: rather than only reporting the jobs left on qtodo as not run,
        #       loop on all jobs in qread and look for 'notrun' mark

        notrun = []
        notdone = []
        for qid,bjob in self.accountant.getDone():
            if bjob.result == 'notrun': notrun.append( str(qid) )
            elif bjob.result == 'notdone': notdone.append( str(qid) )

        return notrun, notdone, notrunL

    def finalizeJob(self, qid, bjob, mark=None):
        """
        """
        tL = []

        if not os.path.exists( bjob.outfile ):
            mark = 'notrun'
        
        elif os.path.exists( bjob.resultsfile ):
            if mark == None:
                mark = 'notdone'

            self.tlist.readTestResults( bjob.resultsfile )

            tlr = testlistio.TestListReader( bjob.resultsfile )
            tlr.read()
            jobtests = tlr.getTests()

            # only add tests to the stopped list that are done
            for tx in bjob.testL:
                xdir = tx.atest.getExecuteDirectory()

                tspec = jobtests.get( xdir, None )
                if tspec and self.statushandler.isDone( tspec ):
                    tL.append( tx.atest )
                    self.tlist.stopped[ xdir ] = tx
        
        else:
            mark = 'fail'
        
        self.accountant.markJobDone( qid, mark )

        return tL

    def getBlockingDependency(self, bjob):
        """
        If a dependency of any of the tests in the current list have not run or
        ran but did not pass or diff, then that dependency test is returned.
        Otherwise None is returned.
        """
        for tx in bjob.testL:
            deptx = tx.getBlockingDependency()
            if deptx != None:
                return deptx
        return None


class BatchJob:
    
    def __init__(self, maxnp, fout, resultsfile, testL,
                       read_interval, read_timeout):
        self.maxnp = maxnp
        self.outfile = fout
        self.resultsfile = resultsfile
        self.testL = testL  # list of TestExec objects
        self.jobid = None
        self.tstart = None
        self.tstop = None
        self.tcheck = None
        self.result = None
        self.read_interval = read_interval
        self.read_timeout = read_timeout

    def start(self, jobid):
        """
        """
        self.jobid = jobid
        self.tstart = time.time()

    def stop(self):
        """
        """
        self.tstop = time.time()
        self.tcheck = self.tstop + self.read_interval

    def timeToCheckIfFinished(self, current_time):
        """
        """
        return self.tcheck < current_time

    def extendFinishCheck(self, current_time):
        """
        Resets the finish check time to a time into the future.  Returns
        False if the number of extensions has been exceeded.
        """
        if current_time < self.tstop+self.read_timeout:
            # set the time for the next read attempt
            self.tcheck = current_time + self.read_interval
            return False
        return True

    def finished(self, result):
        """
        """
        assert result in ['clean','notrun','notdone','fail']
        self.result = result


class BatchFileNamer:

    def __init__(self, rootdir, listbasename):
        """
        """
        self.rootdir = rootdir
        self.listbasename = listbasename

    def getTestListName(self, qid, relative=False):
        """
        """
        return self.getPath( self.listbasename, qid, relative )

    def getBatchScriptName(self, qid):
        """
        """
        return self.getPath( 'qbat', qid )

    def getBatchOutputName(self, qid):
        """
        """
        return self.getPath( 'qbat-out', qid )

    def getPath(self, basename, qid, relative=False):
        """
        Given a base file name and a batch id, this function returns the
        file name in the batchset subdirectory and with the id appended.
        If 'relative' is true, then the path is relative to the TestResults
        directory.
        """
        subd = self.getSubdir( qid, relative )
        fn = os.path.join( subd, basename+'.'+str(qid) )
        return fn

    def getSubdir(self, qid, relative=False):
        """
        Given a queue/batch id, this function returns the corresponding
        subdirectory name.  The 'qid' argument can be a string or integer.
        """
        d = 'batchset' + str( int( float(qid)/50 + 0.5 ) )
        if relative:
            return d
        return os.path.join( self.rootdir, d )

    def globBatchDirectories(self):
        """
        Returns a list of existing batch working directories.
        """
        dL = []
        for f in os.listdir( self.rootdir ):
            if f.startswith( 'batchset' ):
                dL.append( os.path.join( self.rootdir, f ) )
        return dL


class BatchAccountant:

    def __init__(self):
        # queue jobs to be submitted, qid -> BatchJob
        self.qtodo = {}
        # queue jobs submitted, qid -> BatchJob
        self.qstart = {}
        # queue jobs submitted then have left the queue, qid -> BatchJob
        self.qstop  = {}
        # queue jobs whose final results have been read, qid -> BatchJob
        self.qdone  = {}

    def addJob(self, qid, batchjob ):
        """
        """
        self.qtodo[ qid ] = batchjob

    def numStarted(self):
        return len( self.qstart )

    def numDone(self):
        return len( self.qdone )

    def numInFlight(self):
        return len( self.qstart ) + len( self.qstop )

    def numPastQueue(self):
        return len( self.qstop ) + len( self.qdone )

    def getNotStarted(self):
        """
        """
        return self.qtodo.items()

    def getStarted(self):
        """
        """
        return self.qstart.items()

    def getStopped(self):
        """
        """
        return self.qstop.items()

    def getDone(self):
        """
        """
        return self.qdone.items()

    def markJobStarted(self, qid, jobid):
        """
        """
        jb = self.popJob( qid )
        jb.start( jobid )
        self.qstart[ qid ] = jb

    def markJobStopped(self, qid):
        """
        """
        jb = self.popJob( qid )
        jb.stop()
        self.qstop[ qid ] = jb

    def markJobDone(self, qid, done_mark):
        """
        """
        jb = self.popJob( qid )
        jb.finished( done_mark )
        self.qdone[ qid ] = jb

    def popJob(self, qid):
        """
        """
        if qid in self.qtodo: return self.qtodo.pop( qid )
        if qid in self.qstart: return self.qstart.pop( qid )
        if qid in self.qstop: return self.qstop.pop( qid )
        if qid in self.qdone: return self.qdone.pop( qid )
        raise Exception( 'job id not found: '+str(qid) )

