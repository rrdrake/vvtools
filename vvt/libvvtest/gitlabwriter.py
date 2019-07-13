#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time
from os.path import join as pjoin

from . import outpututils
print3 = outpututils.print3


class GitLabWriter:

    def __init__(self, permsetter, output_dir, results_test_dir):
        ""
        self.permsetter = permsetter
        self.outdir = os.path.normpath( os.path.abspath( output_dir ) )
        self.testdir = results_test_dir

        self.sortspec = None

    def setSortingSpecification(self, sortspec):
        ""
        self.sortspec = sortspec

    def writeFiles(self, atestlist, runattrs):
        ""
        if not os.path.isdir( self.outdir ):
            os.mkdir( self.outdir )

        try:
            tcaseL = atestlist.getActiveTests( self.sortspec )

            print3( "Writing", len(tcaseL),
                    "tests in GitLab format to", self.outdir )

            conv = GitLabMarkDownConverter( self.testdir, self.outdir )
            conv.setRunAttr( **runattrs )
            conv.saveResults( tcaseL )

        finally:
            self.permsetter.recurse( self.outdir )


class GitLabFileSelector:
    def include(self, filename):
        ""
        bn,ext = os.path.splitext( filename )
        return ext in [ '.vvt', '.xml', '.log', '.txt', '.py', '.sh' ]


class GitLabMarkDownConverter:

    def __init__(self, test_dir, destdir,
                       max_KB=10,
                       big_table_size=100,
                       max_links_per_table=200 ):
        ""
        self.test_dir = test_dir
        self.destdir = destdir
        self.max_KB = max_KB
        self.big_table = big_table_size
        self.max_links = max_links_per_table

        self.selector = GitLabFileSelector()

        self.runattrs = {}

    def setRunAttr(self, **kwargs):
        ""
        self.runattrs.update( kwargs )

    def saveResults(self, tcaseL):
        ""
        parts = outpututils.partition_tests_by_result( tcaseL )

        basepath = pjoin( self.destdir, 'TestResults' )
        fname = basepath + '.md'

        with open( fname, 'w' ) as fp:

            write_run_attributes( fp, self.runattrs )

            for result in [ 'fail', 'diff', 'timeout',
                            'pass', 'notrun', 'notdone' ]:
                altname = basepath + '_' + result + '.md'
                write_gitlab_results( fp, result, parts[result], altname,
                                      self.big_table, self.max_links )

        for result in [ 'fail', 'diff', 'timeout' ]:
            for i,tcase in enumerate( parts[result] ):
                if i < self.max_links:
                    self.createTestFile( tcase )

    def createTestFile(self, tcase):
        ""
        xdir = tcase.getSpec().getDisplayString()
        base = xdir.replace( os.sep, '_' ).replace( ' ', '_' )
        fname = pjoin( self.destdir, base+'.md' )

        srcdir = pjoin( self.test_dir, xdir )

        result = outpututils.XstatusString( tcase, self.test_dir, os.getcwd() )
        preamble = 'Name: '+tcase.getSpec().getName()+'  \n' + \
                   'Result: <code>'+result+'</code>  \n' + \
                   'Run directory: ' + os.path.abspath(srcdir) + '  \n'

        self.createGitlabDirectoryContents( fname, preamble, srcdir )

    def createGitlabDirectoryContents(self, filename, preamble, srcdir):
        ""
        with open( filename, 'w' ) as fp:

            fp.write( preamble + '\n' )

            try:
                stream_gitlab_files( fp, srcdir, self.selector, self.max_KB )

            except Exception:
                xs,tb = outpututils.capture_traceback( sys.exc_info() )
                fp.write( '\n```\n' + \
                    '*** error collecting files: '+srcdir+'\n'+tb + \
                    '```\n' )


def write_run_attributes( fp, attrs ):
    ""
    nvL = list( attrs.items() )
    nvL.sort()
    for name,value in nvL:
        fp.write( '* '+name+' = '+str(value)+'\n' )
    fp.write( '\n' )


def write_gitlab_results( fp, result, testL, altname,
                              maxtablesize, max_path_links ):
    ""
    hdr = '## Tests that '+result+' = '+str( len(testL) ) + '\n\n'
    fp.write( hdr )

    if len(testL) == 0:
        pass

    elif len(testL) <= maxtablesize:
        write_gitlab_results_table( fp, result, testL, max_path_links )

    else:
        bn = os.path.basename( altname )
        fp.write( 'Large table contained in ['+bn+']('+bn+').\n\n' )
        with open( altname, 'w' ) as altfp:
            altfp.write( hdr )
            write_gitlab_results_table( altfp, result, testL, max_path_links )


def write_gitlab_results_table( fp, result, testL, max_path_links ):
    ""
    fp.write( '| Result | Date   | Time   | Path   |\n' + \
              '| ------ | ------ | -----: | :----- |\n' )

    for i,tcase in enumerate(testL):
        add_link = ( i < max_path_links )
        fp.write( format_gitlab_table_line( tcase, add_link ) + '\n' )

    fp.write( '\n' )


def format_gitlab_table_line( tcase, add_link ):
    ""
    tspec = tcase.getSpec()

    result = tcase.getStat().getResultStatus()
    dt = outpututils.format_test_run_date( tcase )
    tm = outpututils.format_test_run_time( tcase )
    path = tspec.getExecuteDirectory_magik()

    makelink = ( add_link and result in ['diff','fail','timeout'] )

    if not tm:
        tm = '-'

    s = '| '+result+' | '+dt+' | '+tm+' | '
    s += format_test_path_for_gitlab( path, makelink ) + ' |'

    return s


def format_test_path_for_gitlab( path, makelink ):
    ""
    if makelink:
        repl = path.replace( os.sep, '_' )
        return '['+path+']('+repl+'.md)'
    else:
        return path


def stream_gitlab_files( fp, srcdir, selector, max_KB ):
    ""

    files,namewidth = get_directory_file_list( srcdir )

    for fn in files:
        fullfn = pjoin( srcdir, fn )

        incl = selector.include( fullfn )
        meta = get_file_meta_data_string( fullfn, namewidth )

        fp.write( '\n' )
        write_gitlab_formatted_file( fp, fullfn, incl, meta, max_KB )


def get_directory_file_list( srcdir ):
    ""
    maxlen = 0
    fL = []
    for fn in os.listdir( srcdir ):
        fL.append( ( os.path.getmtime( pjoin( srcdir, fn ) ), fn ) )
        maxlen = max( maxlen, len(fn) )
    fL.sort()
    files = [ tup[1] for tup in fL ]

    namewidth = min( 30, max( 10, maxlen ) )

    return files, namewidth


def write_gitlab_formatted_file( fp, filename, include_content, label, max_KB ):
    ""
    fp.write( '<details>\n' + \
              '<summary><code>'+label+'</code></summary>\n' + \
              '\n' + \
              '```\n' )

    if include_content:
        try:
            buf = outpututils.file_read_with_limit( filename, max_KB )
        except Exception:
            xs,tb = outpututils.capture_traceback( sys.exc_info() )
            buf = '*** error reading file: '+str(filename)+'\n' + tb

        if buf.startswith( '```' ):
            buf = buf.replace( '```', "'''", 1 )
        buf = buf.replace( '\n```', "\n'''" )

    else:
        buf = '*** file not archived ***'

    fp.write( buf )

    if not buf.endswith( '\n' ):
        fp.write( '\n' )

    fp.write( '```\n' + \
              '\n' + \
              '</details>\n' )


def get_file_meta_data_string( filename, namewidth ):
    ""
    bn = os.path.basename( filename )

    try:

        fmt = "%-"+str(namewidth)+'s'
        if os.path.islink( filename ):
            fname = os.readlink( filename )
            meta = fmt % ( bn + ' -> ' + fname )
            if not os.path.isabs( fname ):
                d = os.path.dirname( os.path.abspath( filename ) )
                fname = pjoin( d, fname )
        else:
            fname = filename
            meta = fmt % bn

        fsize = os.path.getsize( fname )
        meta += " %-12s" % ( ' size='+str(fsize) )

        fmod = os.path.getmtime( fname )
        meta += ' ' + time.ctime( fmod )

    except Exception:
        meta += ' *** error: '+str( sys.exc_info()[1] )

    return meta
