#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os


def construct_batch_interface( batchconfig, interactive=False ):
    ""
    btype = batchconfig.getBatchType().lower()

    if btype == 'proc':

        from batchscripts import BatchScripts
        bat = BatchScripts()

        if interactive:
            bat.setTimeout( 'script', 20 )
            bat.setTimeout( 'logcheck', 4 )

    elif btype == 'slurm':

        from batchSLURM import BatchSLURM
        bat = BatchSLURM()

        if interactive:
            bat.setTimeout( 'script', 30 )
            bat.setTimeout( 'logcheck', 8 )

    else:
        raise Exception( 'Unknown batch type: '+str(batchconfig.getBatchType()) )

    return bat
