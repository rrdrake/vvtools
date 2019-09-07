#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import re
import fnmatch


class TestFilter:

    def __init__(self, rtconfig, user_plugin):
        ""
        self.rtconfig = rtconfig
        self.plugin = user_plugin

    def checkSubdirectory(self, tcase, subdir):
        ""
        ok = True

        tspec = tcase.getSpec()
        xdir = tspec.getExecuteDirectory()
        if subdir and subdir != xdir and not is_subdir( subdir, xdir ):
            ok = False
            tcase.getStat().markSkipBySubdirectoryFilter()

        return ok

    def checkEnabled(self, tcase):
        ""
        tspec = tcase.getSpec()
        ok = tspec.isEnabled()
        if not ok:
            tcase.getStat().markSkipByEnabled()
        return ok

    def checkPlatform(self, tcase):
        ""
        tspec = tcase.getSpec()

        pev = PlatformEvaluator( tspec.getPlatformEnableExpressions() )
        ok = self.rtconfig.evaluate_platform_include( pev.satisfies_platform )
        if not ok:
            tcase.getStat().markSkipByPlatform()
        return ok

    def checkOptions(self, tcase):
        ""
        ok = True

        tspec = tcase.getSpec()
        for opexpr in tspec.getOptionEnableExpressions():
            if not self.rtconfig.evaluate_option_expr( opexpr ):
                ok = False
                break
        if not ok:
            tcase.getStat().markSkipByOption()
        return ok

    def checkKeywords(self, tcase, results_keywords=True):
        ""
        tspec = tcase.getSpec()

        kwlist = tspec.getKeywords() + tcase.getStat().getResultsKeywords()

        if results_keywords:
            ok = self.rtconfig.satisfies_keywords( kwlist, True )
            if not ok:
                nr_ok = self.rtconfig.satisfies_keywords( kwlist, False )
                if nr_ok:
                    # only mark failed by results keywords if including
                    # results keywords is what causes it to fail
                    tcase.getStat().markSkipByKeyword( with_results=True )
                else:
                    tcase.getStat().markSkipByKeyword( with_results=False )

        else:
            ok = self.rtconfig.satisfies_keywords( kwlist, False )
            if not ok:
                tcase.getStat().markSkipByKeyword( with_results=False )

        return ok

    def checkTDD(self, tcase):
        ""
        tspec = tcase.getSpec()

        if self.rtconfig.getAttr( 'include_tdd', False ):
            ok = True
        else:
            ok = ( 'TDD' not in tspec.getKeywords() )
        if not ok:
            tcase.getStat().markSkipByTDD()
        return ok

    def checkParameters(self, tcase, permanent=True):
        ""
        tspec = tcase.getSpec()

        if tspec.isAnalyze():
            # analyze tests are not excluded by parameter expressions
            ok = True
        else:
            ok = self.rtconfig.evaluate_parameters( tspec.getParameters() )

        if not ok:
            tcase.getStat().markSkipByParameter( permanent=permanent )

        return ok

    def checkFileSearch(self, tcase):
        ""
        tspec = tcase.getSpec()

        regexL = self.rtconfig.getAttr( 'search_regexes', None )
        globL = self.rtconfig.getAttr( 'search_file_globs', None )

        ok = file_search( tspec, regexL, globL )
        if not ok:
            tcase.getStat().markSkipByFileSearch()

        return ok

    def checkMaxProcessors(self, tcase):
        ""
        tspec = tcase.getSpec()

        np = int( tspec.getParameters().get( 'np', 1 ) )
        ok = self.rtconfig.evaluate_maxprocs( np )
        if not ok:
            tcase.getStat().markSkipByMaxProcessors()

        return ok

    def checkRuntime(self, tcase):
        ""
        ok = True

        tm = tcase.getStat().getRuntime( None )
        if tm != None and not self.rtconfig.evaluate_runtime( tm ):
            ok = False
        if not ok:
            tcase.getStat().markSkipByRuntime()

        return ok

    def userValidation(self, tcase):
        ""
        ok = True

        reason = self.plugin.validateTest( tcase )
        if reason:
            ok = False
            reason = 'validate: '+reason
            tcase.getStat().markSkipByUserValidation( reason )

        return ok

    def applyPermanent(self, tcase_map):
        ""
        for tcase in tcase_map.values():

            self.checkParameters( tcase, permanent=True ) and \
                self.checkKeywords( tcase, results_keywords=False ) and \
                self.checkEnabled( tcase ) and \
                self.checkPlatform( tcase ) and \
                self.checkOptions( tcase ) and \
                self.checkTDD( tcase ) and \
                self.checkFileSearch( tcase ) and \
                self.checkMaxProcessors( tcase ) and \
                self.checkRuntime( tcase ) and \
                self.userValidation( tcase )

        self.filterByCummulativeRuntime( tcase_map )

    def applyRuntime(self, tcase_map, filter_dir):
        ""
        include_all = self.rtconfig.getAttr( 'include_all', False )

        if not include_all:

            subdir = clean_up_filter_directory( filter_dir )

            for tcase in tcase_map.values():

                tspec = tcase.getSpec()

                if not tcase.getStat().skipTest():

                    self.checkSubdirectory( tcase, subdir ) and \
                        self.checkKeywords( tcase, results_keywords=True ) and \
                        self.checkParameters( tcase, permanent=False ) and \
                        self.checkTDD( tcase ) and \
                        self.checkMaxProcessors( tcase ) and \
                        self.checkRuntime( tcase )

                    # these don't work in restart mode
                    #   self.checkFileSearch( tcase )
                    #   self.checkEnabled( tcase )
                    #   self.checkPlatform( tcase )
                    #   self.checkOptions( tcase )
                    #   self.userValidation( tcase )
                    # although checkPlatform() & checkOptions() is because
                    # those expressions can affect the tests that are created

            self.filterByCummulativeRuntime( tcase_map )

    def filterByCummulativeRuntime(self, tcase_map):
        ""
        rtsum = self.rtconfig.getAttr( 'runtime_sum', None )
        if rtsum != None:

            # first, generate list with times
            tL = []
            for tcase in tcase_map.values():
                tm = tcase.getStat().getRuntime( None )
                if tm == None: tm = 0
                xdir = tcase.getSpec().getDisplayString()
                tL.append( (tm,xdir,tcase) )
            tL.sort()

            # accumulate tests until allowed runtime is exceeded
            tsum = 0.
            i = 0 ; n = len(tL)
            while i < n:
                tm,xdir,tcase = tL[i]
                if not tcase.getStat().skipTest():
                    tsum += tm
                    if tsum > rtsum:
                        tcase.getStat().markSkipByCummulativeRuntime()

                i += 1


def clean_up_filter_directory( filter_dir ):
    ""
    subdir = None

    if filter_dir != None:
        subdir = os.path.normpath( filter_dir )
        if subdir == '' or subdir == '.':
            subdir = None

    return subdir


class PlatformEvaluator:
    """
    Tests can use platform expressions to enable/disable the test.  This class
    caches the expressions and provides a function that answers the question

        "Would the test run on the given platform name?"
    """
    def __init__(self, list_of_word_expr):
        self.exprL = list_of_word_expr

    def satisfies_platform(self, plat_name):
        ""
        for wx in self.exprL:
            if not wx.evaluate( lambda tok: tok == plat_name ):
                return False
        return True


def is_subdir(parent_dir, subdir):
    """
    TODO: test for relative paths
    """
    lp = len(parent_dir)
    ls = len(subdir)
    if ls > lp and parent_dir + '/' == subdir[0:lp+1]:
      return subdir[lp+1:]
    return None


def file_search( tspec, regex_patterns, file_globs ):
    """
    Searches certain test files that are linked or copied in the test for
    regular expression patterns.  Returns true if at least one pattern
    matched in one of the files.  Also returns true if no regular
    expressions were given at construction.
    """
    if regex_patterns == None or len(regex_patterns) == 0:
        return True

    if file_globs == None:
        # filter not applied if no file glob patterns
        return True

    varD = { 'NAME':tspec.getName() }
    for k,v in tspec.getParameters().items():
        varD[k] = v
    for src,dest in tspec.getLinkFiles()+tspec.getCopyFiles():
        src = expand_variables(src,varD)
        for fn in file_globs:
            xmldir = os.path.join( tspec.getRootpath(), \
                                   os.path.dirname(tspec.getFilepath()) )
            f = os.path.join( xmldir, src )
            if os.path.exists(f) and fnmatch.fnmatch(os.path.basename(src),fn):
                for p in regex_patterns:
                    try:
                        fp = open(f)
                        s = fp.read()
                        fp.close()
                        if p.search(s):
                            return True
                    except IOError:
                        pass

    return False


curly_pat = re.compile( '[$][{][^}]*[}]' )
var_pat   = re.compile( '[$][a-zA-Z][a-zA-Z0-9_]*' )


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
                m = curly_pat.search( s, idx )
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
                m = var_pat.search( s, idx )
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
        
        s = curly_pat.sub('', s)
        s = var_pat.sub('', s)

    return s
