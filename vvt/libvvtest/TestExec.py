#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import subprocess
import signal
import time
import traceback


# if a test times out, it receives a SIGINT.  if it doesn't finish up
# after that in this number of seconds, it gets sent a SIGKILL
interrupt_to_kill_timeout = 30


class TestExec:
    """
    Runs a test in the background and provides methods to poll and kill it.
    """
    
    def __init__(self):
        ""
        self.timeout = 0
        self.rundir = None
        self.resource_obj = None

        self.pid = None
        self.tstart = None
        self.tstop = None

    def setRunDirectory(self, rundir):
        ""
        self.rundir = rundir

    def getRunDirectory(self):
        ""
        return self.rundir

    def setTimeout(self, value):
        ""
        self.timeout = value

    def getTimeout(self):
        ""
        return self.timeout

    def setExecutionHandler(self, handler):
        ""
        self.handler = handler

    def setResourceObject(self, obj):
        ""
        self.resource_obj = obj

    def getResourceObject(self):
        ""
        return self.resource_obj

    def start(self, baseline=0):
        """
        Launches the child process.
        """
        assert self.pid == None

        self.timedout = 0  # holds time.time() if the test times out
        self.tstart = time.time()

        sys.stdout.flush() ; sys.stderr.flush()

        self.pid = os.fork()
        if self.pid == 0:
            # child process is the test itself
            self._prepare_and_execute_test( baseline )

    def getStartTime(self):
        ""
        return self.tstart

    def poll(self):
        """
        """
        if self.tstart == None:
            return False

        if self.tstop != None:
            return True

        assert self.pid > 0

        cpid,code = os.waitpid( self.pid, os.WNOHANG )

        if cpid > 0:

            # test finished

            self.tstop = time.time()

            if self.timedout > 0:
                exit_status = None
            else:
                exit_status = decode_subprocess_exit_code( code )

            self.handler.finishExecution( exit_status, self.timedout )

        elif self.timeout > 0:
            # not done .. check for timeout
            tm = time.time()
            if tm-self.tstart > self.timeout:
                if self.timedout == 0:
                    # interrupt all processes in the process group
                    self.signalJob( signal.SIGINT )
                    self.timedout = tm
                elif (tm - self.timedout) > interrupt_to_kill_timeout:
                    # SIGINT isn't killing fast enough, use stronger method
                    self.signalJob( signal.SIGTERM )

        return self.tstop != None
    
    def signalJob(self, sig):
        """
        Sends a signal to the job, such as signal.SIGINT.
        """
        try:
            os.kill( self.pid, sig )
        except Exception:
            pass
    
    def killJob(self):
        """
        Sends the job a SIGINT signal, waits a little, and if the job
        has not shutdown, sends it SIGTERM followed by SIGKILL.
        """
        self.signalJob( signal.SIGINT )
        time.sleep(2)

        if self.poll() == None:
            self.signalJob( signal.SIGTERM )
            time.sleep(5)
            self.poll()

    def _prepare_and_execute_test(self, baseline):
        ""
        try:
            os.chdir( self.rundir )

            cmd_list = self.handler.prepare_for_launch( baseline )

            sys.stdout.flush() ; sys.stderr.flush()

            if cmd_list == None:
                # this can only happen in baseline mode
                os._exit(0)
            else:
                x = group_exec_subprocess( cmd_list )
                os._exit(x)

        except:
            sys.stdout.flush() ; sys.stderr.flush()
            traceback.print_exc()
            sys.stdout.flush() ; sys.stderr.flush()
            os._exit(1)


def decode_subprocess_exit_code( exit_code ):
    ""
    if os.WIFEXITED( exit_code ):
        return os.WEXITSTATUS( exit_code )

    if os.WIFSIGNALED( exit_code ) or os.WIFSTOPPED( exit_code ):
        return 1

    if exit_code == 0:
        return 0

    return 1


def group_exec_subprocess( cmd, **kwargs ):
    """
    Run the given command in a subprocess in its own process group, then wait
    for it.  Catch all signals and dispatch them to the child process group.

    The SIGTERM and SIGHUP signals are sent to the child group, but they also
    cause a SIGKILL to be sent after a short delay.

    This function modifies the current environment by registering signal
    handlers, so the intended use is something like this

        pid = os.fork()
        if pid == 0:
            x = group_exec_subprocess( 'some command', shell=True )
            os._exit(x)
    """
    register_signal_handlers()

    terminate_delay = kwargs.pop( 'terminate_delay', 5 )

    kwargs[ 'preexec_fn' ] = lambda: os.setpgid( os.getpid(), os.getpid() )
    proc = subprocess.Popen( cmd, **kwargs )

    while True:
        try:
            x = proc.wait()
            break
        except KeyboardInterrupt:
            os.kill( -proc.pid, signal.SIGINT )
        except SignalException:
            e = sys.exc_info()[1]
            os.kill( -proc.pid, e.sig )
            if e.sig in [ signal.SIGTERM, signal.SIGHUP ]:
                x = check_terminate_subprocess( proc, terminate_delay )
                break
        except:
            os.kill( -proc.pid, signal.SIGTERM )

    return x


class SignalException( Exception ):
    def __init__(self, signum):
        self.sig = signum
        Exception.__init__( self, 'Received signal '+str(signum) )

def signal_handler( signum, frame ):
    raise SignalException( signum )


def register_signal_handlers( reset=False ):
    ""
    if reset:
        handler = signal.SIG_DFL
    else:
        handler = signal_handler

    signal.signal( signal.SIGTERM, handler )
    signal.signal( signal.SIGABRT, handler )
    signal.signal( signal.SIGHUP, handler )
    signal.signal( signal.SIGALRM, handler )
    signal.signal( signal.SIGUSR1, handler )
    signal.signal( signal.SIGUSR2, handler )


def check_terminate_subprocess( proc, terminate_delay ):
    ""
    if terminate_delay:
        time.sleep( terminate_delay )

    x = proc.poll()

    os.kill( -proc.pid, signal.SIGKILL )

    return x
