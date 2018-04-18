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

Defined here is an abstract interface, called BatchInterface.  Derived classes
interact with a given batch system by submitting script files and querying
their status using shell commands.

A job script file is composed like this:

    <header>   : batch system directives, and startup shell commands
    <commands> : job shell commands
    <tail>     : informational job completion shell commands
"""



#############################################################################

class BatchInterface:

    def __init__(self):
        ""
        self.attrs = {}

    def setAttr(self, name, value):
        ""
        self.attrs[ name ] = value

    def getAttr(self, name, *default):
        ""
        if len(default) > 0:
            return self.attrs.get( name, default[0] )
        return self.attrs[ name ]

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

    def poll(self):
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


class AutoPoller:
    """
    """

    def __init__(self, poll_function, poll_interval):
        ""
        assert poll_interval > 0

        self.pollfunc = poll_function
        self.ipoll = poll_interval

        self.stop_event = threading.Event()

        self.thr = threading.Thread( target=self.pollLoop )
        self.thr.daemon = True
        self.thr.start()

    def stop(self):
        ""
        self.stop_event.set()
        self.thr.join()

    def pollLoop(self):
        ""
        tstart = time.time()

        while True:

            if self.isStopped():
                break

            if time.time() - tstart > self.ipoll:
                self.pollfunc()
                tstart = time.time()

            time.sleep(1)

    def isStopped(self):
        ""
        if hasattr( self.stop_event, 'is_set' ):
            stopped = self.stop_event.is_set()
        else:
            stopped = self.stop_event.isSet()

        return stopped

