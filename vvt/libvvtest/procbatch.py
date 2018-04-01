#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time

from runcmd import runcmd

class ProcessBatch:

    def __init__(self, ppn):
        if ppn <= 0: ppn = 1
        self.ppn = ppn
        self.childids = []

    def header(self, np, qtime, workdir, outfile):
        """
        """
        hdr = '\n' + \
              'cd '+workdir + ' || exit 1\n'
        
        return hdr

    def submit(self, fname, workdir, outfile,
                     queue=None, account=None, confirm=False):
        """
        Executes the script 'fname' as a background process.
        Returns (cmd, out, job id, error message) where 'cmd' is
        (approximately) the fork command and 'out' is a little informational
        message.  The job id is None if an error occured, and error
        message is a string containing the error.  If successful, job id is an
        integer.
        """
        sys.stdout.flush()
        sys.stderr.flush()
        
        jobid = os.fork()
        
        if jobid == 0:
            os.chdir(workdir)
            fpout = open( outfile, 'wb' )
            os.dup2( fpout.fileno(), sys.stdout.fileno() )
            os.dup2( fpout.fileno(), sys.stderr.fileno() )
            os.execv( '/bin/csh', ['/bin/csh', '-f', fname] )
        
        cmd = '/bin/csh -f ' + fname + ' >& ' + outfile
        out = '[forked process '+str(jobid)+']'

        # keep the child process ids as the queue ids
        self.childids.append( jobid )

        return cmd, out, jobid, ''

    def query(self, jobidL):
        """
        Determine the state of the given job ids.  Returns (cmd, out, err, stateD)
        where stateD is dictionary mapping the job ids to a string equal to
        'pending', 'running', or '' (empty) and empty means either the job was
        not listed or it was listed but not pending or running.  The err value
        contains an error message if an error occurred when getting the states.
        """
        doneL = []
        jobD = {}
        for jobid in jobidL:
            if jobid in self.childids:
                cpid,xcode = os.waitpid( jobid, os.WNOHANG )
                if cpid > 0:
                    # child finished; empty string means done
                    jobD[jobid] = ''
                    doneL.append( jobid )
                else:
                    jobD[jobid] = 'running'
            else:
                jobD[jobid] = ''

        for jobid in doneL:
            self.childids.remove( jobid )

        out = ' '.join( [ str(jid) for jid in jobidL ] )
        return 'ps', out, '', jobD


#########################################################################

if __name__ == "__main__":
    pass
