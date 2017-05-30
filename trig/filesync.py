#!/usr/bin/env python

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import time
import re
import shutil

import remotepython as rpy
print3 = rpy.print3


helpstr = \
"""
USAGE:
    filesync.py [OPTIONS] [machine:]source [machine:]target

SYNOPSIS:
    Copy or overwrite files from the source directory into the target
    directory.  At most one directory can be prefixed with a machine name.

    File operations are performed using the remotepython module, so the only
    requirement on the remote machine is that a python (of any version) be
    in PATH.

OPTIONS:
    -h, --help             : this help
    -p <pattern>           : glob pattern of files to copy; may be repeated
    --age <seconds old>    : only files newer than this age are copied
    -T <seconds>           : apply timeout to each remotepython command
    --sshexe <path to ssh> : use this ssh
"""

############################################################################

def main():

    import getopt
    optL,argL = getopt.getopt( sys.argv[1:], 'hp:T:',
                               longopts=['help','age=','sshexe='] )

    optD ={}
    for n,v in optL:
        if n == '-h' or n == '--help':
            print3( helpstr )
            return 0
        elif n in ['-p']:
            optD[n] = optD.get(n,[]) + [v]
        else:
            optD[n] = v

    if len(argL) != 2:
        print3( '*** filesync.py: expected exactly two arguments' )
        sys.exit(1)

    age = optD.get( '--age', None )
    if age != None:
        age = float( age )

    tmout = optD.get( '-T', None )
    if tmout != None:
        tmout = float( tmout )

    sync_directories( argL[0], argL[1],
                      glob=optD.get( '-p', '*' ),
                      age=age,
                      timeout=tmout,
                      sshexe=optD.get( '--sshexe', None ) )


############################################################################

def sync_directories( read_dir, write_dir, glob='*', age=None,
                      echo=True, timeout=None, sshexe=None ):
    """
    Copy or overwrite files from 'read_dir' into 'write_dir'.  Only files
    that match the 'glob' pattern and are no older than 'age' seconds are
    copied (no age limit by default).

    Either the read dir or write dir can be prefixed with a machine name
    plus a colon to indicate a directory on a remote machine.  For example,
    "sparky:/some/directory" means the directory /some/directory on machine
    sparky.  A machine specification can only be given to one directory,
    not both.

    The 'glob' argument can be a shell glob pattern or a python list of
    patterns.

    If 'echo' is True, the actions are printed to stdout as they occur.

    If 'timeout' is not None, a time limit is applied to each remote operation,
    and if one times out, an exception is raised.

    The 'sshexe' option is passed through to the RemotePython constructor.
    """
    rm,rd = splitmach( read_dir )
    wm,wd = splitmach( write_dir )

    assert rm == None or wm == None, "two remote paths not supported"

    rmt = None

    # list source files
    if rm == None:
        rL = long_list_files( rd, glob=glob, age=age )
    else:
        rmt = rpy.RemotePython( rm, sshexe=sshexe )
        rmt.addRemoteContent( remote_functions )
        if echo: print3( 'Connect to "'+rm+'"' )
        if timeout: rmt.timeout(timeout)
        rmt.connect()
        rL = rmt.x_long_list_files( rd, glob=glob, age=age )

    # list target files
    if wm == None:
        wL = long_list_files( wd, glob=glob, age=age )
    else:
        rmt = rpy.RemotePython( wm, sshexe=sshexe )
        rmt.addRemoteContent( remote_functions )
        if echo: print3( 'Connect to "'+wm+'"' )
        if timeout: rmt.timeout(timeout)
        rmt.connect()
        wL = rmt.x_long_list_files( wd, glob=glob, age=age )

    try:
        wD = {}
        for T in wL:
            wD[ T[0] ] = T

        # compose list of files which need to be copied
        cpL = []
        for rT in rL:
            wT = wD.get( rT[0], None )
            if wT == None or abs( rT[1]-wT[1] ) > 1 or \
                             rT[2] != wT[2] or \
                             rT[3] != wT[3]:
                f = rT[0]
                cpL.append( (f, rd+'/'+f, wd+'/'+f) )

        if rm == None and wm == None:
            # copy files local to local
            for f,rf,wf in cpL:
                if echo: print3( 'copy -p '+rf+' '+wf )
                shutil.copy2( rf, wf )

        elif rm != None:
            # copy files from remote machine to local
            for f,rf,wf in cpL:
                if echo: print3( 'copy -p '+read_dir+'/'+f+' '+wf )
                if timeout: rmt.timeout(timeout)
                rmt.getFile( rf, wf, preserve=True )

        else:
            assert wm != None
            # copy files from local to remote machine
            for f,rf,wf in cpL:
                if echo: print3( 'copy -p '+rf+' '+write_dir+'/'+f )
                if timeout: rmt.timeout(timeout)
                rmt.putFile( rf, wf, preserve=True )

    finally:
        if rmt != None:
            if timeout: rmt.timeout(timeout)
            rmt.shutdown()

    return [ T[0] for T in cpL ]


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
import fnmatch

def list_files( directory, glob='*', age=None ):
    "Returns a list of files matching the given pattern no older than 'age'."
    # glob can be a string or a list of strings
    if type(glob) == type(''):
        glob = [glob]

    L = []
    for f in os.listdir( directory ):
        for pat in glob:
            if fnmatch.fnmatch( f, pat ):
                L.append(f)
                break

    if age == None:
        return L

    tm = time.time()
    fL = []
    for f in L:
        mt = os.path.getmtime( directory+'/'+f )
        if tm-mt <= age:
            fL.append(f)

    return fL


def long_list_files( directory, glob='*', age=None ):
    "Same as list_files() except each entry is (filename, modification time, file size, SHA-1)."
    L = list_files( directory, glob, age )
    fL = []
    for f in L:
        df = directory+'/'+f
        fL.append( ( f, os.path.getmtime(df), os.path.getsize(df), filesha1(df) ) )
    return fL


# Returns the SHA-1 hex digest of the contents of the given filename
if sys.version_info[0] == 2 and sys.version_info[1] < 5:
    import sha
    def filesha1( filename ):
        dig = sha.new()
        fp = open( filename )
        try:
            dig.update( fp.read() )
        finally:
            fp.close()
        return dig.hexdigest()
elif sys.version_info[0] < 3:
    import hashlib
    def filesha1( filename ):
        dig = hashlib.sha1()
        fp = open( filename )
        try:
            dig.update( fp.read() )
        finally:
            fp.close()
        return dig.hexdigest()
else:
    import hashlib
    def filesha1( filename ):
        dig = hashlib.sha1()
        fp = open( filename )
        try:
            dig.update( fp.read().encode() )
        finally:
            fp.close()
        return dig.hexdigest()
'''

# this makes the remote function code available in the current namespace
cobj = compile( remote_functions, "<string>", "exec" )
eval( cobj, globals() )


##########################################################################

if __name__ == "__main__":
    mydir = os.path.abspath( sys.path[0] )
    main()
