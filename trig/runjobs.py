#!/usr/bin/env python

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import time
import subprocess
import threading
import pipes
import traceback


def run_job( jobname, *args, **kwargs ):
    """
    Runs a job, waits for it to finish, then returns the Job object.

    The shell command is formed from 'args', which must be length one or
    more.

    The keyword arguments are passed to the underlying Job object.
    """
    return RunJobs.inst.run_job( False, False, jobname, *args, **kwargs )


def run_shell_job( jobname, *args, **kwargs ):
    """
    Same as run_job() except that the shell is used to execute the command.
    
    If a single argument is given, it is passed to the shell directly.  If
    more than one argument is given, then each argument is treated as a
    separate argument in a combined command string.  So

        run_shell_job( 'job', 'ls -a "file name"' )

    would execute

        $ ls -a "file name"

    The following would execute the same thing:

        run_shell_job( 'job', 'ls', '-a', 'file name' )
    """
    return RunJobs.inst.run_job( True, False, jobname, *args, **kwargs )


def run_job_bg( jobname, *args, **kwargs ):
    """
    Runs a job in the background and returns the job id.
    """
    return RunJobs.inst.run_job( False, True, jobname, *args, **kwargs )


def run_shell_job_bg( jobname, *args, **kwargs ):
    """
    Same as run_job_bg() except the arguments are interpreted as they are
    in run_shell_job().
    """
    return RunJobs.inst.run_job( True, True, jobname, *args, **kwargs )


def poll_job( jobid ):
    """
    Returns True if the 'jobid' completed.  If the 'jobid' is unknown, an
    exception is raised.
    """
    return RunJobs.inst.poll( jobid )


def wait_job( jobid ):
    """
    Waits for the job to complete and returns the Job object.  The 'jobid'
    must exist otherwise an exception is raised.
    """
    return RunJobs.inst.wait( jobid )


###########################################################################

class Job:
    """
    Required attributes are:

        name
        command

    Optional attributes are:

        machine
        workdir
        logdir
        timeout
        poll_interval
    """

    def __init__(self, **kwargs):
        """
        """
        self.lock = threading.Lock()

        self.attrD = {}
        for n,v in kwargs.items():
            self.set( n, v )
    
    def __bool__(self):
        """
        This allows a Job class instance to be cast (coerced) to True/False.
        That is, an instance will evaluate to True if the job exited and the
        exit status is zero.  If the job has not been run yet, or is still
        running, or the exit status is non-zero, then it evaluates to False.
        """
        x = self.get( 'exit', 1 )
        if type(x) == type(2) and x == 0:
            return True
        return False
    __nonzero__ = __bool__

    def has(self, attr_name):
        """
        Returns True if the given attribute name is defined.
        """
        self.lock.acquire()
        try:
            v = ( attr_name in self.attrD )
        finally:
            self.lock.release()
        return v

    def get(self, attr_name, *default):
        """
        Get an attribute name.  If a default is given and the attribute name
        is not set, then the default is returned.
        """
        self.lock.acquire()
        try:
            if len(default) > 0:
                v = self.attrD.get( attr_name, default[0] )
            else:
                v = self.attrD[attr_name]
        finally:
            self.lock.release()
        return v

    def clear(self, attr_name):
        """
        """
        assert attr_name and attr_name == attr_name.strip()
        self.lock.acquire()
        try:
            if attr_name in self.attrD:
                self.attrD.pop( attr_name )
        finally:
            self.lock.release()

    def set(self, attr_name, attr_value):
        """
        Set an attribute.  The attribute name cannot be empty or contain
        spaces at the beginning or end of the string.

        Some attribute names have checks applied to their values.
        """
        assert attr_name and attr_name == attr_name.strip()

        if attr_name in ["name","machine"]:
            assert attr_value and attr_value == attr_value.strip()
        elif attr_name == 'timeout':
            attr_value = int( attr_value )
        elif attr_name == 'poll_interval':
            attr_value = int( attr_value )
            assert attr_value > 0
        self.lock.acquire()
        try:
            self.attrD[attr_name] = attr_value
        finally:
            self.lock.release()

    def date(self):
        """
        Returns a formatted date string with no spaces.  If a 'date' attribute
        is not already set, the current time is used to create the date and
        set the 'date' attribute.
        """
        if not self.get( 'date', None ):
            self.set( 'date', time.strftime( "%a_%b_%d_%Y_%H:%M:%S_%Z" ) )
        return self.get( 'date' )

    def logname(self):
        """
        Returns the log file name for the job (without the directory).
        """
        if not self.get( 'logname', None ):
            n = self.get( 'name' )
            m = self.get( 'machine', None )
            if m: n += '-' + m
            n += '-' + self.date() + '.log'
            self.set( 'logname', n )
        return self.get( 'logname' )

    def logpath(self):
        """
        Returns the remote log file path (directory plus file name).
        """
        if not self.get( 'logpath', None ):
            logn = self.logname()
            wd = self.get( 'workdir', RunJobs.getDefault( 'workdir', None ) )
            logd = self.get( 'logdir', RunJobs.getDefault( 'logdir', wd ) )
            if logd: logf = os.path.join( logd, logn )
            else:    logf = logn
            self.set( 'logpath', logf )
        return self.get( 'logpath' )

    def jobid(self):
        """
        Returns a tuple that uniquely identifies this job.
        """
        return ( self.get( 'name', None ),
                 self.get( 'machine', None ),
                 self.date() )
    
    def finalize(self):
        """
        Create the launch command.  An exception is raised if the job is not
        well formed.  Returns the job id.
        """
        self.jobid()
        assert self.has( 'command' )
        assert self.logname()

    def execute(self):
        """
        If the job does not have a 'machine' attribute, the command is run
        directly as a subprocess with all output redirected to a log file.
        When the command finishes, the exit status is set in the 'exit'
        attribute and this function returns.

        If the job has a 'machine' attribute, the remotepython.py module is
        used to run the command on the remote machine in the background.
        Output from the remote command is redirected to a log file, and that
        log file is brought back every 'poll_interval' seconds.  When the
        remote command finishes, the exit status is set in the 'exit'
        attribute and this function returns.
        """
        self.clear( 'exit' )

        mach = self.get( 'machine', None )

        if not mach:
            self._run_wait()
        else:
            self._run_remote( mach )

    def _run_wait(self):
        """
        """
        ipoll = self.get( 'poll_interval',
                          RunJobs.getDefault( 'poll_interval' ) )
        timeout = self.get( 'timeout', RunJobs.getDefault( 'timeout' ) )

        cmd = self.get( 'command' )
        wrkd = self.get( 'workdir', RunJobs.getDefault( 'workdir' ) )
        logn = self.logname()

        cwd = os.getcwd()
        logfp = open( logn, 'w' )
        
        x = None
        try:
            if wrkd: os.chdir( wrkd )
            x = runcmd( cmd, outfd=logfp.fileno(),
                             timeout=timeout,
                             poll_interval=ipoll )
        finally:
            logfp.close()
            os.chdir( cwd )
        
        self.set( 'exit', x )

    def _run_remote(self, mach):
        """
        """
        timeout = self.get( 'timeout', RunJobs.getDefault( 'timeout' ) )
        cmd = self.get( 'command' )
        wrkd = self.get( 'workdir', RunJobs.getDefault( 'workdir' ) )
        sshexe = self.get( 'sshexe', RunJobs.getDefault( 'sshexe' ) )
        numconn = self.get( 'connection_attempts',
                            RunJobs.getDefault( 'connection_attempts' ) )

        logf = self.logpath()

        mydir = os.path.dirname( os.path.abspath( __file__ ) )
        rfile = os.path.join( mydir, 'runjobs_remote.py' )

        from remotepython import RemotePython

        rmt = RemotePython( mach, rfile, sshexe=sshexe )

        tprint( 'Connect machine:', mach )
        tprint( 'Remote command:', cmd )
        if wrkd:
            tprint( 'Remote workdir:', wrkd )
        if timeout != None:
            tprint( 'Remote timeout:', timeout )

        T = self._connect( rmt, numconn )
        if T != None:
            sys.stderr.write( '[' + time.ctime() + '] ' + \
                'Connect exception for jobid '+str(self.jobid())+'\n' + T[1] )
            sys.stderr.flush()
            raise Exception( "Could not connect to "+mach )

        try:
            rmt.startTimeout( 30 )
            rusr = rmt.x_get_user_id()

            rmt.startTimeout( 30 )
            rpid = rmt.x_background_command( cmd, logf,
                                             workdir=wrkd,
                                             timeout=timeout )

            time.sleep(2)

            self._monitor( rmt, rusr, rpid )

        finally:
            rmt.shutdown()

    def _connect(self, rmtpy, limit=10):
        """
        Tries to make a connection to the remote machine.  It tries up to
        'limit' times, sleeping 2**i seconds between each attempt.  Returns
        None if a connection was made, otherwise the return value from
        capture_traceback().
        """
        assert limit > 0

        for i in range(limit):
            if i > 0:
                time.sleep( 2**i )
            rtn = None
            try:
                rmtpy.startTimeout( 30 )
                rmtpy.connect()
            except:
                #raise  # uncomment this when debugging connections
                rtn = capture_traceback( sys.exc_info() )
            else:
                break

        return rtn

    def _monitor(self, rmtpy, rusr, rpid):
        """
        """
        ipoll = self.get( 'remote_poll_interval',
                          RunJobs.getDefault( 'remote_poll_interval' ) )
        xinterval = self.get( 'exception_print_interval',
                        RunJobs.getDefault( 'exception_print_interval' ) )
        timeout = self.get( 'timeout', RunJobs.getDefault( 'timeout' ) )

        if timeout:
            ipoll = min( ipoll, int( 0.45 * timeout ) )

        logn = self.logname()
        logf = self.logpath()

        tstart = time.time()
        texc1 = tstart
        texc2 = tstart

        pause = 2
        while True:

            if not rmtpy.isConnected():
                T = self._connect( rmtpy, 1 )
                t = time.time()
                if T != None and t - texc1 > xinterval:
                    sys.stderr.write( '[' + time.ctime() + '] ' + \
                            'Warning: remote connection failed for jobid ' + \
                            str( self.jobid() ) + '\n' + T[1] + \
                            'Exception ignored; continuing to monitor...\n' )
                    sys.stderr.flush()
                    texc1 = t

            if rmtpy.isConnected():

                elapsed = True
                try:

                    self.updateFile( rmtpy, logf, logn )

                    rmtpy.startTimeout( 30 )
                    s = rmtpy.x_processes( pid=rpid, user=rusr,
                                           fields='etime' )
                    elapsed = s.strip()

                    # TODO: add a check that the elapsed time agrees
                    #       approximately with the expected elapsed time
                    #       since the job was launched

                except:
                    xs,tb = capture_traceback( sys.exc_info() )
                    t = time.time()
                    if t - texc2 > xinterval:
                        sys.stderr.write( '[' + time.ctime() + '] ' + \
                            'Warning: exception monitoring jobid ' + \
                            str( self.jobid() ) + '\n' + tb + \
                            'Exception ignored; continuing to monitor...\n' )
                        sys.stderr.flush()
                        texc2 = t

                self.scanExitStatus( logn )

                if not elapsed:
                    # remote process id not found - assume it is done
                    break

            if timeout and time.time()-tstart > timeout:
                sys.stderr.write( 'Monitor process timed out at ' + \
                    str( int(time.time()-tstart) ) + ' seconds for jobid ' + \
                    str( self.jobid() ) + '\n' )
                sys.stderr.flush()
                # TODO: try to kill the remote process
                break

            time.sleep( pause )
            pause = min( 2*pause, ipoll )

    def updateFile(self, rmtpy, logfile, logname):
        """
        As 'logfile' on the remote side grows, the new part of the file is
        transferred back to the local side and appended to 'logname'.
        """
        from remotepython import _BYTES_
        
        small = int( self.get( 'getlog_small_file_size',
                        RunJobs.getDefault( 'getlog_small_file_size' ) ) )
        chunksize = int( self.get( 'getlog_chunk_size',
                        RunJobs.getDefault( 'getlog_chunk_size' ) ) )

        lcl_sz = -1
        if os.path.exists( logname ):
            lcl_sz = os.path.getsize( logname )

        rmtpy.startTimeout( 30 )
        rmt_sz = rmtpy.x_file_size( logfile )

        if lcl_sz != rmt_sz and rmt_sz >= 0:
            if rmt_sz < small or lcl_sz > rmt_sz or lcl_sz < 0.2*rmt_sz:
                # for small files, or if somehow the local file is larger than
                # the remote, or if not much of the file has been transferred
                # yet, just do a complete file transfer
                rmtpy.startTimeout( 10*60 )
                rmtpy.getFile( logfile, logname, preserve=True )

            else:
                # only transfer the end of the remote file that has not
                # been obtained yet (the first part of the file is assumed
                # to be the same between local and remote)
                off = lcl_sz
                fp = open( logname, 'ab' )
                try:
                    # open the remote file
                    rmtpy.startTimeout( 30 )
                    mt, at, fm = rmtpy.x_open_file_read( logfile, off )

                    # get the tail of the file in chunks
                    while off < rmt_sz:
                        off2 = min( off + chunksize, rmt_sz )
                        rmtpy.startTimeout( 30 )
                        buf = rmtpy.x_file_read( off2-off )
                        fp.write( _BYTES_( buf ) )
                        off = off2
                
                finally:
                    fp.close()
                    rmtpy.startTimeout( 30 )
                    rmtpy.x_close_file()
                
                # match the date stamp and file mode
                os.utime( logname, (at,mt) )
                os.chmod( logname, fm )

    def scanExitStatus(self, logname):
        """
        Reads the end of the given log file name for "Subcommand exit:" and
        if found, the 'exit' attribute of this job is set to the value.
        """
        try:
            fp = None
            sz = os.path.getsize( logname )
            fp = open( logname, 'r' )
            if sz > 256:
                fp.seek( sz-256 )
            s = fp.read()
            fp.close() ; fp = None
            L = s.split( 'Subcommand exit:' )
            if len(L) > 1:
                x = L[-1].split( '\n' )[0].strip()
                if x.lower() == 'none':
                    # remote process timed out
                    x = None
                else:
                    try:
                        ix = int( x )
                    except:
                        # leave exit value as a string
                        pass
                    else:
                        # process exited normally
                        x = ix
                self.set( 'exit', x )

        except:
            if fp != None:
                fp.close()


#########################################################################

class RunJobs:
    
    def __init__(self):
        """
        """
        self.db = {}
        self.defaults = {
                            'poll_interval': 15,
                            'remote_poll_interval': 5*60,
                            'exception_print_interval': 15*60,
                            'timeout': None,
                            'workdir': None,
                            'sshexe': None,
                            'connection_attempts': 10,
                            'getlog_small_file_size': 5*1024,
                            'getlog_chunk_size': 512,
                        }

    inst = None  # a singleton RunJobs instance (set below)

    @staticmethod
    def jobDefault( attr_name, attr_value ):
        """
        Default values for job attributes can be set here.  Examples are
        'timeout' and 'poll_frequency'.
        """
        RunJobs.inst.defaults[ attr_name ] = attr_value

    @staticmethod
    def getDefault( attr_name, *args ):
        """
        Get the default value for a job attribute.
        """
        if len(args) > 0:
            return RunJobs.inst.defaults.get( attr_name, args[0] )
        return RunJobs.inst.defaults[ attr_name ]

    def insert(self, job, thr=None):
        """
        Insert the job into the database.
        """
        self.db[ job.jobid() ] = ( job, thr )

    def execute(self, job):
        """
        Add the given job in the database, run the job, and wait for it to
        finish.  Print a "done" message when finished.
        """
        self.insert( job )
        job.execute()
        tprint( 'JobDone:', 'jobid='+str(job.jobid()),
                'exit='+str(job.get('exit','')).strip(),
                'exc='+str(job.get('exc','')).strip() )

    def start(self, job):
        """
        Add the given job in the database and start the job execution in a
        separate thread.  Returns without waiting on the job.  The "done"
        message is printed at join time in poll() and wait().
        """
        # local function which serves as the thread entry point to run the
        # job; exceptions are caught, the 'exc' attribute set, and the
        # exception re-raised
        def threxec( jb ):
            try:
                jb.execute()
            except:
                xt,xv,xtb = sys.exc_info()
                xs = ''.join( traceback.format_exception_only( xt, xv ) )
                ct = time.ctime()
                jb.set( 'exc', '[' + ct + '] ' + xs )
                sys.stderr.write( '[' + ct + '] Exception: ' + xs + '\n' )
                raise

        t = threading.Thread( target=threxec, args=(job,) )
        t.setDaemon( True )  # so ctrl-C will exit the program
        self.insert( job, t )
        # set the thread name so exceptions include the job id
        if hasattr( t, 'setName' ):
            t.setName( str( job.jobid() ) )
        else:
            t.name = str( job.jobid() )
        t.start()

    def poll(self, jobid):
        """
        Tests for job completion.  Returns True if the underlying job thread
        has completed.
        """
        job,t = self.db[ jobid ]
        if t != None:
            if hasattr( t, 'is_alive' ):
                ia = t.is_alive()
            else:
                ia = t.isAlive()
            if not ia:
                t.join()
                self.db[ jobid ] = ( job, None )
                t = None
                tprint( 'JobDone:', 'jobid='+str(job.jobid()),
                        'exit='+str(job.get('exit','')).strip(),
                        'exc='+str(job.get('exc','')).strip() )
        return t == None

    def wait(self, jobid):
        """
        Waits for the job to complete (for the underlying job thread to finish)
        then returns the Job object.
        """
        job,t = self.db[ jobid ]
        if t != None:
            t.join()
            self.db[ jobid ] = ( job, None )
            tprint( 'JobDone:', 'jobid='+str(job.jobid()),
                    'exit='+str(job.get('exit','')).strip(),
                    'exc='+str(job.get('exc','')).strip() )
        return job

    def run_job(self, sh, bg, jobname, *args, **kwargs ):
        """
        A helper function that executes a job command.  If 'sh' is True,
        then the args are treated as a shell command.  If 'bg' is True, then
        the command is run in a separate thread.

        For non-background jobs, an uncaught exception from Job.execute() will
        be caught here, recorded and printed to stderr.  This function returns
        normally.

        For background jobs, the Job.execute() is run in a separate thread and
        this function immediately returns with the job id.  Uncaught exceptions
        will be written to stderr by the normal threading behavior, and the
        thread will finish.
        """
        tprint( 'RunJob:', jobname, args, kwargs )
        print3( ''.join( traceback.format_list(
                            traceback.extract_stack()[:-1] ) ).rstrip() )

        jb = Job()

        try:
            assert len(args) > 0, "empty or no command given"

            jb.set( 'name', jobname )

            if sh:
                # treat the arguments as a shell command
                if len(args) > 1:
                    # shell quote each argument (escape wildcards, for example)
                    cmd = ' '.join( [ pipes.quote(arg) for arg in args ] )
                    jb.set( 'command', cmd )
                else:
                    # send command through unmodified (no escaping is done)
                    jb.set( 'command', args[0] )
            else:
                # treat arguments as raw positional arguments to a subprocess
                jb.set( 'command', args )
            
            for n,v in kwargs.items():
                jb.set( n, v )

            jb.finalize()
            tprint( 'RunJob: jobid='+str(jb.jobid()) )

            if bg:
                # run in a thread and return without waiting
                self.start( jb )
            else:
                # run and wait on the job
                self.execute( jb )
        
        except:
            # catch all exceptions to avoid crashing the calling script;
            # instead, treat any issue as a job failure
            xs,tb = capture_traceback( sys.exc_info() )
            jb.set( 'exc', '[' + time.ctime() + '] ' + xs )
            sys.stderr.write( '['+time.ctime() +'] ' + \
                'Exception running jobid '+str( jb.jobid() )+'\n' + tb )
            sys.stderr.flush()
            self.insert( jb )  # make sure job is in the database

        # this just ensures that the next job will have a unique date stamp
        time.sleep(1)

        if bg:
            return jb.jobid()
        return jb

# construct the RunJobs singleton instance
RunJobs.inst = RunJobs()


def capture_traceback( excinfo ):
    """
    This should be called in an except block of a try/except, and the argument
    should be sys.exc_info().  It extracts and formats the traceback for the
    exception.  Returns a pair ( the exception string, the full traceback ).
    """
    xt,xv,xtb = excinfo
    xs = ''.join( traceback.format_exception_only( xt, xv ) )
    tb = 'Traceback (most recent call last):\n' + \
         ''.join( traceback.format_list(
                        traceback.extract_stack()[:-2] +
                        traceback.extract_tb( xtb ) ) ) + xs
    return xs,tb


def runcmd( cmd, outfd=None, timeout=None, poll_interval=15 ):
    """
    Run the given command in a subprocess then wait for it to finish.  An
    exception is raised if the command fails to launch.  Returns the command's
    exit status, or None if the command times out.
    """
    import signal

    argD = {}

    if type(cmd) == type(''):
        argD['shell'] = True

    if outfd != None:
        argD['stdout'] = outfd
        argD['stderr'] = subprocess.STDOUT

    if sys.platform.lower().startswith('win'):
        def kill_process( po ):
            po.terminate()

    else:
        # use preexec_fn to put the child into its own process group
        # (to more easily kill it and all its children)
        argD['preexec_fn'] = lambda: os.setpgid( os.getpid(), os.getpid() )

        def kill_process( po ):
            # send all processes in the process group a SIGTERM
            os.kill( -po.pid, signal.SIGTERM )
            # wait for child process to complete
            for i in range(10):
                x = po.poll()
                if x != None:
                      break
                time.sleep(1)
            if x == None:
                # child did not die - try to force it
                os.kill( po.pid, signal.SIGKILL )
                time.sleep(1)
                po.poll()

    t0 = time.time()

    p = subprocess.Popen( cmd, **argD )

    x = None
    try:
        if timeout != None:
            ipoll = min( poll_interval, int( 0.45*timeout ) )
            pause = 2
            while True:
                time.sleep( pause )
                pause = min( 2*pause, ipoll )
                x = p.poll()
                if x != None:
                    break
                if time.time() - t0 > timeout:
                    kill_process(p)
                    x = None  # mark as timed out
                    break
        else:
            x = p.wait()

    except:
        kill_process(p)
        raise

    return x


def print3( *args ):
    """
    Python 2 & 3 compatible print function.
    """
    s = ' '.join( [ str(x) for x in args ] )
    sys.stdout.write( s + '\n' )
    sys.stdout.flush()

def tprint( *args ):
    """
    Same as print3 but prefixes with the date.
    """
    s = ' '.join( [ str(x) for x in args ] )
    sys.stdout.write( '['+time.ctime()+'] ' + s + '\n' )
    sys.stdout.flush()
