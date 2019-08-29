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

        self.results = ResultsCache()

    def readResults(self):
        ""
        self.results.read( self.url )

    def getDateStamps(self):
        ""
        dsL = [ gr.getDateStamp() for gr in self.results.iterate() ]
        return dsL

    def writePages(self, filepath, summary_title='Results Summary'):
        ""
        idxfile = determine_page_filename( filepath )
        pathdir = dirname( idxfile )

        self.writeSummaryPage( idxfile, title=summary_title )

        for gr in self.results.iterate():
            lab = gr.getLabel()
            fn = pjoin( pathdir, filename_for_history_results( lab ) )
            self.writeHistoryPage( fn, title=lab,
                                       label_pattern='^'+lab+'$',
                                       show_label=False )

    def writeSummaryPage(self, filepath, title='Results Summary'):
        ""
        page = create_web_page( filepath, title )
        page.getBody().add( webgen.Heading( title, align='center' ) )
        write_summary_table( page.getBody(), self.results )
        add_scidev_logo( page )
        page.close()

    def writeHistoryPage(self, filepath, title='Results History',
                                         label_pattern=None,
                                         show_label=True):
        ""
        page = create_web_page( filepath, title )
        page.getBody().add( webgen.Heading( title, align='center' ) )
        write_history_table( page.getBody(), self.results,
                             label_pattern=label_pattern,
                             show_label=show_label )
        add_scidev_logo( page )
        page.close()


class ResultsCache:

    def __init__(self, gitresults_list=[]):
        ""
        self.gitres = gitresults_list

    def read(self, git_url):
        ""
        rdr = gitresults.GitResultsReader( git_url )

        sortlist = []

        for branch,rdir in rdr.iterateDirectories():
            gr = gitresults.ResultsSummary( git_url, branch, rdir )
            sortlist.append( [ gr.getDateStamp(), rdir, gr ] )

        rdr.cleanup()

        sortlist.sort( reverse=True )

        self.gitres = [ L[2] for L in sortlist ]

    def iterate(self, label_pattern=None):
        ""
        for gr in self.gitres:
            if results_label_match( gr.getLabel(), label_pattern ):
                yield gr

    def getLatestResults(self):
        """
        - gets the most recent results that finished for each label
        - if none of the results for a label finished, get the most recent
        """
        resmap = {}

        for gr in self.iterate():
            lab = gr.getLabel()

            if lab in resmap:
                prev_is_finished = resmap[lab].isFinished()
                if gr.isFinished() and not prev_is_finished:
                    resmap[ lab ] = gr
            else:
                resmap[ lab ] = gr

        return resmap


def results_label_match( label, pattern ):
    ""
    if pattern == None:
        return True

    if re.search( pattern, label, re.MULTILINE ) != None:
        return True

    return False


class WebPage:

    def __init__(self, filepath):
        ""
        self.filename = determine_page_filename( filepath )

        self.doc = webgen.HTMLDocument( self.filename )

    def addHead(self, title):
        ""
        self.doc.add( webgen.Head( title ) )

    def addBody(self):
        ""
        self.body = self.doc.add( webgen.Body( background='cadetblue' ) )

    def getDirname(self):
        ""
        return dirname( self.filename )

    def getBody(self):
        ""
        return self.body

    def close(self):
        ""
        self.doc.close()


def create_web_page( filename, page_title ):
    ""
    page = WebPage( filename )

    page.addHead( page_title )
    page.addBody()

    return page


def write_summary_table( body, results ):
    ""
    tab = webgen.Table( border='internal', align='center',
                        background='white', radius=5, padding=2 )
    body.add( tab )

    tab.add( 'Label', 'Elapsed', 'pass', 'fail', 'other', 'Information',
             header=True )

    latest = results.getLatestResults()

    labels = list( latest.keys() )
    labels.sort()

    for lab in labels:
        row = tab.add()
        fill_summary_row( row, latest[lab] )


def write_history_table( body, results,
                         label_pattern=None,
                         show_label=True ):
    ""
    tab = webgen.Table( border='internal', align='center',
                        background='white', radius=5, padding=2 )
    body.add( tab )

    add_history_table_header( tab, show_label )

    for gr in results.iterate( label_pattern ):
        row = tab.add()
        fill_history_row( row, gr, show_label )


def add_history_table_header( tab, show_label ):
    ""
    row = tab.add( 'Job Date', header=True )

    if show_label:
        row.add( 'Label' )

    row.add( 'Elapsed',
             'pass', 'fail', 'diff', 'timeout', 'notdone', 'notrun',
             'Details',
             header=True )


def fill_history_row( row, gitres, show_label ):
    ""
    row.add( make_job_date( gitres.getDateStamp() ), align='right' )

    if show_label:
        row.add( gitres.getLabel() )

    add_elapsed_time_entry( gitres, row )

    cnts = gitres.getCounts()
    for res in ['pass','fail','diff','timeout','notdone','notrun']:
        cnt = cnts.get( res, None )
        add_result_entry( row, res, cnt, gitres )

    lnk = webgen.make_hyperlink( gitres.getResultsLink(),
                                 gitres.getResultsSubdirectory() )
    row.add( lnk )


def fill_summary_row( row, gitres ):
    ""
    fn = filename_for_history_results( gitres.getLabel() )
    lablnk = webgen.make_hyperlink( fn, gitres.getLabel() )
    row.add( lablnk )

    add_elapsed_time_entry( gitres, row )

    cnts = gitres.getCounts()
    for res in ['pass','fail']:
        cnt = cnts.get( res, None )
        add_result_entry( row, res, cnt, gitres )

    res,cnt = distill_other_results( cnts )
    add_result_entry( row, res, cnt, gitres )

    row.add( '' )


def filename_for_history_results( label ):
    ""
    fn = 'his_' + webgen.url_safe_string( label ) + '.htm'
    return fn


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


def add_scidev_logo( page ):
    ""
    body = page.getBody()
    page_directory = page.getDirname()

    fn = 'scidev_logo.png'
    mydir = dirname( abspath( __file__ ) )

    dest = pjoin( page_directory, fn )
    if not os.path.exists( dest ):
        shutil.copy( pjoin( mydir, fn ), dest )

    img = webgen.make_image( fn, width=100,
                             position='fixed', bottom=5, right=5 )
    body.add( img )


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


def determine_page_filename( filepath ):
    ""
    if os.path.isdir( filepath ):
        fn = pjoin( abspath( filepath ), 'index.htm' )
    else:
        fn = abspath( filepath )

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
