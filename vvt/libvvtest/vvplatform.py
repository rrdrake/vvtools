#!/usr/bin/env python

import os, sys
import re

############################################################################

class Platform:
    """
    This class is .
    """
    
    def __init__(self, vvtesthome, optdict):
        
        self.vvtesthome = vvtesthome
        self.optdict = optdict
        
        self.maxprocs = 1
        self.nprocs = 0
        self.nfree = 0
        
        self.platname = None
        self.cplrname = None

        self.plugin = None

        self.envD = {}
        self.attrs = {}

        self.batch = None
    
    # ----------------------------------------------------------------
    
    def getName(self):  return self.platname
    def getCompiler(self): return self.cplrname
    def getOptions(self): return self.optdict
    def getMaxProcs(self): return self.maxprocs
    
    def display(self):
        s = "Platform " + self.platname
        if self.nprocs > 0:
            s += ", num procs = " + str(self.nprocs)
        s += ", max procs = " + str(self.maxprocs)
        print s
    
    def getEnvironment(self):
        """
        Returns a dictionary of environment variables and their values.
        """
        return self.envD
    
    # ----------------------------------------------------------------
    
    def setenv(self, name, value):
        """
        """
        if value == None:
            if name in self.envD:
                del self.envD[name]
        else:
            self.envD[name] = value

    def setattr(self, name, value):
        """
        """
        if value == None:
            if name in self.attrs:
                del self.attrs[name]
        else:
            self.attrs[name] = value

    def setBatchSystem(self, batch, ppn, **kwargs ):
        """
        Set the batch system for this platform.  If 'batch' is a string, it
        must be one of the known batch systems, such as

              craypbs   : for Cray machines running PBS (or PBS-like)
              moab      : for Cray machines running Moab (may work in general)
              pbs       : standard PBS system
              slurm     : standard SLURM system

        It can also be a python object which implements the batch functions.
        """
        assert ppn and ppn > 0

        if type(batch) == type(''):
            if batch == 'craypbs':
                import craypbs
                self.batch = craypbs.BatchCrayPBS( ppn, **kwargs )
            elif batch == 'pbs':
                import pbs
                self.batch = pbs.BatchPBS( ppn, **kwargs )
            elif batch == 'slurm':
                import slurm
                self.batch = slurm.BatchSLURM( ppn, **kwargs )
            elif batch == 'moab':
                import moab
                self.batch = moab.BatchMOAB( ppn, **kwargs )
            else:
                raise Exception( "Unknown batch system name: "+str(batch) )
        else:
            self.batch = batch

    def getQsubScriptHeader(self, np, queue_time, workdir, qout_file):
        """
        """
        if not self.batch:
            # construct a default processor batch system
            import procbatch
            self.batch = procbatch.ProcessBatch( 1 )

        qt = self.attrs.get( 'walltime', queue_time )

        hdr = '#!/bin/csh -f\n' + \
              self.batch.header( np, qt, workdir, qout_file ) + '\n'

        if qout_file:
            hdr += 'touch '+qout_file + ' || exit 1\n'

        # add in the shim if specified for this platform
        s = self.attrs.get( 'batchshim', None )
        if s:
            hdr += '\n'+s
        hdr += '\n'

        return hdr
    
    def getDefaultQsubLimit(self):
        """
        """
        n = self.attrs.get( 'maxsubs', 5 )
        return n
    
    def Qsubmit(self, workdir, outfile, scriptname):
        """
        """
        q = self.attrs.get( 'queue', None )
        acnt = self.attrs.get( 'account', None )
        cmd, out, jobid, err = \
                self.batch.submit( scriptname, workdir, outfile, q, acnt )
        if err:
            print cmd + os.linesep + out + os.linesep + err
        else:
            print "Job script", scriptname, "submitted with id", jobid
        
        return jobid
    
    def Qquery(self, jobidL):
        """
        """
        cmd, out, err, jobD = self.batch.query( jobidL )
        if err:
            print cmd + os.linesep + out + os.linesep + err
        return jobD
        
        return jobD
    
    def initProcs(self, set_num, set_max):
        """
        Determines the number of processors and the maximum number for the
        current platform.

        For max procs:
            1. Use 'set_max' if not None
            2. The "maxprocs" attribute if set by the platform plugin
            3. Try to probe the system
            4. The value one if all else fails

        For num procs:
            1. Use 'set_num' if not None
            2. The value of max procs

        This function should not be called for batch mode.
        """
        if set_max == None:
            mx = self.attrs.get( 'maxprocs', None )
            if mx == None:
                if self.batch == None:
                    mx = probe_max_processors()
                else:
                    mx = 2**31 - 1  # by default, no limit for batch systems
            self.maxprocs = mx if mx != None else 1
        else:
            self.maxprocs = set_max

        if set_num == None:
            self.nprocs = self.maxprocs
        else:
            self.nprocs = set_num
        
        self.nfree = self.nprocs
    
    def queryProcs(self, np):
        """
        """
        if np <= 0: np = 1
        return np <= self.nfree
    
    def obtainProcs(self, np):
        """
        """
        if np <= 0: np = 1

        if self.optdict.has_key( '--qsub-id' ):
            assert self.nfree > 0
            self.nfree = 0
        else:
            self.nfree = max( 0, self.nfree - np )
        
        job_info = JobInfo( np )

        pf = self.attrs.get( 'mpifile', '' )
        if pf == 'hostfile':
            # use OpenMPI style machine file
            job_info.mpi_opts = "--hostfile machinefile"
            slots = min( np, self.nprocs )
            job_info.machinefile = \
                        os.uname()[1].strip() + " slots=" + str(slots) + '\n'

        elif pf == 'machinefile':
            # use MPICH style machine file
            job_info.mpi_opts = "-machinefile machinefile"
            job_info.machinefile = ''
            for i in range(np):
                job_info.machinefile += machine + '\n'
        
        mpiopts = self.attrs.get( 'mpiopts', '' )
        if mpiopts:
            job_info.mpi_opts += ' ' + mpiopts

        return job_info
    
    def giveProcs(self, job_info):
        """
        """
        np = job_info.np
        assert np > 0

        if self.optdict.has_key( '--qsub-id' ):
            assert self.nfree == 0
            self.nfree = 1
        else:
            self.nfree = min( self.nprocs, self.nfree + np )
    
    # ----------------------------------------------------------------
    
    def testingDirectory(self):
        """
        """
        if 'TESTING_DIRECTORY' in os.environ:
            return os.environ['TESTING_DIRECTORY']
        
        elif 'testingdir' in self.attrs:
            return self.attrs['testingdir']

        return None
    
    def which(self, prog):
        """
        """
        if not prog:
          return None
        if os.path.isabs(prog):
          return prog
        for d in os.environ['PATH'].split(':'):
          if not d: d = '.'
          if os.path.isdir(d):
            f = os.path.join( d, prog )
            if os.path.exists(f) and \
               os.access(f,os.R_OK) and os.access(f,os.X_OK):
              if not os.path.isabs(f):
                f = os.path.abspath(f)
              return os.path.normpath(f)
        return None


def construct_Platform( toolsdir, optdict, **kwargs ):
    """
    This function constructs a Platform object, determines the platform &
    compiler, and loads the platform plugin.
    """
    assert toolsdir
    assert os.path.exists( toolsdir )
    assert os.path.isdir( toolsdir )
    
    if 'debug' in kwargs:
        print 'construct_Platform A:', toolsdir, optdict

    plat = Platform( toolsdir, optdict )

    # set the platform name and compiler name
    try:
        # this comes from the config directory
        import idplatform
    except ImportError:
        plat.platname = os.uname()[0]
        plat.cplrname = 'gcc'
        if 'debug' in kwargs:
            print 'construct_Platform B:', plat.platname, plat.cplrname
    else:
        if 'debug' in kwargs:
            idplatform.debug = True
        
        plat.platname = None
        if '--plat' in optdict:
            plat.platname = optdict['--plat']
        elif hasattr( idplatform, "platform" ):
            plat.platname = idplatform.platform( optdict )
        if not plat.platname:
            plat.platname = os.uname()[0]

        plat.cplrname = None
        if hasattr( idplatform, "compiler" ):
            plat.cplrname = idplatform.compiler( plat.platname, optdict )
        if not plat.cplrname:
            plat.cplrname = 'gcc'
        
        if 'debug' in kwargs:
            print 'construct_Platform C:', plat.platname, plat.cplrname
            idplatform.debug = False

    platopts = optdict.get( '--platopt', {} )

    q = platopts.get( 'queue', platopts.get( 'q', None ) )
    plat.setattr( 'queue', q )

    act = platopts.get( 'account', platopts.get( 'PT', None ) )
    plat.setattr( 'account', act )

    wall = platopts.get( 'walltime', None )
    plat.setattr( 'walltime', wall )

    try:
        # this comes from the config directory
        import platform_plugin
    except ImportError:
        pass
    except:
        raise
    else:
        plat.plugin = platform_plugin

        if hasattr( platform_plugin, 'initialize' ):
            platform_plugin.initialize( plat )

    plat.initProcs( optdict.get( '-n', None ), optdict.get( '-N', None ) )

    return plat


##########################################################################

class JobInfo:
    """
    This object is used to communicate and hold information for a job
    processor request, including a string to give to the mpirun command, if
    any.  It is returned to the Platform when the job finishes.
    """
    def __init__(self, np):
        self.np = np
        self.mpi_opts = ''


def probe_max_processors():
    """
    Tries to determine the number of processors on the current machine.  On
    Linux systems, it uses /proc/cpuinfo.  On OSX systems, it uses sysctl.
    Returns the max, or None if the probe failed.
    """
    mx = None
    
    if os.uname()[0].startswith( 'Darwin' ):
        # try to use sysctl on Macs
        try:
            fp = os.popen( 'sysctl -n hw.physicalcpu 2>/dev/null' )
            s = fp.read().strip()
            fp.close()
            mx = int(s)
        except:
            mx = None
    
    if mx == None and os.path.exists( '/proc/cpuinfo' ):
        # try to probe the number of available processors by
        # looking at the proc file system
        repat = re.compile( 'processor\s*:' )
        mx = 0
        try:
            fp = open( '/proc/cpuinfo', 'r' )
            for line in fp.readlines():
                if repat.match(line) != None:
                    mx += 1
            fp.close()
        except:
            mx = None

    return mx


##########################################################################

# determine the directory containing the current file

mydir = None
if __name__ == "__main__":
  mydir = os.path.abspath( sys.path[0] )
else:
  mydir = os.path.dirname( os.path.abspath( __file__ ) )


###############################################################################

if __name__ == "__main__":
    """
    """
    toolsdir = os.path.dirname(mydir)
    sys.path.insert( 1, os.path.join( toolsdir, 'config' ) )
    plat = construct_Platform( toolsdir, {} )
    plat.display()
