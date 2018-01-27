#!/usr/bin/env python

import os, sys


def initialize( plat ):
    """
    This function is called to add environment variables and attributes to
    the given Platform object.

    There are a few varieties of batch systems on cluster machines.  For known
    platforms, this function tells vvtest which variety is being used.
    """
    platname = plat.getName()
    opts = plat.getOptions()
    platopts = opts.get( '--platopt', {} )

    if platname == "Cray":
        # XT had 16 cores per node, DoD Excalibur has 32
        plat.setBatchSystem( "pbs", 32, variation="select" )

    elif platname == "CrayXC":

        if 'knl' in platopts:
            plat.setBatchSystem( "slurm", 64, variation='knl' )
        else:
            plat.setBatchSystem( "slurm", 32 )

    elif platname == "TLCC2":
        plat.setBatchSystem( "slurm", 16 )

    elif platname == "CTS1":
        plat.setBatchSystem( "slurm", 36 )

    elif platname == "Godzilla":
        plat.setBatchSystem( "slurm", 20 )
