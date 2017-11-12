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
    filename = os.path.expanduser( filename )
    if os.path.exists( filename ):
        return os.path.getsize( filename )
    return -1


def open_file_read( filename, offset=None ):
    """
    Opens the given file name and saves the open file pointer in the object
    map.  If 'offset' is not None, a seek(offset) is done immediately
    after the file is opened.  Returns the file modification time, the access
    time, the file mode for the file, and the remote file pointer id.
    """
    filename = os.path.expanduser( filename )
    mt = os.path.getmtime( filename )
    at = os.path.getatime( filename )
    fm = stat.S_IMODE( os.stat(filename)[stat.ST_MODE] )
    fp = open( filename, 'rb' )
    if offset != None:
        fp.seek( offset )
    return mt, at, fm, save_object( fp )

def file_read( fp_id, num_bytes ):
    """
    Reads and returns 'num_bytes' bytes from the file pointer specified by
    the 'fp_id' object id.
    """
    fp = get_object( fp_id )
    buf = _STRING_( fp.read( num_bytes ) )
    return buf

def close_file( fp_id ):
    """
    Close the file pointer specified by the 'fp_id' object id, and remove it
    from the remote object id map.
    """
    if fp_id != None:
        fp = pop_object( fp_id )
        fp.close()
