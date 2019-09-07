#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os

from . import FilterExpressions


class RuntimeConfig:

    known_attrs = [ \
       'param_expr_list',   # k-format or string expression parameter filter
       'keyword_expr',      # a WordExpression object for keyword filtering
       'option_list',       # list of build options
       'platform_name',     # target platform name
       'ignore_platforms',  # boolean to turn off filtering by platform
       'set_platform_expr', # platform expression
       'search_file_globs', # file glob patterns used with 'search_regexes'
       'search_regexes',    # list of regexes for seaching within files
       'include_tdd',       # if True, tests marked TDD are not excluded
       'include_all',       # boolean to turn off test inclusion filtering
       'runtime_range',     # [ minimum runtime, maximum runtime ]
       'runtime_sum',       # maximum accumulated runtime
       'maxprocs',          # maximum number of processors, np
    ]

    defaults = { \
        'vvtestdir'  : None,  # the top level vvtest directory
        'configdir'  : None,  # the configuration directory
        'exepath'    : None,  # the path to the executables
        'onopts'     : [],
        'offopts'    : [],
        'refresh'    : 1,
        'postclean'  : 0,
        'timeout'    : None,
        'multiplier' : 1.0,
        'preclean'   : 1,
        'analyze'    : 0,
        'logfile'    : 1,
        'testargs'   : [],
    }

    def __init__(self, **kwargs ):
        """
        """
        self.attrs = {}

        for n,v in RuntimeConfig.defaults.items():
            self.setAttr( n, v )

        for k,v in kwargs.items():
            self.setAttr( k, v )

    def setAttr(self, name, value):
        """
        Set the value of an attribute name (which must be known).
        """
        self.attrs[name] = value

        if name in ['platform_name','set_platform_expr']:
            self._set_platform_expression()
        elif name == 'param_expr_list':
            self.attrs['param_filter'] = FilterExpressions.ParamFilter( value )

    def getAttr(self, name, *default):
        """
        Get the value of an attribute name.  A default value can be given
        and will be returned when the attribute name is not set.
        """
        if len(default) == 0:
            return self.attrs[name]
        return self.attrs.get( name, default[0] )

    def platformName(self):
        ""
        return self.getAttr( 'platform_name', None )

    def getOptionList(self):
        ""
        return self.attrs.get( 'option_list', [] )

    def addResultsKeywordExpression(self, add_expr):
        ""
        expr = self.attrs['keyword_expr']
        if not expr.containsResultsKeywords():
            expr.append( add_expr, 'and' )

    def satisfies_keywords(self, keyword_list, include_results=True):
        ""
        if 'keyword_expr' in self.attrs:
            expr = self.attrs['keyword_expr']
            return expr.evaluate( keyword_list.count, include_results )
        return True

    def evaluate_parameters(self, paramD):
        ""
        pf = self.attrs.get( 'param_filter', None )
        if pf == None: return 1
        return pf.evaluate(paramD)

    def _set_platform_expression(self):
        pexpr = self.attrs.get( 'set_platform_expr', None )
        pname = self.attrs.get( 'platform_name', None )
        if pexpr != None:
            self.attrs['platform_expr'] = pexpr
        elif pname != None:
            self.attrs['platform_expr'] = FilterExpressions.WordExpression( pname )
        else:
            self.attrs['platform_expr'] = FilterExpressions.WordExpression()

    def evaluate_platform_include(self, platform_test_func):
        """
        Evaluate the command line platform expression using the given function
        to test each platform name.  That is, the 'platform_test_func' is given
        a platform name and is expected to return true if the test would run
        on that platform.
        """
        ip = self.attrs.get( 'ignore_platforms', 0 )
        if ip: return 1

        # if the current platform was not given, no filtering by platform
        # is performed
        pn = self.attrs.get('platform_name',None)
        if not pn: return 1

        platexpr = self.attrs['platform_expr']

        # to evaluate the command line expression, each platform name in the
        # expression is evaluated using the given 'platform_test_func'
        return platexpr.evaluate( platform_test_func )

    def evaluate_option_expr(self, expr):
        """
        Evaluate the given expression against the list of command line options.
        """
        #x = FilterExpressions.WordExpression(expr)
        opL = self.attrs.get( 'option_list', [] )
        return expr.evaluate( opL.count )

    def evaluate_runtime(self, test_runtime):
        """
        If a runtime range is specified in this object, the given runtime is
        evaluated against that range.  False is returned only if the given
        runtime is outside the specified range.
        """
        mn,mx = self.attrs.get( 'runtime_range', [None,None] )
        if mn != None and test_runtime < mn:
            return False
        if mx != None and test_runtime > mx:
            return False

        return True

    def evaluate_maxprocs(self, test_np):
        ""
        maxprocs = self.attrs.get( 'maxprocs', None )

        if maxprocs != None and test_np > maxprocs:
            return False

        return True
