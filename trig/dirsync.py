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


helpstr = \
"""
USAGE:
    dirsync.py [OPTIONS] [machine:]from_dir [machine:]to_dir

SYNOPSIS:
    Recursively copy/overwrite/delete files in the 'from_dir' directory to
    the 'to_dir' directory.  Only one directory can specify a machine.  Files
    and directories are deleted on the destination if they no longer exist in
    the source.

    For example,

        dirsync.py path/srcdir sparky:/path/destdir

    will make directory 'destdir' on machine sparky (if it does not already
    exist), and copy srcdir/* to destdir/*.

OPTIONS:
    -h, --help  : this help
"""

############################################################################

def main():

    import getopt
    optL,argL = getopt.getopt( sys.argv[1:], 'h',
                               longopts=['help'] )

    optD ={}
    for n,v in optL:
        if n == '-h' or n == '--help':
            print3( helpstr )
            return
        else:
            optD[n] = v

    if len(argL) != 2:
        print3( '*** dirsync.py: expected exactly two arguments' )
        sys.exit(1)

    sync_directories( argL[0], argL[1] )


class DirSyncError( Exception ):
    pass


def sync_directories( from_dir, to_dir ):
    ""
    srcdir = os.path.normpath( from_dir ) + '/'
    dstdir = os.path.normpath( to_dir )

    runcmd( 'rsync -rlptg --delete '+srcdir+' '+dstdir )


def runcmd( cmd ):
    ""
    po = subprocess.Popen( cmd, shell=True )
    sout,serr = po.communicate()

    if po.returncode != 0:
        raise DirSyncError( 'command failed: '+cmd )


def print3( *args ):
    sys.stdout.write( ' '.join( [ str(arg) for arg in args ] ) + '\n' )
    sys.stdout.flush()


if __name__ == "__main__":
    main()
