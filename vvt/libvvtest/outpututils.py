#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time
import traceback

from . import TestExec
from . import pathutil


def XstatusString( statushandler, t, test_dir, cwd ):
    """
    Returns a formatted string containing the job and its status.
    """
    ref = ensure_TestSpec( t )

    s =  '%-20s' % ref.getName()
    s += ' %-8s' % statushandler.getResultStatus( ref )
    s += ' %-4s' % format_test_run_time( statushandler, ref )
    s += ' %14s' % format_test_run_date( statushandler, ref )

    xdir = ref.getExecuteDirectory()
    s += ' ' + pathutil.relative_execute_directory( xdir, test_dir, cwd )

    return s


def file_read_with_limit( filename, max_KB ):
    ""
    maxsize = max( 128, max_KB * 1024 )
    fsz = os.path.getsize( filename )

    buf = ''
    if fsz < maxsize:
        with open( filename, 'r' ) as fp:
            buf = fp.read()
    else:
        hdr = int( float(maxsize) * 0.20 + 0.5 )
        bot = fsz - int( float(maxsize) * 0.70 + 0.5 )
        with open( filename, 'r' ) as fp:
            buf = fp.read( hdr )
            buf += '\n\n*** the middle of this file has been removed ***\n\n'
            fp.seek( bot )
            buf += fp.read()

    return buf


def make_date_stamp( testdate, optrdate, timefmt="%Y_%m_%d" ):
    ""
    if optrdate != None:
        if type( optrdate ) == type(''):
            datestr = optrdate
        else:
            tup = time.localtime( optrdate )
            datestr = time.strftime( timefmt, tup )
    else:
        tup = time.localtime( testdate )
        datestr = time.strftime( timefmt, tup )

    return datestr


def partition_tests_by_result( statushandler, testL ):
    ""
    parts = { 'fail':[], 'timeout':[], 'diff':[],
              'pass':[], 'notrun':[], 'notdone':[],
              'skip':[] }

    for tst in testL:
        if statushandler.skipTest( tst ):
            parts[ 'skip' ].append( tst )
        else:
            result = statushandler.getResultStatus( ensure_TestSpec( tst ) )
            parts[ result ].append( tst )

    return parts


def results_summary_string( testparts ):
    ""
    sumL = []

    for result in [ 'pass', 'fail', 'diff', 'timeout',
                    'notdone', 'notrun', 'skip' ]:
        sumL.append( result+'='+str( len( testparts[result] ) ) )

    return ', '.join( sumL )


def format_test_run_date( statushandler, tspec ):
    ""
    xdate = statushandler.getStartDate( tspec, 0 )
    if xdate > 0:
        return time.strftime( "%m/%d %H:%M:%S", time.localtime(xdate) )
    else:
        return ''


def format_test_run_time( statushandler, tspec ):
    ""
    xtime = statushandler.getRuntime( tspec, -1 )
    if xtime < 0:
        return ''
    else:
        return pretty_time( xtime )


def pretty_time( nseconds ):
    """
    Returns a string with the given number of seconds written in a human
    readable form.
    """
    h = int( nseconds / 3600 )
    sh = str(h)+'h'

    m = int( ( nseconds - 3600*h ) / 60 )
    sm = str(m)+'m'

    s = int( ( nseconds - 3600*h - 60*m ) )
    if h == 0 and m == 0 and s == 0: s = 1
    ss = str(s) + 's'

    if h > 0: return sh+' '+sm+' '+ss
    if m > 0: return sm+' '+ss
    return ss


def ensure_TestSpec( testobj ):
    ""
    if isinstance( testobj, TestExec.TestExec ):
        return testobj.atest
    else:
        return testobj


def print3( *args ):
    sys.stdout.write( ' '.join( [ str(arg) for arg in args ] ) + '\n' )
    sys.stdout.flush()


def capture_traceback( excinfo ):
    """
    This should be called in an except block of a try/except, and the argument
    should be sys.exc_info().  It extracts and formats the traceback for the
    exception.  Returns a pair ( the exception string, the full traceback ).
    """
    xt,xv,xtb = excinfo
    xs = ''.join( traceback.format_exception_only( xt, xv ) )
    tb = 'Traceback (most recent call last):\n' + \
         ''.join( traceback.format_list(
                        traceback.extract_stack()[:-2] +
                        traceback.extract_tb( xtb ) ) ) + xs
    return xs,tb
