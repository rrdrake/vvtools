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
import threading


class ScriptRunner:

    def __init__(self):
        ""
        self.queued = {}
        self.running = {}
        self.done = {}

    def submit(self, bash_script, delay=None, redirect=None, timeout=None):
        ""
        ps = ScriptProcess( bash_script, redirect, timeout )

        startat = time.time()
        if delay != None:
            startat += delay

        self.queued[ ps.getId() ] = [ ps, startat ]

        return ps

    def poll(self):
        ""
        tm = time.time()

        qL = list( self.queued.items() )
        for rid,L in qL:
            ps,startat = L
            if not startat > tm:
                ps.run()
                self.queued.pop( rid )
                self.running[ rid ] = ps

        rL = list( self.running.items() )
        for rid,ps in rL:
            x = ps.poll()
            if x != None:
                self.running.pop( rid )
                self.done[ rid ] = ps


###########################################################################

class ScriptProcess:

    # use a persistent counter to provide unique ids for each run
    counter = 1

    def __init__(self, script_filename, redirect=None, timeout=None):
        ""
        self.procid = ScriptProcess.counter
        ScriptProcess.counter += 1

        self.script = script_filename

        if redirect != None and type(redirect) != type(''):
            raise ValueError( 'redirect must be None or a string' )
        if timeout != None and \
           ( type(timeout) != type(2) and type(timeout) != type(2.2) ):
            raise ValueError( 'timeout must be None or a number' )

        self.redirect = redirect
        self.timeout = timeout

        self.proc = None

        self.state = ''
        self.tstart = None
        self.tstop = None
        self.exit = None

        self.lock = threading.Lock()

    def getId(self):
        ""
        return self.procid

    def run(self):
        ""
        assert not self.state

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

        self.setResults( state='running', start=t0 )

    def poll(self):
        """
        Call this periodically until the exit status is not None.

        Note: This is the only function that should call setResults()
              to set the exit status.
        """
        if self.proc != None:

            tm = time.time()

            if self.state == 'running':
                
                x = self.proc.poll()

                if x == None:
                    if self.timeout != None and tm-self.tstart > self.timeout:
                        self._terminate()
                        self.setResults( state='timeout' )

                else:
                    self.setResults( state='exit', stop=tm, exit=x )

            elif self.exit == None:

                x = self.proc.poll()

                if x != None:
                    self.setResults( stop=tm, exit=x )

        return self.exit

    def kill(self):
        ""
        self._terminate()
        self.setResults( state='killed' )

    def _terminate(self):
        ""
        if hasattr( self.proc, 'terminate' ):
            self.proc.terminate()
        else:
            os.kill( self.proc.pid, signal.SIGTERM )

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
    def getResults(self):
        """
        Returns a tuple

            ( state, start time, stop time, exit status )

        where the state value is a string:

            <empty> : the run() method has not been called
            running : the subprocess was launched
            timeout : the subprocess timed out and was killed
            killed  : the kill() method was called
            exit    : the subprocess completed on its own

        The start time is the time the run() function was called.

        The stop time is the time the poll() function recognized that the
        subprocess exited.

        The exit status is the subprocess.returncode, which is None if still
        running or an integer if exited.
        """
        return self.state, self.tstart, self.tstop, self.exit

    def isDone(self):
        ""
        st,t0,t1,x = self.getResults()
        return st and x != None

    def getStatus(self):
        ""
        st,t0,t1,x = self.getResults()
        return st,x

    def getDates(self):
        ""
        st,t0,t1,x = self.getResults()
        return t0,t1

    @thread_lock
    def setResults(self, state=None, start=None, stop=None, exit=None):
        ""
        if state != None: self.state = state
        if start != None: self.tstart = start
        if stop != None: self.tstop = stop
        if exit != None: self.exit = exit

    @thread_lock
    def testThreadLock(self, num_seconds):
        """
        Only used for testing, this function acquires the lock then sleeps.
        """
        time.sleep( num_seconds )
