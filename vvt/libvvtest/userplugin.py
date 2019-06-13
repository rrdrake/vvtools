#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys

from .outpututils import capture_traceback


class UserPluginError( Exception ):
    pass


class UserPluginBridge:

    def __init__(self, rtconfig, plugin_module):
        ""
        self.rtconfig = rtconfig
        self.plugin = plugin_module

        self._probe_for_functions()

        # avoid flooding output if the user plugin has an error (which
        # raises an exception) by only printing the traceback once for
        # each exception string
        self.exc_uniq = set()

    def validateTest(self, tcase):
        """
        Returns non-empty string (an explanation) if user validation fails.
        """
        rtn = None
        if self.validate != None:
            specs = self._make_test_to_user_interface_dict( tcase )
            try:
                rtn = self.validate( specs )
            except Exception:
                xs,tb = capture_traceback( sys.exc_info() )
                self._check_print_exc( xs, tb )
                rtn = xs.strip().replace( '\n', ' ' )[:160]

        return rtn

    def testTimeout(self, tcase):
        """
        Returns None for no change or an integer value.
        """
        rtn = None
        if self.timeout != None:
            specs = self._make_test_to_user_interface_dict( tcase )
            try:
                rtn = self.timeout( specs )
                if rtn != None:
                    rtn = max( 0, int(rtn) )
            except Exception:
                xs,tb = capture_traceback( sys.exc_info() )
                self._check_print_exc( xs, tb )
                rtn = None

        return rtn

    def testPreload(self, tcase):
        """
        May modify os.environ and return value is either None/empty or
        a string containing the python to use.
        """
        pyexe = None

        if self.preload != None:
            specs = self._make_test_to_user_interface_dict( tcase )
            try:
                label = tcase.getSpec().getPreloadLabel()
                if label:
                    specs['preload'] = label
                pyexe = self.preload( specs )
            except Exception:
                xs,tb = capture_traceback( sys.exc_info() )
                sys.stdout.write( '\n' + tb + '\n' )
                pyexe = None

        return pyexe

    def _probe_for_functions(self):
        ""
        self.validate = None
        if self.plugin and hasattr( self.plugin, 'validate_test' ):
            self.validate = self.plugin.validate_test

        self.timeout = None
        if self.plugin and hasattr( self.plugin, 'test_timeout' ):
            self.timeout = self.plugin.test_timeout

        self.preload = None
        if self.plugin and hasattr( self.plugin, 'test_preload' ):
            self.preload = self.plugin.test_preload

    def _check_print_exc(self, xs, tb):
        ""
        if xs not in self.exc_uniq:
            sys.stdout.write( '\n' + tb + '\n' )
            self.exc_uniq.add( xs )

    def _make_test_to_user_interface_dict(self, tcase):
        ""
        tspec = tcase.getSpec()

        specs = { 'name'       : tspec.getName(),
                  'keywords'   : tspec.getKeywords( include_implicit=False ),
                  'parameters' : tspec.getParameters(),
                  'timeout'    : tspec.getTimeout(),
                  'platform'   : self.rtconfig.platformName(),
                  'options'    : self.rtconfig.getOptionList() }
        return specs


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
