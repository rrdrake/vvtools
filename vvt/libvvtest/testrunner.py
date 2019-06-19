#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import shutil
import glob

from . import cshScriptWriter
from . import ScriptWriter
from .makecmd import MakeScriptCommand


def initialize_for_execution( tcase, test_dir, platform,
                              commondb, config, usrplugin, perms ):
    """
    The platform is a Platform object.  The test_dir is the top level
    testing directory, which is either an absolute path or relative to
    the current working directory.
    """
    tspec = tcase.getSpec()
    texec = tcase.getExec()
    tstat = tcase.getStat()

    handler = ExecutionHandler( tcase, perms, config, platform, usrplugin )
    texec.setExecutionHandler( handler )

    texec.setTimeout( tspec.getAttr( 'timeout', 0 ) )

    tstat.resetResults()

    wdir = os.path.join( test_dir, tspec.getExecuteDirectory() )
    texec.setRunDirectory( wdir )

    if not os.path.exists( wdir ):
        os.makedirs( wdir )

    perms.set( tspec.getExecuteDirectory() )

    if tspec.getSpecificationForm() == 'xml':
        write_xml_run_script( tcase, commondb, config, platform, perms )
    else:
        write_script_utils( tcase, test_dir, config, platform, perms )


def write_xml_run_script( tcase, commondb, config, platform, perms ):
    ""
    # no 'form' defaults to the XML test specification format

    tspec = tcase.getSpec()
    texec = tcase.getExec()
    rundir = texec.getRunDirectory()

    script_file = os.path.join( rundir, 'runscript' )

    if config.get('refresh') or not os.path.exists( script_file ):

        troot = tspec.getRootpath()
        assert os.path.isabs( troot )
        tdir = os.path.dirname( tspec.getFilepath() )
        srcdir = os.path.normpath( os.path.join( troot, tdir ) )

        # note that this writes a different sequence if the test is an
        # analyze test
        cshScriptWriter.writeScript( tspec, commondb, platform,
                                     config.get('toolsdir'),
                                     config.get('exepath'),
                                     srcdir,
                                     config.get('onopts'),
                                     config.get('offopts'),
                                     script_file )

        perms.set( os.path.abspath( script_file ) )


def write_script_utils( tcase, test_dir, config, platform, perms ):
    ""
    texec = tcase.getExec()
    rundir = texec.getRunDirectory()

    for lang in ['py','sh']:

        script_file = os.path.join( rundir, 'vvtest_util.'+lang )

        if config.get('refresh') or not os.path.exists( script_file ):
            ScriptWriter.writeScript( tcase, script_file,
                                      lang, config, platform,
                                      test_dir )

            perms.set( os.path.abspath( script_file ) )


class ExecutionHandler:

    def __init__(self, tcase, perms, config, platform, usrplugin):
        ""
        self.tcase = tcase
        self.perms = perms
        self.config = config
        self.platform = platform
        self.plugin = usrplugin

    def check_redirect_output_to_log_file(self, baseline):
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

    def check_run_preclean(self, baseline):
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

        if self.tcase.getSpec().getSpecificationForm() == 'xml':
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

    def check_set_working_files(self, baseline):
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

        tspec = self.tcase.getSpec()

        srcdir = os.path.normpath(
                      os.path.join(
                          tspec.getRootpath(),
                          os.path.dirname( tspec.getFilepath() ) ) )

        ok = True

        # first establish the soft linked files
        for srcname,tstname in tspec.getLinkFiles():

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
        for srcname,tstname in tspec.getCopyFiles():

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

    def apply_plugin_preload(self):
        ""
        pyexe = self.plugin.testPreload( self.tcase )
        if pyexe:
            return pyexe
        else:
            return sys.executable

    def set_timeout_environ_variable(self, timeout):
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

            # [Apr 2019] using TIMEOUT is deprecated
            os.environ['TIMEOUT'] = str( int( t ) )
            os.environ['VVTEST_TIMEOUT'] = str( int( t ) )

    def set_environ_for_python_execution(self, baseline):
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

    def check_postclean(self):
        ""
        if self.config.get('postclean') and \
           self.tcase.getStat().passed() and \
           not self.tcase.hasDependent():
            self.postclean()

    def postclean(self):
        """
        Should only be run right after the test script finishes.  It removes
        all files in the execute directory except for a few vvtest files.
        """
        xL = [ 'execute.log', 'baseline.log', 'machinefile' ]

        tspec = self.tcase.getSpec()

        if tspec.getSpecificationForm() == 'xml':
            xL.append( 'runscript' )

        # might as well keep the linked files
        for sf,tf in tspec.getLinkFiles():
            if tf == None:
                tf = os.path.basename( sf )
            xL.append( tf )

        rundir = self.tcase.getExec().getRunDirectory()

        for f in os.listdir( rundir ):
            if f not in xL and not f.startswith( 'vvtest_util' ):
                fp = os.path.join( rundir, f )
                if os.path.islink( fp ):
                    os.remove( fp )
                elif os.path.isdir( fp ):
                    shutil.rmtree( fp )
                else:
                    os.remove( fp )

    def copyBaselineFiles(self):
        """
        """
        tspec = self.tcase.getSpec()

        troot = tspec.getRootpath()
        tdir = os.path.dirname( tspec.getFilepath() )
        srcdir = os.path.normpath( os.path.join( troot, tdir ) )

        # TODO: add file globbing for baseline files
        for fromfile,tofile in tspec.getBaselineFiles():
            dst = os.path.join( srcdir, tofile )
            sys.stdout.write( "baseline: cp -p "+fromfile+" "+dst+'\n' )
            sys.stdout.flush()
            shutil.copy2( fromfile, dst )

    def check_write_mpi_machine_file(self):
        ""
        obj = self.tcase.getExec().getResourceObject()

        if hasattr( obj, 'machinefile' ):

            fp = open( "machinefile", "w" )
            try:
                fp.write( obj.machinefile )
            finally:
                fp.close()

            self.perms.set( os.path.abspath( "machinefile" ) )

    def finishExecution(self, exit_status, timedout):
        ""
        tspec = self.tcase.getSpec()
        tstat = self.tcase.getStat()

        if timedout > 0:
            tstat.markTimedOut()
        else:
            tstat.markDone( exit_status )

        rundir = self.tcase.getExec().getRunDirectory()
        self.perms.recurse( rundir )

        self.check_postclean()

        self.platform.giveProcs( self.tcase.getExec().getResourceObject() )

    def make_execute_command(self, baseline, pyexe):
        ""
        maker = MakeScriptCommand( self.tcase.getSpec(), pyexe )
        cmdL = maker.make_base_execute_command( baseline )

        if cmdL != None:

            obj = self.tcase.getExec().getResourceObject()
            if hasattr( obj, "mpi_opts") and obj.mpi_opts:
                cmdL.extend( ['--mpirun_opts', obj.mpi_opts] )

            if self.config.get('analyze'):
                cmdL.append('--execute_analysis_sections')

            cmdL.extend( self.config.get( 'testargs' ) )

        return cmdL

    def prepare_for_launch(self, baseline):
        ""
        self.check_redirect_output_to_log_file( baseline )

        tm = self.tcase.getExec().getTimeout()
        self.set_timeout_environ_variable( tm )

        self.check_run_preclean( baseline )
        self.check_write_mpi_machine_file()
        self.check_set_working_files( baseline )

        self.set_environ_for_python_execution( baseline )

        pyexe = self.apply_plugin_preload()

        cmd_list = self.make_execute_command( baseline, pyexe )

        echo_test_execution_info( self.tcase.getSpec().getName(), cmd_list, tm )

        sys.stdout.write( '\n' )
        sys.stdout.flush()

        if baseline:
            self.copyBaselineFiles()

        return cmd_list


def echo_test_execution_info( testname, cmd_list, timeout ):
    ""
    sys.stdout.write( "Starting test: "+testname+'\n' )
    sys.stdout.write( "Directory    : "+os.getcwd()+'\n' )

    if cmd_list != None:
        sys.stdout.write( "Command      : "+' '.join( cmd_list )+'\n' )

    sys.stdout.write( "Timeout      : "+str(timeout)+'\n' )

    sys.stdout.write( '\n' )
    sys.stdout.flush()


def redirect_stdout_stderr_to_filename( filename ):
    ""
    ofile = open( filename, "w+" )

    # reassign stdout & stderr file descriptors to the file
    os.dup2( ofile.fileno(), sys.stdout.fileno() )
    os.dup2( ofile.fileno(), sys.stderr.fileno() )
