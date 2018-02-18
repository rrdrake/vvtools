#!/usr/bin/env python

import os
import string
import types

results_keywords = [ 'notrun', 'notdone',
                     'fail', 'diff', 'pass',
                     'timeout' ]

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

    def getForm(self, key, *default):
        """
        Gets test form information for a given 'key'.
        """
        if len(default) > 0:
            return self.form.get( key, default[0] )
        return self.form[ key ]

    def getOrigin(self):
        """
        Returns a list of origin strings.  If the list is empty, only the
        constructor was called.  Origin strings:
            "file"   : this object was constructed or refreshed from test source
            "string" : this object was constructed using a string
            "copy"   : this object is a copy of another object
        """
        return []+self.origin

    def getKeywords(self, result_attrs=False):
        """
        Returns the list of keyword strings.  If 'result_attrs' is true, the
        attribute values for "state" and "result" are included if they exist.
        """
        kL = [] + self.keywords
        if result_attrs:
          if self.attrs.has_key('state'): kL.append( self.attrs['state'] )
          if self.attrs.has_key('result'): kL.append( self.attrs['result'] )
        return kL
    
    def hasKeyword(self, keyword):
        """
        Returns true if the keyword is contained in the list of keywords.
        """
        return keyword in self.keywords
    
    def getResultsKeywords(self):
        """
        Returns the keyword or keywords indicating the run state of the test.
        """
        state = self.getAttr('state',None)
        if state != None:
          if state == "notrun": return ["notrun"]
          if state == "notdone": return ["notdone","running"]
        result = self.getAttr('result',None)
        if result != None:
          if result == "timeout": return ["timeout","fail"]
          return [result]
        return []
    
    def getParameters(self):
        """
        Returns a dictionary mapping parameter names to values.
        """
        D = self.__copy_dictionary(self.params)
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

    def getAnalyze(self, key, *default):
        """
        An analyze script can be specified by the contents of the script,
        by a file name, or by a command line option to the test file.  Which
        one of these and the information for each are contained in a dict.
        This function allows access to that dict.

        Returns the value for the given key.  If 'default' is given and the
        key is not in the dict, then 'default' is reterned.
        """
        if len(default) > 0:
            return self.analyze.get( key, default[0] )
        return self.analyze[key]
    
    def getTimeout(self):
        """
        Returns a timeout specification, in seconds (an integer).  Or None if
        not specified.
        """
        return self.timeout
    
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
    
    def hasBaseline(self):
        """
        Returns true if this test has a baseline specification.
        """
        return len(self.baseline) > 0

    def getBaselineFiles(self):
        """
        Returns a list of pairs (test directory name, source directory name)
        of files to be copied from the testing directory to the source
        directory.
        """
        return self.baseline.get( 'files', [] )

    def getBaselineFragments(self):
        """
        Returns a list of script fragments to be executed during baselining.
        """
        return self.baseline.get( 'scriptfrag', [] )
    
    def getBaseline(self, key, *default):
        """
        Returns the baseline value for the given key.  If 'default' is given
        and the key is not in the dict, then 'default' is reterned.
        """
        if len(default) > 0:
            return self.baseline.get( key, default[0] )
        return self.baseline[key]

    def getExecutionList(self):
        """
        Returns, in order, raw fragments and named execution fragments for
        the given platform.  Returns a list of tuples
          ( name, fragment, exit status, analyze boolean )
        where 'name' is None for raw fragments and 'exit status' is a string.
        """
        return [] + self.execL
    
    varname_chars = {}
    
    def setAttr(self, name, value):
        """
        Set a name to value pair.  The name can only contain a-zA-Z0-9 and _.
        """
        for c in name:
          if not TestSpec.varname_chars.has_key(c):
            raise ValueError( "character '" + c + "' not allowed in name" )
        self.attrs[name] = value
    
    def hasAttr(self, name):
        return self.attrs.has_key(name)
    
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
        return D.keys()
    
    ##########################################################
    
    def __init__(self, name, rootpath, filepath, origin=None):
        """
        A test object always needs a root path and file path, where the file
        path must be a relative path name.
        """
        assert not os.path.isabs(filepath)

        self.data = {}

        self.form = {}

        self.origin = []  # strings, such as "file", "string", "copy"
        if origin:
            self.origin.append( origin )

        self.name = name
        self.rootpath = rootpath
        self.filepath = filepath

        self.keywords = []         # list of strings
        self.params = {}           # name string to value string
        self.analyze = {}          # analyze script specifications
        self.timeout = None        # timeout value in seconds (an integer)
        self.execL = []            # list of
                                   #   (name, fragment, exit status, analyze)
                                   # where name is None when the
                                   # fragment is a raw fragment, exit status
                                   # is any string, and analyze is true/false
        self.lnfiles = []          # list of (src name, test name)
        self.cpfiles = []          # list of (src name, test name)
        self.baseline = {}         # baseline specifications
        self.src_files = []        # extra source files listed by the test
        self.attrs = {}            # maps name string to value string; the
                                   # allowed characters are restricted
        self.paramset = None       # for parent tests, this maps parameter
                                   # names to lists of values

        # initial execute directory; recomputed by setParameters()
        self.xdir = os.path.normpath( \
                        os.path.join( os.path.dirname(filepath), name ) )

        # set the default attributes
        self.attrs[ 'state' ] = 'notrun'
        self.attrs[ 'xtime' ] = -1
        self.attrs[ 'xdate' ] = -1

        # always add the test specification file to the linked file list
        self.lnfiles.append( (os.path.basename(self.filepath),None) )

    def __cmp__(self, rhs):
        if rhs == None: return 1  # None objects are always less
        if   self.name < rhs.name: return -1
        elif self.name > rhs.name: return  1
        if   self.xdir < rhs.xdir: return -1
        elif self.xdir > rhs.xdir: return  1
        return 0
    
    def __repr__(self):
        return 'TestSpec(name=' + str(self.name) + ', xdir=' + self.xdir + ')'

    def addDataNameIfNeededAndReturnValue(self, name, data_type):
        ""
        if name not in self.data:
            self.data[name] = data_type()
        return self.data[name]

    ##########################################################
    
    # construction methods
    
    def setForm(self, key, value):
        """
        Add the given 'key'='value' pair to the test form information.
        If both 'key' and 'value' are None, then all information is removed
        (the default state).  If just 'value' is None, then 'key' is removed.
        """
        if key == None:
            if value == None:
                self.form.clear()
        else:
            if value == None:
                if key in self.form:
                    self.form.pop( key )
            else:
                self.form[ key ] = value

    def addOrigin(self, origin):
        """
        Appends an origin string to the orgin list for this object.
        """
        assert origin
        self.origin.append( origin )

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
        self.keywords = [] + keyword_list

        # transfer TDD marks to the attributes
        if 'TDD' in self.keywords:
            self.setAttr( 'TDD', True )
    
    def setParameters(self, param_dict):
        """
        Set the key/value pairs for this test and reset the execute directory.
        """
        self.params = self.__copy_dictionary(param_dict)
        
        b = self.getName()
        if len(self.params) > 0:
          L = []
          for n,v in self.params.items():
            L.append( n + '=' + v )
          L.sort()
          b = b + '.' + string.join(L,'.')
        
        d = os.path.dirname( self.getFilepath() )
        
        self.xdir = os.path.normpath( os.path.join( d, b ) )
    
    def setParameterSet(self, param_set):
        """
        Set the ParameterSet instance, which maps parameter names to a list of
        parameter values.
        """
        self.paramset = param_set
    
    def setAnalyze(self, key, value):
        """
        Add the given 'key'='value' pair to the analyze information.
        If 'value' is None, then 'key' is removed.
        """
        if value == None:
            if key in self.analyze:
                self.analyze.pop( key )
        else:
            self.analyze[ key ] = value
    
    def setTimeout(self, timeout):
        """
        Adds a timeout specification.  Sending in None will remove the timeout.
        """
        if timeout != None:
          timeout = int(timeout)
        self.timeout = timeout
    
    def resetExecutionList(self):
        """
        Clears the current list of execution fragments for this test.
        """
        self.execL = []
    
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
        s = string.join( string.split(content) )  # remove embedded newlines
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
        L = self.baseline.get( 'files', None )
        if L == None:
            L = []
            self.baseline[ 'files' ] = L
        L.append( (test_dir_name, source_dir_name) )

    def addBaselineFragment(self, script_fragment):
        """
        Add a script fragment to be executed during baselining.
        """
        L = self.baseline.get( 'scriptfrag', None )
        if L == None:
            L = []
            self.baseline[ 'scriptfrag' ] = L
        L.append( script_fragment )
    
    def setBaseline(self, key, value):
        """
        Add the given 'key'='value' pair to the baseline information.
        If both 'key' and 'value' are None, then all baseline information is
        removed (the default state).  If just 'value' is None, then 'key' is
        removed.
        """
        if key == None:
            if value == None:
                self.baseline.clear()
        else:
            if value == None:
                if key in self.baseline:
                    self.baseline.pop( key )
            else:
                self.baseline[ key ] = value

    def setSourceFiles(self, files):
        """
        A list of file names needed by this test (this is in addition to the
        file to be copied, linked, and baselined.)
        """
        self.src_files = [] + files

    def __copy_list(self, L):
        newL = None
        if L != None:
          newL = []
          uniq = {}
          for i in L:
            if not uniq.has_key(i):
              newL.append(i)
              uniq[i] = None
        return newL
    
    def __copy_dictionary(self, D):
        newD = None
        if D != None:
          newD = {}
          for (n,v) in D.items():
            newD[n] = v
        return newD
    
    def makeParent(self):
        """
        Creates a TestSpec instance and copies all data members of this test
        except the parameters.  The new test instance is returned.
        """
        ts = TestSpec( self.name, self.rootpath, self.filepath )
        ts.origin = self.origin + ["copy"]
        ts.form = self.__copy_dictionary( self.form )
        ts.keywords = self.__copy_list(self.keywords)
        ts.setParameters({})  # skip ts.params
        ts.analyze = self.__copy_dictionary( self.analyze )
        ts.timeout = self.timeout
        ts.execL = self.__copy_list(self.execL)
        ts.lnfiles = self.__copy_list(self.lnfiles)
        ts.cpfiles = self.__copy_list(self.cpfiles)
        ts.baseline = self.__copy_dictionary(self.baseline)
        ts.attrs = self.__copy_dictionary(self.attrs)
        return ts

for c in varname_chars_list:
  TestSpec.varname_chars[c] = None
