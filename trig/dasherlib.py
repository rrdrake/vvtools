#!/usr/bin/env python

import os, sys
from os.path import abspath, dirname, basename, normpath
from os.path import join as pjoin
import shutil
import time
import re

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

    def writeHistoryPage(self, pathname, title='Results History',
                                         label_pattern=None):
        ""
        pathdir = self._write_page_structure( pathname, title )
        self.body.add( webgen.Heading( title, align='center' ) )
        self._write_history_table( label_pattern=label_pattern )
        self._add_scidev_logo( pathdir )
        self.doc.close()

    def writeSummaryPage(self, pathname, title='Results Summary'):
        ""
        pathdir = self._write_page_structure( pathname, title )
        self.body.add( webgen.Heading( title, align='center' ) )
        self._write_summary_table( )
        self._add_scidev_logo( pathdir )
        self.doc.close()

    def _write_page_structure(self, pathname, page_title):
        ""
        filename = determine_filename( pathname )

        self.doc = webgen.HTMLDocument( filename )

        self.doc.add( webgen.Head( page_title ) )

        self.body = self.doc.add( webgen.Body( background='cadetblue' ) )

        return dirname( filename )

    def _write_history_table(self, label_pattern=None):
        ""
        tab = webgen.Table( border='internal', align='center',
                            background='white', radius=5, padding=2 )
        self.body.add( tab )

        tab.add( 'Job Date', 'Label', 'Elapsed',
                 'pass', 'fail', 'diff', 'timeout', 'notdone', 'notrun',
                 'Details',
                 header=True )

        for ds,rdir,rsum in self.summaries:
            if results_label_match( rsum.getLabel(), label_pattern ):
                row = tab.add()
                fill_history_row( row, ds, rdir, rsum )

    def _write_summary_table(self):
        ""
        latest = get_latest_results_for_each_label( self.summaries )

        labels = list( latest.keys() )
        labels.sort()

        tab = webgen.Table( border='internal', align='center',
                            background='white', radius=5, padding=2 )
        self.body.add( tab )

        tab.add( 'Label', 'Elapsed', 'pass', 'fail', 'other', 'Information',
                 header=True )

        for lab in labels:
            ds,rdir,rsum = latest[lab]
            row = tab.add()
            fill_summary_row( row, ds, rdir, rsum )

    def _add_scidev_logo(self, page_directory):
        ""
        fn = 'scidev_logo.png'
        mydir = dirname( abspath( __file__ ) )
        shutil.copy( pjoin( mydir, fn ), pjoin( page_directory, fn ) )

        img = webgen.make_image( fn, width=100,
                                 position='fixed', bottom=5, right=5 )
        self.body.add( img )


def results_label_match( label, pattern ):
    ""
    if pattern == None:
        return True

    if re.search( pattern, label, re.MULTILINE ) != None:
        return True

    return False


def get_latest_results_for_each_label( summaries ):
    """
    - gets the most recent results that finished for each label
    - if none of the results for a label finished, get the most recent
    - the 'summaries' argument must be sorted most recent first
    """
    resmap = {}

    for dstamp,rdir,rsum in summaries:
        lab = rsum.getLabel()

        if lab in resmap:
            prev_is_finished = resmap[lab][2].isFinished()
            if rsum.isFinished() and not prev_is_finished:
                resmap[ lab ] = [ dstamp,rdir,rsum ]
        else:
            resmap[ lab ] = [ dstamp,rdir,rsum ]

    return resmap


def fill_history_row( row, datestamp, resultsdir, summary ):
    ""
    row.add( make_job_date( datestamp ), align='right' )
    row.add( summary.getLabel() )

    add_elapsed_time_entry( summary, row )

    cnts = summary.getCounts()
    for res in ['pass','fail','diff','timeout','notdone','notrun']:
        cnt = cnts.get( res, None )
        add_result_entry( row, res, cnt, summary )

    lnk = webgen.make_hyperlink( summary.getResultsLink(),
                                 basename( resultsdir ) )
    row.add( lnk )


def fill_summary_row( row, datestamp, resultsdir, summary ):
    ""
    row.add( summary.getLabel() )

    add_elapsed_time_entry( summary, row )

    cnts = summary.getCounts()
    for res in ['pass','fail']:
        cnt = cnts.get( res, None )
        add_result_entry( row, res, cnt, summary )

    res,cnt = distill_other_results( cnts )
    add_result_entry( row, res, cnt, summary )

    row.add( '' )


def add_elapsed_time_entry( summary, row ):
    ""
    elap = format_elapsed_time( summary.getElapsedTime() )
    clr = None if summary.isFinished() else 'yellow'
    row.add( elap, align='right', background=clr )


def distill_other_results( counts ):
    ""
    sumcnt = 0
    sample = None

    for res in ['diff','timeout','notdone','notrun']:
        n = int( counts.get( res, 0 ) )
        sumcnt += n

        if sample == None and n > 0:
            sample = res

    if not sample:
        sample = 'diff'

    return sample,sumcnt


def add_result_entry( row, result, cnt, summary ):
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


def format_elapsed_time( seconds ):
    ""
    n = int( float(seconds) + 0.5 )

    if n < 60*60:
        m = int( n/60 )
        s = n%60
        return str(m)+':'+"%02d"%(s,)

    h = int( n/(60*60) )
    m = int( (n-h*60*60)/60 )
    s = n-h*60*60-m*60
    return str(h)+':'+"%02d"%(m,)+':'+"%02d"%(s,)
