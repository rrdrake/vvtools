#!/usr/bin/env python

import os, sys
from os.path import join as pjoin
from os.path import basename
import time
import tempfile
import shutil
import re

from gitinterface import GitInterface, GitInterfaceError
from gitinterface import change_directory, print3


class GitResults:

    def __init__(self, results_repo_url, working_directory=None):
        ""
        self.git = clone_results_repo( results_repo_url,
                                       working_directory,
                                       'master' )

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

        print3( 'Using directory', self.subdir, 'on branch', branch )

        rdir = get_results_orphan_branch( self.git, branch, self.subdir )
        assert os.path.isdir( rdir )

        return rdir

    def pushResults(self, message):
        ""
        branch = self.git.currentBranch()

        print3( 'Pushing results...' )
        self.git.add( self.subdir )
        self.git.commit( message )
        resilient_commit_push( self.git )

        return branch

    def cleanup(self):
        ""
        check_remove_directory( self.git.getRootDir() )


class GitResultsReader:

    def __init__(self, results_repo_url, working_directory=None):
        ""
        self.git = clone_results_repo( results_repo_url, working_directory )

    def iterateDirectories(self):
        ""
        top = self.git.getRootDir()

        for branch in self.iterateBranches():
            self.git.checkoutBranch( branch )
            for dn in self._iterate_results_dirs( top ):
                yield branch,dn

    def iterateBranches(self):
        ""
        for branch in self.git.listRemoteBranches():
            if GitResultsReader.branchpat.match( branch ):
                yield branch

    def cleanup(self):
        ""
        check_remove_directory( self.git.getRootDir() )

    branchpat = re.compile( 'results_2[01][0-9][0-9]_[0123][0-9]' )
    dirpat = re.compile( '2[01][0-9][0-9]_[0123][0-9].*' )

    def _iterate_results_dirs(self, topdir):
        ""
        for pn in os.listdir( topdir ):
            if GitResultsReader.dirpat.match( pn ):
                dn = pjoin( topdir, pn )
                if self._summary_file_exists( dn ):
                    yield dn

    def _summary_file_exists(self, dirname):
        """
        a README.md has been used since Aug 2019, before it was TestResults.md
        """
        fn1 = pjoin( dirname, 'README.md' )
        fn2 = pjoin( dirname, 'TestResults.md' )
        if os.path.isfile( fn1 ) or os.path.isfile( fn2 ):
            return True
        else:
            return False


class ResultsSummary:

    def __init__(self, giturl, branch, results_directory):
        ""
        self.url = giturl
        self.branch = branch
        self.rdir = results_directory

        self.cnts = {}
        self.anchors = {}

        self._parse_readme()

    def getDateStamp(self):
        ""
        ts = basename( self.rdir ).split('.',1)[0]
        tm = time.mktime( time.strptime( ts, "%Y_%m_%d_%H" ) )
        return tm

    def getLabel(self):
        ""
        ls = basename( self.rdir ).split('.',1)[1]
        return ls

    def getCounts(self):
        ""
        return self.cnts

    def getResultsLink(self, result=None):
        """
        https://gitlab.cool.com/space/proj/blob/branch/resultsdir/README.md
            #tests-that-pass-34
        """
        loc = map_git_url_to_web_url( self.url )

        bdir = basename( self.rdir )
        lnk = pjoin( loc, 'blob', self.branch, bdir, self.readme )

        if result:
            lnk += '#tests-that-'+result.lower()+'-'+str( self.cnts[result] )

        return lnk

    def _parse_readme(self):
        ""
        self.readme,fn = self._probe_readme_name()

        with open( fn, 'rt' ) as fp:
            for line in fp:
                if line.startswith( ResultsSummary.cntmark ):
                    try:
                        res,cnt = self._header_line_result_and_count( line )
                    except Exception:
                        pass
                    else:
                        self.cnts[res] = cnt
                        self.anchors[res] = self._header_line_to_anchor( line )

    def _probe_readme_name(self):
        ""
        readme = 'README.md'
        fn = pjoin( self.rdir, readme )

        if not os.path.exists( fn ):
            readme = 'TestResults.md'
            fn = pjoin( self.rdir, readme )
            assert os.path.exists( fn ), \
                'A README.md or TestResults.md must exist in '+self.rdir

        return readme,fn

    cntmark = '## Tests that '
    mlen = len( cntmark )

    def _header_line_result_and_count(self, line):
        ""
        res,cnt = line[ ResultsSummary.mlen : ].split('=',1)
        res = res.strip()
        assert res
        cnt = int( cnt )

        return res,cnt

    def _header_line_to_anchor(self, line):
        """
        try to duplicate GitLab algorithm (good enough) to make a header anchor
        """
        s1 = line[3:].strip().replace( '=', '' )
        s2 = ' '.join( s1.split() )
        s3 = s2.lower()

        return s3


def map_git_url_to_web_url( giturl ):
    ""
    loc = giturl
    if giturl.endswith( '.git' ):
        loc = giturl[:-4]

    if loc.startswith( 'git@' ):
        loc = loc[4:]
        apL = loc.split( ':', 1 )
        if len(apL) == 2:
            loc = '/'.join( apL )
        loc = 'https://'+loc

    return loc


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


def clone_results_repo( giturl, working_directory, branch=None ):
    ""
    assert giturl and giturl == giturl.strip()

    if not working_directory:
        working_directory = os.getcwd()

    tmpdir = tempfile.mkdtemp( '', 'gitresults_work_clone_', os.getcwd() )

    git = GitInterface()

    print3( 'Cloning', giturl, 'into', tmpdir )
    git.clone( giturl, tmpdir, branch='master' )

    return git


def resilient_commit_push( git ):
    ""
    err = ''

    for i in range(3):
        try:
            git.push()
        except GitInterfaceError as e:
            err = str(e)
        else:
            err = ''
            break

        git.pull()

    if err:
        raise GitInterfaceError( 'could not push results: '+err )
