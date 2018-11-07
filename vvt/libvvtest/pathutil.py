#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys


def compute_relative_path(d1, d2):
    """
    Compute relative path from directory d1 to directory d2.
    """
    assert os.path.isabs(d1)
    assert os.path.isabs(d2)

    d1 = os.path.normpath(d1)
    d2 = os.path.normpath(d2)

    list1 = d1.split( os.sep )
    list2 = d2.split( os.sep )

    while True:
        try: list1.remove('')
        except Exception: break
    while True:
        try: list2.remove('')
        except Exception: break

    i = 0
    while i < len(list1) and i < len(list2):
        if list1[i] != list2[i]:
            break
        i = i + 1

    p = []
    j = i
    while j < len(list1):
        p.append('..')
        j = j + 1

    j = i
    while j < len(list2):
        p.append(list2[j])
        j = j + 1

    if len(p) > 0:
        return os.path.normpath( os.sep.join(p) )

    return "."


def relative_execute_directory( xdir, testdir, cwd ):
    """
    Returns the test execute directory relative to the given current working
    directory.
    """
    if testdir == None:
        return xdir

    d = os.path.join( testdir, xdir )
    sdir = issubdir( cwd, d )
    if sdir == None or sdir == "":
        return os.path.basename( xdir )

    return sdir


def issubdir(parent_dir, subdir):
    """
    TODO: test for relative paths
    """
    lp = len(parent_dir)
    ls = len(subdir)
    if ls > lp and parent_dir + '/' == subdir[0:lp+1]:
        return subdir[lp+1:]
    return None
