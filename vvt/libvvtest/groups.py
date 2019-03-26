#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys


class ParameterizeAnalyzeGroups:

    def __init__(self, statushandler):
        ""
        self.statushandler = statushandler
        self.groupmap = {}  # (test filepath, test name) -> list of TestSpec

    def getGroup(self, tspec):
        ""
        key = ( tspec.getFilepath(), tspec.getName() )
        tL = []
        for tspec in self.groupmap[key]:
            if not self.statushandler.skipTestByParameter( tspec ):
                tL.append( tspec )
        return tL

    def rebuild(self, tspecs):
        ""
        self.groupmap.clear()

        for xdir,t in tspecs.items():

            # this key is common to each test in a parameterize/analyze
            # test group (including the analyze test)
            key = ( t.getFilepath(), t.getName() )

            L = self.groupmap.get( key, None )
            if L == None:
                L = []
                self.groupmap[ key ] = L

            L.append( t )

    def iterateGroups(self):
        ""
        for key,tspecL in self.groupmap.items():

            analyze = None
            tL = []

            for tspec in tspecL:

                if tspec.isAnalyze():
                    analyze = tspec
                elif not self.statushandler.skipTestByParameter( tspec ):
                    tL.append( tspec )

            if analyze != None:
                yield ( analyze, tL )
