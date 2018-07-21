#!/usr/bin/env python

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import fnmatch

"""
The following config_table contains a section for each machine/platform, which
always starts with

[machine name]

Follow this with "host_match" to match the current machine to one of the
entries.  For example,

host_match = chama-login*
host_match = mach-login[0-9] mach-login[0-9][0-9]

The matching uses shell style matching (not regular expressions), and multiple
expressions are OR-ed together.

Then define the batch type and each queue configuration.  For example,

batch_type = slurm
queue_config = ppn=16, maxtime=24hr, maxnodes=500,
               short: maxtime=4hr,
               viz: ppn=32, maxtime=8hr, maxnodes=32

The first line in the queue_config is the default queue, followed by named
queues with values that are different from the default.

As a python module, the entry point for this file is the get_config() function.
Run as a script, the batch type and queue config are written to stdout.
"""

config_table = \
"""
### TLCC2

[chama]
host_match = chama-login*
batch_type = slurm
queue_config = string one
               string two
               string three

[uno]
host_match = uno-login*
batch_type = slurm
queue_config = string one
               string two
               string three

[skybridge]
host_match = skybridge-login*
batch_type = slurm
queue_config = string one
               string two
               string three

### CTS-1

[serrano]
host_match = serrano-login*
batch_type = slurm
queue_config = string one
               string two
               string three

[ghost]
host_match = ghost-login*
batch_type = slurm
queue_config = string one
               string two
               string three

###

[doom]
host_match = ?
batch_type = slurm
queue_config = string one
               string two
               string three

"""


class ParseException( Exception ):
    pass


def get_config():
    """
    Returns a pair of strings ( batch type, batch config ).  Or if the current
    machine is unknown or there is more than one configuration match, then
    ( None, None ) is returned.
    """
    cfgD = ini_style_string_to_dict( config_table )

    filter_config_set_by_host_name( cfgD, os.uname()[1] )

    btype, qconfig = determine_batch_type_and_queue_config( cfgD )

    return btype, qconfig


##########################################################################

def get_ip():
    """
    this might be useful as some point

    https://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib
    """
    import socket

    IP = '127.0.0.1'
    sock = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
    try:
        # doesn't have to be reachable
        sock.connect( ('10.255.255.255', 1) )
        IP = sock.getsockname()[0]
    finally:
        sock.close()

    return IP


def determine_batch_type_and_queue_config( cfgD ):
    """
    """
    btype = qcfg = None

    if len(cfgD) == 2:

        for mach,specD in cfgD.items():
            if mach == None: defaultD = specD
            else:            machD = specD

        btype = machD.get( 'batch_type', defaultD.get( 'batch_type', None ) )
        qcfg = machD.get( 'queue_config', defaultD.get( 'queue_config', None ) )

    return btype, qcfg


def filter_config_set_by_host_name( cfgD, hostname ):
    """
    """
    for mach,specD in list( cfgD.items() ):
        if not satisfies_host_match( hostname, specD ):
            cfgD.pop( mach )


def satisfies_host_match( hostname, specD ):
    """
    """
    if 'host_match' in specD:

        match = specD['host_match']

        for pat in match.strip().split():
            if fnmatch.fnmatchcase( hostname, pat ):
                return True

        return False

    else:
        return True


def ini_style_string_to_dict( ini_string ):
    ""
    content = { None:{} }
    section = None
    kvpair = None

    for line in ini_string.split('\n'):
        if line.startswith('['):
            if kvpair:
                content[section][kvpair[0]] = kvpair[1]
                kvpair = None
            section = line.strip().strip('[').strip(']')
            if section not in content:
                content[section] = {}
        else:
            lineL = line.split('=',1)
            if not line.strip() or line.startswith('#'):
                if kvpair:
                    content[section][kvpair[0]] = kvpair[1]
                    kvpair = None
            elif line.startswith(' ') or line.startswith('\t'):
                if kvpair:
                    kvpair[1] = ( kvpair[1] + ' ' + line.lstrip() ).strip()
                else:
                    raise ParseException( 'invalid syntax: '+repr(line) )
            elif len(lineL) == 2:
                if kvpair:
                    content[section][kvpair[0]] = kvpair[1]
                    kvpair = None
                kvpair = [ lineL[0].strip(), lineL[1].strip() ]
            else:
                raise ParseException( 'invalid syntax: '+repr(line) )

    if kvpair:
        content[section][kvpair[0]] = kvpair[1]

    return content


###########################################################################

if __name__ == "__main__":

    btype, qconfig = get_config()
    sys.stdout.write( str(btype) + ' ' + str(qconfig) + '\n' )
    sys.stdout.flush()
