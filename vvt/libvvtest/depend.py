#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import fnmatch


class TestDependency:

    def __init__(self, tcase, matchpat, wordexpr):
        ""
        self.tcase = tcase
        self.matchpat = matchpat
        self.wordexpr = wordexpr

    def getTestCase(self):
        ""
        return self.tcase

    def hasTestExec(self):
        ""
        return self.tcase.getExec() != None

    def hasSameTestID(self, testdep):
        ""
        tid1 = self.tcase.getSpec().getID()
        tid2 = testdep.tcase.getSpec().getID()

        return tid1 == tid2

    def satisfiesResult(self, result):
        ""
        if self.wordexpr == None:
            if result not in ['pass','diff']:
                return False

        elif not self.wordexpr.evaluate( lambda word: word == result ):
            return False

        return True

    def getMatchDirectory(self):
        ""
        return self.matchpat, self.tcase.getSpec().getExecuteDirectory()

    def isBlocking(self):
        ""
        tcase = self.getTestCase()
        tstat = tcase.getStat()

        if tstat.isDone() or tstat.skipTest():
            result = tstat.getResultStatus()
            if not self.satisfiesResult( result ):
                return True

        elif tstat.isNotDone():
            return True

        else:
            assert tstat.isNotrun()

            if tcase.willNeverRun():
                result = tstat.getResultStatus()
                if not self.satisfiesResult( result ):
                    return True
            else:
                return True

        return False

    def willNeverRun(self):
        ""
        tcase = self.getTestCase()
        tstat = tcase.getStat()

        if tstat.isDone() or tstat.skipTest():
            result = tstat.getResultStatus()
            if not self.satisfiesResult( result ):
                return True

        elif tstat.isNotrun():
            if tcase.willNeverRun():
                result = tstat.getResultStatus()
                if not self.satisfiesResult( result ):
                    return True

        return False


def connect_dependency( from_tcase, to_tcase, pattrn=None, expr=None ):
    ""
    assert from_tcase.getExec() != None

    from_tcase.addDependency( to_tcase, pattrn, expr )

    if to_tcase.getExec() != None:
        to_tcase.setHasDependent()


def find_tests_by_pattern( xdir, pattern, testcasemap ):
    """
    The 'xdir' is the execute directory of the dependent test.  The shell
    glob 'pattern' is matched against the display strings of tests in the
    'testcasemap', in this order:

        1. basename(xdir)/pat
        2. basename(xdir)/*/pat
        3. pat
        4. *pat

    The first of these that matches at least one test will be returned.

    If more than one staged test is matched, then only the last stage is
    included (unless none of them are a last stage, in which case all of
    them are included).

    A python set of TestSpec ID is returned.
    """
    tbase = os.path.dirname( xdir )
    if tbase == '.':
        tbase = ''
    elif tbase:
        tbase += '/'

    pat1 = os.path.normpath( tbase+pattern )
    pat2 = tbase+'*/'+pattern
    pat3 = pattern
    pat4 = '*'+pattern

    L1 = [] ; L2 = [] ; L3 = [] ; L4 = []

    for tid,tcase in testcasemap.items():

        tspec = tcase.getSpec()
        displ = tspec.getDisplayString()

        if tspec.getStageID() == None:
            xdir = None
        else:
            xdir = tspec.getExecuteDirectory()

        if match_test( xdir, displ, pat1 ):
            L1.append( tid )

        if match_test( xdir, displ, pat2 ):
            L2.append( tid )

        if match_test( xdir, displ, pat3 ):
            L3.append( tid )

        if match_test( xdir, displ, pat4 ):
            L4.append( tid )

    for L in [ L1, L2, L3, L4 ]:
        if len(L) > 0:
            return collect_match_test_ids( L, testcasemap )

    return set()


def match_test( xdir, displ, pat ):
    ""
    return fnmatch.fnmatch( displ, pat ) or \
           ( xdir and fnmatch.fnmatch( xdir, pat ) )


def collect_match_test_ids( idlist, testcasemap ):
    ""
    idset = set()

    stagemap = map_staged_xdir_to_tspec_list( idlist, testcasemap )

    for tid in idlist:
        tspec = testcasemap[tid].getSpec()
        if not_staged_or_last_stage( stagemap, tspec ):
            idset.add( tid )

    return idset


def not_staged_or_last_stage( stagemap, tspec ):
    ""
    stagL = stagemap.get( tspec.getExecuteDirectory(), None )

    if stagL == None or len(stagL) < 2:
        return True

    return tspec.isLastStage() or no_last_stages( stagL )


def no_last_stages( tspecs ):
    ""
    for tspec in tspecs:
        if tspec.isLastStage():
            return False

    return True


def map_staged_xdir_to_tspec_list( idlist, testcasemap ):
    ""
    stagemap = {}

    for tid in idlist:
        tspec = testcasemap[tid].getSpec()
        if tspec.getStageID() != None:
            add_test_to_map( stagemap, tspec )

    return stagemap


def add_test_to_map( stagemap, tspec ):
    ""
    xdir = tspec.getExecuteDirectory()
    tL = stagemap.get( xdir, None )
    if tL == None:
        stagemap[xdir] = [tspec]
    else:
        tL.append( tspec )


def connect_analyze_dependencies( analyze, tcaseL, testcasemap ):
    ""
    for tcase in tcaseL:
        tspec = tcase.getSpec()
        if not tspec.isAnalyze():
            connect_dependency( analyze, tcase )
            gxt = testcasemap.get( tspec.getID(), None )
            if gxt != None:
                gxt.setHasDependent()


def check_connect_dependencies( tcase, testcasemap ):
    ""
    tspec = tcase.getSpec()

    for dep_pat,expr in tspec.getDependencies():
        xdir = tspec.getExecuteDirectory()
        depL = find_tests_by_pattern( xdir, dep_pat, testcasemap )
        for dep_id in depL:
            dep_obj = testcasemap.get( dep_id, None )
            if dep_obj != None:
                connect_dependency( tcase, dep_obj, dep_pat, expr )
