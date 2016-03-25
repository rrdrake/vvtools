#!/usr/bin/env python

import os
import string, re
import types
import fnmatch

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

def createTestObjects( filedoc, rootpath, filepath, \
                       force_params=None, ufilter=None ):
    """
    The 'filedoc' argument must be an XmlNode object which contains the test
    file.  The 'filepath' is relative to 'rootpath' and must not be an absolute
    filename.  If 'force_params' is not None, then any parameters in the test
    that are in the 'force_params' dictionary have their values replaced for
    that parameter name.  The 'ufilter' argument must be None or an
    ExpressionSet instance.
    
    Returns a list of TestSpec objects, including a "parent" test if needed.
    """
    assert not os.path.isabs(filepath)
    
    name = testName(filedoc)
    if name == None:
      return []
    
    if ufilter == None:
      ufilter = FilterExpressions.ExpressionSet()
    
    keywords = parseKeywords( filedoc )
    
    if not parseIncludeTest( filedoc, ufilter ):
      return []
    
    if not ufilter.getAttr('include_all',0):
      if not ufilter.satisfies_nonresults_keywords( keywords ):
        return []
    
    # parse the parameters then create the test instances
    
    combined = parseTestParameters( filedoc, ufilter, force_params )
    
    testL = []
    
    if len(combined) == 0:
      
      t = TestSpec.TestSpec( name, rootpath, filepath )
      testL.append(t)
    
    else:
      
      # take a cartesian product of all the parameter values
      
      # first, make a list containing each parameter value list
      plist_keys = []
      plist = []
      for pname,pL in combined.items():
        plist_keys.append(pname)
        plist.append( pL )
      
      # then loop over each set in the cartesian product
      dimset = range(len(plist))
      for set in _cartesianProduct(plist):
        # load the parameter values into a dictionary; note that the combined
        # values are used which may have multiple parameter values embedded
        pdict = {}
        for i in dimset:
          kL = string.split( plist_keys[i], ',' )
          sL = string.split( set[i], ',' )
          assert len(kL) == len(sL)
          n = len(kL)
          for j in range(n):
            pdict[ kL.pop(0) ] = sL.pop(0)
        # create the test and add to test list
        t = TestSpec.TestSpec( name, rootpath, filepath )
        t.setParameters( pdict )
        testL.append(t)
    
    # parse and set the rest of the XML file for each test
    
    finalL = []
    parent = None
    for t in testL:
      
      if not ufilter.getAttr('include_all',0):
        if not ufilter.evaluate_parameters(t.getParameters()):
          continue
      
      t.setKeywords( keywords )
      
      parseAnalyze      ( t, filedoc, ufilter )
      parseTimeouts     ( t, filedoc, ufilter )
      parseExecuteList  ( t, filedoc, ufilter )
      parseFiles        ( t, filedoc, ufilter )
      parseBaseline     ( t, filedoc, ufilter )
      
      if ufilter.getAttr('include_all',0) or ufilter.file_search(t):
        
        finalL.append(t)
        
        if parent == None and t.getAnalyzeScript() != None:
          parent = t.makeParent( combined )
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


def refreshTest( testobj, filedoc, params, ufilter=None ):
    """
    Parses the 'filedoc' XmlNode and resets the settings for the given test.
    The test name is not changed.  The parameters in the test XML file are
    not considered; instead, the given parameters will be used.  If the
    test XML contains bad syntax, a TestSpecError is raised.
    
    Returns false if any of the filtering would exclude this test.
    """
    name = testName(filedoc)
    
    testobj.setParameters( params )
    
    if not testobj.getParent():
      combined = parseTestParameters( filedoc, ufilter, None )
      testobj.setParameterSet( combined )
    
    if ufilter == None:
      ufilter = FilterExpressions.ExpressionSet()
    
    keep = 1
    
    if not parseIncludeTest( filedoc, ufilter ):
      keep = 0
    
    keywords = parseKeywords( filedoc )
    testobj.setKeywords( keywords )
    
    if not ufilter.satisfies_keywords( testobj.getKeywords(1) ):
      keep = 0
    
    if not ufilter.evaluate_parameters( testobj.getParameters() ):
      keep = 0
    
    parseFiles       ( testobj, filedoc, ufilter )
    parseAnalyze     ( testobj, filedoc, ufilter )
    parseTimeouts    ( testobj, filedoc, ufilter )
    parseExecuteList ( testobj, filedoc, ufilter )
    parseBaseline    ( testobj, filedoc, ufilter )
    
    if ufilter.getAttr('include_all',0):
      return 1
    
    if not ufilter.file_search(testobj):
      keep = 0
    
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
      tspec.setParameters(params)
    
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

def testName( filedoc ):
    """
    Determine the test name and check for validity.  If this XML file is not
    an "rtest" then returns None.
    """
    if filedoc.name != "rtest":
      return None
    
    # determine the test name
    
    name = string.strip( filedoc.getAttr('name', '') )
    if not name or not allowableString(name):
      raise TestSpecError( 'missing or invalid test name attribute, line ' + \
                           str(filedoc.line_no) )
    
    return name


def filterAttr( attrname, attrvalue, paramD, ufilter, lineno ):
    """
    Checks the attribute name for a filtering attributes.  Returns a pair of
    boolean values, (is filter, filter result).  The first is whether the
    attribute name is a filtering attribute, and if so, the second value is
    true/false depending on the result of applying the filter.
    """
    try:
      
      if attrname in ["platform","platforms"]:
        return 1, ufilter.evaluate_platform_expr( attrvalue )
      
      elif attrname in ["keyword","keywords"]:
        L = attrvalue.split()
        if 'and' in L or 'or' in L or 'not' in L or \
           '(' in attrvalue or ')' in attrvalue:
          # allow keyword expressions for backward compatibility
          return 1, ufilter.evaluate_keyword_expr( attrvalue )
        return 1, ufilter.satisfies_nonresults_keywords( L, 1 )
      
      elif attrname in ["not_keyword","not_keywords"]:
        v = not ufilter.satisfies_nonresults_keywords( attrvalue.split(), 1 )
        return 1, v
      
      elif attrname in ["option","options"]:
        return 1, ufilter.evaluate_option_expr( attrvalue )
      
      elif attrname in ["parameter","parameters"]:
        pf = FilterExpressions.ParamFilter(attrvalue)
        return 1, pf.evaluate( paramD )
    
    except ValueError, e:
      raise TestSpecError( "bad " + attrname + " expression, line " + \
                           lineno + ": " + str(e) )
    
    return 0, 0  # false, false


def parseTestParameters( filedoc, ufilter, force_params ):
    """
    Parses the parameter settings for a test XML file.
    
      <parameterize paramname="value1 value2"/>
      <parameterize paramA="A1 A2"
                    paramB="B1 B2"/>
      <parameterize platforms="Linux or SunOS"
                    keywords="fast or medium"
                    options="not dbg"
                    paramname="value1 value2"/>
    
    where paramname can be any string.  The second form creates combined
    parameters where the values are "zipped" together.  That is, paramA=A1
    and paramB=B1 then paramA=A2 and paramB=B2.  A separate test will NOT
    be created for the combination paramA=A1, paramB=B2, for example.
    
    Returns a dictionary mapping combined parameter names to lists of the
    combined string values.  The separater in the combined case is a comma.
    """
    
    combined = {}
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
        
        isfa, istrue = filterAttr( n, v, None, ufilter, str(nd.line_no) )
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
        if len(pL) == 1:
          combined[ pL[0][0] ] = pL[0][1:]
        else:
          # combine the parameter values
          oneL = []
          for L in pL:
            if len(oneL) == 0:
              oneL.extend( L )
            else:
              newL = []
              for i in range(len(L)):
                newL.append( oneL.pop(0) + ',' + L.pop(0) )
              oneL = newL
          combined[ oneL[0] ] = oneL[1:]
    
    return combined


def parseKeywords( filedoc ):
    """
    Parse the test keywords for the test XML file.
    
      <keywords> key1 key2 </keywords>
    
    Also includes the name="..." on <execute> blocks, the parameter names in
    <parameterize> blocks, and the words in keywords="..." attributes.
    """
    
    keyD = {}
    
    name = string.strip( filedoc.getAttr('name', '') )
    if name and allowableString(name):
      keyD[name] = None
    
    for nd in filedoc.matchNodes(['keywords$']):
      for key in string.split( nd.getContent() ):
        if allowableString(key):
          keyD[key] = None
        else:
          raise TestSpecError( 'bad keyword: "' + key + '", line ' + \
                               str(nd.line_no) )
    
    for nd in filedoc.getSubNodes():
      if nd.name == 'parameterize':
        # the parameter names are included in the test keywords
        for n,v in nd.getAttrs().items():
          if n in ['parameter','parameters','keyword','keywords',
                   'platform','platforms','option','options']:
            pass
          elif allowableVariable(n):
            keyD[ str(n) ] = None
      elif nd.name == 'execute':
        # the execute name is included in the test keywords
        n = nd.getAttr('name', None)
        if n != None:
          keyD[ str(n) ] = None
      if nd.name in ['parameterize','analyze','execute','timeout',
                     'copy_files','link_files','glob_copy','glob_link',
                     'baseline']:
        # look for keywords attribute and include those as test keywords
        kwstr = nd.getAttr( 'keywords', nd.getAttr( 'keyword', None ) )
        if kwstr != None:
          L = kwstr.split()
          if 'and' in L or 'or' in L or 'not' in L or \
             '(' in kwstr or ')' in kwstr:
            # deprecated now, but keyword expressions used to be allowed here
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


def parseIncludeTest( filedoc, ufilter ):
    """
    Parse syntax that will filter out this test by platform or build option.
    Returns false if the test is to be excluded.
    
    Platform expressions and build options use word expressions.
    
       <include platforms="not SunOS and not Linux"/>
       <include options="2D and ( tridev or tri8 )"/>
       <include platforms="..." options="..."/>
    
    If both platform and option expressions are given, their results are
    ANDed together.  If more than one <include> block is given, each must
    result in True for the test to be included.
    
    For backward compatibility, allow the following.
    
      <build_options> 2D+tridev|tri8 </build_options>
      <options> 2D+tridev|tri8 </options>
      
      <platform include="SunOS Linux"/>
      <platform include=""/>
      <platform exclude="IRIX64"/>
    
      <include platforms="SunOS Linux"/>
      <exclude platforms="IRIX"/>
    
    Note that on November 24, 2014, a scan of Benchmarks showed that the only
    backward compatibility still being used was <include platforms="..."/>
    had platforms listed (they had "Linux NWCC", for example).  These last
    benchmarks were changed to be a valid expression and committed on this
    date as well.
    """
    if ufilter.getAttr('include_all',0):
      return 1
    
    pev = PlatformEvaluator( filedoc )
    if not ufilter.evaluate_platform_include( pev.satisfies_platform ):
      return 0
    
    for nd in filedoc.getSubNodes():
      
      if nd.name == "build_options":
        # syntax for backward compatibility
        s = string.join( string.split( nd.getContent() ) )
        if s:
          expr = ''
          for op in s.split( '+' ):
            orL = string.join( string.split( op, '|' ), ' or ' )
            if expr: expr = ' ( ' + expr + ' ) and ( ' + orL + ' )'
            else:    expr = orL
          if not ufilter.evaluate_option_expr(expr):
            return 0
      
      elif nd.name == "include":
        if nd.hasAttr('options') or nd.hasAttr('option'):
          if nd.hasAttr('options'): s = nd.getAttr('options')
          else:                     s = nd.getAttr('option')
          s = string.strip(s)
          if s and not ufilter.evaluate_option_expr(s):
            return 0
    
    return 1


class PlatformEvaluator:
    """
    This class is a helper to provide UserFilter an evaluator function.
    """
    
    def __init__(self, xmldoc):
        self.xmldoc = xmldoc
    
    def satisfies_platform(self, plat_name):
        """
        This function parses the test XML file for platform restrictions and
        returns true if the test would run under the given 'plat_name'.
        Otherwise, returns it false.
        """
        for nd in self.xmldoc.getSubNodes():
          
          if nd.name == "platform":
            # syntax for backward compatibility
            if nd.hasAttr('parameters') or nd.hasAttr('parameter'):
              raise TestSpecError( 'the "parameters" attribute is not allowed '
                         'in a <platform> block, line ' + str(nd.line_no) )
            wx = FilterExpressions.WordExpression()
            s = string.strip( nd.getAttr('exclude','') )
            if s:
              L = []
              for w in string.split(s):
                L.append( ' not ' + w )
              wx.append( string.join( L, ' and ' ), 'and' )
            if nd.hasAttr('include'):
              s = string.strip( nd.getAttr('include') )
              wx.append( string.join( string.split(s), ' or ' ), 'and' )
            if not wx.evaluate( lambda tok: tok == plat_name ):
              return 0
          
          elif nd.name == "exclude":
            # syntax for backward compatibility
            s = string.strip( nd.getAttr('platforms','') )
            if s:
              L = []
              for w in string.split(s):
                L.append( ' not ' + w )
              wx = FilterExpressions.WordExpression( string.join(L,' and ') )
              if not wx.evaluate( lambda tok: tok == plat_name ):
                return 0
          
          elif nd.name == "include":
            if nd.hasAttr('platforms'):
              # have to check for backward compatible syntax
              s = string.strip( nd.getAttr('platforms') )
              if '/' in s:
                raise TestSpecError( 'invalid "platforms" attribute content '
                                     ', line ' + str(nd.line_no) )
              pL = string.split(s)
              if '(' in s or ')' in s or \
                 'or' in pL or 'and' in pL or 'not' in pL:
                # an expression syntax is being used
                wx = FilterExpressions.WordExpression(s)
              else:
                # assume list of platform names to include
                wx = FilterExpressions.WordExpression( \
                                   string.join( string.split(s), ' or ' ) )
              if not wx.evaluate( lambda tok: tok == plat_name ):
                return 0
            
            elif nd.hasAttr('platform'):
              # without plural spelling, must be current syntax
              s = nd.getAttr('platform').strip()
              if '/' in s:
                raise TestSpecError( 'invalid "platform" attribute content '
                                     ', line ' + str(nd.line_no) )
              wx = FilterExpressions.WordExpression(s)
              if not wx.evaluate( lambda tok: tok == plat_name ):
                return 0
        
        return 1


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
        
        isfa, istrue = filterAttr( n, v, t.getParameters(),
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
      <timeout include="SunOS" value="240"/>
      <timeout parameters="hsize=0.01" value="320"/>
    
    "Multiplier" is deprecated.
    
      <timeout exclude="Linux" multiplier="2"/>
      <timeout parameters="hsize=0.01" multiplier="2"/>
    """
    specL = []
    
    for nd in filedoc.matchNodes(['timeout$']):
      
      skip = 0
      for n,v in nd.getAttrs().items():
        isfa, istrue = filterAttr( n, v, t.getParameters(),
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
      <execute include="SunOS" name="aname"> arguments </execute>
      <execute exclude="SunOS"> script language </execute>
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
        isfa, istrue = filterAttr( n, v, t.getParameters(),
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
    Helper function that parses file names in content with optional test_name
    attribute:
    
        <something platforms="SunOS"> file1.C file2.C </something>
    
    or
    
        <something test_name="file1_copy.dat file2_copy.dat">
          file1.C file2.C
        </something>
    
    Returns a list of (source filename, test filename).
    """
    
    fileL = string.split( nd.getContent() )
    if len(fileL) > 0:
      
      skip = 0
      for n,v in nd.getAttrs().items():
        isfa, istrue = filterAttr( n, v, paramD, ufilter, str(nd.line_no) )
        if isfa and not istrue:
          skip = 1
          break
      
      if not skip:
        
        fL = []
        tnames = nd.getAttr('test_name',None)
        if tnames != None:
          
          tnames = string.split(tnames)
          if len(tnames) != len(fileL):
            raise TestSpecError( 'the number of file names in the ' + \
               '"test_name" attribute must equal the number of names in ' + \
               'the content (' + str(len(tnames)) + ' != ' + str(len(fileL)) + \
               '), line ' + str(nd.line_no) )
          for i in range(len(fileL)):
            if os.path.isabs(fileL[i]) or os.path.isabs(tnames[i]):
              raise TestSpecError( 'file names cannot be absolute paths, ' + \
                                   'line ' + str(nd.line_no) )
            fL.append( [fileL[i], tnames[i]] )
        
        else:
          for f in fileL:
            if os.path.isabs(f):
              raise TestSpecError( 'file names cannot be absolute paths, ' + \
                                   'line ' + str(nd.line_no) )
            fL.append( [f, None] )
        
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
    
    globL = string.split( nd.getContent() )
    if len(globL) > 0:
      
      skip = 0
      for n,v in nd.getAttrs().items():
        isfa, istrue = filterAttr( n, v, paramD, ufilter, str(nd.line_no) )
        if nofilter and isfa:
          raise TestSpecError( 'filter attributes not allowed here' + \
                               ', line ' + str(nd.line_no) )
        if isfa and not istrue:
          skip = 1
          break
      
      if not skip:
        
        # first, substitute variables into the file names
        variableExpansion( tname, ufilter.platformName(), paramD, globL )
        
        # TODO: implement a file list cache mechanism
        for fp in os.listdir(homedir):
          for fg in globL:
            if fnmatch.fnmatch( fp, fg ):
              flist.append( [fp,None] )
              break
    
    else:
      raise TestSpecError( 'expected a list of file names as content' + \
                           ', line ' + str(nd.line_no) )


def parseFiles( t, filedoc, ufilter ):
    """
    Parse the files to copy and soft link for the test XML file.
    
      <copy_files> file1.C file2.F </copy_files>
      <copy_files test_name="f1.C f2.F"> file1.C file2.F </copy_files>
      <copy_files include="SunOS"> file1.C file2.F </copy_files>
      <copy_files exclude="SunOS"> file1.C file2.F </copy_files>
      <copy_files parameters="np=4" test_name="in4.exo"> in.exo </copy_files>
      
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
      globFileNames( nd, lnfiles, t, ufilter )
    
    for nd in filedoc.matchNodes(["glob_copy$"]):
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
        isfa, istrue = filterAttr( n, v, t.getParameters(),
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
              fL.append( [f,f] )
            
          else:
            fdest = string.split(fdest)
            if len(fname) != len(fdest):
              raise TestSpecError( 'the number of file names in the ' + \
               '"file" attribute must equal the number of names in ' + \
               'the "destination" attribute (' + str(len(fdest)) + ' != ' + \
               str(len(fname)) + '), line ' + str(nd.line_no) )
            
            for i in range(len(fname)):
              fL.append( [fname[i], fdest[i]] )
        
        variableExpansion( t.getName(), ufilter.platformName(),
                           t.getParameters(), fL )
        
        for f,d in fL:
          t.addBaselineFile( f, d )
        
        script = string.strip( nd.getContent() )
        if script:
          t.addBaselineFragment( script )


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
