#!/usr/bin/env python

import os, sys
from os.path import abspath, dirname, basename, normpath
from os.path import join as pjoin
import shutil
import time

import webgen
import gitresults


class DashboardCreator:

    def __init__(self, results_repo_url, working_directory=None):
        ""
        self.url = results_repo_url
        self.workdir = working_directory

        self.summaries = []

    def readResults(self):
        ""
        rdr = gitresults.GitResultsReader( self.url )

        for branch,rdir in rdr.iterateDirectories():
            rsum = gitresults.ResultsSummary( self.url, branch, rdir )
            self.summaries.append( [ rsum.getDateStamp(), rdir, rsum ] )

        self.summaries.sort( reverse=True )

        rdr.cleanup()

    def getDateStamps(self):
        ""
        dsL = [ L[0] for L in self.summaries ]
        return dsL

    def writeHistoryPage(self, pathname, page_title='Results History'):
        ""
        pathdir = self._write_page_structure( pathname, page_title )
        self.body.add( webgen.Heading( 'Results History', align='center' ) )
        self._write_history_table()
        self._add_scidev_logo( pathdir )
        self.doc.close()

    def _write_page_structure(self, pathname, page_title):
        ""
        filename = determine_filename( pathname )

        self.doc = webgen.HTMLDocument( filename )

        self.doc.add( webgen.Head( page_title ) )

        self.body = self.doc.add( webgen.Body( background='cadetblue' ) )

        return dirname( filename )

    def _write_history_table(self):
        ""
        tab = webgen.Table( border='internal', align='center',
                            background='white', radius=5, padding=2 )
        self.body.add( tab )

        tab.add( 'Job Date', 'Label',
                 'pass', 'fail', 'diff', 'timeout', 'notdone', 'notrun',
                 'Details',
                 header=True )

        for ds,rdir,rsum in self.summaries:
            row = tab.add()
            fill_history_row( row, ds, rdir, rsum )

    def _add_scidev_logo(self, page_directory):
        ""
        fn = 'scidev_logo.png'
        mydir = dirname( abspath( __file__ ) )
        shutil.copy( pjoin( mydir, fn ), pjoin( page_directory, fn ) )

        img = webgen.make_image( fn, width=100,
                                 position='fixed', bottom=5, right=5 )
        self.body.add( img )


def fill_history_row( row, datestamp, resultsdir, summary ):
    ""
    row.add( make_job_date( datestamp ), align='right' )
    row.add( summary.getLabel() )

    cnts = summary.getCounts()
    for res in ['pass','fail','diff','timeout','notdone','notrun']:
        cnt = cnts.get( res, None )
        add_history_result_entry( row, res, cnt, summary )

    lnk = webgen.make_hyperlink( summary.getResultsLink(),
                                 basename( resultsdir ) )
    row.add( lnk )


def add_history_result_entry( row, result, cnt, summary ):
    ""
    if cnt == None:
        row.add( '?', align='center' )
    else:
        clr = map_result_to_color( result, cnt )
        ent = map_result_to_entry( result, cnt, summary )
        row.add( ent, align='center', background=clr )


def map_result_to_color( result, cnt ):
    ""
    if result == 'pass' or cnt == 0:
        clr = 'lightgreen'

    elif result == 'fail':
        clr = 'tomato'

    else:
        clr = 'yellow'

    return clr


def map_result_to_entry( result, cnt, summary ):
    ""
    if cnt == 0:
        ent = cnt
    else:
        lnk = summary.getResultsLink(result)
        ent = webgen.make_hyperlink( lnk, cnt )

    return ent


def make_job_date( epoch ):
    ""
    stm = time.strftime( "%a %b %d %Hh", time.localtime( epoch ) )
    return stm


def determine_filename( pathname ):
    ""
    if os.path.isdir( pathname ):
        fn = pjoin( abspath( pathname ), 'index.htm' )
    else:
        fn = abspath( pathname )

    return normpath( fn )
