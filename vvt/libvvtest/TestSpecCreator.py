#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import string, re
import types

import xmlwrapper
import TestSpec
import FilterExpressions

from ParameterSet import ParameterSet


class TestSpecError(Exception):
    def __init__(self, msg=None):
      if msg != None:
        self.msg = "Error: " + msg
      else:
        self.msg = "Error: (unknown)"
    def __str__(self): return self.msg


###########################################################################

def createTestObjects( rootpath, relpath, force_params, rtconfig ):
    """
    The 'rootpath' is the top directory of the file scan.  The 'relpath' is
    the name of the test file relative to 'rootpath' (it must not be an
    absolute path).  If 'force_params' is not None, then any parameters in
    the test that are in the 'force_params' dictionary have their values
    replaced for that parameter name.
    
    Returns a list of TestSpec objects, including a "parent" test if needed.


    Is the following note about parameter filtering still relevant?  Is it
    any different when filtering is performed above create/refresh?

        Important: this function always applies filtering, even if the
        "include_all" flag is present in 'rtconfig'.  This means any command
        line parameter expressions must be passed along in batch queue mode.

    """
    evaluator = ExpressionEvaluator( rtconfig.platformName(),
                                     rtconfig.getOptionList() )

    tests = create_unfiltered_testlist( rootpath, relpath,
                                        force_params, evaluator )

    tL = []
    for t in tests:

        if t.isAnalyze():
            # if analyze test, filter the parameter set to the parameters
            # that would be included
            paramset = t.getParameterSet()
            paramset.applyParamFilter( rtconfig.evaluate_parameters )

        if test_is_active( t, rtconfig, results_keywords=False ):
            tL.append( t )

    return tL


def refreshTest( testobj, rtconfig ):
    """
    Parses the test source file and resets the settings for the given test.
    The test name is not changed.  The parameters in the test XML file are
    not considered; instead, the parameters already defined in the test
    object are used.

    If the test XML contains bad syntax, a TestSpecError is raised.
    
    Returns false if any of the filtering would exclude this test.
    """
    evaluator = ExpressionEvaluator( rtconfig.platformName(),
                                     rtconfig.getOptionList() )

    reparse_test_object( testobj, evaluator )

    if testobj.isAnalyze():
        # if analyze test, filter the parameter set to the parameters
        # that would be included
        paramset = testobj.getParameterSet()
        paramset.applyParamFilter( rtconfig.evaluate_parameters )

    keep = True
    filt = not rtconfig.getAttr( 'include_all', False )
    if filt and not test_is_active( testobj, rtconfig, results_keywords=True ):
        keep = False

    return keep


def test_is_active( testobj, rtconfig, results_keywords ):
    """
    Uses the given filter to test whether the test is active (enabled).  The
    'results_keywords' boolean should be True when refreshing a test, but
    False when creating a test.  (Yeah, I would like to avoid that logic, but
    not sure how to do it yet.)
    """
    pev = PlatformEvaluator( testobj.getPlatformEnableExpressions() )
    if not rtconfig.evaluate_platform_include( pev.satisfies_platform ):
        return False

    for opexpr in testobj.getOptionEnableExpressions():
        if not rtconfig.evaluate_option_expr( opexpr ):
            return False

    if results_keywords:
        if not rtconfig.satisfies_keywords( testobj.getKeywords(True) ):
            return False
    else:
        if not rtconfig.satisfies_nonresults_keywords( testobj.getKeywords() ):
            return False

    if not rtconfig.getAttr( 'include_tdd', False ) and \
       'TDD' in testobj.getKeywords():
        return False

    if not rtconfig.evaluate_parameters( testobj.getParameters() ):
        return False

    if not rtconfig.file_search( testobj ):
        return False

    return True


class PlatformEvaluator:
    """
    Tests can use platform expressions to enable/disable the test.  This class
    caches the expressions and provides a function that answers the question

        "Would the test run on the given platform name?"
    """
    def __init__(self, list_of_word_expr):
        self.exprL = list_of_word_expr

    def satisfies_platform(self, plat_name):
        ""
        for wx in self.exprL:
            if not wx.evaluate( lambda tok: tok == plat_name ):
                return False
        return True


class ExpressionEvaluator:
    """
    Script test headers or attributes in test XML can specify a word
    expression that must be evaluated during test parsing.  This class caches
    the current platform name and command line option list, and provides
    functions to evaluate platform and option expressions.
    """

    def __init__(self, platname, option_list):
        self.platname = platname
        self.option_list = option_list

    def getPlatformName(self):
        ""
        return self.platname

    def evaluate_platform_expr(self, expr):
        """
        Evaluate the given expression against the current platform name.
        """
        wx = FilterExpressions.WordExpression(expr)
        return wx.evaluate( self._equals_platform )

    def _equals_platform(self, platname):
        ""
        if self.platname != None:
          return platname == self.platname
        return True

    def evaluate_option_expr(self, word_expr):
        """
        Evaluate the given expression against the list of command line options.
        """
        #wx = WordExpression(expr)
        #opL = self.attrs.get( 'option_list', [] )
        return word_expr.evaluate( self.option_list.count )


###########################################################################

def create_unfiltered_testlist( rootpath, relpath, force_params, evaluator ):
    """
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

    fname = os.path.join( rootpath, relpath )
    ext = os.path.splitext( relpath )[1]

    if ext == '.xml':

        docreader = xmlwrapper.XmlDocReader()
        try:
            filedoc = docreader.readDoc( fname )
        except xmlwrapper.XmlError:
            raise TestSpecError( str( sys.exc_info()[1] ) )
        
        nameL = testNameList( filedoc )
        if nameL == None:
            return []
        
        tL = []
        for tname in nameL:
            L = createTestName( tname, filedoc, rootpath, relpath,
                                force_params, evaluator )
            tL.extend( L )
    
    elif ext == '.vvt':
        
        vspecs = ScriptReader( fname )
        nameL = testNameList_scr( vspecs )
        tL = []
        for tname in nameL:
            L = createScriptTest( tname, vspecs, rootpath, relpath,
                                  force_params, evaluator )
            tL.extend( L )

    else:
        raise Exception( "invalid file extension: "+ext )

    return tL


def createTestName( tname, filedoc, rootpath, relpath, force_params,
                    evaluator ):
    """
    """
    paramset = parseTestParameters( filedoc, tname, evaluator, force_params )
    numparams = len( paramset.getParameters() )
    
    keywords = parseKeywords( filedoc, tname )
    
    # create the test instances
    
    testL = []

    if numparams == 0:
        t = TestSpec.TestSpec( tname, rootpath, relpath, "file" )
        t.setKeywords( keywords )
        testL.append(t)

    else:
        # take a cartesian product of all the parameter values
        for pdict in paramset.getInstances():
            # create the test and add to test list
            t = TestSpec.TestSpec( tname, rootpath, relpath, "file" )
            t.setParameters( pdict )
            t.setKeywords( keywords )
            testL.append(t)

    if len(testL) > 0:
        # check for parameterize/analyze

        t = testL[0]

        has_analyze = parseAnalyze( t, filedoc, evaluator )

        if has_analyze:
            if numparams == 0:
                raise TestSpecError( 'an analyze requires at least one ' + \
                                     'parameter to be defined' )

            # create an analyze test
            parent = t.makeParent()
            parent.setParameterSet( paramset )
            testL.append( parent )

    # parse and set the rest of the XML file for each test
    
    for t in testL:

        parse_include_platform ( t, filedoc )
        parseTimeouts          ( t, filedoc, evaluator )
        parseExecuteList       ( t, filedoc, evaluator )
        parseFiles             ( t, filedoc, evaluator )
        parseBaseline          ( t, filedoc, evaluator )
        set_test_form          ( t )
    
    return testL


def createScriptTest( tname, vspecs, rootpath, relpath,
                      force_params, evaluator ):
    """
    """
    paramset = parseTestParameters_scr( vspecs, tname, evaluator, force_params )
    numparams = len( paramset.getParameters() )
    
    keywords = parseKeywords_scr( vspecs, tname )
    
    testL = []

    if numparams == 0:
        t = TestSpec.TestSpec( tname, rootpath, relpath, "file" )
        t.setKeywords( keywords )
        testL.append(t)

    else:
        # take a cartesian product of all the parameter values
        for pdict in paramset.getInstances():
            # create the test and add to test list
            t = TestSpec.TestSpec( tname, rootpath, relpath, "file" )
            t.setParameters( pdict )
            t.setKeywords( keywords )
            testL.append(t)
    
    if len(testL) > 0:
        # check for parameterize/analyze

        t = testL[0]

        has_analyze = parseAnalyze_scr( t, vspecs, evaluator )

        if has_analyze:

            if numparams == 0:
                raise TestSpecError( 'an analyze requires at least one ' + \
                                     'parameter to be defined' )

            # create an analyze test
            parent = t.makeParent()
            parent.setParameterSet( paramset )
            testL.append( parent )

    for t in testL:

        parse_enable_platform ( t, vspecs )
        parseFiles_scr        ( t, vspecs, evaluator )
        parseTimeouts_scr     ( t, vspecs, evaluator )
        parseBaseline_scr     ( t, vspecs, evaluator )
        parseDependencies_scr ( t, vspecs, evaluator )

        set_test_form         ( t, vspecs )

    return testL


def set_test_form( tspec, vspecs=None ):
    """
    """
    if vspecs == None:
        tspec.setForm( 'lang', 'xml' )
        tspec.setForm( 'file', 'runscript' )
        cmdL = ['/bin/csh', '-f', './runscript']
        tspec.setForm( 'cmd', cmdL )
        if tspec.hasBaseline():
            tspec.setBaseline( 'cmd', cmdL+['--baseline'] )
    
    else:
        
        fname = vspecs.filename
        shebang = vspecs.shebang

        lang,cmdL = get_script_language( fname, True, shebang )

        if not cmdL:
            raise TestSpecError( "Could not determine the script " + \
                                 "test command line: "+fname )

        tspec.setForm( 'file', fname )

        if tspec.isAnalyze():
            # an analyze test may be a separate script
            zfile = tspec.getAnalyze( 'file', None )
            if zfile != None:
                # execute the analyze script rather than the test file
                lang = tspec.getAnalyze( 'lang' )
                cmdL = tspec.getAnalyze( 'cmd' )
                # add the analyze script to the link file list
                tspec.addLinkFile( zfile )
            else:
                # execute the test file but add the analyze command line option
                arg = tspec.getAnalyze( 'arg', None )
                if arg:
                    cmdL = cmdL + [ arg ]
        
        if lang: tspec.setForm( 'lang', lang )
        tspec.setForm( 'cmd', cmdL )

        if tspec.hasBaseline():
          arg = tspec.getBaseline( 'arg', None )
          if arg:
              basecmdL = tspec.getBaseline( 'cmd', None )
              if basecmdL == None:
                  # use the test script itself for the baseline script
                  basecmdL = cmdL
                  if lang: tspec.setBaseline( 'lang', lang )
              tspec.setBaseline( 'cmd', basecmdL+[arg] )

        bfile = tspec.getBaseline( 'file', None )
        if bfile:
            tspec.addLinkFile( bfile )


def reparse_test_object( testobj, evaluator ):
    """
    Given a TestSpec object, this function opens the original test file,
    parses, and overwrite the test contents.
    """
    fname = testobj.getFilename()
    ext = os.path.splitext( fname )[1]

    if ext == '.xml':

        docreader = xmlwrapper.XmlDocReader()
        filedoc = docreader.readDoc( fname )

        # run through the test name logic to check XML validity
        nameL = testNameList(filedoc)

        tname = testobj.getName()

        parse_include_platform( testobj, filedoc )

        keywords = parseKeywords( filedoc, tname )
        testobj.setKeywords( keywords )

        has_analyze = parseAnalyze( testobj, filedoc, evaluator )

        if has_analyze and len( testobj.getParameters() ) == 0:

            paramset = parseTestParameters( filedoc, tname, evaluator, None )

            if len( paramset.getParameters() ) == 0:
                raise TestSpecError( 'an analyze requires at least one ' + \
                               'parameter to be defined' )

            testobj.setParameterSet( paramset )

        parseFiles       ( testobj, filedoc, evaluator )
        parseTimeouts    ( testobj, filedoc, evaluator )
        parseExecuteList ( testobj, filedoc, evaluator )
        parseBaseline    ( testobj, filedoc, evaluator )

        set_test_form( testobj )

    elif ext == '.vvt':

        vspecs = ScriptReader( fname )

        # run through the test name logic to check validity
        nameL = testNameList_scr( vspecs )

        tname = testobj.getName()

        parse_enable_platform( testobj, vspecs )

        keywords = parseKeywords_scr( vspecs, tname )
        testobj.setKeywords( keywords )

        has_analyze = parseAnalyze_scr( testobj, vspecs, evaluator )

        if has_analyze and len( testobj.getParameters() ) == 0:

            paramset = parseTestParameters_scr( vspecs, tname, evaluator, None )

            if len( paramset.getParameters() ) == 0:
                raise TestSpecError( 'an analyze requires at least one ' + \
                               'parameter to be defined' )

            testobj.setParameterSet( paramset )

        parseFiles_scr    ( testobj, vspecs, evaluator )
        parseTimeouts_scr ( testobj, vspecs, evaluator )
        parseBaseline_scr ( testobj, vspecs, evaluator )
        parseDependencies_scr ( testobj, vspecs, evaluator )
        
        set_test_form( testobj, vspecs )

    else:
        raise Exception( "invalid file extension: "+ext )

    testobj.addOrigin( 'file' )  # mark test as refreshed


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
      elif type(v) == type(True):
        s = s + ' "' + n + '=B'
        if v: s += '1"'
        else: s += '0"'
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
    
    tspec = TestSpec.TestSpec( name, root, path, "string" )
    
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
      if nvL[0] == '_keywords_':
        tspec.setKeywords( string.split( nvL[1] ) )
      elif nvL[0] == '_parent_':
        pass  # backward compatibility; remove after a few months [Feb 2018]
      elif nvL[1][0] == 'I': tspec.setAttr( nvL[0], int(nvL[1][1:]) )
      elif nvL[1][0] == 'F': tspec.setAttr( nvL[0], float(nvL[1][1:]) )
      elif nvL[1][0] == 'N': tspec.setAttr( nvL[0], None )
      elif nvL[1][0] == 'B': tspec.setAttr( nvL[0], nvL[1][1:] == '1' )
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
        
        self.speclineL = []  # list of [line number, raw spec string]
        self.specL = []  # list of ScriptSpec objects
        self.shebang = None  # a string, if not None

        self.readfile( filename )

    def basename(self):
        """
        Returns the base name of the source file without the extension.
        """
        return os.path.splitext( os.path.basename( self.filename ) )[0]
    
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

    def readfile(self, filename):
        """
        """
        fp = open( filename )
        
        self.shebang = None
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
        if line:
            if line[0] == '#':
                m = ScriptReader.vvtpat.match( line )
                if m == None:
                    # comment line, which stops any continuation
                    if spec != None:
                        self.speclineL.append( spec )
                        spec = None
                else:
                    spec = self.parse_spec( line[m.end():], spec, lineno )
            else:
                # not empty and not a comment
                done = True
        
        elif spec != None:
            # an empty line stops any continuation
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


def get_script_language( filename, usebase, shebang ):
    """
    Given the full path to the script file and the #!/path/prog string from
    the script (without the #! and if it exists), this function determines the
    language that the script is written in and the command line that should be
    used to launch the script.

    Returns a pair lang,cmdL which is the language and command line (as a
    list).  The known languages are

        py, pl, sh, bash, csh, tcsh
    """
    lang = None
    cmdL = None

    bname = os.path.basename( filename )

    if shebang:
        
        import shlex
        L = shlex.split( shebang )
        xf = os.path.basename( L[0] )

        if xf.startswith( 'python' ):
            lang = 'py'
        elif xf.startswith( 'perl' ):
            lang = 'pl'
        elif xf in ['sh','bash','csh','tcsh']:
            lang = xf
        elif xf == 'env':
            # TODO: could use getopt here if options to the env program
            #       are given and need to be handled
            n = None
            for arg in L[1:]:
                # try to ignore VARNAME=value arguments
                if '=' not in arg:
                    n = arg
                    break
            if n:
                n = os.path.basename( n )
                if n.startswith( 'python' ):
                    lang = 'py'
                elif n.startswith( 'perl' ):
                    lang = 'pl'
                elif n in ['sh','bash','csh','tcsh']:
                    lang = n

        if os.access( filename, os.X_OK ):
            if usebase:
                cmdL = [ './'+bname ]
            else:
                cmdL = [ filename ]
        else:
            cmdL = L
            if usebase:
                cmdL.append( bname )
            else:
                cmdL.append( filename )

    if not lang:
        
        # look at the extension
        b1,x1 = os.path.splitext( bname )
        if b1 and x1 in ['.py']:
            lang = 'py'
        elif b1 and x1 in ['.pl']:
            lang = 'pl'
        elif b1 and x1 in ['.sh','.bash','.csh','.tcsh']:
            lang = x1[1:]
        
        if lang == None:
            # look for an embedded extension, such as name.py.vvt
            b2,x2 = os.path.splitext( b1 )
            if b2 and x2 in ['.py']:
                lang = 'py'
            elif b2 and x2 in ['.pl']:
                lang = 'pl'
            elif b2 and x2 in ['.sh','.bash','.csh','.tcsh']:
                lang = x2[1:]

    if not cmdL:
        
        if os.access( filename, os.X_OK ):
            if usebase:
                cmdL = [ './'+bname ]
            else:
                cmdL = [ filename ]
        
        elif lang:
            if usebase: fn = bname
            else:    fn = filename
            if lang == 'py':
                cmdL = [ sys.executable, fn ]
            elif lang == 'pl':
                cmdL = [ 'perl', fn ]
            elif lang in ['sh','bash','perl']:
                cmdL = [ lang, fn ]
            elif lang in ['csh','tcsh']:
                cmdL = [ lang, '-f', fn ]

    return lang,cmdL


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


def parseKeywords_scr( vspecs, tname ):
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

        if spec.attrs:
            # explicitly deny certain attributes for keyword definition
            for attrname in ['parameters','parameter',
                             'platform','platforms',
                             'option','options']:
                if attrname in spec.attrs:
                    raise TestSpecError( "the "+attrname + \
                        " attribute is not allowed here, " + \
                                 "line " + str(spec.lineno) )

        if not testname_ok_scr( spec.attrs, tname ):
            continue

        for key in spec.value.strip().split():
            if allowableString(key):
                keyD[key] = None
            else:
                raise TestSpecError( 'invalid keyword: "'+key+'", line ' + \
                                     str(spec.lineno) )

    # the parameter names are included in the test keywords
    for spec in vspecs.getSpecList( 'parameterize' ):
        if not testname_ok_scr( spec.attrs, tname ):
            continue
        L = spec.value.split( '=', 1 )
        if len(L) == 2 and L[0].strip():
            for k in [ n.strip() for n in L[0].strip().split(',') ]:
                keyD[k] = None

    L = keyD.keys()
    L.sort()
    return L


def parseTestParameters_scr( vspecs, tname, evaluator, force_params ):
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

    paramset = ParameterSet()

    for spec in vspecs.getSpecList( 'parameterize' ):
        
        lnum = spec.lineno

        if spec.attrs and \
           ( 'parameters' in spec.attrs or 'parameter' in spec.attrs ):
            raise TestSpecError( "parameters attribute not allowed here, " + \
                                 "line " + str(lnum) )
        
        if not filterAttr_scr( spec.attrs, tname, None, evaluator, lnum ):
            continue

        L = spec.value.split( '=', 1 )
        if len(L) < 2:
            raise TestSpecError( "invalid parameterize specification, " + \
                                 "line " + str(lnum) )
        if not L[0].strip():
            raise TestSpecError( "no parameter name given, " + \
                                 "line " + str(lnum) )

        nL = [ n.strip() for n in L[0].strip().split(',') ]

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

            paramset.addParameter( nL[0], vL )

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
                                          s+'", line ' + str(lnum) )
                for v in gL:
                    if not allowableString(v):
                        raise TestSpecError( 'invalid parameter value: "' + \
                                             v+'", line ' + str(lnum) )
                vL.append( gL )

            paramset.addParameterGroup( nL, vL )

    return paramset


def parseAnalyze_scr( t, vspecs, evaluator ):
    """
    Parse any analyze specifications.
    
        #VVT: analyze : analyze.py
        #VVT: analyze (file) : analyze.py
        #VVT: analyze : --analyze
        #VVT: analyze (argument) : --analyze
        #VVT: analyze (argument, testname=not mytest_fast) : --analyze

    If neither (file) nor (argument) is given as an attribute, then
        - if the value starts with a dash, then (argument) is assumed
        - otherwise, (file) is assumed

    Returns true if an analyze specification was found.
    """
    form = None
    specval = None
    for spec in vspecs.getSpecList( 'analyze' ):
        
        if spec.attrs and \
           ( 'parameters' in spec.attrs or 'parameter' in spec.attrs ):
            raise TestSpecError( "parameters attribute not allowed here, " + \
                                 "line " + str(spec.lineno) )
        
        if not filterAttr_scr( spec.attrs, t.getName(), None,
                               evaluator, spec.lineno ):
            continue

        sval = spec.value
        if not sval or not sval.strip():
            raise TestSpecError( 'missing or invalid analyze value, ' + \
                                 'line ' + str(spec.lineno) )
        
        specval = sval.strip()
        if spec.attrs and 'file' in spec.attrs:
            form = 'file'
        elif spec.attrs and 'argument' in spec.attrs:
            form = 'arg'
            if specval == '--execute_analysis_sections':
                raise TestSpecError( "cannot use reserved word for " + \
                    "analyze argument '"+specval+"', " + \
                    "line " + str(spec.lineno) )
        elif specval.startswith('-'):
            form = 'arg'
            if specval == '--execute_analysis_sections':
                raise TestSpecError( "cannot use reserved word for " + \
                    "analyze argument '"+specval+"', " + \
                    "line " + str(spec.lineno) )
        else:
            form = 'file'

    if form == 'file':
        fname = os.path.normpath( specval )
        lang,cmdL = configure_auxiliary_script( t, fname, vspecs.filename )

        if not cmdL:
            raise TestSpecError( "Could not determine the script " + \
                         "command line for analyze script: "+specval )
        
        t.setAnalyze( 'file', fname )
        t.setAnalyze( 'lang', lang )
        t.setAnalyze( 'cmd', cmdL )

        return True

    elif form == 'arg':
        t.setAnalyze( 'arg', specval )
        return True

    else:
        return False


def configure_auxiliary_script( testobj, scriptname, test_filename ):
    """
    """
    if os.path.isabs( scriptname ):
        # absolute path names are NOT soft linked into the test
        # execution directory
        usebase = False
    else:
        usebase = True
        # relative paths are relative to the test file directory
        d = os.path.dirname( test_filename )
        scriptname = os.path.normpath( os.path.join( d, scriptname ) )
    
    if os.path.exists( scriptname ):
        
        # to determine the execution command, look for shebang and
        # then leverage the logic used to invoke the test script itself
        fp = open( scriptname, 'r' )
        line = fp.readline()
        fp.close()
        shebang = None
        if line[:2] == '#!':
            shebang = line[2:]
        
        lang,cmdL = get_script_language( scriptname, usebase, shebang )
        
        return lang,cmdL
    
    else:
        raise TestSpecError( 'script file does not exist: ' + scriptname )


def parseFiles_scr( t, vspecs, evaluator ):
    """
        #VVT: copy : file1 file2
        #VVT: link : file3 file4
        #VVT: copy (rename) : srcname1,copyname1 srcname2,copyname2
        #VVT: link (rename) : srcname1,linkname1 srcname2,linkname2

        #VVT: sources : file1 file2 ${NAME}_*.py
    """
    cpfiles = []
    lnfiles = []
    tname = t.getName()
    params = t.getParameters()

    for spec in vspecs.getSpecList( 'copy' ):
        if filterAttr_scr( spec.attrs, tname, params, evaluator, spec.lineno ):
            collectFileNames_scr( spec, cpfiles, tname, params, evaluator )

    for spec in vspecs.getSpecList( 'link' ):
        if filterAttr_scr( spec.attrs, tname, params, evaluator, spec.lineno ):
            collectFileNames_scr( spec, lnfiles, tname, params, evaluator )
    
    for src,dst in lnfiles:
        t.addLinkFile( src, dst )
    for src,dst in cpfiles:
        t.addCopyFile( src, dst )

    fL = []
    for spec in vspecs.getSpecList( 'sources' ):
        if filterAttr_scr( spec.attrs, tname, params, evaluator, spec.lineno ):
            if spec.value:
                L = spec.value.split()
                variableExpansion( tname, evaluator.getPlatformName(), params, L )
                fL.extend( L )
    t.setSourceFiles( fL )


def collectFileNames_scr( spec, flist, tname, paramD, evaluator ):
    """
        #VVT: copy : file1 file2
        #VVT: copy (rename) : srcname1,copyname1 srcname2,copyname2
    """
    val = spec.value.strip()

    if spec.attrs and 'rename' in spec.attrs:
        cpat = re.compile( '[\t ]*,[\t ]*' )
        fL = []
        for s in cpat.sub( ',', val ).split():
            L = s.split(',')
            if len(L) != 2:
                raise TestSpecError( 'malformed (rename) file list: "' + \
                                      s+'", line ' + str(spec.lineno) )
            fsrc,fdst = L
            if os.path.isabs(fsrc) or os.path.isabs(fdst):
                raise TestSpecError( 'file names cannot be absolute ' + \
                                     'paths, line ' + str(spec.lineno) )
            fL.append( [fsrc,fdst] )
        
        variableExpansion( tname, evaluator.getPlatformName(), paramD, fL )

        flist.extend( fL )

    else:
        fL = val.split()
        
        for f in fL:
            if os.path.isabs(f):
                raise TestSpecError( 'file names cannot be absolute ' + \
                                     'paths, line ' + str(spec.lineno) )
        
        variableExpansion( tname, evaluator.getPlatformName(), paramD, fL )

        flist.extend( [ [f,None] for f in fL ] )


def parseTimeouts_scr( t, vspecs, evaluator ):
    """
      #VVT: timeout : 3600
      #VVT: timeout (testname=vvfull, platforms=Linux) : 3600
    """
    tname = t.getName()
    params = t.getParameters()
    for spec in vspecs.getSpecList( 'timeout' ):
        if filterAttr_scr( spec.attrs, tname, params, evaluator, spec.lineno ):
            sval = spec.value
            try:
                ival = int(sval)
                assert ival >= 0
            except:
                raise TestSpecError( 'timeout value must be a positive ' + \
                            'integer: "'+sval+'", line ' + str(spec.lineno) )
            t.setTimeout( ival )


def parseBaseline_scr( t, vspecs, evaluator ):
    """
      #VVT: baseline (attrs) : copyfrom,copyto copyfrom,copyto
      #VVT: baseline (file) : baseline.py
      #VVT: baseline (argument) : --baseline
    
    where default behavior is:
      - if no "file" and no "argument" attribute
        - if at least one comma, assume simple file copy
        - elif value starts with a dash, assume argument
        - else assume name of script
    """
    tname = t.getName()
    params = t.getParameters()
    
    cpat = re.compile( '[\t ]*,[\t ]*' )

    for spec in vspecs.getSpecList( 'baseline' ):
        
        if filterAttr_scr( spec.attrs, tname, params, evaluator, spec.lineno ):
            
            sval = spec.value.strip()

            if not sval or not sval.strip():
                raise TestSpecError( 'missing or invalid baseline value, ' + \
                                     'line ' + str(spec.lineno) )

            if spec.attrs and 'file' in spec.attrs:
                form = 'file'
            elif spec.attrs and 'argument' in spec.attrs:
                form = 'arg'
            elif ',' in sval:
                form = 'copy'
            elif sval.startswith( '-' ):
                form = 'arg'
            else:
                form = 'file'

            if form == 'copy':
                fL = []
                for s in cpat.sub( ',', sval ).split():
                    L = s.split(',')
                    if len(L) != 2:
                        raise TestSpecError( 'malformed baseline file ' + \
                                  'list: "'+s+'", line ' + str(spec.lineno) )
                    fsrc,fdst = L
                    if os.path.isabs(fsrc) or os.path.isabs(fdst):
                        raise TestSpecError( 'file names cannot be ' + \
                                  'absolute paths, line ' + str(spec.lineno) )
                    fL.append( [fsrc,fdst] )
                
                variableExpansion( tname, evaluator.getPlatformName(), params, fL )

                for fsrc,fdst in fL:
                    t.addBaselineFile( fsrc, fdst )

            elif form == 'file':
                # for baseline specifications that use a separate file, need to
                # determine the script language and command line for execution
                fname = os.path.normpath( sval )
                lang,cmdL = configure_auxiliary_script( t, fname, vspecs.filename )
                
                if not cmdL:
                    raise TestSpecError( "Could not determine the script " + \
                                 "command line for baseline script: "+sval )
                
                if lang:  t.setBaseline( 'lang', lang )
                t.setBaseline( 'cmd', cmdL )
                t.setBaseline( 'file', fname )
            
            else:
                assert form == 'arg'
                # set the arg here; the cmd and lang are set in set_test_form()
                t.setBaseline( 'arg', sval )


def parseDependencies_scr( t, vspecs, evaluator ):
    """
    Parse the test names that must run before this test can run.

        #VVT: depends on : test1 test2
        #VVT: depends on : test_pattern
        #VVT: depends on (result=pass) : testname
        #VVT: depends on (result="pass or diff") : testname
        #VVT: depends on (result="*") : testname
    """
    tname = t.getName()
    params = t.getParameters()

    for spec in vspecs.getSpecList( 'depends on' ):
        if filterAttr_scr( spec.attrs, tname, params, evaluator, spec.lineno ):

            wx = None
            if spec.attrs != None and 'result' in spec.attrs:
                result = spec.attrs['result'].strip()
                if result == '*':
                    wx = FilterExpressions.WordExpression()
                else:
                    wx = FilterExpressions.WordExpression( result )

            for val in spec.value.strip().split():
                t.addDependency( val, wx )


def testname_ok_scr( attrs, tname ):
    """
    """
    if attrs != None:
        tval = attrs.get( 'testname', None )
        if tval != None and not evauate_testname_expr( tname, tval ):
            return False
    return True


def evauate_testname_expr( testname, expr ):
    """
    """
    wx = FilterExpressions.WordExpression(expr)
    L = [ testname ]
    return wx.evaluate( L.count )


def filterAttr_scr( attrs, testname, paramD, evaluator, lineno ):
    """
    Checks for known attribute names in the given 'attrs' dictionary.
    Returns False only if at least one attribute evaluates to false.
    """
    if attrs:

        for name,value in attrs.items():

            try:

                if name == "testname":
                    if not evauate_testname_expr( testname, value ):
                        return False

                elif name in ["platform","platforms"]:
                    if not evaluator.evaluate_platform_expr( value ):
                        return False

                elif name in ["option","options"]:
                    wx = FilterExpressions.WordExpression( value )
                    if not evaluator.evaluate_option_expr( wx ):
                        return False

                elif name in ["parameter","parameters"]:
                    pf = FilterExpressions.ParamFilter(value)
                    if not pf.evaluate( paramD ):
                        return False

            except ValueError:
                raise TestSpecError( 'invalid '+name+' expression, ' + \
                                     'line ' + lineno + ": " + \
                                     str(sys.exc_info()[1]) )

    return True


###########################################################################

def testNameList( filedoc ):
    """
    Determine the test name and check for validity.  If this XML file is not
    an "rtest" then returns None.  Otherwise returns a list of test names.
    """
    if filedoc.getName() != "rtest":
        return None
    
    # determine the test name
    
    name = filedoc.getAttr('name', '').strip()
    if not name or not allowableString(name):
        raise TestSpecError( 'missing or invalid test name attribute, ' + \
                             'line ' + str(filedoc.getLineNumber()) )
    
    L = [ name ]
    for xnd in filedoc.matchNodes( ['rtest'] ):
        nm = xnd.getAttr('name', '').strip()
        if not nm or not allowableString(nm):
            raise TestSpecError( 'missing or invalid test name attribute, ' + \
                                 'line ' + str(xnd.getLineNumber()) )
        L.append( nm )

    return L


def filterAttr( attrname, attrvalue, testname, paramD, evaluator, lineno ):
    """
    Checks the attribute name for a filtering attributes.  Returns a pair of
    boolean values, (is filter, filter result).  The first is whether the
    attribute name is a filtering attribute, and if so, the second value is
    true/false depending on the result of applying the filter.
    """
    try:
      
      if attrname == "testname":
        return True, evauate_testname_expr( testname, attrvalue )
      
      elif attrname in ["platform","platforms"]:
        return True, evaluator.evaluate_platform_expr( attrvalue )
      
      elif attrname in ["keyword","keywords"]:
        # deprecated [became an error Sept 2017]
        raise TestSpecError( attrname + " attribute not allowed here, " + \
                             "line " + str(lineno) )
      
      elif attrname in ["not_keyword","not_keywords"]:
        # deprecated [became an error Sept 2017]
        raise TestSpecError( attrname + " attribute not allowed here, " + \
                             "line " + str(lineno) )
      
      elif attrname in ["option","options"]:
        wx = FilterExpressions.WordExpression( attrvalue )
        return True, evaluator.evaluate_option_expr( wx )
      
      elif attrname in ["parameter","parameters"]:
        pf = FilterExpressions.ParamFilter(attrvalue)
        return True, pf.evaluate( paramD )
    
    except ValueError, e:
      raise TestSpecError( "bad " + attrname + " expression, line " + \
                           lineno + ": " + str(e) )
    
    return False, False


def parseTestParameters( filedoc, tname, evaluator, force_params ):
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
    paramset = ParameterSet()

    if force_params == None:
        force_params = {}
    
    for nd in filedoc.matchNodes(['parameterize$']):
      
      attrs = nd.getAttrs()
      
      pL = []
      skip = 0
      for n,v in attrs.items():
        
        if n in ["parameters","parameter"]:
          raise TestSpecError( n + " attribute not allowed here, " + \
                               "line " + str(nd.getLineNumber()) )

        isfa, istrue = filterAttr( n, v, tname, None, evaluator,
                                   str(nd.getLineNumber()) )
        if isfa:
          if not istrue:
            skip = 1
            break
          continue
        
        if not allowableVariable(n):
          raise TestSpecError( 'bad parameter name: "' + n + '", line ' + \
                               str(nd.getLineNumber()) )
        
        vals = string.split(v)
        if len(vals) == 0:
          raise TestSpecError( "expected one or more values separated by " + \
                               "spaces, line " + str(nd.getLineNumber()) )
        
        for val in vals:
          if not allowableString(val):
            raise TestSpecError( 'bad parameter value: "' + val + '", line ' + \
                                 str(nd.getLineNumber()) )
        
        vals = force_params.get(n,vals)
        L = [ n ]
        L.extend( vals )
        
        for mL in pL:
          if len(L) != len(mL):
            raise TestSpecError( 'combined parameters must have the same ' + \
                                 'number of values, line ' + str(nd.getLineNumber()) )
        
        pL.append( L )

      if len(pL) > 0 and not skip:
            # TODO: the parameter names should really be sorted here in order
            #       to avoid duplicates if another parameterize comes along
            #       with a different order of the same names
            # the name(s) and each of the values are tuples
            if len(pL) == 1:
                L = pL[0]
                paramset.addParameter( L[0], L[1:] )
            else:
                L = [ list(T) for T in zip( *pL ) ]
                paramset.addParameterGroup( L[0], L[1:] )

    return paramset


def testname_ok( xmlnode, tname ):
    """
    """
    tval = xmlnode.getAttr( 'testname', None )
    if tval != None and not evauate_testname_expr( tname, tval ):
        return False
    return True


def parseKeywords( filedoc, tname ):
    """
    Parse the test keywords for the test XML file.
    
      <keywords> key1 key2 </keywords>
      <keywords testname="mytest"> key3 </keywords>
    
    Also includes the name="..." on <execute> blocks and the parameter names
    in <parameterize> blocks.
    """
    keyD = {}
    
    keyD[tname] = None
    
    for nd in filedoc.matchNodes(['keywords$']):
      if not testname_ok( nd, tname ):
        # skip this keyword set (filtered out based on test name)
        continue
      for key in string.split( nd.getContent() ):
        if allowableString(key):
          keyD[key] = None
        else:
          raise TestSpecError( 'invalid keyword: "' + key + '", line ' + \
                               str(nd.getLineNumber()) )
    
    for nd in filedoc.getSubNodes():
      if not testname_ok( nd, tname ):
        continue
      if nd.getName() == 'parameterize':
        # the parameter names are included in the test keywords
        for n,v in nd.getAttrs().items():
          if n in ['parameter','parameters','testname'
                   'platform','platforms','option','options']:
            pass
          elif allowableVariable(n):
            keyD[ str(n) ] = None
      elif nd.getName() == 'execute':
        # the execute name is included in the test keywords
        n = nd.getAttr('name', None)
        if n != None:
          keyD[ str(n) ] = None

    L = keyD.keys()
    L.sort()
    return L


def parse_include_platform( testobj, xmldoc ):
    """
    Parse syntax that will filter out this test by platform or build option.
    
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
    tname = testobj.getName()

    for nd in xmldoc.matchNodes(['include$']):
          
        if nd.hasAttr( 'parameters' ) or nd.hasAttr( 'parameter' ):
            raise TestSpecError( 'the "parameters" attribute not allowed '
                                 'here, line ' + str(nd.getLineNumber()) )

        if not testname_ok( nd, tname ):
            # the <include> does not apply to this test name
            continue

        platexpr = nd.getAttr( 'platforms', nd.getAttr( 'platform', None ) )
        if platexpr != None:
            platexpr = platexpr.strip()

            if '/' in platexpr:
                raise TestSpecError( 'invalid "platforms" attribute content '
                                     ', line ' + str(nd.getLineNumber()) )

            wx = FilterExpressions.WordExpression( platexpr )
            testobj.addEnablePlatformExpression( wx )

        opexpr = nd.getAttr( 'options', nd.getAttr( 'option', None ) )
        if opexpr != None:
            opexpr = opexpr.strip()
            if opexpr:
                wx = FilterExpressions.WordExpression( opexpr )
                testobj.addEnableOptionExpression( wx )


def parse_enable_platform( testobj, vspecs ):
    """
    Parse syntax that will filter out this test by platform or build option.
    
    Platform expressions and build options use word expressions.
    
        #VVT: enable (platforms="not SunOS and not Linux")
        #VVT: enable (options="not dbg and ( tridev or tri8 )")
        #VVT: enable (platforms="...", options="...")
    
    If both platform and option expressions are given, their results are
    ANDed together.  If more than one "enable" block is given, each must
    result in True for the test to be included.
    """
    tname = testobj.getName()

    for spec in vspecs.getSpecList( 'enable' ):

        if spec.attrs:

            if not testname_ok_scr( spec.attrs, tname ):
                # the "enable" does not apply to this test name
                continue

            if 'parameters' in spec.attrs or 'parameter' in spec.attrs:
                raise TestSpecError( "parameters attribute not " + \
                                     "allowed here, line " + str(spec.lineno) )

            platexpr = spec.attrs.get( 'platforms',
                                       spec.attrs.get( 'platform', None ) )
            if platexpr != None:
                platexpr = platexpr.strip()
                if '/' in platexpr:
                    raise TestSpecError( \
                            'invalid "platforms" attribute value '
                            ', line ' + str(spec.lineno) )
                wx = FilterExpressions.WordExpression( platexpr )
                testobj.addEnablePlatformExpression( wx )

            opexpr = spec.attrs.get( 'options',
                                     spec.attrs.get( 'option', None ) )
            if opexpr != None:
                opexpr = opexpr.strip()

                # an empty option expression is ignored
                if opexpr:
                    wx = FilterExpressions.WordExpression( opexpr )
                    testobj.addEnableOptionExpression( wx )


def parseAnalyze( t, filedoc, evaluator ):
    """
    Parse analyze scripts that get run after all parameterized tests complete.
    
       <analyze keywords="..." parameters="..." platform="...">
         script contents that post processes test results
       </analyze>

    Returns true if the test specifies an analyze script.
    """
    a = None
    
    ndL = filedoc.matchNodes(['analyze$'])
    
    for nd in ndL:
      
      skip = 0
      for n,v in nd.getAttrs().items():
        
        if n in ["parameter","parameters"]:
          raise TestSpecError( 'an <analyze> block cannot have a ' + \
                               '"parameters=..." attribute: ' + \
                               ', line ' + str(nd.getLineNumber()) )
        
        isfa, istrue = filterAttr( n, v, t.getName(), None,
                                   evaluator, str(nd.getLineNumber()) )
        if isfa and not istrue:
          skip = 1
          break
      
      if not skip:
        try:
          content = str( nd.getContent() )
        except:
          raise TestSpecError( 'the content in an <analyze> block must be ' + \
                               'ASCII characters, line ' + str(nd.getLineNumber()) )
        if a == None:
          a = content.strip()
        else:
          a += os.linesep + content.strip()
    
    t.setAnalyze( 'scriptfrag', a )

    return a != None


def parseTimeouts( t, filedoc, evaluator ):
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
                                   evaluator, str(nd.getLineNumber()) )
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
                                 val + '", line ' + str(nd.getLineNumber()) )
          if to < 0:
            raise TestSpecError( 'timeout value must be non-negative: "' + \
                                 val + '", line ' + str(nd.getLineNumber()) )
        
        if to != None:
          t.setTimeout( to )


def parseExecuteList( t, filedoc, evaluator ):
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
                                   evaluator, str(nd.getLineNumber()) )
        if isfa and not istrue:
          skip = 1
          break
      
      if nd.hasAttr('ifdef'):
        L = string.split( nd.getAttr('ifdef') )
        for n in L:
          if not allowableVariable(n):
            raise TestSpecError( 'invalid environment variable name: "' + \
                                 n + '"' + ', line ' + str(nd.getLineNumber()) )
        for n in L:
          if not os.environ.has_key(n):
            skip = 1
            break
      
      if not skip:
        
        xname = nd.getAttr('name', None)
        
        analyze = False
        if xname == None:
          if string.lower( string.strip( nd.getAttr('analyze','') ) ) == 'yes':
            analyze = True
        else:
          if not xname or not allowableString(xname):
            raise TestSpecError( 'invalid name value: "' + xname + \
                                 '", line ' + str(nd.getLineNumber()) )

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


def collectFileNames( nd, flist, tname, paramD, evaluator ):
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
                                   evaluator, str(nd.getLineNumber()) )
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
               '), line ' + str(nd.getLineNumber()) )
          for i in range(len(fileL)):
            if os.path.isabs(fileL[i]) or os.path.isabs(tnames[i]):
              raise TestSpecError( 'file names cannot be absolute paths, ' + \
                                   'line ' + str(nd.getLineNumber()) )
            fL.append( [str(fileL[i]), str(tnames[i])] )
        
        else:
          for f in fileL:
            if os.path.isabs(f):
              raise TestSpecError( 'file names cannot be absolute paths, ' + \
                                   'line ' + str(nd.getLineNumber()) )
            fL.append( [str(f), None] )
        
        variableExpansion( tname, evaluator.getPlatformName(), paramD, fL )
        
        flist.extend(fL)
    
    else:
      raise TestSpecError( 'expected a list of file names as content' + \
                           ', line ' + str(nd.getLineNumber()) )


def globFileNames( nd, flist, t, evaluator, nofilter=0 ):
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
                                   evaluator, str(nd.getLineNumber()) )
        if nofilter and isfa:
          raise TestSpecError( 'filter attributes not allowed here' + \
                               ', line ' + str(nd.getLineNumber()) )
        if isfa and not istrue:
          skip = 1
          break
      
      if not skip:
        
        # first, substitute variables into the file names
        variableExpansion( tname, evaluator.getPlatformName(), paramD, globL )
        
        for fn in globL:
          flist.append( [str(fn),None] )
    
    else:
      raise TestSpecError( 'expected a list of file names as content' + \
                           ', line ' + str(nd.getLineNumber()) )


def parseFiles( t, filedoc, evaluator ):
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
      collectFileNames( nd, cpfiles, t.getName(), t.getParameters(), evaluator )
    
    for nd in filedoc.matchNodes(["link_files$"]):
      collectFileNames( nd, lnfiles, t.getName(), t.getParameters(), evaluator )
    
    # include mirror_files for backward compatibility
    for nd in filedoc.matchNodes(["mirror_files$"]):
      collectFileNames( nd, lnfiles, t.getName(), t.getParameters(), evaluator )
    
    for nd in filedoc.matchNodes(["glob_link$"]):
      # This construct is deprecated [April 2016].
      globFileNames( nd, lnfiles, t, evaluator )
    
    for nd in filedoc.matchNodes(["glob_copy$"]):
      # This construct is deprecated [April 2016].
      globFileNames( nd, cpfiles, t, evaluator )
    
    for src,dst in lnfiles:
      t.addLinkFile( src, dst )
    for src,dst in cpfiles:
      t.addCopyFile( src, dst )
    
    fL = []
    for nd in filedoc.matchNodes(["source_files$"]):
      globFileNames( nd, fL, t, evaluator, 1 )
    t.setSourceFiles( map( lambda T: T[0], fL ) )


def parseBaseline( t, filedoc, evaluator ):
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
    for nd in filedoc.matchNodes(['baseline$']):
      
      skip = 0
      for n,v in nd.getAttrs().items():
        isfa, istrue = filterAttr( n, v, t.getName(), t.getParameters(),
                                   evaluator, str(nd.getLineNumber()) )
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
               str(len(fname)) + '), line ' + str(nd.getLineNumber()) )
            
            for i in range(len(fname)):
              fL.append( [str(fname[i]), str(fdest[i])] )
        
        variableExpansion( t.getName(), evaluator.getPlatformName(),
                           t.getParameters(), fL )
        
        for f,d in fL:
          t.addBaselineFile( str(f), str(d) )
        
        script = string.strip( nd.getContent() )
        if script:
          t.addBaselineFragment( script )


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
