#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time

from . import outpututils


class ConsoleWriter:

    def __init__(self, statushandler, output_file_obj, results_test_dir):
        ""
        self.statushandler = statushandler
        self.fileobj = output_file_obj
        self.testdir = results_test_dir

        self.sortspec = None

    def setSortingSpecification(self, sortspec):
        ""
        self.sortspec = sortspec

    def writeTests(self, atestlist, abbreviate=False):
        ""
        testL = atestlist.getActiveTests( self.sortspec )

        cwd = os.getcwd()

        self.write( "==================================================" )

        if abbreviate and len(testL) > 16:
            for atest in testL[:8]:
                self.write( outpututils.XstatusString( self.statushandler, atest,
                                                       self.testdir, cwd ) )
            self.write( "..." )
            for atest in testL[-8:]:
                self.write( outpututils.XstatusString( self.statushandler, atest,
                                                       self.testdir, cwd ) )
        else:
            for atest in testL:
                self.write( outpututils.XstatusString( self.statushandler, atest,
                                                       self.testdir, cwd ) )

        self.write( "==================================================" )

        parts = outpututils.partition_tests_by_result( self.statushandler, testL )
        self.write( "Summary:", outpututils.results_summary_string( parts ) )

    def write(self, *args):
        ""
        self.fileobj.write( ' '.join( [ str(arg) for arg in args ] ) + '\n' )
        self.fileobj.flush()
