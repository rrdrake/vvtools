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

        state : state of the job in the queue; can be
                    absent  : job not found in the queue listing
                    queue   : job is in the queue
                    running : job is in the queue and marked running
                    done    : job is in the queue marked completed, or was
                              previously in the queue but is no longer

        exit  : job exit status; can be
                    ok      : script ran and completed
                    fail    : script ran but failed to complete
                    missing : time expired waiting for the job to show up in
                              the queue, or for the log file to be created
                    killed  : the batch interface was told to kill/cancel the job


    commands:
        A string with newlines containing the commands to run in the batch job.
    """


    def __init__(self):
        ""
        self.name = 'job'
        self.nnodes = 1
        self.fname = self.name+'_'+str(id(self))+'.sh'
        self.rundir = '.'
        self.cmds = '\n'
        self.logfname = self.name+'_'+str(id(self))+'.log'
        self.rtime = 60*60
        self.qname = None
        self.account = None

        self.jobid = None
        self.subout = None
        self.suberr = None
        self.subdate = None
        self.rundate = None
        self.donedate = None
        self.startdate = None
        self.stopdate = None
        self.state = None
        self.exit = None

        self.lock = threading.Lock()

    # job specifications

    def setName(self, name): self.name = name
    def getName(self): return self.name

    def setNumNodes(self, num_nodes): self.nnodes = num_nodes
    def getNumNodes(self): return self.nnodes

    def setBatchFileName(self, filename): self.fname = filename
    def getBatchFileName(self): return self.fname

    def setRunDirectory(self, rundir): self.rundir = rundir
    def getRunDirectory(self): return self.rundir

    def setRunCommands(self, commands): self.cmds = commands
    def getRunCommands(self): return self.cmds

    def setLogFileName(self, filename): self.logfname = filename
    def getLogFileName(self): return self.logfname

    def setRunTime(self, queue_time): self.rtime = queue_time
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
    def getQueueDates(self): return self.subdate, self.rundate, self.donedate

    @thread_lock
    def getRunDates(self): return self.startdate, self.stopdate

    @thread_lock
    def getStatus(self): return self.state, self.exit

    # result set methods

    @thread_lock
    def setJobId(self, jobid): self.jobid = jobid

    @thread_lock
    def setSubmitOutput(self, out=None, err=None):
        if out != None: self.subout = out
        if err != None: self.suberr = err

    @thread_lock
    def setQueueDates(self, sub=None, run=None, done=None):
        if sub != None: self.subdate = sub
        if run != None: self.rundate = run
        if done != None: self.donedate = done

    @thread_lock
    def setRunDates(self, start=None, stop=None):
        if start != None: self.startdate = start
        if stop != None: self.stopdate = stop

    @thread_lock
    def setStatus(self, state=None, exit=None):
        if state != None: self.state = state
        if exit != None: self.exit = exit

    @thread_lock
    def testThreadLock(self, num_seconds):
        """
        Only used for testing, this function acquires the lock then sleeps.
        """
        time.sleep( num_seconds )