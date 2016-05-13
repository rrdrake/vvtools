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
    
    def getParent(self):
        """
        Returns the execution directory of the parent of this test, or None
        if it has no parent.
        """
        return self.parent_xdir

    def getScriptForm(self):
        """
        Returns the run script form, such as ('script','shebang=/bin/sh').
        """
        return self.form

    def getKeywords(self, result_attrs=0):
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
        For parent tests, this returns a dict mapping parameter names to a
        list of parameter values.  Combined/zipped parameter name and values
        are separated by a comma, such as 'np,h' -> ['2,0.2','4,0.1'].
        """
        return self.paramD

    def getAnalyzeScript(self):
        """
        A script (as a string) to be run after all parameterized tests run.
        If no script is defined, then None is returned.
        """
        return self.analyze
    
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
    
    def getBaselineFiles(self):
        """
        Returns a list of pairs (test directory name, source directory name)
        of files to be copied from the testing directory to the source
        directory.
        """
        L = []
        for tst,src,script in self.baseline:
          if tst != None:
            assert src != None
            L.append( (tst,src) )
        return L
    
    def getBaselineFragments(self):
        """
        Returns a list of script fragments to be executed during baseling.
        Standard filters are used to decide whether each baseline fragment
        will be included in the list.
        """
        L = []
        for tst,src,script in self.baseline:
          if script != None:
            L.append( script )
        return L
    
    def getExecutionList(self):
        """
        Returns, in order, raw fragments and named execution fragments for
        the given platform.  Returns a list of tuples
          ( name, fragment, exit status, analyze flag )
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
    
    def __init__(self, name, rootpath, filepath):
        """
        A test object always needs a root path and file path, where the file
        path must be a relative path name.
        """
        assert not os.path.isabs(filepath)
        
        self.form = ()             # a tuple, such as ('script',)

        self.name = name
        self.rootpath = rootpath
        self.filepath = filepath
        
        self.parent_xdir = None    # if child, this is the parent execute dir
        
        self.keywords = []         # list of strings
        self.params = {}           # name string to value string
        self.analyze = None        # contents of an analyze script
        self.timeout = None        # timeout value in seconds (an integer)
        self.execL = []            # list of
                                   #   (name, fragment, exit status, analyze)
                                   # where name is None when the
                                   # fragment is a raw fragment, exit status
                                   # is any string, and analyze is yes or no
        self.lnfiles = []          # list of (src name, test name)
        self.cpfiles = []          # list of (src name, test name)
        self.baseline = []         # list of (test name, src name, script)
                                   # where both names OR script may be None
        self.src_files = []        # extra source files listed by the test
        self.attrs = {}            # maps name string to value string; the
                                   # allowed characters are restricted
        self.paramD = {}           # for parent tests, this maps parameter
                                   # names to a list of values
        
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
    
    ##########################################################
    
    # construction methods
    
    def setScriptForm(self, form_tuple):
        """
        """
        self.form = form_tuple

    def setParent(self, parent_xdir):
        """
        """
        self.parent_xdir = parent_xdir
    
    def setKeywords(self, keyword_list):
        """
        A list of strings.
        """
        self.keywords = [] + keyword_list
    
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
    
    def setParameterSet(self, paramD):
        """
        For parent tests, set the dict which maps parameter names to a
        list of parameter values (which is what generated the child
        tests prior to this).
        """
        self.paramD = {}
        self.paramD.update( paramD )
    
    def setAnalyze(self, analyze_text):
        """
        Set the analyze script.  Should be the contents of a script, or None.
        """
        assert analyze_text == None or type(analyze_text) == types.StringType
        self.analyze = analyze_text
    
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
        self.execL.append( (name, s, exit_status, "no") )
   
    def setLinkFiles(self, link_file_list):
        """
        Set the list of files to link from the test source directory to
        the testing directory.  Each item in the list is a pair:
           ( source name, test name )
        where the test name may be None.
        """
        self.lnfiles = []
        D = {}
        for src,tst in link_file_list:
          assert src and not os.path.isabs(src)
          assert tst == None or not os.path.isabs(tst)
          self.lnfiles.append( (src, tst) )
          D[ src ] = None
        
        # always include the test specification file
        src = os.path.basename( self.filepath )
        if src not in D:
            self.lnfiles.append( (src,None) )
    
    def setCopyFiles(self, copy_files_list):
        """
        Set the list of files to copy from the test source directory to
        the testing directory.  Each item in the list is a pair:
           ( source name, test name )
        where the test name may be None.
        """
        self.cpfiles = []
        for src,tst in copy_files_list:
          assert src and not os.path.isabs(src)
          assert tst == None or not os.path.isabs(tst)
          self.cpfiles.append( (src, tst) )
    
    def resetBaseline(self):
        """
        Clears the files to be baselined and script fragments for baselining.
        """
        self.baseline = []
    
    def addBaselineFile(self, test_dir_name, source_dir_name):
        """
        Add a file to be copied from the test directory to the source
        directory during baselining.
        """
        assert test_dir_name and source_dir_name
        self.baseline.append( (test_dir_name, source_dir_name, None) )
    
    def addBaselineFragment(self, script_fragment):
        """
        Add a script fragment to be executed during baselining.
        """
        self.baseline.append( (None, None, script_fragment) )
    
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
        ts.form = self.form
        ts.keywords = self.__copy_list(self.keywords)
        ts.setParameters({})  # skip ts.params
        ts.analyze = self.analyze
        ts.timeout = self.timeout
        ts.execL = self.__copy_list(self.execL)
        ts.lnfiles = self.__copy_list(self.lnfiles)
        ts.cpfiles = self.__copy_list(self.cpfiles)
        ts.baseline = self.__copy_list(self.baseline)
        ts.attrs = self.__copy_dictionary(self.attrs)
        return ts

for c in varname_chars_list:
  TestSpec.varname_chars[c] = None
