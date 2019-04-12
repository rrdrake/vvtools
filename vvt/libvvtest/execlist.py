#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys

from . import CommonSpec
from . import TestExec
from . import depend


class TestExecList:

    def __init__(self, statushandler, tlist):
        ""
        self.statushandler = statushandler
        self.tlist = tlist

        self.xtlist = {}  # np -> list of TestExec objects
        self.started = {}  # TestSpec xdir -> TestExec object
        self.stopped = {}  # TestSpec xdir -> TestExec object

    def createTestExecs(self, test_dir, platform, config, perms):
        """
        Creates the set of TestExec objects from the active test list.
        """
        d = os.path.join( config.get('toolsdir'), 'libvvtest' )
        c = config.get('configdir')
        xdb = CommonSpec.loadCommonSpec( d, c )

        self._createTestExecList( perms )
        
        for xt in self.getTestExecList():
            xt.init( test_dir, platform, xdb, config )

    def markTestsWithDependents(self):
        ""
        for tx in self.getTestExecList():
            if tx.hasDependent():
                tx.atest.setAttr( 'hasdependent', True )

    def _createTestExecList(self, perms):
        ""
        self.xtlist = {}

        xtD = {}
        for t in self.tlist.getTests():

            if not self.statushandler.skipTest( t ):

                assert t.constructionCompleted()

                xt = TestExec.TestExec( self.statushandler, t, perms )

                if t.getAttr( 'hasdependent', False ):
                    xt.setHasDependent()

                np = int( t.getParameters().get('np', 0) )
                if np in self.xtlist:
                    self.xtlist[np].append(xt)
                else:
                    self.xtlist[np] = [xt]

                xtD[ t.getExecuteDirectory() ] = xt

        # sort tests longest running first; 
        self.sortTestExecList()

        self._connect_execute_dependencies( xtD )

    def _connect_execute_dependencies(self, xdir2testexec):
        ""
        tmap = self.tlist.getTestMap()
        groups = self.tlist.getGroupMap()

        for xt in self.getTestExecList():

            if xt.atest.isAnalyze():
                grpL = groups.getGroup( xt.atest )
                depend.connect_analyze_dependencies( xt, grpL, xdir2testexec )

            depend.check_connect_dependencies( xt, tmap, xdir2testexec )

    def sortTestExecList(self):
        """
        Sort the TestExec objects by runtime, descending order.  This is so
        popNext() will try to avoid launching long running tests at the end
        of the testing sequence, which can add significantly to the total wall
        time.
        """
        for np,L in self.xtlist.items():
            sortL = []
            for tx in L:
                t = tx.atest
                tm = self.statushandler.getRuntime( t, None )
                if tm == None: tm = 0
                sortL.append( (tm,tx) )
            sortL.sort()
            sortL.reverse()
            L[:] = [ tx for tm,tx in sortL ]

    def getTestExecProcList(self):
        """
        Returns a list of integers; each integer is the number of processors
        needed by one or more tests in the TestExec list.
        """
        return self.xtlist.keys()
    
    def getTestExecList(self, numprocs=None):
        """
        If 'numprocs' is None, all TestExec objects are returned.  If 'numprocs'
        is not None, a list of TestExec objects is returned each of which need
        that number of processors to run.
        """
        L = []
        if numprocs == None:
          for txL in self.xtlist.values():
            L.extend( txL )
        else:
          L.extend( self.xtlist.get(numprocs,[]) )
        return L
    
    def popNext(self, platform):
        """
        Finds a test to execute.  Returns a TestExec object, or None if no
        test can run.  In this case, one of the following is true
        
            1. there are not enough free processors to run another test
            2. the only tests left are parent tests that cannot be run
               because one or more of their children did not pass or diff

        In the latter case, numRunning() will be zero.
        """
        npL = list( self.xtlist.keys() )
        npL.sort()
        npL.reverse()

        # find longest runtime test such that the num procs is available
        tx = self._pop_next_test( npL, platform )
        if tx == None and len(self.started) == 0:
            # search for tests that need more processors than platform has
            tx = self._pop_next_test( npL )

        if tx != None:
            self.started[ tx.atest.getExecuteDirectory() ] = tx

        return tx

    def popRemaining(self):
        """
        All remaining tests are removed from the run list and returned.
        """
        tL = []
        for np,L in list( self.xtlist.items() ):
            tL.extend( L )
            del L[:]
            self.xtlist.pop( np )
        return tL

    def getRunning(self):
        """
        Return the list of tests that are still running.
        """
        return self.started.values()

    def testDone(self, tx):
        ""
        xdir = tx.atest.getExecuteDirectory()
        self.tlist.appendTestResult( tx.atest )
        self.started.pop( xdir, None )
        self.stopped[ xdir ] = tx

    def numDone(self):
        """
        Return the number of tests that have been run.
        """
        return len(self.stopped)

    def numRunning(self):
        """
        Return the number of tests are currently running.
        """
        return len(self.started)

    def _pop_next_test(self, npL, platform=None):
        ""
        for np in npL:
            if platform == None or platform.queryProcs(np):
                tL = self.xtlist[np]
                N = len(tL)
                i = 0
                while i < N:
                    tx = tL[i]
                    if tx.getDependencySet().getBlocking() == None:
                        self._pop_test_exec( np, i )
                        return tx
                    i += 1
        return None

    def _pop_test_exec(self, np, i):
        ""
        L = self.xtlist[np]
        del L[i]
        if len(L) == 0:
            self.xtlist.pop( np )
