#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os
from os.path import basename

varname_chars_list = "abcdefghijklmnopqrstuvwxyz" + \
                     "ABCDEFGHIJKLMNOPQRSTUVWXYZ" + "0123456789_"


class TestSpec:
    """
    Holds the contents of a test specification in memory.  Also stores
    arbitrary attributes, such as the results of an execution of the test.
    
    Many specifications allow filtering by platform, parameter value, and
    environment variable, and are referred to as "standard filtering".
    """
    
    def getName(self):
        """
        The name of the test.
        """
        return self.name
    
    def getFilename(self):
        """
        The full path of the original test specification file.
        """
        return os.path.join( self.rootpath, self.filepath )
    
    def getRootpath(self):
        """
        The top directory of the original scan.
        """
        return self.rootpath
    
    def getFilepath(self):
        """
        The original test specification file relative to the root path.
        """
        return self.filepath
    
    def getDirectory(self):
        """
        The directory containing the original test specification file.
        """
        return os.path.dirname( self.getFilename() )
    
    def getExecuteDirectory(self):
        """
        The directory containing getFilepath() followed by a subdir containing
        the test name and the test parameters, such as "some/dir/myname.np=4".
        """
        return self.xdir

    def getDisplayString(self):
        """
        """
        dis = self.getExecuteDirectory()

        if self.staged:

            stage_name,params = self.staged

            paramL = list( params )
            paramL.sort()
            pL = []
            for param in paramL:
                pL.append( param+'='+self.params[param] )

            dis += ' ' + stage_name+'='+self.params[stage_name]
            dis += '('+','.join( pL )+')'

        return dis

    def getID(self):
        """
        A tuple uniquely identifying this test, which is composed of the
        test filename relative to the scan root, the test name, and the test
        parameters with values.
        """
        return self.testid

    def getStageID(self):
        ""
        if self.staged:
            stage_name = self.staged[0]
            stage_value = self.params[ stage_name ]
            return stage_name+'='+stage_value

        return None

    def isFirstStage(self):
        """
        True if this test is not staged or this is the first stage.
        """
        return self.first_stage

    def isLastStage(self):
        """
        True if this test is not staged or this is the last stage.
        """
        return self.last_stage

    def getSpecificationForm(self):
        """
        Returns "xml" if the test was specified using XML, or "script" if the
        test is a script.
        """
        if os.path.splitext( self.getFilepath() )[1] == '.xml':
            return 'xml'
        else:
            return 'script'

    def getKeywords(self, include_implicit=True):
        """
        Returns the list of keyword strings.  If 'include_implicit' is True,
        the parameter names and the test name itself is included in the list.
        """
        if include_implicit:
            kwset = set( self.getParameterNames() )
            kwset.add( self.name )
            kwset.add( os.path.splitext( basename( self.getFilepath() ) )[0] )
            for n,s,x,b in self.execL:
                if n:
                    kwset.add( n )
            kwset.update( self.keywords )
        else:
            kwset = self.keywords

        return list( kwset )

    def hasKeyword(self, keyword):
        """
        Returns true if the keyword is contained in the list of keywords.
        """
        return keyword in self.getKeywords()

    def getParameters(self):
        """
        Returns a dictionary mapping parameter names to values.
        """
        D = {}
        D.update( self.params )
        return D
    
    def getParameterNames(self):
        """
        Returns a list of the parameter names for this test.
        """
        return self.params.keys()
    
    def getParameterValue(self, param_name):
        """
        Returns the string value for the given parameter name.
        """
        return self.params[param_name]
    
    def getParameterSet(self):
        """
        Return the test's ParameterSet instance.  Will be None unless this
        is a parent.
        """
        return self.paramset

    def isAnalyze(self):
        """
        Returns true if this is the analyze test of a parameterize/analyze
        test group.
        """
        if self.paramset != None:
            if len( self.params ) == 0:
                return True

        return False

    def getAnalyzeScript(self):
        """
        Returns None, or a string if this is an analyze test.  The string is
        is one of the following:

            1. If this test is specified with XML, then the returned string
               is a csh script fragment.

            2. If this is a script test, and the returned string starts with
               a hyphen, then the test script should be run with the string
               as an option to the base script file.

            3. If this is a script test, and the returned string does not start
               with a hyphen, then the string is a filename of a separate
               script to run.  The filename is a relative path to
               getDirectory().
        """
        return self.analyze_spec

    def getTimeout(self):
        """
        Returns a timeout specification, in seconds (an integer).  Or None if
        not specified.
        """
        return self.timeout

    def getPreloadLabel(self):
        ""
        return self.preload

    def getLinkFiles(self):
        """
        Returns a list of pairs (source filename, test filename) for files
        that are to be soft linked into the testing directory.  The test
        filename may be None if it was not specified (meaning the name should
        be the same as the name in the source directory).
        """
        return [] + self.lnfiles
    
    def getCopyFiles(self):
        """
        Returns a list of pairs (source filename, test filename) for files
        that are to be copied into the testing directory.  The test
        filename may be None if it was not specified (meaning the name should
        be the same as the name in the source directory).
        """
        return [] + self.cpfiles

    def getExecutionList(self):
        """
        Returns, in order, raw fragments and named execution fragments for
        the given platform.  Returns a list of tuples
          ( name, fragment, exit status, analyze boolean )
        where 'name' is None for raw fragments and 'exit status' is a string.
        """
        return [] + self.execL

    def hasBaseline(self):
        """
        Returns true if this test has a baseline specification.
        """
        return len(self.baseline_files) > 0 or self.baseline_spec

    def getBaselineFiles(self):
        """
        Returns a list of pairs (test directory name, source directory name)
        of files to be copied from the testing directory to the source
        directory.
        """
        return self.baseline_files

    def getBaselineScript(self):
        """
        Returns None if this test has no baseline script, or a string which
        is one of the following:

            1. If this test is specified with XML, then the returned string
               is a csh script fragment.

            2. If this is a script test, and the returned string starts with
               a hyphen, then the test script should be run with the string
               as an option to the base script file.

            3. If this is a script test, and the returned string does not start
               with a hyphen, then the string is a filename of a separate
               script to run.  The file path is a relative to getDirectory().
        """
        return self.baseline_spec

    def getDependencies(self):
        """
        Returns a list of ( xdir pattern, result expression ) specifying
        test dependencies and their expected results.

        The xdir pattern is a shell pattern (not a regular expression) and
        will be matched against the execution directory of the dependency
        test.  For example "subdir/name*.np=8".

        The result expression is a FilterExpressions.WordExpression object
        and should be evaluated against the dependency test result.  For
        example "pass or diff" or just "pass".  If the dependency result
        expression is not true, then this test should not be run.
        """
        return [] + self.deps

    varname_chars = {}
    
    def setAttr(self, name, value):
        """
        Set a name to value pair.  The name can only contain a-zA-Z0-9 and _.
        """
        for c in name:
          if c not in TestSpec.varname_chars:
            raise ValueError( "character '" + c + "' not allowed in name" )
        self.attrs[name] = value
    
    def hasAttr(self, name):
        return name in self.attrs
    
    def getAttr(self, name, *args):
        """
        Returns the attribute value corresponding to the attribute name.
        If the attribute name does not exist, an exception is thrown.  If
        the attribute name does not exist and a default value is given, the
        default value is returned.
        """
        if len(args) > 0:
          return self.attrs.get( name, args[0] )
        return self.attrs[name]

    def removeAttr(self, name):
        ""
        self.attrs.pop( name, None )
    
    def getAttrs(self):
        """
        Returns a copy of the test attributes (a name->value dictionary).
        """
        aD = {}
        aD.update( self.attrs )
        return aD
    
    def getSourceFiles(self):
        """
        Gathers and returns a list of files that are needed by this test from
        the test source area.  The files are obtained from the files to be
        copied, soft linked, rebaselined, and files just listed as needed.
        """
        D = {}
        for f,tf in self.getLinkFiles(): D[f] = None
        for f,tf in self.getCopyFiles(): D[f] = None
        for tf,f in self.getBaselineFiles(): D[f] = None
        for f in self.src_files: D[f] = None
        return list( D.keys() )
    
    ##########################################################
    
    def __init__(self, name, rootpath, filepath):
        """
        A test object always needs a root path and file path, where the file
        path must be a relative path name.
        """
        assert not os.path.isabs(filepath)

        self.data = {}

        self.ctor_done = False

        self.name = name
        self.rootpath = rootpath
        self.filepath = filepath

        self.keywords = set()      # set of strings
        self.params = {}           # name string to value string
        self.analyze_spec = None
        self.timeout = None        # timeout value in seconds (an integer)
        self.preload = None        # a string label
        self.execL = []            # list of
                                   #   (name, fragment, exit status, analyze)
                                   # where name is None when the
                                   # fragment is a raw fragment, exit status
                                   # is any string, and analyze is true/false
        self.lnfiles = []          # list of (src name, test name)
        self.cpfiles = []          # list of (src name, test name)
        self.baseline_files = []   # list of (test name, src name)
        self.baseline_spec = None
        self.src_files = []        # extra source files listed by the test
        self.deps = []             # list of (xdir pattern, result expr)
        self.attrs = {}            # maps name string to value string; the
                                   # allowed characters are restricted
        self.paramset = None       # for parent tests, this maps parameter
                                   # names to lists of values
        self.staged = None         # ( stage param name, list of param names )
        self.first_stage = True
        self.last_stage = True

        # initial execute directory; recomputed by setParameters()
        self.xdir = self._compute_execute_directory()
        self.testid = self._compute_id()

        # always add the test specification file to the linked file list
        self.lnfiles.append( (basename(self.filepath),None) )
    
    def __str__(self):
        return 'TestSpec(name=' + str(self.name) + ', xdir=' + self.xdir + ')'

    def setConstructionCompleted(self):
        ""
        self.ctor_done = True

    def constructionCompleted(self):
        ""
        return self.ctor_done

    def addDataNameIfNeededAndReturnValue(self, name, data_type):
        ""
        if name not in self.data:
            self.data[name] = data_type()
        return self.data[name]

    ##########################################################
    
    # construction methods

    def addEnablePlatformExpression(self, word_expression):
        ""
        L = self.addDataNameIfNeededAndReturnValue( 'platform enable', list )
        L.append( word_expression )

    def addEnableOptionExpression(self, word_expression):
        ""
        L = self.addDataNameIfNeededAndReturnValue( 'option enable', list )
        L.append( word_expression )

    def getPlatformEnableExpressions(self):
        ""
        return self.data.get( 'platform enable', [] )

    def getOptionEnableExpressions(self):
        ""
        return self.data.get( 'option enable', [] )

    def setKeywords(self, keyword_list):
        """
        A list of strings.
        """
        self.keywords = set( keyword_list )

        # transfer TDD marks to the attributes
        if 'TDD' in self.keywords:
            self.setAttr( 'TDD', True )

    def setParameters(self, param_dict):
        """
        Set the key/value pairs for this test and reset the ID and execute
        directory.
        """
        self.params.clear()
        self.params.update( param_dict )

        self.xdir = self._compute_execute_directory()

        self.testid = self._compute_id()

    def setStagedParameters(self, is_first_stage, is_last_stage,
                                  stage_name, *param_names):
        ""
        self.first_stage = is_first_stage
        self.last_stage = is_last_stage

        self.staged = [ stage_name, list( param_names ) ]

        self.xdir = self._compute_execute_directory()

    def getStagedParameters(self):
        ""
        if self.staged:
            return [ self.first_stage, self.last_stage ] + \
                   [ self.staged[0] ] + self.staged[1]

        return None

    def _compute_id(self):
        ""
        lst = [ self.filepath, self.name ]
        lst.extend( self._get_parameters_as_list() )
        return tuple( lst )

    def _compute_execute_directory(self):
        ""
        bname = self.getName()

        paramL = self._get_parameters_as_list( compress_stage=True )
        if len( paramL ) > 0:
            bname += '.' + '.'.join(paramL)

        dname = os.path.dirname( self.getFilepath() )

        return os.path.normpath( os.path.join( dname, bname ) )

    def _get_parameters_as_list(self, compress_stage=False):
        ""
        L = []
        if len(self.params) > 0:
            for n,v in self.params.items():
                if self._hide_parameter( n, compress_stage ):
                    pass
                elif self._compress_parameter( n, compress_stage ):
                    L.append( n )
                else:
                    L.append( n + '=' + v )
            L.sort()

        return L

    def _hide_parameter(self, param_name, compress_stage):
        ""
        if compress_stage and self.staged:
            return param_name == self.staged[0]
        return False

    def _compress_parameter(self, param_name, compress_stage):
        ""
        if compress_stage and self.staged:
            if param_name in self.staged[1]:
                return True
        return False

    def setParameterSet(self, param_set):
        """
        Set the ParameterSet instance, which maps parameter names to a list of
        parameter values.
        """
        self.paramset = param_set

    def setAnalyzeScript(self, script_spec):
        ""
        self.analyze_spec = script_spec

    def setTimeout(self, timeout):
        """
        Adds a timeout specification.  Sending in None will remove the timeout.
        """
        if timeout != None:
            timeout = int(timeout)
        self.timeout = timeout

    def setPreloadLabel(self, label):
        ""
        self.preload = label

    def appendExecutionFragment(self, fragment, exit_status, analyze ):
        """
        Append a raw execution fragment to this test.  The exit_status is any
        string.  The 'analyze' is either "yes" or "no".
        """
        self.execL.append( (None, fragment, exit_status, analyze) )
    
    def appendNamedExecutionFragment(self, name, content, exit_status):
        """
        Append an execution fragment to this test.  The name will be searched
        in a fragment database when writing the actual script.  The content
        replaces the $(CONTENT) variable in the database fragment.  The
        'exit_status' is any string.
        """
        assert name
        s = ' '.join( content.split() )  # remove embedded newlines
        self.execL.append( (name, s, exit_status, False) )
   
    def addLinkFile(self, srcname, destname=None):
        """
        Add the given file name to the set of files to link from the test
        source area into the test execution directory.  The 'srcname' is an
        existing file, and 'destname' is the name of the sym link file in
        the test execution directory.  If 'destname' is None, the base name
        of 'srcname' is used.
        """
        assert srcname and not os.path.isabs( srcname )
        if (srcname,destname) not in self.lnfiles:
            self.lnfiles.append( (srcname,destname) )
    
    def addCopyFile(self, srcname, destname=None):
        """
        Add the given file name to the set of files to copy from the test
        source area into the test execution directory.  The 'srcname' is an
        existing file, and 'destname' is the name of the file in the test
        execution directory.  If 'destname' is None, the base name of
        'srcname' is used.
        """
        assert srcname and not os.path.isabs( srcname )
        if (srcname,destname) not in self.cpfiles:
            self.cpfiles.append( (srcname,destname) )
    
    def addBaselineFile(self, test_dir_name, source_dir_name):
        """
        Add a file to be copied from the test directory to the source
        directory during baselining.
        """
        assert test_dir_name and source_dir_name
        self.baseline_files.append( (test_dir_name, source_dir_name) )

    def setBaselineScript(self, script_spec):
        ""
        self.baseline_spec = script_spec

    def setSourceFiles(self, files):
        """
        A list of file names needed by this test (this is in addition to the
        files to be copied, linked, and baselined.)
        """
        self.src_files = [] + files

    def addDependency(self, xdir_pattern, result_word_expr):
        ""
        self.deps.append( (xdir_pattern, result_word_expr) )

    def makeParent(self):
        """
        Creates a TestSpec instance and copies all data members of this test
        except the parameters.  The new test instance is returned.
        """
        ts = TestSpec( self.name, self.rootpath, self.filepath )
        ts.ctor_done = self.ctor_done
        ts.keywords = set( self.keywords )
        ts.setParameters({})  # skip ts.params
        ts.analyze_spec = self.analyze_spec
        ts.timeout = self.timeout
        ts.execL = list( self.execL )
        ts.lnfiles = list( self.lnfiles )
        ts.cpfiles = list( self.cpfiles )
        ts.baseline_files = list( self.baseline_files )
        ts.baseline_spec = self.baseline_spec
        ts.deps = list( self.deps )
        ts.attrs.clear() ; self.attrs.update( self.attrs )
        return ts

for c in varname_chars_list:
  TestSpec.varname_chars[c] = None
