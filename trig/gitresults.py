#!/usr/bin/env python

import os, sys
import time
import tempfile
import shutil

from gitinterface import GitInterface, change_directory, print3


class GitResults:

    def __init__(self, results_repo_url, working_directory=None):
        ""
        if not working_directory:
            working_directory = os.getcwd()

        tmpdir = tempfile.mkdtemp( '', 'gitresults_work_clone_', os.getcwd() )

        self.git = GitInterface()

        print3( 'Cloning', results_repo_url, 'into', tmpdir )
        self.git.clone( results_repo_url, tmpdir, branch='master' )

    def getCloneDirectory(self):
        ""
        return self.git.getRootDir()

    def createBranchLocation(self, directory_suffix='',
                                   epochdate=None,
                                   granularity='month'):
        ""
        branch,self.subdir = branch_name_and_directory(
                                directory_suffix,
                                epochdate,
                                granularity )

        print3( 'Using directory', branch, 'on branch', self.subdir )

        rdir = get_results_orphan_branch( self.git, branch, self.subdir )
        assert os.path.isdir( rdir )

        return rdir

    def pushResults(self, message):
        ""
        branch = self.git.currentBranch()

        print3( 'Pushing results...' )
        self.git.add( self.subdir )
        self.git.commit( message )
        self.git.push()

        return branch

    def cleanup(self):
        ""
        check_remove_directory( self.git.getRootDir() )


def get_results_orphan_branch( git, branch, subdir ):
    ""
    with change_directory( git.getRootDir() ):

        if branch in git.listRemoteBranches():

            git.checkoutBranch( branch )

            if not os.path.exists( subdir ):
                os.mkdir( subdir )

        else:
            create_orphan_branch( git, branch, subdir )

        rdir = os.path.abspath( subdir )

    return rdir


def check_remove_directory( dirpath ):
    ""
    if os.path.exists( dirpath ):
        print3( 'rm -r '+dirpath )
        shutil.rmtree( dirpath )


def branch_name_and_directory( subdir_suffix='',
                               epochdate=None,
                               granularity='month'):
    ""
    assert granularity == 'month'

    if epochdate == None:
        epochdate = time.time()

    tup = time.localtime(epochdate)
    branch = time.strftime( "results_%Y_%m", tup )
    subdir = time.strftime( "%Y_%m_%d_%H", tup )

    if subdir_suffix:
        subdir += '.'+subdir_suffix

    return branch, subdir


def create_orphan_branch( git, branchname, resultsdir ):
    ""
    tmpdir = tempfile.mkdtemp( '.gitresults' )
    try:
        rdir = os.path.join( tmpdir, resultsdir )
        rfile = os.path.join( rdir, '.create' )

        os.mkdir( rdir )

        with open( rfile, 'w' ) as fp:
            fp.write( time.ctime() + '\n' )

        cmtmsg = "Start results branch"
        git.createRemoteOrphanBranch( branchname, cmtmsg, rdir )

    finally:
        shutil.rmtree( tmpdir )
