#!/usr/bin/env python

import os, sys
from os.path import abspath, dirname, basename
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

    def writeHistoryPage(self, filename, page_title='Results History'):
        ""
        self._write_page_structure( filename, page_title )
        self.body.addHeading( 'Results History', align='center' )
        self._write_history_table()
        self._add_scidev_logo( dirname( abspath(filename) ) )
        self.doc.close()

    def _write_page_structure(self, filename, page_title):
        ""
        self.doc = webgen.HTMLDocument( filename )

        head = self.doc.addHead()
        head.addTitle( page_title )

        self.body = self.doc.addBody( background='cadetblue' )

    def _write_history_table(self):
        ""
        tab = self.body.addTable( borders='internal', align='center',
                                  background='white', radius=5, padding=2 )

        tab.addRow( 'Job Date', 'Label',
                    'pass', 'fail', 'diff', 'timeout', 'notdone', 'notrun',
                    'Details',
                    header=True )

        for ds,rdir,rsum in self.summaries:
            row = tab.addRow()
            fill_history_row( row, ds, rdir, rsum )

    def _add_scidev_logo(self, page_directory):
        ""
        fn = 'scidev_logo.png'
        mydir = dirname( abspath( __file__ ) )
        shutil.copy( pjoin( mydir, fn ), pjoin( page_directory, fn ) )

        img = webgen.make_image( fn, width=100,
                                 position='fixed', bottom=5, right=5,
                                      )
        self.body.addParagraph( img )


def fill_history_row( row, datestamp, resultsdir, summary ):
    ""
    row.addEntry( make_job_date( datestamp ), align='right' )
    row.addEntry( summary.getLabel() )

    cnts = summary.getCounts()
    for res in ['pass','fail','diff','timeout','notdone','notrun']:
        cnt = cnts.get( res, None )
        add_history_result_entry( row, res, cnt, summary )

    lnk = webgen.make_hyperlink( summary.getResultsLink(),
                                 basename( resultsdir ) )
    row.addEntry( lnk )


def add_history_result_entry( row, result, cnt, summary ):
    ""
    if cnt == None:
        row.addEntry( '?', align='center' )
    else:
        clr = map_result_to_color( result, cnt )
        ent = map_result_to_entry( result, cnt, summary )
        row.addEntry( ent, align='center', background=clr )


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
