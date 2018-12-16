#!/usr/bin/env python

import os, sys
import time
import tempfile
import shutil

from gitinterface import GitInterface, change_directory


class ResultsHandler:
    
    def __init__(self, gitinterface_obj):
        ""
        self.git = gitinterface_obj

    def setNamingScheme(self, epochdate=None, granularity='month'):
        ""
        bn,sb = branch_name_and_directory( epochdate, granularity )

        self.branch = bn
        self.subdir = sb

        return bn, sb

    def createResultsDirectory(self):
        """
        Create or checkout results directory according to the naming scheme.
        Returns absolute path to the results directory.
        """
        with change_directory( self.git.getRootPath() ):

            if self.branch in self.git.listRemoteBranches():

                self.git.checkoutBranch( self.branch )

                if not os.path.exists( self.subdir ):
                    os.mkdir( self.subdir )

            else:
                create_orphan_branch( self.git, self.branch, self.subdir )

            rdir = os.path.abspath( self.subdir )

        assert os.path.isdir( rdir )
        return rdir

    def pushResults(self, commit_message):
        ""
        self.git.add( self.subdir )
        self.git.commit( commit_message )
        self.git.push()


def branch_name_and_directory( epochdate=None, granularity='month'):
    ""
    assert granularity == 'month'

    if epochdate == None:
        epochdate = time.time()

    tup = time.localtime(epochdate)
    branch = time.strftime( "results_%Y_%m", tup )
    subdir = time.strftime( "%d_%H", tup )

    return branch, subdir


#########################################################################

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
