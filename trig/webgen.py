#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

#RUNTEST:

import sys
import os


class WebGenError( Exception ):
    pass


class DocumentElement:
    """
    Internal base class for most of the HTML document element classes.
    """

    def __init__(self):
        ""
        self.writer = None
        self.child = None

    def add(self, child_element):
        ""
        self._check_close_child()
        self._check_add_child( child_element )

        return child_element

    def _check_add_child(self, child):
        ""
        if isinstance( child, DocumentElement ):
            child.writer = self.writer
            self.child = child
            child.begin()
        else:
            self.writer.writeln( str(child) )

    def writeln(self, *lines):
        ""
        self.writer.writeln( *lines )

    def createWriter(self, filename):
        ""
        self.writer = Writer( filename )

    def closeWriter(self):
        ""
        self.writer.close()

    def _check_close_child(self):
        ""
        if self.child != None:
            self.child._check_close_child()
            self.child.close()
            self.child = None


class HTMLDocument( DocumentElement ):

    def __init__(self, filename=None):
        ""
        DocumentElement.__init__( self )

        self.createWriter( filename )

        self.writeln( '<!DOCTYPE html>', '<html>' )

    def close(self):
        ""
        self._check_close_child()
        self.writeln( '</html>' )
        self.closeWriter()


class Head( DocumentElement ):

    def __init__(self, title=None):
        ""
        DocumentElement.__init__( self )

        self.title = title
        self.title_written = False

    def begin(self):
        ""
        self.writeln( '<head>' )
        self._write_title( self.title )

    def setTitle(self, title):
        ""
        self._write_title( title )

    def _write_title(self, title):
        ""
        if title:
            if self.title_written:
                raise WebGenError( 'title already written' )

            self.writeln( '<title>'+title+'</title>' )
            self.title_written = True

    def close(self):
        ""
        self.writeln( '</head>' )


class Body( DocumentElement ):

    def __init__(self, **attrs):
        """
            background = <color>
        """
        DocumentElement.__init__( self )

        self.attrs = attrs

    def begin(self):
        ""
        self.writeln( '<body'+self._make_style()+'>' )

    def close(self):
        ""
        self.writeln( '</body>' )

    def _make_style(self):
        ""
        buf = ''

        buf += pop_background_style( self.attrs )

        if len(self.attrs) > 0:
            raise WebGenError( 'unknown Body attribute(s): '+str(self.attrs) )

        return decorate_style_buffer( buf )


class Paragraph( DocumentElement ):

    def __init__(self, *content):
        ""
        DocumentElement.__init__( self )

        self.content = content

    def begin(self):
        ""
        self.writeln( '<p>' )
        for item in self.content:
            self.writeln( item )

    def close(self):
        ""
        self.writeln( '</p>' )


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

    def __init__(self, text=None, **attrs):
        """
            align = left, center, right
        """
        DocumentElement.__init__( self )

        self.text = text
        self.attrs = attrs

    def begin(self):
        ""
        self.writeln( '<h1'+self._make_style()+'>' )

        if self.text:
            self.writeln( self.text )

    def close(self):
        ""
        self.writeln( '</h1>' )

    def _make_style(self):
        ""
        buf = pop_text_align_style( self.attrs )

        if len(self.attrs) > 0:
            raise WebGenError( 'unknown Heading attribute(s): '+str(self.attrs) )

        return decorate_style_buffer( buf )


class Table( DocumentElement ):

    def __init__(self, **attrs):
        """
            align = left center right
            spacing = [0] 1 2 ... : border spacing (between cells)
            border  = all      : border around the table and internal cells
                      internal : borders on internal cells
                      surround : border around the table
            radius = <integer> : make rounded border corners
            background = <color> : background color
            padding = <integer> : set padding between cell content and border
        """
        DocumentElement.__init__( self )

        self.attrs = attrs
        self.rowattrs = {}

    def begin(self):
        ""
        sty = self._make_style()
        self.writeln( '<table'+sty+'>' )

        self.rowcnt = 0

    def add(self, *entries, **rowattrs):
        """
        Adds a row to the table, and returns a TableRow instance.
        The 'entries' are the (perhaps initial) entries in the row.
        The 'rowattrs' are given to TableRow.
        """
        attrs = dict( self.rowattrs, **rowattrs )
        row = TableRow( **attrs )
        row.setRowIndex( self.rowcnt )
        DocumentElement.add( self, row )

        self.rowcnt += 1

        for ent in entries:
            row.add( ent )

        return row

    def close(self):
        ""
        self.writeln( '</table>' )

    def _make_style(self):
        ""
        buf = ''

        buf += pop_page_align_style( self.attrs )

        buf += pop_radius_style( self.attrs )
        buf += pop_background_style( self.attrs )
        pop_padding_style( self.attrs, self.rowattrs )

        sp = self.attrs.pop( 'spacing', 0 )
        buf += 'border-spacing: '+str(sp)+'px;'

        buf += self._pop_border_style( sp )

        if len(self.attrs) > 0:
            raise WebGenError( 'unknown Table attribute(s): '+str(self.attrs) )

        return decorate_style_buffer( buf )

    def _pop_border_style(self, spacing):
        ""
        sty = ''

        bdr = self.attrs.pop( 'border', '' )

        if bdr == 'all' or bdr == 'surround':
            sty = 'border: 1px solid black;'

        if bdr == 'all':
            if spacing == 0:
                self.rowattrs['border'] = 'internal'
            else:
                self.rowattrs['border'] = 'all'

        elif bdr == 'internal':
            self.rowattrs['border'] = 'internal'

        return sty


class TableRow( DocumentElement ):

    def __init__(self, **attrs):
        """
            header = True [False] : mark row entries as header row entries
        """
        DocumentElement.__init__( self )

        self.attrs = attrs
        self.entattrs = {}

    def setRowIndex(self, rowindex):
        ""
        self.rowidx = rowindex

    def begin(self):
        ""
        sty = self._make_style()

        self.writeln( '<tr'+sty+'>' )

        self.colidx = 0

    def add(self, *entries, **entryattrs):
        """
        If no 'entries', an empty TableEntry is returned.
        If an entry is a DocumentElement instance, it is returned.
        Otherwise a TableEntry containing the entry is returned.
        If more than one entry is given, the last entry is returned.
        An entry value of None creates an empty cell.
        The 'entryattrs' are given to TableEntry.
        """
        if len(entries) == 0:
            entries = (None,)

        for ent in entries:

            attrs = dict( self.entattrs, **entryattrs )
            tabent = TableEntry( ent, **attrs )
            tabent.setRowAndColumn( self.rowidx, self.colidx )

            DocumentElement.add( self, tabent )

            if isinstance( ent, DocumentElement ):
                obj = ent
            else:
                obj = tabent

            self.colidx += 1

        return obj

    def close(self):
        ""
        self.writeln( '</tr>' )

    def _make_style(self):
        ""
        buf = ''

        pop_table_header_element_name( self.attrs, self.entattrs )
        pop_table_entry_border( self.attrs, self.entattrs )
        pop_padding_style( self.attrs, self.entattrs )
        pop_background_style( self.attrs, self.entattrs )

        if len(self.attrs) > 0:
            raise WebGenError( 'unknown TableRow attribute(s): '+str(self.attrs) )

        return decorate_style_buffer( buf )


class TableEntry( DocumentElement ):

    def __init__(self, content=None, **attrs):
        """
            align = left center right
            background = <color> : set the background color of the cell
            border = all internal
            padding = <integer> : between cell content and border
            header = [False] True : use table header properties
        """
        DocumentElement.__init__( self )

        self.content = content
        self.attrs = attrs

        self.elmt = 'td'
        self.rowidx = 0
        self.colidx = 0

    def setRowAndColumn(self, rowindex, colindex):
        ""
        self.rowidx = rowindex
        self.colidx = colindex

    def begin(self):
        ""
        sty = self._make_style()
        self.writeln( '<'+self.elmt+sty+'>' )

        if self.content != None:
            if isinstance( self.content, DocumentElement ):
                DocumentElement.add( self, self.content )
            else:
                self.writeln( str(self.content) )

    def close(self):
        ""
        self.writeln( '</'+self.elmt+'>' )

    def _make_style(self):
        ""
        buf = ''

        buf += pop_background_style( self.attrs )
        buf += pop_text_align_style( self.attrs )
        buf += pop_padding_style( self.attrs )

        buf += pop_table_entry_border( self.attrs,
                                       rowidx=self.rowidx,
                                       colidx=self.colidx )

        self.elmt = pop_table_header_element_name( self.attrs )

        if len(self.attrs) > 0:
            raise WebGenError( 'unknown TableEntry attribute(s): '+str(self.attrs) )

        return decorate_style_buffer( buf )


def pop_text_align_style( attrs ):
    ""
    sty = ''

    align = attrs.pop( 'align', None )
    if align != None:
        assert align in [ 'left', 'center', 'right' ]
        sty = 'text-align:'+align+';'

    return sty


def pop_background_style( attrs, copy_attrs=None ):
    ""
    sty = ''

    bg = attrs.pop( 'background', None )
    if bg != None:
        sty = 'background-color:'+bg+';'

        if copy_attrs != None:
            copy_attrs['background'] = bg

    return sty


def pop_padding_style( attrs, copy_attrs=None ):
    ""
    sty = ''

    pad = attrs.pop( 'padding', None )
    if pad != None:
        sty = 'padding: '+str(pad)+'px;'

        if copy_attrs != None:
            copy_attrs['padding'] = pad

    return sty


def pop_radius_style( attrs ):
    ""
    sty = ''

    rad = attrs.pop( 'radius', None )
    if rad != None:
        sty = 'border-radius: '+str(rad)+'px;'

    return sty


def pop_page_align_style( attrs ):
    ""
    sty = ''

    align = attrs.pop( 'align', '' )
    if align == 'left':
        sty = 'margin-right:auto;'
    elif align == 'right':
        sty = 'margin-left:auto;'
    elif align == 'center':
        sty = 'margin-left:auto;margin-right:auto;'

    return sty


def pop_table_header_element_name( attrs, copy_attrs=None ):
    ""
    name = 'td'

    ishdr = attrs.pop( 'header', False )
    if ishdr:
        name = 'th'

        if copy_attrs != None:
            copy_attrs['header'] = True

    return name


def pop_table_entry_border( attrs, copy_attrs=None, rowidx=0, colidx=0 ):
    ""
    sty = ''

    bdr = attrs.pop( 'border', None )

    if bdr != None:

        if bdr == 'all':
            sty += 'border: 1px solid black;'

        elif bdr == 'internal':
            if rowidx > 0:
                sty += 'border-top: 1px solid black;'
            if colidx > 0:
                sty += 'border-left: 1px solid black;'

        if copy_attrs != None:
            copy_attrs['border'] = bdr

    return sty


def decorate_style_buffer( buf ):
    ""
    if buf:
        return ' style="'+buf+'"'
    else:
        return ''


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


def url_safe_string( segment ):
    """
    replaces reserved and unsafe characters for use in web url segments

        https://stackoverflow.com/questions/695438/safe-characters-for-friendly-url

        The reserved characters are:

        ampersand ("&")
        dollar ("$")
        plus sign ("+")
        comma (",")
        forward slash ("/")
        colon (":")
        semi-colon (";")
        equals ("=")
        question mark ("?")
        'At' symbol ("@")
        pound ("#")

        The characters generally considered unsafe are:

        space (" ")
        less than and greater than ("<>")
        open and close brackets ("[]")
        open and close braces ("{}")
        pipe ("|")
        backslash ("\\")
        caret ("^")
        percent ("%")
    """
    seg = segment.replace( '&', 'a' )
    seg = seg.replace( '$', 'd' )
    seg = seg.replace( '+', 'p' )
    seg = seg.replace( ',', 'c' )
    seg = seg.replace( '/', 's' )
    seg = seg.replace( ':', 'o' )
    seg = seg.replace( ';', 'i' )
    seg = seg.replace( '=', 'e' )
    seg = seg.replace( '?', 'q' )
    seg = seg.replace( '@', 't' )
    seg = seg.replace( '#', 'h' )

    seg = seg.replace( ' ', '_' )
    seg = seg.replace( '<', 'l' )
    seg = seg.replace( '>', 'g' )
    seg = seg.replace( '[', 'b' )
    seg = seg.replace( ']', 'B' )
    seg = seg.replace( '{', 'r' )
    seg = seg.replace( '}', 'R' )
    seg = seg.replace( '|', 'v' )
    seg = seg.replace( '\\', 'k' )
    seg = seg.replace( '^', 'u' )
    seg = seg.replace( '%', 'n' )

    return seg
