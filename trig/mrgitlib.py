#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import getopt
import re
import tempfile
import shutil
from os.path import join as pjoin
from os.path import abspath
from os.path import normpath

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
            create_local_config_from_url_list( cfg, urls, directory )
            clone_repositories( cfg )

        cfg.commitState()


# magic: overlap
#   - the initial clone uses the remote URLs, but the local layout
#   - the local config written to mrgit_config is not the same as the
#     one used to clone the repositories
#   - maybe having the repo map and manifests in the same object, the
#     Configuration, is the wrong concept; keep those two seperate

def clone_repositories( cfg ):
    ""
    topdir = cfg.getTopDir()

    if not os.path.isdir( topdir ):
        os.mkdir( topdir )

    with gititf.change_directory( topdir ):
        git = gititf.GitInterface()
        for url,loc in get_repo_layout( cfg ):
            git.clone( url, loc )

    cfg.createRepo()


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


def create_local_config_from_url_list( cfg, urls, directory=None ):
    ""
    rmap = cfg.rmap
    mfest = cfg.mfest

    groupname = None
    for i,url in enumerate(urls):
        name = gititf.repo_name_from_url( url )
        if i == 0:
            groupname = name
            path = name
        else:
            path = pjoin( groupname, name )

        mfest.addRepo( groupname, name, path )
        rmap.setRepoURL( name, url )

    cfg.setTopDir( directory )


def clone_from_single_url( cfg, url, directory ):
    ""
    if directory and not os.path.exists( directory ):
        os.mkdir( directory )

    tmprepo = make_temp_repo_dir( directory )

    git = gititf.GitInterface( url, tmprepo )

    if check_load_mrgit_repo( cfg, git, directory ):

        cfg.setTopDir( directory )

        topdir = cfg.getTopDir()

        if not os.path.exists( topdir ):
            os.mkdir( topdir )

        os.rename( tmprepo, topdir+'/.mrgit' )

        if not directory:
            shutil.rmtree( os.path.dirname( tmprepo ) )

        # magic: need to checkout, modify the config, and commit

        # print ( 'magic: root', rootdir )
        # for url,path in get_repo_layout( rmap, mfest ):
        #     print ( 'magic: url path', url, path )

    else:
        create_local_config_from_url_list( cfg, [ url ], directory )

        move_repo( tmprepo, cfg.getTopDir() )

        if not directory:
            shutil.rmtree( os.path.dirname( tmprepo ) )

        cfg.createRepo()

    # tmprepo = directory / random string
    # or
    # tmprepo = random string / random string
    # quietly checkout url+'/.mrgit' into tmprepo
    # if ok:
    #     construct Configuration from mrgit data
    #     move tmprepo to .mrgit subdir
    # else:
    #     pass
    # try checking out urls[0]+'/.mrgit' or '/.mrgit.git'
    # else checkout urls[0]


def check_load_mrgit_repo( cfg, git, directory ):
    ""
    rmap = cfg.rmap
    mfest = cfg.mfest

    mfestfn = pjoin( git.getRootDir(), 'manifests' )
    rmapfn = pjoin( git.getRootDir(), 'config' )

    if os.path.isfile( mfestfn ):
        if 'mrgit_config' in git.listBranches() or \
           'mrgit_config' in git.listRemoteBranches():

            with open( mfestfn, 'r' ) as fp:
                mfest.readFromFile( fp )

            try:
                git.checkoutBranch( 'mrgit_config' )
                with open( rmapfn, 'r' ) as fp:
                    rmap.readFromFile( fp )

            finally:
                git.checkoutBranch( 'master' )

            return True

    return False


def move_repo( fromdir, todir ):
    ""
    if not os.path.exists( todir ):
        os.rename( fromdir, todir )
    else:
        for fn in os.listdir( fromdir ):
            frompath = pjoin( fromdir, fn )
            shutil.move( frompath, todir )
        shutil.rmtree( fromdir )


def make_temp_repo_dir( directory ):
    ""
    if directory:
        tmpdir = tempfile.mkdtemp( '', 'mrgit_tempclone_', abspath(directory) )
    else:
        tmpdir1 = tempfile.mkdtemp( '', 'mrgit_tempclone_', os.getcwd() )
        tmpdir  = tempfile.mkdtemp( '', 'mrgit_tempclone_', tmpdir1 )

    return tmpdir


# create .mrgit repository
# create mrgit_config branch
# create & commit .mrgit/config file on the mrgit_config branch
#    [ remote "origin" ]
#        manifests = git@gitlab.sandia.gov:rrdrake/manifests.git
#        base-url-0 = sierra-git.sandia.gov:/git/
#    but manifests is None (because was not cloned from a manifests)
#    and the base-urls are the ones from the command line
# create & commit .mrgit/manifests file on the master branch
#    [ group cool ]
#        repo=cool, base-url=0, path=cool
#        repo=ness, base-url=1, path=cool/ness


class Configuration:

    def __init__(self):
        ""
        self.topdir = None
        self.rmap = RepoMap()
        self.mfest = Manifests()

    def setTopDir(self, directory):
        ""
        if directory:
            self.topdir = abspath( normpath( directory ) )
        else:
            grp = self.mfest.findGroup( None )
            self.topdir = abspath( grp.getName() )

    def getTopDir(self):
        ""
        return self.topdir

    def commitState(self):
        ""
        pass
        # topdir = rmap.getTopDir()

        # git = GitInterface( rootdir=topdir+'/.mrgit' )
        # git.checkoutBranch( 'mrgit_config' )

        # repos = list( rmap.getRepoURLs() )
        # for repo,url in repos:
        #     s
        #     rmap.setRepoURL( repo, )

    def createRepo(self):
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
            self.rmap.writeToFile( fp )

        git.add( 'config' )
        git.commit( 'init config' )
        git.checkoutBranch( 'master' )


class RepoMap:

    def __init__(self):
        ""
        self.repomap = {}

    def setRepoURL(self, reponame, repourl):
        ""
        self.repomap[ reponame ] = repourl

    def getRepoURL(self, reponame):
        ""
        return self.repomap[ reponame ]

    def writeToFile(self, fileobj):
        ""
        for name,url in self.repomap.items():
            fileobj.write( 'repo='+name )
            fileobj.write( ', url='+url )
            fileobj.write( '\n' )
        fileobj.write( '\n' )

    def readFromFile(self, fileobj):
        ""
        for line in fileobj:
            line = line.strip()
            if line.startswith('#'):
                pass
            elif line:
                attrs = parse_attribute_line( line )
                if 'repo' in attrs and 'url' in attrs:
                    self.setRepoURL( attrs['repo'], attrs['url'] )


def get_repo_layout( cfg ):
    ""
    rmap = cfg.rmap
    mfest = cfg.mfest

    grp = mfest.findGroup( None )

    repolist = []
    for spec in grp.getRepoList():
        url = rmap.getRepoURL( spec['repo'] )
        repolist.append( [ url, spec['path'] ] )

    adjust_repo_paths( repolist )

    return repolist


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
