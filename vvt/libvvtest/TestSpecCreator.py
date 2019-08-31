#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import re
import string

from . import xmlwrapper
from . import TestSpec
from . import FilterExpressions

from .paramset import ParameterSet
from .ScriptReader import ScriptReader, check_parse_attributes_section
from .errors import TestSpecError


class TestCreator:

    def __init__(self, rtconfig):
        ""
        self.evaluator = ExpressionEvaluator( rtconfig.platformName(),
                                              rtconfig.getOptionList() )

    def fromFile(self, rootpath, relpath, force_params):
        """
        The 'rootpath' is the top directory of the file scan.  The 'relpath' is
        the name of the test file relative to 'rootpath' (it must not be an
        absolute path).  If 'force_params' is not None, then any parameters in
        the test that are in the 'force_params' dictionary have their values
        replaced for that parameter name.
        
        Returns a list of TestSpec objects, including a "parent" test if needed.
        """
        tests = create_testlist( self.evaluator,
                                 rootpath,
                                 relpath,
                                 force_params )

        return tests

    def reparse(self, tspec):
        """
        Parses the test source file and resets the settings for the given test.
        The test name is not changed.  The parameters in the test XML file are
        not considered; instead, the parameters already defined in the test
        object are used.

        If the test XML contains bad syntax, a TestSpecError is raised.
        """
        reparse_test_object( self.evaluator, tspec )


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
        return word_expr.evaluate( self.option_list.count )


def create_testlist( evaluator, rootpath, relpath, force_params ):
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
            L = createXmlTest( tname, filedoc, rootpath, relpath,
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

    for tspec in tL:
        tspec.setConstructionCompleted()

    return tL


def createXmlTest( tname, filedoc, rootpath, relpath, force_params, evaluator ):
    ""
    paramset = parseTestParameters( filedoc, tname, evaluator, force_params )
    numparams = len( paramset.getParameters() )

    # create the test instances

    testL = generate_test_objects( tname, rootpath, relpath, paramset )

    if len(testL) > 0:
        # check for parameterize/analyze

        t = testL[0]

        analyze_spec = parseAnalyze( t, filedoc, evaluator )

        if analyze_spec:
            if numparams == 0:
                raise TestSpecError( 'an analyze requires at least one ' + \
                                     'parameter to be defined' )

            # create an analyze test
            parent = t.makeParent()
            parent.setParameterSet( paramset )
            testL.append( parent )

            parent.setAnalyzeScript( analyze_spec )

    # parse and set the rest of the XML file for each test
    
    for t in testL:
        parseKeywords          ( t, filedoc, tname )
        parse_include_platform ( t, filedoc )
        parseTimeouts          ( t, filedoc, evaluator )
        parseExecuteList       ( t, filedoc, evaluator )
        parseFiles             ( t, filedoc, evaluator )
        parseBaseline          ( t, filedoc, evaluator )

    return testL


def createScriptTest( tname, vspecs, rootpath, relpath,
                      force_params, evaluator ):
    ""
    paramset = parseTestParameters_scr( vspecs, tname, evaluator, force_params )

    testL = generate_test_objects( tname, rootpath, relpath, paramset )

    mark_staged_tests( paramset, testL )

    check_add_analyze_test( paramset, testL, vspecs, evaluator )

    for t in testL:
        parseKeywords_scr     ( t, vspecs, tname )
        parse_enable          ( t, vspecs )
        parseFiles_scr        ( t, vspecs, evaluator )
        parseTimeouts_scr     ( t, vspecs, evaluator )
        parseBaseline_scr     ( t, vspecs, evaluator )
        parseDependencies_scr ( t, vspecs, evaluator )
        parse_preload_label   ( t, vspecs, evaluator )

    return testL


def generate_test_objects( tname, rootpath, relpath, paramset ):
    ""
    testL = []

    numparams = len( paramset.getParameters() )
    if numparams == 0:
        t = TestSpec.TestSpec( tname, rootpath, relpath )
        testL.append(t)

    else:
        # take a cartesian product of all the parameter values
        for pdict in paramset.getInstances():
            # create the test and add to test list
            t = TestSpec.TestSpec( tname, rootpath, relpath )
            t.setParameters( pdict )
            testL.append(t)

    return testL


def mark_staged_tests( paramset, testL ):
    """
    1. each test must be told which parameter names form the staged set
    2. the first and last tests in a staged set must be marked as such
    3. each staged test "depends on" the previous staged test
    """
    if paramset.getStagedGroup():

        oracle = StagingOracle( paramset.getStagedGroup(), testL )

        for tspec in testL:

            set_stage_params( tspec, oracle )

            prev = oracle.findPreviousStageTest( tspec )
            if prev:
                add_staged_dependency( tspec, prev )


def set_stage_params( tspec, oracle ):
    ""
    idx = oracle.getStageIndex( tspec )
    is_first = ( idx == 0 )
    is_last = ( idx == oracle.numStages() - 1 )

    names = oracle.getStagedParameterNames()

    tspec.setStagedParameters( is_first, is_last, *names )


def add_staged_dependency( from_tspec, to_tspec ):
    ""
    wx = create_dependency_result_expression( None )
    from_tspec.addDependency( to_tspec.getDisplayString(), wx )


class StagingOracle:

    def __init__(self, stage_group, tspec_list):
        ""
        self.param_nameL = stage_group[0]
        self.param_valueL = stage_group[1]
        self.tspecs = tspec_list

        self.stage_values = [ vals[0] for vals in self.param_valueL ]

    def getStagedParameterNames(self):
        ""
        return self.param_nameL

    def numStages(self):
        ""
        return len( self.param_valueL )

    def getStageIndex(self, tspec):
        ""
        stage_name = self.param_nameL[0]
        stage_val = tspec.getParameterValue( stage_name )
        idx = self.stage_values.index( stage_val )
        return idx

    def findPreviousStageTest(self, tspec):
        ""
        prev_tspec = None

        idx = self.getStageIndex( tspec )
        if idx > 0:

            paramD = tspec.getParameters()
            self._overwrite_with_stage_params( paramD, idx-1 )
            prev_tspec = self._find_test_with_parameters( paramD )

            assert prev_tspec, 'unable to find test with params '+str(paramD)

        return prev_tspec

    def _overwrite_with_stage_params(self, paramD, stage_idx):
        ""
        for i,pname in enumerate( self.param_nameL ):
            pval = self.param_valueL[ stage_idx ][i]
            paramD[ pname ] = pval

    def _find_test_with_parameters(self, paramD):
        ""
        for tspec in self.tspecs:
            if tspec.getParameters() == paramD:
                return tspec


def check_add_analyze_test( paramset, testL, vspecs, evaluator ):
    ""
    if len(testL) > 0:

        t = testL[0]

        analyze_spec = parseAnalyze_scr( t, vspecs, evaluator )

        if analyze_spec:

            numparams = len( paramset.getParameters() )
            if numparams == 0:
                raise TestSpecError( 'an analyze requires at least one ' + \
                                     'parameter to be defined' )

            # create an analyze test
            parent = t.makeParent()
            parent.setParameterSet( paramset )
            testL.append( parent )

            parent.setAnalyzeScript( analyze_spec )
            if not analyze_spec.startswith('-'):
                parent.addLinkFile( analyze_spec )


def reparse_test_object( evaluator, testobj ):
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

        if testobj.isAnalyze():
            analyze_spec = parseAnalyze( testobj, filedoc, evaluator )
            testobj.setAnalyzeScript( analyze_spec )

        parseKeywords    ( testobj, filedoc, tname )
        parseFiles       ( testobj, filedoc, evaluator )
        parseTimeouts    ( testobj, filedoc, evaluator )
        parseExecuteList ( testobj, filedoc, evaluator )
        parseBaseline    ( testobj, filedoc, evaluator )

    elif ext == '.vvt':

        vspecs = ScriptReader( fname )

        # run through the test name logic to check validity
        nameL = testNameList_scr( vspecs )

        tname = testobj.getName()

        parse_enable( testobj, vspecs )

        if testobj.isAnalyze():
            analyze_spec = parseAnalyze_scr( testobj, vspecs, evaluator )
            testobj.setAnalyzeScript( analyze_spec )
            if not analyze_spec.startswith('-'):
                testobj.addLinkFile( analyze_spec )

        parseKeywords_scr ( testobj, vspecs, tname )
        parseFiles_scr    ( testobj, vspecs, evaluator )
        parseTimeouts_scr ( testobj, vspecs, evaluator )
        parseBaseline_scr ( testobj, vspecs, evaluator )
        parseDependencies_scr ( testobj, vspecs, evaluator )
        parse_preload_label   ( testobj, vspecs, evaluator )

    else:
        raise Exception( "invalid file extension: "+ext )

    testobj.setConstructionCompleted()


##########################################################################

def testNameList_scr( vspecs ):
    """
    Determine the test name and check for validity.
    Returns a list of test names.
    """
    L = []

    specL = vspecs.getSpecList("testname") + vspecs.getSpecList("name")
    for spec in specL:

        if spec.attrs:
            raise TestSpecError( 'no attributes allowed here, ' + \
                                 'line ' + str(spec.lineno) )

        name,attrD = parse_test_name_value( spec.value, spec.lineno )

        if not name or not allowableString(name):
            raise TestSpecError( 'missing or invalid test name, ' + \
                                 'line ' + str(spec.lineno) )
        L.append( name )

    if len(L) == 0:
        # the name defaults to the basename of the script file
        L.append( vspecs.basename() )

    return L


def parse_test_name_value( value, lineno ):
    ""
    name = value
    aD = {}

    sL = value.split( None, 1 )
    if len(sL) == 2:
        name,tail = sL

        if tail[0] == '#':
            pass

        elif tail[0] == '(':
            aD,tail = check_parse_attributes_section( tail, str(lineno) )
            check_test_name_attributes( aD, lineno )

        else:
            raise TestSpecError( 'invalid test name: ' + \
                    ', line ' + str(lineno) )

    return name, aD


def check_test_name_attributes( attrD, lineno ):
    ""
    if attrD:

        checkD = {}
        checkD.update( attrD )

        checkD.pop( 'depends on', None )
        checkD.pop( 'result', None )

        if len( checkD ) > 0:
            raise TestSpecError( 'unexpected attributes: ' + \
                ' '.join( checkD.keys() ) + ', line ' + str(lineno) )


def parseKeywords_scr( tspec, vspecs, tname ):
    """
    Parse the test keywords for the test script file.
    
      keywords : key1 key2
      keywords (testname=mytest) : key3
    
    Also includes the test name and the parameterize names.
    TODO: what other implicit keywords ??
    """
    keys = []

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
                keys.append( key )
            else:
                raise TestSpecError( 'invalid keyword: "'+key+'", line ' + \
                                     str(spec.lineno) )

    tspec.setKeywords( keys )


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

        namestr,valuestr = L

        if not namestr.strip():
            raise TestSpecError( "no parameter name given, " + \
                                 "line " + str(lnum) )
        if not valuestr.strip():
            raise TestSpecError( "no parameter value(s) given, " + \
                                 "line " + str(lnum) )

        nameL = [ n.strip() for n in namestr.strip().split(',') ]

        check_parameter_names( nameL, lnum )

        if len(nameL) == 1:
            valL = parse_param_values( nameL[0], valuestr, force_params )
            check_parameter_values( valL, lnum )
        else:
            valL = parse_param_group_values( nameL, valuestr, lnum )
            check_forced_group_parameter( force_params, nameL, lnum )

        staged = check_for_staging( spec.attrs, paramset, nameL, valL, lnum )

        check_for_duplicate_parameter( valL, lnum )

        if len(nameL) == 1:
            paramset.addParameter( nameL[0], valL )
        else:
            paramset.addParameterGroup( nameL, valL, staged )

    return paramset


def check_for_staging( spec_attrs, paramset, nameL, valL, lineno ):
    """
    for staged parameterize, the names & values are augmented. for example,

        nameL = [ 'pname' ] would become [ 'stage', 'pname' ]
        valL = [ 'val1', 'val2' ] would become [ ['1','val1'], ['2','val2'] ]
    """
    if spec_attrs and 'staged' in spec_attrs:

        if paramset.getStagedGroup() != None:
            raise TestSpecError( 'only one parameterize can be staged' + \
                                 ', line ' + str(lineno) )

        insert_staging_into_names_and_values( nameL, valL )

        return True

    return False


def insert_staging_into_names_and_values( names, values ):
    ""
    if len( names ) == 1:
        values[:] = [ [str(i),v] for i,v in enumerate(values, start=1) ]
    else:
        values[:] = [ [str(i)]+vL for i,vL in enumerate(values, start=1) ]

    names[:] = [ 'stage' ] + names


def check_parameter_names( name_list, lineno ):
    ""
    for v in name_list:
        if not allowableVariable(v):
            raise TestSpecError( 'invalid parameter name: "' + \
                                 v+'", line ' + str(lineno) )


def check_parameter_values( value_list, lineno ):
    ""
    for v in value_list:
        if not allowableString(v):
            raise TestSpecError( 'invalid parameter value: "' + \
                                 v+'", line ' + str(lineno) )


def parse_param_values( param_name, value_string, force_params ):
    ""
    if force_params != None and param_name in force_params:
        vals = force_params[ param_name ]
    else:
        vals = value_string.strip().split()

    return vals


spaced_comma_pattern = re.compile( '[\t ]*,[\t ]*' )

def parse_param_group_values( name_list, value_string, lineno ):
    ""
    compressed_string = spaced_comma_pattern.sub( ',', value_string.strip() )

    vL = []
    for s in compressed_string.split():

        gL = s.split(',')
        if len(gL) != len(name_list):
            raise TestSpecError( 'malformed parameter list: "' + \
                                  s+'", line ' + str(lineno) )

        check_parameter_values( gL, lineno )

        vL.append( gL )

    return vL


def check_forced_group_parameter( force_params, name_list, lineno ):
    ""
    if force_params != None:
        for n in name_list:
            if n in force_params:
                raise TestSpecError( 'cannot force a grouped ' + \
                                     'parameter name: "' + \
                                     n+'", line ' + str(lineno) )


def check_for_duplicate_parameter( paramlist, lineno ):
    ""
    for val in paramlist:
        if paramlist.count( val ) > 1:

            if is_list_or_tuple(val):
                dup = ','.join(val)
            else:
                dup = str(val)

            raise TestSpecError( 'duplicate parameter value: "'+dup + \
                                 '", line ' + str(lineno) )


def is_list_or_tuple( obj ):
    ""
    if type(obj) in [ type(()), type([]) ]:
        return True

    return False


def parseAnalyze_scr( t, vspecs, evaluator ):
    """
    Parse any analyze specifications.
    
        #VVT: analyze : analyze.py
        #VVT: analyze : --analyze
        #VVT: analyze (testname=not mytest_fast) : --analyze

        - if the value starts with a hyphen, then an option is assumed
        - otherwise, a script file is assumed

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

        if spec.attrs and 'file' in spec.attrs:
            raise TestSpecError( 'the "file" analyze attribute is ' + \
                                 'no longer supported, ' + \
                                 'line ' + str(spec.lineno) )

        if spec.attrs and 'argument' in spec.attrs:
            raise TestSpecError( 'the "argument" analyze attribute is ' + \
                                 'no longer supported, ' + \
                                 'line ' + str(spec.lineno) )

        sval = spec.value
        if not sval or not sval.strip():
            raise TestSpecError( 'missing or invalid analyze value, ' + \
                                 'line ' + str(spec.lineno) )

        specval = sval.strip()

    return specval


def parseFiles_scr( t, vspecs, evaluator ):
    """
        #VVT: copy : file1 file2
        #VVT: link : file3 file4
        #VVT: copy (filters) : srcname1,copyname1 srcname2,copyname2
        #VVT: link (filters) : srcname1,linkname1 srcname2,linkname2

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
      #VVT: baseline : copyfrom,copyto copyfrom,copyto
      #VVT: baseline : --option-name
      #VVT: baseline : baseline.py
    
    where the existence of a comma triggers the first form
    otherwise, if the value starts with a hyphen then the second form
    otherwise, the value is the name of a filename
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
                raise TestSpecError( 'the "file" baseline attribute is ' + \
                                     'no longer supported, ' + \
                                     'line ' + str(spec.lineno) )

            if spec.attrs and 'argument' in spec.attrs:
                raise TestSpecError( 'the "argument" baseline attribute is ' + \
                                     'no longer supported, ' + \
                                     'line ' + str(spec.lineno) )

            if ',' in sval:
                form = 'copy'
            elif sval.startswith( '-' ):
                form = 'arg'
            else:
                form = 'file'

            if ',' in sval:
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

            else:
                t.setBaselineScript( sval )
                if not sval.startswith( '-' ):
                    t.addLinkFile( sval )


def parseDependencies_scr( t, vspecs, evaluator ):
    """
    Parse the test names that must run before this test can run.

        #VVT: depends on : test1 test2
        #VVT: depends on : test_pattern
        #VVT: depends on (result=pass) : testname
        #VVT: depends on (result="pass or diff") : testname
        #VVT: depends on (result="*") : testname

        #VVT: testname = testA (depends on=testB, result="*")
    """
    tname = t.getName()
    params = t.getParameters()

    for spec in vspecs.getSpecList( 'depends on' ):
        if filterAttr_scr( spec.attrs, tname, params, evaluator, spec.lineno ):

            wx = create_dependency_result_expression( spec.attrs )

            for val in spec.value.strip().split():
                t.addDependency( val, wx )

    specL = vspecs.getSpecList("testname") + vspecs.getSpecList("name")
    for spec in specL:

        name,attrD = parse_test_name_value( spec.value, spec.lineno )
        if name == tname:

            wx = create_dependency_result_expression( attrD )

            for depname in attrD.get( 'depends on', '' ).split():
                t.addDependency( depname, wx )


def create_dependency_result_expression( attrs ):
    ""
    wx = None

    if attrs != None and 'result' in attrs:

        result = attrs['result'].strip()

        if result == '*':
            wx = FilterExpressions.WordExpression()
        else:
            wx = FilterExpressions.WordExpression( result )

    return wx


def parse_preload_label( tspec, vspecs, evaluator ):
    """
    #VVT: preload (filters) : label
    """
    tname = tspec.getName()
    params = tspec.getParameters()

    for spec in vspecs.getSpecList( 'preload' ):
        if filterAttr_scr( spec.attrs, tname, params, evaluator, spec.lineno ):
            val = ' '.join( spec.value.strip().split() )
            tspec.setPreloadLabel( val )


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
    
    except ValueError:
      raise TestSpecError( "bad " + attrname + " expression, line " + \
                           lineno + ": " + str(sys.exc_info()[1]) )
    
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
      attrL = list( attrs.items() )
      attrL.sort()
      for n,v in attrL:
        
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
        
        vals = v.split()
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


def parseKeywords( tspec, filedoc, tname ):
    """
    Parse the test keywords for the test XML file.
    
      <keywords> key1 key2 </keywords>
      <keywords testname="mytest"> key3 </keywords>
    
    Also includes the name="..." on <execute> blocks and the parameter names
    in <parameterize> blocks.
    """
    keys = []

    for nd in filedoc.matchNodes(['keywords$']):
        if testname_ok( nd, tname ):
            for key in nd.getContent().split():
                if allowableString(key):
                    keys.append( key )
                else:
                    raise TestSpecError( 'invalid keyword: "' + key + \
                                         '", line ' + str(nd.getLineNumber()) )

    tspec.setKeywords( keys )


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


def parse_enable( testobj, vspecs ):
    """
    Parse syntax that will filter out this test by platform or build option.
    
    Platform expressions and build options use word expressions.
    
        #VVT: enable (platforms="not SunOS and not Linux")
        #VVT: enable (options="not dbg and ( tridev or tri8 )")
        #VVT: enable (platforms="...", options="...")
        #VVT: enable = True
        #VVT: enable = False

    If both platform and option expressions are given, their results are
    ANDed together.  If more than one "enable" block is given, each must
    result in True for the test to be included.
    """
    tname = testobj.getName()

    for spec in vspecs.getSpecList( 'enable' ):

        platexpr = None
        opexpr = None

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

        if spec.value:
            val = spec.value.lower().strip()
            if val != 'true' and val != 'false':
                raise TestSpecError( 'invalid "enable" value, line ' + \
                                     str(spec.lineno) )
            if val == 'false' and ( platexpr != None or opexpr != None ):
                raise TestSpecError( 'an "enable" with platforms or ' + \
                    'options attributes cannot specify "false", line ' + \
                    str(spec.lineno) )
            testobj.setEnabled( val == 'true' )


def parseAnalyze( t, filedoc, evaluator ):
    """
    Parse analyze scripts that get run after all parameterized tests complete.
    
       <analyze keywords="..." parameters="..." platform="...">
         script contents that post processes test results
       </analyze>

    Returns true if the test specifies an analyze script.
    """
    analyze_spec = None
    
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
        if analyze_spec == None:
          analyze_spec = content.strip()
        else:
          analyze_spec += os.linesep + content.strip()

    return analyze_spec


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
          val = nd.getAttr("value").strip()
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
    """
    for nd in filedoc.matchNodes(["execute$"]):

        skip = 0
        for n,v in nd.getAttrs().items():
            isfa, istrue = filterAttr( n, v, t.getName(), t.getParameters(),
                                       evaluator, str(nd.getLineNumber()) )
            if isfa and not istrue:
                skip = 1
                break

        if nd.hasAttr('ifdef'):
            L = nd.getAttr('ifdef').split()
            for n in L:
                if not allowableVariable(n):
                    raise TestSpecError( 'invalid environment variable name: "' + \
                                         n + '"' + ', line ' + str(nd.getLineNumber()) )
            for n in L:
                if n not in os.environ:
                    skip = 1
                    break

        if not skip:

            xname = nd.getAttr('name', None)

            analyze = False
            if xname == None:
                if nd.getAttr('analyze','').strip().lower() == 'yes':
                    analyze = True
            else:
                if not xname or not allowableString(xname):
                    raise TestSpecError( 'invalid name value: "' + xname + \
                                         '", line ' + str(nd.getLineNumber()) )

            xstatus = nd.getAttr( 'expect', None )

            content = nd.getContent()
            if content == None: content = ''
            else:               content = content.strip()

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
    if platname == None: platname = ''
    
    if len(fL) > 0:
      
      # substitute parameter values for $PARAM, ${PARAM}, and {$PARAM} patterns;
      # also replace the special NAME variable with the name of the test and
      # PLATFORM with the name of the current platform
      for n,v in list(paramD.items()) + [('NAME',tname)] + [('PLATFORM',platname)]:
        pat1 = re.compile( '[{](?<![\\\\])[$]' + n + '[}]' )
        pat2 = re.compile( '(?<![\\\\])[$][{]' + n + '[}]' )
        pat3 = re.compile( '(?<![\\\\])[$]' + n + '(?![_a-zA-Z0-9])' )
        if type(fL[0]) == type([]):
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
      if type(fL[0]) == type([]):
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
    
    fileL = nd.getContent().split()
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
    t.setSourceFiles( list( T[0] for T in fL ) )


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
    scriptfrag = ''

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
          fname = fname.split()
          fdest = nd.getAttr('destination',None)
          if fdest == None:
            for f in fname:
              f = str(f)
              fL.append( [f,f] )
            
          else:
            fdest = fdest.split()
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
        
        script = nd.getContent().strip()
        if script:
          scriptfrag += '\n' + script

    if scriptfrag:
        t.setBaselineScript( scriptfrag )


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
      if c not in allowable_chars_dict:
        return 0
    return 1

alphanum_chars_dict = {}
for c in alphanum_chars:
  alphanum_chars_dict[c] = None

def allowableVariable(s):
    if s[:1] in ['0','1','2','3','4','5','6','7','8','9','_']:
      return 0
    for c in s:
      if c not in alphanum_chars_dict:
        return 0
    return 1
