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

    def addBody(self, **attrs):
        """
            background = <color>
        """
        self._check_close_current()
        self.cur = Body( self.writer, attrs )
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

    def __init__(self, writer, attrs):
        ""
        DocumentElement.__init__( self, writer )

        sty = self._make_style( attrs )

        self.writeln( '<body'+sty+'>' )

    def addHeading(self, text, **attrs):
        """
            align = left, center, right
        """
        self._check_close_current()
        self.cur = Heading( self.writer, text, **attrs )
        return self.cur

    def addParagraph(self, *text):
        ""
        self._check_close_current()
        self.writeln( '<p>' )
        for item in text:
            self.writeln( str(item) )
        self.writeln( '</p>' )

    def addTable(self, **attrs):
        """
            align = left center right
            spacing = [0] 1 2 ... : border spacing (between cells)
            borders  = all      : border around the table and internal cells
                       internal : borders on internal cells
                       surround : border around the table
            radius = <integer> : make rounded border corners
            background = <color> : background color
            padding = <integer> : set padding between cell content and border
        """
        self._check_close_current()
        self.cur = Table( self.writer, **attrs )
        return self.cur

    def close(self):
        ""
        self._check_close_current()
        self.writeln( '</body>' )

    def _make_style(self, attrs):
        ""
        buf = ''

        bg = attrs.get( 'background', '' )
        if bg:
            buf += 'background-color:'+bg+';'

        if buf:
            return ' style="'+buf+'"'
        else:
            return ''


def make_hyperlink( address, display_text ):
    ""
    return '<a href="'+address+'">'+str(display_text)+'</a>'


def make_image( location, failtext='<broken image>',
                width=None, height=None,
                position=None, top=None, bottom=None, left=None, right=None ):
    """
        width, height in pixels (px)
        position = absolute  : relative to the containing element
                   fixed     : relative to the browser window
                   relative  : relative to its default position
        top, bottom, left, right : spacing from the side in pixels (px)
    """
    buf = '<img src="'+location+'" alt="'+failtext+'"'

    sty = ''

    if width != None: sty += 'width:'+str(width)+'px;'
    if height != None: sty += 'height:'+str(height)+'px;'

    if position != None: sty += 'position:'+position+';'

    if top != None: sty += 'top:'+str(top)+'px;'
    if bottom != None: sty += 'bottom:'+str(bottom)+'px;'
    if left != None: sty += 'left:'+str(left)+'px;'
    if right != None: sty += 'right:'+str(right)+'px;'

    if sty:
        buf += ' style="'+sty+'"'

    buf += '/>'

    return buf


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

        sty = self.sty
        if self.rowcnt > 0:
            sty += self.bdrtop

        self.cur = TableRow( self.writer, sty, self.bdrleft, attrs )

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
        self.sty = ''

        buf = ''

        align = attrs.get( 'align', '' )
        if align == 'left':
            buf += 'margin-right:auto;'
        elif align == 'right':
            buf += 'margin-left:auto;'
        elif align == 'center':
            buf += 'margin-left:auto;margin-right:auto;'

        sp = attrs.get( 'spacing', 0 )
        buf += 'border-spacing: '+str(sp)+'px;'

        bdr = attrs.get( 'borders', '' )
        if bdr == 'all' or bdr == 'surround':
            buf += 'border: 1px solid black;'
        if bdr == 'all':
            if sp == 0:
                self.bdrtop += 'border-top: 1px solid black;'
                self.bdrleft += 'border-left: 1px solid black;'
            else:
                self.sty += 'border: 1px solid black;'
        elif bdr == 'internal':
            self.bdrtop += 'border-top: 1px solid black;'
            self.bdrleft += 'border-left: 1px solid black;'

        rad = attrs.get( 'radius', '' )
        if rad:
            buf += 'border-radius: '+str(rad)+'px;'

        bg = attrs.get( 'background', None )
        if bg != None:
            buf += 'background-color:'+bg+';'

        pad = attrs.get( 'padding', None )
        if pad != None:
            self.sty += 'padding: '+str(pad)+'px;'

        if buf:
            buf = ' style="'+buf+'"'

        return buf


class TableRow( DocumentElement ):

    def __init__(self, writer, sty, lftsty, attrs):
        ""
        DocumentElement.__init__( self, writer )

        self.elmt = 'th' if attrs.get( 'header', False ) else 'td'
        self.sty = sty
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
        sty = self.sty

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
