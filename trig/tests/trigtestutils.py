#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import time
import subprocess
import unittest

import testutils as util

testsrcdir = os.path.dirname( os.path.abspath( sys.argv[0] ) )
sys.path.insert( 0, os.path.dirname( testsrcdir ) )


def get_process_list():
    """
    Return a python list of all processes on the current machine, where each
    entry is a length three list of form

        [ user, pid, ppid ]
    """
    plat = sys.platform.lower()
    if plat.startswith( 'darwin' ):
        cmd = 'ps -o user,pid,ppid'
    else:
        cmd = 'ps -o user,pid,ppid'
    cmd += ' -e'

    p = subprocess.Popen( 'ps -o user,pid,ppid -e',
                          shell=True, stdout=subprocess.PIPE )
    sout,serr = p.communicate()

    sout = util._STRING_(sout)

    # strip off first non-empty line (the header)

    first = True
    lineL = []
    for line in sout.split( os.linesep ):
        line = line.strip()
        if line:
            if first:
                first = False
            else:
                L = line.split()
                if len(L) == 3:
                    try:
                        L[1] = int(L[1])
                        L[2] = int(L[2])
                    except Exception:
                        pass
                    else:
                        lineL.append( L )

    return lineL


def find_process_in_list( proclist, pid ):
    """
    Searches for the given 'pid' in 'proclist' (which should be the output
    from get_process_list().  If not found, None is returned.  Otherwise a
    list

        [ user, pid, ppid ]
    """
    for L in proclist:
        if pid == L[1]:
            return L
    return None
