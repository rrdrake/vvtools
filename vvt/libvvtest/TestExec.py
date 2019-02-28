#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import signal
import time
import shutil
import glob
import traceback

from . import cshScriptWriter
from . import ScriptWriter
from . import pgexec


# if a test times out, it receives a SIGINT.  if it doesn't finish up
# after that in this number of seconds, it gets sent a SIGKILL
interrupt_to_kill_timeout = 30


class TestExec:
    """
    Runs a test in the background and provides methods to poll and kill it.
    The status and test results are saved in the TestSpec object.
    """
    
    def __init__(self, statushandler, atest, perms):
        """
        Constructs a test execution object which references a TestSpec obj.
        The 'perms' argument is a PermissionsSetter object.
        """
        self.statushandler = statushandler
        self.atest = atest
        self.perms = perms
        self.has_dependent = False
        
        self.platform = None
        self.timeout = 0
        self.pid = 0
        self.xdir = None

        # magic: make a class to hold dependencies
        # a list of runtime dependencies; items are tuples
        #    (TestExec or TestSpec, match pattern, word expr)
        self.deps = []

    def init(self, test_dir, platform, commondb, config ):
        """
        The platform is a Platform object.  The test_dir is the top level
        testing directory, which is either an absolute path or relative to
        the current working directory.
        """
        self.platform = platform
        self.config = config
        self.timeout = self.atest.getAttr( 'timeout', 0 )

        self.statushandler.resetResults( self.atest )

        self.xdir = os.path.join( test_dir, self.atest.getExecuteDirectory() )

        if not os.path.exists( self.xdir ):
            os.makedirs( self.xdir )

        self.perms.set( self.atest.getExecuteDirectory() )

        if self.atest.getSpecificationForm() == 'xml':
            self._write_xml_run_script( commondb )
        else:
            self._write_script_utils( test_dir )

    def start(self, baseline=0):
        """
        Launches the child process.
        """
        assert self.pid == 0

        np = int( self.atest.getParameters().get('np', 0) )

        self.plugin_obj = self.platform.obtainProcs( np )

        self.timedout = 0  # holds time.time() if the test times out

        self.statushandler.startRunning( self.atest )

        sys.stdout.flush() ; sys.stderr.flush()

        self.pid = os.fork()
        if self.pid == 0:
            # child process is the test itself
            self._prepare_and_execute_test( baseline )

    def poll(self):
        """
        """
        if self.isNotrun():
            return False

        if self.isDone():
            return True

        assert self.pid > 0

        cpid,code = os.waitpid(self.pid, os.WNOHANG)

        if cpid > 0:

            # test finished

            self.platform.giveProcs( self.plugin_obj )

            if self.timedout > 0:
                self.statushandler.markTimedOut( self.atest )
            else:
                exit_status = decode_subprocess_exit_code( code )
                self.statushandler.markDone( self.atest, exit_status )

            self.perms.recurse( self.xdir )

            if self.config.get('postclean') and \
               self.statushandler.passed( self.atest ) and \
               not self.has_dependent:
                self.postclean()

        # not done .. check for timeout
        elif self.timeout > 0:
            tm = time.time()
            tzero = self.statushandler.getStartDate( self.atest )
            if tm-tzero > self.timeout:
                if self.timedout == 0:
                    # interrupt all processes in the process group
                    self.signalJob( signal.SIGINT )
                    self.timedout = tm
                elif (tm - self.timedout) > interrupt_to_kill_timeout:
                    # SIGINT isn't killing fast enough, use stronger method
                    self.signalJob( signal.SIGTERM )

        return self.isDone()

    def isNotrun(self):
        return self.statushandler.isNotrun( self.atest )

    def isDone(self):
        return self.statushandler.isDone( self.atest )
    
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

    def setHasDependent(self):
        ""
        self.has_dependent = True

    def hasDependent(self):
        ""
        return self.has_dependent

    def addDependency(self, testexec, match_pattern=None, expr=None):
        """
        A dependency can be either a TestExec object or a TestSpec object.
        A TestExec object will replace a TestSpec object with the same
        execute directory.
        """
        append = True
        for i,tup in enumerate( self.deps ):
            if same_execute_directory( testexec, tup[0] ):
                if isinstance( testexec, TestExec ):
                    self.deps[i] = ( testexec, match_pattern, expr )
                append = False
                break

        if append:
            self.deps.append( (testexec,match_pattern,expr) )

    def hasDependency(self):
        """
        """
        return len(self.deps) > 0

    def getDependencies(self):
        """
        """
        return self.deps

    def getBlockingDependency(self):
        """
        If one or more dependencies did not run, did not finish, or failed,
        then that offending TestExec is returned.  Otherwise, None is returned.
        """
        for tx,pat,expr in self.deps:

            if isinstance( tx, TestExec ):
                ref = tx.atest
            else:
                ref = tx

            if not self.statushandler.isDone( ref ):
                return tx

            result = self.statushandler.getResultStatus( ref )

            if expr == None:
                if result not in ['pass','diff']:
                    return tx

            elif not expr.evaluate( lambda word: word == result ):
                return tx

        return None

    def getDependencyDirectories(self):
        ""
        L = []

        for tx,pat,expr in self.deps:

            if isinstance( tx, TestExec ):
                L.append( (pat,tx.atest.getExecuteDirectory()) )
            else:
                L.append( (pat,tx.getExecuteDirectory()) )

        return L

    def _prepare_and_execute_test(self, baseline):
        ""
        try:
            os.chdir(self.xdir)

            self._check_redirect_output_to_log_file( baseline )

            set_timeout_environ_variable( self.timeout )

            cmd_list = self._make_execute_command( baseline )

            echo_test_execution_info( self.atest.getName(),
                                      cmd_list, self.timeout )

            self._check_run_preclean( baseline )
            self._check_write_mpi_machine_file()
            self._check_set_working_files( baseline )

            self._set_environ_for_python_execution( baseline )

            sys.stdout.write( '\n' )
            sys.stdout.flush()

            if baseline:
                self.copyBaselineFiles()

            sys.stdout.flush() ; sys.stderr.flush()

            if cmd_list == None:
                # this can only happen in baseline mode
                os._exit(0)
            else:
                x = pgexec.group_exec_subprocess( cmd_list )
                os._exit(x)

        except:
            sys.stdout.flush() ; sys.stderr.flush()
            traceback.print_exc()
            sys.stdout.flush() ; sys.stderr.flush()
            os._exit(1)

    def _make_execute_command(self, baseline):
        ""
        cmdL = make_core_execute_command( self.atest, baseline )

        if cmdL != None:
            if hasattr(self.plugin_obj, "mpi_opts") and self.plugin_obj.mpi_opts:
                cmdL.extend(['--mpirun_opts', self.plugin_obj.mpi_opts])

            if self.config.get('analyze'):
                cmdL.append('--execute_analysis_sections')

            cmdL.extend( self.config.get( 'testargs' ) )

        return cmdL

    def _check_redirect_output_to_log_file(self, baseline):
        ""
        if baseline:
            logfname = 'baseline.log'
        elif not self.config.get('logfile'):
            logfname = None
        else:
            logfname = 'execute.log'

        if logfname != None:
            redirect_stdout_stderr_to_filename( logfname )
            self.perms.set( os.path.abspath( logfname ) )

    def _check_run_preclean(self, baseline):
        ""
        if self.config.get('preclean') and \
           not self.config.get('analyze') and \
           not baseline:
            self.preclean()

    def preclean(self):
        """
        Should only be run just prior to launching the test script.  It
        removes all files in the execute directory except for a few vvtest
        files.
        """
        sys.stdout.write( "Cleaning execute directory...\n" )
        sys.stdout.flush()

        xL = [ 'execute.log', 'baseline.log' ]

        if self.atest.getSpecificationForm() == 'xml':
            xL.append( 'runscript' )

        for f in os.listdir('.'):
          if f not in xL and not f.startswith( 'vvtest_util' ):
            if os.path.islink( f ):
              os.remove( f )
            elif os.path.isdir(f):
              sys.stdout.write( "rm -r "+f+"\n" ) ; sys.stdout.flush()
              shutil.rmtree( f )
            else:
              sys.stdout.write( "rm "+f+"\n" ) ; sys.stdout.flush()
              os.remove( f )

    def _check_write_mpi_machine_file(self):
        ""
        if hasattr( self.plugin_obj, 'machinefile' ):

            fp = open( "machinefile", "w" )
            try:
                fp.write( self.plugin_obj.machinefile )
            finally:
                fp.close()

            self.perms.set( os.path.abspath( "machinefile" ) )

    def _check_set_working_files(self, baseline):
        """
        establish soft links and make copies of working files
        """
        if not baseline:
            if not self.setWorkingFiles():
                sys.stdout.flush()
                sys.stderr.flush()
                os._exit(1)

    def setWorkingFiles(self):
        """
        Called before the test script is executed, this sets the link and
        copy files in the test execution directory.  Returns False if certain
        errors are encountered and written to stderr, otherwise True.
        """
        sys.stdout.write( "Linking and copying working files...\n" )
        sys.stdout.flush()

        srcdir = os.path.normpath(
                      os.path.join(
                          self.atest.getRootpath(),
                          os.path.dirname( self.atest.getFilepath() ) ) )
        
        ok = True

        # first establish the soft linked files
        for srcname,tstname in self.atest.getLinkFiles():
            
            f = os.path.normpath( os.path.join( srcdir, srcname ) )

            srcL = []
            if os.path.exists(f):
                srcL.append( f )
            else:
                fL = glob.glob( f )
                if len(fL) > 1 and tstname != None:
                    sys.stderr.write( "*** error: the test requested to " + \
                          "soft link a file that matched multiple sources " + \
                          "AND a single linkname was given: " + f + "\n" )
                    ok = False
                    continue
                else:
                    srcL.extend( fL )

            if len(srcL) > 0:
                
                for srcf in srcL:

                    if tstname == None:
                        tstf = os.path.basename( srcf )
                    else:
                        tstf = tstname
                    
                    if os.path.islink( tstf ):
                        lf = os.readlink( tstf )
                        if lf != srcf:
                            os.remove( tstf )
                            sys.stdout.write( 'ln -s '+srcf+' '+tstf+'\n' )
                            os.symlink( srcf, tstf )
                    
                    elif os.path.exists( tstf ):
                        if os.path.isdir( tstf ):
                            shutil.rmtree( tstf )
                        else:
                            os.remove( tstf )
                        sys.stdout.write( 'ln -s '+srcf+' '+tstf+'\n' )
                        os.symlink( srcf, tstf )
                    
                    else:
                        sys.stdout.write( 'ln -s '+srcf+' '+tstf+'\n' )
                        os.symlink( srcf, tstf )
            
            else:
                sys.stderr.write( "*** error: the test requested to " + \
                      "soft link a non-existent file: " + f + "\n" )
                ok = False
        
        # files to be copied
        for srcname,tstname in self.atest.getCopyFiles():

            f = os.path.normpath( os.path.join( srcdir, srcname ) )

            srcL = []
            if os.path.exists(f):
                srcL.append( f )
            else:
                fL = glob.glob( f )
                if len(fL) > 1 and tstname != None:
                    sys.stderr.write( "*** error: the test requested to " + \
                          "copy a file that matched multiple sources " + \
                          "AND a single copyname was given: " + f + "\n" )
                    ok = False
                    continue
                else:
                    srcL.extend( fL )

            if len(srcL) > 0:
                
                for srcf in srcL:
                    
                    if tstname == None:
                        tstf = os.path.basename( srcf )
                    else:
                        tstf = tstname
                    
                    if os.path.islink( tstf ):
                        os.remove( tstf )
                    elif os.path.exists( tstf ):
                        if os.path.isdir( tstf ):
                            shutil.rmtree( tstf )
                        else:
                            os.remove( tstf )

                    if os.path.isdir( srcf ):
                        sys.stdout.write( 'cp -rp '+srcf+' '+tstf+'\n' )
                        shutil.copytree( srcf, tstf, symlinks=True )
                    else:
                        sys.stdout.write( 'cp -p '+srcf+' '+tstf+'\n' )
                        shutil.copy2( srcf, tstf )
            
            else:
                sys.stderr.write( "*** error: the test requested to " + \
                      "copy a non-existent file: " + f + "\n" )
                ok = False

        return ok

    def copyBaselineFiles(self):
        """
        """
        troot = self.atest.getRootpath()
        tdir = os.path.dirname( self.atest.getFilepath() )
        srcdir = os.path.normpath( os.path.join( troot, tdir ) )
        
        # TODO: add file globbing for baseline files
        for fromfile,tofile in self.atest.getBaselineFiles():
            dst = os.path.join( srcdir, tofile )
            sys.stdout.write( "baseline: cp -p "+fromfile+" "+dst+'\n' )
            sys.stdout.flush()
            shutil.copy2( fromfile, dst )

    def _set_environ_for_python_execution(self, baseline):
        """
        set up python pathing to make import of script utils easy
        """
        pth = os.getcwd()
        if self.config.get('configdir'):
            # make sure the config dir comes before vvtest/config
            pth += ':'+self.config.get('configdir')

        d = self.config.get('toolsdir')
        pth += ':'+os.path.join( d, 'config' )
        pth += ':'+d

        val = os.environ.get( 'PYTHONPATH', '' )
        if val: os.environ['PYTHONPATH'] = pth + ':' + val
        else:   os.environ['PYTHONPATH'] = pth

    def postclean(self):
        """
        Should only be run right after the test script finishes.  It removes
        all files in the execute directory except for a few vvtest files.
        """
        xL = [ 'execute.log', 'baseline.log', 'machinefile' ]

        if self.atest.getSpecificationForm() == 'xml':
            xL.append( 'runscript' )

        # might as well keep the linked files
        for sf,tf in self.atest.getLinkFiles():
            if tf == None:
                tf = os.path.basename( sf )
            xL.append( tf )
        
        for f in os.listdir( self.xdir ):
          if f not in xL and not f.startswith( 'vvtest_util' ):
            fp = os.path.join( self.xdir, f )
            if os.path.islink( fp ):
              os.remove( fp )
            elif os.path.isdir( fp ):
              shutil.rmtree( fp )
            else:
              os.remove( fp )

    def _write_xml_run_script(self, commondb):
        ""
        # no 'form' defaults to the XML test specification format

        script_file = os.path.join( self.xdir, 'runscript' )

        if self.config.get('refresh') or not os.path.exists( script_file ):

            troot = self.atest.getRootpath()
            assert os.path.isabs( troot )
            tdir = os.path.dirname( self.atest.getFilepath() )
            srcdir = os.path.normpath( os.path.join( troot, tdir ) )

            # note that this writes a different sequence if the test is an
            # analyze test
            cshScriptWriter.writeScript( self.atest, commondb, self.platform,
                                         self.config.get('toolsdir'),
                                         self.config.get('exepath'),
                                         srcdir,
                                         self.config.get('onopts'),
                                         self.config.get('offopts'),
                                         script_file )

            self.perms.set( os.path.abspath( script_file ) )

    def _write_script_utils(self, test_dir):
        ""
        for lang in ['py','sh']:

            script_file = os.path.join( self.xdir, 'vvtest_util.'+lang )

            if self.config.get('refresh') or not os.path.exists( script_file ):
                ScriptWriter.writeScript( self.atest, script_file,
                                          lang, self.config, self.platform,
                                          test_dir,
                                          self.getDependencyDirectories() )

                self.perms.set( os.path.abspath( script_file ) )

    def __cmp__(self, rhs):
        if rhs == None: return 1  # None objects are always less
        return cmp( self.atest, rhs.atest )
    
    def __lt__(self, rhs):
        if rhs == None: return False  # None objects are always less
        return self.atest < rhs.atest


def redirect_stdout_stderr_to_filename( filename ):
    ""
    ofile = open( filename, "w+" )

    # reassign stdout & stderr file descriptors to the file
    os.dup2( ofile.fileno(), sys.stdout.fileno() )
    os.dup2( ofile.fileno(), sys.stderr.fileno() )


def echo_test_execution_info( testname, cmd_list, timeout ):
    ""
    sys.stdout.write( "Starting test: "+testname+'\n' )
    sys.stdout.write( "Directory    : "+os.getcwd()+'\n' )

    if cmd_list != None:
        sys.stdout.write( "Command      : "+' '.join( cmd_list )+'\n' )

    sys.stdout.write( "Timeout      : "+str(timeout)+'\n' )

    sys.stdout.write( '\n' )
    sys.stdout.flush()


def same_execute_directory( testobj1, testobj2 ):
    ""
    if isinstance( testobj1, TestExec ):
        xdir1 = testobj1.atest.getExecuteDirectory()
    else:
        xdir1 = testobj1.getExecuteDirectory()

    if isinstance( testobj2, TestExec ):
        xdir2 = testobj2.atest.getExecuteDirectory()
    else:
        xdir2 = testobj2.getExecuteDirectory()

    return xdir1 == xdir2


def set_timeout_environ_variable( timeout ):
    """
    add a timeout environ variable so the test can take steps to
    shutdown a running application that is taking too long;  add
    a bump factor so it won't shutdown before the test harness
    recognizes it as a timeout
    """
    if timeout > 0:

        if timeout < 30: t = 60
        if timeout < 120: t = timeout * 1.4
        else: t = timeout * 1.2

        os.environ['TIMEOUT'] = str( int( t ) )


def make_file_execute_command( srcdir, path ):
    ""
    if os.path.isabs( path ):
        if os.access( path, os.X_OK ):
            return [ path ]
        else:
            return [ sys.executable, path ]

    else:
        full = os.path.join( srcdir, path )
        if os.access( full, os.X_OK ):
            return [ './'+path ]
        else:
            return [ sys.executable, path ]


def make_test_script_command( atest ):
    ""
    if atest.getSpecificationForm() == 'xml':
        cmdL = ['/bin/csh', '-f', './runscript']
    else:
        srcdir,fname = os.path.split( atest.getFilename() )
        cmdL = make_file_execute_command( srcdir, fname )

    return cmdL


def command_from_filename_or_option( atest, spec ):
    ""
    if spec.startswith('-'):
        cmdL = make_test_script_command( atest )
        cmdL.append( spec )
    else:
        srcdir = atest.getDirectory()
        cmdL = make_file_execute_command( srcdir, spec )

    return cmdL


def make_baseline_analyze_command( atest ):
    ""
    bscr = atest.getBaselineScript()
    ascr = atest.getAnalyzeScript()

    if bscr.startswith('-'):
        # add the baseline option to the analyze script command
        cmdL = command_from_filename_or_option( atest, ascr )
        cmdL.append( bscr )

    else:
        # start with the baseline script command
        cmdL = command_from_filename_or_option( atest, bscr )

        # if there is an analyze script AND a baseline script, just use the
        # baseline script; but if there is an analyze option then add it
        if ascr.startswith('-'):
            cmdL.append( ascr )

    return cmdL


def make_script_baseline_command( atest ):
    ""
    if atest.isAnalyze():
        cmdL = make_baseline_analyze_command( atest )
    else:
        scr = atest.getBaselineScript()
        cmdL = command_from_filename_or_option( atest, scr )

    return cmdL


def check_make_script_baseline_command( atest ):
    ""
    if atest.getBaselineScript():
        cmdL = make_script_baseline_command( atest )
    else:
        cmdL = None

    return cmdL


def make_core_execute_command( atest, baseline ):
    ""
    if atest.getSpecificationForm() == 'xml':
        cmdL = make_test_script_command( atest )
        if baseline:
            if atest.getBaselineScript():
                cmdL.append( '--baseline' )
            else:
                cmdL = None

    else:
        if baseline:
            cmdL = check_make_script_baseline_command( atest )

        elif atest.isAnalyze():
            ascr = atest.getAnalyzeScript()
            cmdL = command_from_filename_or_option( atest, ascr )

        else:
            cmdL = make_test_script_command( atest )

    return cmdL


def decode_subprocess_exit_code( exit_code ):
    ""
    if os.WIFEXITED( exit_code ):
        return os.WEXITSTATUS( exit_code )

    if os.WIFSIGNALED( exit_code ) or os.WIFSTOPPED( exit_code ):
        return 1

    if exit_code == 0:
        return 0

    return 1
