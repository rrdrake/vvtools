#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os


class BatchConfiguration:
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
            PLATFORM_QUEUE_CONFIG = "short:ppn=16,maxtime=4h,maxprocs=512,
                                     batch:ppn=16,maxtime=24h,maxprocs=1024"
        - from vvtest command line
            --platform-batch-type=SLURM
            --platform-batch-config="ppn=16,maxtime=4h,maxprocs=512"
            --platform-batch-config="short:ppn=16,maxtime=4h,maxprocs=512"
    """

    def __init__(self):
        ""
        self.batch_type = 'proc'
        self.queue_config = { None : QueueConfiguration(None) }
        self.timeouts = {
                'script' : None,
                'missing' : None,
                'complete' : None,
                'logcheck' : None,
            }

    def getBatchType(self):
        return self.batch_type

    def getProcessorsPerNode(self, queue_name=None):
        ""
        return self.getConfigAttr( queue_name, 'ppn' )

    def getMaxTime(self, queue_name=None):
        ""
        return self.getConfigAttr( queue_name, 'maxtime' )

    def getMaxProcessors(self, queue_name=None):
        ""
        maxcores = self.getConfigAttr( queue_name, 'maxcores' )
        maxnodes = self.getConfigAttr( queue_name, 'maxnodes' )
        return maxcores, maxnodes

    def getTimeout(self, name):
        ""
        return self.timeouts[name]

    def getQueueConfigurations(self, queue_name):
        ""
        default_cfg = self.queue_config[None]
        queue_cfg = self.queue_config.get( queue_name, default_cfg )
        return default_cfg, queue_cfg

    def getConfigAttr(self, queue_name, attr_name):
        ""
        default_cfg, queue_cfg = self.getQueueConfigurations( queue_name )
        val = queue_cfg.getAttr( attr_name, default_cfg.getAttr( attr_name ) )
        return val

    def setBatchType(self, batch_type):
        self.batch_type = batch_type

    def setConfigAttr(self, queue_name=None,
                            ppn=None,
                            maxtime=None,
                            maxcores=None,
                            maxnodes=None):
        ""
        cfg = self.queue_config.get( queue_name, None )

        if cfg == None:
            cfg = QueueConfiguration( queue_name )
            self.queue_config[ queue_name ] = cfg

        if ppn      != None: cfg.setAttr( 'ppn',      ppn      )
        if maxtime  != None: cfg.setAttr( 'maxtime',  maxtime  )
        if maxcores != None: cfg.setAttr( 'maxcores', maxcores )
        if maxnodes != None: cfg.setAttr( 'maxnodes', maxnodes )

    def setTimeout(self, name, value):
        ""
        self.timeouts[name] = value


class QueueConfiguration:

    def __init__(self, name):
        ""
        self.name = name
        self.config = {
            'ppn' : None,
            'maxtime' : None,
            'maxcores' : None,
            'maxnodes' : None,
        }

    def getName(self): return self.name

    def setAttr(self, attr_name, attr_value):
        self.config[ attr_name ] = attr_value

    def getAttr(self, attr_name, *default):
        if len(default) > 0:
            return self.config.get( attr_name, default[0] )
        return self.config[attr_name]

