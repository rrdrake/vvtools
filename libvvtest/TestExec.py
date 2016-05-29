#!/usr/bin/env python

import os, sys
import signal
import time
import shutil
import glob
import traceback

import cshScriptWriter
import ScriptWriter

# this is the exit status that tests use to indicate a diff
diffExitStatus = 64

# if a test times out, it receives a SIGINT.  if it doesn't finish up
# after that in this number of seconds, it gets sent a SIGKILL
interrupt_to_kill_timeout = 30


class TestExec:
    """
    Runs a test in the background and provides methods to poll and kill it.
    The status and test results are saved in the TestSpec object.
    """
    
    def __init__(self, atest, perms):
        """
        Constructs a test execution object which references a TestSpec obj.
        The 'perms' argument is a Permissions object, or None.
        """
        self.atest = atest
        self.perms = perms
        
        self.platform = None
        self.timeout = 0
        self.tzero = 0
        self.pid = 0
        self.xdir = None
        self.children = None  # parent tests will have a list of their children

        self.cmdL = None  # the first part of the launch command
    
    def init(self, test_dir, platform, commondb, config ):
        """
        The platform is a Platform object.  The test_dir is the top level
        testing directory, which is either an absolute path or relative to
        the current working directory.
        """
        self.platform = platform
        self.config = config
        self.timeout = self.atest.getAttr( 'timeout', 0 )
        
        self.xdir = os.path.join( test_dir, self.atest.getExecuteDirectory() )
        
        if not os.path.exists( self.xdir ):
          os.makedirs( self.xdir )
        
        if self.perms != None:
          self.perms.set( self.atest.getExecuteDirectory() )
        
        form = self.atest.getScriptForm()
            
        if form == None:
          
          # no 'form' defaults to the XML test specification format

          script_file = os.path.join( self.xdir, 'runscript' )
          
          if config.get('refresh') or not os.path.exists( script_file ):
            
            troot = self.atest.getRootpath()
            assert os.path.isabs( troot )
            tdir = os.path.dirname( self.atest.getFilepath() )
            srcdir = os.path.normpath( os.path.join( troot, tdir ) )
            
            cshScriptWriter.writeScript( self.atest, commondb, self.platform,
                                         config.get('toolsdir'),
                                         config.get('exepath'),
                                         srcdir,
                                         config.get('onopts'),
                                         config.get('offopts'),
                                         script_file )
            if self.perms != None:
              self.perms.set( os.path.abspath( script_file ) )

          self.cmdL = ['/bin/csh', '-f', './runscript']

          self.lang = 'xml'
        
        else:
          
          if self.atest.hasAnalyze():
            zfile = self.atest.getAnalyze( 'file', None )
            if zfile != None:
              # execute the analyze script rather than the test file
              lang = self.atest.getAnalyze( 'lang' )
              cmdL = self.atest.getAnalyze( 'cmd' )
            else:
              # execute the test file but add the analyze command line option
              lang = form['lang']
              cmdL = form['cmd']
              arg = self.atest.getAnalyze( 'arg', None )
              if arg != None:
                cmdL = cmdL + [ arg ]
          
          else:
            lang = form['lang']
            cmdL = form['cmd']

          self.cmdL = cmdL

          if lang:
              
              #  write utility script fragment

              script_file = os.path.join( self.xdir, 'vvtest_util.'+lang )
              
              if config.get('refresh') or not os.path.exists( script_file ):
                
                  ScriptWriter.writeScript( self.atest, script_file,
                                            lang, config, self.platform )
                  
                  if self.perms != None:
                      self.perms.set( os.path.abspath( script_file ) )

          self.lang = lang

    def start(self, baseline=0):
        """
        Launches the child process.
        """
        assert self.pid == 0
        
        cmd_list = [] + self.cmdL
        
        np = int( self.atest.getParameters().get('np', 0) )
        
        self.plugin_obj = self.platform.obtainProcs( np )
        
        logfname = 'execute.log'
        
        if baseline:
          cmd_list.append('--baseline')
          logfname = 'baseline.log'
        elif not self.config.get('logfile'):
          logfname = None
        
        if hasattr(self.plugin_obj, "mpi_opts") and self.plugin_obj.mpi_opts:
          cmd_list.extend(['--mpirun_opts', self.plugin_obj.mpi_opts])
        
        if self.config.get('analyze'):
          cmd_list.append('--analyze')
        
        self.tzero = time.time()
        
        self.timedout = 0  # holds time.time() if the test times out
        
        self.atest.setAttr( 'state', "notdone" )
        self.atest.setAttr( 'xtime', -1 )
        self.atest.setAttr( 'xdate', int(time.time()) )
        
        sys.stdout.flush() ; sys.stderr.flush()
        
        self.pid = os.fork()
        
        if self.pid == 0:  # child
          
          try:
            os.chdir(self.xdir)
            
            if self.timeout > 0:
              # add a timeout environ variable so the test can take steps to
              # shutdown a running application that is taking too long;  add
              # a bump factor so it won't shutdown before the test harness
              # recognizes it as a timeout
              if self.timeout < 30: t = 60
              if self.timeout < 120: t = self.timeout * 1.4
              else: t = self.timeout * 1.2
              os.environ['TIMEOUT'] = str( int( t ) )
            
            if hasattr( self.plugin_obj, 'run' ):
              self.plugin_obj.run( self.plugin_obj, self.timeout,
                                   self.xdir, logfname, cmd_list )
              sys.stdout.flush() ; sys.stderr.flush()
              os._exit(1)
            
            else:
              
              if logfname != None:
                
                # open the output files
                ofile = open( logfname, "w+" )
                
                # reassign stdout & stderr to the log file
                os.dup2(ofile.fileno(), sys.stdout.fileno())
                os.dup2(ofile.fileno(), sys.stderr.fileno())
                
                if self.perms != None:
                  self.perms.set( os.path.abspath( logfname ) )
              
              sys.stdout.write( "Starting test: "+self.atest.getName()+'\n' )
              sys.stdout.write( "Directory    : "+os.getcwd()+'\n' )
              sys.stdout.write( "Command      : "+' '.join( cmd_list )+'\n' )
              sys.stdout.write( "Timeout      : "+str(self.timeout)+'\n' )
              sys.stdout.write( '\n' )
              sys.stdout.flush()
              
              if self.config.get('preclean') and \
                 not self.config.get('analyze') and \
                 not baseline:
                self.preclean()
              
              if hasattr(self.plugin_obj, 'machinefile'):
                f = open("machinefile", "w")
                f.write(self.plugin_obj.machinefile)
                f.close()
                if self.perms != None:
                  self.perms.set( os.path.abspath( "machinefile" ) )
              
              if not self.setWorkingFiles():
                sys.stdout.flush() ; sys.stderr.flush()
                os._exit(1)

              if hasattr(self.plugin_obj, 'sshcmd'):
                
                # turn off X11 forwarding by unsetting the DISPLAY env variable
                # (should eliminate X authorization errors)
                if os.environ.has_key('DISPLAY'):
                  del os.environ['DISPLAY']
                
                safecmd = ''
                for arg in cmd_list:
                  if len( arg.split() ) > 1:
                    safecmd = safecmd + ' "' + arg + '"'
                  else:
                    safecmd = safecmd + ' ' + arg
                sshcmd = self.plugin_obj.sshcmd
                sshcmd.append('cd ' + os.getcwd() + ' &&' + safecmd)
                cmd_list = sshcmd
              
              if self.lang == 'py':
                # since the script is a soft link, the execute directory must
                # to be added to the python path (soft links are followed);
                # doing so enables "import vvtest_util" in the script
                val = os.environ.get( 'PYTHONPATH', '' )
                if val: os.environ['PYTHONPATH'] = os.getcwd() + ':' + val
                else:   os.environ['PYTHONPATH'] = os.getcwd()

              sys.stdout.write( '\n' )
              sys.stdout.flush()

              # replace this process with the command
              if os.path.isabs( cmd_list[0] ):
                  os.execve( cmd_list[0], cmd_list, os.environ )
              else:
                  os.execvpe( cmd_list[0], cmd_list, os.environ )
              
              raise Exception( "os.exec should not return" )

          except:
            sys.stdout.flush() ; sys.stderr.flush()
            traceback.print_exc()
            sys.stdout.flush() ; sys.stderr.flush()
            os._exit(1)
    
    def poll(self):
        """
        """
        if self.atest.getAttr('state') == "notrun": return 0
        
        if self.atest.getAttr('state') == "done": return 1
        
        assert self.pid > 0
        
        (cpid, code) = os.waitpid(self.pid, os.WNOHANG)
        
        if cpid > 0:
          
          # test finished
          
          self.platform.giveProcs( self.plugin_obj )
          
          self.atest.setAttr('state', "done")
          self.atest.setAttr('xtime', int(time.time()-self.tzero))
          
          # handle the resulting code
          if os.WIFEXITED(code):
            if os.WEXITSTATUS(code) == 0:
              self.atest.setAttr('result', 'pass')
            elif os.WEXITSTATUS(code) == diffExitStatus:
              self.atest.setAttr('result', 'diff')
            else:
              self.atest.setAttr('result', 'fail')
          elif os.WIFSIGNALED(code) or os.WIFSTOPPED(code):
            self.atest.setAttr('result', 'fail')
          else:
            # could not translate exit code
            if code == 0:
              self.atest.setAttr('result', 'pass')  # assume pass
            else:
              self.atest.setAttr('result', 'fail')  # assume fail
          
          if self.timedout > 0:
            self.atest.setAttr('result', "timeout")

          if self.perms != None:
            self.perms.recurse( self.xdir )

          if self.config.get('postclean') and \
             self.atest.getAttr('result') == 'pass' and \
             self.atest.getParent() == None:
            self.postclean()
          
        # not done .. check for timeout
        elif self.timeout > 0 and (time.time() - self.tzero) > self.timeout:
          if self.timedout == 0:
            # interrupt all processes in the process group
            self.signalJob()
            self.timedout = time.time()
          elif (time.time() - self.timedout) > interrupt_to_kill_timeout:
            # SIGINT isn't killing fast enough, use SIGKILL
            self.signalJob(signal.SIGKILL)
        
        return self.atest.getAttr('state') == "done"
    
    def isDone(self):
        return self.atest.getAttr('state') == "done"
    
    def signalJob(self, sig=signal.SIGINT):
        """
        Sends all the process in the job a signal.
        """
        for p in self._get_processes():
          try: os.kill(p, sig)
          except OSError: pass
    
    def killJob(self):
        """
        Sends the job a SIGINT signal, waits a little, and if the job
        has not shutdown, sends it a SIGKILL signal.
        """
        pids = self._get_processes()
        for p in pids:
          try: os.kill(p, signal.SIGINT)
          except OSError: pass
        time.sleep(2)
        if not self.poll():
          for p in pids:
            try: os.kill(p, signal.SIGKILL)
            except: pass
          time.sleep(5)
          self.poll()
    
    def addChild(self, testexec):
        """
        """
        if self.children == None:
          self.children = []
        self.children.append( testexec )
    
    def hasChildren(self):
        """
        """
        return self.children != None
    
    def getChildren(self):
        """
        """
        return self.children

    def badChild(self):
        """
        If this is a parent test and one of its children didn't run, didn't
        finish, or failed, then that offending child is returned.  Otherwise,
        None is returned.
        """
        if self.children != None:
          for tx in self.children:
            if tx.atest.getAttr('state') != 'done' or \
               tx.atest.getAttr('result') not in ['pass','diff']:
              return tx
        return None
    
    def preclean(self):
        """
        Should only be run just prior to launching the test script.  It
        removes all files in the execute directory except for a few vvtest
        files.
        """
        sys.stdout.write( "Cleaning execute directory...\n" )
        sys.stdout.flush()

        for f in os.listdir('.'):
          if f not in ['execute.log', 'baseline.log', 'runscript'] \
             and not f.startswith( 'vvtest_util' ):
            if os.path.isdir(f):
              sys.stdout.write( "rm -r "+f+"\n" ) ; sys.stdout.flush()
              shutil.rmtree( f )
            else:
              sys.stdout.write( "rm "+f+"\n" ) ; sys.stdout.flush()
              os.remove( f )
    
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

    def postclean(self):
        """
        Should only be run right after the test script finishes.  It
        removes all files in the execute directory except for a few vvtest
        files.
        """
        for f in os.listdir( self.xdir ):
          if f != 'execute.log' and f != 'baseline.log' and \
             f != 'runscript' and f != 'machinefile':
            fp = os.path.join( self.xdir, f )
            if os.path.islink( fp ):
              os.remove( fp )
            elif os.path.isdir( fp ):
              shutil.rmtree( fp )
            else:
              os.remove( fp )

    pscmd = None
    
    def _get_processes(self, rpid=None, psdict=None, pidlist=None):
        """
        Retrieves all descendent processes of the job and returns them
        in a list.  The rpid, psdict, and pidlist arguments are for
        internal use.
        """
        if TestExec.pscmd == None:
          if os.system( "ps -ef > /dev/null" ) == 0:
            TestExec.pscmd = [ 'ps', '-ef' ]
          elif os.system( "ps -Ao user,pid,ppid > /dev/null" ) == 0:
            TestExec.pscmd = [ 'ps', '-Ao', 'user,pid,ppid' ]
          else:
            TestExec.pscmd = [ 'ps', '-ef' ]
        
        if rpid == None:
          
          if self.pid <= 0:
            return []
          
          # run the platform's ps command to get a list of all processes
          
          sys.stdout.flush()
          
          outRead, outWrite = os.pipe()
          pspid = os.fork()
          
          if pspid == 0:
            os.close(outRead)
            os.dup2(outWrite, sys.stdout.fileno())
            os.execvp( TestExec.pscmd[0], TestExec.pscmd )
            assert 0, "execvp should not return"
          
          os.close(outWrite)
          
          psdict = {}
          lineno = 0
          for line in os.fdopen(outRead).readlines():
            if lineno > 0:
              linelist = line.split()
              try:
                cpid = int(linelist[1])
                ppid = int(linelist[2])
              except:
                # if the ps output is not "name pid parentpid ..." then ignore
                pass
              else:
                # skip the init process
                if ppid > 1:
                  if psdict.has_key( ppid ):
                    psdict[ppid].append(cpid)
                  else:
                    psdict[ppid] = [cpid]
            
            lineno = lineno + 1
          
          os.waitpid(pspid, 0)
          
          pidlist = [self.pid]
          self._get_processes(self.pid, psdict, pidlist)
          return pidlist
        
        else: # this is a recursive call
          pids = psdict.get(rpid, [])
          pidlist.extend(pids)
          for p in pids:
            self._get_processes(p, psdict, pidlist)
        
        return None
