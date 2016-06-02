#!/usr/bin/env python

import os, sys


def writeScript( testobj, filename, lang, config, plat ):
    """
    TODO: add helper functions for evaluating testname, options, parameters, etc
    """
    tname = testobj.getName()

    troot = testobj.getRootpath()
    assert os.path.isabs( troot )
    trel = os.path.dirname( testobj.getFilepath() )
    srcdir = os.path.normpath( os.path.join( troot, trel ) )
    
    tdir = config.get('toolsdir')
    assert tdir
    vvtlib = os.path.join( tdir, 'libvvtest' )

    projdir = config.get('exepath')
    if not projdir: projdir = ''

    onopts = config.get('onopts')
    offopts = config.get('offopts')

    platname = plat.getName()
    cplrname = plat.getCompiler()

    w = LineWriter()

    if lang == 'py':

        w.add( 'import os, sys',
               'sys.path.insert( 0, "'+vvtlib+'" )' )
        w.add( 'from script_util import *' )
        cdir = config.get('configdir')
        if cdir:
            w.add( 'sys.path.insert( 0, "'+cdir+'" )' )
        
        w.add( '',
               'def print3( *args, **kwargs ):',
               '    "a python 2 & 3 compatible print function"',
               '    s = " ".join( [ str(x) for x in args ] )',
               '    if len(kwargs) > 0:',
               '        L = [ str(k)+"="+str(v) for k,v in kwargs.items() ]',
               '        s += " " + " ".join( L )',
               '    sys.stdout.write( s + os.linesep )',
               '    sys.stdout.flush()' )

        w.add( '',
               'NAME = "'+tname+'"',
               'PLATFORM = "'+platname+'"',
               'COMPILER = "'+cplrname+'"',
               'VVTESTSRC = "'+tdir+'"',
               'PROJECT = "'+projdir+'"',
               'OPTIONS = '+repr( onopts ),
               'OPTIONS_OFF = '+repr( offopts ),
               'SRCDIR = "'+srcdir+'"' )

        w.add( '', '# platform settings' )
        for k,v in plat.getEnvironment().items():
            w.add( 'os.environ["'+k+'"] = "'+v+'"' )

        w.add( '', '# parameters defined by the test' )
        for k,v in testobj.getParameters().items():
            w.add( k+' = "'+v+'"' )
        
        if testobj.getParent() == None and testobj.hasAnalyze():
            w.add( '', '# parameters comprising the children' )
            D = testobj.getParameterSet()
            if len(D) > 0:
              # the parameter names and values of the children tests
              for n,L in D.items():
                assert type(n) == type(())
                if len(n) == 1:
                    L2 = [ T[0] for T in L ]
                    w.add( 'PARAM_'+n[0]+' = ' + repr(L2) )
                else:
                    n2 = '_'.join( n )
                    w.add( 'PARAM_'+n2+' = ' + repr(L) )
        
        w.add(  """
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
                """ )

        w.add(  """
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
                """ )

        w.add(  """
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
                        import difflib
                        fp1 = open( file1, 'r' )
                        flines1 = fp1.readlines()
                        fp2 = open( file2, 'r' )
                        flines2 = fp2.readlines()
                        diffs = difflib.unified_diff( flines1, flines2,
                                                      file1, file2 )
                        fp1.close()
                        fp2.close()
                        sys.stdout.writelines( diffs )
                        return True
                    return False
                """ )
        
        w.add(  """
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

                    print3( 'nlinesdiff: filename = '+filename + \\
                            ', num lines = '+str(n) + \\
                            ', max lines = '+str(maxlines) )
                    if n > maxlines:
                        print3( '*** nlinesdiff: number of lines exceeded',
                                'max, setting have_diff' )
                        set_have_diff()
                        return True
                    return False
                """ )
    
    elif lang == 'pl':
        pass
    
    elif lang in ['sh','bash']:

        w.add( '',
               'NAME="'+tname+'"',
               'PLATFORM="'+platname+'"',
               'COMPILER="'+cplrname+'"',
               'VVTESTSRC="'+tdir+'"',
               'PROJECT="'+projdir+'"',
               'OPTIONS="'+'+'.join( onopts )+'"',
               'OPTIONS_OFF="'+'+'.join( offopts )+'"',
               'SRCDIR="'+srcdir+'"' )

        w.add( '', '# platform settings' )
        for k,v in plat.getEnvironment().items():
            w.add( 'export '+k+'="'+v+'"' )

        w.add( '', '# parameters defined by the test' )
        for k,v in testobj.getParameters().items():
            w.add( k+'="'+v+'"' )
        
        if testobj.getParent() == None and testobj.hasAnalyze():
            w.add( '', '# parameters comprising the children' )
            D = testobj.getParameterSet()
            if len(D) > 0:
              # the parameter names and values of the children tests
              for n,L in D.items():
                assert type(n) == type(())
                n2 = '_'.join( n )
                L2 = [ '/'.join( v ) for v in L ]
                w.add( 'PARAM_'+n2+'="' + ' '.join(L2) + '"' )
        
        w.add(  """
                # a test can call "set_have_diff" one or more times if it
                # decides the test should diff, then at the end of the test,
                # call "if_diff_exit_diff"

                diff_exit_status=64
                have_diff=0

                set_have_diff() {
                    have_diff=1
                }

                exit_diff() {
                    echo "*** exitting diff"
                    exit $diff_exit_status
                }

                if_diff_exit_diff() {
                    if [ $have_diff -ne 0 ]
                    then
                        exit_diff
                    fi
                }
                """ )
        
        w.add(  """
                sedfile() {
                    # arguments are the file name then a substitution
                    # expression, such as "s/pattern/replacement/"
                    # additional expressions can be given but you must
                    # preceed each with -e
                    # note that an edit of a soft linked file will remove
                    # the soft link and replace the file name with a regular
                    # file with modified contents

                    if [ $# -lt 2 ]
                    then
                        echo "*** error: sedfile() requires at least 2 arguments"
                        exit 1
                    fi

                    fname=$1
                    shift
                    
                    echo "sedfile: sed -e $@ $fname > $fname.sedfile_tmp"
                    sed -e "$@" $fname > $fname.sedfile_tmp || exit 1

                    echo "sedfile: mv $fname.sedfile_tmp $fname"
                    rm -f $fname
                    mv $fname.sedfile_tmp $fname
                }
                """ )

        w.add(  """
                unixdiff() {
                    if [ $# -ne 2 ]
                    then
                        echo "*** error: unixdiff requires exactly 2 arguments"
                        exit 1
                    fi
                    file1=$1
                    file2=$2

                    if [ ! -f $file1 ]
                    then
                        echo "*** unixdiff: file does not exist: $file1"
                        exit 1
                    fi
                    if [ ! -f $file2 ]
                    then
                        echo "*** unixdiff: file does not exist: $file2"
                        exit 1
                    fi
                    echo "unixdiff: diff $file1 $file2"
                    setdiff=0
                    diff $file1 $file2 || setdiff=1
                    if [ $setdiff -eq 1 ]
                    then
                        echo "*** unixdiff: files are different, setting have_diff"
                        set_have_diff
                    fi
                }
                """ )
        
        w.add(  """
                nlinesdiff() {
                    if [ $# -ne 2 ]
                    then
                        echo "*** error: nlinesdiff requires exactly 2 arguments"
                        exit 1
                    fi
                    filename=$1
                    maxlines=$2

                    if [ ! -f $filename ]
                    then
                        echo "*** nlinesdiff: file does not exist: $filename"
                        exit 1
                    fi

                    nlines=`cat $filename | wc -l`
                    
                    echo "nlinesdiff: filename = $filename, num lines = $nlines, max lines = $maxlines"
                    if [ $nlines -gt $maxlines ]
                    then
                        echo "*** nlinesdiff: number of lines exceeded max, setting have_diff"
                        set_have_diff
                    fi
                }
                """ )
    
    elif lang in ['csh','tcsh']:

        w.add( '',
               'set NAME="'+tname+'"',
               'set PLATFORM="'+platname+'"',
               'set COMPILER="'+cplrname+'"',
               'set VVTESTSRC="'+tdir+'"',
               'set PROJECT="'+projdir+'"',
               'set OPTIONS="'+'+'.join( onopts )+'"',
               'set OPTIONS_OFF="'+'+'.join( offopts )+'"',
               'set SRCDIR="'+srcdir+'"' )

        w.add( '', '# platform settings' )
        for k,v in plat.getEnvironment().items():
            w.add( 'setenv '+k+' "'+v+'"' )

        w.add( '', '# parameters defined by the test' )
        for k,v in testobj.getParameters().items():
            w.add( 'set '+k+'="'+v+'"' )
        
        if testobj.getParent() == None and testobj.hasAnalyze():
            w.add( '', '# parameters comprising the children' )
            D = testobj.getParameterSet()
            if len(D) > 0:
              # the parameter names and values of the children tests
              for n,L in D.items():
                assert type(n) == type(())
                n2 = '_'.join( n )
                L2 = [ '/'.join( v ) for v in L ]
                w.add( 'set PARAM_'+n2+'="' + ' '.join(L2) + '"' )
        
        w.add(  """
                set diff_exit_status=64
                set have_diff=0

                alias set_have_diff 'set have_diff=1'
                alias exit_diff 'echo "*** exitting diff" ; exit $diff_exit_status'
                alias if_diff_exit_diff 'if ( $have_diff ) echo "*** exitting diff" ; if ( $have_diff ) exit $diff_exit_status'
                """ )
    
    w.write( filename )


#########################################################################

class LineWriter:

    def __init__(self):
        self.lineL = []

    def add(self, *args):
        """
        """
        if len(args) > 0:
            indent = ''
            if type(args[0]) == type(2):
                n = args.pop(0)
                indent = '  '*n
            for line in args:
                if line.startswith('\n'):
                    for line in self._split( line ):
                        self.lineL.append( indent+line )
                else:
                    self.lineL.append( indent+line )

    def _split(self, s):
        """
        """
        off = None
        lineL = []
        for line in s.split( '\n' ):
            line = line.strip( '\r' )
            lineL.append( line )
            if off == None and line.strip():
                i = 0
                for c in line:
                    if c != ' ':
                        off = i
                        break
                    i += 1
        if off == None:
            return lineL
        return [ line[off:] for line in lineL ]

    def write(self, filename):
        """
        """
        fp = open( filename, 'w' )
        fp.write( '\n'.join( self.lineL ) + '\n' )
        fp.close()
