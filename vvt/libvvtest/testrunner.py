#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import shutil
import glob
import fnmatch
from os.path import join as pjoin

from . import CommonSpec
from . import cshScriptWriter
from . import ScriptWriter
from .makecmd import MakeScriptCommand


class TestRunner:

    def __init__(self, test_dir, platform, config, usrplugin, perms):
        """
        The platform is a Platform object.  The test_dir is the top level
        testing directory, which is either an absolute path or relative to
        the current working directory.
        """
        self.test_dir = test_dir
        self.platform = platform
        self.config = config
        self.usrplugin = usrplugin
        self.perms = perms

        self.commondb = None

    def initialize_for_execution(self, tcase):
        ""
        tspec = tcase.getSpec()
        texec = tcase.getExec()
        tstat = tcase.getStat()

        handler = ExecutionHandler( tcase,
                                    self.perms,
                                    self.config,
                                    self.platform,
                                    self.usrplugin,
                                    self.test_dir,
                                    self.getCommonXMLDB( tspec ) )
        texec.setExecutionHandler( handler )

        texec.setTimeout( tspec.getAttr( 'timeout', 0 ) )

        tstat.resetResults()

        xdir = tspec.getExecuteDirectory()
        wdir = pjoin( self.test_dir, xdir )
        texec.setRunDirectory( wdir )

        if not os.path.exists( wdir ):
            os.makedirs( wdir )

        self.perms.set( xdir )

    def getCommonXMLDB(self, tspec):
        ""
        if tspec.getSpecificationForm() == 'xml':
            if self.commondb == None:
                d = pjoin( self.config.get('vvtestdir'), 'libvvtest' )
                c = self.config.get('configdir')
                self.commondb = CommonSpec.loadCommonSpec( d, c )

            return self.commondb

        return None


class ExecutionHandler:

    def __init__(self, tcase, perms, config, platform,
                       usrplugin, test_dir, commondb):
        ""
        self.tcase = tcase
        self.perms = perms
        self.config = config
        self.platform = platform
        self.plugin = usrplugin
        self.test_dir = test_dir
        self.commondb = commondb

    def check_redirect_output_to_log_file(self, baseline):
        ""
        if self.config.get('logfile'):
            logfname = get_execution_log_filename( self.tcase, baseline )
            redirect_stdout_stderr_to_filename( logfname )
            self.perms.set( os.path.abspath( logfname ) )

    def check_run_preclean(self, baseline):
        ""
        if self.config.get('preclean') and \
           not self.config.get('analyze') and \
           not baseline and \
           self.tcase.getSpec().isFirstStage():
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
            if f not in xL and not f.startswith( 'vvtest_util' ) and \
               not fnmatch.fnmatch( f, 'execute_*.log' ):
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
                      pjoin( tspec.getRootpath(),
                             os.path.dirname( tspec.getFilepath() ) ) )

        ok = True

        # first establish the soft linked files
        for srcname,tstname in tspec.getLinkFiles():

            f = os.path.normpath( pjoin( srcdir, srcname ) )

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

            f = os.path.normpath( pjoin( srcdir, srcname ) )

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

    def set_PYTHONPATH(self, baseline):
        """
        When running Python in a test, the sys.path must include a few vvtest
        directories as well as the user's config dir.  This can be done with
        PYTHONPATH *unless* a directory contains a colon, which messes up
        Python's handling of the paths.

        To work in this case, sys.path is set in the vvtest_util.py file.
        The user's test just imports vvtest_util.py first thing.  However,
        importing vvtest_util.py assumes the execute directory is in sys.path
        on startup.  Normally it would be, but this can fail to be the case
        if the script is a soft link (which it is for the test script).

        The solution is to make sure PYTHONPATH contains an empty directory,
        which Python will expand to the current working directory. Note that
        versions of Python before 3.4 would allow the value of PYTHONPATH to
        be an empty string, but for 3.4 and later, it must at least be a single
        colon.

        [July 2019] To preserve backward compatibility for tests that do not
        import vvtest_util.py first thing, the directories are placed in
        PYTHONPATH here too (but only those that do not contain colons).
        """
        val = ''

        cfgd = self.config.get( 'configdir' )
        if cfgd and ':' not in cfgd:
            val += ':'+cfgd

        tdir = self.config.get( 'vvtestdir' )
        if ':' not in tdir:
            val += ':'+pjoin( tdir, 'config' ) + ':'+tdir

        if 'PYTHONPATH' in os.environ:
            val += ':'+os.environ['PYTHONPATH']

        if not val:
            val = ':'

        os.environ['PYTHONPATH'] = val

    def check_run_postclean(self):
        ""
        if self.config.get('postclean') and \
           self.tcase.getStat().passed() and \
           not self.tcase.hasDependent() and \
           self.tcase.getSpec().isLastStage():
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

        # magic: this is ugly, and duplicates with preclean somewhat
        for f in os.listdir( rundir ):
            if f not in xL and not f.startswith( 'vvtest_util' ) and \
               not fnmatch.fnmatch( f, 'execute_*.log' ):
                fp = pjoin( rundir, f )
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
        srcdir = os.path.normpath( pjoin( troot, tdir ) )

        # TODO: add file globbing for baseline files
        for fromfile,tofile in tspec.getBaselineFiles():
            dst = pjoin( srcdir, tofile )
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

        self.check_run_postclean()

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

        if self.tcase.getSpec().getSpecificationForm() == 'xml':
            self.write_xml_run_script()
        else:
            self.write_script_utils()

        tm = self.tcase.getExec().getTimeout()
        self.set_timeout_environ_variable( tm )

        self.check_run_preclean( baseline )
        self.check_write_mpi_machine_file()
        self.check_set_working_files( baseline )

        self.set_PYTHONPATH( baseline )

        pyexe = self.apply_plugin_preload()

        cmd_list = self.make_execute_command( baseline, pyexe )

        echo_test_execution_info( self.tcase.getSpec().getName(), cmd_list, tm )

        sys.stdout.write( '\n' )
        sys.stdout.flush()

        if baseline:
            self.copyBaselineFiles()

        return cmd_list

    def write_xml_run_script(self):
        ""
        # no 'form' defaults to the XML test specification format

        tspec = self.tcase.getSpec()
        texec = self.tcase.getExec()
        rundir = texec.getRunDirectory()

        script_file = pjoin( rundir, 'runscript' )

        if self.config.get('refresh') or not os.path.exists( script_file ):

            troot = tspec.getRootpath()
            assert os.path.isabs( troot )
            tdir = os.path.dirname( tspec.getFilepath() )
            srcdir = os.path.normpath( pjoin( troot, tdir ) )

            # note that this writes a different sequence if the test is an
            # analyze test
            cshScriptWriter.writeScript( tspec,
                                         self.commondb,
                                         self.platform,
                                         self.config.get('vvtestdir'),
                                         self.config.get('exepath'),
                                         srcdir,
                                         self.config.get('onopts'),
                                         self.config.get('offopts'),
                                         script_file )

            self.perms.set( os.path.abspath( script_file ) )

    def write_script_utils(self):
        ""
        texec = self.tcase.getExec()
        rundir = texec.getRunDirectory()

        for lang in ['py','sh']:

            script_file = pjoin( rundir, 'vvtest_util.'+lang )

            if self.config.get('refresh') or not os.path.exists( script_file ):
                ScriptWriter.writeScript( self.tcase,
                                          script_file,
                                          lang,
                                          self.config,
                                          self.platform,
                                          self.test_dir )

                self.perms.set( os.path.abspath( script_file ) )


def get_execution_log_filename( tcase, baseline ):
    ""
    stageid = tcase.getSpec().getStageID()

    if baseline:
        logfname = 'baseline.log'
    elif stageid != None:
        logfname = 'execute_'+stageid+'.log'
    else:
        logfname = 'execute.log'

    return logfname


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
