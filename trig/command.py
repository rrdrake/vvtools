#/usr/bin/env python

'''
INTRODUCTION

This module is a convenience wrapper around subprocess.  It provides easy
ways to construct commands and execute them.  The interface is the Command
class.

Examples:

    1. exit_status = Command( 'ls -l */*.txt > files' ).run()

    2. files = Command( 'ls -l */*.txt' ).run_output()

    3. cmd = Command( 'myscript', '--prefix', todir )
       if bindir:
           cmd.add( '--bin-dir', bindir )
       x = cmd.run()

Commands can be built up by accumulating arguments with these functions:

    add()    : uses shell-like handling and variable substitution
    arg()    : performs variable substitution
    raw()    : add arguments without shell handling or variable substitution
    escape() : escapes shell special characters


VARIABLE SUBSTITUTION

Python variables are substituted in command arguments the same way a shell
would.  For example,

    loc = '/install/directory'
    ident = 42
    Command( 'buildscript --id $ident --prefix=$loc target' ).run()

In this example, the actual command would be

    buildscript --id 42 --prefix=/install/directory target

Locally scoped python variables take precedence, followed by global python
variables, followed by environment variables.  Two forms are allowed: $NAME
and ${NAME}.  If the NAME is not in scope, no replacement is performed.


RUN METHODS

There are three run methods:

    run()           : runs command and returns the exit status
    run_output()    : runs the command and returns the command output
    run_timeout()   : runs the command and waits for completion with a time
                      limit; returns the exit status or the value None if the
                      command timed out


RUN METHOD ARGUMENTS

The following arguments are allowed in each of the run methods:

    shell : defaults to True; if True, the shell will be used to interpret the
            command before execution

    chdir : change to this directory before running the command; this occurs
            before output redirection

    echo : defaults to "echo"; a shell equivalent command is echoed to stdout
           by default, but a value of "none" will suppress output, and the
           value "log" will write date stamps and verbose information before
           the command is executed and the final result when the command
           returns

    raise_on_error : defaults to False; if True and the command returns a
                     non-zero exit status, then a CommandException is raised

    stdout : redirects stdout to a file name, or to an integer file descriptor
    stderr : redirects stderr to a file name, or to an integer file descriptor

    machine : executes the command on another machine using ssh; the value is
              the network name or IP address

    sshexe : defaults to "ssh"; this is the ssh program used when the 'machine'
             option is given

This argument is allowed with the run() and run_timeout() methods:

    redirect : redirects both stdout and stderr to a file name or an integer
               file descriptor


NOTES

Commands can be combined by including a Command instance as an argument to
another Command instance.  For example,

    base_cmd = Command( 'gmake -k' )
    Command( base_cmd, 'target1' ).run()
    Command( base_cmd, 'target2' ).run()


The 'redirect', 'stdout', and 'stderr' arguments can be given a (string) file
name.  Doing so will cause a file to be opened for write and the command output
will be redirected to the file.  If the file already exists, it will be
overwritten.

To redirect to a file and have it appended instead, prefix the file name with
">>".  For example,

    1. redirect=">>/my/directory/log.txt"
    2. redirect=">>log.txt"
    3. redirect="./>>>>>"

Example 3 shows how to handle the unlikely case where the actual file name
starts with ">>" and you do NOT want to append.


A "dry run" or "no-op" mode can be invoked by defining COMMAND_DRYRUN in the
environment.  See the CommandDryRun class at the bottom of this file for more
information.
'''


import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import inspect
import re
import shlex
import pipes
import subprocess
import time
import traceback
import signal


class CommandException(Exception):
    pass


class Command:

    def __init__(self, *arglist):
        """
        Same as
            cmd = Command()
            cmd.add( arg1, arg2, ... )
        """
        self.expander = VariableExpander()
        self.argL = []
        self._appendExpandAndReplace( *arglist )

    def add(self, *arglist):
        """
        Each argument has this done to it:
            - shell quote and whitespace handling (can become multiple args)
            - local variable replacement
        """
        self._appendExpandAndReplace( *arglist )
        return self

    def arg(self, *arglist):
        """
        Each argument has this done to it:
            - local variable replacement
        """
        self._appendReplace( *arglist )
        return self

    def raw(self, *arglist):
        """
        Each argument is a single argument without variable replacement.
        """
        for arg in arglist:
            if isinstance( arg, Command ):
                self.argL.extend( arg.argL )
            else:
                self.argL.append( SingleArgument( str(arg) ) )
        return self

    def escape(self, *arglist):
        """
        Each argument has this done to it:
            - all shell special characters are escaped or quoted

        Note that if running the final command with shell=False, then escaping
        arguments is not necessary.  Escaping can add quote characters and
        backslashes, which will then be passed in as part of the argument to
        the program being executed.
        """
        for arg in arglist:
            if isinstance( arg, Command ):
                self.argL.extend( arg.argL )
            else:
                self.argL.append( EscapedArgument( str(arg) ) )
        return self

    def asShellString(self, shell=True):
        """
        Returns the command as a string in a form that could be given to a
        shell command prompt.  The 'shell' variable is the same as it is for
        the subprocess module, which if False means the shell does not
        interpret the arguments (and therefore does not expand variables and
        perform file glob-ing).
        """
        if shell:
            argL = [ arg.shellStringForExpansion() for arg in self.argL ]
        else:
            argL = [ arg.shellStringWithoutExpansion() for arg in self.argL ]
        return ' '.join( argL )

    def run(self, shell=True,
                  chdir=None,
                  echo="echo",
                  raise_on_error=False,
                  redirect=None, stdout=None, stderr=None,
                  machine=None, sshexe='ssh' ):
        """
        Returns the subprocess exit status.
        """
        pycmd,shcmd = self._makeFinalCommands( shell, machine, sshexe )
        streams = SubprocessStreams( redirect, stdout, stderr )
        echobj = construct_echo_object( echo, shcmd, streams.getFilename() )
        runit = CommandDryRun().runIt( pycmd )

        runner = SubprocessRunner( pycmd, chdir, streams, echobj )
        return runner.runCommand( raise_on_error, runit )

    def run_output(self, capture='stdout',
                         shell=True,
                         chdir=None,
                         echo="echo",
                         raise_on_error=False,
                         stdout=None, stderr=None,
                         machine=None, sshexe='ssh' ):
        """
        The 'capture' argument can be one of the values: "stdout", "stderr",
        or "stdouterr".  The captured output is returned as a string.
        """
        pycmd,shcmd = self._makeFinalCommands( shell, machine, sshexe )
        streams = SubprocessStreams( None, stdout, stderr, capture )
        echobj = construct_echo_object( echo, shcmd, streams.getFilename() )
        runit = CommandDryRun().runIt( pycmd )

        runner = OutputSubprocessRunner( pycmd, chdir, streams, echobj )
        return runner.runCommand( raise_on_error, runit )

    def run_timeout(self, timeout=None, timeout_date=None, poll_interval=15,
                          shell=True,
                          chdir=None,
                          echo="echo",
                          raise_on_error=False,
                          redirect=None, stdout=None, stderr=None,
                          machine=None, sshexe='ssh' ):
        """
        One of 'timeout' or 'timeout_date' must be non-None.  A 'timeout' is
        the maximum time allowed for the command in seconds.  A 'timeout_date'
        is an epoch date in seconds, such as that returned from time.time().

        The 'poll_interval' is the number of seconds between checks for the
        subprocess completion.

        The exit status is returned, or None if the command times out.
        """
        tm = compute_timeout_value( timeout, timeout_date )

        pycmd,shcmd = self._makeFinalCommands( shell, machine, sshexe )
        streams = SubprocessStreams( redirect, stdout, stderr )
        echobj = construct_echo_object( echo, shcmd, streams.getFilename(), tm )
        runit = CommandDryRun().runIt( pycmd )

        runner = TimeoutSubprocessRunner( tm, poll_interval,
                                          pycmd, chdir, streams, echobj )
        return runner.runCommand( raise_on_error, runit )

    #######################################################################

    def _appendExpandAndReplace(self, *arglist):
        for arg1 in arglist:
            if isinstance( arg1, Command ):
                self.argL.extend( arg1.argL )
            else:
                s = self._expandVars( str(arg1) )
                for arg2 in shlex.split(s):
                    self.argL.append( SingleArgument(arg2) )

    def _appendReplace(self, *arglist):
        for arg in arglist:
            if isinstance( arg, Command ):
                self.argL.extend( arg.argL )
            else:
                s = self._expandVars( str(arg) )
                self.argL.append( SingleArgument(s) )

    def _expandVars(self, astring):
        """
        """
        # retrieve the variables defined in the calling function
        lclD,gblD = get_calling_frame_variables( 4 )

        # build dict with environment and calling function variables
        D = {}
        D.update( os.environ )
        D.update( gblD )
        D.update( lclD )

        return self.expander.expand( astring, D )

    def _makeFinalCommands(self, shell, machine, sshexe):
        """
        Composes and returns the command to send to subprocess and an
        equivalent command as it would be executed on a shell command line.

        A note on using ssh to execute a command on a remote machine.  The
        command is a list of arguments given to ssh:

          ssh <machine> <arg0> <arg1> ...

        Equally valid, the arguments can be given as a single string:

          ssh <machine> "arg0 arg1 ..."

        When given on the shell command line, the shell processes the command
        before sending it to the remote machine.  Then the shell on the remote
        machine is used to execute the command.  When executed in Python, the
        shell processing on the local machine can be avoided just by giving
        subprocess a list and shell=False.
        """
        if shell:
            shelltrue = self.asShellString( shell=True )
            if machine:
                # send remote shell an un-escaped command string
                subproc_cmd = [ sshexe, machine, shelltrue ]
                # the shell command must have escaped special characters;
                # these are removed by the local shell before sending and
                # executing on the remote machine (using remote shell)
                shell_cmd = sshexe+' '+machine+' '+pipes.quote( shelltrue )
            else:
                subproc_cmd = shelltrue
                shell_cmd = shelltrue

        else:
            shellfalse = self.asShellString( shell=False )
            if machine:
                # send remote shell a command string with escaped characters
                subproc_cmd = [ sshexe, machine, shellfalse ]
                # the shell command has to be doubly escaped;  the first set
                # is removed by the local shell, and the second set by the
                # shell on the remote machine
                shell_cmd = sshexe+' '+machine+' '+pipes.quote( shellfalse )
            else:
                # send subprocess a python list (shell=False should get set)
                subproc_cmd = [ arg.getArgument() for arg in self.argL ]
                # shell command has special characters escaped
                shell_cmd = shellfalse

        return subproc_cmd, shell_cmd


###########################################################################

class SingleArgument:

    def __init__(self, arg):
        self.arg = arg

    def getArgument(self):
        """
        The argument for passing to subprocess as a command list item.
        """
        return self.arg

    def shellStringForExpansion(self):
        """
        The argument as if given on a shell command line where shell expansion
        would be allowed/applied.

        The challenge here is that the argument must be interpreted by the
        shell as a single argument.  E.g, white space is treated as multiple
        arguments by default, so it must be escaped in some way.  But just
        quoting the whole argument will surpress tilde home directory
        expansion.
        """
        s = ''
        c1 = None
        for c2 in self.arg:
            if c2 in [' ','"',"'"] and c1 != '\\':
                s += '\\'+c2
            elif c2 == '\t':
                s += '\\t'
            else:
                s += c2
            c1 = c2
        return s

    def shellStringWithoutExpansion(self):
        """
        The argument as if given on a shell command line where shell expansion
        is not allowed/applied.
        """
        return pipes.quote( self.arg )


class EscapedArgument:

    def __init__(self, arg):
        self.arg = arg

    def getArgument(self):
        return pipes.quote( self.arg )

    def shellStringForExpansion(self):
        return pipes.quote( self.arg )

    def shellStringWithoutExpansion(self):
        return pipes.quote( self.arg )


###########################################################################

class VariableExpander:
    """
    Utility to take a string, find all shell-like variable syntax
    specifications, and replace them with corresponding values.
    This class looks for variables specified with $VARNAME and ${VARNAME}
    and replaced with values from a dictionary.  If a variable is not
    defined in a dictionary, then the string is not modified (as opposed
    to replacing with an empty string, for example).

    Dollar signs that are escaped with a backslash are not replaced and the
    backslash is removed.

    For example,

        vx = VariableExpander()
        valueD = { 'VARNAME':'value' }
        repl = vx.expand( "VARNAME=$VARNAME", valueD )

    In this example, the string 'repl' will be "VARNAME=value".
    """

    def __init__(self):
        self.varpat = re.compile(
            '(?<![\\\\])[$][a-zA-Z_]+[a-zA-Z0-9_]*' + \
            '|(?<![\\\\])[$][{][a-zA-Z_]+[a-zA-Z0-9_]*[}]' )
        self.escpat = re.compile( '[\\\\][$]' )

    def expand(self, astring, variable_dict):
        """
        Return a string with variable replacements performed on 'astring'
        using the values in 'variable_dict'.
        """
        s = ''
        pos = 0
        for m in self.varpat.finditer( astring ):

            i,j = m.start(), m.end()

            if astring[i+1] == '{':
                varname = astring[i+2:j-1]
            else:
                varname = astring[i+1:j]

            value = variable_dict.get( varname, None )

            if value != None:
                s += astring[pos:i] + value
                pos = j

        if pos < len(astring):
            s += astring[pos:]

        return self.escpat.sub( '$', s )


###########################################################################

def get_calling_frame_variables( call_depth ):
    """
    Uses the inspect module to get hold of the calling frames leading to this
    function, picks the frame 'call_depth' back (up the call stack), then
    gets the local and global variables as they exist in the scope of that
    caller function.  Two dictionaries are returned, the locals and globals.

    The 'call_depth' must be an integer greater than zero.  A value of one
    is the direct caller of this function.
    """
    assert call_depth > 0

    lclD = {}
    gblD = {}
    try:
        caller = inspect.getouterframes( inspect.currentframe() )[call_depth]
        L = inspect.getmembers( caller[0] )
        for n,obj in L:
            if n == 'f_locals':
                lclD.update( obj )
            elif n == 'f_globals':
                gblD.update( obj )
    except:
        pass

    return lclD, gblD


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


###########################################################################

class SubprocessRunner:

    def __init__(self, cmd, chdir, streams, echobj):
        self.cmd = cmd
        self.chdir = chdir
        self.streams = streams
        self.echobj = echobj

    def runCommand(self, raise_on_error=False, runit=True):
        """
        Changes directory in a try/catch then dispatches to subprocessWrapper().
        """
        rtn = self.errorReturnValue()

        try:
            dirswap = ChangeDirectory( self.chdir )

        except:
            if raise_on_error:
                raise CommandException( 'Could not change to directory "' + \
                    str(self.chdir) + '": ' + str( sys.exc_info()[1] ) )
            else:
                xs,tb = capture_traceback( sys.exc_info() )
                sys.stderr.write( tb )

        else:
            try:
                rtn = self.subprocessWrapper( raise_on_error, runit )
            finally:
                dirswap.changeToOriginal()

        return rtn

    def subprocessWrapper(self, raise_on_error, runit):
        """
        Forms the arguments to subprocess.Popen() then dispatches to
        runSubprocess().
        """
        x = 0
        rtn = self.errorReturnValue()

        self.echobj.preExecute()

        # build the arguments
        argD = {}

        if type(self.cmd) == type(''):
            argD['shell'] = True

        argD['bufsize'] = -1  # use system buffer size (is this needed?)

        try:
            argD['stdout'] = self.streams.openStdout()
            argD['stderr'] = self.streams.openStderr()
        except:
            xs,tb = capture_traceback( sys.exc_info() )
            sys.stderr.write( tb )
            x = 1

        if x == 0:
            try:
                x,rtn = self.runSubprocess( self.cmd, runit, argD )
            except:
                xs,tb = capture_traceback( sys.exc_info() )
                sys.stderr.write( tb )
                self.streams.close()
                x = 1
            else:
                self.streams.close()

        self.echobj.postExecute(x)

        if raise_on_error and x != 0:
            raise CommandException( '\nCommand failed: '+str(self.cmd) )

        return rtn

    def errorReturnValue(self):
        """
        Error return value is a non-zero exit status.
        """
        return 1

    def runSubprocess(self, cmd, runit, argD):
        """
        The return value and the exit status are the same thing.
        """
        x = 0
        if runit:
            p = subprocess.Popen( cmd, **argD )
            x = p.wait()
        return x,x


class OutputSubprocessRunner(SubprocessRunner):

    def errorReturnValue(self):
        """
        Error return value is an empty string.
        """
        return ''

    def runSubprocess(self, cmd, runit, argD):
        """
        Returns the exit status and the command output as a string.
        """
        x = 0
        out = ''
        if runit:
            p = subprocess.Popen( cmd, **argD )
            sout,serr = p.communicate()

            x = p.returncode
            if sout:
                out += _STRING_(sout)
            if serr:
                out += _STRING_(serr)

        return x,out


if sys.version_info[0] < 3:
    # with python 2.x, files, pipes, and sockets work naturally
    def _BYTES_(s): return s
    def _STRING_(b): return b

else:
    # with python 3.x, read/write to files, pipes, and sockets is tricky
    bytes_type = type( ''.encode() )

    def _BYTES_(s):
        if type(s) == bytes_type:
            return s
        return s.encode( 'ascii' )

    def _STRING_(b):
        if type(b) == bytes_type:
            return b.decode()
        return b


class TimeoutSubprocessRunner(SubprocessRunner):

    def __init__(self, timeout, poll_interval,
                       cmd, chdir, streams, echobj):

        SubprocessRunner.__init__( self, cmd, chdir, streams, echobj )

        self.timeout = timeout
        self.poll_interval = max( 1, int( poll_interval ) )

    def runSubprocess(self, cmd, runit, argD):
        """
        The return value and the exit status are the same thing.  The exit
        status is None if the command times out.
        """
        x = 0
        if runit:
            ksp = KillableSubprocess( cmd, **argD )
            tstart = time.time()

            try:
                # use a poll interval that considers a small timeout value
                ipoll = min( self.poll_interval, int( 0.45*self.timeout ) )

                # pause between polls starting at 2 seconds, then double
                # each time to a maximum of the ipoll value
                pause = 2
                while True:
                    time.sleep( pause )
                    pause = min( 2*pause, ipoll )

                    x = ksp.getSubproc().poll()
                    if x != None:
                        break

                    if time.time() - tstart > self.timeout:
                        ksp.kill( signal.SIGTERM, signal.SIGKILL )
                        x = None  # mark as timed out
                        break

            except:
                # should never get here, but just in case
                ksp.kill( signal.SIGTERM, signal.SIGKILL )
                raise

        return x,x


class KillableSubprocess:
    """
    Launches a subprocess in its own process group.  The process and its
    children processes can be killed using kill().
    """

    def __init__(self, cmd, **argD):

        if sys.platform.startswith('win'):
            pass
        else:
            # use preexec_fn to put the child into its own process group
            # (to more easily kill it and all its children)
            argD['preexec_fn'] = lambda: os.setpgid( os.getpid(), os.getpid() )

        self.subproc = subprocess.Popen( cmd, **argD )

    def getSubproc(self):
        return self.subproc

    def kill(self, *signals):
        """
        Sends the process a set of signals one at a time, pausing in between
        for the process to complete.  Returns when the process completes or
        all signals have been sent.

        Signals are signal.SIGINT, signal.SIGTERM, signal.SIGKILL, etc.
        """
        if sys.platform.startswith('win'):
            # not sure how to properly terminate a child process on Windows
            # so that the child and all its children, etc, will terminate
            # NOTE: try "taskkill /t <pid>"
            #       there is also "tasklist" and "tasklist /v"
            subproc.terminate()

        else:
            for sig in signals:
                os.kill( -self.subproc.pid, sig )
                if self.checkIfDone(10):
                    break

    def checkIfDone(self, check_count):
        """
        Poll the subprocess a max of 'check_count' times, sleeping one second
        in between.  Returns True if the subprocess has completed.
        """
        for i in range(check_count):
            x = self.subproc.poll()
            if x != None:
                return True
            time.sleep(1)

        return False


def compute_timeout_value( timeout, timeout_date ):
    """
    Computes and returns a timeout in seconds.  The timeout is adjusted to be
    a minimum of 0.01 seconds.
    """
    assert timeout != None or timeout_date != None

    if timeout != None:
        rtn = float(timeout)
        if timeout_date != None:
            t2 = float( timeout_date ) - time.time()
            rtn = min( rtn, t2 )

    else:
        rtn = float( timeout_date ) - time.time()

    return max( 0.01, rtn )


##########################################################################

class RedirectToFilename:

    def __init__(self, filename):
        """
        If 'filename' starts with ">>", then the file is appended.  Otherwise
        overwritten.
        """
        self.fp = None
        self.append = False

        if filename.startswith( '>>' ):
            if filename == '>>':
                raise CommandException('invalid filename specification: ">>"')
            self.fname = filename[2:]
            self.append = True
        else:
            self.fname = filename

    def getFilename(self):
        return self.fname

    def open(self):
        """
        Returns a file descriptor.
        """
        if self.append:
            self.fp = open( self.fname, "a" )
        else:
            self.fp = open( self.fname, "w" )

        return self.fp.fileno()

    def close(self):
        self.fp.close()
        self.fp = None


class RedirectToFileDescriptor:
    def __init__(self, filedes): self.fd = filedes
    def getFilename(self): return None
    def open(self): return self.fd
    def close(self): pass


class RedirectNone:
    def getFilename(self): return None
    def open(self): return None
    def close(self): pass


class SubprocessStreams:

    def __init__(self, redirect, stdout, stderr, capture=None):
        self.out = RedirectNone()
        self.err = RedirectNone()

        if redirect != None:
            self.out = self.constructRedirectionObject( redirect )
            self.err = RedirectToFileDescriptor( subprocess.STDOUT )

        if stdout != None:
            self.out = self.constructRedirectionObject( stdout )

        if stderr != None:
            self.err = self.constructRedirectionObject( stderr )

        if capture != None:
            # treat subprocess.PIPE as a file descriptor
            if capture == "stdout":
                self.out = RedirectToFileDescriptor( subprocess.PIPE )
            elif capture == "stderr":
                self.err = RedirectToFileDescriptor( subprocess.PIPE )
            elif capture == "stdouterr":
                self.out = RedirectToFileDescriptor( subprocess.PIPE )
                self.err = RedirectToFileDescriptor( subprocess.STDOUT )

    def constructRedirectionObject(self, spec):
        if type(spec) == type(''):
            return RedirectToFilename( spec )
        return RedirectToFileDescriptor( spec )

    def getFilename(self):
        """
        Returns filename used to redirect stdout.  If stdout is not being
        redirected to a filename, then the filename used to redirect stderr.
        If neither, then None is returned.
        """
        fn = self.out.getFilename()
        if fn == None:
            fn = self.err.getFilename()
        return fn

    def openStdout(self):
        """
        Returns a file descriptor, or None.
        """
        return self.out.open()

    def openStderr(self):
        """
        Returns a file descriptor, or None.
        """
        return self.err.open()

    def close(self):
        self.out.close()
        self.err.close()


##########################################################################

class CommandNoEcho:
    def preExecute(self): pass
    def postExecute(self, exit_status): pass


class CommandEcho:
    def __init__(self, cmdstr):
        assert type(cmdstr) == type('')
        self.cmd = cmdstr
    def preExecute(self):
        sys.stdout.write( self.cmd + '\n' )
        sys.stdout.flush()
    def postExecute(self, exit_status):
        pass


class CommandLogging:

    def __init__(self, cmdstr, logfile, timeout):
        assert type(cmdstr) == type('')
        self.cmd = cmdstr
        self.logfile = logfile
        self.timeout = timeout

    def preExecute(self):
        """
        """
        self.tstart = time.time()
        self.startid = 'start='+str(self.tstart)

        L = [ 'dir='+os.getcwd() ]

        if self.logfile:
            L.append( 'logfile='+self.logfile )

        if self.timeout != None:
            L.append( 'timeout='+str(self.timeout) )

        L.append( self.startid )

        L.append( 'cmd='+self.cmd )

        s = '['+time.ctime(self.tstart)+'] runcmd: '+repr(L)
        sys.stdout.write( s+'\n' )
        sys.stdout.flush()

    def postExecute(self, exit_status):
        """
        """
        L = [ 'exit='+str(exit_status), self.startid, 'cmd='+self.cmd ]
        sys.stdout.write( '['+time.ctime()+'] return: '+repr(L)+'\n' )
        sys.stdout.flush()


def construct_echo_object( echo, shell_cmd, logfile, timeout=None ):
    """
    Returns a class instance depending the value of the 'echo' string.
    """
    if echo == "echo":
        return CommandEcho( shell_cmd )

    if echo == "log":
        return CommandLogging( shell_cmd, logfile, timeout )

    return CommandNoEcho()


###########################################################################

class ChangeDirectory:

    def __init__(self, chdir):
        """
        Changes to directory 'chdir' if that is a non-empty string.
        """
        self.savedir = os.getcwd()
        if chdir:
            os.chdir( chdir )

    def changeToOriginal(self):
        os.chdir( self.savedir )


class CommandDryRun:
    """
    Class for helping with "dry run" or "no-op" mode for executing commands.

    If the environment defines COMMAND_DRYRUN to an empty string or to the
    value "1", then the runIt() function returns False, which means this is a
    dry run and the command should not be executed.

    If COMMAND_DRYRUN is set to a nonempty string, it should be a list of
    program basenames, where the list separator is a forward slash, "/".
    If the basename of the command program given to runIt() is in the list,
    then it is allowed to run (True is returned).  Otherwise False is returned.
    For example, if

        COMMAND_DRYRUN="scriptname.py/runstuff"

    then runIt( '/some/full/path/scriptname.py -l foo' ) would return True
    but runIt( '/some/path/other.sh -t bar' ) would return False.
    """

    def __init__(self):

        self.is_dry_run = False
        self.allowed_programs = {}

        v = os.environ.get( 'COMMAND_DRYRUN', None )

        if v != None:
            self.is_dry_run = True
            if v and v.strip() != "1":
                for p in v.split('/'):
                    self.allowed_programs[p] = None

    def runIt(self, command=None):
        """
        The 'command' can be a string shell command or a python list command.
        """
        if self.is_dry_run:
            if command:
                try:
                    # extract the basename of the program being run
                    if type(command) == type(''):
                        n = os.path.basename( shlex.split( command )[0] )
                    else:
                        n = os.path.basename( command[0] )

                    if n in self.allowed_programs:
                        return True

                except:
                    pass  # a failure is treated as a dry run

            return False

        return True

