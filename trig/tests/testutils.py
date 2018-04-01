#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import re
import shutil
import stat
import fnmatch
import time
import subprocess
import signal
import shlex
import pipes
import filecmp
import glob


# this file is expected to be imported from a script that was run
# within the tests directory (which is how all the tests are run)
testdir = os.path.dirname( os.path.abspath( sys.argv[0] ) )

srcdir = os.path.normpath( os.path.join( testdir, '..' ) )

sys.path.insert( 0, srcdir )

arglist = sys.argv[1:]

def get_arg_list(): return arglist

def get_test_dir():  # magic: is this still needed ??
    return testdir

def print3( *args ):
    """
    Python 2 & 3 compatible print function.
    """
    s = ' '.join( [ str(x) for x in args ] )
    sys.stdout.write( s + '\n' )
    sys.stdout.flush()

def writefile( fname, content, header=None ):
    """
    Open and write 'content' to file 'fname'.  The content is modified to
    remove leading spaces on each line.  The first non-empty line is used
    to determine how many spaces to remove.
    """
    # determine indent pad of the given content
    pad = None
    lineL = []
    for line in content.split( '\n' ):
        line = line.rstrip( '\r' )
        lineL.append( line )
        if pad == None and line.strip():
            for i in range(len(line)):
                if line[i] != ' ':
                    pad = i
                    break
    # make the directory to contain the file, if not already exist
    d = os.path.dirname( fname )
    if os.path.normpath(d) not in ['','.']:
      if not os.path.exists(d):
        os.makedirs(d)
    # open and write contents
    fp = open( fname, 'w' )
    if header != None:
        fp.write( header.strip() + '\n' )
    for line in lineL:
        if pad != None: fp.write( line[pad:] + '\n' )
        else:           fp.write( line + '\n' )
    fp.close()

def writescript( fname, header, content ):
    """
    The 'header' is something like "#!/bin/sh" and 'content' is the same as
    for writefile().
    """
    writefile( fname, content, header )
    perm = stat.S_IMODE( os.stat(fname)[stat.ST_MODE] )
    perm = perm | stat.S_IXUSR
    try: os.chmod(fname, perm)
    except: pass


def runout( cmd, raise_on_failure=False ):
    """
    """
    opts = {}
    if type(cmd) == type(''):
        opts['shell'] = True
    p = subprocess.Popen( cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               **opts )
    out = p.communicate()[0]
    try:
        s = out.decode()
        out = s
    except:
        pass

    x = p.returncode
    if raise_on_failure and x != 0:
        print3(out)
        raise Exception( 'command failed: ' + str(cmd) )

    return out

    # the below method redirects output to a file rather than a pipe;
    # sometimes the pipe method will hang if the child does not go away;
    # however, we would rather know if the child is being left around, so
    # this redirect method should only be used for debugging
    
    #fpout = open( 'runout.log', 'wb' )
    #opts = {}
    #if type(cmd) == type(''):
    #    opts['shell'] = True
    #p = subprocess.Popen( cmd, stdout=fpout.fileno(),
    #                           stderr=subprocess.STDOUT,
    #                           **opts )
    #p.wait()
    #fpout.close()
    #fpout = open( 'runout.log', 'rb' )
    #out = fpout.read()
    #fpout.close()
    #os.remove( 'runout.log' )
    #try:
    #    s = out.decode()
    #    out = s
    #except:
    #    pass
    #return out


def run_redirect( cmd, redirect_filename ):
    """
    Executes the given command as a child process, waits for it, and returns
    True if the exit status is zero.
    
    The 'redirect_filename' string is the filename to redirect the output.

    If 'cmd' is a string, then the /bin/sh shell is used to interpret the
    command.  If 'cmd' is a python list, then the shell is not used and each
    argument is sent verbatim to the program being executed.
    """
    append = False

    outfp = None
    fdout = None
    if type(redirect_filename) == type(2):
        fdout = redirect_filename
    elif type(redirect_filename) == type(''):
        if append:
            outfp = open( redirect_filename, "a" )
        else:
            outfp = open( redirect_filename, "w" )
        fdout = outfp.fileno()

    if type(cmd) == type(''):
        scmd = cmd
    else:
        scmd = shell_escape( cmd )
    if outfp == None:
        sys.stdout.write( scmd + '\n' )
    else:
        sys.stdout.write( scmd + ' > ' + redirect_filename + '\n' )
    sys.stdout.flush()
    
    # build the arguments for subprocess.Popen()
    argD = {}

    if type(cmd) == type(''):
        argD['shell'] = True
    
    argD['bufsize'] = -1  # use system buffer size (is this needed?)

    if fdout != None:
        argD['stdout'] = fdout
        argD['stderr'] = subprocess.STDOUT

    p = subprocess.Popen( cmd, **argD )

    x = p.wait()

    if outfp != None:
      outfp.close()
    outfp = None
    fdout = None

    return x == 0


def shell_escape( cmd ):
    """
    Returns a string with shell special characters escaped so they are not
    interpreted by the shell.

    The 'cmd' can be a string or a python list.
    """
    if type(cmd) == type(''):
        return ' '.join( [ pipes.quote(s) for s in shlex.split( cmd ) ] )
    return ' '.join( [ pipes.quote(s) for s in cmd ] )


def rmallfiles( not_these=None ):
    for f in os.listdir("."):
      if not_these == None or not fnmatch.fnmatch( f, not_these ):
        if os.path.islink(f):
          os.remove(f)
        elif os.path.isdir(f):
          shutil.rmtree(f)
        else:
          os.remove(f)

def filegrep(fname, pat):
    L = []
    fp = open(fname,"r")
    repat = re.compile(pat)
    for line in fp.readlines():
      line = line.rstrip()
      if repat.search(line):
        L.append(line)
    fp.close()
    return L

def grep(out, pat):
    L = []
    repat = re.compile(pat)
    for line in out.split( '\n' ):
      line = line.rstrip()
      if repat.search(line):
        L.append(line)
    return L


def readfile( fname ):
    """
    Read and return the contents of the given filename.
    """
    fp = open(fname,'r')
    try:
        s = fp.read()
    finally:
        fp.close()
    return s


def which( program ):
    """
    Returns the absolute path to the given program name if found in PATH.
    If not found, None is returned.
    """
    if os.path.isabs( program ):
        return program

    pth = os.environ.get( 'PATH', None )
    if pth:
        for d in pth.split(':'):
            f = os.path.join( d, program )
            if not os.path.isdir(f) and os.access( f, os.X_OK ):
                return os.path.abspath( f )

    return None


###########################################################################

if 'TOOLSET_RUNDIR' not in os.environ:
    # directly executing a test script can be done but rm -rf * is performed;
    # to avoid accidental removal of files, cd into a working directory
    d = os.path.join( os.path.basename( sys.argv[0] )+'_dir' )
    if not os.path.exists(d):
        os.mkdir(d)
    os.environ['TOOLSET_RUNDIR'] = d
    os.chdir(d)
