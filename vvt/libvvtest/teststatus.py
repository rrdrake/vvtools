#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys, os
import time


RESULTS_KEYWORDS = [ 'notrun', 'notdone',
                     'fail', 'diff', 'pass',
                     'timeout', 'skip' ]


# this is the exit status that tests use to indicate a diff
DIFF_EXIT_STATUS = 64

PARAM_SKIP = 'param'
RESTART_PARAM_SKIP = 'restartparam'
KEYWORD_SKIP = 'keyword'
RESULTS_KEYWORD_SKIP = 'resultskeyword'
SUBDIR_SKIP = 'subdir'

SKIP_REASON = {
        PARAM_SKIP           : 'excluded by parameter expression',
        RESTART_PARAM_SKIP   : 'excluded by parameter expression',
        KEYWORD_SKIP         : 'excluded by keyword expression',
        RESULTS_KEYWORD_SKIP : 'previous result keyword expression',
        SUBDIR_SKIP          : 'current working directory',
        'platform'           : 'excluded by platform expression',
        'option'             : 'excluded by option expression',
        'tdd'                : 'TDD test',
        'search'             : 'excluded by file search expression',
        'maxprocs'           : 'exceeds max processors',
        'runtime'            : 'runtime too low or too high',
        'nobaseline'         : 'no rebaseline specification',
        'depskip'            : 'analyze dependency skipped',
        'tsum'               : 'cummulative runtime exceeded',
    }


class TestStatusHandler:

    def resetResults(self, tspec):
        ""
        tspec.setAttr( 'state', 'notrun' )
        tspec.removeAttr( 'xtime' )
        tspec.removeAttr( 'xdate' )

    def getResultsKeywords(self, tspec):
        ""
        kL = []

        skip = tspec.getAttr( 'skip', None )
        if skip != None:
            kL.append( 'skip' )

        state = tspec.getAttr('state',None)
        if state == None:
            kL.append( 'notrun' )
        else:
            if state == "notrun":
                kL.append( 'notrun' )
            elif state == "notdone":
                kL.extend( ['notdone', 'running'] )

        result = tspec.getAttr('result',None)
        if result != None:
            if result == 'timeout':
                kL.append( 'fail' )
            kL.append( result )

        return kL

    def markSkipByParameter(self, tspec, permanent=True):
        ""
        if permanent:
            tspec.setAttr( 'skip', PARAM_SKIP )
        else:
            tspec.setAttr( 'skip', RESTART_PARAM_SKIP )

    def skipTestByParameter(self, tspec):
        ""
        return tspec.getAttr( 'skip', None ) == PARAM_SKIP

    def markSkipByKeyword(self, tspec, with_results=False):
        ""
        if with_results:
            tspec.setAttr( 'skip', RESULTS_KEYWORD_SKIP )
        else:
            tspec.setAttr( 'skip', KEYWORD_SKIP )

    def markSkipBySubdirectoryFilter(self, tspec):
        ""
        tspec.setAttr( 'skip', SUBDIR_SKIP )

    def markSkipByPlatform(self, tspec):
        ""
        tspec.setAttr( 'skip', 'platform' )

    def markSkipByOption(self, tspec):
        ""
        tspec.setAttr( 'skip', 'option' )

    def markSkipByTDD(self, tspec):
        ""
        tspec.setAttr( 'skip', 'tdd' )

    def markSkipByFileSearch(self, tspec):
        ""
        tspec.setAttr( 'skip', 'search' )

    def markSkipByMaxProcessors(self, tspec):
        ""
        tspec.setAttr( 'skip', 'maxprocs' )

    def markSkipByRuntime(self, tspec):
        ""
        tspec.setAttr( 'skip', 'runtime' )

    def markSkipByBaselineHandling(self, tspec):
        ""
        tspec.setAttr( 'skip', 'nobaseline' )

    def markSkipByAnalyzeDependency(self, tspec):
        ""
        tspec.setAttr( 'skip', 'depskip' )

    def markSkipByCummulativeRuntime(self, tspec):
        ""
        tspec.setAttr( 'skip', 'tsum' )

    def markSkipByUserValidation(self, tspec, reason):
        ""
        tspec.setAttr( 'skip', reason )

    def skipTestCausingAnalyzeSkip(self, tspec):
        ""
        skipit = False
        skp = tspec.getAttr( 'skip', None )
        if skp != None:
            if skp.startswith( PARAM_SKIP ) or \
               skp.startswith( RESTART_PARAM_SKIP ) or \
               skp.startswith( RESULTS_KEYWORD_SKIP ) or \
               skp.startswith( SUBDIR_SKIP ):
                skipit = False
            else:
                skipit = True
        return skipit

    def skipTest(self, tspec):
        ""
        return tspec.getAttr( 'skip', False )

    def getReasonForSkipTest(self, tspec):
        ""
        skip = self.skipTest( tspec )
        assert skip
        # a shortened skip reason is mapped to a longer description, but
        # if not found, then just return the skip value itself
        return SKIP_REASON.get( skip, skip )

    def isNotrun(self, tspec):
        ""
        # a test without a state is assumed to not have been run
        return tspec.getAttr( 'state', 'notrun' ) == 'notrun'

    def isDone(self, tspec):
        ""
        return tspec.getAttr( 'state', None ) == 'done'

    def isNotDone(self, tspec):
        ""
        return tspec.getAttr( 'state', None ) == 'notdone'

    def passed(self, tspec):
        ""
        return self.isDone( tspec ) and \
               tspec.getAttr( 'result', None ) == 'pass'

    def getResultStatus(self, tspec):
        ""
        st = tspec.getAttr( 'state', 'notrun' )

        if st == 'notrun':
            return 'notrun'

        elif st == 'done':
            return tspec.getAttr( 'result', 'fail' )

        else:
            return 'notdone'

    def startRunning(self, tspec):
        ""
        tspec.setAttr( 'state', 'notdone' )
        tspec.setAttr( 'xtime', -1 )
        tspec.setAttr( 'xdate', int( 100 * time.time() ) * 0.01 )

    def getStartDate(self, tspec, *default):
        ""
        if len( default ) > 0:
            return tspec.getAttr( 'xdate', default[0] )
        return tspec.getAttr( 'xdate' )

    def getRuntime(self, tspec, *default):
        ""
        xt = tspec.getAttr( 'xtime', None )
        if xt == None or xt < 0:
            if len( default ) > 0:
                return default[0]
            raise KeyError( "runtime attribute not set" )
        return xt

    def setRuntime(self, tspec, num_seconds):
        ""
        tspec.setAttr( 'xtime', num_seconds )

    def markDone(self, tspec, exit_status):
        ""
        tzero = self.getStartDate( tspec )

        tspec.setAttr( 'state', 'done' )
        self.setRuntime( tspec, int(time.time()-tzero) )

        result = translate_exit_status_to_result_string( exit_status )
        tspec.setAttr( 'result', result )

    def markTimedOut(self, tspec):
        ""
        self.markDone( tspec, 1 )
        tspec.setAttr( 'result', 'timeout' )

    def copyResults(self, to_tcase, from_tcase):
        ""
        for k,v in from_tcase.getSpec().getAttrs().items():
            if k in ['state','xtime','xdate','result']:
                to_tcase.getSpec().setAttr( k, v )


def translate_exit_status_to_result_string( exit_status ):
    ""
    if exit_status == 0:
        return 'pass'

    elif exit_status == DIFF_EXIT_STATUS:
        return 'diff'

    else:
        return 'fail'
