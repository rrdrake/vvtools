#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import time
import glob
import shlex
import getopt

from scriptrunner import ScriptRunner


class FakeSLURM:

    def __init__(self):
        ""
        self.scrun = ScriptRunner()
        self.jobs = []

    def runcmd(self, cmd):
        ""
        self.scrun.poll()

        argv = shlex.split( cmd )

        prog = os.path.basename(argv[0])
        if prog == 'sbatch':
            rtn = self.run_sbatch_command( argv )
        elif prog == 'squeue':
            rtn = self.run_squeue_command( argv )
        else:
            raise NotImplementedError( 'unexpected program: "'+prog+'"' )

        self.scrun.poll()

        return rtn

    def run_sbatch_command(self, argv):
        ""
        optL,argL = getopt( argv[1:], '', [] )
        if len(argL) != 1:
            raise ValueError( 'expected exactly one argument' )

        optD = parse_sbatch_options( argL[0] )

        logf = optD['--output']  # required
        tm = optD.get( '--time', None )

        proc = self.scrun.submit( argL[0], redirect=logf, timeout=tm )

        out = 'Submitted batch job '+str(proc.getId())

        submit_time = time.time()
        self.jobs.append( [ proc, submit_time ] )

        return 0,out,''

    def run_squeue_command(self, argv):
        ""
        optL,argL = getopt( argv[1:], 'o:', ['noheader'] )

        if len(argL) != 0:
            raise ValueError( 'unexpected argument: '+str(argL) )

        nohdr = False
        fmt = None

        for n,v in optL:
            if n == '-o':
                fmt = v
            elif n == '--noheader':
                nohdr = True

        if not nohdr:
            raise ValueError( 'expected --noheader option' )

        if fmt == None:
            raise ValueError( 'expected a -o option' )

        if fmt != '%i _ %t _ %V _ %S _ %M':
            raise ValueError( 'this mock only knows one -o format,' + \
                ' which is not "'+str(fmt)+'"' )

        out = ''

        for job, submit_time in self.jobs:
            st,x = job.getStatus()
            if not st:
                out += pending_job_line( job, submit_time ) + '\n'
            elif st == 'running':
                out += running_job_line( job, submit_time ) + '\n'
            elif x != None:
                out += completed_job_line( job, submit_time ) + '\n'

        return 0,out,''


def parse_sbatch_options( batchfile ):
    ""
    optD = {}

    fp = open( batchfile, 'r' )
    try:

        line = fp.readline()
        while line:

            line = line.strip()

            if line.startswith( '#' ):
                if line.startswith( '#SBATCH ' ):
                    optstr = line.split( '#SBATCH ', 1 )[1]
                    kvL = optstr.split( '=', 1 )
                    if len(kvL) != 2:
                        raise ValueError( 'expected <option>=<value> ' + \
                                'format, but got "'+optstr+'"' )
                    k,v = kvL
                    if not k.strip():
                        raise ValueError( 'option name empty: "'+optstr+'"' )

                    optD[k] = v

            elif line:
                break

            line = fp.readline()

    finally:
        fp.close()

    return optD


def pending_job_line( job, submit_time ):
    ""
    line = str( job.getId() )  # job id
    line += ' _ PD'            # job is pending
    line += ' _ '+format_date( submit_time )  # date job was submitted
    line += ' _ N/A'
    line += ' _ 0:00'

    return line


def running_job_line( job, submit_time ):
    ""
    t0,t1 = job.getDates()
    assert t0

    line = str( job.getId() )  # job id
    line += ' _ R'             # job is running
    line += ' _ '+format_date( submit_time )  # date job was submitted
    line += ' _ '+format_date( t0 )           # date job started
    line += ' _ '+format_elapsed_time( time.time()-t0 )  # time used by job

    return line


def completed_job_line( job, submit_time ):
    ""
    t0,t1 = job.getDates()
    assert t0 and t1

    line = str( job.getId() )  # job id
    line += ' _ CD'            # job is completed
    line += ' _ '+format_date( submit_time )    # date job was submitted
    line += ' _ '+format_date( t0 )             # date job started
    line += ' _ '+format_elapsed_time( t1-t0 )  # time used by job

    return line


def format_date( epoch_time ):
    """
    Turns an epoch time into a string like 2018-04-20T22:20:30.
    """
    return time.strftime( "%Y-%m-%dT%H:%M:%S", time.localtime(epoch_time) )


def format_elapsed_time( seconds ):
    """
    Turns an integer num seconds into a string like 11:27 or 21:42:39 or
    1-20:21:50.
    """
    seconds = int(seconds)

    sc = seconds % 60
    mn = ( (seconds-sc) % (60*60) ) // 60
    hr = ( (seconds-sc-mn) % (24*60*60) ) // (60*60)
    dy = (seconds-sc-mn-hr) // (24*60*60)

    s = ''

    if dy > 0: s += str(dy)

    if s:        s += '-%02d'%hr
    elif hr > 0: s += str(hr)

    if s: s += ':%02d'%mn
    else: s += str(mn)

    s += ':%02d'%sc

    return s
