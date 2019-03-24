#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys


class TestFilter:

    def __init__(self, rtconfig, statushandler):
        ""
        self.rtconfig = rtconfig
        self.statushandler = statushandler

    def checkSubdirectory(self, tspec, subdir):
        ""
        ok = True

        xdir = tspec.getExecuteDirectory()
        if subdir and subdir != xdir and not is_subdir( subdir, xdir ):
            ok = False
            self.statushandler.markSkipBySubdirectoryFilter( tspec )

        return ok

    def checkPlatform(self, tspec):
        ""
        pev = PlatformEvaluator( tspec.getPlatformEnableExpressions() )
        ok = self.rtconfig.evaluate_platform_include( pev.satisfies_platform )
        if not ok:
            self.statushandler.markSkipByPlatform( tspec )
        return ok

    def checkOptions(self, tspec):
        ""
        ok = True
        for opexpr in tspec.getOptionEnableExpressions():
            if not self.rtconfig.evaluate_option_expr( opexpr ):
                ok = False
                break
        if not ok:
            self.statushandler.markSkipByOption( tspec )
        return ok

    def checkKeywords(self, tspec, results_keywords=True):
        ""
        kwlist = tspec.getKeywords() + \
                 self.statushandler.getResultsKeywords( tspec )

        if results_keywords:
            ok = self.rtconfig.satisfies_keywords( kwlist, True )
            if not ok:
                nr_ok = self.rtconfig.satisfies_keywords( kwlist, False )
                if nr_ok:
                    # only mark failed by results keywords if including
                    # results keywords is what causes it to fail
                    self.statushandler.markSkipByKeyword( tspec,
                                                          with_results=True )
                else:
                    self.statushandler.markSkipByKeyword( tspec,
                                                          with_results=False )

        else:
            ok = self.rtconfig.satisfies_keywords( kwlist, False )
            if not ok:
                self.statushandler.markSkipByKeyword( tspec,
                                                      with_results=False )

        return ok

    def checkTDD(self, tspec):
        ""
        if self.rtconfig.getAttr( 'include_tdd', False ):
            ok = True
        else:
            ok = ( 'TDD' not in tspec.getKeywords() )
        if not ok:
            self.statushandler.markSkipByTDD( tspec )
        return ok

    def checkParameters(self, tspec, permanent=True):
        ""
        if tspec.isAnalyze():
            # analyze tests are not excluded by parameter expressions
            ok = True
        else:
            ok = self.rtconfig.evaluate_parameters( tspec.getParameters() )

        if not ok:
            self.statushandler.markSkipByParameter( tspec, permanent=permanent )

        return ok

    def checkFileSearch(self, tspec):
        ""
        ok = self.rtconfig.file_search( tspec )
        if not ok:
            self.statushandler.markSkipByFileSearch( tspec )
        return ok

    def checkMaxProcessors(self, tspec):
        ""
        np = int( tspec.getParameters().get( 'np', 1 ) )
        ok = self.rtconfig.evaluate_maxprocs( np )
        if not ok:
            self.statushandler.markSkipByMaxProcessors( tspec )
        return ok

    def checkRuntime(self, tspec):
        ""
        ok = True
        tm = self.statushandler.getRuntime( tspec, None )
        if tm != None and not self.rtconfig.evaluate_runtime( tm ):
            ok = False
        if not ok:
            self.statushandler.markSkipByRuntime( tspec )
        return ok

    def applyPermanent(self, tspec_map):
        ""
        for xdir,tspec in tspec_map.items():

            self.checkParameters( tspec, permanent=True ) and \
                self.checkKeywords( tspec, results_keywords=False ) and \
                self.checkPlatform( tspec ) and \
                self.checkOptions( tspec ) and \
                self.checkTDD( tspec ) and \
                self.checkFileSearch( tspec ) and \
                self.checkMaxProcessors( tspec ) and \
                self.checkRuntime( tspec )

        # magic: TODO: add skip analyze logic to this function (see comment below)
        self.filterByCummulativeRuntime( tspec_map )

        # magic:
        #   - use case that will fail is:
        #       - a bunch of analyze tests that take a considerable amount of time
        #       - they are not excluded before the --tsum filter process
        #       - they are excluded afterwards if all children are excluded by
        #         parameter
        #       - now the tests left to run will take significantly less time
        #         than the --tmax value

    def applyRuntime(self, tspec_map, filter_dir):
        ""
        include_all = self.rtconfig.getAttr( 'include_all', False )

        if not include_all:

            subdir = clean_up_filter_directory( filter_dir )

            for xdir,tspec in tspec_map.items():

                if not self.statushandler.skipTest( tspec ):

                    self.checkSubdirectory( tspec, subdir ) and \
                        self.checkKeywords( tspec, results_keywords=True ) and \
                        self.checkParameters( tspec, permanent=False ) and \
                        self.checkPlatform( tspec ) and \
                        self.checkOptions( tspec ) and \
                        self.checkTDD( tspec ) and \
                        self.checkMaxProcessors( tspec ) and \
                        self.checkRuntime( tspec )

                    # file search doesn't work in restart mode
                    #   self.checkFileSearch( tspec )

            self.filterByCummulativeRuntime( tspec_map )

    def filterByCummulativeRuntime(self, tspec_map):
        ""
        rtsum = self.rtconfig.getAttr( 'runtime_sum', None )
        if rtsum != None:

            # first, generate list with times
            tL = []
            for xdir,t in tspec_map.items():
                tm = self.statushandler.getRuntime( t, None )
                if tm == None: tm = 0
                tL.append( (tm,xdir,t) )
            tL.sort()

            # accumulate tests until allowed runtime is exceeded
            tsum = 0.
            i = 0 ; n = len(tL)
            while i < n:
                tm,xdir,t = tL[i]
                if not self.statushandler.skipTest( t ):
                    tsum += tm
                    if tsum > rtsum:
                        self.statushandler.markSkipByCummulativeRuntime( t )

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
