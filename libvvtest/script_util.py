#!/usr/bin/env python

import os, sys

############################################################################

# a test can call set_have_diff() one or more times if it
# decides the test should diff, then at the end of the test,
# call if_diff_exit_diff()

diff_exit_status = 64
have_diff = False

def set_have_diff():
    global have_diff
    have_diff = diff_exit_status

def exit_diff():
    print3( "*** exitting diff" )
    sys.exit( diff_exit_status )

def if_diff_exit_diff():
    if have_diff:
        exit_diff()

############################################################################

def print3( *args, **kwargs ):
    "a python 2 & 3 compatible print function"
    s = " ".join( [ str(x) for x in args ] )
    if len(kwargs) > 0:
        L = [ str(k)+"="+str(v) for k,v in kwargs.items() ]
        s += " " + " ".join( L )
    sys.stdout.write( s + os.linesep )
    sys.stdout.flush()

############################################################################

def sedfile( filename, pattern, replacement, *more ):
    '''
    Apply one or more regex pattern replacements to each
    line of the given file.  If the file is a regular file,
    its contents is replaced.  If the file is a soft link, the
    soft link is removed and a regular file is written with
    the new contents in its place.
    '''
    import re
    assert len(more) % 2 == 0
    
    info = 'sedfile: filename="'+filename+'":'
    info += ' '+pattern+' -> '+replacement
    prL = [ ( re.compile( pattern ), replacement ) ]
    for i in range( 0, len(more), 2 ):
        info += ', '+more[i]+' -> '+more[i+1]
        prL.append( ( re.compile( more[i] ), more[i+1] ) )
    
    print3( info )

    fpin = open( filename, 'r' )
    fpout = open( filename+'.sedfile_tmp', 'w' )
    line = fpin.readline()
    while line:
        for cpat,repl in prL:
            line = cpat.sub( repl, line )
        fpout.write( line )
        line = fpin.readline()
    fpin.close()
    fpout.close()

    os.remove( filename )
    os.rename( filename+'.sedfile_tmp', filename )

############################################################################

def unixdiff( file1, file2 ):
    '''
    If the filenames 'file1' and 'file2' are different, then
    the differences are printed and set_have_diff() is called.
    Returns True if there is a diff, otherwise False.
    '''
    assert os.path.exists( file1 ), "file does not exist: "+file1
    assert os.path.exists( file2 ), "file does not exist: "+file2
    import filecmp
    print3( 'unixdiff: diff '+file1+' '+file2 )
    if not filecmp.cmp( file1, file2 ):
        print3( '*** unixdiff: files are different,',
                'setting have_diff' )
        set_have_diff()
        fp1 = open( file1, 'r' )
        flines1 = fp1.readlines()
        fp2 = open( file2, 'r' )
        flines2 = fp2.readlines()
        import difflib
        diffs = difflib.unified_diff( flines1, flines2,
                                      file1, file2 )
        fp1.close()
        fp2.close()
        sys.stdout.writelines( diffs )
        sys.stdout.flush()
        return True
    return False

############################################################################

def nlinesdiff( filename, maxlines ):
    '''
    Counts the number of lines in 'filename' and if more
    than 'maxlines' then have_diff is set and True is returned.
    Otherwise, False is returned.
    '''
    fp = open( filename, 'r' )
    n = 0
    line = fp.readline()
    while line:
        n += 1
        line = fp.readline()
    fp.close()

    print3( 'nlinesdiff: filename = '+filename + \
            ', num lines = '+str(n) + \
            ', max lines = '+str(maxlines) )
    if n > maxlines:
        print3( '*** nlinesdiff: number of lines exceeded',
                'max, setting have_diff' )
        set_have_diff()
        return True
    return False

############################################################################

import FilterExpressions





