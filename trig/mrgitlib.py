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

        if len(argL) == 1 or is_a_repository_url( argL[-1] ):
            urls = argL
            indir = gititf.repo_name_from_url( urls[0] )
        else:
            urls = argL[:-1]
            indir = argL[-1]

        urls = adjust_local_repository_urls( urls )

        if not os.path.isdir( indir ):
            os.mkdir( indir )

        with gititf.change_directory( indir ):
            gititf.GitInterface( urls[0], '.' )
            for url in urls[1:]:
                gititf.GitInterface( url )


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



def adjust_local_repository_urls( urls ):
    ""
    newurls = []
    for url in urls:
        if os.path.isdir( url ) and gititf.is_a_local_repository( url ):
            newurls.append( abspath( url ) )
        else:
            newurls.append( url )

    return newurls


# regex matching start of the form [user@]host.xz:path/to/repo.git/
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
