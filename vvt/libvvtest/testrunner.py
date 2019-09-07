#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import shutil
import glob
import fnmatch
from os.path import normpath, dirname
from os.path import join as pjoin

from . import CommonSpec
from . import cshScriptWriter
from . import ScriptWriter
from .makecmd import MakeScriptCommand


class TestRunner:

    def __init__(self, test_dir, platform, rtconfig, usrplugin, perms):
        """
        The platform is a Platform object.  The test_dir is the top level
        testing directory, which is either an absolute path or relative to
        the current working directory.
        """
        self.test_dir = test_dir
        self.platform = platform
        self.rtconfig = rtconfig
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
                                    self.rtconfig,
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
                d = pjoin( self.rtconfig.get('vvtestdir'), 'libvvtest' )
                c = self.rtconfig.get('configdir')
                self.commondb = CommonSpec.loadCommonSpec( d, c )

            return self.commondb

        return None


class ExecutionHandler:

    def __init__(self, tcase, perms, rtconfig, platform,
                       usrplugin, test_dir, commondb):
        ""
        self.tcase = tcase
        self.perms = perms
        self.rtconfig = rtconfig
        self.platform = platform
        self.plugin = usrplugin
        self.test_dir = test_dir
        self.commondb = commondb

    def check_redirect_output_to_log_file(self, baseline):
        ""
        if self.rtconfig.get('logfile'):
            logfname = get_execution_log_filename( self.tcase, baseline )
            redirect_stdout_stderr_to_filename( logfname )
            self.perms.set( os.path.abspath( logfname ) )

    def check_run_preclean(self, baseline):
        ""
        if self.rtconfig.get('preclean') and \
           not self.rtconfig.get('analyze') and \
           not baseline and \
           self.tcase.getSpec().isFirstStage():
            self.preclean()

    def preclean(self):
        """
        Should only be run just prior to launching the test script.  It
        removes all files in the execute directory except for a few vvtest
        files.
        """
        print3( "Cleaning execute directory for execution..." )
        specform = self.tcase.getSpec().getSpecificationForm()
        pre_clean_execute_directory( specform )

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
        print3( "Linking and copying working files..." )

        tspec = self.tcase.getSpec()

        srcdir = normpath( pjoin( tspec.getRootpath(),
                                  dirname( tspec.getFilepath() ) ) )

        ok = link_and_copy_files( srcdir,
                                  tspec.getLinkFiles(),
                                  tspec.getCopyFiles() )

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

        cfgd = self.rtconfig.get( 'configdir' )
        if cfgd and ':' not in cfgd:
            val += ':'+cfgd

        tdir = self.rtconfig.get( 'vvtestdir' )
        if ':' not in tdir:
            val += ':'+pjoin( tdir, 'config' ) + ':'+tdir

        if 'PYTHONPATH' in os.environ:
            val += ':'+os.environ['PYTHONPATH']

        if not val:
            val = ':'

        os.environ['PYTHONPATH'] = val

    def check_run_postclean(self):
        ""
        if self.rtconfig.get('postclean') and \
           self.tcase.getStat().passed() and \
           not self.tcase.hasDependent() and \
           self.tcase.getSpec().isLastStage():
            self.postclean()

    def postclean(self):
        """
        Should only be run right after the test script finishes.  It removes
        all files in the execute directory except for a few vvtest files.
        """
        print3( "Cleaning execute directory after execution..." )

        specform = self.tcase.getSpec().getSpecificationForm()
        rundir = self.tcase.getExec().getRunDirectory()

        post_clean_execute_directory( rundir, specform )

    def copyBaselineFiles(self):
        ""
        tspec = self.tcase.getSpec()

        troot = tspec.getRootpath()
        tdir = os.path.dirname( tspec.getFilepath() )
        srcdir = normpath( pjoin( troot, tdir ) )

        # TODO: add file globbing for baseline files
        for fromfile,tofile in tspec.getBaselineFiles():
            dst = pjoin( srcdir, tofile )
            print3( "baseline: cp -p "+fromfile+" "+dst )
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

            if self.rtconfig.get('analyze'):
                cmdL.append('--execute_analysis_sections')

            cmdL.extend( self.rtconfig.get( 'testargs' ) )

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

        print3()

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

        if self.rtconfig.get('refresh') or not os.path.exists( script_file ):

            troot = tspec.getRootpath()
            assert os.path.isabs( troot )
            tdir = os.path.dirname( tspec.getFilepath() )
            srcdir = normpath( pjoin( troot, tdir ) )

            # note that this writes a different sequence if the test is an
            # analyze test
            cshScriptWriter.writeScript( tspec,
                                         self.commondb,
                                         self.platform,
                                         self.rtconfig.get('vvtestdir'),
                                         self.rtconfig.get('exepath'),
                                         srcdir,
                                         self.rtconfig.get('onopts'),
                                         self.rtconfig.get('offopts'),
                                         script_file )

            self.perms.set( os.path.abspath( script_file ) )

    def write_script_utils(self):
        ""
        texec = self.tcase.getExec()
        rundir = texec.getRunDirectory()

        for lang in ['py','sh']:

            script_file = pjoin( rundir, 'vvtest_util.'+lang )

            if self.rtconfig.get('refresh') or not os.path.exists( script_file ):
                ScriptWriter.writeScript( self.tcase,
                                          script_file,
                                          lang,
                                          self.rtconfig,
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
    print3( "Starting test: "+testname )
    print3( "Directory    : "+os.getcwd() )

    if cmd_list != None:
        print3( "Command      : "+' '.join( cmd_list ) )

    print3( "Timeout      : "+str(timeout) )

    print3()


def pre_clean_execute_directory( specform ):
    ""
    excludes = [ 'execute.log',
                 'baseline.log',
                 'vvtest_util.py',
                 'vvtest_util.sh' ]

    if specform == 'xml':
        excludes.append( 'runscript' )

    for fn in os.listdir('.'):
        if fn not in excludes and \
           not fnmatch.fnmatch( fn, 'execute_*.log' ):
            remove_path( fn )


def post_clean_execute_directory( rundir, specform ):
    ""
    excludes = [ 'execute.log',
                 'baseline.log',
                 'vvtest_util.py',
                 'vvtest_util.sh',
                 'machinefile' ]

    if specform == 'xml':
        excludes.append( 'runscript' )

    for fn in os.listdir( rundir ):
        if fn not in excludes and \
           not fnmatch.fnmatch( fn, 'execute_*.log' ):
            fullpath = pjoin( rundir, fn )
            if not os.path.islink( fullpath ):
                remove_path( fullpath )


def link_and_copy_files( srcdir, linkfiles, copyfiles ):
    ""
    ok = True

    for srcname,destname in linkfiles:

        srcf = normpath( pjoin( srcdir, srcname ) )
        srcL = get_source_file_names( srcf )

        if check_source_file_list( 'soft link', srcf, srcL, destname ):
            for srcf in srcL:
                force_link_path_to_current_directory( srcf, destname )
        else:
            ok = False

    for srcname,destname in copyfiles:

        srcf = normpath( pjoin( srcdir, srcname ) )
        srcL = get_source_file_names( srcf )

        if check_source_file_list( 'copy', srcf, srcL, destname ):
            for srcf in srcL:
                force_copy_path_to_current_directory( srcf, destname )
        else:
            ok = False

    return ok


def check_source_file_list( operation_type, srcf, srcL, destname ):
    ""
    ok = True

    if len( srcL ) == 0:
        print3( "*** error: cannot", operation_type,
                "a non-existent file:", srcf )
        ok = False

    elif len( srcL ) > 1 and destname != None:
        print3( "*** error:", operation_type, "failed because the source",
                "expanded to more than one file but a destination path",
                "was given:", srcf, destname )
        ok = False

    return ok


def get_source_file_names( srcname ):
    ""
    files = []

    if os.path.exists( srcname ):
        files.append( srcname )
    else:
        files.extend( glob.glob( srcname ) )

    return files


def force_link_path_to_current_directory( srcf, destname ):
    ""
    if destname == None:
        tstf = os.path.basename( srcf )
    else:
        tstf = destname

    if os.path.islink( tstf ):
        lf = os.readlink( tstf )
        if lf != srcf:
            os.remove( tstf )
            print3( 'ln -s '+srcf+' '+tstf )
            os.symlink( srcf, tstf )
    else:
        remove_path( tstf )
        print3( 'ln -s '+srcf+' '+tstf )
        os.symlink( srcf, tstf )


def force_copy_path_to_current_directory( srcf, destname ):
    ""
    if destname == None:
        tstf = os.path.basename( srcf )
    else:
        tstf = destname

    remove_path( tstf )

    if os.path.isdir( srcf ):
        print3( 'cp -rp '+srcf+' '+tstf )
        shutil.copytree( srcf, tstf, symlinks=True )
    else:
        print3( 'cp -p '+srcf+' '+tstf )
        shutil.copy2( srcf, tstf )


def remove_path( path ):
    ""
    if os.path.islink( path ):
        os.remove( path )

    elif os.path.exists( path ):
        if os.path.isdir( path ):
            shutil.rmtree( path )
        else:
            os.remove( path )


def redirect_stdout_stderr_to_filename( filename ):
    ""
    ofile = open( filename, "w+" )

    # reassign stdout & stderr file descriptors to the file
    os.dup2( ofile.fileno(), sys.stdout.fileno() )
    os.dup2( ofile.fileno(), sys.stderr.fileno() )


def print3( *args ):
    ""
    sys.stdout.write( ' '.join( [ str(x) for x in args ] ) + '\n' )
    sys.stdout.flush()

def printerr( *args ):
    ""
    sys.stderr.write( ' '.join( [ str(x) for x in args ] ) + '\n' )
    sys.stderr.flush()
