#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

#RUNTEST:

import sys
import os


class DocumentElement:
    """
    Base class for most of the document element classes.
    """

    def __init__(self, writer):
        ""
        self.writer = writer
        self.cur = None

    def _check_close_current(self):
        ""
        if self.cur != None:
            self.cur.close()
            self.cur = None

    def writeln(self, *lines):
        ""
        self.writer.writeln( *lines )

    def closeWriter(self):
        ""
        self.writer.close()
        self.writer = None


class HTMLDocument( DocumentElement ):

    def __init__(self, filename=None):
        ""
        DocumentElement.__init__( self, Writer( filename ) )

    def addHead(self):
        ""
        self.cur = Head( self.writer )
        return self.cur

    def addBody(self):
        ""
        self._check_close_current()
        self.cur = Body( self.writer )
        return self.cur

    def close(self):
        ""
        self._check_close_current()
        self.closeWriter()


class Head( DocumentElement ):

    def __init__(self, writer):
        ""
        DocumentElement.__init__( self, writer )

        self.writeln( '<!DOCTYPE html>', '<html>', '<head>' )

    def addTitle(self, title):
        ""
        self._check_close_current()
        self.writeln( '<title>'+title+'</title>' )

    def close(self):
        ""
        self._check_close_current()
        self.writeln( '</head>' )


class Body( DocumentElement ):

    def __init__(self, writer):
        ""
        DocumentElement.__init__( self, writer )

        self.writeln( '<body>' )

    def addHeading(self, text, **attrs):
        """
            align = left, center, right
        """
        self._check_close_current()
        self.cur = Heading( self.writer, text, **attrs )
        return self.cur

    def addParagraph(self, text=None):
        ""
        self._check_close_current()
        self.writeln( '<p>'+text+'</p>' )

    def addTable(self, **attrs):
        """
            collapse = [True] False : True means no gap between cells
            borders  = all      : border around the table and internal cells
                       internal : borders on internal cells
        """
        self._check_close_current()
        self.cur = Table( self.writer, **attrs )
        return self.cur

    def close(self):
        ""
        self._check_close_current()
        self.writeln( '</body>' )


class Heading( DocumentElement ):

    def __init__(self, writer, text=None, **attrs):
        ""
        DocumentElement.__init__( self, writer )

        self.writeln( '<h1'+self._make_style( attrs )+'>' )
        if text:
            self.writeln( text )

    def close(self):
        ""
        self._check_close_current()
        self.writeln( '</h1>' )

    def _make_style(self, attrs):
        ""
        buf = ''

        for n,v in attrs.items():
            if n == 'align':
                assert v in [ 'left', 'center', 'right' ]
                buf += 'text-align:'+v+';'

        if buf:
            buf = ' style="'+buf+'"'

        return buf


class Table( DocumentElement ):

    def __init__(self, writer, **attrs):
        ""
        DocumentElement.__init__( self, writer )

        sty = self._compute_styles( attrs )
        self.writeln( '<table'+sty+'>' )

        self.rowcnt = 0

    def addRow(self, *entries, **attrs):
        """
            header = True [False] : mark row entries as header row entries
            background = <color> : set the background color of the cell
        """
        self._check_close_current()

        topsty = ''
        if self.rowcnt > 0 and self.bdrtop:
            topsty += self.bdrtop

        self.cur = TableRow( self.writer, topsty, self.bdrleft, attrs )

        for ent in entries:
            self.cur.addEntry( ent )

        self.rowcnt += 1

        return self.cur

    def close(self):
        ""
        self._check_close_current()
        self.writeln( '</table>' )

    def _compute_styles(self, attrs):
        ""
        self.bdrtop = ''
        self.bdrleft = ''

        buf = ''

        if attrs.get( 'collapse', True ):
            buf += 'border-collapse: collapse;'

        for n,v in attrs.items():
            if n == 'borders':
                if v == 'all':
                    buf += 'border: 1px solid black;'
                if v == 'all' or v == 'internal':
                    self.bdrtop += 'border-top: 1px solid black;'
                    self.bdrleft += 'border-left: 1px solid black;'

        if buf:
            buf = ' style="'+buf+'"'

        return buf


class TableRow( DocumentElement ):

    def __init__(self, writer, topsty, lftsty, attrs):
        ""
        DocumentElement.__init__( self, writer )

        self.elmt = 'th' if attrs.get( 'header', False ) else 'td'
        self.topsty = topsty
        self.lftsty = lftsty

        self.writeln( '<tr>' )

        self.colidx = 0

    def addEntry(self, *entries, **attrs):
        ""
        for ent in entries:
            sty = self._make_style( attrs )
            self.writeln( '<'+self.elmt+sty+'>'+str(ent)+'</'+self.elmt+'>' )
            self.colidx += 1

    def close(self):
        ""
        self._check_close_current()
        self.writeln( '</tr>' )

    def _make_style(self, attrs):
        ""
        sty = self.topsty

        if self.colidx > 0 and self.lftsty:
            sty += self.lftsty

        for n,v in attrs.items():
            if n == 'background':
                sty += 'background-color:'+v+';'
            elif n == 'align':
                sty += 'text-align:'+v+';'

        if sty:
            sty = ' style="'+sty+'"'

        return sty


class Writer:

    def __init__(self, filename):
        ""
        self.fp = open( filename, 'wt' )

    def writeln(self, *lines):
        ""
        for line in lines:
            self.fp.write( line+'\n' )

    def close(self):
        ""
        self.fp.close()
        self.fp = None
