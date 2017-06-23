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
    
    version = '30'
    
    def __init__(self, ufilter=None):
        
        self.filename = None
        self.datestamp = None
        self.finish = None

        self.tspecs = {}  # TestSpec xdir -> TestSpec object
        self.active = {}  # TestSpec xdir -> TestSpec object

        self.xtlist = {}  # np -> list of TestExec objects
        self.started = {}  # TestSpec xdir -> TestExec object
        self.stopped = {}  # TestSpec xdir -> TestExec object
        
        self.ufilter = ufilter
    
    def stringFileWrite(self, filename, datestamp=None):
        """
        Writes the tests in this container to the given filename.  All tests
        are written, even those that were not executed (were filtered out).

        The given filename is recorded in this object and is used for
        subsequent write actions, such as AddIncludeFile() and writeFinished().

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

        for t in self.tspecs.values():
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
        Appends the current filename with the name and attributes of the given
        TestSpec object.
        """
        assert self.filename
        fp = open( self.filename, 'a' )
        fp.write( TestSpecCreator.toString( tspec ) + '\n' )
        fp.close()
    
    def writeFinished(self, datestamp=None):
        """
        Appends the current filename with a finish marker that contains the
        given 'datestamp', or the current date if that is None.
        """
        assert self.filename

        if datestamp == None:
          datestamp = time.time()
        
        fp = open( self.filename, 'a' )
        fp.write( '\n#VVT: Finish = ' + time.ctime( datestamp ) + '\n' )
        fp.close()

    def readFile(self, filename, count_entries=None):
        """
        Read test list from a file.  Existing TestSpec objects have their
        attributes overwritten, but new TestSpec objects are not created.

        If 'count_entries' is not None, it should be a dictionary.  This
        dictionary maps test execute directory to the number of times that
        test appears in 'filename'.

        If this object has not had its filename set, this function will
        set it.

        If this object does not already have a date stamp, then the stamp
        contained in 'filename' will be loaded and set.
        """
        if not self.filename:
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
            if count_entries != None:
              if xdir in count_entries: count_entries[xdir] += 1
              else:                     count_entries[xdir] = 1

            t2 = self.tspecs.get( xdir, None )
            if t2 == None:
                self.tspecs[xdir] = t
            else:
                # just overwrite the attributes of the previous test object
                for k,v in t.getAttrs().items():
                    t2.setAttr(k,v)
                t2.addOrigin( t.getOrigin()[-1] )

    def getDateStamp(self, default=None):
        """
        Return the date of the last stringFileWrite() or the date read in by
        the first readFile().  If neither of those were issued, the 'default'
        argument is returned.
        """
        if self.datestamp:
          return self.datestamp
        return default

    def getFinishDate(self, default=None):
        """
        Return the date on the finish mark as contained in the file and read
        in by readFile().  If no finish mark was found, 'default' is returned.
        """
        if self.finish:
          return self.finish
        return default

    def scanFile(self, filename):
        """
        Reads through the file and records the date stamp and finish date, but
        does not construct any tests.
        """
        self._read_file_lines( filename )

    def _read_file_lines(self, filename):
        """
        Opens the file name, reads the test lines, and returns the file
        format version and the test line list.
        """
        fp = open( filename, 'r' )
        
        # read the header, if any
        
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
            # only load the date stamp once
            if self.datestamp == None:
              L = line.split( '=', 1 )
              if len(L) == 2:
                tup = time.strptime( L[1].strip() )
                self.datestamp = time.mktime( tup )
          elif line.startswith( '#VVT: Finish' ):
            # if there are no tests in this file, the finish mark is
            # seen during the header read
            L = line.split( '=', 1 )
            if len(L) == 2:
              tup = time.strptime( L[1].strip() )
              self.finish = time.mktime( tup )
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
              # avoid changing datestamp and finish marks from included files
              dat = self.datestamp
              fin = self.finish
              v,inclL = self._read_file_lines(f)
              lineL.extend( inclL )
              self.finish = fin
              self.datestamp = dat
          elif line.startswith( '#VVT: Finish' ):
            L = line.split( '=', 1 )
            if len(L) == 2:
              tup = time.strptime( L[1].strip() )
              self.finish = time.mktime( tup )
          elif line and line[0] != "#":
            lineL.append( line )
          line = fp.readline()
        
        fp.close()
        
        return vers, lineL

    def getTests(self):
        """
        Returns, in a list, all tests either scanned or read from a file.
        """
        return self.tspecs.values()

    def loadAndFilter(self, maxprocs, filter_dir=None,
                            analyze_only=0, prune=False ):
        """
        Creates the active test list using the scanned tests and the tests
        read in from a test list file.  A subdirectory filter is applied and
        the filter given in the constructor.

        If 'prune' is true, then analyze tests are filtered out if they have
        inactive children that did not pass/diff in a previous run.

        Returns a list of (analyze test, child test) for analyze tests that
        were pruned.  The second item is the child that did not pass/diff.
        """
        self.active = {}

        subdir = None
        if filter_dir != None:
          subdir = os.path.normpath( filter_dir )
          if subdir == '' or subdir == '.':
            subdir = None

        # TODO: is it possible that the filter apply before refresh could
        #       miss a test that changed since last time and now should
        #       be included !!
        for xdir,t in self.tspecs.items():
            if self._apply_filters( xdir, t, subdir, analyze_only ):
                if 'file' in t.getOrigin():
                    self.active[ xdir ] = t
                else:
                    # read from test source, which double checks filtering
                    keep = TestSpecCreator.refreshTest( t, self.ufilter )
                    if keep:
                        self.active[ xdir ] = t

        pruneL = []
        cntmax = 0
        if prune:
            
            # remove analyze tests from the active set if they have inactive
            # children that have a bad result
            for xdir,t in self.tspecs.items():
                pxdir = t.getParent()
                # does this test have a parent and is this test inactive
                if pxdir != None and xdir not in self.active:
                    # is the parent active and does the child have a bad result
                    if pxdir in self.active and \
                          ( t.getAttr('state') != 'done' or \
                            t.getAttr('result') not in ['pass','diff'] ):
                        # remove the parent from the active set
                        pt = self.active.pop( pxdir )
                        pruneL.append( (pt,t) )

            # Remove tests that exceed the platform resources (num processors).
            # For execute/analyze, if an execute test exceeds the resources
            # then the entire test set is removed.
            rmD = {}
            cntmax = 0
            for xdir,t in self.active.items():
                np = int( t.getParameters().get( 'np', 1 ) )
                assert maxprocs != None
                if np > maxprocs:
                    rmD[xdir] = t
                    cntmax += 1
                    pxdir = t.getParent()
                    if pxdir != None:
                        rmD[pxdir] = None
            xdL = []
            if cntmax > 0:
                for xdir,t in self.active.items():
                    pxdir = t.getParent()
                    if ( xdir in rmD ) or  \
                       ( pxdir != None and pxdir in rmD ):
                        xdL.append( xdir )
            for xdir in xdL:
                self.active.pop( xdir )
            xdL = None
            rmD = None

        return pruneL, cntmax
    
    def _apply_filters(self, xdir, tspec, subdir, analyze_only):
        """
        """
        if self.ufilter.getAttr('include_all',0):
            return True
        
        kwL = tspec.getResultsKeywords() + tspec.getKeywords()
        if not self.ufilter.satisfies_keywords( kwL ):
            return False
        
        if subdir != None and subdir != xdir and not is_subdir( subdir, xdir ):
            return False
        
        # want child tests to run with the "analyze only" option ?
        # if yes, then comment this out; if no, then uncomment it
        #if analyze_only and tspec.getParent() != None:
        #  return 0
        
        if not self.ufilter.evaluate_parameters( tspec.getParameters() ):
            return False

        if not self.ufilter.getAttr( 'include_tdd', False ) and \
           tspec.hasAttr( 'TDD' ):
            return False
        
        return True

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

        # scan files with extension "xml" or "vvt"; soft links to directories
        # seem to be skipped by os.path.walk so special handling is performed

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
            # this new test is ignored if it was already read from source
            # (or a different test source but the same relative path from root)
            xdir = t.getExecuteDirectory()

            t2 = self.tspecs.get( xdir, None )
            if t2 == None:
                self.tspecs[xdir] = t
            elif 'file' in t2.getOrigin():
                # this new test is ignored because there is a previous test
                # (generated from a file) with the same execute directory
                pass
            else:
                # existing test was read from a test list file; use the new
                # test instance but take on the attributes from the previous
                for n,v in t2.getAttrs().items():
                    t.setAttr(n,v)
                self.tspecs[xdir] = t

    def addTest(self, t):
        """
        Add a test to the test spec list.  Will overwrite an existing test.
        """
        self.tspecs[ t.getExecuteDirectory() ] = t
    
    def createTestExecs(self, test_dir, platform, config, perms):
        """
        Creates the set of TestExec objects from the active test list.
        """
        d = os.path.join( config.get('toolsdir'), 'libvvtest' )
        c = config.get('configdir')
        xdb = CommonSpec.loadCommonSpec( d, c )
        
        self._createTestExecList( perms )
        
        for xt in self.getTestExecList():
          xt.init( test_dir, platform, xdb, config )
    
    def _createTestExecList(self, perms):
        """
        """
        self.xtlist = {}
        
        xtD = {}
        for t in self.active.values():

          assert 'file' in t.getOrigin()

          xt = TestExec.TestExec( t, perms )
          
          np = int( t.getParameters().get('np', 0) )
          if self.xtlist.has_key(np):
            self.xtlist[np].append(xt)
          else:
            self.xtlist[np] = [xt]
          
          xtD[ t.getExecuteDirectory() ] = xt
        
        # put tests with the "fast" keyword first in each list; this is to try
        # to avoid launching long running tests at the end of the sequence
        # which can add significantly to the total run time
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
    
    def popNext(self, platform):
        """
        Finds a test to execute.  Returns a TestExec object, or None if no
        test can run.  In this case, one of the following is true
        
            1. there are not enough free processors to run another test
            2. the only tests left are parent tests that cannot be run
               because one or more of their children did not pass or diff

        In the latter case, numRunning() will be zero.
        """
        npL = self.xtlist.keys()
        npL.sort()
        npL.reverse()

        # look for non-fast tests of highest num procs first
        tx = self._pop_next_test( npL, platform, 'fast' )
        if tx == None:
            # same search but fast is ok
            tx = self._pop_next_test( npL, platform )
            if tx == None and len(self.started) == 0:
                # search for tests that need more processors than platform has
                tx = self._pop_next_test( npL )

        if tx != None:
            self.started[ tx.atest.getExecuteDirectory() ] = tx

        return tx

    def popRemaining(self):
        """
        All remaining tests are removed from the run list and returned.
        """
        tL = []
        for np,L in self.xtlist.items():
            tL.extend( L )
            del L[:]
            self.xtlist.pop( np )
        return tL

    def getRunning(self):
        """
        Return the list of tests that are still running.
        """
        return self.started.values()

    def testDone(self, tx):
        """
        """
        xdir = tx.atest.getExecuteDirectory()
        self.AppendTestResult( tx.atest )
        self.started.pop( xdir )
        self.stopped[ xdir ] = tx

    def numActive(self):
        """
        Return the total number of active tests (the tests that are to be run).
        """
        return len(self.active)

    def numDone(self):
        """
        Return the number of tests that have been run.
        """
        return len(self.stopped)

    def numRunning(self):
        """
        Return the number of tests are currently running.
        """
        return len(self.started)

    def _pop_next_test(self, npL, platform=None, notkey=None):
        """
        """
        for np in npL:
            if platform == None or platform.queryProcs(np):
                tL = self.xtlist[np]
                N = len(tL)
                i = 0
                while i < N:
                    tx = tL[i]
                    if notkey == None or not tx.atest.hasKeyword(notkey):
                        if self._children_ok( tx ):
                            self._pop_test_exec( np, i )
                            return tx
                    i += 1
        return None

    def _children_ok(self, tx):
        """
        Returns True unless this test is a parent and one or more children
        tests did not pass or diff.
        """
        if tx.hasChildren():
            if tx.badChild() != None:
                return False
            for childtx in tx.getChildren():
                cxdir = childtx.atest.getExecuteDirectory()
                if cxdir not in self.stopped:
                    return False
        return True
    
    def _pop_test_exec(self, np, i):
        """
        """
        L = self.xtlist[np]
        del L[i]
        if len(L) == 0:
            self.xtlist.pop( np )


def is_subdir(parent_dir, subdir):
    """
    TODO: test for relative paths
    """
    lp = len(parent_dir)
    ls = len(subdir)
    if ls > lp and parent_dir + '/' == subdir[0:lp+1]:
      return subdir[lp+1:]
    return None
