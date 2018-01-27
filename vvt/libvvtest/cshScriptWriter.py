#!/usr/bin/env python

import os
import string
import re
import stat

diffExitStatus = 64

content_replace_re = re.compile('[$][(]CONTENT[)]')
expect_status_replace_re = re.compile('[$][(]EXPECT_STATUS[)]')


def writeScript( tspec, xdb, plat, \
                 toolsdir, projdir, srcdir, \
                 onopts, offopts,
                 scriptname ):
    """
      tspec is a TestSpec object
      xdb is a CommonSpecDB object
      plat is a Platform object
      toolsdir is the top level toolset directory containing this script
      projdir is the directory to the executables
      srcdir is the directory containing the test description
      onopts is a list of -o options (not a dictionary)
      offopts is a list of -O options (not a dictionary)
    """
    
    scriptbasename = os.path.basename( scriptname )
    
    idstr = tspec.getName()
    for (n,v) in tspec.getParameters().items():
      idstr = idstr + ' ' + n + '=' + v
    
    line_list = []
    
    # start the csh script
    
    line_list.extend([ \
      '#!/bin/csh -f', '',
      '# clear variables and aliases to prevent the users',
      '# environment from interferring with the test',
      'unalias rm',
      'unalias ls',
      'unalias cp',
      'unalias ln',
      'unalias mv',
      'unalias set',
      'unalias setenv',
      'unalias echo',
      'unset newbaseline',
      'unsetenv newbaseline', '',
      'set analyze = 0',
      'echo "++++++++++++++++ begin ' + idstr + '"', '',
      'echo " "',
      'set have_diff = no', '' ])
    
    # the common database might have variables to clear from the environment
    
    s = xdb.getClear()
    if s != None:
      line_list.append( s )
    
    # option parsing is for things that can only be known during invocation
    
    line_list.extend( [ \
      '',
      '# parse command line options',
      '@ i = 1',
      'while ($i <= $#argv)',
      '  switch ("$argv[$i]")',
      '    case --baseline:',
      '      set newbaseline = 1',
      '      breaksw',
      '    case --mpirun_opts:',
      '      @ i += 1',
      '      setenv MPI_OPT "$argv[$i]"',
      '      echo "MPI_OPT=$MPI_OPT"',
      '      breaksw',
      '    case --execute_analysis_sections:',
      '      set analyze = 1',
      '      breaksw',
      '  endsw',
      '  @ i += 1',
      'end', '',
      '' ] )
    
    # set variables guaranteed to be defined for each test
    
    line_list.extend( [ \
      '',
      '# variables defined for all tests',
      'set NAME = "' + tspec.getName() + '"',
      'set PLATFORM = ' + plat.getName(),
      'echo "PLATFORM = $PLATFORM"',
      'set COMPILER = ' + plat.getCompiler(),
      'echo "COMPILER = $COMPILER"',
      'set TOOLSET_DIR = ' + toolsdir,
      'echo "TOOLSET_DIR = $TOOLSET_DIR"' ] )
    if projdir:
      line_list.append( 'set PROJECT = ' + projdir )
    else:
      line_list.append( 'set PROJECT =' )
    line_list.extend( [ \
      'echo "PROJECT = $PROJECT"',
      'set ON = "'  + string.join(onopts,'+') + '"',
      'echo ON = "$ON"',
      'set OFF = "' + string.join(offopts,'+') + '"',
      'echo OFF = "$OFF"',
      'set np = ' + str(tspec.getParameters().get('np',0)),
      'set SRCDIR = "' + srcdir + '"',
      'set XMLDIR = "' + srcdir + '"',
      'echo "XMLDIR = $XMLDIR"' ] )
    
    # set variables defined by the platform
    
    line_list.extend( [ '', '# variables defined by the platform' ] )
    for (k,v) in plat.getEnvironment().items():
      line_list.extend( [ \
        'setenv ' + k + ' "' + v + '"',
        'echo "' + k + ' = $' + k + '"' ] )
    
    # set defines and variables contained in the common database
    
    line_list.extend( [ '',
                 '######## common database definitions ########', '' ] )
    
    for cs in xdb.getDefines():
      dfn = cs.getDefine( plat.getName() )
      assert dfn != None
      line_list.append( dfn )
    
    for cs in xdb.getVariables():
      
      varL = cs.getVariable( plat.getName() )
      assert varL != None
      assert len(varL) == 2
      
      vname = varL[0]
      if len(varL[1]) == 2:
        # a path list is to be used to define the variable
        assert vname != None
        paths = varL[1][0]
        flags = varL[1][1]
        line_list.extend( [ \
          'foreach p (' + string.join(paths) + ')',
          '  if ( -e $p ) then',
          '    set ' + vname + ' = "$p ' + flags + '"',
          '    break',
          '  endif',
          'end' ] )
      else:
        # a script fragment is to be used to define the variable
        assert len(varL[1]) == 1
        line_list.append( varL[1][0] )
      
      if vname != None:
        line_list.extend( [ \
          'if ( $?' + vname + ' ) then',
          '  echo "' + vname + ' = $' + vname + '"',
          'else',
          '  echo "' + vname + ' is not defined"',
          'endif', '' ] )
    
    # set the problem parameter variables
    
    line_list.extend( [ '', '# parameters defined by the test' ] )
    for (k,v) in tspec.getParameters().items():
      line_list.extend( [ \
        'set ' + k + ' = ' + v,
        'echo "' + k + ' = $' + k + '"' ] )
    
    # put the baseline fragment in before the file removal occurs
    
    line_list.extend( [ '',
          '# copy baseline files if this is a rebaselining execution' ] )
    line_list.extend( [ \
      'if ($?newbaseline) then',
      '  set echo', '' ] )
    
    # TODO: add file globbing for baseline files
    for frag in tspec.getBaselineFragments():
      line_list.append( frag )
    
    line_list.extend( [ \
      '  exit 0',
      'endif', '' ] )
    
    # finally, add the main execution fragments
    
    just_analyze = 0
    if tspec.getParent() == None and tspec.hasAnalyze():
      just_analyze = 1
    
    if not just_analyze:
      
      line_list.extend( [ '',
                   '######## main execution fragments ########', '' ] )
      
      for name,content,exitstat,analyze in tspec.getExecutionList():
        
        if name == None:
          if not analyze:
            line_list.extend( [ '', 'if ( $analyze == 0 ) then' ] )
          
          # a raw csh script fragment
          line_list.append( content )
          
          if not analyze:
            line_list.extend( [ 'endif', '' ] )
        
        else:
          # a named executable block
          cs = xdb.findContent( name )
          if cs != None:
            
            # get the common script fragment from the common specification
            frag = cs.getContent( plat.getName() )
            
            if frag != None and frag:
              # substitute the content from the test into $(CONTENT) patterns
              frag = content_replace_re.sub( content, frag )
              
              # the invocation of the script fragment may expect and handle
              # non-zero exit statuses
              x = "0"
              if exitstat != None:
                if exitstat == "fail": x = "1"
                elif exitstat == "anyexit" or exitstat == "any": x = "-1"
              frag = expect_status_replace_re.sub( x, frag )
              
              if not cs.isAnalyze():
                line_list.extend( [ '', 'if ( $analyze == 0 ) then' ] )
              
              line_list.append( frag )
              
              if not cs.isAnalyze():
                line_list.extend( [ 'endif', '' ] )
          
          else:
            # could not find the name in the database; make sure the test fails
            line_list.extend( [ \
              '''echo "*** error: the test specification file refers to the "'"'"''' + \
                                                               name +'"'+ """'"'""",
              'echo "           execute fragment, but the fragment database did"',
              'echo "           not contain that fragment name"',
              'exit 1', '' ] )
    
    else:
      line_list.append('################ begin analyze script')
      line_list.append('')

      paramset = tspec.getParameterSet()
      if paramset != None:
          psetD = paramset.getParameters()
          if len(psetD) > 0:
              # provide the parameter names and values that formed the
              # children tests
              for n,L in psetD.items():
                  n2 = '_'.join( n )
                  L2 = [ '/'.join( v ) for v in L ]
                  line_list.append( 'set PARAM_'+n2+' = ( ' + ' '.join(L2) + ' )' )
                  line_list.append( 'echo "PARAM_'+n2+' = $PARAM_'+n2+'"' )
              line_list.append('')

      line_list.extend( string.split( tspec.getAnalyze('scriptfrag'), os.linesep ) )
      line_list.append('')
      line_list.append('################ end analyze script')
      line_list.append('')
    
    # lastly, check for a diff status
    
    line_list.extend( [ \
      '',
      '# check for a diff status before quitting',
      'echo " "',
      'if ( "$have_diff" != "no" ) then',
      '  echo "*** at least one diff test showed differences; exiting diff"',
      '  exit ' + str(diffExitStatus),
      'endif',
      'echo "++++++++++++++++ SUCCESS: ' + idstr + '"' ] )
    
    line_list.append( 'exit 0' )
    
    fp = open( scriptname, 'w' )
    for l in line_list:
      fp.write( l + '\n' )
    fp.close()
    
    perm = stat.S_IMODE( os.stat(scriptname)[stat.ST_MODE] )
    perm |= stat.S_IXUSR
    try:
      os.chmod( scriptname, perm )
    except:
      pass
