#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time
import stat
import tempfile
import shutil

from . import TestSpec
from .paramset import ParameterSet
from .testcase import TestCase

version = 33


class TestListWriter:

    def __init__(self, filename):
        ""
        self.filename = filename

    def start(self, **file_attrs):
        ""
        datestamp = repr( [ time.ctime(), time.time() ] )

        remove_attrs_with_None_for_a_value( file_attrs )

        fp = open( self.filename, 'w' )
        try:
            fp.write( '#VVT: Version = '+str(version)+'\n' )
            fp.write( '#VVT: Start = '+datestamp+'\n' )
            fp.write( '#VVT: Attrs = '+repr( file_attrs )+'\n\n' )
        finally:
            fp.close()

    def addIncludeFile(self, filename):
        ""
        fp = open( self.filename, 'a' )
        try:
            fp.write( '#VVT: Include = '+filename+'\n' )
        finally:
            fp.close()

    def append(self, tcase, extended=False):
        ""
        fp = open( self.filename, 'a' )
        try:
            fp.write( test_to_string( tcase, extended ) + '\n' )
        finally:
            fp.close()

    def finish(self):
        ""
        datestamp = repr( [ time.ctime(), time.time() ] )

        fp = open( self.filename, 'a' )
        try:
            fp.write( '\n#VVT: Finish = '+datestamp+'\n' )
        finally:
            fp.close()


class TestListReader:

    def __init__(self, filename):
        ""
        self.filename = filename
        self.vers = None
        self.start = None
        self.attrs = {}
        self.finish = None
        self.tests = {}

    def read(self):
        ""
        for key,val in self._iterate_file_lines():
            try:
                if key == 'Version':
                    self.vers = int( val )
                elif key == 'Start':
                    self.start = eval( val )[1]
                elif key == 'Attrs':
                    self.attrs = eval( val )
                elif key == 'Include':
                    self._read_include_file( val )
                elif key == 'Finish':
                    self.finish = eval( val )[1]
                else:
                    tcase = string_to_test( val )
                    self.tests[ tcase.getSpec().getID() ] = tcase

            except Exception:
                pass

        assert self.vers == 32 or self.vers == 33, \
            'corrupt test list file or older format: '+str(self.filename)

    def getFileVersion(self):
        ""
        return self.vers

    def getStartDate(self):
        ""
        return self.start

    def getFinishDate(self):
        ""
        return self.finish

    def getAttr(self, name, *default):
        ""
        if len(default) > 0:
            return self.attrs.get( name, default[0] )
        return self.attrs[name]

    def getTests(self):
        """
        Returns dictionary mapping execute dir to TestSpec object.
        """
        return self.tests

    def scanForFinishDate(self):
        """
        If the file has a finish date it is returned, otherwise None.
        """
        finish = None

        for key,val in self._iterate_file_lines():
            try:
                if key == 'Finish':
                    finish = eval( val )[1]
            except Exception:
                pass

        return finish

    def _iterate_file_lines(self):
        ""
        fp = open( self.filename, 'r' )
        try:
            for line in fp:

                line = line.strip()

                try:
                    if line.startswith( '#VVT: ' ):
                        n,v = line[5:].split( '=', 1 )
                        yield ( n.strip(), v.strip() )

                    elif line:
                        yield ( None, line )

                except Exception:
                    pass

        finally:
            fp.close()

    def _read_include_file(self, fname):
        ""
        if not os.path.isabs( fname ):
            # include file is relative to self.filename
            fname = os.path.join( os.path.dirname( self.filename ), fname )

        if os.path.exists( fname ):

            tlr = TestListReader( fname )
            tlr.read()
            self.tests.update( tlr.getTests() )


def inline_include_files( filename ):
    """
    For each "include" line in the given test list file, the include statement
    is replaced with the test specifications from the included file.  If the
    file contains no include lines, the file is not touched.
    """
    fdir = os.path.dirname( filename )

    tmpfp = TempFile( '.vvtest' )
    try:
        numincl = 0

        fp = open( filename, 'r' )
        for line in fp:
            if line.startswith( '#VVT: ' ):
                numincl += process_inline_vvt_directive( tmpfp, fdir, line )
            else:
                tmpfp.write( line )

        if numincl > 0:
            tmpfp.copyto( filename )

    finally:
        tmpfp.remove()


def process_inline_vvt_directive( tmpfp, fdir, line ):
    ""
    numincl = 0

    kvL = line[5:].split( '=', 1 )
    if len(kvL) == 1:
        tmpfp.write( line )
    else:
        n,v = kvL
        if n.strip() == 'Include':
            numincl = 1
            try:
                insert_include_file( tmpfp, fdir, v.strip() )
            except Exception:
                pass
        else:
            tmpfp.write( line )

    return numincl


def insert_include_file( tmpfp, fdir, inclfname ):
    ""
    if not os.path.isabs( inclfname ):
        inclfname = os.path.join( fdir, inclfname )

    if os.path.exists( inclfname ):
        fp = open( inclfname, 'r' )
        try:
            for incline in fp:
                sline = incline.strip()
                if sline and not sline.startswith( '#VVT: ' ):
                    tmpfp.write( incline )
        finally:
            fp.close()


class TempFile:

    def __init__(self, suffix):
        ""
        fd, self.fname = tempfile.mkstemp( suffix=suffix )
        self.fp = os.fdopen( fd, 'w' )

    def getFilename(self):
        ""
        return self.fname

    def write(self, buf):
        ""
        self.fp.write( buf )

    def copyto(self, filename):
        ""
        self.fp.close()
        self.fp = None

        if os.path.exists( filename ):
            fmode = stat.S_IMODE( os.stat(filename)[stat.ST_MODE] )
            shutil.copyfile( self.fname, filename )
            os.chmod( filename, fmode )
        else:
            shutil.copyfile( self.fname, filename )

    def remove(self):
        ""
        try:
            if self.fp != None:
                self.fp.close()
        finally:
            os.remove( self.fname )


def remove_attrs_with_None_for_a_value( attrdict ):
    ""
    for k,v in list( attrdict.items() ):
        if v == None:
            attrdict.pop( k )


def test_to_string( tcase, extended=False ):
    """
    Returns a string with no newlines containing the file path, parameter
    names/values, and attribute names/values.
    """
    tspec = tcase.getSpec()

    assert tspec.getName() and tspec.getRootpath() and tspec.getFilepath()

    testdict = {}

    testdict['name'] = tspec.getName()
    testdict['root'] = tspec.getRootpath()
    testdict['path'] = tspec.getFilepath()
    testdict['keywords'] = tspec.getKeywords( include_implicit=False )

    if tspec.isAnalyze():
        testdict['paramset'] = tspec.getParameterSet().getParameters()
    else:
        testdict['params'] = tspec.getParameters()

    testdict['attrs'] = tspec.getAttrs()

    if extended:
        insert_extended_test_info( tcase, testdict )

    s = repr( testdict )

    return s


def string_to_test( strid ):
    """
    Creates and returns a partially filled TestSpec object from a string
    produced by the test_to_string() method.
    """
    testdict = eval( strid.strip() )

    name = testdict['name']
    root = testdict['root']
    path = testdict['path']

    tspec = TestSpec.TestSpec( name, root, path )

    if 'paramset' in testdict:
        pset = ParameterSet()
        for T,L in testdict['paramset'].items():
            pset.addParameterGroup( T, L )
        tspec.setParameterSet( pset )
    else:
        tspec.setParameters( testdict['params'] )

    tspec.setKeywords( testdict['keywords'] )

    for k,v in testdict['attrs'].items():
        tspec.setAttr( k, v )

    tcase = TestCase( tspec )

    check_load_extended_info( tcase, testdict )

    return tcase


def insert_extended_test_info( tcase, testdict ):
    ""
    if tcase.hasDependent():
        testdict['hasdependent'] = True

    depL = tcase.getDepDirectories()
    if len( depL ) > 0:
        testdict['depdirs'] = depL


def check_load_extended_info( tcase, testdict ):
    ""
    if testdict.get( 'hasdependent', False ):
        tcase.setHasDependent()

    depL = testdict.get( 'depdirs', None )
    if depL:
        for pat,xdir in depL:
            tcase.addDepDirectory( pat, xdir )


def print3( *args ):
    sys.stdout.write( ' '.join( [ str(arg) for arg in args ] ) + '\n' )
    sys.stdout.flush()
