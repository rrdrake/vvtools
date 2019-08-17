#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys


def parse_key_value_arguments( arglist, *argspecs ):
    """
    The 'arglist' is a list of arguments, such as sys.argv.
    The 'argspecs' define the known key=value arguments, with defaults.
    Specifications can be,

        1. name=value : the argument "name" will default to "value"
        2. name=      : the argument "name" will default an empty string
        3. name=None  : the argument "name" will default to Python None
        4. name       : the argument "name" will default to False

    If 'arglist' contains "name", then its default value will be overridden.
    A Python object is returned that contains the names and values.  For
    example,

        args = parse_key_value_arguments( ['check=foo','other','path'],
                                          'check=bar', 'other' )
        assert args.check == 'bar'
        assert args.other == True
        assert not hasattr( args, 'path' )
    """
    class ArgumentStore:
        pass

    argstore = ArgumentStore()

    kvspecs = KeyValueSpecs( argstore, argspecs )

    arglist = list( arglist )
    while len(arglist) > 0:
        arg = arglist.pop(0)
        if not arg.startswith('-'):
            kvspecs.check_set_argument( arg, arglist )

    return argstore


class KeyValueSpecs:

    def __init__(self, argstore, argspecs):
        ""
        self.argstore = argstore
        self.opts = set()
        self.argopts = set()

        for spec in argspecs:
            L = spec.split('=',1)
            if len(L) == 2:
                self.add_key_value_spec( self.argopts, L )
            else:
                self.add_key_value_spec( self.opts, [ L[0], False ] )

    def check_set_argument(self, arg, arglist):
        ""
        L = arg.split('=',1)

        if len(L) == 2:
            self.set_key_value_argument( L )
        elif arg in self.argopts:
            setattr( self.argstore, arg, arglist.pop(0) )
        elif arg in self.opts:
            setattr( self.argstore, arg, True )

    def set_key_value_argument(self, keyval):
        ""
        name,value = keyval

        if name in self.argopts:
            setattr( self.argstore, name, value )
        elif name in self.opts:
            setattr( self.argstore, name, True )

    def add_key_value_spec(self, optset, keyval):
        ""
        name,value = keyval

        optset.add( name )

        if value == 'None':
            setattr( self.argstore, name, None )
        else:
            setattr( self.argstore, name, value )
