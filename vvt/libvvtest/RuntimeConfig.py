#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import re
import fnmatch

import FilterExpressions


class RuntimeConfig:
    """
    """
    
    known_attrs = [ \
       'param_expr_list',  # k-format or string expression parameter filter
       'keyword_expr',     # a WordExpression object for keyword filtering
       'option_list',      # list of build options
       'platform_name',    # target platform name
       'ignore_platforms',  # boolean to turn off filtering by platform
       'platform_expr_list',  # k-format or string platform expression
       'search_file_globs',  # file glob patterns used with 'search_patterns'
       'search_patterns',  # list of regex patterns for seaching within files
       'include_tdd',      # if True, tests marked TDD are not excluded
       'include_all',      # boolean to turn off test inclusion filtering
       'runtime_range',    # [ minimum runtime, maximum runtime ]
       'runtime_sum',      # maximum accumulated runtime
    ]
    
    def __init__(self, **kwargs ):
        """
        """
        self.attrs = {}
        
        for k,v in kwargs.items():
          self.setAttr( k, v )
    
    def setAttr(self, name, value):
        """
        Set the value of an attribute name (which must be known).
        """
        assert name in RuntimeConfig.known_attrs
        self.attrs[name] = value
        
        if name in ['platform_name','platform_expr_list']:
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
        """
        """
        return self.getAttr( 'platform_name', None )

    def getOptionList(self):
        ""
        return self.attrs.get( 'option_list', [] )

    def satisfies_keywords(self, keyword_list):
        """
        """
        if 'keyword_expr' in self.attrs:
          expr = self.attrs['keyword_expr']
          return expr.evaluate( keyword_list.count )
        return 1

    def evaluate_parameters(self, paramD):
        pf = self.attrs.get( 'param_filter', None )
        if pf == None: return 1
        return pf.evaluate(paramD)
    
    def _set_platform_expression(self):
        exprL = self.attrs.get( 'platform_expr_list', None )
        pname = self.attrs.get( 'platform_name', None )
        if exprL != None:
          self.attrs['platform_expr'] = FilterExpressions.WordExpression( exprL )
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
    
    def file_search(self, tspec):
        """
        Searches certain test files that are linked or copied in the test for
        regular expression patterns.  Returns true if at least one pattern
        matched in one of the files.  Also returns true if no regular
        expressions were given at construction.
        """
        fnglob = self.attrs.get( 'search_file_globs', None )
        srchpats = self.attrs.get( 'search_patterns', None )
        if fnglob == None or srchpats == None:
          # filter not applied if no file glob patterns or no search patterns
          return 1
        
        # TODO: see if there is a way to avoid passing tpsec in here
        
        varD = { 'NAME':tspec.getName() }
        for k,v in tspec.getParameters().items():
          varD[k] = v
        reL = []
        for p in srchpats:
          reL.append( re.compile(p, re.IGNORECASE | re.MULTILINE) )
        for src,dest in tspec.getLinkFiles()+tspec.getCopyFiles():
          src = expand_variables(src,varD)
          for fn in fnglob:
            xmldir = os.path.join( tspec.getRootpath(), \
                                   os.path.dirname(tspec.getFilepath()) )
            f = os.path.join( xmldir, src )
            if os.path.exists(f) and fnmatch.fnmatch(os.path.basename(src),fn):
              for p in reL:
                try:
                  fp = open(f)
                  s = fp.read()
                  fp.close()
                  if p.search(s):
                    return 1
                except IOError:
                  pass
        
        return 0

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


class PatternStore:
    """Class to store the patterns used by the expand_variables function."""
    curly    = re.compile( '[$][{][^}]*[}]' )
    var      = re.compile( '[$][a-zA-Z][a-zA-Z0-9_]*' )


def expand_variables(s, vardict):
    """
    Expands the given string with values from the dictionary.  It will
    expand ${NAME} and $NAME style variables.
    """
    if s:
      
      # first, substitute from dictionary argument
      
      if len(vardict) > 0:
        
        idx = 0
        while idx < len(s):
          m = PatternStore.curly.search( s, idx )
          if m != None:
            p = m.span()
            varname = s[ p[0]+2 : p[1]-1 ]
            if varname in vardict:
              varval = vardict[varname]
              s = s[:p[0]] + varval + s[p[1]:]
              idx = p[0] + len(varval)
            else:
              idx = p[1]
          else:
            break
    
        idx = 0
        while idx < len(s):
          m = PatternStore.var.search( s, idx )
          if m != None:
            p = m.span()
            varname = s[ p[0]+1 : p[1] ]
            if varname in vardict:
              varval = vardict[varname]
              s = s[:p[0]] + varval + s[p[1]:]
              idx = p[0] + len(varval)
            else:
              idx = p[1]
          else:
            break
    
      # then replace un-expanded variables with empty strings
      
      s = PatternStore.curly.sub('', s)
      s = PatternStore.var.sub('', s)
    
    return s
