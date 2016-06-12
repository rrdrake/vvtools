#!/usr/bin/env python

import os, sys


def writeScript( testobj, filename, lang, config, plat ):
    """
    Writes a helper script for the test.  The script language is based on
    the 'lang' argument.
    """
    tname = testobj.getName()

    troot = testobj.getRootpath()
    assert os.path.isabs( troot )
    trel = os.path.dirname( testobj.getFilepath() )
    srcdir = os.path.normpath( os.path.join( troot, trel ) )
    
    configdir = config.get('configdir')

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
               '',
               'NAME = "'+tname+'"',
               'TESTID = "'+testobj.getExecuteDirectory()+'"',
               'PLATFORM = "'+platname+'"',
               'COMPILER = "'+cplrname+'"',
               'VVTESTSRC = "'+tdir+'"',
               'VVTESTLIB = "'+vvtlib+'"',
               'PROJECT = "'+projdir+'"',
               'OPTIONS = '+repr( onopts ),
               'OPTIONS_OFF = '+repr( offopts ),
               'SRCDIR = "'+srcdir+'"',
               '',
               'sys.path.insert( 0, VVTESTLIB )' )

        platenv = plat.getEnvironment()
        w.add( '',
               '# platform settings',
               'PLATFORM_VARIABLES = '+repr(platenv),
               'def apply_platform_variables():',
               '    "sets the platform variables in os.environ"' )
        for k,v in platenv.items():
            w.add( '    os.environ["'+k+'"] = "'+v+'"' )

        w.add( '', '# parameters defined by the test' )
        paramD = testobj.getParameters()
        w.add( 'PARAM_DICT = '+repr( paramD ) )
        for k,v in paramD.items():
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
        
        if configdir:
            w.add( """
                CONFIGDIR = '"""+configdir+"""'
                sys.path.insert( 0, CONFIGDIR )
                plug = os.path.join( CONFIGDIR, 'script_util_plugin.py' )
                if os.path.exists( plug ):
                    from script_util_plugin import *
                else:
                    from script_util import *
                    apply_platform_variables()
                """ )
        else:
            w.add( '',
                   'from script_util import *',
                   'apply_platform_variables()' )

        ###################################################################
    
    elif lang in ['sh','bash']:

        w.add( '',
               'NAME="'+tname+'"',
               'TESTID="'+testobj.getExecuteDirectory()+'"',
               'PLATFORM="'+platname+'"',
               'COMPILER="'+cplrname+'"',
               'VVTESTSRC="'+tdir+'"',
               'VVTESTLIB="'+vvtlib+'"',
               'PROJECT="'+projdir+'"',
               'OPTIONS="'+' '.join( onopts )+'"',
               'OPTIONS_OFF="'+' '.join( offopts )+'"',
               'SRCDIR="'+srcdir+'"',
               'PYTHONEXE="'+sys.executable+'"' )

        platenv = plat.getEnvironment()
        w.add( '',
               '# platform settings',
               'PLATFORM_VARIABLES="'+' '.join( platenv.keys() )+'"' )
        for k,v in platenv.items():
            w.add( 'PLATVAR_'+k+'="'+v+'"' )
        w.add( 'apply_platform_variables() {',
               '    # sets the platform variables in the environment' )
        for k,v in platenv.items():
            w.add( '    export '+k+'="'+v+'"' )
        if len(platenv) == 0:
            w.add( '    :' )  # cannot have an empty function
        w.add( '}' )

        w.add( '', '# parameters defined by the test' )
        paramD = testobj.getParameters()
        s = ' '.join( [ n+'/'+v for n,v in paramD.items() ] )
        w.add( 'PARAM_DICT="'+s+'"' )
        for k,v in paramD.items():
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

        if configdir:
            w.add( """
                CONFIGDIR='"""+configdir+"""'
                if [ -e $CONFIGDIR/script_util_plugin.sh ]
                then
                    source $CONFIGDIR/script_util_plugin.sh
                else
                    source $VVTESTLIB/script_util.sh
                    apply_platform_variables
                fi
                """ )
        else:
            w.add( '',
                   'source $VVTESTLIB/script_util.sh )',
                   'apply_platform_variables' )

        ###################################################################
    
    elif lang in ['csh','tcsh']:

        w.add( '',
               'set NAME="'+tname+'"',
               'set TESTID = "'+testobj.getExecuteDirectory()+'"',
               'set PLATFORM="'+platname+'"',
               'set COMPILER="'+cplrname+'"',
               'set VVTESTSRC="'+tdir+'"',
               'set VVTESTLIB="'+vvtlib+'"',
               'set PROJECT="'+projdir+'"',
               'set OPTIONS="'+' '.join( onopts )+'"',
               'set OPTIONS_OFF="'+' '.join( offopts )+'"',
               'set SRCDIR="'+srcdir+'"',
               'set PYTHONEXE="'+sys.executable+'"' )

        platenv = plat.getEnvironment()
        w.add( '',
               '# platform settings',
               'set PLATFORM_VARIABLES="'+' '.join( platenv.keys() )+'"' )
        for k,v in platenv.items():
            w.add( 'set PLATVAR_'+k+'="'+v+'"' )
        for k,v in platenv.items():
            w.add( 'setenv '+k+' "'+v+'"' )

        w.add( '', '# parameters defined by the test' )
        paramD = testobj.getParameters()
        s = ' '.join( [ n+'/'+v for n,v in paramD.items() ] )
        w.add( 'PARAM_DICT="'+s+'"' )
        for k,v in paramD.items():
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
    
        ###################################################################
    
    elif lang == 'pl':
        pass
    
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
