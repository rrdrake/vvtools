#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time
from os.path import join as pjoin

from . import outpututils
from . import fmtresults
print3 = outpututils.print3


class ListWriter:
    """
    Option is
    
      --save-results
    
    which writes to the platform config testing directory (which looks first at
    the TESTING_DIRECTORY env var).  Can add
    
      --results-tag <string>
    
    which is appended to the results file name.  A date string is embedded in
    the file name, which is obtained from the date of the first test that
    ran.  But if the option

      --results-date <float or string>

    is given on the vvtest command line, then that date is used instead.
    """

    def __init__(self, permsetter, output_dir, results_test_dir):
        ""
        self.permsetter = permsetter
        self.outdir = os.path.normpath( os.path.abspath( output_dir ) )
        self.testdir = results_test_dir

        self.datestamp = None
        self.onopts = []
        self.ftag = None

    def setOutputDate(self, datestamp):
        ""
        self.datestamp = datestamp

    def setNamingTags(self, on_option_list, final_tag):
        ""
        self.onopts = on_option_list
        self.ftag = final_tag

    def writeList(self, atestlist, runattrs, inprogress=False):
        ""
        datestamp = atestlist.getDateStamp( time.time() )
        datestr = outpututils.make_date_stamp( datestamp, self.datestamp )

        fname = self.makeFilename( datestr, runattrs )
        absfname = os.path.join( self.outdir, fname )

        if not os.path.isdir( self.outdir ):
            os.mkdir( self.outdir )

        try:
            tcaseL = atestlist.getActiveTests()

            print3( "Writing results of", len(tcaseL), "tests to", absfname )

            self.writeTestResults( tcaseL, absfname, runattrs, inprogress )

        finally:
            self.permsetter.set( absfname )

    def makeFilename(self, datestr, runattrs):
        ""
        pname = runattrs['platform']
        cplr = runattrs['compiler']

        opL = [ cplr ]
        for op in self.onopts:
            if op != cplr:
                opL.append( op )
        optag = '+'.join( opL )

        L = [ 'results', datestr, pname, optag ]
        if self.ftag:
            L.append( self.ftag )
        basename = '.'.join( L )

        return basename

    def writeTestResults(self, tcaseL, filename, runattrs, inprogress):
        ""
        dcache = {}
        tr = fmtresults.TestResults()

        for tcase in tcaseL:
            rootrel = fmtresults.determine_rootrel( tcase.getSpec(), dcache )
            if rootrel:
                tr.addTest( tcase.getSpec(), rootrel )

        pname = runattrs['platform']
        cplr = runattrs['compiler']
        mach = os.uname()[1]

        tr.writeResults( filename, pname, cplr, mach, self.testdir, inprogress )
