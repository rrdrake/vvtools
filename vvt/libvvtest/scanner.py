#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys

from .errors import FatalError


class TestFileScanner:

    def __init__(self, testlist, force_params_dict=None):
        """
        If 'force_params_dict' is not None, it must be a dictionary mapping
        parameter names to a list of parameter values.  Any test that contains
        a parameter in this dictionary will take on the given values for that
        parameter.
        """
        self.tlist = testlist
        self.params = force_params_dict

    def scanPaths(self, path_list):
        ""
        for d in path_list:
            if not os.path.exists(d):
                raise FatalError( 'scan path does not exist: ' + str(d) )

            self.scanPath( d )

    def scanPath(self, path):
        """
        Recursively scans for test XML or VVT files starting at 'path'.
        """
        bpath = os.path.normpath( os.path.abspath(path) )

        if os.path.isfile( bpath ):
            basedir,fname = os.path.split( bpath )
            self.tlist.readTestFile( basedir, fname, self.params )

        else:
            for root,dirs,files in os.walk( bpath ):
                self._scan_recurse( bpath, root, dirs, files )

    def _scan_recurse(self, basedir, d, dirs, files):
        """
        This function is given to os.walk to recursively scan a directory
        tree for test XML files.  The 'basedir' is the directory originally
        sent to the os.walk function.
        """
        d = os.path.normpath(d)

        if basedir == d:
            reldir = '.'
        else:
            assert basedir+os.sep == d[:len(basedir)+1]
            reldir = d[len(basedir)+1:]

        # scan files with extension "xml" or "vvt"; soft links to directories
        # are skipped by os.walk so special handling is performed

        for f in files:
            bn,ext = os.path.splitext(f)
            df = os.path.join(d,f)
            if bn and ext in ['.xml','.vvt']:
                fname = os.path.join(reldir,f)
                self.tlist.readTestFile( basedir, fname, self.params )

        linkdirs = []
        for subd in list(dirs):
            rd = os.path.join( d, subd )
            if not os.path.exists(rd) or \
                    subd.startswith("TestResults.") or \
                    subd.startswith("Build_"):
                dirs.remove( subd )
            elif os.path.islink(rd):
                linkdirs.append( rd )

        # TODO: should check that the soft linked directories do not
        #       point to a parent directory of any of the directories
        #       visited thus far (to avoid an infinite scan loop)
        #       - would have to use os.path.realpath() or something because
        #         the actual path may be the softlinked path rather than the
        #         path obtained by following '..' all the way to root

        # manually recurse into soft linked directories
        for ld in linkdirs:
            for lroot,ldirs,lfiles in os.walk( ld ):
                self._scan_recurse( basedir, lroot, ldirs, lfiles )
