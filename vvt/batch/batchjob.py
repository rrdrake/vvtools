#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import time
import threading


class BatchJob:
    """
    Job specifications are stored in this object, as are the results of
    submitting and running the job.

    Specification names and values are:

        name       : the name of the job
        num nodes  : the requested number of compute nodes
        batch file : the batch script file name to write, submit, and run
        work dir   : the working directory in which to run the batch file
        commands   : bash commands to run (a string, newline separated)
        log file   : stdout and stderr is redirected to this file
        time       : requested time for the allocation
        queue      : the queue/partition to submit the job
        account    : resource account name

    Result names and values are:

        jobid : the job id given back from submission

        submit out : stdout from submission command
        submit err : stderr from submission command

        submit date : date submitted to the queue
        run date    : start date according to the queue
        done date   : date the job completed according to the queue, or the
                      first date it was observed to no longer be in the queue,
                      or the date the job was killed/cancelled
        start date  : script start date according to the log file
        stop date   : script exit date according to the log file

        state : state of the job in the queue; if the job script runs and
                provably exits, then the state will not change; can be
                    absent  : job not found in the queue listing
                    queue   : job is in the queue
                    running : job is in the queue and marked running
                    done    : job is in the queue marked completed, or was
                              previously in the queue but is no longer

        exit  : job exit status; can be
                    ok      : script ran and completed
                    fail    : script ran but failed to complete (no stop date)
                    missing : time expired waiting for the job to show up in
                              the queue, or for the log file to be created
                    killed  : the batch interface was told to kill/cancel the job


        submit jobid : the job id given back from submission
        submit out : stdout from submission command
        submit err : stderr from submission command

        Q submit date  : date submitted to the queue
        Q pending date : first time batch system showed job as pending
        Q running date : first time batch system showed job as running
        Q completed date : date the batch system showed the job completed
        Q done date : one of the following:
                        1. the first date the job was absent from the queue
                           after appearing as "pending" or "running"
                        2. the first date the job was marked by the queue as
                           "completed"
                        3. the date the timeout was reached waiting for the
                           job to appear in the queue at all

        script start date : start date from the script log file
        script stop date : stop date from the script log file
        script done date : one of the following:
                        1. first time the stop date was parsed
                        2. the date the timeout was reached after the queue
                           done date was set


    commands:
        A string with newlines containing the commands to run in the batch job.
    """


    def __init__(self):
        ""
        self.name = 'job'
        self.nprocs = (1,1)
        self.fname = os.path.abspath( self.name+'_'+str(id(self))+'.sh' )
        self.rundir = '.'
        self.cmds = '\n'
        self.logfname = os.path.abspath( self.name+'_'+str(id(self))+'.log' )
        self.rtime = 60*60
        self.qname = None
        self.account = None

        self.jobid = None
        self.subout = None
        self.suberr = None

        self.qdates = {}
        self.scriptdates = {}

        self.lock = threading.Lock()

    # job specifications

    def setName(self, name): self.name = name
    def getName(self): return self.name

    def setBatchFileName(self, filename): self.fname = os.path.abspath( filename )
    def getBatchFileName(self): return self.fname

    def setRunDirectory(self, rundir): self.rundir = os.path.abspath( rundir )
    def getRunDirectory(self): return self.rundir

    def setRunCommands(self, commands): self.cmds = commands
    def getRunCommands(self): return self.cmds

    def setLogFileName(self, filename): self.logfname = os.path.abspath( filename )
    def getLogFileName(self): return self.logfname

    # resource specifications

    def setProcessors(self, num_cores, num_nodes):
        self.nprocs = ( num_cores, num_nodes )
    def getProcessors(self):
        return self.nprocs

    def setRunTime(self, runtime): self.rtime = runtime
    def getRunTime(self): return self.rtime

    def setQueueName(self, queue_name): self.qname = queue_name
    def getQueueName(self): return self.qname

    def setAccount(self, account): self.account = account
    def getAccount(self): return self.account

    # job results

    def thread_lock(func):
        ""
        def thread_lock_wrapper( self, *args, **kwargs ):
            self.lock.acquire()
            try:
                rtn = func( self, *args, **kwargs )
            finally:
                self.lock.release()
            return rtn

        return thread_lock_wrapper

    @thread_lock
    def getJobId(self): return self.jobid

    @thread_lock
    def getSubmitOutput(self): return self.subout, self.suberr

    @thread_lock
    def getQueueDates(self):
        S = ( self.qdates.get( 'submit', None ),
              self.qdates.get( 'pending', None ),
              self.qdates.get( 'run', None ),
              self.qdates.get( 'complete', None ),
              self.qdates.get( 'done', None ) )
        return S

    @thread_lock
    def getScriptDates(self):
        S = ( self.scriptdates.get( 'start', None ),
              self.scriptdates.get( 'stop', None ),
              self.scriptdates.get( 'done', None ) )
        return S

    @thread_lock
    def isFinished(self):
        """
        """
        return self.qdates.get( 'done', None ) != None and \
               self.scriptdates.get( 'done', None )

    # result set methods

    @thread_lock
    def setJobId(self, jobid): self.jobid = jobid

    @thread_lock
    def setSubmitOutput(self, out=None, err=None):
        if out != None: self.subout = out
        if err != None: self.suberr = err

    @thread_lock
    def setQueueDates(self, submit=None, pending=None, run=None,
                            complete=None, done=None):
        set_date_attr( self.qdates, 'submit', submit )
        set_date_attr( self.qdates, 'pending', pending )
        set_date_attr( self.qdates, 'run', run )
        set_date_attr( self.qdates, 'complete', complete )
        set_date_attr( self.qdates, 'done', done )

    @thread_lock
    def setScriptDates(self, start=None, stop=None, done=None):
        set_date_attr( self.scriptdates, 'start', start )
        set_date_attr( self.scriptdates, 'stop', stop )
        set_date_attr( self.scriptdates, 'done', done )

    @thread_lock
    def testThreadLock(self, num_seconds):
        """
        Only used for testing, this function acquires the lock then sleeps.
        """
        time.sleep( num_seconds )


def set_date_attr( attrs, name, value ):
    """
    """
    if value and name not in attrs:
        attrs[ name ] = value
