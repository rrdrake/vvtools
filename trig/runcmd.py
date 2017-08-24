#!/usr/bin/env python

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import subprocess
import signal
import time
import shlex
import pipes

"""
Functions in this file are conveniences for running subprocesses:

    run_command : run a command with optional redirect
    run_output  : run a command and capture & return the output as a string
    run_timeout : run a command with a timeout

Helper functions for composing commands are:

    command : joins command arguments into a string
    escape  : joins arguments and escapes shell special characters

A command can be specified in a few ways - the main difference being whether
shell expansion is performed or not.

Shell expansion.  Each of these methods will apply shell expansion.

    1. A single string argument, such as

            run_command( 'ls -l *' )

    2. Use the command() function, such as

            cmd = command( 'ls', '-l', '*' )
            run_command( cmd )

No shell expansion.  None of these methods apply shell expansion.

    1. A single python list argument, such as

            run_command( ['ls', '-l', '*'] )

    2. More than one string argument, such as

            run_command( 'ls', '-l', '*' )

    3. Use the escape() function, such as

            cmd = escape( 'ls', '-l', '*' )
            run_command( cmd )

To compose a command in which some arguments are expanded but not others,
just use escape() on the arguments not to be expanded.  Such as

        cmd = command( 'ls', '-l' )
        cmd += ' ' + escape( '~' )  # do not apply home directory expansion
        cmd += ' ~/file'  # do apply home directory expansion
        run_command( cmd )

Note that if the first argument is a python list, then subsequent arguments
can be strings or lists.  The final command is treated as a list.  For example,

        cmd = ['ls','-l']
        fL = ['*','../subdir/file.txt']
        run_command( cmd, 'foo.log', fL )

The previous example would be the same as

        run_command( 'ls', '-l', 'foo.log', '*', '../subdir/file.txt' )

Note: Look at the documentation below in the function "def _is_dryrun" for use
of the environment variable COMMAND_DRYRUN for noop execution.
"""


class CommandException(Exception):
    """
    This exception is raised in the run_* functions when 'raise_on_failure'
    is True and the command returns with a non-zero exit status.
    """
    pass


def command( *args ):
    """
    Returns the command as a string joining the given arguments.  Arguments
    with embedded spaces are double quoted, as are empty arguments.
    """
    cmd = ''
    for s in args:
        if cmd: cmd += ' '
        if not s or ' ' in s:
            cmd += '"'+s+'"'
        else:
            cmd += s
    return cmd


def escape( *args ):
    """
    Returns the arguments joined as a string.  Each argument has any shell
    special characters escaped.
    """
    cmd = ''
    for s in args:
        if cmd: cmd += ' '
        if not s:
            cmd += '""'
        else:
            cmd += pipes.quote(s)
    return cmd


def run_command( *args, **kwargs ):
    """
    Executes the given command as a child process, waits for it, and returns
    the exit status.

    See documentation at the top of this file for explanation of the command
    arguments.

    Optional keyword arguments with default values are

        echo = True
        chdir = None
        raise_on_failure = True
        redirect = None
        append = False
        machine = None
        sshexe = None
    
    If 'echo' is True, the command to be executed is written to stdout.

    If 'chdir' is not None, it specifies a directory to change to before
    running the command.  When this function returns, the directory will
    be changed back.  Note that 'chdir' is applied *before* a 'redirect'
    file, so an absolute redirect file path name may be necesary.
    
    If 'redirect' is a string, it should be a file name which is opened and
    stdout and stderr is redirected to the file.  If 'append' is true, then
    the redirect file is appended.  The 'redirect' value can also be an
    integer file descriptor, which is then sent the command output.

    If 'raise_on_failure' is True and the command exit status is not zero,
    then a CommandException is raised.

    If 'machine' is not None, then the command is run on a remote machine
    using ssh.  In this case, the 'sshexe' keyword argument can be used to
    specify the ssh program to use.
    """
    echo = kwargs.get( 'echo', True )
    cd = kwargs.get( 'chdir', None )
    raise_on_failure = kwargs.get( 'raise_on_failure', True )
    redirect = kwargs.get( 'redirect', None )
    append = kwargs.get( 'append', False )
    mach = kwargs.get( 'machine', None )
    sshexe = kwargs.get( 'sshexe', None )

    cmd,scmd = _assemble_command( *args )
    if mach:
        ss = 'ssh'
        if sshexe:
            ss = sshexe
        cmd,scmd = _assemble_command( ss, mach, scmd )

    dryrun = _is_dryrun( cmd )

    outfp = None
    fdout = None
    if not dryrun and redirect != None:
        if type(redirect) == type(2):
            fdout = redirect
        elif type(redirect) == type(''):
            fn = redirect
            if cd and not os.path.isabs( redirect ):
                fn = os.path.join( cd, redirect )
            if append: outfp = open( fn, "a" )
            else:      outfp = open( fn, "w" )
            fdout = outfp.fileno()

    if echo:
        tm = time.time()
        L = []
        if cd: L.append( 'dir='+cd )
        else:  L.append( 'dir='+os.getcwd() )
        if outfp != None:
            L.append( 'logfile='+redirect )
        startid = 'start='+str(tm)
        L.append( startid )
        L.append( 'cmd='+scmd )
        sys.stdout.write( '['+time.ctime(tm)+'] runcmd: '+repr(L)+'\n' )
        sys.stdout.flush()

    # build the arguments for subprocess.Popen()
    argD = {}

    if type(cmd) == type(''):
        argD['shell'] = True

    argD['bufsize'] = -1  # use system buffer size (is this needed?)

    if fdout != None:
        argD['stdout'] = fdout
        argD['stderr'] = subprocess.STDOUT

    if cd:
        cwd = os.getcwd()
        os.chdir( cd )

    try:
        if dryrun:
            x = 0
        else:
            p = subprocess.Popen( cmd, **argD )
            x = p.wait()
    finally:
        if cd:
            os.chdir( cwd )

    if outfp != None:
      outfp.close()
    outfp = None
    fdout = None

    if echo:
        L = [ 'exit='+str(x), startid, 'cmd='+scmd ]
        sys.stdout.write( '['+time.ctime()+'] return: '+repr(L)+'\n' )
        sys.stdout.flush()

    if raise_on_failure and x != 0:
        raise CommandException( '\nCommand failed: '+scmd )

    return x


def run_output( *args, **kwargs ):
    """
    Executes the given command as a child process, captures its output, waits
    for it to finish, and returns the output as a string.

    See documentation at the top of this file for explanation of the command
    arguments.

    Optional keyword arguments are

        echo = True
        chdir = None
        include_stderr = True
        raise_on_failure = True
        machine = None
        sshexe = None

    If 'echo' is True, the command to be executed is written to stdout.

    If 'chdir' is not None, it specifies a directory to change to before
    running the command.  When this function returns, the directory will
    be changed back.
    
    If 'include_stderr' is True, then the captured output include the stderr
    stream from the command.

    If 'raise_on_failure' is True and the command exit status is not zero,
    then a CommandException is raised.

    If 'machine' is not None, then the command is run on a remote machine
    using ssh.  In this case, the 'sshexe' keyword argument can be used to
    specify the ssh program to use.
    """
    echo = kwargs.get( 'echo', True )
    cd = kwargs.get( 'chdir', None )
    raise_on_failure = kwargs.get( 'raise_on_failure', True )
    include_stderr = kwargs.get( 'include_stderr', True )
    mach = kwargs.get( 'machine', None )
    sshexe = kwargs.get( 'sshexe', None )

    cmd,scmd = _assemble_command( *args )
    if mach:
        ss = 'ssh'
        if sshexe:
            ss = sshexe
        cmd,scmd = _assemble_command( ss, mach, scmd )

    dryrun = _is_dryrun( cmd )

    if echo:
        tm = time.time()
        L = []
        if cd: L.append( 'dir='+cd )
        else:  L.append( 'dir='+os.getcwd() )
        startid = 'start='+str(tm)
        L.append( startid )
        L.append( 'cmd='+scmd )
        sys.stdout.write( '['+time.ctime(tm)+'] runcmd: '+repr(L)+'\n' )
        sys.stdout.flush()

    # build the arguments for subprocess.Popen()
    argD = {}

    if type(cmd) == type(''):
        argD['shell'] = True

    argD['bufsize'] = -1  # use system buffer size (is this needed?)

    argD['stdout'] = subprocess.PIPE
    if include_stderr:
        argD['stderr'] = subprocess.STDOUT

    if cd:
        cwd = os.getcwd()
        os.chdir( cd )

    try:
        if not dryrun:
            p = subprocess.Popen( cmd, **argD )
            sout,serr = p.communicate()
    finally:
        if cd:
            os.chdir( cwd )

    if dryrun:
        x = 0
        sout = ''
    else:
        x = p.returncode

    if type(sout) != type(''):
        # in python 3, the output is a bytes object .. convert to a string
        sout = sout.decode()

    if echo:
        L = [ 'exit='+str(x), startid, 'cmd='+scmd ]
        sys.stdout.write( '['+time.ctime()+'] return: '+repr(L)+'\n' )
        sys.stdout.flush()

    if raise_on_failure and x != 0:
        if len(sout) < 1024:
            raise CommandException( '\n'+sout+'\n' + \
                                    'Command failed: '+scmd )
        else:
            raise CommandException( '\n...\n'+sout[-1024:]+'\n' + \
                                    'Command failed: '+scmd )

    return sout


def run_timeout( *args, **kwargs ):
    """
    Executes the given command as a child process, waits for it or kills it
    after a timeout, and returns the exit status.

    See documentation at the top of this file for explanation of the command
    arguments.

    The keyword timeout=<num seconds> or timeout_date=<epoch seconds> is
    required.

    Optional keyword arguments are

        echo = True
        chdir = None
        redirect = None
        append = False
        raise_on_failure = True
        poll_interval = 15
        machine = None
        sshexe = None

    The 'timeout' is the number of seconds before the child process will be
    killed.  If the child times out, a None is returned for the exit status.
    If 'timeout_date' is given, it should be an epoch time in seconds (which
    time.time() returns, for example), and the timeout is computed as
    timeout = timeout_date - time.time().

    If 'echo' is True, the command to be executed is written to stdout.

    If 'chdir' is not None, it specifies a directory to change to before
    running the command.  When this function returns, the directory will
    be changed back.  Note that 'chdir' is applied *before* a 'redirect'
    file, so an absolute redirect file path name may be necesary.

    If 'redirect' is a string, it should be a file name which is opened and
    stdout and stderr is redirected to the file.  If 'append' is true, then
    the redirect file is appended.  The 'redirect' value can also be an
    integer file descriptor.

    If 'raise_on_failure' is True and the command exit status is not zero,
    then a CommandException is raised.

    The 'poll_interval' is the number of seconds between polling the subprocess
    to see if it has completed.

    If 'machine' is not None, then the command is run on a remote machine
    using ssh.  In this case, the 'sshexe' keyword argument can be used to
    specify the ssh program to use.

    TODO: - if this process receives a signal (like Control-C), then what
            happens to the child process ?  Need to understand that and add
            handling for receiving signals
    """
    echo = kwargs.get( 'echo', True )
    cd = kwargs.get( 'chdir', None )
    raise_on_failure = kwargs.get( 'raise_on_failure', True )
    redirect = kwargs.get( 'redirect', None )
    append = kwargs.get( 'append', False )
    poll_interval = kwargs.get( 'poll_interval', 15 )
    mach = kwargs.get( 'machine', None )
    sshexe = kwargs.get( 'sshexe', None )

    if 'timeout' in kwargs:
        timeout = float( kwargs['timeout'] )
    else:
        assert 'timeout_date' in kwargs, \
            'one of "timeout" or "timeout_date" must be given'
        timeout = float( kwargs['timeout_date'] ) - time.time()

    cmd,scmd = _assemble_command( *args )
    if mach:
        ss = 'ssh'
        if sshexe:
            ss = sshexe
        cmd,scmd = _assemble_command( ss, mach, scmd )

    dryrun = _is_dryrun( cmd )

    outfp = None
    fdout = None
    if not dryrun and redirect != None:
        if type(redirect) == type(2):
            fdout = redirect
        elif type(redirect) == type(''):
            fn = redirect
            if cd and not os.path.isabs( redirect ):
                fn = os.path.join( cd, redirect )
            if append: outfp = open( fn, "a" )
            else:      outfp = open( fn, "w" )
            fdout = outfp.fileno()

    if echo:
        tm = time.time()
        L = []
        if cd: L.append( 'dir='+cd )
        else:  L.append( 'dir='+os.getcwd() )
        if outfp != None:
            L.append( 'logfile='+redirect )
        L.append( 'timeout='+str(timeout) )
        startid = 'start='+str(tm)
        L.append( startid )
        L.append( 'cmd='+scmd )
        sys.stdout.write( '['+time.ctime(tm)+'] runcmd: '+repr(L)+'\n' )
        sys.stdout.flush()

    # build the arguments for subprocess.Popen()
    argD = {}

    if type(cmd) == type(''):
        argD['shell'] = True

    argD['bufsize'] = -1  # use system buffer size (is this needed?)

    if fdout != None:
        argD['stdout'] = fdout
        argD['stderr'] = subprocess.STDOUT

    if sys.platform.startswith('win'):
        # TODO: determine and test how to properly terminate a child process
        #       so that the child and all its children, etc, will terminate
        def kill_process( popen ):
            popen.terminate()

    else:
        # use preexec_fn to put the child into its own process group
        # (to more easily kill it and all its children)
        argD['preexec_fn'] = lambda:os.setpgid(os.getpid(),os.getpid())

        def kill_process( popen ):
            # send all processes in the process group a SIGTERM
            os.kill( -popen.pid, signal.SIGTERM )
            # wait for child process to complete
            i = 0
            while i < 10:
              x = popen.poll()
              if x != None:
                  break
              time.sleep(1)
              i += 1
            if x == None:
              # child did not die - try to force it
              os.kill( popen.pid, signal.SIGKILL )
              time.sleep(1)
              popen.poll()

    tstart = time.time()

    if cd:
        cwd = os.getcwd()
        os.chdir( cd )

    try:
        if dryrun:
            x = 0
        else:
            p = subprocess.Popen( cmd, **argD )

            x = None
            try:
                ipoll = min( poll_interval, int( 0.45*timeout ) )
                pause = 2
                while True:
                    time.sleep( pause )
                    pause = min( 2*pause, ipoll )
                    x = p.poll()
                    if x != None:
                        break
                    if time.time() - tstart > timeout:
                        kill_process(p)
                        x = None  # mark as timed out
                        break
            except:
                kill_process(p)
                raise  # should not happen
    finally:
        if cd:
            os.chdir( cwd )

    if outfp != None:
      outfp.close()
    outfp = None
    fdout = None

    if echo:
        L = [ 'exit='+str(x), startid, 'cmd='+scmd ]
        sys.stdout.write( '['+time.ctime()+'] return: '+repr(L)+'\n' )
        sys.stdout.flush()

    if raise_on_failure and x != 0:
        if x == None:
            raise CommandException( '\nCommand timed out (' + \
                                    str(timeout) + 's): '+scmd )
        else:
            raise CommandException( '\nCommand failed: '+scmd )

    return x


##################################################################

def _assemble_command( *args ):
    """
    Internal command that interprets the arguments as a python list or a
    string.  Returns the command (a string or a list) and a shell accurate
    string representation of the command.
    """
    if len(args) == 0:
        return '',''
    elif len(args) == 1:
        if type(args[0]) == type(''):
            # single command string
            return args[0],args[0]
        # assume a command list
        return args[0],' '.join( [ pipes.quote(s) for s in args[0] ] )
    elif type(args[0]) == type(''):
        # send arguments as a list into subprocess.Popen()
        return []+list(args),' '.join( [ pipes.quote(s) for s in args ] )
    else:
        # assume args start with a list or tuple
        L = list( args[0] )
        for arg in args[1:]:
            # strings are treated as another argument
            if type(arg) == type(''):
                L.append( arg )
            else:
                L += list( arg )
        return L,' '.join( [ pipes.quote(s) for s in L ] )


def _is_dryrun( cmd ):
    """
    If the environment defines COMMAND_DRYRUN to an empty string or to the
    value "1", then this function returns True, which means this is a dry
    run and the command should not be executed.

    If COMMAND_DRYRUN is set to a nonempty string, it should be a list of
    program basenames, where the list separator is a forward slash, "/".
    If the basename of the given command program is in the list, then it is
    allowed to run (False is returned).  Otherwise True is returned and the
    command is not run.  For example,

        COMMAND_DRYRUN="scriptname.py/runstuff"
    """
    v = os.environ.get( 'COMMAND_DRYRUN', None )
    if v != None:
        if v and v != "1":
            try:
                # extract the basename of the program being run
                if type(cmd) == type(''):
                    import shlex
                    n = os.path.basename( shlex.split( cmd )[0] )
                else:
                    n = os.path.basename( cmd[0] )
            except:
                return True  # a failure is treated as a dry run

            L = v.split('/')
            if n in L:
                return False
        return True

    return False
