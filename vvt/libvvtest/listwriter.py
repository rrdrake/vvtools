#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time
from os.path import join as pjoin

import results
from . import outpututils
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

    def __init__(self, statushandler, permsetter,
                       output_dir, results_test_dir):
        ""
        self.statushandler = statushandler
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
            testL = atestlist.getActiveTests()

            print3( "Writing results of", len(testL), "tests to", absfname )

            self.writeTestResults( testL, absfname, runattrs, inprogress )

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

    def writeTestResults(self, testlist, filename, runattrs, inprogress):
        ""
        tr = results.TestResults()

        for tspec in testlist:
            tr.addTest( tspec )

        pname = runattrs['platform']
        cplr = runattrs['compiler']
        mach = os.uname()[1]

        tr.writeResults( filename, pname, cplr, mach, self.testdir, inprogress )


def saveResults( opts, optD, tlist, plat, test_dir, inprogress=False ):
    ""
    pname = plat.getName()
    cplr = plat.getCompiler()

    rtag = opts.results_tag
    
    # determine the date to embed in the file name
    datestr = make_date_stamp(
                    tlist.getDateStamp( time.time() ), opts.results_date )

    L = []
    if optD['onopts']:
        for o in optD['onopts']:
            if o != cplr:
                L.append(o)
    L.sort()
    L.insert( 0, cplr )
    optstag = '+'.join(L)

    rdir = plat.testingDirectory()
    if rdir == None or not os.path.isdir(rdir):
      raise Exception( "invalid testing directory: " + str(rdir) )
    
    L = ['results',datestr,pname,optstag]
    if rtag != None: L.append(rtag)
    fname = os.path.join( rdir, '.'.join( L ) )
    
    tr = results.TestResults()
    for t in tlist.getActiveTests():
      tr.addTest(t)
    mach = os.uname()[1]
    tr.writeResults( fname, pname, cplr, mach, test_dir, inprogress )
