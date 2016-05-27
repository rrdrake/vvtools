#!/usr/bin/env python

import os, sys
import string, re
import types

import xmlwrapper
import TestSpec
import FilterExpressions


class TestSpecError(Exception):
    def __init__(self, msg=None):
      if msg != None:
        self.msg = "Error: " + msg
      else:
        self.msg = "Error: (unknown)"
    def __str__(self): return self.msg


###########################################################################

def createTestObjects( rootpath, relpath, force_params=None, ufilter=None ):
    """
    The 'rootpath' is the top directory of the file scan.  The 'relpath' is
    the name of the test file relative to 'rootpath' (it must not be an
    absolute path).  If 'force_params' is not None, then any parameters in
    the test that are in the 'force_params' dictionary have their values
    replaced for that parameter name.  The 'ufilter' argument must be None
    or an ExpressionSet instance.
    
    Returns a list of TestSpec objects, including a "parent" test if needed.

    Can use a (nested) rtest element to cause another test to be defined.
        
        <rtest name="mytest">
          <rtest name="mytest_fast"/>
          ...
        </rtest>

    then use the testname="..." attribute to filter XML elements.

        <keywords testname="mytest_fast"> fast </keywords>
        <keywords testname="mytest"> long </keywords>

        <parameters testname="mytest" np="1 2 4 8 16 32 64 128 256 512"/>
        <parameters testname="mytest_fast" np="1 2 4 8"/>
        
        <execute testname="mytest_fast" name="exodiff"> ... </execute>

        <analyze testname="mytest">
          ...
        </analyze>
        <analyze testname="mytest_fast">
          ...
        </analyze>
    """
    assert not os.path.isabs( relpath )

    if ufilter == None:
      ufilter = FilterExpressions.ExpressionSet()
    
    fname = os.path.join( rootpath, relpath )
    ext = os.path.splitext( relpath )[1]
    
    if ext == '.xml':
        
        try:
            filedoc = readxml( fname )
        except xmlwrapper.XmlError:
            raise TestSpecError( str( sys.exc_info()[1] ) )
        
        nameL = testNameList( filedoc )
        if nameL == None:
            return []
        
        tL = []
        for tname in nameL:
            L = createTestName( tname, filedoc, rootpath, relpath,
                                force_params, ufilter )
            tL.extend( L )
    
    elif ext == '.vvt':
        
        vspecs = ScriptReader( fname )
        nameL = testNameList_scr( vspecs )
        tL = []
        for tname in nameL:
            L = createScriptTest( tname, vspecs, rootpath, relpath,
                                  force_params, ufilter )
            tL.extend( L )

    else:
        raise Exception( "invalid file extension: "+ext )

    return tL


def createTestName( tname, filedoc, rootpath, relpath, force_params, ufilter ):
    """
    """
    if not parseIncludeTest( filedoc, tname, ufilter ):
      return []
    
    paramD = parseTestParameters( filedoc, tname, ufilter, force_params )
    
    keywords = parseKeywords( filedoc, tname, ufilter )
    
    do_all = ufilter.getAttr('include_all',0)

    if not do_all and not ufilter.satisfies_nonresults_keywords( keywords ):
      return []
    
    # create the test instances
    
    testL = []
    
    if len(paramD) == 0:
      
      if do_all or ufilter.evaluate_parameters( {} ):
        t = TestSpec.TestSpec( tname, rootpath, relpath )
        testL.append(t)
    
    else:
      
      # take a cartesian product of all the parameter values but apply
      # parameter filtering (this may change the paramD)
      instanceL = cartesian_product_and_filter( paramD, ufilter )

      for pdict in instanceL:
        # create the test and add to test list
        t = TestSpec.TestSpec( tname, rootpath, relpath )
        t.setParameters( pdict )
        testL.append(t)
      
    # parse and set the rest of the XML file for each test
    
    finalL = []
    parent = None
    for t in testL:
      
      t.setKeywords( keywords )
      
      parseAnalyze      ( t, filedoc, ufilter )
      parseTimeouts     ( t, filedoc, ufilter )
      parseExecuteList  ( t, filedoc, ufilter )
      parseFiles        ( t, filedoc, ufilter )
      parseBaseline     ( t, filedoc, ufilter )
      
      if do_all or ufilter.file_search(t):
        
        finalL.append(t)
        
        if parent == None and t.getAnalyzeScript() != None:
          parent = t.makeParent()
          parent.setParameterSet( paramD )
          if parent.getExecuteDirectory() == t.getExecuteDirectory():
            # a test with no parameters but with an analyze script
            parent = None
            t.appendExecutionFragment( t.getAnalyzeScript(), None, "yes" )
            t.setAnalyze( None )
    
    if parent != None:
      for t in finalL:
        t.setAnalyze( None )
        t.setParent( parent.getExecuteDirectory() )
      finalL.append( parent )
    
    return finalL


def createScriptTest( tname, vspecs, rootpath, relpath,
                      force_params, ufilter ):
    """
    """
    if not parseEnableTest( vspecs, tname, ufilter ):
        return []
    
    paramD = parseTestParameters_scr( vspecs, tname, ufilter, force_params )
    
    keywords = parseKeywords_scr( vspecs, tname, ufilter )
    
    do_all = ufilter.getAttr('include_all',0)

    if not do_all and not ufilter.satisfies_nonresults_keywords( keywords ):
        return []
    
    testL = []

    if len(paramD) == 0:

        if do_all or ufilter.evaluate_parameters( {} ):
            t = TestSpec.TestSpec( tname, rootpath, relpath )
            testL.append(t)

    else:
        
        # take a cartesian product of all the parameter values but apply
        # parameter filtering (this may change the paramD)
        instanceL = cartesian_product_and_filter( paramD, ufilter )
        
        for pdict in instanceL:
            # create the test and add to test list
            t = TestSpec.TestSpec( tname, rootpath, relpath )
            t.setParameters( pdict )
            testL.append(t)
    
    finalL = []
    parent = None
    for t in testL:
      
      t.setScriptForm( vspecs.getForm() )
      t.setKeywords( keywords )
      
      if do_all or ufilter.file_search(t):
        
        finalL.append(t)
        
        #parseAnalyze      ( t, filedoc, ufilter )
        #parseTimeouts     ( t, filedoc, ufilter )
        #parseExecuteList  ( t, filedoc, ufilter )
        #parseFiles        ( t, filedoc, ufilter )
        #parseBaseline     ( t, filedoc, ufilter )
        #
        #if parent == None and t.getAnalyzeScript() != None:
        #  parent = t.makeParent()
        #  parent.setParameterSet( paramD )
        #  if parent.getExecuteDirectory() == t.getExecuteDirectory():
        #    # a test with no parameters but with an analyze script
        #    parent = None
        #    t.appendExecutionFragment( t.getAnalyzeScript(), None, "yes" )
        #    t.setAnalyze( None )
    
    if parent != None:
      for t in finalL:
        t.setAnalyze( None )
        t.setParent( parent.getExecuteDirectory() )
      finalL.append( parent )

    return finalL


def refreshTest( testobj, ufilter=None ):
    """
    Parses the test source file and resets the settings for the given test.
    The test name is not changed.  The parameters in the test XML file are
    not considered; instead, the parameters already defined in the test
    object are used.

    If the test XML contains bad syntax, a TestSpecError is raised.
    
    Returns false if any of the filtering would exclude this test.
    """
    fname = testobj.getFilename()
    ext = os.path.splitext( fname )[1]

    keep = True
    
    if ext == '.xml':
        
        filedoc = readxml( fname )

        # run through the test name logic to check XML validity
        nameL = testNameList(filedoc)
        
        tname = testobj.getName()
        
        if ufilter == None:
          ufilter = FilterExpressions.ExpressionSet()
        
        if not testobj.getParent():
          paramD = parseTestParameters( filedoc, tname, ufilter, None )
          cartesian_product_and_filter( paramD, ufilter )
          testobj.setParameterSet( paramD )
        
        if not parseIncludeTest( filedoc, tname, ufilter ):
          keep = False
        
        keywords = parseKeywords( filedoc, tname, ufilter )
        testobj.setKeywords( keywords )
        
        if not ufilter.satisfies_keywords( testobj.getKeywords(1) ):
          keep = False
        
        if not ufilter.evaluate_parameters( testobj.getParameters() ):
          keep = False
        
        parseFiles       ( testobj, filedoc, ufilter )
        parseAnalyze     ( testobj, filedoc, ufilter )
        parseTimeouts    ( testobj, filedoc, ufilter )
        parseExecuteList ( testobj, filedoc, ufilter )
        parseBaseline    ( testobj, filedoc, ufilter )
        
        if ufilter.getAttr('include_all',0):
          return True
        
        if not ufilter.file_search(testobj):
          keep = False

    elif ext == '.vvt':
        
        vspecs = ScriptReader( fname )
        
        testobj.setScriptForm( vspecs.getForm() )

        # run through the test name logic to check validity
        nameL = testNameList_scr( vspecs )

        tname = testobj.getName()

        if ufilter == None:
          ufilter = FilterExpressions.ExpressionSet()
        
        if not testobj.getParent():
          paramD = parseTestParameters_scr( vspecs, tname, ufilter, None )
          cartesian_product_and_filter( paramD, ufilter )
          testobj.setParameterSet( paramD )
        
        if not parseEnableTest( vspecs, tname, ufilter ):
          keep = False
        
        keywords = parseKeywords_scr( vspecs, tname, ufilter )
        testobj.setKeywords( keywords )
        
        if not ufilter.satisfies_keywords( testobj.getKeywords(1) ):
          keep = False
        
        if not ufilter.evaluate_parameters( testobj.getParameters() ):
          keep = False
        
        #parseFiles       ( testobj, filedoc, ufilter )
        #parseAnalyze     ( testobj, filedoc, ufilter )
        #parseTimeouts    ( testobj, filedoc, ufilter )
        #parseExecuteList ( testobj, filedoc, ufilter )
        #parseBaseline    ( testobj, filedoc, ufilter )
        
        if ufilter.getAttr('include_all',0):
          return True
        
        #if not ufilter.file_search(testobj):
        #  keep = False

    else:
        raise Exception( "invalid file extension: "+ext )
    
    return keep


##########################################################################

def toString( tspec ):
    """
    Returns a string with no newlines containing the file path, parameter
    names/values, and attribute names/values.
    """
    assert tspec.getName() and tspec.getRootpath() and tspec.getFilepath()
    
    s = tspec.getName() + \
        ' "' + escape_file( tspec.getRootpath() ) + '" "' + \
               escape_file( tspec.getFilepath() ) + '"'
    
    pxdir = tspec.getParent()
    if pxdir != None:
      s = s + ' "_parent_=' + escape_file(pxdir) + '"'
    
    L = tspec.getKeywords()
    if len(L) > 0:
      s = s + ' "_keywords_=' + string.join(L) + '"'
    
    L = tspec.getParameters().items()
    L.sort()
    for n,v in L:
      s = s + ' ' + n + '=' + v
    
    L = tspec.getAttrs().keys()
    L.sort()
    for n in L:
      v = tspec.getAttr(n)
      if type(v) == types.StringType:
        v1 = ''
        for c in v:
          v1 = v1 + inout_chars.get(c,' ')
        s = s + ' "' + n + '=S' + v1 + '"'
      elif type(v) == types.IntType:
        s = s + ' "' + n + '=I' + str(v) + '"'
      elif type(v) == types.FloatType:
        s = s + ' "' + n + '=F' + str(v) + '"'
      elif type(v) == types.NoneType:
        s = s + ' "' + n + '=N"'
      else:
        raise ValueError( "unsupported attribute value type for " + \
                          n + ": " + str(type(v)) )
    
    return s


def fromString( strid ):
    """
    Creates and returns a partially filled TestSpec object from a string
    produced by the toString() method.  The values that are filled in are the
    name, root path, file path, parameter names/values, and attribute
    names/values.
    """
    qtoks, toks = special_tokenize(strid)
    
    if len(toks) < 1 or len(qtoks) < 2:
      raise TestSpecError( "fromString(): corrupt or unknown string format" )
    
    name = toks.pop(0)
    root = qtoks.pop(0)
    path = qtoks.pop(0)
    
    tspec = TestSpec.TestSpec( name, root, path )
    
    if len(toks) > 0:
      params = {}
      for tok in toks:
        L = string.split( tok, '=', 1 )
        if len(L) != 2:
          raise TestSpecError( \
                  "fromString(): corrupt or unknown string format: " + tok )
        params[ L[0] ] = L[1]
      tspec.setParameters( params )
    
    for tok in qtoks:
      nvL = string.split( tok, '=', 1 )
      if len(nvL) != 2 or len(nvL[0]) == 0 or len(nvL[1]) == 0:
        raise TestSpecError( \
                "fromString(): corrupt or unknown string format: " + tok )
      if nvL[0] == '_parent_':
        tspec.setParent( nvL[1] )
      elif nvL[0] == '_keywords_':
        tspec.setKeywords( string.split( nvL[1] ) )
      elif nvL[1][0] == 'I': tspec.setAttr( nvL[0], int(nvL[1][1:]) )
      elif nvL[1][0] == 'F': tspec.setAttr( nvL[0], float(nvL[1][1:]) )
      elif nvL[1][0] == 'N': tspec.setAttr( nvL[0], None )
      else:                  tspec.setAttr( nvL[0], nvL[1][1:] )
    
    return tspec


def special_tokenize(s):
    """
    """
    toks = []
    qtoks = []
    inquote = 0
    tok = None
    slen = len(s)
    i = 0
    while i < slen:
      c = s[i]
      if c == '"':
        if inquote:
          inquote = 0
          qtoks.append(tok)
          tok = None
        else:
          inquote = 1
          tok = ''
      elif inquote:
        if c == '\\':
          i = i + 1
          if i < slen:
            if s[i] == 't':
              tok = tok + '\t'
            elif s[i] == 'n':
              tok = tok + os.linesep
            else:
              tok = tok + s[i]
          else:
            tok = tok + '\\'
        else:
          tok = tok + c
      elif c == ' ':
        if tok:
          toks.append(tok)
          tok = ""
      else:
        if tok == None:
          tok = ''
        tok = tok + c
      i = i + 1
    
    if tok != None:
      if inquote: qtoks.append(tok)
      else:       toks.append(tok)
    
    return qtoks, toks


inout_chars = {}
for c in """0123456789abcdefghijklmnopqrstuvwxyz""" + \
         """ABCDEFGHIJKLMNOPQRSTUVWXYZ!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~""" + \
         string.whitespace:
  if   c == '"':               inout_chars[c] = '\\"'
  elif c == '\\':              inout_chars[c] = '\\\\'
  elif c == '\t':              inout_chars[c] = '\\t'
  elif c == '\n':              inout_chars[c] = '\\n'
  elif c == '\r':              inout_chars[c] = ''
  elif c in string.whitespace: inout_chars[c] = ' '
  else:                        inout_chars[c] = c

def escape_file(s):
    s2 = ''
    for c in s:
      if   c == '"':  s2 = s2 + '\\"'
      elif c == '\\': s2 = s2 + '\\\\'
      else:           s2 = s2 + c
    return s2


###########################################################################

class ScriptReader:
    
    def __init__(self, filename):
        """
        """
        self.filename = filename
        
        self.shebang = None
        self.speclineL = []  # list of [line number, raw spec string]
        self.specL = []  # list of ScriptSpec objects

        self.readfile( filename )

    def basename(self):
        """
        Returns the base name of the source file without the extension.
        """
        return os.path.splitext( os.path.basename( self.filename ) )[0]
    
    def getForm(self):
        """
        """
        if self.shebang:
            return ('script', 'shebang='+self.shebang)
        return ('script',)

    def getSpecList(self, specname):
        """
        Returns a list of ScriptSpec objects whose keyword equals 'specname'.
        The order is the same as in the source test script.
        """
        L = []
        for sspec in self.specL:
            if sspec.keyword == specname:
                L.append( sspec )
        return L

    vvtpat = re.compile( '[ \t]*#[ \t]*VVT[ \t]*:' )
    cmtpat = re.compile( '[ \t]*#+$' )

    def readfile(self, filename):
        """
        """
        fp = open( filename )
        
        try:
            
            line = fp.readline()
            lineno = 1

            if line[:2] == '#!':
                self.shebang = line[2:].strip()
                line = fp.readline()
                lineno += 1
            
            spec = None
            while line:
                done,spec = self.parse_line( line, spec, lineno )
                if done:
                    break
                line = fp.readline()
                lineno += 1

            if spec != None:
                self.speclineL.append( spec )
        
        except:
            fp.close()
            raise
        
        fp.close()

        self.process_specs()

        self.filename = filename
    
    def parse_line(self, line, spec, lineno):
        """
        Parse a line of the script file.
        """
        done = False
        line = line.strip()
        if line and not ScriptReader.cmtpat.match( line ):
            if line[0] != '#':
                done = True
            m = ScriptReader.vvtpat.match( line )
            if m != None:
                spec = self.parse_spec( line[m.end():], spec, lineno )
            else:
                # not #VVT: and not an empty comment or empty line
                done = True
        
        elif spec != None:
            # an empty line or comment stops any continuation
            self.speclineL.append( spec )
            spec = None

        return done,spec

    def parse_spec(self, line, spec, lineno):
        """
        Parse the contents of the line after a #VVT: marker.
        """
        line = line.strip()
        if line:
            if line[0] == ':':
                # continuation of previous spec
                if spec == None:
                    raise TestSpecError( "A #VVT:: continuation was found" + \
                            " but there is nothing to continue, line " + \
                            str( lineno ) )
                elif len(line) > 1:
                    spec[1] += ' ' + line[1:]
            elif spec == None:
                # no existing spec and new spec found
                spec = [ lineno, line ]
            else:
                # spec exists and new spec found
                self.speclineL.append( spec )
                spec = [ lineno, line ]
        elif spec != None:
            # an empty line stops any continuation
            self.speclineL.append( spec )
            spec = None

        return spec

    # the following pattern should match the first paren enclosed stuff,
    # but parens within double quotes are ignored
    #   1. this would match as few chars within parens
    #       [(].*?[)]
    #   2. this would match as few chars within parens unless there is a
    #      double quote in the parens
    #       [(][^"]*?[)]
    #   3. this would match as few chars within double quotes
    #       ["].*?["]
    #   4. this would match as few chars within double quotes possible
    #      chars on either side (but as few of them as well)
    #       .*?["].*?["].*?
    #   5. this will match either number 2 or number 4 above as a regex group
    #       ([^"]*?|.*?["].*?["].*?)
    #   6. this adds back the parens on the outside
    #       [(]([^"]*?|.*?["].*?["].*?)[)]
    ATTRPAT = re.compile( '[(]([^"]*?|.*?["].*?["].*?)[)]' )

    # this pattern matches everything up to the first ':' or '=' or paren
    DEFPAT = re.compile( '.*?[:=(]' )

    def process_specs(self):
        """
        Turns the list of string specifications into keywords with attributes
        and content.
        """
        ppat = ScriptReader.ATTRPAT
        kpat = ScriptReader.DEFPAT
        
        for lineno,line in self.speclineL:
            key = None
            val = None
            attrs = None
            m = kpat.match( line )
            if m:
                key = line[:m.end()-1].strip()
                rest = line[m.end()-1:]
                if rest and rest[0] == '(':
                    # extract attribute(s)
                    m = ppat.match( rest )
                    if m:
                        attrs = rest[:m.end()]
                        attrs = attrs.lstrip('(').rstrip(')').strip()
                        rest = rest[m.end():].strip()
                        if rest and rest[0] in ':=':
                            val = rest[1:]
                        elif rest:
                            raise TestSpecError( \
                              'extra text following attributes, ' + \
                              'line ' + str(lineno) )
                    else:
                        raise TestSpecError( \
                              'malformed attribute specification, ' + \
                              'line ' + str(lineno) )
                else:
                    val = rest[1:].strip()
            else:
                key = line.strip()
            
            if not key:
                raise TestSpecError( \
                              'missing or invalid specification keyword, ' + \
                              'line ' + str(lineno) )

            if attrs:
                # process the attributes into a dictionary
                D = {}
                for s in attrs.split(','):
                    s = s.strip().strip('"').strip()
                    i = s.find( '=' )
                    if i == 0:
                        raise TestSpecError( \
                                'invalid attribute specification, ' + \
                                'line ' + str(lineno) )
                    elif i > 0:
                        n = s[:i]
                        v = s[i+1:].strip().strip('"')
                        D[n] = v
                    elif s:
                        D[s] = ''
                attrs = D

            specobj = ScriptSpec( lineno, key, attrs, val )
            self.specL.append( specobj )


class ScriptSpec:

    def __init__(self, lineno, keyword, attrs, value):
        self.keyword = keyword
        self.attrs = attrs
        self.value = value
        self.lineno = lineno


def testNameList_scr( vspecs ):
    """
    Determine the test name and check for validity.
    Returns a list of test names.
    """
    L = []

    for spec in vspecs.getSpecList( "name" ):

        if spec.attrs:
            raise TestSpecError( 'no attributes allowed here, ' + \
                                 'line ' + str(spec.lineno) )

        name = spec.value
        if not name or not allowableString(name):
            raise TestSpecError( 'missing or invalid test name, ' + \
                                 'line ' + str(spec.lineno) )
        L.append( name )

    if len(L) == 0:
        # the name defaults to the basename of the script file
        L.append( vspecs.basename() )

    return L


def parseEnableTest( vspecs, tname, ufilter ):
    """
    Parse syntax that will filter out this test by platform or build option.
    Returns false if the test is to be disabled/excluded.
    
    Platform expressions and build options use word expressions.
    
        #VVT: enable (platforms="not SunOS and not Linux")
        #VVT: enable (options="not dbg and ( tridev or tri8 )")
        #VVT: enable (platforms="...", options="...")
    
    If both platform and option expressions are given, their results are
    ANDed together.  If more than one "enable" block is given, each must
    result in True for the test to be included.
    """
    if ufilter.getAttr('include_all',0):
        return True
    
    # first, evaluate based purely on the platform restrictions
    pev = PlatformEvaluator_scr( vspecs, tname, ufilter )
    if not ufilter.evaluate_platform_include( pev.satisfies_platform ):
        return False
    
    # second, evaluate based on the "options" attribute of "enable"
    for spec in vspecs.getSpecList( 'enable' ):
      
        if spec.attrs:
        
            if 'parameters' in spec.attrs or 'parameter' in spec.attrs:
                raise TestSpecError( "parameters attribute not " + \
                                     "allowed here, line " + str(spec.lineno) )

            if not testname_ok_scr( spec.attrs, tname, ufilter ):
              # the "enable" does not apply to this test name
              continue
            
            opexpr = spec.attrs.get( 'options',
                                     spec.attrs.get( 'option', None ) )
            if opexpr != None:
                opexpr = opexpr.strip()
                if opexpr and not ufilter.evaluate_option_expr( opexpr ):
                    return False
    
    return True


def parseKeywords_scr( vspecs, tname, ufilter ):
    """
    Parse the test keywords for the test script file.
    
      keywords : key1 key2
      keywords (testname=mytest) : key3
    
    Also includes the test name and the parameterize names.
    TODO: what other implicit keywords ??
    """
    keyD = {}
    
    keyD[tname] = None
    
    for spec in vspecs.getSpecList( 'keywords' ):
        
        if spec.attrs and \
           ( 'parameters' in spec.attrs or 'parameter' in spec.attrs ):
            raise TestSpecError( "parameters attribute not allowed here, " + \
                                 "line " + str(spec.lineno) )
        
        if not filterAttr_scr( spec.attrs, tname, {}, ufilter, spec.lineno ):
            continue
        
        for key in spec.value.strip().split():
            if allowableString(key):
                keyD[key] = None
            else:
                raise TestSpecError( 'invalid keyword: "'+key+'", line ' + \
                                     str(spec.lineno) )
    
    # the parameter names are included in the test keywords
    for spec in vspecs.getSpecList( 'parameterize' ):
        if not testname_ok_scr( spec.attrs, tname, ufilter ):
            continue
        L = spec.value.split( '=', 1 )
        if len(L) == 2 and L[0].strip():
            for k in [ n.strip() for n in L[0].strip().split(',') ]:
                keyD[k] = None
    
    L = keyD.keys()
    L.sort()
    return L


def parseTestParameters_scr( vspecs, tname, ufilter, force_params ):
    """
    Parses the parameter settings for a script test file.
        
        #VVT: parameterize : np=1 4
        #VVT: parameterize (testname=mytest_fast) : np=1 4
        #VVT: parameterize (platforms=Cray or redsky) : np=128
        #VVT: parameterize (options=not dbg) : np=32
        
        #VVT: parameterize : dt,dh = 0.1,0.2  0.01,0.02  0.001,0.002
        #VVT: parameterize : np,dt,dh = 1, 0.1  , 0.2
        #VVT::                          4, 0.01 , 0.02
        #VVT::                          8, 0.001, 0.002
    
    Returns a dictionary mapping combined parameter names to lists of the
    combined values.  For example,

        #VVT: parameterize : pA=value1 value2

    would return the dict

        { (pA,) : [ (value1,), (value2,) ] }

    And this
        
        #VVT: parameterize : pA=value1 value2
        #VVT: parameterize : pB=val1 val2

    would return

        { (pA,) : [ (value1,), (value2,) ],
          (pB,) : [ (val1,), (val2,) ] }

    And this

        #VVT: parameterize : pA,pB = value1,val1 value2,val2
    
    would return

        { (pA,pB) : [ (value1,val1), (value2,val2) ] }
    """
    cpat = re.compile( '[\t ]*,[\t ]*' )

    paramD = {}

    for spec in vspecs.getSpecList( 'parameterize' ):
        
        lnum = spec.lineno

        if spec.attrs and \
           ( 'parameters' in spec.attrs or 'parameter' in spec.attrs ):
            raise TestSpecError( "parameters attribute not allowed here, " + \
                                 "line " + str(lnum) )
        
        if not filterAttr_scr( spec.attrs, tname, {}, ufilter, lnum ):
            continue

        L = spec.value.split( '=', 1 )
        if len(L) < 2:
            raise TestSpecError( "invalid parameterize specification, " + \
                                 "line " + str(lnum) )
        if not L[0].strip():
            raise TestSpecError( "no parameter name given, " + \
                                 "line " + str(lnum) )
        
        nL = tuple( [ n.strip() for n in L[0].strip().split(',') ] )
        
        for n in nL:
            if not allowableVariable(n):
                raise TestSpecError( 'invalid parameter name: "'+n+'", ' + \
                                     'line ' + str(lnum) )

        if len(nL) == 1:
            
            if force_params != None and nL[0] in force_params:
                vL = force_params[ nL[0] ]
            else:
                vL = L[1].strip().split()
            
            for v in vL:
                if not allowableString(v):
                    raise TestSpecError( 'invalid parameter value: "' + \
                                         v+'", line ' + str(lnum) )
            
            paramD[ nL ] = [ (v,) for v in vL ]
        
        else:
            
            if force_params != None:
                for n in nL:
                    if n in force_params:
                        raise TestSpecError( 'cannot force a grouped ' + \
                                    'parameter name: "' + \
                                    n+'", line ' + str(lnum) )
            
            vL = []
            for s in cpat.sub( ',', L[1].strip() ).split():
                gL = s.split(',')
                if len(gL) != len(nL):
                    raise TestSpecError( 'malformed parameter list: "' + \
                                          v+'", line ' + str(lnum) )
                for v in gL:
                    if not allowableString(v):
                        raise TestSpecError( 'invalid parameter value: "' + \
                                             v+'", line ' + str(lnum) )
                vL.append( tuple(gL) )
            
            paramD[ nL ] = vL

    return paramD


def testname_ok_scr( attrs, tname, ufilter ):
    """
    """
    if attrs != None:
        tval = attrs.get( 'testname', None )
        if tval != None and not ufilter.evauate_testname_expr( tname, tval ):
            return False
    return True


def filterAttr_scr( attrs, testname, paramD, ufilter, lineno ):
    """
    Checks for known attribute names in the given 'attrs' dictionary.
    Returns False only if at least one attribute evaluates to false.
    """
    if attrs:

        for attrname,attrvalue in attrs.items():
            
            try:
                
                if attrname == "testname":
                    return ufilter.evauate_testname_expr( testname, attrvalue )
                
                elif attrname in ["platform","platforms"]:
                    return ufilter.evaluate_platform_expr( attrvalue )
                
                elif attrname in ["option","options"]:
                    return ufilter.evaluate_option_expr( attrvalue )
                
                elif attrname in ["parameter","parameters"]:
                    pf = FilterExpressions.ParamFilter(attrvalue)
                    return pf.evaluate( paramD )
            
            except ValueError:
                raise TestSpecError( 'invalid '+attrname+' expression, ' + \
                                     'line ' + lineno + ": " + \
                                     str(sys.exc_info()[1]) )
    
    return True


###########################################################################

xmldocreader = None

def readxml( filename ):
    """
    Uses the XML reader from the xmlwrapper module to read the XML file and
    return an XML DOM object.
    """
    global xmldocreader
    if xmldocreader == None:
        xmldocreader = xmlwrapper.XmlDocReader()
    return xmldocreader.readDoc( filename )


def testNameList( filedoc ):
    """
    Determine the test name and check for validity.  If this XML file is not
    an "rtest" then returns None.  Otherwise returns a list of test names.
    """
    if filedoc.name != "rtest":
        return None
    
    # determine the test name
    
    name = filedoc.getAttr('name', '').strip()
    if not name or not allowableString(name):
        raise TestSpecError( 'missing or invalid test name attribute, ' + \
                             'line ' + str(filedoc.line_no) )
    
    L = [ name ]
    for xnd in filedoc.matchNodes( ['rtest'] ):
        nm = xnd.getAttr('name', '').strip()
        if not nm or not allowableString(nm):
            raise TestSpecError( 'missing or invalid test name attribute, ' + \
                                 'line ' + str(xnd.line_no) )
        L.append( nm )

    return L


def filterAttr( attrname, attrvalue, testname, paramD, ufilter, lineno ):
    """
    Checks the attribute name for a filtering attributes.  Returns a pair of
    boolean values, (is filter, filter result).  The first is whether the
    attribute name is a filtering attribute, and if so, the second value is
    true/false depending on the result of applying the filter.
    """
    try:
      
      if attrname == "testname":
        return True, ufilter.evauate_testname_expr( testname, attrvalue )
      
      elif attrname in ["platform","platforms"]:
        return True, ufilter.evaluate_platform_expr( attrvalue )
      
      elif attrname in ["keyword","keywords"]:
        # TODO: deprecate keyword(s) attributes [Apr 2016]
        #raise TestSpecError( n + " attribute not allowed here, " + \
        #                     "line " + str(lineno) )
        L = attrvalue.split()
        if 'and' in L or 'or' in L or 'not' in L or \
           '(' in attrvalue or ')' in attrvalue:
          # allow keyword expressions for backward compatibility
          return True, ufilter.evaluate_keyword_expr( attrvalue )
        return True, ufilter.satisfies_nonresults_keywords( L, 1 )
      
      elif attrname in ["not_keyword","not_keywords"]:
        # TODO: deprecate not_keyword(s) attributes [Apr 2016]
        #raise TestSpecError( n + " attribute not allowed here, " + \
        #                     "line " + str(lineno) )
        v = not ufilter.satisfies_nonresults_keywords( attrvalue.split(), 1 )
        return True, v
      
      elif attrname in ["option","options"]:
        return True, ufilter.evaluate_option_expr( attrvalue )
      
      elif attrname in ["parameter","parameters"]:
        pf = FilterExpressions.ParamFilter(attrvalue)
        return True, pf.evaluate( paramD )
    
    except ValueError, e:
      raise TestSpecError( "bad " + attrname + " expression, line " + \
                           lineno + ": " + str(e) )
    
    return False, False


def parseTestParameters( filedoc, tname, ufilter, force_params ):
    """
    Parses the parameter settings for a test XML file.
    
      <parameterize paramname="value1 value2"/>
      <parameterize paramA="A1 A2"
                    paramB="B1 B2"/>
      <parameterize platforms="Linux or SunOS"
                    options="not dbg"
                    paramname="value1 value2"/>
    
    where paramname can be any string.  The second form creates combined
    parameters where the values are "zipped" together.  That is, paramA=A1
    and paramB=B1 then paramA=A2 and paramB=B2.  A separate test will NOT
    be created for the combination paramA=A1, paramB=B2, for example.
    
    Returns a dictionary mapping combined parameter names to lists of the
    combined values.  For example,

        <parameterize pA="value1 value2"/>

    would return the dict

        { (pA,) : [ (value1,), (value2,) ] }

    And this
        
        <parameterize pA="value1 value2"/>
        <parameterize pB="val1 val2"/>

    would return

        { (pA,) : [ (value1,), (value2,) ],
          (pB,) : [ (val1,), (val2,) ] }

    And this

        <parameterize pA="value1 value2" pB="val1 val2"/>
    
    would return

        { (pA,pB) : [ (value1,val1), (value2,val2) ] }
    """
    
    paramD = {}
    if force_params == None:
      force_params = {}
    
    for nd in filedoc.matchNodes(['parameterize$']):
      
      attrs = nd.getAttrs()
      
      pL = []
      skip = 0
      for n,v in attrs.items():
        
        if n in ["parameters","parameter"]:
          raise TestSpecError( n + " attribute not allowed here, " + \
                               "line " + str(nd.line_no) )
        
        # TODO: deprecate keyword(s) attributes [Apr 2016]
        #if n in ["keywords","keyword"]:
        #  raise TestSpecError( n + " attribute not allowed here, " + \
        #                       "line " + str(nd.line_no) )
        
        isfa, istrue = filterAttr( n, v, tname, None, ufilter, str(nd.line_no) )
        if isfa:
          if not istrue:
            skip = 1
            break
          continue
        
        if not allowableVariable(n):
          raise TestSpecError( 'bad parameter name: "' + n + '", line ' + \
                               str(nd.line_no) )
        
        vals = string.split(v)
        if len(vals) == 0:
          raise TestSpecError( "expected one or more values separated by " + \
                               "spaces, line " + str(nd.line_no) )
        
        for val in vals:
          if not allowableString(val):
            raise TestSpecError( 'bad parameter value: "' + val + '", line ' + \
                                 str(nd.line_no) )
        
        vals = force_params.get(n,vals)
        L = [ n ]
        L.extend( vals )
        
        for mL in pL:
          if len(L) != len(mL):
            raise TestSpecError( 'combined parameters must have the same ' + \
                                 'number of values, line ' + str(nd.line_no) )
        
        pL.append( L )
      
      if len(pL) > 0 and not skip:
        # TODO: the parameter names should really be sorted here in order
        #       to avoid duplicates if another parameterize comes along
        #       with a different order of the same names
        # the name(s) and each of the values are tuples
        if len(pL) == 1:
          L = pL[0]
          paramD[ (L[0],) ] = [ (v,) for v in L[1:] ]
        else:
          L = zip( *pL )
          paramD[ L[0] ] = L[1:]
    
    return paramD


def testname_ok( xmlnode, tname, ufilter ):
    """
    """
    tval = xmlnode.getAttr( 'testname', None )
    if tval != None and not ufilter.evauate_testname_expr( tname, tval ):
        return False
    return True


def parseKeywords( filedoc, tname, ufilter ):
    """
    Parse the test keywords for the test XML file.
    
      <keywords> key1 key2 </keywords>
      <keywords testname="mytest"> key3 </keywords>
    
    Also includes the name="..." on <execute> blocks, the parameter names in
    <parameterize> blocks, and the words in keywords="..." attributes.
    """
    keyD = {}
    
    keyD[tname] = None
    
    for nd in filedoc.matchNodes(['keywords$']):
      if not testname_ok( nd, tname, ufilter ):
        # skip this keyword set (filtered out based on test name)
        continue
      for key in string.split( nd.getContent() ):
        if allowableString(key):
          keyD[key] = None
        else:
          raise TestSpecError( 'invalid keyword: "' + key + '", line ' + \
                               str(nd.line_no) )
    
    for nd in filedoc.getSubNodes():
      if not testname_ok( nd, tname, ufilter ):
        continue
      if nd.name == 'parameterize':
        # the parameter names are included in the test keywords
        for n,v in nd.getAttrs().items():
          if n in ['parameter','parameters','keyword','keywords',
                   'platform','platforms','option','options','testname']:
            pass
          elif allowableVariable(n):
            keyD[ str(n) ] = None
      elif nd.name == 'execute':
        # the execute name is included in the test keywords
        n = nd.getAttr('name', None)
        if n != None:
          keyD[ str(n) ] = None
      
      # TODO: deprecate keyword(s) attributes [Apr 2016]
      if nd.name in ['parameterize','analyze','execute','timeout',
                     'copy_files','link_files','glob_copy','glob_link',
                     'baseline']:
        # look for keywords attribute and include those as test keywords
        kwstr = nd.getAttr( 'keywords', nd.getAttr( 'keyword', None ) )
        if kwstr != None:
          # can use this to find out if any tests use keywords attr
          #print 'NOTE: keyword attr in', nd.name, nd.filename, nd.line_no
          L = kwstr.split()
          if 'and' in L or 'or' in L or 'not' in L or \
             '(' in kwstr or ')' in kwstr:
            try:
              wx = FilterExpressions.WordExpression( kwstr )
              for k in wx.getWordList():
                keyD[ str(k) ] = None
            except:
              pass
          else:
            for k in L:
              keyD[ str(k) ] = None
    
    L = keyD.keys()
    L.sort()
    return L


def parseIncludeTest( filedoc, tname, ufilter ):
    """
    Parse syntax that will filter out this test by platform or build option.
    Returns false if the test is to be excluded.
    
    Platform expressions and build options use word expressions.
    
       <include platforms="not SunOS and not Linux"/>
       <include options="not dbg and ( tridev or tri8 )"/>
       <include platforms="..." options="..."/>
    
    If both platform and option expressions are given, their results are
    ANDed together.  If more than one <include> block is given, each must
    result in True for the test to be included.
    
    For backward compatibility, allow the following.
    
       <include platforms="SunOS Linux"/>

    """
    if ufilter.getAttr('include_all',0):
      return 1
    
    # first, evaluate based purely on the platform restrictions
    pev = PlatformEvaluator( filedoc, tname, ufilter )
    if not ufilter.evaluate_platform_include( pev.satisfies_platform ):
      return 0
    
    # second, evaluate based on the "options" attribute of <include>
    for nd in filedoc.matchNodes(['include$']):
      
      if nd.hasAttr( 'parameters' ) or nd.hasAttr( 'parameter' ):
        raise TestSpecError( 'the "parameters" attribute not allowed '
                             'here, line ' + str(nd.line_no) )

      if not testname_ok( nd, tname, ufilter ):
        # the <include> does not apply to this test name
        continue
      
      opexpr = nd.getAttr( 'options', nd.getAttr( 'option', None ) )
      if opexpr != None:
        opexpr = opexpr.strip()
        if opexpr and not ufilter.evaluate_option_expr( opexpr ):
          return 0
    
    return 1


class PlatformEvaluator:
    """
    This class is a helper to provide UserFilter an evaluator function.
    """
    
    def __init__(self, xmldoc, tname, ufilter):
        self.xmldoc = xmldoc
        self.tname = tname
        self.ufilter = ufilter
    
    def satisfies_platform(self, plat_name):
        """
        This function parses the test XML file for platform restrictions and
        returns true if the test would run under the given 'plat_name'.
        Otherwise, it returns false.
        """
        for nd in self.xmldoc.matchNodes(['include$']):
          
          if nd.hasAttr( 'parameters' ) or nd.hasAttr( 'parameter' ):
            raise TestSpecError( 'the "parameters" attribute not allowed '
                                 'here, line ' + str(nd.line_no) )
          
          if not testname_ok( nd, self.tname, self.ufilter ):
            # the <include> does not apply to this test name
            continue
          
          s = nd.getAttr( 'platforms', nd.getAttr( 'platform', None ) )
          if s != None:
            s = s.strip()
            
            if '/' in s:
              raise TestSpecError( 'invalid "platforms" attribute content '
                                   ', line ' + str(nd.line_no) )
            pL = s.split()
            if len(pL) > 1:
              if '(' in s or ')' in s or \
                 'or' in pL or 'and' in pL or 'not' in pL:
                # an expression syntax is being used
                wx = FilterExpressions.WordExpression(s)
              else:
                # assume list of platform names to include; this is for
                # backward compatibility (no uses since December 2014)
                wx = FilterExpressions.WordExpression( ' or '.join( pL ) )
            else:
              wx = FilterExpressions.WordExpression(s)
            
              wx.evaluate( lambda tok: tok == plat_name )
            if not wx.evaluate( lambda tok: tok == plat_name ):
              return 0
        
        return 1


class PlatformEvaluator_scr:
    """
    This class is a helper to provide UserFilter an evaluator function.
    """
    
    def __init__(self, vspecs, tname, ufilter):
        self.vspecs = vspecs
        self.tname = tname
        self.ufilter = ufilter
    
    def satisfies_platform(self, plat_name):
        """
        This function parses the test header for platform restrictions and
        returns true if the test would run under the given 'plat_name'.
        Otherwise, it returns false.
        """
        for spec in self.vspecs.getSpecList( 'enable' ):
            
            if spec.attrs:

                if 'parameters' in spec.attrs or 'parameter' in spec.attrs:
                    raise TestSpecError( "parameters attribute not allowed here, " + \
                                         "line " + str(spec.lineno) )
                
                if not testname_ok_scr( spec.attrs, self.tname, self.ufilter ):
                  # the "enable" does not apply to this test name
                  continue
                
                s = spec.attrs.get( 'platforms',
                                    spec.attrs.get( 'platform', None ) )
                if s != None:
                    s = s.strip()
                    if '/' in s:
                        raise TestSpecError( \
                            'invalid "platforms" attribute value '
                            ', line ' + str(spec.lineno) )
                    wx = FilterExpressions.WordExpression(s)
                    if not wx.evaluate( lambda tok: tok == plat_name ):
                        return False
        
        return True


def parseAnalyze( t, filedoc, ufilter ):
    """
    Parse analyze scripts that get run after all parameterized tests complete.
    
       <analyze keywords="..." parameters="..." platform="...">
         script contents that post processes test results
       </analyze>
    """
    a = None
    
    ndL = filedoc.matchNodes(['analyze$'])
    
    for nd in ndL:
      
      skip = 0
      for n,v in nd.getAttrs().items():
        
        if n in ["parameter","parameters"]:
          raise TestSpecError( 'an <analyze> block cannot have a ' + \
                               '"parameters=..." attribute: ' + \
                               ', line ' + str(nd.line_no) )
        
        isfa, istrue = filterAttr( n, v, t.getName(), t.getParameters(),
                                   ufilter, str(nd.line_no) )
        if isfa and not istrue:
          skip = 1
          break
      
      if not skip:
        try:
          content = str( nd.getContent() )
        except:
          raise TestSpecError( 'the content in an <analyze> block must be ' + \
                               'ASCII characters, line ' + str(nd.line_no) )
        if a == None:
          a = content.strip()
        else:
          a += os.linesep + content.strip()
    
    t.setAnalyze( a )


def parseTimeouts( t, filedoc, ufilter ):
    """
    Parse test timeouts for the test XML file.
    
      <timeout value="120"/>
      <timeout platforms="SunOS" value="240"/>
      <timeout parameters="hsize=0.01" value="320"/>
    """
    specL = []
    
    for nd in filedoc.matchNodes(['timeout$']):
      
      skip = 0
      for n,v in nd.getAttrs().items():
        isfa, istrue = filterAttr( n, v, t.getName(), t.getParameters(),
                                   ufilter, str(nd.line_no) )
        if isfa and not istrue:
          skip = 1
          break
      
      if not skip:
        
        to = None
        if nd.hasAttr('value'):
          val = string.strip( nd.getAttr("value") )
          try: to = int(val)
          except:
            raise TestSpecError( 'timeout value must be an integer: "' + \
                                 val + '", line ' + str(nd.line_no) )
          if to < 0:
            raise TestSpecError( 'timeout value must be non-negative: "' + \
                                 val + '", line ' + str(nd.line_no) )
        
        if to != None:
          t.setTimeout( to )


def parseExecuteList( t, filedoc, ufilter ):
    """
    Parse the execute list for the test XML file.
    
      <execute> script language </execute>
      <execute name="aname"> arguments </execute>
      <execute platforms="SunOS" name="aname"> arguments </execute>
      <execute ifdef="ENVNAME"> arguments </execute>
      <execute expect="fail"> script </execute>
    
    If a name is given, the content is arguments to the named executable.
    Otherwise, the content is a script fragment.
    
    Returns a list of 3-tuples consisting of
    
      ( name, content, filterspec )
    
    where the name may be None.
    """
    t.resetExecutionList()
    
    for nd in filedoc.matchNodes(["execute$"]):
      
      skip = 0
      for n,v in nd.getAttrs().items():
        isfa, istrue = filterAttr( n, v, t.getName(), t.getParameters(),
                                   ufilter, str(nd.line_no) )
        if isfa and not istrue:
          skip = 1
          break
      
      if nd.hasAttr('ifdef'):
        L = string.split( nd.getAttr('ifdef') )
        for n in L:
          if not allowableVariable(n):
            raise TestSpecError( 'invalid environment variable name: "' + \
                                 n + '"' + ', line ' + str(nd.line_no) )
        for n in L:
          if not os.environ.has_key(n):
            skip = 1
            break
      
      if not skip:
        
        xname = nd.getAttr('name', None)
        
        analyze = "no"
        if xname == None:
          if string.lower( string.strip( nd.getAttr('analyze','') ) ) == 'yes':
            analyze = "yes"
        else:
          if not xname or not allowableString(xname):
            raise TestSpecError( 'invalid name value: "' + xname + \
                                 '", line ' + str(nd.line_no) )
        
        xstatus = nd.getAttr( 'expect', None )
        
        content = nd.getContent()
        if content == None: content = ''
        else:               content = string.strip(content)
        
        if xname == None:
          t.appendExecutionFragment( content, xstatus, analyze )
        else:
          t.appendNamedExecutionFragment( xname, content, xstatus )


def variableExpansion( tname, platname, paramD, fL ):
    """
    Replaces shell style variables in the given file list with their values.
    For example $np or ${np} is replaced with 4.  Also replaces NAME and
    PLATFORM with their values.  The 'fL' argument can be a list of strings
    or a list of [string 1, string 2] pairs.  Dollar signs preceeded by a
    backslash are not expanded and the backslash is removed.
    """
    # these patterns are not needed but I was so happy with myself for
    # figuring out how to match csh style variables with regex that I
    # can't get myself to delete them :)
    # p1 = re.compile( '(?<![\\\\])[$][a-zA-Z]+[a-zA-Z0-9]*' )
    # p2 = re.compile( '(?<![\\\\])[$][{][a-zA-Z]+[a-zA-Z0-9]*[}]' )
    
    if platname == None: platname = ''
    
    if len(fL) > 0:
      
      # substitute parameter values for $PARAM, ${PARAM}, and {$PARAM} patterns;
      # also replace the special NAME variable with the name of the test and
      # PLATFORM with the name of the current platform
      for n,v in paramD.items() + [('NAME',tname)] + [('PLATFORM',platname)]:
        pat1 = re.compile( '[{](?<![\\\\])[$]' + n + '[}]' )
        pat2 = re.compile( '(?<![\\\\])[$][{]' + n + '[}]' )
        pat3 = re.compile( '(?<![\\\\])[$]' + n + '(?![_a-zA-Z0-9])' )
        if type(fL[0]) == types.ListType:
          for fpair in fL:
            f,t = fpair
            f,n = pat1.subn( v, f )
            f,n = pat2.subn( v, f )
            f,n = pat3.subn( v, f )
            if t != None:
              t,n = pat1.subn( v, t )
              t,n = pat2.subn( v, t )
              t,n = pat3.subn( v, t )
            fpair[0] = f
            fpair[1] = t
            # TODO: replace escaped $ with a dollar
        else:
          for i in range(len(fL)):
            f = fL[i]
            f,n = pat1.subn( v, f )
            f,n = pat2.subn( v, f )
            f,n = pat3.subn( v, f )
            fL[i] = f
      
      # replace escaped dollar with just a dollar
      patD = re.compile( '[\\\\][$]' )
      if type(fL[0]) == types.ListType:
        for fpair in fL:
          f,t = fpair
          f,n = patD.subn( '$', f )
          if t != None:
            t,n = patD.subn( '$', t )
          fpair[0] = f
          fpair[1] = t
      else:
        for i in range(len(fL)):
          f = fL[i]
          f,n = patD.subn( '$', f )
          fL[i] = f


def collectFileNames( nd, flist, tname, paramD, ufilter ):
    """
    Helper function that parses file names in content with optional linkname
    attribute:
    
        <something platforms="SunOS"> file1.C file2.C </something>
    
    or
    
        <something linkname="file1_copy.dat file2_copy.dat">
          file1.C file2.C
        </something>
    
    Returns a list of (source filename, link filename).
    """
    
    fileL = string.split( nd.getContent() )
    if len(fileL) > 0:
      
      skip = 0
      for n,v in nd.getAttrs().items():
        isfa, istrue = filterAttr( n, v, tname, paramD,
                                   ufilter, str(nd.line_no) )
        if isfa and not istrue:
          skip = 1
          break
      
      if not skip:
        
        fL = []
        tnames = nd.getAttr( 'linkname',
                 nd.getAttr('copyname',
                 nd.getAttr('test_name',None) ) )
        if tnames != None:
          
          tnames = tnames.split()
          if len(tnames) != len(fileL):
            raise TestSpecError( 'the number of file names in the ' + \
               '"linkname" attribute must equal the number of names in ' + \
               'the content (' + str(len(tnames)) + ' != ' + str(len(fileL)) + \
               '), line ' + str(nd.line_no) )
          for i in range(len(fileL)):
            if os.path.isabs(fileL[i]) or os.path.isabs(tnames[i]):
              raise TestSpecError( 'file names cannot be absolute paths, ' + \
                                   'line ' + str(nd.line_no) )
            fL.append( [str(fileL[i]), str(tnames[i])] )
        
        else:
          for f in fileL:
            if os.path.isabs(f):
              raise TestSpecError( 'file names cannot be absolute paths, ' + \
                                   'line ' + str(nd.line_no) )
            fL.append( [str(f), None] )
        
        variableExpansion( tname, ufilter.platformName(), paramD, fL )
        
        flist.extend(fL)
    
    else:
      raise TestSpecError( 'expected a list of file names as content' + \
                           ', line ' + str(nd.line_no) )


def globFileNames( nd, flist, t, ufilter, nofilter=0 ):
    """
    Queries the file system for file names.  Syntax is
    
      <glob_copy parameters="..."> ${NAME}_*.base_exo </glob_copy>
      <glob_link platforms="..." > ${NAME}.*exo       </glob_link>
    
    Returns a list of (source filename, test filename).
    """
    tname = t.getName()
    paramD = t.getParameters()
    homedir = t.getDirectory()
    
    globL = nd.getContent().strip().split()
    if len(globL) > 0:
      
      skip = 0
      for n,v in nd.getAttrs().items():
        isfa, istrue = filterAttr( n, v, tname, paramD,
                                   ufilter, str(nd.line_no) )
        if nofilter and isfa:
          raise TestSpecError( 'filter attributes not allowed here' + \
                               ', line ' + str(nd.line_no) )
        if isfa and not istrue:
          skip = 1
          break
      
      if not skip:
        
        # first, substitute variables into the file names
        variableExpansion( tname, ufilter.platformName(), paramD, globL )
        
        for fn in globL:
          flist.append( [str(fn),None] )
    
    else:
      raise TestSpecError( 'expected a list of file names as content' + \
                           ', line ' + str(nd.line_no) )


def parseFiles( t, filedoc, ufilter ):
    """
    Parse the files to copy and soft link for the test XML file.
    
      <link_files> file1.C file2.F </link_files>
      <link_files linkname="f1.C f2.F"> file1.C file2.F </link_files>
      <copy_files platforms="SunOS"> file1.C file2.F </copy_files>
      <copy_files parameters="np=4" copyname="in4.exo"> in.exo </copy_files>
      
    For backward compatibility, "test_name" is accepted:

      <copy_files test_name="f1.C f2.F"> file1.C file2.F </copy_files>
    
    Deprecated:
      <glob_link> ${NAME}_data.txt </glob_link>
      <glob_copy> files_to_glob.* </glob_copy>
    
    Also here is parsing of test source files
    
      <source_files> file1 ${NAME}_*_globok.baseline <source_files>
    
    which are just files that are needed by (dependencies of) the test.
    """
    
    cpfiles = []
    lnfiles = []
    
    for nd in filedoc.matchNodes(["copy_files$"]):
      collectFileNames( nd, cpfiles, t.getName(), t.getParameters(), ufilter )
    
    for nd in filedoc.matchNodes(["link_files$"]):
      collectFileNames( nd, lnfiles, t.getName(), t.getParameters(), ufilter )
    
    # include mirror_files for backward compatibility
    for nd in filedoc.matchNodes(["mirror_files$"]):
      collectFileNames( nd, lnfiles, t.getName(), t.getParameters(), ufilter )
    
    for nd in filedoc.matchNodes(["glob_link$"]):
      # This construct is deprecated [April 2016].
      globFileNames( nd, lnfiles, t, ufilter )
    
    for nd in filedoc.matchNodes(["glob_copy$"]):
      # This construct is deprecated [April 2016].
      globFileNames( nd, cpfiles, t, ufilter )
    
    t.setLinkFiles( lnfiles )
    t.setCopyFiles( cpfiles )
    
    fL = []
    for nd in filedoc.matchNodes(["source_files$"]):
      globFileNames( nd, fL, t, ufilter, 1 )
    t.setSourceFiles( map( lambda T: T[0], fL ) )


def parseBaseline( t, filedoc, ufilter ):
    """
    Parse the baseline files and scripts for the test XML file.
    
      <baseline file="$NAME.exo"/>
      <baseline file="$NAME.exo" destination="$NAME.base_exo"/>
      <baseline file="$NAME.exo $NAME.his"
                destination="$NAME.base_exo $NAME.base_his"/>
      <baseline parameters="np=1" file="$NAME.exo"
                                  destination="$NAME.base_exo"/>
      
      <baseline>
        script language here
      </baseline>
    """
    
    t.resetBaseline()
    
    for nd in filedoc.matchNodes(['baseline$']):
      
      skip = 0
      for n,v in nd.getAttrs().items():
        isfa, istrue = filterAttr( n, v, t.getName(), t.getParameters(),
                                   ufilter, str(nd.line_no) )
        if isfa and not istrue:
          skip = 1
          break
      
      if not skip:
        
        fL = []
        
        fname = nd.getAttr('file',None)
        if fname != None:
          fname = string.split( fname )
          fdest = nd.getAttr('destination',None)
          if fdest == None:
            for f in fname:
              f = str(f)
              fL.append( [f,f] )
            
          else:
            fdest = string.split(fdest)
            if len(fname) != len(fdest):
              raise TestSpecError( 'the number of file names in the ' + \
               '"file" attribute must equal the number of names in ' + \
               'the "destination" attribute (' + str(len(fdest)) + ' != ' + \
               str(len(fname)) + '), line ' + str(nd.line_no) )
            
            for i in range(len(fname)):
              fL.append( [str(fname[i]), str(fdest[i])] )
        
        variableExpansion( t.getName(), ufilter.platformName(),
                           t.getParameters(), fL )
        
        for f,d in fL:
          t.addBaselineFile( str(f), str(d) )
        
        script = string.strip( nd.getContent() )
        if script:
          t.addBaselineFragment( script )


def cartesian_product_and_filter( paramD, ufilter ):
    """
    Takes a cartesian product of the parameters in 'paramD', applies parameter
    filtering, then collects the cartesian product as a list of param=value
    dictionaries (which is returned).  Note that the 'paramD' argument is
    modified in-place to remove parameters that are filtered out.
    """
    do_all = ufilter.getAttr('include_all',0)

    # first, make a list containing each parameter value list
    plist_keys = []
    plist_vals = []
    for pname,pL in paramD.items():
      plist_keys.append(pname)
      plist_vals.append( pL )
    
    instanceL = []
    paramD_filtered = {}
    
    # then loop over each set in the cartesian product
    dimvals = range(len(plist_vals))
    for vals in _cartesianProduct(plist_vals):
      # load the parameter values into a dictionary; note that any combined
      # values are used which may have multiple parameter values embedded
      pdict = {}
      for i in dimvals:
        kL = plist_keys[i]
        sL = vals[i]
        assert len(kL) == len(sL)
        n = len(kL)
        for j in range(n):
          pdict[ kL[j] ] = sL[j]
      
      if do_all or ufilter.evaluate_parameters( pdict ):
        
        instanceL.append( pdict )
        
        for i in dimvals:
          kL = plist_keys[i]
          sL = vals[i]
          if kL in paramD_filtered:
            if sL not in paramD_filtered[kL]:  # avoid duplicates
              paramD_filtered[kL].append( sL )
          else:
            paramD_filtered[kL] = [ sL ]

    # replace paramD parameters with a filtered set
    paramD.clear()
    paramD.update( paramD_filtered )

    return instanceL


def _cartesianProduct(lists, current=[], idx=0):
    """
    Call this function with a list of lists.  It returns a list of all
    combinations of each item in each list.  The additional arguments should
    not be used directly.
    """
    
    if idx < len(lists):
      
      plist = lists[idx]
      
      newp = []
      if len(current) == 0:
        for p in plist:
          newp.append([p])
      else:
        for c in current:
          for p in plist:
            newp.append( c + [p] )
      
      return _cartesianProduct(lists, newp, idx+1)
      
    else:
      return current


###########################################################################

alphanum_chars  = 'abcdefghijklmnopqrstuvwxyz' + \
                  'ABCDEFGHIJKLMNOPQRSTUVWXYZ' + \
                  '0123456789_'
allowable_chars = alphanum_chars + '.-=+#@^%:~'

allowable_chars_dict = {}
for c in allowable_chars:
  allowable_chars_dict[c] = None

def allowableString(s):
    for c in s:
      if not allowable_chars_dict.has_key(c):
        return 0
    return 1

alphanum_chars_dict = {}
for c in alphanum_chars:
  alphanum_chars_dict[c] = None

def allowableVariable(s):
    if s[:1] in ['0','1','2','3','4','5','6','7','8','9','_']:
      return 0
    for c in s:
      if not alphanum_chars_dict.has_key(c):
        return 0
    return 1

def extract_keywords( expr ):
    """
    """
    wx = FilterExpressions.WordExpression( expr )
    return wx.getWordList()
