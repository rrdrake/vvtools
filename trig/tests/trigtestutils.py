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


def create_bare_repo_with_topic_branch():
    ""
    url = create_local_bare_repository( 'subdir' )
    push_file_to_repo( url, 'file.txt', 'file contents' )
    push_new_branch_with_file( url, 'topic', 'file.txt', 'new contents' )

    return url


def create_local_bare_repository( subdir='.', name='example' ):
    ""
    if not os.path.exists( subdir ):
        os.makedirs( subdir )

    cwd = os.getcwd()
    os.chdir( subdir )

    try:
        if not name.endswith( '.git' ):
            name += '.git'

        util.runcmd( 'git init --bare '+name, print_output=False )

        url = 'file://'+os.getcwd()+'/'+name

    finally:
        os.chdir( cwd )

    return url


def push_file_to_repo( url, filename, filecontents ):
    ""
    os.mkdir( 'addfiletemp' )
    cwd = os.getcwd()
    os.chdir( 'addfiletemp' )
    try:
        util.runcmd( 'git clone '+url, print_output=False )

        pL = os.listdir( '.' )
        assert len( pL ) == 1
        os.chdir( pL[0] )

        util.writefile( filename, filecontents )

        util.runcmd( 'git add '+filename, print_output=False )
        util.runcmd( 'git commit -m "push_file_to_repo '+time.ctime()+'"',
                     print_output=False )
        util.runcmd( 'git push origin master', print_output=False )

    finally:
        os.chdir( cwd )

    shutil.rmtree( 'addfiletemp' )


def push_new_branch_with_file( url, branchname, filename, filecontents ):
    ""
    os.mkdir( 'addfiletemp' )
    cwd = os.getcwd()
    os.chdir( 'addfiletemp' )
    try:
        util.runcmd( 'git clone '+url, print_output=False )

        pL = os.listdir( '.' )
        assert len( pL ) == 1
        os.chdir( pL[0] )

        util.runcmd( 'git checkout -b '+branchname, print_output=False )

        util.writefile( filename, filecontents )

        util.runcmd( 'git add '+filename, print_output=False )
        util.runcmd( 'git commit -m "push_new_branch_with_file ' + \
                                                        time.ctime()+'"',
                      print_output=False )
        util.runcmd( 'git push -u origin '+branchname, print_output=False )

    finally:
        os.chdir( cwd )

    shutil.rmtree( 'addfiletemp' )


def create_local_branch( local_directory, branchname ):
    ""
    cwd = os.getcwd()
    os.chdir( local_directory )
    try:
        util.runcmd( 'git checkout -b '+branchname, print_output=False )
    finally:
        os.chdir( cwd )


def checkout_to_previous_sha1( directory ):
    ""
    cwd = os.getcwd()
    os.chdir( directory )
    try:
        util.runcmd( 'git checkout HEAD^1', print_output=False )

    finally:
        os.chdir( cwd )
