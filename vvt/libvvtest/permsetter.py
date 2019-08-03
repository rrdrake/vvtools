#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import stat
import itertools

import perms
from .errors import FatalError


class PermissionSetter:
    
    def __init__(self, topdir, spec):
        """
        The 'spec' can be a list or a comma separate string, which is sent
        into the perms.py module for processing.  The only difference here
        is that (for backward compatibility), g= o= g+ and o+ specifications
        will have little x replaced with capital X.

        Examples of 'spec': "wg-alegra,g=r-x,o=---"
                            ['wg-alegra','g=rx','o=']
                            ['wg-alegra', 'g=rx,o=rx']
        """
        self.topdir = topdir
        self.spec = spec
        self.cache = {}

        self.speclist = parse_permission_specifications( spec )

    def set(self, path):
        """
        If 'path' is an absolute path, then set the permissions on the base
        path segment only.

        If 'path' is a relative path, then it must be relative to 'topdir'
        and the permissions are set on the path and all intermediate
        directories at or below the 'topdir'.

        An instance of this class caches the paths that have their permissions
        set and will not set them more than once.
        """
        if os.path.isabs( path ):
            assert os.path.exists( path )
            self._setperms( path )

        else:
            path = os.path.normpath( path )
            assert not path.startswith( '..' )

            fp = os.path.join( self.topdir, path )
            assert os.path.exists( fp )

            # split the path into a list of directory segments
            L = []
            p = path
            while True:
                d,b = os.path.split( p )
                L.append( b )
                if d:
                    p = d
                else:
                    break
            L.reverse()

            rel = '.'
            for b in L:
                rel = os.path.normpath( os.path.join( rel, b ) )
                if rel not in self.cache:
                    self.cache[ rel ] = None
                    fp = os.path.join( self.topdir, rel )
                    self._setperms( fp )

    def recurse(self, path):
        """
        If 'path' is a regular file, then permissions are applied to it.
        If 'path' is a directory, then permissions are applied recursively
        to the each entry in the directory.  Soft links are left untouched
        and not followed.
        """
        if os.path.isdir( path ):
            
            if not os.path.islink( path ):
                self._setperms( path )

            def walker( arg, dirname, dirs, files ):
                ""
                for f in itertools.chain( dirs, files ):
                    p = os.path.join( dirname, f )
                    if not os.path.islink(p):
                        arg._setperms(p)

            for root,dirs,files in os.walk( path ):
                walker( self, root, dirs, files )

        elif not os.path.islink( path ):
            self._setperms( path )

    def _setperms(self, path):
        """
        Applies the permissions stored in this class to the give path.
        """
        perms.apply_chmod( path, *self.speclist )


def parse_permission_specifications( string_or_list ):
    ""
    if type(string_or_list) == type(''):
        speclist = [ string_or_list ]
    else:
        speclist = string_or_list

    specL = []
    for spec_string in speclist:
        for spec in split_by_space_and_comma( spec_string ):
            if len(spec) >= 2 and spec[0] in 'ugo' and spec[1] in '=+-':
                try:
                    perms.change_filemode( 0, spec )
                    spec = change_x_perms_to_capital_X( spec )
                    specL.append( spec )
                except perms.PermissionSpecificationError as e:
                    raise FatalError( 'invalid permission specification "' + \
                                      spec+'" '+str(e) )
            else:
                if not perms.can_map_group_name_to_group_id( spec ):
                    raise FatalError( 'invalid permission specification "' + \
                                      spec+'"' )
                specL.append( spec )

    return specL


def change_x_perms_to_capital_X( spec ):
    ""
    if len(spec) >= 3 and spec[0] in 'go' and spec[1] in '=+':
        spec = spec.replace( 'x', 'X' )

    return spec


def split_by_space_and_comma( spec_string ):
    ""
    sL = []

    for s1 in spec_string.strip().split():
        for s2 in s1.split( ',' ):
            s2 = s2.strip()
            if s2:
                sL.append( s2 )

    return sL
