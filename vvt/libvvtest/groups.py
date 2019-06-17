#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys


class ParameterizeAnalyzeGroups:

    def __init__(self):
        ""
        self.groupmap = {}  # (test filepath, test name) -> list of TestCase

    def getGroup(self, tcase):
        ""
        key = ( tcase.getSpec().getFilepath(), tcase.getSpec().getName() )
        tL = []
        for grp_tcase in self.groupmap[key]:
            if not grp_tcase.getStat().skipTestByParameter():
                tL.append( grp_tcase )
        return tL

    def rebuild(self, tcase_map):
        ""
        self.groupmap.clear()

        for xdir,tcase in tcase_map.items():

            t = tcase.getSpec()

            # this key is common to each test in a parameterize/analyze
            # test group (including the analyze test)
            key = ( t.getFilepath(), t.getName() )

            L = self.groupmap.get( key, None )
            if L == None:
                L = []
                self.groupmap[ key ] = L

            L.append( tcase )

    def iterateGroups(self):
        ""
        for key,tcaseL in self.groupmap.items():

            analyze = None
            tL = []

            for tcase in tcaseL:

                tspec = tcase.getSpec()

                if tspec.isAnalyze():
                    analyze = tcase
                elif not tcase.getStat().skipTestByParameter():
                    tL.append( tcase )

            if analyze != None:
                yield ( analyze, tL )
