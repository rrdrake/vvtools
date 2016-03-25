#!/usr/bin/env python

import os, sys
import string

import xmlwrapper
import TestSpec
import TestExec
import TestSpecCreator
import CommonSpec

class TestList:
    """
    Stores a set of TestSpec objects.  Has utilities to read/write to a text
    file and to read from a test XML file.
    """
    
    version = '27'
    
    def __init__(self, ufilter=None):
        
        self.write_version = TestList.version
        self.filed = {}  # TestSpec xdir -> TestSpec object
        self.scand = {}  # TestSpec xdir -> TestSpec object
        self.active = {}  # TestSpec xdir -> TestSpec object
        self.xtlist = {}  # np -> list of TestExec objects
        
        self.ufilter = ufilter
        
        self.xmldocreader = None
    
    def stringFileWrite(self, filename):
        """
        Writes the tests in this container to the given filename.  All tests
        are written, even those that were not executed (were filtered out).
        """
        f = self.openFileForWrite(filename)
        for t in self.filed.values():
          f.write( TestSpecCreator.toString(t) + os.linesep )
        for t in self.scand.values():
          f.write( TestSpecCreator.toString(t) + os.linesep )
        f.close()
    
    def pipelineFileWrite(self, filename, qidL):
        """
        Write a file out as a placeholder for pipelining. It saves the
        pipeline queue id list so stringFileRead will pick up all the files.
        """
        fp = open( filename, 'w' )
        s = '\n### PipeLine'
        for qid in qidL:
          s = s + ' ' + str(qid)
        fp.write( s + '\n' )
        fp.close()
    
    def openFileForWrite(self, filename):
        """
        Opens and writes the file header.
        """
        filename = os.path.normpath(filename)
        fp = open(filename, 'w')
        fp.write("\n# Version " + TestList.version + "\n\n")
        return fp
    
    def readFileLines(self, filename):
        """
        Opens the file name and reads and returns its test lines.
        """
        fp = open(filename, 'r')
        
        # read the header, if any
        
        self.write_version = 0
        while 1:
          line = fp.readline()
          if line:
            line = string.strip(line)
            if line[0:10] == "# Version ":
              # use the version for backward compatibility logic
              self.write_version = int( string.strip(line[10:] ) )
              line = fp.readline()
              break
            elif line[0:13] == "### PipeLine ":
              fp.close()
              lineL = []
              wv = self.write_version
              for qid in string.split(line[13:]):
                f = filename + '.' + qid
                if os.path.exists(f):
                  lineL.extend( self.readFileLines(f) )
                  wv = max( wv, self.write_version )
              self.write_version = wv
              return lineL
            elif line and line[0] != '#':
              break
        
        # collect all the test lines in the file
        
        lineL = []
        while line:
          line = string.strip(line)
          if line and line[0] != "#":
            lineL.append( line )
          line = fp.readline()
        
        fp.close()
        
        return lineL
    
    def readFile(self, filename):
        """
        Read test list from a file.  Existing TestSpec objects have their
        attributes overwritten, but new TestSpec objects are not created.
        """
        lineL = self.readFileLines(filename)
        
        if len(lineL) > 0 and self.write_version < 12:
          print "*** error: cannot read version " + \
                       str(self.write_version) + \
                " test results files with this version of the test harness"
          print "    (or maybe the file is corrupt: " + filename + ")"
          sys.exit(1)
        
        # record all the test lines in the file
        
        for line in lineL:
          try:
            t = TestSpecCreator.fromString(line)
          except TestSpecCreator.TestSpecError, e:
            print "WARNING: reading file", filename, "string", line + ":", e
          else:
            xdir = t.getExecuteDirectory()
            t2 = self.scand.get( xdir, None )
            if t2 != None:
              for k,v in t.getAttrs().items():
                t2.setAttr(k,v)
            else:
              self.filed[xdir] = t
    
    def loadTests(self, filter_dir=None, analyze_only=0 ):
        """
        """
        if self.xmldocreader == None:
          self.xmldocreader = xmlwrapper.XmlDocReader()
        
        self.active = {}
        
        subdir = None
        if filter_dir != None:
          subdir = os.path.normpath( filter_dir )
          if subdir == '' or subdir == '.':
            subdir = None
        
        for xdir,t in self.scand.items():
          if self._apply_filters( xdir, t, subdir, analyze_only ):
            self.active[ xdir ] = t
        
        for xdir,t in self.filed.items():
          if self._apply_filters( xdir, t, subdir, analyze_only ):
            doc = self.xmldocreader.readDoc( t.getFilename() )
            keep = TestSpecCreator.refreshTest( t, doc,
                                                t.getParameters(),
                                                self.ufilter )
            
            del self.filed[xdir]
            self.scand[xdir] = t
            if keep:
              self.active[ xdir ] = t
    
    def _apply_filters(self, xdir, tspec, subdir, analyze_only):
        """
        """
        if self.ufilter.getAttr('include_all',0):
          return 1
        
        kwL = tspec.getResultsKeywords() + tspec.getKeywords()
        if not self.ufilter.satisfies_keywords( kwL ):
          return 0
        
        if subdir != None and subdir != xdir and not is_subdir( subdir, xdir ):
          return 0
        
        # want child tests to run with the "analyze only" option ?
        # if yes, then comment this out; if no, then uncomment it
        #if analyze_only and tspec.getParent() != None:
        #  return 0
        
        if not self.ufilter.evaluate_parameters( tspec.getParameters() ):
          return 0
        
        return 1
    
    def scanDirectory(self, base_directory, force_params=None):
        """
        Recursively scans for test XML files starting at 'base_directory'.
        If 'force_params' is not None, it must be a dictionary mapping
        parameter names to a list of parameter values.  Any test that contains
        a parameter in this dictionary will take on the given values for that
        parameter.
        """
        if self.xmldocreader == None:
          self.xmldocreader = xmlwrapper.XmlDocReader()
        
        base_dir = os.path.normpath( os.path.abspath(base_directory) )
        os.path.walk( base_dir, self._scan_recurse, (base_dir,force_params) )
    
    def _scan_recurse(self, argtuple, d, files):
        """
        This function is given to os.path.walk to recursively scan a directory
        tree for test XML files.  The 'base_dir' is the directory originally
        sent to the os.path.walk function.
        """
        base_dir, force_params = argtuple
        
        d = os.path.normpath(d)
        
        if base_dir == d:
          reldir = '.'
        else:
          assert base_dir+os.sep == d[:len(base_dir)+1]
          reldir = d[len(base_dir)+1:]
        
        # scan all files with extension "xml"; soft links to directories seem
        # to be skipped by os.path.walk so special handling is done for them
        
        linkdirs = []
        skipL = []
        for f in files:
          if f.startswith("TestResults.") or f.startswith("Build_"):
            # avoid descending into build and TestResults directories
            skipL.append(f)
          else:
            rawfile = os.path.join(d,f)
            if os.path.splitext(f)[1] == '.xml' and os.path.isfile(rawfile):
              self.XMLread( base_dir, os.path.join(reldir, f), force_params )
            elif os.path.islink(rawfile) and os.path.isdir(rawfile):
              linkdirs.append(f)
        
        # TODO: should check that the soft linked directories do not
        #       point to a parent directory of any of the directories
        #       visited thus far (to avoid an infinite scan loop)
        #       - would have to use inodes or something because the actual
        #         path may be the softlinked path rather than the path
        #         obtained by following '..' all the way to root
        
        # take the soft linked directories out of the list just in case some
        # version of os.path.walk actually does recurse into them automatically
        for f in linkdirs:
          files.remove(f)
        
        for f in skipL:
          files.remove(f)
        
        # manually recurse into soft linked directories
        for f in linkdirs:
          os.path.walk( os.path.join(d,f), self._scan_recurse, argtuple )
    
    def XMLread(self, basepath, xmlfile, force_params):
        """
        Parses an XML file for test instances.  Attributes from existing
        tests will be absorbed.
        """
        assert basepath
        assert xmlfile
        assert os.path.isabs(basepath)
        assert not os.path.isabs(xmlfile)
        
        basepath = os.path.normpath(basepath)
        xmlfile  = os.path.normpath(xmlfile)
        
        assert xmlfile
        
        fname = os.path.join( basepath, xmlfile )
        
        try:
          doc = self.xmldocreader.readDoc(fname)
          testL = TestSpecCreator.createTestObjects( doc, basepath, xmlfile,
                                                     force_params,
                                                     self.ufilter )
        except xmlwrapper.XmlError, e:
          print "*** skipping file: " + str(e)
          testL = []
        except TestSpecCreator.TestSpecError, e:
          print "*** skipping file: " + fname + ": " + str(e)
          testL = []
        
        for t in testL:
          # absorb attributes of an existing test (if any) and add test
          xdir = t.getExecuteDirectory()
          tmp = self.filed.get( xdir, None )
          if tmp != None:
            for n,v in tmp.getAttrs().items():
              t.setAttr(n,v)
            del self.filed[xdir]
          tmp = self.scand.get( xdir, None )
          if tmp != None:
            for n,v in tmp.getAttrs().items():
              t.setAttr(n,v)
          self.scand[xdir] = t
    
    def addTest(self, t):
        """
        Add a test to the list.  Will overwrite an existing test.
        """
        xdir = t.getExecuteDirectory()
        self.scand[xdir] = t
        if self.filed.has_key(xdir):
          del self.filed[xdir]
    
    def createTestExecs(self, test_dir, platform, config ):
        """
        """
        d = os.path.join( config.get('toolsdir'), 'libvvtest' )
        c = config.get('configdir')
        xdb = CommonSpec.loadCommonSpec( d, c )
        
        self._createTextExecList()
        
        for xt in self.getTestExecList():
          xt.init( test_dir, platform, xdb, config )
    
    def _createTextExecList(self):
        """
        """
        self.xtlist = {}
        
        xtD = {}
        for t in self.active.values():
          
          assert self.scand.has_key( t.getExecuteDirectory() )
          
          xt = TestExec.TestExec(t)
          
          np = int( t.getParameters().get('np', 0) )
          if self.xtlist.has_key(np):
            self.xtlist[np].append(xt)
          else:
            self.xtlist[np] = [xt]
          
          xtD[ t.getExecuteDirectory() ] = xt
        
        # put tests with the "fast" keyword first in each list; this is to try
        # to avoid launching long running tests at the end of the sequence which
        # can add significantly to the total run time
        self.sortTestExecList()
        
        # add children tests to parent tests
        for xt in self.getTestExecList():
          pxdir = xt.atest.getParent()
          if pxdir != None:
            # this test has a parent; find the parent TestExec object
            pxt = xtD.get( pxdir, None )
            if pxt != None:
              pxt.addChild( xt )
    
    def sortTestExecList(self):
        """
        put tests with the "fast" keyword first in each TestExec list
        """
        for np,L in self.xtlist.items():
          newL = []
          longL = []
          for tx in L:
            if tx.atest.hasKeyword('fast'): newL.append(tx)
            else:                           longL.append(tx)
          newL.extend(longL)
          self.xtlist[np] = newL
    
    def numTestExec(self):
        """
        Total number of TestExec objects.
        """
        n = 0
        for np,L in self.xtlist.items():
          n += len(L)
        return n
    
    def getTestExecProcList(self):
        """
        Returns a list of integers; each integer is the number of processors
        needed by one or more tests in the TestExec list.
        """
        return self.xtlist.keys()
    
    def getTestExecList(self, numprocs=None):
        """
        If 'numprocs' is None, all TestExec objects are returned.  If 'numprocs'
        is not None, a list of TestExec objects is returned each of which need
        that number of processors to run.
        """
        L = []
        if numprocs == None:
          for txL in self.xtlist.values():
            L.extend( txL )
        else:
          L.extend( self.xtlist.get(numprocs,[]) )
        return L
    
    def popNonFastNonParentTestExec(self, platform):
        """
        next test of largest np available to the platform, does not have
        'fast' keyword, and is not a parent test
        """
        npL = self.xtlist.keys()
        npL.sort()
        npL.reverse()
        for np in npL:
          if platform.queryProcs(np):
            L = self.xtlist[np]
            for i in xrange(len(L)):
              tx = L[i]
              if not tx.atest.hasKeyword('fast') and not tx.isParent():
                del L[i]
                if len(L) == 0:
                  del self.xtlist[np]
                return tx
        return None
    
    def popNonParentTestExec(self, platform=None):
        """
        if 'platform' is None, return the next non-parent test
        else, next non-parent test of largest np available to the platform
        """
        npL = self.xtlist.keys()
        npL.sort()
        npL.reverse()
        for np in npL:
          if platform == None or platform.queryProcs(np):
            L = self.xtlist[np]
            for i in xrange(len(L)):
              tx = L[i]
              if not tx.isParent():
                del L[i]
                if len(L) == 0:
                  del self.xtlist[np]
                return tx
        return None
    
    def popTestExec(self):
        """
        return next test of largest np in the list
        """
        npL = self.xtlist.keys()
        npL.sort()
        npL.reverse()
        for np in npL:
          L = self.xtlist[np]
          for i in xrange(len(L)):
            tx = L[i]
            del L[i]
            if len(L) == 0:
              del self.xtlist[np]
            return tx
        return None


def is_subdir(parent_dir, subdir):
    """
    TODO: test for relative paths
    """
    lp = len(parent_dir)
    ls = len(subdir)
    if ls > lp and parent_dir + '/' == subdir[0:lp+1]:
      return subdir[lp+1:]
    return None
