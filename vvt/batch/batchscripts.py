#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import time
import subprocess
import signal

import batchitf


class BatchScripts( batchitf.BatchInterface ):
    """
    This class implements the BatchInterface using subprocesses.
    """

    def __init__(self):
        ""
        batchitf.BatchInterface.__init__(self)

        self.sprocs = batchitf.ThreadSafeMap()  # proc id -> ScriptProcess

    def writeScriptHeader(self, job, fileobj):
        ""
        pass  # no header necessary

    def submitJobScript(self, job):
        """
        """
        batname = job.getBatchFileName()
        logname = job.getLogFileName()
        timeout = job.getRunTime()

        sproc = ScriptProcess( batname, redirect=logname, timeout=timeout )
        sproc.run()

        jid = str( sproc.getId() )
        out = 'Job ID: '+jid
        err = ''

        self.sprocs.set( jid, sproc )

        return jid,out,err

    def queryQueue(self, jqtab):
        """
        Only one thread at a time should call this function because it reads
        and writes ScriptProcess data.
        """
        for jid,sproc in self.sprocs.asList():

            sproc.poll()

            start,stop = sproc.getDates()

            if not start:
                state = 'pending'
            elif not stop:
                state = 'running'
            else:
                state = 'done'
                self.sprocs.pop( jid )

            if stop:
                timeused = stop-start
            else:
                timeused = None

            jqtab.setJobInfo( jid, state, start, timeused )

    def cancel(self, job_list=None):
        ""
        pass


##########################################################################

class ScriptProcess:

    # use a persistent counter to provide unique ids for each run
    counter = 1

    def __init__(self, script_filename, redirect=None, timeout=None):
        ""
        self.procid = ScriptProcess.counter
        ScriptProcess.counter += 1

        self.script = script_filename

        self.redirect = redirect
        self.timeout = timeout

        self.proc = None
        self.tstart = None
        self.tstop = None

    def getId(self):
        ""
        return self.procid

    def run(self):
        ""
        assert self.proc == None

        t0 = time.time()

        if self.redirect:
            fp = open( self.redirect, 'w' )
            try:
                self.proc = subprocess.Popen(
                                ['bash',self.script],
                                stdout=fp.fileno(),
                                stderr=subprocess.STDOUT )
            finally:
                fp.close()
        else:
            self.proc = subprocess.Popen( ['bash',self.script] )

        self.tstart = t0

    def poll(self):
        ""
        if self.proc != None:

            tm = time.time()

            x = self.proc.poll()

            if x == None:
                if self.timeout != None and tm-self.tstart > self.timeout:
                    self._terminate()
                    self.timeout = None  # avoid repeated terminations

            else:
                self.tstop = tm
                self.proc = None

    def kill(self):
        ""
        if self.proc != None:
            self._terminate()

    def _terminate(self):
        ""
        if hasattr( self.proc, 'terminate' ):
            self.proc.terminate()
        else:
            os.kill( self.proc.pid, signal.SIGTERM )

    def getDates(self):
        """
        Returns ( start time, stop time )

        The start time is the time the run() function was called.

        The stop time is the time the poll() function recognized that the
        subprocess exited.
        """
        return self.tstart, self.tstop
