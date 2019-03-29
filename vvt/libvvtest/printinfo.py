#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time
import datetime
import select


class TestInformationPrinter:

    def __init__(self, outfile, tlist):
        ""
        self.outfile = outfile
        self.tlist = tlist
        self.starttime = time.time()

        self._check_input = standard_in_has_data

    def checkPrint(self):
        ""
        if self._check_input():
            self.writeInfo()

    def writeInfo(self):
        ""
        now = time.time()
        total_runtime = datetime.timedelta( seconds=int(now - self.starttime) )

        self.println( "\nInformation:" )
        self.println( "  * Total runtime:", total_runtime )

        statushandler = self.tlist.statushandler

        txL = self.tlist.getRunning()
        self.println( "  *", len(txL), "running test(s):" )

        for tx in txL:
            sdt = statushandler.getStartDate( tx.atest )
            duration = datetime.timedelta( seconds=int(now-sdt) )
            xdir = tx.atest.getExecuteDirectory()
            self.println( "    *", xdir, duration )

    def println(self, *args):
        ""
        s = ' '.join( [ str(arg) for arg in args ] )
        self.outfile.write( s + '\n' )

    def setInputChecker(self, func):
        ""
        self._check_input = func


class BatchInformationPrinter:

    def __init__(self, outfile, tlist, batcher):
        ""
        self.outfile = outfile
        self.tlist = tlist
        self.batcher = batcher
        self.starttime = time.time()

        self._check_input = standard_in_has_data

    def checkPrint(self):
        ""
        if self._check_input():
            self.writeInfo()

    def writeInfo(self):
        ""
        now = time.time()
        total_runtime = datetime.timedelta( seconds=int(now - self.starttime) )

        self.println( "\nInformation:" )
        self.println( "  * Total runtime:", total_runtime )

        accnt = self.batcher.getAccountant()

        self.println( '  *', accnt.numStarted(), 'batch job(s) in flight:' )
        for qid, batch_job in accnt.qstart.items():
            duration = now - accnt.timer[qid]
            duration = datetime.timedelta( seconds=int(duration) )
            self.println( '    * qbat.{0},'.format(qid), duration, 'since submitting' )
            for tx in batch_job.testL:
                xdir = tx.atest.getExecuteDirectory()
                self.println( '      *', xdir )

    def println(self, *args):
        ""
        s = ' '.join( [ str(arg) for arg in args ] )
        self.outfile.write( s + '\n' )


def standard_in_has_data():
    ""
    if sys.stdin.isatty():
        if select.select( [sys.stdin,], [], [], 0.0 )[0]:
            sys.stdin.readline()
            return True

    return False
