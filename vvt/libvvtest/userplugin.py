#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys


class UserPluginError:
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
    try:
        code = compile( 'import '+modulename+' as newmodule', 'string', 'exec' )
        eval( code, globals() )
        return newmodule

    except Exception:
        pass

    return None
