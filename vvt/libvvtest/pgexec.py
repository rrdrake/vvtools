#!/usr/bin/env python

import sys, os
import subprocess
import signal
import time


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
