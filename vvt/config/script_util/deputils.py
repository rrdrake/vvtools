#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
from os.path import join as pjoin

TEST_DATA_FILE_NAME = 'testdata.repr'


def save_test_data( **kwargs ):
    """
    Saves (appends) the given key=value pairs to a file in the current test
    execute directory.
    """
    fn = get_data_file_pathname()

    data = {}
    if os.path.exists( fn ):
        data = read_test_data_file( fn )

    data.update( kwargs )

    with open( fn, 'w' ) as fp:
        fp.write( repr(data) + '\n' )


def read_test_data( testid=None ):
    """
    Reads and returns a test data file as dictionary.  If 'testid' is None,
    the current test data is read.  If not None, the test data from calling
    find_depdir() is read.
    """
    if testid == None:
        # read from current test
        fn = get_data_file_pathname()
    else:
        depd = find_depdir( testid )
        fn = pjoin( depd, TEST_DATA_FILE_NAME )

    data = read_test_data_file( fn )

    return data


def find_depdir( testid ):
    """
    Finds and returns the path to a dependency test matching the given
    'testid'.  Looks for an exact testid match, then one that ends with
    'testid', then one whose test name is 'testid'.
    """
    path = find_vvtest_util_file()
    assert path, 'could not determine current test location'

    vvtD = manual_vvtest_util_read( path )
    xdir = pjoin( vvtD['TESTROOT'], vvtD['TESTID'] )

    depdirs = recursively_accumulate_depdirs( xdir )

    depd = search_depdirs_for_testid( depdirs, testid )
    assert depd, 'could not find testid in dependency tests: '+testid

    return depd


#########################################################################

def search_depdirs_for_testid( depdirs, testid ):
    ""
    depd = search_depdirs_for_full_testid( depdirs, testid )

    if depd == None:
        depd = search_depdirs_for_testid_suffix( depdirs, testid )

    if depd == None:
        depd = search_depdirs_for_test_name( depdirs, testid )

    return depd


def search_depdirs_for_full_testid( depdirs, testid ):
    ""
    for depd,vvtD in depdirs.items():
        if testid == vvtD['TESTID']:
            return depd

    return None


def search_depdirs_for_testid_suffix( depdirs, testid ):
    ""
    for depd,vvtD in depdirs.items():
        if vvtD['TESTID'].endswith( testid ):
            return depd

    return None


def search_depdirs_for_test_name( depdirs, testname ):
    ""
    for depd,vvtD in depdirs.items():
        if testname == vvtD['NAME']:
            return depd

    return None


def recursively_accumulate_depdirs( depdir, depdirs=None ):
    ""
    if depdirs == None:
        depdirs = {}

    try:
        vvtD = manual_vvtest_util_read( depdir )
        depdirs[ depdir ] = vvtD

        for depd in vvtD['DEPDIRS']:
            if depd not in depdirs:
                recursively_accumulate_depdirs( depd, depdirs )

    except Exception:
        pass

    return depdirs


def read_test_data_file( filename ):
    ""
    data = {}

    with open( filename, 'r' ) as fp:
        try:
            data = eval( fp.read().strip() )
        except Exception:
            pass

    return data


def get_data_file_pathname():
    """
    Determines the data file pathname for the current test.  Although if a
    current test cannot be determined, it uses the current directory.
    """
    destdir = None

    try:
        # emulate python import by searching sys.path for vvtest_util.py
        path = search_sys_path_for_file_name( 'vvtest_util.py' )
        if path:
            valD = manual_vvtest_util_read( path )
            destdir = pjoin( valD['TESTROOT'], valD['TESTID'] )

    except Exception:
        pass

    if not destdir:
        destdir = os.getcwd()

    fn = pjoin( destdir, TEST_DATA_FILE_NAME )

    return fn


def search_sys_path_for_file_name( filename ):
    ""
    for pd in sys.path:
        fn = pjoin( pd, filename )
        if os.path.exists( fn ) and os.access( fn, os.R_OK ):
            return fn

    return None


def find_vvtest_util_file():
    ""
    path = search_sys_path_for_file_name( 'vvtest_util.py' )

    if not path:
        fn = os.path.abspath( 'vvtest_util.py' )
        if os.path.exists( fn ):
            path = fn

    return path


def manual_vvtest_util_read( pathname ):
    """
    Manually read (as opposed to python import) the given file and extract
    all "key = <value>" pairs where <value> is a repr'ed python object.
    """
    vals = {}

    if os.path.isdir( pathname ):
        pathname += '/vvtest_util.py'

    with open( pathname, 'r' ) as fp:
        for line in fp.readlines():
            kv = parse_line_into_a_key_value_pair( line )
            if kv:
                vals[ kv[0] ] = kv[1]

    return vals


def parse_line_into_a_key_value_pair( line ):
    ""
    kv = None

    lineL = line.strip().split( ' = ', 1 )
    if len( lineL ) == 2:
        key,sval = lineL
        key = key.strip()
        if key and ' ' not in key:
            try:
                val = eval( sval.strip() )
            except Exception:
                pass
            else:
                kv = [ key, val ]

    return kv
