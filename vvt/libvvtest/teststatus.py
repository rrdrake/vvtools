#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys, os
import time


RESULTS_KEYWORDS = [ 'notrun', 'notdone',
                     'fail', 'diff', 'pass',
                     'timeout' ]


# this is the exit status that tests use to indicate a diff
DIFF_EXIT_STATUS = 64


class TestStatusHandler:

    def __init__(self):
        ""
        pass

    def resetResults(self, tspec):
        ""
        tspec.setAttr( 'state', 'notrun' )
        # magic: setting to -1 is a little ugly; should remove the attribute
        tspec.setAttr( 'xtime', -1 )
        tspec.setAttr( 'xdate', -1 )

    def getResultsKeywords(self, tspec):
        ""
        state = tspec.getAttr('state',None)
        if state == None:
            return ['notrun']
        else:
            if state == "notrun": return ["notrun"]
            if state == "notdone": return ["notdone","running"]

        result = tspec.getAttr('result',None)
        if result != None:
            if result == "timeout": return ["timeout","fail"]
            return [result]

        return []

    def isNotrun(self, tspec):
        ""
        # a test without a state is assumed to not have been run
        return tspec.getAttr( 'state', 'notrun' ) == 'notrun'

    def isDone(self, tspec):
        ""
        return tspec.getAttr( 'state', None ) == 'done'

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


def translate_exit_status_to_result_string( exit_status ):
    ""
    if exit_status == 0:
        return 'pass'

    elif exit_status == DIFF_EXIT_STATUS:
        return 'diff'

    else:
        return 'fail'
