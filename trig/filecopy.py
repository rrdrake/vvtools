#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import time
import re
import shutil
import pipes
import subprocess
import traceback

import remotepython as rpy
print3 = rpy.print3

import perms


helpstr = \
"""
USAGE:
    filecopy.py [OPTIONS] [machine:]source_paths [machine:]to_directory

SYNOPSIS:
    Copy one or more files (or directories) to the directory 'to_directory'.
    The source files or the destination directory can be prefixed with a
    machine name, but not both.  The 'source_paths' can be shell glob patterns.

    Remote file operations are performed using ssh, so password-less ssh
    operations are necessary.

OPTIONS:
    -h, --help             : this help

    --fperms <spec>        : set or adjust file permissions on files placed
                             into the destination directory; may be repeated
                             and multiple specs can be separated by white space;
                             examples:
                                o=-     : set world permissions to none
                                g=r-x   : set group to read, no write, execute
                                g+rx    : add read & execute to group
                                o-w     : remove write to world
                                u+x     : add execute to owner
    --dperms <spec>        : same as --fperms except applied only to
                             directories
    --group                : change the group of all files and directories
                             when placed in the destination directory

    -T <seconds>           : apply timeout to each remote command
    --sshexe <path to ssh> : use this ssh
"""


############################################################################

def main():

    import getopt
    optL,argL = getopt.getopt( sys.argv[1:], 'hT:',
                   longopts=['help','sshexe=','fperms=','dperms=','group='] )

    optD ={}
    for n,v in optL:
        if n == '-h' or n == '--help':
            print3( helpstr )
            return 0
        elif n in ['--fperms','--dperms']:
            optD[n] = optD.get(n,[]) + v.split()
        else:
            optD[n] = v

    if len(argL) < 2:
        print3( '*** filecopy.py: expected at least two arguments' )
        sys.exit(1)

    tmout = optD.get( '-T', None )
    if tmout != None:
        tmout = float( tmout )

    try:
        copy_files( argL[:-1], argL[-1],
                    fperms=optD.get( '--fperms', [] ),
                    dperms=optD.get( '--dperms', [] ),
                    group=optD.get( '--group', None ),
                    timeout=tmout,
                    sshexe=optD.get( '--sshexe', 'ssh' ),
                     )
    except:
        traceback.print_exc()
        print3( '*** filecopy.py: '+str( sys.exc_info()[1] ) )
        sys.exit(1)


############################################################################

def copy_files( files, to_dir,
                fperms=[], dperms=[], group=None,
                echo=True, timeout=None, sshexe='ssh' ):
    """
    Copy or replace paths in the 'files' list into the 'to_dir' directory.

    Either the 'files' paths or the 'to_dir' directory can be prefixed with a
    machine name plus a colon (to indicate a path on a remote machine), but
    not both.  For example, "sparky:/some/directory" means the directory
    /some/directory on machine sparky.  If a machine is specified for one of
    the 'files' paths, then it must be the same on all 'files' paths.

    The 'files' paths can be glob patterns, but not 'to_dir'.

    Upond arrival in 'to_dir', the 'fperms' file permissions are applied to
    files, while 'dperms' are applied to directories (recursively).  Both
    'fperms' and 'dperms' are lists of permission specifications, such as
    "g+r" and "o-rwx".  If 'group' is given, the group name on all paths are
    set to the given group name.

    If 'echo' is True, the actions are printed to stdout as they occur.

    If 'timeout' is not None, a time limit is applied to each remote python
    operation, and if one times out, an exception is raised.  This does not
    apply to file transfers that use ssh.

    The 'sshexe' option is passed through to the RemotePython constructor and
    is used to perform file transfers.
    """
    rm = None
    fL = []
    for f in files:
        m,p = splitmach( f )
        if ( m != None and rm == '' ) or ( m == None and rm ):
            raise Exception(
                "Source files must have a consistent machine specification" )
        if m == None:
            rm = ''
        else:
            rm = m
        fL.append( p )
    if not rm:
        rm = None

    wm,wd = splitmach( to_dir )

    assert rm == None or wm == None, \
        "a machine specification on both source and target is not supported"

    # if needed, connect to remote machine
    rmt = None
    if rm != None or wm != None:
        m = rm
        if wm != None: m = wm
        rmt = rpy.RemotePython( m, sshexe=sshexe )
        rmt.addRemoteContent( remote_functions )
        # include the permissions module in the remote content
        assert perms.get_filename() != None, "file perms.py not found"
        rmt.addRemoteContent( filename=perms.get_filename() )
        if echo: print3( 'Connecting to "'+m+'"' )
        if timeout: rmt.timeout(timeout)
        rmt.connect()

    try:
        # check destination directory
        if wm == None: wdL = check_dir( wd )
        else:          wdL = rmt.x_check_dir( wd )
        if not wdL[0]:
            raise Exception( "destination directory does not exist: "+to_dir )
        if not wdL[1]:
            raise Exception( "destination path is not a directory: "+to_dir )
        if not wdL[2]:
            raise Exception( "destination directory does not have " + \
                             "read, write & execute permissions: "+to_dir )
        wd = wdL[3]

        # list source files
        if rm == None: rL,nL = glob_paths( fL )
        else:          rL,nL = rmt.x_glob_paths( fL )
        if len(nL) > 0:
            p = nL[0]
            if rm != None: p = rm+':'+p
            raise Exception( "source path does not exist: "+p )

        if len(rL) > 0:

            check_unique( rm, rL, wm, wd )

            if rm == None and wm == None:
                # local to local copy
                local_copy( rL, wd, fperms, dperms, group )

            elif rm == None:
                # destination machine is remote
                local_to_remote_copy( wm, rmt, rL, wd,
                                      fperms=fperms,
                                      dperms=dperms,
                                      group=group,
                                      sshexe=sshexe )

            else:
                # source machine is remote
                remote_to_local_copy( rm, rL, wd,
                                      fperms=fperms,
                                      dperms=dperms,
                                      group=group,
                                      sshexe=sshexe )

    finally:
        if rmt != None:
            if timeout: rmt.timeout(timeout)
            rmt.shutdown()


_machine_prefix_pat = re.compile( '[0-9a-zA-Z_.-]+?:' )

def splitmach( path ):
    """
    Separates "machine:directory" into a pair (machine, directory).  If a
    machine is not specified, returns (None, directory).
    """
    m = _machine_prefix_pat.match( path )
    if m == None:
        return None,path
    return path[:m.end()-1], path[m.end():]


# the follwoing functions are defined and available in the current module
remote_functions = \
'''
import stat
import glob
from shutil import rmtree as shutil_rmtree

def check_dir( directory ):
    # Returns python list:
    #   [ dir exists, is dir, exe & write ok, path w/ user expanded ]
    d = os.path.expanduser(directory)
    rtnL = [ False, False, False, d ]
    if os.path.exists( d ):
        rtnL[0] = True
        if os.path.isdir( d ):
            rtnL[1] = True
            xok = os.access( d, os.X_OK )
            rok = os.access( d, os.R_OK )
            wok = os.access( d, os.W_OK )
            if xok and rok and wok:
                rtnL[2] = True

    return rtnL


def glob_paths( paths ):
    # each path in 'paths' list is glob'ed;  if the path is a soft link, it is
    # followed once (a second soft link is not followed);
    # returns a list of triples
    #   [ abs dirname, link basename, destination basename ]
    # where the link and destination basenames will be the same unless the
    # path is a soft link
    fL = []
    noexistL = []
    for f in paths:
        f = os.path.expanduser(f)
        if os.path.islink(f) or os.path.exists(f):
            # the path exists without glob expansion - take that file
            T = os.path.split( follow_link(f) )
            fL.append( list(T)+[os.path.basename(f)] )
        else:
            gL = glob.glob( f )
            if len(gL) > 0:
                for gf in gL:
                    T = os.path.split( follow_link(gf) )
                    fL.append( list(T)+[os.path.basename(gf)] )
            else:
                noexistL.append( f )
    return fL,noexistL


def follow_link( path ):
    # returns abs path of the given path; if the path is a soft link,
    # the soft link is followed and the target abs path is returned
    if os.path.islink( path ):
        lf = os.readlink( path )
        if not os.path.isabs(lf):
            d = os.path.abspath( os.path.dirname(path) )
            lf = os.path.join( d, lf )
        path = lf
    return os.path.abspath( os.path.normpath( path ) )


def make_temp_dir( parent_dir, itime ):
    # make a subdirectory of 'parent_dir' using the time of day (seconds)
    # and the PID of the current process
    # returns the new directory path
    # the permissions are set so that group and other have no read, write, exe
    pid = str( os.getpid() )
    dt = '_'.join( time.ctime( itime ).split() )
    sd = os.path.join( parent_dir, 'filecopy_'+dt+'_p'+pid )
    print3( 'mkdir '+os.uname()[1]+':'+sd )
    os.mkdir( sd )
    apply_chmod( sd, 'u=rwx', 'g=---', 'o=---' )
    return sd


def swap_paths( readL, tempdir, writedir ):
    # 1. the 'readL' should be a list of [dir,base1,base2]
    #    where 'base1' and 'base2' are basenames
    # 2. paths 'writedir'/base2 are moved to 'tempdir'/base2.old
    # 3. paths 'tempdir'/base1 are moved to 'writedir'/base2
    for dirn,base1,base2 in readL:
        wf = os.path.join( writedir, base2 )
        if os.path.islink( wf ) or os.path.exists( wf ):
            old = os.path.join( tempdir, base2+'.old' )
            print3( os.uname()[1]+':', 'mv '+wf+' '+old )
            os.rename( wf, old )

    for dirn,base1,base2 in readL:
        rf = os.path.join( tempdir, base1 )
        wf = os.path.join( writedir, base2 )
        print3( os.uname()[1]+':', 'mv '+rf+' '+wf )
        os.rename( rf, wf )

def apply_permissions( directory, fileL, fperms, dperms, group ):
    # 
    for basn in fileL:
        wf = os.path.join( directory, basn )
        if os.path.islink(wf):
            pass
        elif os.path.isdir(wf):
            chmod_recurse( wf, fperms, dperms, group )
        else:
            if fperms: apply_chmod( wf, *fperms )
            if group: apply_chmod( wf, group )
'''

# this makes the remote function code available in the current namespace
cobj = compile( remote_functions, "<string>", "exec" )
eval( cobj, globals() )

# inject this into the namespace so it will be available locally and on
# the remote end
from perms import apply_chmod, chmod_recurse


def check_unique( readmach, readL, writemach, writedir ):
    """
    Examines the read list for duplicate read base names or destination base
    names.  If a duplicate is found, an exception is raised.
    """
    if readmach == None: rm = ''
    else:                rm = readmach+':'
    if writemach == None: wm = ''
    else:                 wm = writemach+':'

    bD = {}
    dD = {}
    for dirn,basn,dstn in readL:
        bn = rm+os.path.join(dirn,basn)
        dn = wm+os.path.join(writedir,dstn)
        if basn in bD:
            raise Exception( 'Duplicate source base name: '+bn )
        if dstn in dD:
            raise Exception( 'Duplicate destination base name: '+dn )
        bD[basn] = bn
        dD[dstn] = dn


def local_copy( readL, destdir, fperms=[], dperms=[], group=None ):
    """
    Copy source files/directories from current machine to a destination
    directory on the current machine.  The 'readL' comes from glob_paths()
    and is a list of [dir,base1,base2], where base1 and base2 are basenames.
    """
    tmpd = make_temp_dir( destdir, time.time() )

    for dirn,basn,dstn in readL:
        rf = os.path.join( dirn, basn )
        wf = os.path.join( tmpd, basn )
        if os.path.islink(rf):
            rf1 = os.readlink( rf )
            print3( 'ln -s', rf1, wf )
            os.symlink( rf1, wf )
        elif os.path.isdir(rf):
            print3( 'cp -r', rf, wf )
            shutil.copytree( rf, wf, symlinks=True )
            chmod_recurse( wf, fperms, dperms, group )
        else:
            print3( 'cp -p', rf, wf )
            shutil.copy2( rf, wf )
            if fperms: apply_chmod( wf, *fperms )
            if group: apply_chmod( wf, group )

    swap_paths( readL, tmpd, destdir )

    print3( 'rm -r '+tmpd )
    shutil.rmtree( tmpd )


def remote_to_local_copy( mach, readL, destdir,
                          fperms=[], dperms=[], group=None,
                          sshexe='ssh' ):
    """
    Copy source files/directories from remote machine to a destination
    directory on the current machine.  The 'readL' comes from glob_paths()
    performed on the remote machine and is a list of [dir,base1,base2],
    where base1 and base2 are basenames.
    """
    # collect source files by directory
    dD = {}
    tmpL = []
    for dirn,basn,dstn in readL:
        tmpL.append( basn )
        dD[dirn] = dD.get(dirn,[]) + [basn]

    # create local temporary directory
    tmpd = make_temp_dir( destdir, time.time() )

    for dirn,bfL in dD.items():
        # ssh a tar command on the remote machine and send its output back
        # to the local machine and into an untar on the local machine
        cmdL = [ sshexe, mach,
                 'tar', '-C', pipes.quote(dirn), '-c' ]
        cmdL += [ pipes.quote(p) for p in bfL ]
        cmdL += [ '|', 'tar', '-C', pipes.quote(tmpd), '-xf', '-' ]
        cmd = ' '.join( cmdL )
        print3( cmd )
        x = subprocess.call( cmd, shell=True )
        assert x == 0, "Command failed: "+str(cmd)

    # apply permissions for the files in tmpd
    apply_permissions( tmpd, tmpL, fperms, dperms, group )

    swap_paths( readL, tmpd, destdir )

    print3( 'rm -r '+tmpd )
    shutil.rmtree( tmpd )


def local_to_remote_copy( mach, rmtpy, readL, destdir,
                          fperms=[], dperms=[], group=None,
                          sshexe='ssh' ):
    """
    Copy source files/directories from the local machine to a destination
    directory on a remote machine.  The 'readL' comes from glob_paths()
    performed on the local machine and is a list of [dir,base1,base2],
    where base1 and base2 are basenames.
    """
    # collect source files by directory
    dD = {}
    tmpL = []
    for dirn,basn,dstn in readL:
        tmpL.append( basn )
        dD[dirn] = dD.get(dirn,[]) + [basn]

    # create remote temporary directory
    tmpd = rmtpy.x_make_temp_dir( destdir, time.time() )

    for dirn,bfL in dD.items():
        # use tar sending output through a pipe to ssh on the remote machine
        # which executes an untar (on the remote machine)
        cmdL = [ 'tar', '-C', pipes.quote(dirn), '-c' ]
        cmdL += [ pipes.quote(p) for p in bfL ]
        cmdL += [ '|', sshexe, mach ]
        cmdL += [ pipes.quote( 'tar -C '+pipes.quote(tmpd)+' -xf -' ) ]
        cmd = ' '.join( cmdL )
        print3( cmd )
        x = subprocess.call( cmd, shell=True )
        assert x == 0, "Command failed: "+str(cmd)

    # apply permissions for the files in the remote temporary directory
    rmtpy.x_apply_permissions( tmpd, tmpL, fperms, dperms, group )

    rmtpy.x_swap_paths( readL, tmpd, destdir )

    print3( 'rm -r '+mach+':'+tmpd )
    rmtpy.x_shutil_rmtree( tmpd )


##########################################################################

if __name__ == "__main__":
    mydir = os.path.abspath( sys.path[0] )
    main()
