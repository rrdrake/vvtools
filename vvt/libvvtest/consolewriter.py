#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time

from . import outpututils


class ConsoleWriter:

    def __init__(self, statushandler, output_file_obj, results_test_dir,
                       verbose=1):
        ""
        self.statushandler = statushandler
        self.fileobj = output_file_obj
        self.testdir = results_test_dir

        self.verbose = verbose

        self.sortspec = None
        self.maxnonpass = 32

    def setSortingSpecification(self, sortspec):
        ""
        self.sortspec = sortspec

    def setMaxNonPass(self, num):
        ""
        assert num > 0
        self.maxnonpass = num

    def writeListSummary(self, atestlist, label):
        ""
        self.write( label )
        self._write_summary( atestlist )

    def writeActiveList(self, atestlist):
        ""
        self._write_test_list_results( atestlist, 2 )

    def writeResultsList(self, atestlist):
        ""
        self._write_test_list_results( atestlist, 1 )

    def _write_summary(self, atestlist):
        ""
        testL = atestlist.getTests()
        parts = outpututils.partition_tests_by_result( self.statushandler, testL )

        n = len( parts['pass'] ) + len( parts['diff'] ) + len( parts['timeout'] )
        self.iwrite( 'completed:', n )
        if n > 0:
            self._write_part_count( parts, 'pass' )
            self._write_part_count( parts, 'diff' )
            self._write_part_count( parts, 'fail' )
            self._write_part_count( parts, 'timeout' )

        self._write_part_count( parts, 'notdone', indent=False )
        self._write_part_count( parts, 'notrun', indent=False )

        self._write_part_count( parts, 'skip', indent=False, label='skipped' )
        self._write_skips( parts['skip'] )

    def _write_skips(self, skiplist):
        ""
        skipmap = self._collect_skips( skiplist )

        keys = list( skipmap.keys() )
        keys.sort()
        for k in keys:
            self.iwrite( ' %6d' % skipmap[k], 'due to "'+k+'"' )

    def _collect_skips(self, skiplist):
        ""
        skipmap = {}

        for tst in skiplist:
            reason = self.statushandler.getReasonForSkipTest( tst )
            if reason not in skipmap:
                skipmap[reason] = 0
            skipmap[reason] += 1

        return skipmap

    def _write_part_count(self, parts, part_name, indent=True, label=None):
        ""
        n = len( parts[part_name] )

        if label == None:
            label = part_name

        if n > 0:
            if indent:
                self.iwrite( ' %6d'%n, label  )
            else:
                self.iwrite( label+':', n  )

    def _write_test_list_results(self, atestlist, detail):
        ""
        level = self._adjust_detail_level_by_verbose( detail )

        cwd = os.getcwd()

        self.write( "==================================================" )

        testL = atestlist.getActiveTests( self.sortspec )

        if level == 1:
            numwritten = self._write_nonpass_notdone( testL, cwd )

        elif level >= 2:
            for atest in testL:
                self.writeTest( atest, cwd )
            numwritten = len( testL )

        if numwritten > 0:
            self.write( "==================================================" )

    def _adjust_detail_level_by_verbose(self, detail):
        ""
        level = detail

        if self.verbose > 1:
            level += 1
        if self.verbose > 2:
            level += 1

        return level

    def _write_nonpass_notdone(self, testL, cwd):
        ""
        numwritten = 0
        i = 0
        for atest in testL:

            if i > self.maxnonpass:
                break

            if self._nonpass_or_notdone( atest ):
                self.writeTest( atest, cwd )
                numwritten += 1

            i += 1

        if i < len( testL ):
            self.write( '... non-pass list too long'
                        ' (use -v for full list or run with -i later)' )

        return numwritten

    def _nonpass_or_notdone(self, tspec):
        ""
        if self.statushandler.isDone( tspec ) and \
                not self.statushandler.passed( tspec ):
            return True

        if self.statushandler.isNotDone( tspec ):
            return True

        return False

    def write(self, *args):
        ""
        self.fileobj.write( ' '.join( [ str(arg) for arg in args ] ) + '\n' )
        self.fileobj.flush()

    def iwrite(self, *args):
        ""
        self.write( '   ', *args )

    def writeTest(self, atest, cwd):
        ""
        astr = outpututils.XstatusString( self.statushandler, atest,
                                          self.testdir, cwd )
        self.write( astr )
