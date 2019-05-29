#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import getopt
import re
import tempfile
import shutil
import filecmp
from os.path import join as pjoin
from os.path import abspath
from os.path import normpath
from os.path import basename
from os.path import dirname

import gitinterface as gititf


class MRGitError( Exception ):
    pass


def clone( argv ):
    ""
    optL,argL = getopt.getopt( argv, '', [] )

    optD = {}
    for n,v in optL:
        optD[n] = v

    if len( argL ) > 0:

        urls, directory = parse_url_list( argL )
        assert len( urls ) > 0

        cfg = Configuration()

        if len( urls ) == 1:
            clone_from_single_url( cfg, urls[0], directory )
        else:
            clone_from_multiple_urls( cfg, urls, directory )

        cfg.commitLocalRepoMap()


def parse_url_list( args ):
    ""
    directory = None

    if len( args ) <= 1 or \
       gititf.repository_url_match( args[-1] ) or \
       gititf.is_a_local_repository( args[-1] ) or \
       gititf.is_a_local_repository( args[-1]+'/.mrgit' ):
        urls = list( args )
    else:
        directory = args[-1]
        urls = args[:-1]

    urls = abspath_local_repository_urls( urls )

    return urls, directory


def abspath_local_repository_urls( urls ):
    ""
    newurls = []
    for url in urls:
        if gititf.is_a_local_repository( url ):
            newurls.append( abspath( url ) )
        else:
            newurls.append( url )

    return newurls


def clone_from_single_url( cfg, url, directory ):
    ""
    tmpd = TempDirectory( directory )

    try:
        # prefer an .mrgit repo under the given url
        git = clone_repo( url+'/.mrgit', tmpd.path(), quiet=True )

    except gititf.GitInterfaceError:
        # that failed, so just clone the given url
        tmpd.removeAllFiles()
        git = clone_repo( url, tmpd.path() )

    if check_load_mrgit_repo( cfg, git ):

        # we just cloned an mrgit manifests repo
        cfg.computeLocalRepoMap()
        topdir = cfg.setTopDir( directory )
        tmpd.moveTo( topdir+'/.mrgit' )
        clone_from_remote( cfg )

    else:
        # assume a simple Git repo was given
        cfg.createFromURLs( [ url ] )
        cfg.computeLocalRepoMap()
        topdir = cfg.setTopDir( directory )
        tmpd.moveTo( topdir )
        cfg.createMRGitRepo()


def clone_from_multiple_urls( cfg, urls, directory ):
    ""
    cfg.createFromURLs( urls )
    cfg.computeLocalRepoMap()
    cfg.setTopDir( directory )
    clone_from_remote( cfg )
    cfg.createMRGitRepo()


def clone_from_remote( cfg ):
    ""
    topdir = cfg.getTopDir()

    check_make_directory( topdir )

    with gititf.change_directory( topdir ):
        for url,loc in cfg.getRemoteRepoList():
            clone_repo( url, loc )


def clone_repo( url, into_dir, quiet=False ):
    ""
    git = gititf.GitInterface()

    if os.path.exists( into_dir ):

        assert '.git' not in os.listdir( into_dir )

        tmp = tempfile.mkdtemp( '', 'mrgit_tempclone_', abspath( into_dir ) )
        git.clone( url, tmp, quiet=quiet )
        move_directory_contents( tmp, into_dir )

        git = gititf.GitInterface( rootdir=into_dir )

    else:
        git.clone( url, into_dir, quiet=quiet )

    return git


class TempDirectory:

    def __init__(self, top_level_dir):
        ""
        self.topdir = top_level_dir
        self.tmpdir = self._create()

    def path(self):
        ""
        return self.tmpdir

    def removeAllFiles(self):
        ""
        clear_directory( self.tmpdir )

    def moveTo(self, todir):
        ""
        if os.path.exists( todir ):
            move_directory_contents( self.tmpdir, todir )
        else:
            check_make_directory( dirname( todir ) )
            os.rename( self.tmpdir, todir )

        if not self.topdir:
            shutil.rmtree( dirname( self.tmpdir ) )

    def _create(self):
        ""
        check_make_directory( self.topdir )

        if self.topdir:
            tdir = abspath( self.topdir )
            tmpdir = tempfile.mkdtemp( '', 'mrgit_tempclone_', tdir )
        else:
            tmpdir1 = tempfile.mkdtemp( '', 'mrgit_tempclone_', os.getcwd() )
            tmpdir  = tempfile.mkdtemp( '', 'mrgit_tempclone_', tmpdir1 )

        return tmpdir


def check_load_mrgit_repo( cfg, git ):
    ""
    mfestfn = pjoin( git.getRootDir(), 'manifests' )

    if os.path.isfile( mfestfn ):
        if 'mrgit_config' in git.listBranches() or \
           'mrgit_config' in git.listRemoteBranches():

            cfg.loadFromCheckout( git )

            return True

    return False


def clear_directory( path ):
    ""
    for fn in os.listdir( path ):
        dfn = pjoin( path, fn )
        if os.path.isdir( dfn ):
            shutil.rmtree( dfn )
        else:
            os.remove( dfn )


def move_directory_contents( fromdir, todir ):
    ""
    if not os.path.exists( todir ):
        os.rename( fromdir, todir )
    else:
        for fn in os.listdir( fromdir ):
            frompath = pjoin( fromdir, fn )
            shutil.move( frompath, todir )
        shutil.rmtree( fromdir )


def check_make_directory( path ):
    ""
    if path and not os.path.isdir( path ):
        os.mkdir( path )


class Configuration:

    def __init__(self):
        ""
        self.topdir = None
        self.mfest = Manifests()
        self.remote = RepoMap()
        self.local = RepoMap()

    def createFromURLs(self, urls):
        ""
        groupname = None
        for i,url in enumerate(urls):
            name = gititf.repo_name_from_url( url )
            if i == 0:
                groupname = name
                path = name
            else:
                path = pjoin( groupname, name )

            self.mfest.addRepo( groupname, name, path )
            self.remote.setRepoLocation( name, url=url )

    def loadFromCheckout(self, git):
        ""
        fn = pjoin( git.getRootDir(), 'manifests' )
        with open( fn, 'r' ) as fp:
            self.mfest.readFromFile( fp )

        git.checkoutBranch( 'mrgit_config' )
        try:
            fn = pjoin( git.getRootDir(), 'config' )
            with open( fn, 'r' ) as fp:
                self.remote.readFromFile( fp, git.getRemoteURL() )

        finally:
            git.checkoutBranch( 'master' )

    def computeLocalRepoMap(self):
        ""
        grp = self.mfest.findGroup( None )

        for spec in grp.getRepoList():
            gitpath = remove_top_level_directory( spec['path'] )
            gitpath = normpath( pjoin( '..', gitpath ) )
            self.local.setRepoLocation( spec['repo'], path=gitpath )

    def setTopDir(self, directory):
        ""
        if directory:
            self.topdir = abspath( normpath( directory ) )
        else:
            grp = self.mfest.findGroup( None )
            self.topdir = abspath( grp.getName() )

        return self.topdir

    def getTopDir(self):
        ""
        return self.topdir

    def getRemoteRepoList(self):
        ""
        grp = self.mfest.findGroup( None )

        repolist = []
        for spec in grp.getRepoList():
            url = self.remote.getRepoURL( spec['repo'] )
            repolist.append( [ url, spec['path'] ] )

        adjust_repo_paths( repolist )

        return repolist

    def commitLocalRepoMap(self):
        ""
        repodir = pjoin( self.topdir, '.mrgit' )
        git = gititf.GitInterface( rootdir=repodir )
        git.checkoutBranch( 'mrgit_config' )

        try:
            fn = pjoin( repodir, 'config' )
            tmpfn = pjoin( repodir, 'config.tmp' )
            with open( tmpfn, 'w' ) as fp:
                self.local.writeToFile( fp )
            if not filecmp.cmp( fn, tmpfn ):
                os.rename( tmpfn, fn )
                git.add( 'config' )
                git.commit( 'commitLocalRepoMap' )

        finally:
            git.checkoutBranch( 'master' )

    def createMRGitRepo(self):
        ""
        repodir = pjoin( self.topdir, '.mrgit' )

        git = gititf.GitInterface()
        git.create( repodir )

        with open( repodir+'/manifests', 'w' ) as fp:
            self.mfest.writeToFile( fp )

        git.add( 'manifests' )
        git.commit( 'init manifests' )

        git.createBranch( 'mrgit_config' )
        with open( repodir+'/config', 'w' ) as fp:
            self.remote.writeToFile( fp )

        git.add( 'config' )
        git.commit( 'init config' )
        git.checkoutBranch( 'master' )


class RepoMap:

    def __init__(self):
        ""
        self.repomap = {}

    def setRepoLocation(self, reponame, url=None, path=None):
        ""
        self.repomap[ reponame ] = ( url, path )

    def getRepoURL(self, reponame):
        ""
        return self.repomap[ reponame ][0]

    def writeToFile(self, fileobj):
        ""
        for name,loc in self.repomap.items():
            url = loc[0]
            fileobj.write( 'repo='+name )
            if loc[0]:
                fileobj.write( ', url='+loc[0] )
            if loc[1]:
                fileobj.write( ', path='+loc[1] )
            fileobj.write( '\n' )
        fileobj.write( '\n' )

    def readFromFile(self, fileobj, baseurl):
        ""
        for line in fileobj:
            line = line.strip()
            if line.startswith('#'):
                pass
            elif line:
                attrs = parse_attribute_line( line )
                if 'repo' in attrs:
                    if 'url' in attrs:
                        url = attrs['url']
                    else:
                        url = append_path_to_url( baseurl, attrs['path'] )

                    self.setRepoLocation( attrs['repo'], url=url )


def append_path_to_url( url, path ):
    ""
    url = url.rstrip('/').rstrip(os.sep)
    path = normpath( path )

    if not path or path == '.':
        return url
    elif path == '..':
        return dirname( url )
    elif path.startswith('../') or path.startswith('..'+os.sep):
        return pjoin( dirname( url ), path[3:] )
    else:
        return pjoin( url, path )


def adjust_repo_paths( repolist ):
    ""
    for i in range( len( repolist ) ):
        path = remove_top_level_directory( repolist[i][1] )
        repolist[i][1] = path


def remove_top_level_directory( path ):
    ""
    pL = normpath( path ).split( os.sep )
    if len(pL) == 1:
        return '.'
    else:
        return os.sep.join( pL[1:] )


class Manifests:

    def __init__(self):
        ""
        self.groups = []

    def addRepo(self, groupname, reponame, path):
        ""
        grp = self.findGroup( groupname, create=True )
        grp.setRepo( reponame, path )

    def findGroup(self, groupname, create=False):
        ""
        if not groupname:
            if len( self.groups ) > 0:
                return self.groups[0]

        else:
            for grp in self.groups:
                if grp.getName() == groupname:
                    return grp

            if create:
                grp = RepoGroup( groupname )
                self.groups.append( grp )
                return grp

        return None

    def writeToFile(self, fileobj):
        ""
        for grp in self.groups:
            fileobj.write( '[ group '+grp.getName()+' ]\n' )
            for spec in grp.getRepoList():
                fileobj.write( '    repo='+spec['repo'] )
                fileobj.write( ', path='+spec['path'] )
                fileobj.write( '\n' )

            fileobj.write( '\n' )

    def readFromFile(self, fileobj):
        ""
        groupname = None

        for line in fileobj:
            line = line.strip()
            if line.startswith( '#' ):
                pass
            elif line.startswith( '[' ):
                groupname = None
                sL = line.strip('[').strip(']').strip().split()
                if len(sL) == 2 and sL[0] == 'group':
                    groupname = sL[1]
            elif groupname:
                attrs = parse_attribute_line( line )
                if 'repo' in attrs and 'path' in attrs:
                    self.addRepo( groupname, attrs['repo'], attrs['path'] )


def parse_attribute_line( line ):
    ""
    attrs = {}

    kvL = [ s.strip() for s in line.split(',') ]
    for kvstr in kvL:
        kv = [ s.strip() for s in kvstr.split( '=', 1 ) ]
        if len(kv) == 2 and kv[0]:
            attrs[ kv[0] ] = kv[1]

    return attrs


class RepoGroup:

    def __init__(self, groupname):
        ""
        self.name = groupname
        self.repos = []

    def getName(self):
        ""
        return self.name

    def getRepoList(self):
        ""
        return self.repos

    def setRepo(self, reponame, path):
        ""
        spec = self.findRepo( reponame, create=True )
        spec['path'] = path

    def findRepo(self, reponame, create=False):
        ""
        for spec in self.repos:
            if spec['repo'] == reponame:
                return spec

        if create:
            spec = { 'repo':reponame }
            self.repos.append( spec )
            return spec

        return None
