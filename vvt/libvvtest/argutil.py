#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys, os
import textwrap
import re

try:
    from argparse import ArgumentParser
    from argparse import HelpFormatter
    from argparse import RawDescriptionHelpFormatter
    from argparse import SUPPRESS

    class ParagraphHelpFormatter( HelpFormatter ):
        """
        This formatter preserves paragraphs in description and epilog text,
        and lines beginning with a ">" are written verbatim.
        """
        def _fill_text(self, text, width, indent):
            ""
            return format_text( text, width, indent )


except Exception:

    """
    Adaptor class for python 2.6, 3.0, and 3.1.  It implements a subset of
    argparse functionality.

    Notable differences to argparse:

        - The returned object from parse_args() always contains the
          non-option arguments as the 'args' data member.

        - Positional arguments are not handled.  If a positional argument
          is specified, all the non-option arguments are stored in a
          variable of that name.

        - The help formatting has differences.  Using ParagraphHelpFormatter
          helps reduce the differences.
    """

    import optparse
    from optparse import HelpFormatter
    from optparse import SUPPRESS_HELP as SUPPRESS

    class RawDescriptionHelpFormatter( optparse.IndentedHelpFormatter ):
        def format_description(self, description):
            ""
            txt = ''
            if description:
                txt = description.strip( '\n' )
            return txt+'\n'

    class ParagraphHelpFormatter( optparse.IndentedHelpFormatter ):
        def format_description(self, description):
            ""
            txt = ''
            if description:
                indent = ' '*self.current_indent
                txt = format_text( description, self.width, indent )
            return txt+'\n'

    class ArgumentParser( optparse.OptionParser ):

        def __init__(self, *args, **kwargs):
            ""
            if 'formatter_class' in kwargs:
                fmtclass = kwargs.pop( 'formatter_class' )
                kwargs[ 'formatter' ] = fmtclass()

            optparse.OptionParser.__init__( self, *args, **kwargs )

            self.required = {}
            self.args_name = None

        def add_argument(self, *args, **kwargs):
            ""
            if args[0].startswith( '-' ):

                if 'required' in kwargs:
                    if kwargs.pop( 'required' ):
                        self.required[ args[0] ] = True

                self.add_option( *args, **kwargs )

            else:
                self.args_name = args[0]

        def add_argument_group(self, group_name):
            ""
            grp = OptionGroupAdaptor( self, group_name )
            self.add_option_group( grp )
            return grp

        def parse_args(self, args=None):
            ""
            opts,args = optparse.OptionParser.parse_args( self, args )

            for optname in self.required.keys():
                vname = optname.lstrip('-')
                val = getattr( opts, vname )
                if val == None:
                    sys.stderr.write( '*** error: missing required ' + \
                                      'argument: ' + optname + '\n' )
                    sys.exit(1)

            opts.args = args
            if self.args_name:
                setattr( opts, self.args_name, args )

            return opts

    class OptionGroupAdaptor( optparse.OptionGroup ):

        def add_argument(self, *args, **kwargs):
            ""
            if args[0].startswith( '-' ):

                if 'required' in kwargs:
                    if kwargs.pop( 'required' ):
                        self.parser.required[ args[0] ] = True

                self.add_option( *args, **kwargs )

            else:
                self.parser.args_name = args[0]


def set_num_columns_for_help_formatter( numcols=None ):
    """
    The COLUMNS environment variable is used when formatting the help page.
    If not already set, this function tries to determine the terminal width
    and use that as the number of columns.

    This function must be called before the ArgumentParser is constructed.
    """
    if numcols:
        os.environ['COLUMNS'] = str(numcols)

    elif 'COLUMNS' not in os.environ:
        ncol = get_terminal_width()
        if ncol:
            os.environ['COLUMNS'] = str(ncol)


###########################################################################

def format_text( text, width, indent ):
    ""
    final = ''

    cnt = 0
    para = ''
    numnewlines = 0
    for line in text.strip().splitlines(True):
        if line.strip():
            cnt = 0
            if line.startswith( '>' ):
                if para:
                    final += '\n'*numnewlines
                    final += fill_paragraph( para, width, indent )
                    para = ''
                    numnewlines = 1
                final += '\n'*numnewlines
                final += line[1:].rstrip()
                numnewlines = 1
            else:
                para += line
        else:
            cnt += 1
            if cnt == 1 and para:
                final += '\n'*numnewlines
                final += fill_paragraph( para, width, indent )
                para = ''
            numnewlines = 2

    if para:
        final += '\n'*numnewlines
        final += fill_paragraph( para, width, indent )

    return final


whitespace_regex = re.compile(r'\s+')

def fill_paragraph( text, width, indent ):
    ""
    text = whitespace_regex.sub(' ', text).strip()
    return textwrap.fill( text, width, initial_indent=indent,
                                       subsequent_indent=indent )


def get_terminal_width():
    ""
    ncol = None

    try:
        ncol = os.get_terminal_size(0)[0]
    except Exception:
        try:
            import fcntl, termios, struct
            data = struct.pack( 'HHHH', 0, 0, 0, 0 )
            data = fcntl.ioctl( 0, termios.TIOCGWINSZ, data )
            h, w, hp, wp = struct.unpack( 'HHHH', data )
            ncol = w
        except Exception:
            try:
                import console
                ncol = console.getTerminalSize()[0]
            except Exception:
                pass

    return ncol
