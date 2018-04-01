#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import time


"""
This file defines a programmatic interface into batch systems, such as SLURM,
LSF, etc.

The (common) interface to a batch system is through a script file that is
"submitted" to a batch daemon, then the daemon is subsequently queried to
determine the status of the job.

In the abstraction implemented here, the script file is composed like this:

    <header>   : result of calling BatchInterface.writeHeader()
    <commands> : client shell commands go here
    <tail>     : result of calling BatchInterface.writeTail()

Derived classes of BatchInterface fill in the header and tail content with
shell commands that allow submission according to the job specification, and
to allow the job to be monitored and declared finished.
"""


class BatchJob:
    """
    Job specifications are stored in this object, as are the results of
    submitting and running the job.

    Specification names and values are:

        name       : the name of the job
        num nodes  : the requested number of compute nodes
        batch file : the batch script file name to write, submit, and run
        work dir   : the work directory in which to run the batch file
        commands   : bash commands to run (a string, newline separated)
        log file   : stdout and stderr is redirected to this file
        time       : requested time for the allocation
        queue      : the queue/partition to submit the job
        account    : resource account name

    Result names and values are:

        jobid : the job id given back from submission

        submit out : stdout from submission command
        submit err : stderr from submission command

        submit date : date submitted to the queue
        run date    : start date according to the queue
        done date   : date the job completed according to the queue, or the
                      first date it was observed to no longer be in the queue,
                      or the date the job was killed/cancelled
        start date  : script start date according to the log file
        stop date   : script exit date according to the log file

        state : state of the job in the queue; can be
                    absent  : job cannot be found in the queue listing
                    queue   : job is in the queue
                    running : job is in the queue and marked running
                    done    : job is in the queue marked completed, or was
                              previously in the queue but is no longer

        exit  : job exit status; can be
                    success : script ran and completed
                    fail    : script started but failed to complete
                    missing : time expired waiting for the job to show up in
                              the queue, or for the log file to be created
                    killed  : the batch interface was told to kill/cancel the job
    """

    SPEC_NAMES = [ 'name', 'num nodes', 'batch file',
                   'work dir', 'commands', 'log file',
                   'time', 'queue', 'account' ]

    RESULT_NAMES = [ 'jobid', 'submit out', 'submit err', 'submit date',
                     'run date', 'done date', 'start date', 'stop date',
                     'state', 'exit' ]


    def __init__(self):
        ""
        self.specs = {}
        self.results = {}

    def setSpec(self, name, value):
        ""
        self._set_attr( name, value, self.specs, BatchJob.SPEC_NAMES )

    def getSpec(self, name, *default):
        ""
        if len(default) > 0:
            return self.specs.get( name, default[0] )
        return self.specs[name]

    def setResult(self, name, value):
        ""
        self._set_attr( name, value, self.results, BatchJob.RESULT_NAMES )

    def getResult(self, name, *default):
        ""
        if len(default) > 0:
            return self.results.get( name, default[0] )
        return self.results[name]

    def _set_attr(self, name, value, attrs, valid_names):
        """
        Set 'name' to 'value' in the 'attrs' dictionary.  The 'name' must be
        one of the names in 'valid_names', unless it starts with an underscore.
        """
        if not name.startswith('_'):
            if name not in valid_names:
                raise ValueError( 'Invalid name: '+repr(name) )

        if value == None:
            if name in attrs:
                attrs.pop(name)
        else:
            attrs[name] = value


#############################################################################

class BatchInterface:
    """
    Interface for submitting and managing jobs in a batch queue.
    """

    def computeNumNodes(self, num_cores, cores_per_node=None):
        ""
        raise NotImplementedError( "Method computeNumNodes()" )

    def writeBatchFile(self, job):
        ""
        raise NotImplementedError( "Method writeBatchFile()" )

    def submit(self, job):
        """
        """
        raise NotImplementedError( "Method submit()" )

    def poll(self, job_list=None):
        """
        """
        raise NotImplementedError( "Method poll()" )

    def cancel(self, job_list=None):
        ""
        raise NotImplementedError( "Method cancel()" )


#############################################################################

def lineprint( fileobj, *lines ):
    """
    """
    for line in lines:
        fileobj.write( line + '\n' )


def parse_variant( variant_string ):
    """
    Splits the given string of the form

        "key=value key=value ..."

    into a dict and returns it.
    """
    D = {}

    for s in variant_string.strip().split():

        L = s.split('=',1)

        if len(L) == 1:
            D[s] = None
        else:
            D[ L[0] ] = L[1]

    return D


def compute_num_nodes( requested_num_cores,
                       requested_cores_per_node,
                       platform_ppn ):
    """
    Returns minimum number of compute nodes to fit the requested number of
    cores.  If 'requested_num_cores' is less than one, then one is assumed.
    The 'platform_ppn' is used as the number of cores per node unless the
    'requested_cores_per_node' value is non-None.
    """
    if requested_cores_per_node != None:
        ppn = int( requested_cores_per_node )
    else:
        ppn = int( platform_ppn )

    assert ppn > 0

    requested_num_cores = max( 1, int(requested_num_cores) )

    n = int( requested_num_cores / ppn )
    r = int( requested_num_cores % ppn )

    if r == 0:
        return n
    else:
        return n+1


def construct_batch_filename( jobobj ):
    """
    Constructs an absolute filename path for the batch filename, determined
    in this order

        - the "batch file" job spec
        - the job "name" spec with extention ".bat"
        - the name "batchjob_<id>.bat" where <id> is a python id()

    A relative path is relative to the current working directory.
    """
    fn = jobobj.getSpec( 'batch file', None )

    if fn:
        fn = os.path.abspath( fn )

    else:
        name = jobobj.getSpec( 'name', None )
        if name:
            bname = name
        else:
            bname = 'batchjob_'+str(id(jobobj))

        fn = os.path.abspath( bname+'.bat' )

    return fn


def construct_log_filename( jobobj ):
    """
    Constructs an absolute filename path for the log file, determined in
    this order

        - the "log file" job spec
        - the job "name" spec with extension ".log"
        - the name "batchjob_<id>.log" where <id> is a python id()

    Relative paths are always relative to the "batch file" directory.
    """
    fn = jobobj.getSpec( 'log file', None )

    batchf = construct_batch_filename( jobobj )
    batchd = os.path.dirname( batchf )

    if fn:
        if not os.path.isabs( fn ):
            fn = os.path.normpath( os.path.join( batchd, fn ) )

    else:

        name = jobobj.getSpec( 'name', None )
        if name:
            bname = name
        else:
            bname = 'batchjob_'+str(id(jobobj))

        fn = os.path.join( batchd, bname+'.log' )

    return fn


days_of_week = 'sun mon tue wed thu fri sat'.split() + \
    'sunday monday tuesday wednesday thursday friday saturday'.split()
months_of_year = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()
time_zones = 'EST EDT CST CDT MST MDT PST PDT'.split()

def parse_date_string( datestr ):
    """
    """
    tm = None

    try:
        fmt = ''
        val = ''

        L = datestr.split()
        i = 0
        while i < len(L):
            s = L[i]

            if s.lower() in days_of_week:
                pass

            elif s in months_of_year:
                fmt += ' %b'
                val += ' '+s
                i += 1
                s = L[i]
                fmt += ' %d'
                val += ' '+s

            elif s in time_zones:
                fmt += ' %Z'
                val += ' '+s

            elif ':' in s:
                sL = s.split(':')
                if len(sL) == 3:
                    fmt += ' %H:%M:%S'
                    val += ' '+s
                elif len(sL) == 2:
                    fmt += ' %H:%M'
                    val += ' '+s
            else:
                try:
                    yr = int(s)
                    if yr > 1970 and yr < 3000:
                        fmt += ' %Y'
                        val += ' '+s
                except:
                    pass

            i += 1

        if fmt:
            tup = time.strptime( val, fmt )
            tm = time.mktime( tup )

    except:
        pass

    return tm


def seconds_to_colon_separated_time(self, nseconds):
    """
    Formats number of seconds to H:MM:SS with padded zeros for minutes and
    seconds.
    """
    nseconds = int( float(nseconds) + 0.5 )

    nhrs = int( float(nseconds)/3600.0 )
    t = nseconds - nhrs*3600
    nmin = int( float(t)/60.0 )
    nsec = t - nmin*60
    if nsec < 10: nsec = '0' + str(nsec)
    else:         nsec = str(nsec)
    if nmin < 10: nmin = '0' + str(nmin)
    else:         nmin = str(nmin)
    return str(nhrs) + ':' + nmin + ':' + nsec
