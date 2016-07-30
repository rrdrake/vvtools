#!/usr/bin/env python

import os, sys
import time

from runcmd import runcmd

class BatchCrayPBS:
    """
    """

    def __init__(self, ppn, **kwargs):
        """
        """
        if ppn <= 0: ppn = 1
        self.ppn = ppn

    def header(self, np, qtime, workdir, outfile):
        """
        """
        if np <= 0: np = 1
        nnodes = int( np/self.ppn )
        if (np%self.ppn) != 0:
            nnodes += 1
        
        hdr = '#MSUB -l nodes='+str(nnodes)+':ppn='+str(self.ppn)+ \
                      ',walltime='+str(qtime) + '\n' + \
              '#MSUB -j oe' + '\n' + \
              '#MSUB -o '+outfile + '\n' + \
              '#MSUB -d '+workdir + '\n' + \
              'cd '+workdir
        
        return hdr


    def submit(self, fname, workdir, outfile,
                     queue=None, account=None, confirm=False):
        """
        Creates and executes a command to submit the given filename as a batch
        job to the resource manager.  Returns (cmd, out, job id, error message)
        where 'cmd' is the submit command executed, 'out' is the output from
        running the command.  The job id is None if an error occured, and error
        message is a string containing the error.  If successful, job id is an
        integer.

        If 'confirm' is True, the job is submitted then the queue is queried
        until the job id shows up.  If it does not show up in about 20 seconds,
        an error is returned.
        """
        cmdL = ['msub']
        if queue != None: cmdL.extend(['-q',queue])
        if account != None: cmdL.extend(['-A',account])
        cmdL.extend(['-o', outfile])
        cmdL.extend(['-j', 'oe'])
        cmdL.extend(['-N', os.path.basename(fname)])
        cmdL.append(fname)
        cmd = ' '.join( cmdL )
        
        x, out = runcmd( cmdL, workdir )
        
        # output should contain something like the following
        #    12345.ladmin1 or 12345.sdb
        jobid = None
        s = out.strip()
        if s:
            L = s.split()
            if len(L) == 1:
                jobid = s
        
        if jobid == None:
            return cmd, out, None, "batch submission failed or could not parse " + \
                                   "output to obtain the job id"
        
        if confirm:
            time.sleep(1)
            ok = 0
            for i in range(20):
                c,o,e,stateD = self.query([jobid])
                if stateD.get(jobid,''):
                    ok = 1
                    break
                time.sleep(1)
            if not ok:
                return cmd, out, None, "could not confirm that the job entered " + \
                            "the queue after 20 seconds (job id " + str(jobid) + ")"
        
        return cmd, out, jobid, ""

    def query(self, jobidL):
        """
        Determine the state of the given job ids.  Returns (cmd, out, err, stateD)
        where stateD is dictionary mapping the job ids to a string equal to
        'pending', 'running', or '' (empty) and empty means either the job was
        not listed or it was listed but not pending or running.  The err value
        contains an error message if an error occurred when getting the states.
        """
        cmdL = ['showq']
        cmd = ' '.join( cmdL )
        x, out = runcmd(cmdL)
        
        stateD = {}
        for jid in jobidL:
            stateD[jid] = ''  # default to done
        
        err = ''
        for line in out.strip().split( os.linesep ):
            try:
                L = line.split()
                if len(L) >= 4:
                    jid = L[0]
                    st = L[2]
                    if stateD.has_key(jid):
                        if st in ['Running']: st = 'running'
                        elif st in ['Deferred','Idle']: st = 'pending'
                        else: st = ''
                        stateD[jid] = st
            except Exception, e:
                err = "failed to parse squeue output: " + str(e)
        
        return cmd, out, err, stateD

    def HMSformat(self, nseconds):
        """
        Formats 'nseconds' in H:MM:SS format.  If the argument is a string, then
        it checks for a colon.  If it has a colon, the string is untouched.
        Otherwise it assumes seconds and converts to an integer before changing
        to H:MM:SS format.
        """
        if type(nseconds) == type(''):
            if ':' in nseconds:
                return nseconds
        nseconds = int(nseconds)
        nhrs = int( float(nseconds)/3600.0 )
        t = nseconds - nhrs*3600
        nmin = int( float(t)/60.0 )
        nsec = t - nmin*60
        if nsec < 10: nsec = '0' + str(nsec)
        else:         nsec = str(nsec)
        if nmin < 10: nmin = '0' + str(nmin)
        else:         nmin = str(nmin)
        return str(nhrs) + ':' + nmin + ':' + nsec


########################################################################

if __name__ == "__main__":
    
    bat = BatchCrayPBS()

    fp = open('tmp.sub','w')
    fp.write( '#!/bin/csh -f'+os.linesep )
    fp.write( bat.make_batch_header( 1, 16, 65, os.getcwd(), 'tmp.out' ) )
    fp.write( os.linesep + os.linesep + \
              'echo running tmp.sub job script' + os.linesep + \
              'sleep 5' + os.linesep )
    fp.close()
    cmd, out, jobid, err = bat.submit( 'tmp.sub', os.getcwd(), 'tmp.out', confirm=1 )
    print cmd
    print out
    print 'jobid', jobid
    if err:
        print 'error:', err
    time.sleep(2)
    while 1:
        cmd, out, err, stateD = bat.query([jobid])
        if err:
            print cmd
            print out
            print err
        print "state", stateD[jobid]
        if not stateD[jobid]:
            break
        time.sleep(1)
