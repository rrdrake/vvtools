#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import getopt
import re
from os.path import join as pjoin
from os.path import abspath

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
        cfg = create_config_from_url_list( urls, directory )
        clone_repositories( cfg )


def clone_repositories( cfg ):
    ""
    root = cfg.getRootDir()

    if not os.path.isdir( root ):
        os.mkdir( root )

    with gititf.change_directory( root ):
        git = gititf.GitInterface()
        for url,loc in cfg.getLayout():
            git.clone( url, loc )


def parse_url_list( args ):
    ""
    directory = None

    if len(args) == 1 or is_a_repository_url( args[-1] ):
        urls = list( args )
    else:
        urls = args[:-1]
        directory = args[-1]

    urls = adjust_local_repository_urls( urls )

    return urls, directory


def create_config_from_url_list( urls, directory=None ):
    ""
    cfg = Configuration()

    if directory:
        cfg.setRootDir( directory )

    mfest = Manifests()
    cfg.setManifests( mfest )

    groupname = None
    for i,url in enumerate(urls):
        name = gititf.repo_name_from_url( url )
        if i == 0:
            groupname = name
            path = name
        else:
            path = pjoin( groupname, name )

        mfest.addRepo( groupname, name, path )
        cfg.setRepoURL( name, url )

    return cfg



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
        self.rootdir = None
        self.mfest = None
        self.repomap = {}

    def setRootDir(self, directory):
        ""
        self.rootdir = os.path.abspath( directory )

    def getRootDir(self):
        ""
        if self.rootdir:
            return self.rootdir
        else:
            grp = self.mfest.findGroup( None )
            return grp.getName()

    def setManifests(self, manifests):
        ""
        self.mfest = manifests

    def setRepoURL(self, reponame, repourl):
        ""
        self.repomap[ reponame ] = repourl

    def getLayout(self):
        ""
        grp = self.mfest.findGroup( None )

        repolist = []
        for spec in grp.getRepoList():
            url = self.repomap[ spec['name'] ]
            repolist.append( [ url, spec['path'] ] )

        adjust_repo_paths( repolist )

        return repolist

    def writeManifestsToFile(self, fileobj):
        ""
        self.mfest.writeToFile( fileobj )

    def writeConfigToFile(self, fileobj):
        ""
        for name,url in self.repomap.items():
            fileobj.write( 'repo='+name )
            fileobj.write( ', url='+url )
            fileobj.write( '\n' )
        fileobj.write( '\n' )


def adjust_repo_paths( repolist ):
    ""
    for i in range( len( repolist ) ):
        path = remove_top_level_directory( repolist[i][1] )
        repolist[i][1] = path


def remove_top_level_directory( path ):
    ""
    pL = os.path.normpath( path ).split( os.sep )
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
                fileobj.write( '    repo='+spec['name'] )
                fileobj.write( ', path='+spec['path'] )
                fileobj.write( '\n' )

            fileobj.write( '\n' )


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
            if spec['name'] == reponame:
                return spec

        if create:
            spec = { 'name':reponame }
            self.repos.append( spec )
            return spec

        return None


def create_mrgit_repository( repodir, cfg ):
    ""
    git = gititf.GitInterface()
    git.create( repodir )

    with open( repodir+'/manifests', 'w' ) as fp:
        cfg.writeManifestsToFile( fp )

    git.add( 'manifests' )
    git.commit( 'init manifests' )

    git.createBranch( 'mrgit_config' )
    with open( repodir+'/config', 'w' ) as fp:
        cfg.writeConfigToFile( fp )

    git.add( 'config' )
    git.commit( 'init config' )
    git.checkoutBranch( 'master' )


def adjust_local_repository_urls( urls ):
    ""
    newurls = []
    for url in urls:
        if os.path.isdir( url ) and gititf.is_a_local_repository( url ):
            newurls.append( abspath( url ) )
        else:
            newurls.append( url )

    return newurls


# match the form [user@]host.xz:path/to/repo.git/
scp_like_url = re.compile( r'([a-zA-Z0-9_]+@)?[a-zA-Z0-9_]+([.][a-zA-Z0-9_]*)*:' )

def is_a_repository_url( url ):
    ""
    if os.path.isdir( url ):
        if gititf.is_a_local_repository( url ):
            return True

    elif url.startswith( 'http://' ) or url.startswith( 'https://' ) or \
         url.startswith( 'ftp://' ) or url.startswith( 'ftps://' ) or \
         url.startswith( 'ssh://' ) or \
         url.startswith( 'git://' ) or \
         url.startswith( 'file://' ):
        return True

    elif scp_like_url.match( url ):
        return True

    return False
