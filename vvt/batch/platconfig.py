#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os


class PlatformConfiguration:
    """
    Machine specific constraints
        - max queue time
        - max num processors, max num nodes
        - processors per node available
        - account required
        - GPUs available
        - queues available

    values are determined by queue name
        - queue name of None means default or same for all queues

    a config is populated
        - from known machine matching (a machine database)
        - from environment variables
            PLATFORM_BATCH_TYPE = SLURM, PBS, LSF, ...
            PLATFORM_BATCH_CONFIG = "ppn=16,maxtime=4h,maxprocs=512"
            PLATFORM_QUEUE_CONFIG = "short:ppn=16,maxtime=4h,maxprocs=512"
        - from vvtest command line
            --platform-batch-type
            --platform-batch-config
            --platform-queue-config
    """

    def __init__(self):
        ""
        self.ppn = None
        self.max_runtime = None

    def getProcessorsPerNode(self, ppn=None, queue=None):
        ""
        if ppn == None:
            return self.ppn
        else:
            return ppn

    def getNumNodes(self, numcores, ppn=None, queue=None):
        ""
        ppn = self.getProcessorsPerNode( ppn, queue )

        if ppn != None:
            return numcores/ppn  # magic: not done

        return None

    def getNumCores(self, numnodes, ppn=None, queue=None):
        ""
        ppn = self.getProcessorsPerNode( ppn, queue )

        if ppn != None:
            return numnodes * ppn

        return None

    def getRuntime(self, runtime, queue_name=None):
        ""
        if self.max_runtime:
            runtime min( runtime, self.max_runtime )

        return runtime

    def getGPUsPerNode(self, queue=None):
        ""
        return 0
