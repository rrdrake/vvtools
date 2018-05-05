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
from getopt import getopt

from scriptrunner import ScriptRunner
from batchSLURM import parse_elapsed_time_string

# magic: TODO:
#   - have the partition and account added to the jobs list
#       - this is so tests can check that they were set


class FakeSLURM:

    def __init__(self):
        ""
        self.scrun = ScriptRunner()
        self.jobs = []

    def runcmd(self, cmd):
        """
        This is the entry point for faking the SLURM behavior.  Instead of
        calling "sbatch" and "squeue", it parses the command line options and
        uses ScriptRunner to execute the job scripts.
        """
        self.scrun.poll()

        argv = shlex.split( cmd )
        prog = os.path.basename(argv[0])

        if prog == 'sbatch':
            rtn = self.run_sbatch_command( argv[1:] )

        elif prog == 'squeue':
            rtn = self.run_squeue_command( argv[1:] )

        else:
            raise NotImplementedError( 'unexpected program: "'+prog+'"' )

        self.scrun.poll()

        return rtn

    def run_sbatch_command(self, cmd_opts):
        ""
        optL,argL = parse_sbatch_command_options( cmd_opts )
        scriptname = argL[0]

        logf, runtime = parse_sbatch_script_file( scriptname )

        proc = self.scrun.submit( scriptname, redirect=logf, timeout=runtime )

        out = 'Submitted batch job '+str(proc.getId())

        submit_time = time.time()
        self.jobs.append( [ proc, submit_time ] )

        return 0,out,''

    def run_squeue_command(self, cmd_opts):
        ""
        parse_squeue_command_options( cmd_opts )

        out = ''
        for job, submit_time in self.jobs:
            out += squeue_line_from_runner_status( job.getId(),
                                                   job.getStatus(),
                                                   submit_time,
                                                   job.getDates() )
            out += '\n'

        return 0,out,''


def parse_sbatch_command_options( cmd_opts ):
    ""
    optL,argL = getopt( cmd_opts, '', [] )

    if len(argL) != 1:
        raise ValueError( 'expected exactly one argument' )

    return optL, argL


def parse_sbatch_script_file( batchfile ):
    ""
    optD = parse_sbatch_file_options_into_dictionary( batchfile )

    if '--output' not in optD:
        raise Exception( 'expected --output option to be in sbatch script' )

    logf = optD['--output']

    if not logf:
        raise Exception( 'expected --output option to be non-empty' )

    runtime = optD.get( '--time', None )

    if runtime != None:
        val = parse_elapsed_time_string( runtime )
        if val == None:
            raise Exception( 'invalid --time value: '+str(runtime) )
        runtime = val

    return logf, runtime


def parse_sbatch_file_options_into_dictionary( batchfile ):
    ""
    optD = {}

    fp = open( batchfile, 'r' )
    try:

        line = fp.readline()
        while line:

            line = line.strip()

            if line.startswith( '#' ):
                if line.startswith( '#SBATCH' ):
                    opt,val = parse_sbatch_option_line( line )
                    optD[opt] = val

            elif line:
                break

            line = fp.readline()

    finally:
        fp.close()

    return optD


def parse_sbatch_option_line( line ):
    ""
    optstr = line.split( '#SBATCH ', 1 )[1]

    kvL = optstr.split( '=', 1 )
    if len(kvL) != 2:
        raise ValueError( 'expected <option>=<value> ' + \
                'format, but got "'+optstr+'"' )

    k,v = kvL
    if not k.strip():
        raise ValueError( 'option name empty: "'+optstr+'"' )

    return k,v


def parse_squeue_command_options( cmd_opts ):
    ""
    optL,argL = getopt( cmd_opts, 'o:', ['noheader'] )

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
        raise ValueError( 'unexpected -o format value: '+str(fmt) )


def squeue_line_from_runner_status( jobid, stat_exit, subtime, start_stop ):
    ""
    line = str( jobid )

    st,x = stat_exit
    starttime,stoptime = start_stop

    if not st:
        line += ' _ PD'
    elif st == 'running':
        line += ' _ R'
    elif x != None:
        line += ' _ CD'

    line += ' _ '+format_date( subtime )

    if starttime:
        line += ' _ '+format_date( starttime )
    else:
        line += ' _ N/A'

    if starttime and stoptime:
        line += ' _ '+format_elapsed_time( stoptime-starttime )
    else:
        line += ' _ 0:00'

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
