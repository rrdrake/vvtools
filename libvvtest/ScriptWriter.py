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

        w.add( 'import sys',
               'sys.path.insert( 0, "'+vvtlib+'" )' )
        w.add( 'from script_util import *' )
        cdir = config.get('configdir')
        if cdir:
            w.add( 'sys.path.insert( 0, "'+cdir+'" )' )
        
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
                # the test can set "have_diff" to True in the test script,
                # then at the end call if_diff_exit_diff()
                diffExitStatus = 64
                def exit_diff():
                    sys.exit( diffExitStatus )
                """ )
    
    elif lang == 'pl':
        pass
    
    elif lang == 'sh':
        
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
                # the test can set "have_diff" to 1 in the test script,
                # then at the end check its value and exit 'diffExitStatus'
                diffExitStatus=64
                have_diff=0
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
