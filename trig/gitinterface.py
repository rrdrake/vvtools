#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
from os.path import abspath, normpath
import time
import pipes
import shutil
import tempfile

from command import Command, CommandException


class GitInterfaceError( Exception ):
    pass


class GitInterface:

    def __init__(self, clone_from=None, **options):
        ""
        self._pop_option_values( options )

        self.root = None

        if clone_from:
            self.clone( clone_from )

    def getRootPath(self):
        ""
        if self.root:
            return self.root

        try:
            root = self.runout( 'rev-parse --show-toplevel' ).strip()
        except CommandException:
            raise GitInterfaceError( 'could not determine root '
                                     '(are you in a Git repo?)' )
        return root

    def create(self, directory=None, bare=False):
        """
        If 'directory' is not None, it is created and will contain the repo.
        """
        self.root = None

        cmd = self.gitexe + ' init'
        if bare:
            cmd += ' --bare'

        if directory:
            cd, name = split_and_create_directory( directory )
            cmd += ' '+name
            root = normpath( abspath( directory ) )
        else:
            cd = None
            root = os.getcwd()

        Command( cmd ).run( chdir=cd )

        self.root = root

    def clone(self, url, directory=None, branch=None):
        """
        If 'branch' is None, all branches are fetched.  If a branch name, such
        as "master", then only that branch is fetched.
        """
        self.root = None

        name = os.path.basename( url ).rstrip( '.git' )
        assert name

        if branch:
            self._branch_clone( url, name, directory, branch )
        else:
            self._full_clone( url, name, directory )

    def add(self, *files, **kwargs):
        ""
        if len( files ) > 0:
            fL = [ pipes.quote(f) for f in files ]
            self.run( 'add', *fL )

    def commit(self, message):
        ""
        self.run( 'commit -m', pipes.quote(message) )

    def push(self):
        ""
        self.run( 'push' )

    def pull(self):
        ""
        curbranch = self.currentBranch()

        if curbranch == None:
            raise GitInterfaceError( 'cannot pull when HEAD is detached '
                    ' (which may be due to a previous merge conflict' )

        self.run( 'tag GITINTERFACE_PULL_BACKUP' )

        try:
            self.run( 'pull' )

        except Exception:
            self.run( 'reset --hard GITINTERFACE_PULL_BACKUP' )
            self.run( 'checkout '+curbranch )
            self.run( 'tag -d GITINTERFACE_PULL_BACKUP' )
            raise GitInterfaceError( 'pull failed (probably merge conflict)' )

        self.run( 'tag -d GITINTERFACE_PULL_BACKUP' )

    def currentBranch(self):
        """
        Returns None if in a detached HEAD state.
        """
        loc = ( self.root if self.root else os.getcwd() )

        try:
            out = self.runout( 'branch' )
        except CommandException:
            raise GitInterfaceError(
                    'could not determine current branch, LOCATION='+str(loc) )

        for line in out.splitlines():
            if line.startswith( '* (' ):
                return None  # detatched
            elif line.startswith( '* ' ):
                return line[2:].strip()

        raise GitInterfaceError( 'no branches found, LOCATION='+str(loc) )

    def listBranches(self, remotes=False):
        ""
        bL = []

        cmd = 'branch'
        if remotes:
            cmd += ' -r'

        for line in self.runout( cmd ).splitlines():
            if line.startswith( '* (' ):
                pass
            elif line.startswith( '* ' ) or line.startswith( '  ' ):
                if ' -> ' not in line:
                    line = line[2:]
                    if line.startswith( 'origin/' ):
                        line = line[7:]
                    bL.append( line )

        bL.sort()
        return bL

    def listRemoteBranches(self, url=None):
        """
        Get the list of branches on the remote repository 'url'.  The list is
        independent of the state of the local repository, if any.  If 'url' is
        None, then the URL of the current repository is used.
        """
        if url == None:
            url = self.getRemoteURL()
            if not url:
                raise GitInterfaceError( 'url not given and no local url found' )

        bL = []

        for line in self.runout( 'ls-remote --heads', url ).splitlines():
            lineL = line.strip().split( None, 1 )
            if len( lineL ) == 2:
                if lineL[1].startswith( 'refs/heads/' ):
                    bL.append( lineL[1][11:] )

        bL.sort()
        return bL

    def checkoutBranch(self, branchname):
        ""
        if branchname != self.currentBranch():
            if branchname in self.listBranches():
                self.run( 'checkout', branchname )
            elif branchname in self.listBranches( remotes=True ):
                self.run( 'checkout --track origin/'+branchname )
            elif branchname in self.listRemoteBranches():
                self._fetch_then_checkout_branch( branchname )
            else:
                raise GitInterfaceError( 'branch does not exist: '+branchname )

    def getRemoteURL(self):
        ""
        try:
            out = self.runout( 'config --get remote.origin.url' )
        except CommandException:
            return None
        return out.strip()

    def createRemoteBranch(self, branchname):
        """
        Create a branch on the remote, checkout, and track it locally.
        Any local changes are not pushed, but are merged onto the new branch.
        """
        curbranch = self.currentBranch()

        if branchname in self.listRemoteBranches():
            raise GitInterfaceError(
                    'branch name already exists on remote: '+branchname )

        if curbranch not in self.listBranches( remotes=True ):
            raise GitInterfaceError(
                    'current branch must be tracking a remote: '+curbranch )

        self.run( 'branch', branchname, 'origin/'+curbranch )
        self.run( 'checkout', branchname )
        self.run( 'push -u origin', branchname )
        self.run( 'merge', curbranch )

    def createRemoteOrphanBranch(self, branchname, message, path0, *paths):
        """
        Create and push a branch containing a copy of the given paths
        (files and/or directories), with the given intial commit message.
        It will share no history with any other branch.
        """
        if not self.currentBranch():
            raise GitInterfaceError( 'must currently be on a branch' )

        if branchname in self.listRemoteBranches():
            raise GitInterfaceError(
                    'branch name already exists on remote: '+branchname )

        # newer versions of git have a git checkout --orphan option; the
        # implementation here creates a temporary repo with an initial
        # commit then fetches that into the current repository

        pathL = [ os.path.abspath(p) for p in (path0,)+paths ]

        tmpdir = tempfile.mkdtemp( '.gitinterface' )
        try:
            with change_directory( tmpdir ):
                create_repo_with_these_files( self.gitexe, message, pathL )

            with change_directory( self.getRootPath() ):
                self.run( 'fetch', tmpdir, 'master:'+branchname )
                self.run( 'checkout', branchname )
                self.run( 'push -u origin', branchname )

        finally:
            shutil.rmtree( tmpdir )

    def deleteRemoteBranch(self, branchname):
        ""
        curbranch = self.currentBranch()
        if branchname == curbranch:
            raise GitInterfaceError(
                    'cannot delete current branch: '+branchname )

        if branchname not in self.listRemoteBranches():
            raise GitInterfaceError(
                    'branch name does not exist on remote: '+branchname )

        if branchname in self.listBranches():
            self.run( 'branch -d', branchname )

        self.run( 'push --delete origin', branchname )

    def gitVersion(self):
        ""
        out = Command( self.gitexe, '--version' ).run_output( echo='none' )
        return [ int(s) for s in out.split()[2].split('.') ]

    def _full_clone(self, url, name, directory):
        ""
        if directory:
            with make_and_change_directory( directory ):
                self.run( 'clone', url, '.' )
                self.root = os.getcwd()
        else:
            self.run( 'clone', url )
            assert os.path.isdir( name )
            self.root = os.path.abspath( name )

    def _branch_clone(self, url, name, directory, branch):
        ""
        if not directory:
            directory = name

        with make_and_change_directory( directory ):
            self.run( 'init' )
            self.root = os.getcwd()
            self.run( 'remote add -f -t', branch, '-m', branch, 'origin', url )
            self.run( 'checkout', branch )

    def _fetch_then_checkout_branch(self, branchname):
        ""
        self.run( 'fetch origin' )
        try:
            self.run( 'checkout --track origin/'+branchname )
        except CommandException:
            try:
                # try adding the branch in the fetch list
                self.run( 'config --add remote.origin.fetch ' + \
                                '+refs/heads/'+branchname + \
                                ':refs/remotes/origin/'+branchname )
                self.run( 'fetch origin' )
                self.run( 'checkout --track origin/'+branchname )
            except CommandException:
                raise GitInterfaceError( 'branch appears on remote but ' + \
                                'fetch plus checkout failed: '+branchname )

    def _pop_option_values(self, options):
        ""
        self.envars = {}

        self.gitexe = options.pop( 'gitexe', 'git' )

        prox = options.pop( 'https_proxy', None )
        if prox:
            self.envars['https_proxy'] = prox
            self.envars['HTTPS_PROXY'] = prox

        if len( options ) > 0:
            raise GitInterfaceError( "unknown options: "+str(options) )

    def run(self, arg0, *args, **kwargs):
        ""
        cmd = Command( self.gitexe + ' ' + ' '.join( (arg0,)+args ) )
        with set_environ( **self.envars ):
            cmd.run( chdir=self.root )

    def runout(self, arg0, *args, **kwargs):
        ""
        cmd = Command( self.gitexe + ' ' + ' '.join( (arg0,)+args ) )
        with set_environ( **self.envars ):
            out = cmd.run_output( chdir=self.root )
        return out


########################################################################

class change_directory:

    def __init__(self, directory):
        ""
        self.cwd = os.getcwd()
        self.directory = directory

    def __enter__(self):
        ""
        assert os.path.isdir( self.directory )
        os.chdir( self.directory )

    def __exit__(self, type, value, traceback):
        ""
        os.chdir( self.cwd )


class make_and_change_directory( change_directory ):

    def __enter__(self):
        ""
        if not os.path.exists( self.directory ):
            os.makedirs( self.directory )

        change_directory.__enter__( self )


class set_environ:

    def __init__(self, **name_value_pairs):
        """
        If the value is None, the name is removed from os.environ.
        """
        self.pairs = name_value_pairs

    def __enter__(self):
        ""
        self.save_environ = dict( os.environ )

        for n,v in self.pairs.items():
            if v == None:
                if n in os.environ:
                    del os.environ[n]
            else:
                os.environ[n] = v

    def __exit__(self, type, value, traceback):
        ""
        for n,v in self.pairs.items():
            if n in self.save_environ:
                os.environ[n] = self.save_environ[n]
            elif v != None:
                del os.environ[n]


def split_and_create_directory( repo_path ):
    ""
    path,name = os.path.split( os.path.normpath( repo_path ) )

    if path == '.':
        path = ''

    if path and not os.path.exists( path ):
        os.makedirs( path )

    return path, name


def copy_path_to_current_directory( filepath ):
    ""
    bn = os.path.basename( filepath )

    if os.path.islink( filepath ):
        os.symlink( os.readlink( filepath ), bn )
    elif os.path.isdir( filepath ):
        shutil.copytree( filepath, bn, symlinks=True )
    else:
        shutil.copyfile( filepath, bn )

    return bn


def create_repo_with_these_files( gitexe, message, pathL ):
    ""
    Command( '$gitexe init' ).run()

    fL = []
    for pn in pathL:
        fn = copy_path_to_current_directory( pn )
        fL.append( fn )

    cmd = Command( '$gitexe add' ).escape( *fL ).run()
    cmd = Command( '$gitexe commit -m').escape( message ).run()


def print3( *args ):
    sys.stdout.write( ' '.join( [ str(x) for x in args ] ) + '\n' )
    sys.stdout.flush()
