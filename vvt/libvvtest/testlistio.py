#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time

from . import TestSpec

version = 1


class TestListWriter:

    def __init__(self, filename):
        ""
        self.filename = filename

    def start(self, **file_attrs):
        ""
        datestamp = repr( [ time.ctime(), time.time() ] )

        fp = open( self.filename, 'w' )
        try:
            fp.write( 'VERSION=testlist'+str(version)+'\n' )
            fp.write( 'START='+datestamp+'\n' )
            fp.write( 'ATTRS='+repr( file_attrs )+'\n\n' )
        finally:
            fp.close()

    def append(self, tspec):
        ""
        fp = open( self.filename, 'a' )
        try:
            fp.write( test_to_string( tspec ) + '\n' )
        finally:
            fp.close()

    def finish(self):
        ""
        datestamp = repr( [ time.ctime(), time.time() ] )

        fp = open( self.filename, 'a' )
        try:
            fp.write( '\nFINISH='+datestamp+'\n' )
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
        fp = open( self.filename, 'r' )
        try:
            line = fp.readline()
            while line:
                self._parse_line( line.strip() )
                line = fp.readline()
        finally:
            fp.close()

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

    def _parse_line(self, line):
        ""
        keyval = line.split('=',1)
        try:
            if keyval[0] == 'VERSION':
                self.vers = int( keyval[1] )
            elif keyval[0] == 'START':
                self.start = eval( keyval[1] )[1]
            elif keyval[0] == 'ATTRS':
                self.attrs = eval( keyval[1] )
            elif keyval[0] == 'FINISH':
                self.finish = eval( keyval[1] )[1]
            elif line:
                tspec = string_to_test( line )
                self.tests[ tspec.getExecuteDirectory() ] = tspec

        except Exception:
            pass


def test_to_string( tspec, include_keywords=False ):
    """
    Returns a string with no newlines containing the file path, parameter
    names/values, and attribute names/values.
    """
    assert tspec.getName() and tspec.getRootpath() and tspec.getFilepath()

    testdict = {}

    testdict['name'] = tspec.getName()
    testdict['root'] = tspec.getRootpath()
    testdict['path'] = tspec.getFilepath()
    if include_keywords:
        testdict['keywords'] = tspec.getKeywords()
    testdict['params'] = tspec.getParameters()
    testdict['attrs'] = tspec.getAttrs()

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
    
    tspec = TestSpec.TestSpec( name, root, path, "string" )

    tspec.setParameters( testdict['params'] )

    tspec.setKeywords( testdict.get( 'keywords', [] ) )

    for k,v in testdict['attrs'].items():
        tspec.setAttr( k, v )

    return tspec


def print3( *args ):
    sys.stdout.write( ' '.join( [ str(arg) for arg in args ] ) + '\n' )
    sys.stdout.flush()
