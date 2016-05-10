#!/usr/bin/env python

import os, sys
import time

import TestSpec
import TestExec
import TestSpecCreator
import CommonSpec

class TestList:
    """
    Stores a set of TestSpec objects.  Has utilities to read/write to a text
    file and to read from a test XML file.
    """
    
    version = '29'
    
    def __init__(self, ufilter=None):
        
        self.filename = None
        self.datestamp = None

        self.filed = {}  # TestSpec xdir -> TestSpec object
        self.scand = {}  # TestSpec xdir -> TestSpec object
        self.active = {}  # TestSpec xdir -> TestSpec object
        self.xtlist = {}  # np -> list of TestExec objects
        
        self.ufilter = ufilter
    
    def stringFileWrite(self, filename, datestamp=None):
        """
        Writes the tests in this container to the given filename.  All tests
        are written, even those that were not executed (were filtered out).

        A date stamp is written to the file.  If 'datestamp' is None, then
        the current time is used.
        """
        self.filename = os.path.normpath( filename )

        d,b = os.path.split( self.filename )
        if d and d != '.':
          # allow that one directory level must be created
          if not os.path.exists(d):
            os.mkdir( d )
        
        fp = open( self.filename, 'w' )
        fp.write( "\n#VVT: Version = " + TestList.version + "\n" )

        if datestamp == None:
          datestamp = time.time()
        self.datestamp = datestamp
        fp.write( "#VVT: Date = " + time.ctime( datestamp ) + "\n\n" )
        
        for t in self.filed.values():
          fp.write( TestSpecCreator.toString(t) + os.linesep )
        
        for t in self.scand.values():
          fp.write( TestSpecCreator.toString(t) + os.linesep )
        
        fp.close()
    
    def AddIncludeFile(self, include_file):
        """
        Appends the file 'filename' with a marker that causes the
        _read_file_lines() method to also read the given file 'include_file'.
        """
        assert self.filename
        fp = open( self.filename, 'a' )
        fp.write( '\n# INCLUDE ' + include_file + '\n' )
        fp.close()
    
    def AppendTestResult(self, tspec):
        """
        Appends the given file with the name and attributes of the given
        TestSpec object.
        """
        assert self.filename
        fp = open( self.filename, 'a' )
        fp.write( TestSpecCreator.toString( tspec ) + '\n' )
        fp.close()
    
    def readFile(self, filename):
        """
        Read test list from a file.  Existing TestSpec objects have their
        attributes overwritten, but new TestSpec objects are not created.

        If this object does not already have a date stamp, then the stamp
        contained in 'filename' will be loaded and set.
        """
        self.filename = os.path.normpath( filename )

        vers,lineL = self._read_file_lines(filename)
        
        if len(lineL) > 0 and vers < 12:
          raise Exception( "invalid test list file format version, " + \
                           str( vers ) + '; corrupt file? ' + filename )
        
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

    def getDateStamp(self, default=None):
        """
        Return the date of the last stringFileWrite() or the date read in by
        the first readFile().  If neither of those were issued, the 'default'
        argument is returned.
        """
        if self.datestamp:
          return self.datestamp
        return default

    def _read_file_lines(self, filename):
        """
        Opens the file name, reads the test lines, and returns the file
        format version and the test line list.
        """
        fp = open( filename, 'r' )
        
        # read the header, if any
        
        self.datestamp = None
        vers = 0
        line = fp.readline()
        while line:
          line = line.strip()
          if line[0:10] == "# Version ":
            # TODO: an older format, remove after a few months [May 2016]
            vers = int( line[10:].strip() )
            line = fp.readline()
            break
          elif line.startswith( '#VVT: Version' ):
            L = line.split( '=', 1 )
            if len(L) == 2:
              vers = int( L[1].strip() )
          elif line.startswith( '#VVT: Date' ):
            if self.datestamp == None:
              # only load the date stamp once
              L = line.split( '=', 1 )
              if len(L) == 2:
                tup = time.strptime( L[1].strip() )
                self.datestamp = time.mktime( tup )
          elif line and line[0] != '#':
            break
          line = fp.readline()
        
        # collect all the test lines in the file
        
        lineL = []
        while line:
          line = line.strip()
          if line.startswith( "# INCLUDE " ):
            # read the contents of the included file name
            f = line[10:].strip()
            if not os.path.isabs(f):
              # a relative path is relative to the original file directory
              d = os.path.dirname( filename )
              f = os.path.join( d, f )
            if os.path.exists(f):
              v,inclL = self._read_file_lines(f)
              lineL.extend( inclL )
          elif line and line[0] != "#":
            lineL.append( line )
          line = fp.readline()
        
        fp.close()
        
        return vers, lineL
    
    def loadTests(self, filter_dir=None, analyze_only=0 ):
        """
        """
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
            keep = TestSpecCreator.refreshTest( t, self.ufilter )
            
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
    
    def getActiveTests(self, sorting=''):
        """
        Get a list of the active tests (after filtering).  If 'sorting' is
        not an empty string, it should be a set of characters that control the
        way the test sorting is performed.
                n : test name (the default)
                x : execution directory name
                t : test run time
                d : execution date
                s : test status (such as pass, fail, diff, etc)
                r : reverse the order
        """
        if not sorting:
            tL = self.active.values()
            tL.sort()
        else:
            tL = []
            for t in self.active.values():
                L = []
                for c in sorting:
                    if c == 'n':
                        L.append( t.getName() )
                    elif c == 'x':
                        L.append( t.getExecuteDirectory() )
                    elif c == 't':
                        tm = t.getAttr( 'xtime', t.getAttr( 'runtime', 0 ) )
                        L.append( tm )
                    elif c == 'd':
                        L.append( t.getAttr( 'xdate', 0 ) )
                    elif c == 's':
                        st = t.getAttr( 'state', 'notrun' )
                        if st == 'notrun':
                            L.append( st )
                        elif st == 'done':
                            L.append( t.getAttr( 'result', 'unknown' ) )
                        else:
                            L.append( 'notdone' )
                L.append( t )
                tL.append( L )
            tL.sort()
            if 'r' in sorting:
                tL.reverse()
            tL = [ L[-1] for L in tL ]

        return tL

    def scanDirectory(self, base_directory, force_params=None):
        """
        Recursively scans for test XML files starting at 'base_directory'.
        If 'force_params' is not None, it must be a dictionary mapping
        parameter names to a list of parameter values.  Any test that contains
        a parameter in this dictionary will take on the given values for that
        parameter.
        """
        bdir = os.path.normpath( os.path.abspath(base_directory) )
        os.path.walk( bdir, self._scan_recurse, (bdir,force_params) )
    
    def _scan_recurse(self, argtuple, d, files):
        """
        This function is given to os.path.walk to recursively scan a directory
        tree for test XML files.  The 'base_dir' is the directory originally
        sent to the os.path.walk function.
        """
        basedir, force_params = argtuple
        
        d = os.path.normpath(d)
        
        if basedir == d:
          reldir = '.'
        else:
          assert basedir+os.sep == d[:len(basedir)+1]
          reldir = d[len(basedir)+1:]
        
        # scan all files with extension "xml"; soft links to directories seem
        # to be skipped by os.path.walk so special handling is done for them
        
        linkdirs = []
        skipL = []
        for f in files:
          if f.startswith("TestResults.") or f.startswith("Build_"):
            # avoid descending into build and TestResults directories
            skipL.append(f)
          else:
            bn,ext = os.path.splitext(f)
            df = os.path.join(d,f)
            if os.path.isdir(df):
              if os.path.islink(df):
                linkdirs.append(f)
            elif bn and ext in ['.xml','.vvt']:
              self.readTestFile( basedir, os.path.join(reldir,f), force_params )
        
        # TODO: should check that the soft linked directories do not
        #       point to a parent directory of any of the directories
        #       visited thus far (to avoid an infinite scan loop)
        #       - would have to use os.path.realpath() or something because
        #         the actual path may be the softlinked path rather than the
        #         path obtained by following '..' all the way to root
        
        # take the soft linked directories out of the list just in case some
        # version of os.path.walk actually does recurse into them automatically
        for f in linkdirs:
          files.remove(f)
        
        for f in skipL:
          files.remove(f)
        
        # manually recurse into soft linked directories
        for f in linkdirs:
          os.path.walk( os.path.join(d,f), self._scan_recurse, argtuple )
    
    def readTestFile(self, basepath, relfile, force_params):
        """
        Initiates the parsing of a test file.  XML test descriptions may be
        skipped if they don't appear to be a test file.  Attributes from
        existing tests will be absorbed.
        """
        assert basepath
        assert relfile
        assert os.path.isabs( basepath )
        assert not os.path.isabs( relfile )
        
        basepath = os.path.normpath( basepath )
        relfile  = os.path.normpath( relfile )
        
        assert relfile
        
        try:
          testL = TestSpecCreator.createTestObjects(
                        basepath, relfile, force_params, self.ufilter )
        except TestSpecCreator.TestSpecError:
          print "*** skipping file " + os.path.join( basepath, relfile ) + \
                ": " + str( sys.exc_info()[1] )
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
    
    def createTestExecs(self, test_dir, platform, config, perms):
        """
        """
        d = os.path.join( config.get('toolsdir'), 'libvvtest' )
        c = config.get('configdir')
        xdb = CommonSpec.loadCommonSpec( d, c )
        
        self._createTextExecList( perms )
        
        for xt in self.getTestExecList():
          xt.init( test_dir, platform, xdb, config )
    
    def _createTextExecList(self, perms):
        """
        """
        self.xtlist = {}
        
        xtD = {}
        for t in self.active.values():
          
          assert self.scand.has_key( t.getExecuteDirectory() )
          
          xt = TestExec.TestExec( t, perms )
          
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
