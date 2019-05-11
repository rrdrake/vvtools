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
import subprocess


class GitInterfaceError( Exception ):
    pass


class GitInterface:

    def __init__(self, origin_url=None, rootdir=None, **options):
        """
        If 'origin_url' is not None, then same as clone( origin_url, rootdir ).
        If 'rootdir' is not None, then define it as the root directory on disk.
        Use verbose=True to print the Git commands and output.
        """
        self.root = None
        self._initialize( origin_url, rootdir, options )

    def getRootDir(self):
        ""
        if self.root:
            return self.root

        x,root = self.run( 'rev-parse --show-toplevel',
                           raise_on_error=False, capture=True )

        if x != 0 or not root.strip():
            raise GitInterfaceError( 'could not determine root '
                                     '(are you in a Git repo?)' )

        return root.strip()

    def create(self, rootdir=None, bare=False):
        """
        If 'rootdir' is not None, it is created and will contain the repo.
        """
        self.root = None

        cmd = self.gitexe + ' init'
        if bare:
            cmd += ' --bare'

        if rootdir:
            cd, name = split_and_create_directory( rootdir )
            cmd += ' '+name
            root = normpath( abspath( rootdir ) )
        else:
            cd = None
            root = os.getcwd()

        runcmd( cmd, cd )

        self.root = root

    def clone(self, url, rootdir=None, branch=None, bare=False):
        """
        If 'branch' is None, all branches are fetched.  If a branch name, such
        as "master", then only that branch is fetched.  Returns the url to
        the local clone.

        If 'rootdir' is not None, it will contain the repo on disk.
        """
        self.root = None

        if branch and bare:
            raise GitInterfaceError( 'cannot bare clone a single branch' )

        if branch:
            self._branch_clone( url, rootdir, branch )
        else:
            self._full_clone( url, rootdir, bare )

        return 'file://'+self.root

    def add(self, *files, **kwargs):
        ""
        if len( files ) > 0:
            fL = [ pipes.quote(f) for f in files ]
            self.run( 'add', *fL )

    def commit(self, message):
        ""
        self.run( 'commit -m', pipes.quote(message) )

    def push(self, all_branches=False, all_tags=False, repository=None):
        """
        Pushes current branch by default.
            all_branches=True : push all branches
            all_tags=True : push all tags
            repository=URL : push to this repository (defaults to origin)
        """
        cmd = 'push'

        if all_branches or all_tags:
            if all_branches: cmd += ' --all'
            if all_tags:     cmd += ' --tags'

            if repository:
                cmd += ' '+repository

        else:
            br = self.currentBranch()
            if not br:
                raise GitInterfaceError( 'you must be on a branch to push' )

            if repository:
                cmd += ' '+repository+' '+br
            else:
                cmd += ' origin '+br

        self.run( cmd )

    def pull(self):
        ""
        if self.isBare():
            raise GitInterfaceError( 'cannot pull into a bare repository' )

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

        x,out = self.run( 'branch', capture=True )

        for line in out.splitlines():
            if line.startswith( '* (' ):
                return None  # detatched
            elif line.startswith( '* ' ):
                return line[2:].strip()

        raise GitInterfaceError( 'no branches found, DIR='+str(loc) )

    def listBranches(self, remotes=False):
        ""
        bL = []

        cmd = 'branch'
        if remotes:
            cmd += ' -r'

        x,out = self.run( cmd, capture=True )

        for line in out.splitlines():
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

        x,out = self.run( 'ls-remote --heads', url, capture=True )

        for line in out.strip().splitlines():
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
        x,out = self.run( 'config --get remote.origin.url',
                          raise_on_error=False, capture=True )
        if x != 0:
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

            with change_directory( self.getRootDir() ):
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

    def listTags(self):
        ""
        x,out = self.run( 'tag --list --no-column', capture=True )

        tagL = []

        for line in out.strip().splitlines():
            tag = line.strip()
            if tag:
                tagL.append( tag )

        tagL.sort()

        return tagL

    def gitVersion(self):
        ""
        x,out = self.run( '--version', capture=True )
        return [ int(s) for s in out.strip().split()[2].split('.') ]

    def isBare(self):
        ""
        x,out = self.run( 'rev-parse --is-bare-repository', capture=True )

        val = out.strip().lower()
        if val == 'true':
            return True
        elif val == 'false':
            return False
        else:
            raise GitInterfaceError(
                        'unexpected response from rev-parse: '+str(out) )

    def _full_clone(self, url, rootdir, bare):
        ""
        cmd = 'clone'
        if bare:
            cmd += ' --bare'
        cmd += ' ' + url

        if rootdir:
            with make_and_change_directory( rootdir ):
                self.run( cmd, '.' )
                self.root = os.getcwd()
        else:
            self.run( cmd )

            dname = self._repo_directory_from_url( url, bare )

            assert os.path.isdir( dname )
            self.root = os.path.abspath( dname )

    def _repo_name_from_url(self, url):
        ""
        return os.path.basename( url ).rstrip( '.git' )

    def _repo_directory_from_url(self, url, bare=False):
        ""
        name = self._repo_name_from_url( url )
        if bare:
            return name+'.git'
        else:
            return name

    def _branch_clone(self, url, rootdir, branch):
        ""
        if not rootdir:
            rootdir = self._repo_name_from_url( url )

        with make_and_change_directory( rootdir ):
            self.run( 'init' )
            self.root = os.getcwd()
            self.run( 'remote add -f -t', branch, '-m', branch, 'origin', url )
            self.run( 'checkout', branch )

    def _fetch_then_checkout_branch(self, branchname):
        ""
        self.run( 'fetch origin' )

        x,out = self.run( 'checkout --track origin/'+branchname,
                          raise_on_error=False, capture=True )
        if x != 0:
            # try adding the branch in the fetch list
            x,out2 = self.run( 'config --add remote.origin.fetch ' + \
                               '+refs/heads/'+branchname + \
                               ':refs/remotes/origin/'+branchname,
                               raise_on_error=False, capture=True )
            out += out2

            if x == 0:
                x,out3 = self.run( 'fetch origin',
                                   raise_on_error=False, capture=True )
                out += out3

                if x == 0:
                    x,out4 = self.run( 'checkout --track origin/'+branchname,
                                       raise_on_error=False, capture=True )
                    out += out4

            if x != 0:
                print3( out )
                raise GitInterfaceError( 'branch appears on remote but ' + \
                                'fetch plus checkout failed: '+branchname )

    def _initialize(self, origin_url, rootdir, options):
        ""
        self.envars = {}

        self.gitexe = options.pop( 'gitexe', 'git' )
        self.verbose = options.pop( 'verbose', False )

        prox = options.pop( 'https_proxy', None )
        if prox:
            self.envars['https_proxy'] = prox
            self.envars['HTTPS_PROXY'] = prox

        if len( options ) > 0:
            raise GitInterfaceError( "unknown options: "+str(options) )

        if origin_url:
            self.clone( origin_url, rootdir=rootdir )
        elif rootdir:
            self.root = os.path.abspath( rootdir )

    def run(self, arg0, *args, **kwargs):
        ""
        roe = kwargs.pop( 'raise_on_error', True )
        cap = kwargs.pop( 'capture', False )

        cmdcapture = True
        if not cap and self.verbose:
            cmdcapture = False

        cmd = self.gitexe + ' ' + ' '.join( (arg0,)+args )

        with set_environ( **self.envars ):
            x,out = runcmd( cmd,
                            chdir=self.root,
                            raise_on_error=roe,
                            capture=cmdcapture )

        if cmdcapture and self.verbose:
            print3( cmd + '\n' + out )

        return x, out


def safe_repository_mirror( from_url, to_url, work_clone=None ):
    ""
    work_git = GitInterface()

    if work_clone:

        if os.path.isdir( work_clone ):
            with change_directory( work_clone ):
                mirror_remote_repo_into_pwd( from_url )
                push_branches_and_tags( work_git, to_url )

        else:
            work_git.clone( from_url, rootdir=work_clone, bare=True )
            push_branches_and_tags( work_git, to_url )

    else:
        tdir = tempfile.mkdtemp( dir=os.getcwd() )

        try:
            work_git.clone( from_url, rootdir=tdir, bare=True )
            push_branches_and_tags( work_git, to_url )

        finally:
            shutil.rmtree( tdir )


def mirror_remote_repo_into_pwd( remote_url ):
    ""
    git = GitInterface()

    if not git.isBare():
        raise GitInterfaceError( 'work_clone must be a bare repository' )

    git.run( 'fetch', remote_url,
             '"refs/heads/*:refs/heads/*"',
             '"refs/tags/*:refs/tags/*"' )


def push_branches_and_tags( work_git, to_url ):
    ""
    work_git.push( all_branches=True, repository=to_url )
    work_git.push( all_tags=True, repository=to_url )


########################################################################

class change_directory:

    def __init__(self, directory):
        ""
        self.cwd = os.getcwd()
        self.directory = directory

    def __enter__(self):
        ""
        if self.directory:
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
    runcmd( gitexe + ' init' )

    fL = []
    for pn in pathL:
        fn = copy_path_to_current_directory( pn )
        fL.append( pipes.quote(fn) )

    runcmd( gitexe + ' add ' + ' '.join( fL ) )
    runcmd( gitexe + ' commit -m ' + pipes.quote( message ) )


def runcmd( cmd, chdir=None, raise_on_error=True, capture=True ):
    ""
    out = ''
    x = 1

    with change_directory( chdir ):

        if capture:
            po = subprocess.Popen( cmd, shell=True, stdout=subprocess.PIPE,
                                                    stderr=subprocess.STDOUT )
        else:
            print3( cmd )
            po = subprocess.Popen( cmd, shell=True )

        sout,serr = po.communicate()
        x = po.returncode

        if sout != None:
            out = _STRING_(sout)

    if x != 0 and raise_on_error:
        print3( cmd + '\n' + out )
        raise GitInterfaceError( 'Command failed: '+cmd )

    return x,out


if sys.version_info[0] < 3:
    def _STRING_(b): return b

else:
    bytes_type = type( ''.encode() )

    def _STRING_(b):
        if type(b) == bytes_type:
            return b.decode()
        return b


def print3( *args ):
    sys.stdout.write( ' '.join( [ str(x) for x in args ] ) + '\n' )
    sys.stdout.flush()
