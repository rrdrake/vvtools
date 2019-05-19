#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import time
import subprocess
import shutil
import unittest

import testutils as util

testsrcdir = os.path.dirname( os.path.abspath( sys.argv[0] ) )
sys.path.insert( 0, os.path.dirname( testsrcdir ) )


class trigTestCase( unittest.TestCase ):

    def setUp(self, cleanout=True):
        ""
        util.setup_test( cleanout )

    def tearDown(self):
        ""
        pass


def get_process_list():
    """
    Return a python list of all processes on the current machine, where each
    entry is a length three list of form

        [ user, pid, ppid ]
    """
    plat = sys.platform.lower()
    if plat.startswith( 'darwin' ):
        cmd = 'ps -o user,pid,ppid'
    else:
        cmd = 'ps -o user,pid,ppid'
    cmd += ' -e'

    p = subprocess.Popen( 'ps -o user,pid,ppid -e',
                          shell=True, stdout=subprocess.PIPE )
    sout,serr = p.communicate()

    sout = util._STRING_(sout)

    # strip off first non-empty line (the header)

    first = True
    lineL = []
    for line in sout.split( os.linesep ):
        line = line.strip()
        if line:
            if first:
                first = False
            else:
                L = line.split()
                if len(L) == 3:
                    try:
                        L[1] = int(L[1])
                        L[2] = int(L[2])
                    except Exception:
                        pass
                    else:
                        lineL.append( L )

    return lineL


def find_process_in_list( proclist, pid ):
    """
    Searches for the given 'pid' in 'proclist' (which should be the output
    from get_process_list().  If not found, None is returned.  Otherwise a
    list

        [ user, pid, ppid ]
    """
    for L in proclist:
        if pid == L[1]:
            return L
    return None


def create_bare_repo_with_topic_branch( reponame, subdir=None, tag=None ):
    ""
    url = create_local_bare_repository( reponame )
    push_file_to_repo( url, 'file.txt', 'file contents' )
    push_new_branch_with_file( url, 'topic', 'file.txt', 'new contents' )

    if tag:
        push_tag_to_repo( url, tag )

    return url


def create_local_bare_repository( reponame, subdir=None ):
    ""
    if not subdir:
        subdir = 'bare_repo_'+util.random_string()

    if not os.path.exists( subdir ):
        os.makedirs( subdir )

    with util.change_directory( subdir ):

        if not reponame.endswith( '.git' ):
            reponame += '.git'

        util.runcmd( 'git init --bare '+reponame, print_output=False )

        url = 'file://'+os.getcwd()+'/'+reponame

    return url


def push_file_to_repo( url, filename, filecontents ):
    ""
    workdir = 'wrkdir_'+util.random_string()
    os.mkdir( workdir )

    with util.change_directory( workdir ):

        util.runcmd( 'git clone '+url, print_output=False )

        os.chdir( util.globfile( '*' ) )

        util.writefile( filename, filecontents )

        util.runcmd( 'git add '+filename, print_output=False )
        util.runcmd( 'git commit -m "push_file_to_repo '+time.ctime()+'"',
                     print_output=False )
        util.runcmd( 'git push origin master', print_output=False )


def push_tag_to_repo( url, tagname ):
    ""
    workdir = 'wrkdir_'+util.random_string()
    os.mkdir( workdir )

    with util.change_directory( workdir ):

        util.runcmd( 'git clone '+url, print_output=False )

        os.chdir( util.globfile( '*' ) )

        util.runcmd( 'git tag '+tagname, print_output=False )
        util.runcmd( 'git push origin '+tagname, print_output=False )


def push_new_branch_with_file( url, branchname, filename, filecontents ):
    ""
    workdir = 'wrkdir_'+util.random_string()
    os.mkdir( workdir )

    with util.change_directory( workdir ):

        util.runcmd( 'git clone '+url, print_output=False )

        os.chdir( util.globfile( '*' ) )

        util.runcmd( 'git checkout -b '+branchname, print_output=False )

        util.writefile( filename, filecontents )

        util.runcmd( 'git add '+filename, print_output=False )
        util.runcmd( 'git commit -m "push_new_branch_with_file ' + \
                                                        time.ctime()+'"',
                      print_output=False )
        util.runcmd( 'git push -u origin '+branchname, print_output=False )


def create_local_branch( local_directory, branchname ):
    ""
    with util.change_directory( local_directory ):
        util.runcmd( 'git checkout -b '+branchname, print_output=False )


def checkout_to_previous_sha1( directory ):
    ""
    with util.change_directory( directory ):
        util.runcmd( 'git checkout HEAD^1', print_output=False )
