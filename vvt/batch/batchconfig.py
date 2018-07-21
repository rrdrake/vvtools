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
    This class stores constraints and settings for the batch system.  They
    include

        - The batch type, such as "proc", "lsf", "slurm", etc

        - Queue/partition information.  A default queue is always defined,
          but additional queues may be present and can be queried here.
          Queue information includes

            - processors per node
            - max queue time
            - max cores and max nodes

        - Batch operation timeouts.  These inform underlying algorithms how
          long to wait before giving up on certain events.  They are "script",
          "missing", "complete", and "logcheck".  See BatchInterface.setTimeout()
          for descriptions.
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

    def setConfigAttr(self, attr_name, attr_value, queue_name=None ):
        ""
        cfg = self.queue_config.get( queue_name, None )

        if cfg == None:
            cfg = QueueConfiguration( queue_name )
            self.queue_config[ queue_name ] = cfg

        cfg.setAttr( attr_name, attr_value )

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


def construct_BatchConfiguration( batch_type=None,
                                  queue_config=None,
                                  environ_config=None,
                                  config_path=None ):
    """
    A BatchConfiguration instance is constructed and populated in the following
    order.  If any argument is not given, it is skipped.  Settings are
    overwritten if encountered by more than one specification.

        config_path : a colon separated list of directories is searched for a
                      file called batchconfig_plugin.py and the first one
                      found is read and loaded into the BatchConfiguration

        environ_config : a string containing queue specifications, such as
                            "ppn=16,maxtime=24h,maxprocs=1024,
                             short:ppn=16,maxtime=4h,maxprocs=512,
                             batch: ppn=16,maxtime=24h,maxprocs=1024"

        queue_config : same as environ_config but applied second

        batch_type : batch system type, such as "proc", "slurm", "lsf"
    """
    cfg = BatchConfiguration()

    if config_path:
        load_config_file_from_path( cfg, config_path )

    if environ_config:
        load_config_string( cfg, environ_config )

    if queue_config:
        load_config_string( cfg, queue_config )

    if batch_type:
        cfg.setBatchType( batch_type )

    return cfg


def load_config_file_from_path( batconfig, config_path ):
    ""
    for dp in config_path.split(':'):

        plug = os.path.join( dp, 'batchconfig_plugin.py' )

        if os.path.isfile( plug ) and os.access( plug, os.R_OK ):
            if load_config_from_file( batconfig, plug ):
                break


def load_config_from_file( batconfig, filename ):
    ""
    mod = create_module_from_filename( filename )

    if mod != None and hasattr( mod, 'get_config' ):

        btype,qconfig = mod.get_config()

        if btype != None:
            batconfig.setBatchType( btype )
            load_config_string( batconfig, qconfig )
            return True

    return False


def load_config_string( batconfig, config_string ):
    ""
    for qname,atname,atval in parse_queue_config_string( config_string ):
        if atval.endswith( 'h' ):
            atval = int( atval.rstrip('h') ) * 60*60
        elif atval.endswith( 'hr' ):
            atval = int( atval.rstrip( 'hr' ) ) * 60*60
        else:
            atval = int( atval )
        batconfig.setConfigAttr( atname, atval, queue_name=qname )


def parse_queue_config_string( config_string ):
    """
    Example input strings:
        "ppn=16,maxtime=24h, maxprocs=512"
        "short: ppn=16,maxtime=24h,maxprocs=512"
        "long, ppn=16,maxtime=72h"
    These strings can be concatenated with a comma.
    Returns a list of ( queue name, attr name, attr value ).
    """
    configlist = []
    qname = None

    for chunk in config_string.split(','):
        itemL = chunk.strip().split()
        for item in itemL:
            L = item.split( '=', 1 )
            if len(L) == 2:
                eqname,eqval = L
                L = eqname.split( ':', 1 )
                if len(L) == 2:
                    qname,atname = L
                    qname = qname.strip()
                else:
                    atname = eqname
                configlist.append( ( qname, atname.strip(), eqval.strip() ) )
            else:
                qname = item.strip().rstrip(':')

    return configlist


uniq_id = 0
filename_to_module_map = {}

def create_module_from_filename( fname ):
    ""
    global uniq_id

    fname = os.path.normpath( os.path.abspath( fname ) )

    if fname in filename_to_module_map:

        mod = filename_to_module_map[fname]

    else:

        modname = os.path.splitext(os.path.basename(fname))[0]+str(uniq_id)
        uniq_id += 1

        if sys.version_info[0] < 3 or sys.version_info[1] < 4:
            import imp
            fp = open( fname, 'r' )
            try:
                spec = ('.py','r',imp.PY_SOURCE)
                mod = imp.load_module( modname, fp, fname, spec )
            finally:
                fp.close()
        else:
            import importlib
            import importlib.util as imputil
            spec = imputil.spec_from_file_location( modname, fname )
            mod = imputil.module_from_spec(spec)
            spec.loader.exec_module(mod)

        filename_to_module_map[ fname ] = mod

    return mod
