#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import stat


class PermissionSetter:
    
    def __init__(self, topdir, spec):
        """
        The 'spec' can be a list or a comma separate string.  If a spec
        starts with "g=" or "o=" then set permissions.  Otherwise, set the
        group name to that string.

        Examples of 'spec': "wg-alegra,g=r-x,o=---"
                            ['wg-alegra','g=rx','o=']
                            ['wg-alegra', 'g=rx,o=rx']
        """
        self.topdir = topdir
        self.spec = spec
        self.cache = {}

        self.grpid = None
        self.gperm = None
        self.operm = None
        try:
            self._parse_spec( spec )
        except:
            raise Exception( "invalid permissions specification: "+str(spec) )

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
            
            def walker( arg, dirname, fnames ):
                rmL = []
                for f in fnames:
                    p = os.path.join( dirname, f )
                    if os.path.islink(p):
                        rmL.append(f)
                    else:
                        arg._setperms(p)
                for f in rmL:
                    fnames.remove(f)
            
            os.path.walk( path, walker, self )
        
        elif not os.path.islink( path ):
            self._setperms( path )

    GRP_MASK = (stat.S_ISGID|stat.S_IRWXG)
    GRP_PERMS = { ''    : 0,
                  '---' : 0,
                  '-'   : 0,
                  'r'   : stat.S_IRGRP,
                  'w'   : stat.S_IWGRP,
                  'x'   : stat.S_IXGRP,
                  's'   : stat.S_IXGRP|stat.S_ISGID,
                  'r--' : stat.S_IRGRP,
                  '-w-' : stat.S_IWGRP,
                  '--x' : stat.S_IXGRP,
                  '--s' : stat.S_IXGRP|stat.S_ISGID,
                  'rw'  : stat.S_IRGRP|stat.S_IWGRP,
                  'rx'  : stat.S_IRGRP|stat.S_IXGRP,
                  'rs'  : stat.S_IRGRP|stat.S_IXGRP|stat.S_ISGID,
                  'wx'  : stat.S_IWGRP|stat.S_IXGRP,
                  'rw-' : stat.S_IRGRP|stat.S_IWGRP,
                  'r-x' : stat.S_IRGRP|stat.S_IXGRP,
                  'r-s' : stat.S_IRGRP|stat.S_IXGRP|stat.S_ISGID,
                  '-wx' : stat.S_IWGRP|stat.S_IXGRP,
                  '-ws' : stat.S_IWGRP|stat.S_IXGRP|stat.S_ISGID,
                  'rwx' : stat.S_IRWXG,
                  'rws' : stat.S_IRWXG|stat.S_ISGID }
    
    OTH_MASK = stat.S_IRWXO
    OTH_PERMS = { ''    : 0,
                  '---' : 0,
                  '-'   : 0,
                  'r'   : stat.S_IROTH,
                  'w'   : stat.S_IWOTH,
                  'x'   : stat.S_IXOTH,
                  'r--' : stat.S_IROTH,
                  '-w-' : stat.S_IWOTH,
                  '--x' : stat.S_IXOTH,
                  'rw'  : stat.S_IROTH|stat.S_IWOTH,
                  'rx'  : stat.S_IROTH|stat.S_IXOTH,
                  'wx'  : stat.S_IWOTH|stat.S_IXOTH,
                  'rw-' : stat.S_IROTH|stat.S_IWOTH,
                  'r-x' : stat.S_IROTH|stat.S_IXOTH,
                  '-wx' : stat.S_IWOTH|stat.S_IXOTH,
                  'rwx' : stat.S_IRWXO }
    
    def _parse_spec(self, spec):
        """
        Sets self.grpid, self.gperm, and self.operm based on the command
        line specification.
        """
        if type(spec) == type(''):
            spec = [ spec ]
        for item in spec:
            for s in item.split(','):
                s = s.strip()
                if s:
                    if s.startswith( 'g=' ):
                        self.gperm = PermissionSetter.GRP_PERMS[ s[2:] ]
                    elif s.startswith( 'o=' ):
                        self.operm = PermissionSetter.OTH_PERMS[ s[2:] ]
                    else:
                        import grp
                        self.grpid = grp.getgrnam( s ).gr_gid
    
    def _setperms(self, path):
        """
        Applies the permissions stored in this class to the give path.
        """
        if self.grpid != None:
            uid = os.stat( path ).st_uid
            os.chown( path, uid, self.grpid )
        
        if self.gperm != None or self.operm != None:
            
            fm = stat.S_IMODE( os.stat(path)[stat.ST_MODE] )
            
            if os.path.isdir( path ):
                # for directories, just set the permissions to the values
                # given at construction
                if self.gperm != None:
                    fm &= ( ~(PermissionSetter.GRP_MASK) )
                    fm |= self.gperm
                if self.operm != None:
                    fm &= ( ~(PermissionSetter.OTH_MASK) )
                    fm |= self.operm
            
            else:
                # for regular files, give execute permission if read is
                # allowed AND the owner has execute permission
                
                if self.gperm != None:
                    fm &= ( ~(PermissionSetter.GRP_MASK) )
                    if int( self.gperm & stat.S_IRGRP ):
                        fm |= stat.S_IRGRP
                        if int( fm & stat.S_IXUSR ):
                            fm |= stat.S_IXGRP
                    if int( self.gperm & stat.S_IWGRP ):
                        fm |= stat.S_IWGRP
                
                if self.operm != None:
                    fm &= ( ~(PermissionSetter.OTH_MASK) )
                    if int( self.operm & stat.S_IROTH ):
                        fm |= stat.S_IROTH
                        if int( fm & stat.S_IXUSR ):
                            fm |= stat.S_IXOTH
                    if int( self.operm & stat.S_IWOTH ):
                        fm |= stat.S_IWOTH
            
            os.chmod( path, fm )
