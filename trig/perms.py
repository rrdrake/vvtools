#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import stat
import pwd
import grp


help_string = """
USAGE:
    perms.py [OPTIONS] file1 [ file2 ... ]

SYNOPSIS:
    This script sets file permissions and file group.  Its main use is as a
python module for file & directory manipulation utilities.  The command line
interface is similar in functionality to the shell commands chmod and chgrp.

    Operations are specified using the -p option, such as

        o=-     : set world permissions to none
        g=r-x   : set group to read, no write, execute
        g+rx    : add read & execute to group
        o-w     : remove write to world
        u+rw    : add read & write to owner

    If the specification does not start with one of u=, g=, o=, u+, g+, o+, u-,
g-, or o-, then it is assumed to be a group name, and the file(s) group is set.

OPTIONS:
    -h, --help : this help
    -p <spec>  : permission specification for files and directories
    -f <spec>  : permission specification for files
    -d <spec>  : permission specification for directories
    -R         : apply permissions recursively

Note that the -p, -f, and -d arguments may be repeated.
"""


def main():

    from getopt import getopt
    optL,argL = getopt( sys.argv[1:], 'hp:f:d:R',
                        longopts=['help','prefix='] )
    optD ={}
    for n,v in optL:
        if n in ['-p','-f','-d']:
            optD[n] = optD.get( n, [] ) + [v]
        else:
            optD[n] = v

    if '-h' in optD or '--help' in optD:
        print3( help_string )
        return

    pspecs = optD.get( '-p', [] )
    fspecs = optD.get( '-f', [] )
    dspecs = optD.get( '-d', [] )

    if len(pspecs) + len(fspecs) + len(dspecs) > 0 and len(argL) > 0:

        if '-R' in optD:
            for path in argL:
                chmod_recurse( path, pspecs+fspecs, pspecs+dspecs )

        else:
            for path in argL:
                if os.path.islink( path ):
                    pass
                elif os.path.isdir( path ):
                    apply_chmod( path, *pspecs )
                    apply_chmod( path, *dspecs )
                else:
                    apply_chmod( path, *pspecs )
                    apply_chmod( path, *fspecs )


####################################################################


def filemode( path ):
    """
    Returns the integer containing the file mode permissions for the
    given pathname.
    """
    return stat.S_IMODE( os.stat(path)[stat.ST_MODE] )


def permission( path_or_fmode, which ):
    """
    Answers a permissions question about the given file name (a string) or
    a file mode (an integer).

    Values for 'which':

        read    : True if the file has read permission; 'path' must be a string
        write   : True if the file has write permission; 'path' a string
        execute : True if the file has execute permission; 'path' a string

        setuid  : True if the file is marked set-uid

        owner <mode> : True if the file satisfies the given mode for owner
        group <mode> : True if the file satisfies the given mode for group
        world <mode> : True if the file satisfies the given mode for world

    where <mode> specifies the file mode, such as rx, rwx, r-x, r, w, x, s.
    If a minus sign is in the <mode> then an exact match of the file mode
    must be true for this function to return True.
    """
    if which == 'read':
        assert type(path_or_fmode) == type(''), \
            'arg1 must be a filename when \'which\' == "read"'
        return os.access( path_or_fmode, os.R_OK )
    
    elif which == 'write':
        assert type(path_or_fmode) == type(''), \
            'arg1 must be a filename when \'which\' == "write"'
        return os.access( path_or_fmode, os.W_OK )
    
    elif which == 'execute':
        assert type(path_or_fmode) == type(''), \
            'arg1 must be a filename when \'which\' == "execute"'
        return os.access( path_or_fmode, os.X_OK )

    else:
        
        if type(path_or_fmode) == type(2):
            fmode = path_or_fmode
        else:
            fmode = filemode( path_or_fmode )

        if which == 'setuid':
            if fmode & stat.S_ISUID: return True
            return False

        elif which == 'setgid':
            if fmode & stat.S_ISGID: return True
            return False

        elif which.startswith( 'owner ' ):
            s = which.split()[1]
            if '-' in s:
                return (fmode & owner_mask) == owner_bits[s]
            return (fmode & owner_bits[s]) == owner_bits[s]

        elif which.startswith( 'group ' ):
            s = which.split()[1]
            if '-' in s:
                return (fmode & group_mask) == group_bits[s]
            return (fmode & group_bits[s]) == group_bits[s]

        elif which.startswith( 'world ' ):
            s = which.split()[1]
            if '-' in s:
                return (fmode & world_mask) == world_bits[s]
            return (fmode & world_bits[s]) == world_bits[s]

        raise Exception( "unknown 'which' value: "+str(which) )


def change_filemode( fmode, spec, *more_specs ):
    """
    Modifies the given file mode according to one or more specifications.
    A specification is a string with format

        {u|g|o}{=|+|-}{one two or three letter sequence}

    where

        the first character: u=user/owner, g=group, o=other/world
        the second character: '=' means set, '+' means add, '-' means remove
        the permission characters: r=read, w=write, x=execute, s=sticky

    For example, "u+x" means add user execute permission, and "g=rx" means
    set the group permissions to exactly read, no write, execute.
    """
    for s in (spec,)+more_specs:
        assert len(s) >= 3
        who = s[0] ; assert who in 'ugo'
        op = s[1] ; assert op in '=+-'
        what = s[2:]
        if who == 'u':
            mask = owner_mask
            bits = owner_bits[what]
        elif who == 'g':
            mask = group_mask
            bits = group_bits[what]
        else:
            mask = world_mask
            bits = world_bits[what]

        if op == '=':   fmode = ( fmode & (~mask) ) | bits
        elif op == '+': fmode = fmode | bits
        else:           fmode = fmode & ( ~(bits) )

    return fmode


def fileowner( path ):
    """
    Returns the user name of the owner of the given pathname.  If the user
    id of the file is not in the password database (and so a user name
    cannot associated with the user id), then None is returned.
    """
    uid = os.stat( path ).st_uid
    try:
        ent = pwd.getpwuid( uid )
    except:
        return None
    return ent[0]


def filegroup( path ):
    """
    Returns the group name of the given pathname.  If the group id of
    the file is not in the group database (and so a group name cannot
    associated with the group id), then None is returned.
    """
    gid = os.stat( path ).st_gid
    try:
        ent = grp.getgrgid( gid )
    except:
        return None
    return ent[0]


def change_group( path, group_id ):
    """
    Changes the group of 'path' to the given group id (an integer), or
    'group_id' can be the group name as a string.
    """
    if type(group_id) == type(''):
        group_id = grp.getgrnam( group_id ).gr_gid
    uid = os.stat( path ).st_uid
    os.chown( path, uid, group_id )


def i_own( path ):
    """
    Returns True if the current user owns the given pathname.
    """
    fuid = os.stat( path ).st_uid
    uid = os.getuid()
    return uid == fuid


def my_user_name():
    """
    Returns the name of the user running this process.
    """
    uid = os.getuid()
    return pwd.getpwuid( uid )[0]


def apply_chmod( path, *spec ):
    """
    Change the group and/or the file mode permissions of the given file 'path'.
    The 'spec' argument(s) must be one or more string specifications.  If a
    specification starts with a character from "ugo" then a letter from "=+-",
    then it is treated as a file mode.  Otherwise it is treated as a group
    name.

    Examples of values for 'spec',

        u+x : file mode setting to add execute for owner
        wg-alegra : change file group to "wg-alegra"
    """
    if spec:

        mL = []
        for s in spec:
            if len(s)>=3 and s[0] in 'ugo' and s[1] in '=+-':
                mL.append(s)
            else:
                change_group( path, s )

        if len(mL) > 0:
            os.chmod( path, change_filemode( filemode( path ), *mL ) )


def chmod_recurse( path, filespecs=[], dirspecs=[], setgroup=None):
    """
    Applies 'filespecs' to files and 'dirspecs' to directories.  Each spec
    is the same as for change_filemode(), such as

        u+x   : add execute for owner
        g-w   : remove write for group
        o=--- : set other to no read, no write, no execute

    Recurses into directories.  Sets the file group if 'setgroup' is given.
    Ignores soft links.
    """
    if os.path.islink( path ):
        pass
    elif os.path.isdir( path ):
        if setgroup:
            change_group( path, setgroup )
        if dirspecs:
            apply_chmod( path, *dirspecs )
        for f in os.listdir( path ):
            fp = os.path.join( path, f )
            chmod_recurse( fp, filespecs, dirspecs, setgroup )
    else:
        if filespecs:
            apply_chmod( path, *filespecs )
        if setgroup:
            change_group( path, setgroup )


##############################################################################

"""
This section defines a mapping from permission strings to file mode bit masks
for owner, group, and world.  For example, an owner "rx" is mapped to the
integer stat.S_IRUSR|stat.S_IXUSR.
"""

owner_mask = (stat.S_ISUID|stat.S_IRWXU)
owner_bits = {
        'r' : stat.S_IRUSR,
        'w' : stat.S_IWUSR,
        'x' : stat.S_IXUSR,
        's' : stat.S_IXUSR|stat.S_ISUID,
        'rw' : stat.S_IRUSR|stat.S_IWUSR,
        'rx' : stat.S_IRUSR|stat.S_IXUSR,
        'rs' : stat.S_IRUSR|stat.S_IXUSR|stat.S_ISUID,
        'wx' : stat.S_IWUSR|stat.S_IXUSR,
        'ws' : stat.S_IWUSR|stat.S_IXUSR|stat.S_ISUID,
        'rwx' : stat.S_IRWXU,
        'rws' : stat.S_IRWXU|stat.S_ISUID,
    }
owner_bits['-'] = 0
owner_bits['---'] = 0
owner_bits['r--'] = owner_bits['r']
owner_bits['-w-'] = owner_bits['w']
owner_bits['--x'] = owner_bits['x']
owner_bits['--s'] = owner_bits['s']
owner_bits['rw-'] = owner_bits['rw']
owner_bits['r-x'] = owner_bits['rx']
owner_bits['r-s'] = owner_bits['rs']
owner_bits['-wx'] = owner_bits['wx']
owner_bits['-ws'] = owner_bits['ws']

group_mask = (stat.S_ISGID|stat.S_IRWXG)
group_bits = {
        'r' : stat.S_IRGRP,
        'w' : stat.S_IWGRP,
        'x' : stat.S_IXGRP,
        's' : stat.S_IXGRP|stat.S_ISGID,
        'rw' : stat.S_IRGRP|stat.S_IWGRP,
        'rx' : stat.S_IRGRP|stat.S_IXGRP,
        'rs' : stat.S_IRGRP|stat.S_IXGRP|stat.S_ISGID,
        'wx' : stat.S_IWGRP|stat.S_IXGRP,
        'ws' : stat.S_IWGRP|stat.S_IXGRP|stat.S_ISGID,
        'rwx' : stat.S_IRWXG,
        'rws' : stat.S_IRWXG|stat.S_ISGID,
    }
group_bits['-'] = 0
group_bits['---'] = 0
group_bits['r--'] = group_bits['r']
group_bits['-w-'] = group_bits['w']
group_bits['--x'] = group_bits['x']
group_bits['--s'] = group_bits['s']
group_bits['rw-'] = group_bits['rw']
group_bits['r-x'] = group_bits['rx']
group_bits['r-s'] = group_bits['rs']
group_bits['-wx'] = group_bits['wx']
group_bits['-ws'] = group_bits['ws']


world_mask = stat.S_IRWXO
world_bits = {
        'r' : stat.S_IROTH,
        'w' : stat.S_IWOTH,
        'x' : stat.S_IXOTH,
        'rw' : stat.S_IROTH|stat.S_IWOTH,
        'rx' : stat.S_IROTH|stat.S_IXOTH,
        'wx' : stat.S_IWOTH|stat.S_IXOTH,
        'rwx' : stat.S_IRWXO,
    }
world_bits['-'] = 0
world_bits['---'] = 0
world_bits['r--'] = world_bits['r']
world_bits['-w-'] = world_bits['w']
world_bits['--x'] = world_bits['x']
world_bits['rw-'] = world_bits['rw']
world_bits['r-x'] = world_bits['rx']
world_bits['-wx'] = world_bits['wx']


######################################################################

def print3( *args ):
    """
    A print function compatible for Python 2 and 3.
    """
    s = ' '.join( [ str(x) for x in args ] )
    sys.stdout.write( s + os.linesep )
    sys.stdout.flush()


######################################################################

filename = None
for p in sys.path:
    f = os.path.join( p, 'perms.py' )
    if os.path.exists(f) and os.access( f, os.R_OK ):
        filename = f
        break

def get_filename():
    """
    Returns the file name of the current file, or None if it cannot be found
    in sys.path.
    """
    return filename

if __name__ == "__main__":
    main()
