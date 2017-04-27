#!/usr/bin/env python

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import stat


def get_process_tree( pid ):
    """
    """
    # get all processes
    # parse into a dict
    # find 'pid' in the dict
    # walk up the parents of 'pid'
    # walk down the children of 'pid'
    # indent & combine these into a single string with newlines
    return s

# TODO: - write a psme like function
#       - use it in runjobs.py to print the tree of processes relevant
#         to the job being monitored
#       - print the tree only every 15 minutes or half hour


def file_size( filename ):
    """
    Returns the number of bytes in the given file name, or -1 if the file
    does not exist.
    """
    if os.path.exists( filename ):
        return os.path.getsize( filename )
    return -1

# only one file at a time can be opened, read from, and closed
fileptr = None

def open_file_read( filename, offset=None ):
    """
    Opens the given file name and saves the open file pointer in a global
    variable.  If 'offset' is not None, a seek(offset) is done immediately
    after the file is opened.  Returns the file modification time, the access
    time, and the file mode for the file.
    """
    global fileptr
    mt = os.path.getmtime( filename )
    at = os.path.getatime( filename )
    fm = stat.S_IMODE( os.stat(filename)[stat.ST_MODE] )
    fileptr = open( filename, 'rb' )
    if offset != None:
        fileptr.seek( offset )
    return mt, at, fm

def file_read( num_bytes ):
    buf = _STRING_( fileptr.read( num_bytes ) )
    return buf

def close_file():
    global fileptr
    fileptr.close()
    fileptr = None
