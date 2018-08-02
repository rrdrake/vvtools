#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import re

from .TestSpecError import TestSpecError


class ScriptSpec:

    def __init__(self, lineno, keyword, attrs, value):
        ""
        self.keyword = keyword
        self.attrs = attrs
        self.value = value
        self.lineno = lineno


class ScriptReader:
    
    def __init__(self, filename):
        """
        """
        self.filename = filename

        self.speclineL = []  # list of [line number, raw spec string]
        self.specL = []  # list of ScriptSpec objects
        self.shebang = None  # a string, if not None

        self.readfile( filename )

    def basename(self):
        """
        Returns the base name of the source file without the extension.
        """
        return os.path.splitext( os.path.basename( self.filename ) )[0]

    def getSpecList(self, specname=None):
        """
        Returns a list of ScriptSpec objects whose keyword equals 'specname'.
        The order is the same as in the source test script.  If 'specname' is
        None, return all ScriptSpec objects.
        """
        L = []
        for sspec in self.specL:
            if specname == None or sspec.keyword == specname:
                L.append( sspec )
        return L

    vvtpat = re.compile( '[ \t]*#[ \t]*VVT[ \t]*:' )

    def readfile(self, filename):
        """
        """
        rdr = FileLineReader( filename )

        self.shebang = None
        try:

            line,info = rdr.nextline()

            if line[:2] == '#!':
                self.shebang = line[2:].strip()
                line,info = rdr.nextline()

            spec = None
            while line:
                done,spec = self.parse_line( line, spec, info )
                if done:
                    break

                line,info = rdr.nextline()

            if spec != None:
                self.speclineL.append( spec )

        finally:
            rdr.close()

        self.process_specs()

        self.filename = filename

    def parse_line(self, line, spec, info):
        """
        Parse a line of the script file.
        """
        done = False
        line = line.strip()
        if line:
            if line[0] == '#':
                m = ScriptReader.vvtpat.match( line )
                if m == None:
                    # comment line, which stops any continuation
                    if spec != None:
                        self.speclineL.append( spec )
                        spec = None
                else:
                    spec = self.parse_spec( line[m.end():], spec, info )
            else:
                # not empty and not a comment
                done = True

        elif spec != None:
            # an empty line stops any continuation
            self.speclineL.append( spec )
            spec = None

        return done,spec

    def parse_spec(self, line, spec, info):
        """
        Parse the contents of the line after a #VVT: marker.
        """
        line = line.strip()
        if line:
            if line[0] == ':':
                # continuation of previous spec
                if spec == None:
                    raise TestSpecError( "A #VVT:: continuation was found" + \
                            " but there is nothing to continue, " + info )
                elif len(line) > 1:
                    spec[1] += ' ' + line[1:]
            elif spec == None:
                # no existing spec and new spec found
                spec = [ info, line ]
            else:
                # spec exists and new spec found
                self.speclineL.append( spec )
                spec = [ info, line ]
        elif spec != None:
            # an empty line stops any continuation
            self.speclineL.append( spec )
            spec = None

        return spec

    # the following pattern should match the first paren enclosed stuff,
    # but parens within double quotes are ignored
    #   1. this would match as few chars within parens
    #       [(].*?[)]
    #   2. this would match as few chars within parens unless there is a
    #      double quote in the parens
    #       [(][^"]*?[)]
    #   3. this would match as few chars within double quotes
    #       ["].*?["]
    #   4. this would match as few chars within double quotes possible
    #      chars on either side (but as few of them as well)
    #       .*?["].*?["].*?
    #   5. this will match either number 2 or number 4 above as a regex group
    #       ([^"]*?|.*?["].*?["].*?)
    #   6. this adds back the parens on the outside
    #       [(]([^"]*?|.*?["].*?["].*?)[)]
    ATTRPAT = re.compile( '[(]([^"]*?|.*?["].*?["].*?)[)]' )

    # this pattern matches everything up to the first ':' or '=' or paren
    DEFPAT = re.compile( '.*?[:=(]' )

    def process_specs(self):
        """
        Turns the list of string specifications into keywords with attributes
        and content.
        """
        ppat = ScriptReader.ATTRPAT
        kpat = ScriptReader.DEFPAT

        for info,line in self.speclineL:
            key = None
            val = None
            attrs = None
            m = kpat.match( line )
            if m:
                key = line[:m.end()-1].strip()
                rest = line[m.end()-1:]
                if rest and rest[0] == '(':
                    # extract attribute(s)
                    m = ppat.match( rest )
                    if m:
                        attrs = rest[:m.end()]
                        attrs = attrs.lstrip('(').rstrip(')').strip()
                        rest = rest[m.end():].strip()
                        if rest and rest[0] in ':=':
                            val = rest[1:]
                        elif rest:
                            raise TestSpecError( \
                              'extra text following attributes, ' + info )
                    else:
                        raise TestSpecError( \
                              'malformed attribute specification, ' + info )
                else:
                    val = rest[1:].strip()
            else:
                key = line.strip()

            if not key:
                raise TestSpecError( \
                        'missing or invalid specification keyword, ' + info )

            if attrs:
                # process the attributes into a dictionary
                D = {}
                for s in attrs.split(','):
                    s = s.strip().strip('"').strip()
                    i = s.find( '=' )
                    if i == 0:
                        raise TestSpecError( \
                                'invalid attribute specification, ' + info )
                    elif i > 0:
                        n = s[:i]
                        v = s[i+1:].strip().strip('"')
                        D[n] = v
                    elif s:
                        D[s] = ''
                attrs = D

            if key == 'insert directive file':
                insert_specs = self._parse_insert_file( info, val )
                self.specL.extend( insert_specs )

            else:
                specobj = ScriptSpec( info, key, attrs, val )
                self.specL.append( specobj )

    def _parse_insert_file(self, info, filename):
        ""
        if filename == None or not filename.strip():
            raise TestSpecError( 
                        'missing insert directive file name, ' + info )

        if not os.path.isabs( filename ):
            d = os.path.dirname( os.path.abspath( self.filename ) )
            filename = os.path.normpath( os.path.join( d, filename ) )

        try:
            inclreader = ScriptReader( filename )
        except TestSpecError:
            raise
        except Exception:
            raise TestSpecError( 'at ' + info + ' the insert ' + \
                            'directive failed: ' + str( sys.exc_info()[1] ) )

        return inclreader.getSpecList()


class FileLineReader:

    def __init__(self, filename):
        ""
        self.filename = filename

        self.fp = open( filename )
        self.lineno = 0

    def nextline(self):
        ""
        line = self.fp.readline()
        self.lineno += 1
        return line, self.filename+':'+str(self.lineno)

    def close(self):
        ""
        self.fp.close()
