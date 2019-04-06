#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys

from .outpututils import capture_traceback


class UserPluginError( Exception ):
    pass


class UserPluginBridge:

    def __init__(self, plugin_module):
        ""
        self.plugin = plugin_module

    def hasValidateFunction(self):
        ""
        return self.plugin and hasattr( self.plugin, 'validate_test' )

    def validateTest(self, tspec):
        ""
        rtn = None
        if self.hasValidateFunction():
            specs = { 'keywords' : tspec.getKeywords() }
            rtn = self.plugin.validate_test( specs )

        return rtn


def import_module_by_name( modulename ):
    ""
    mod = None

    try:
        code = compile( 'import '+modulename+' as newmodule',
                        '<string>', 'exec' )
        eval( code, globals() )
        mod = newmodule

    except ImportError:
        pass

    except Exception:
        xs,tb = capture_traceback( sys.exc_info() )
        sys.stdout.write( '\n' + tb + '\n' )
        raise UserPluginError( 'failed to import '+modulename+': '+xs )

    return mod
