#!/usr/bin/env python

import sys
import os
import time

import TestList


class BatchJob:
    
    def __init__(self, maxnp, fout, flist, testL,
                       read_interval, read_timeout):
        self.maxnp = maxnp
        self.outfile = fout
        self.testfile = flist
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
        Given a queue/batch/pipe id, this function returns the corresponding
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

