#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import string
import time
import glob
import re


# this is the file name of source tree runtimes files
runtimes_filename = "runtimes"

# this is the file name of the multiplatform runtimes file
multiruntimes_filename = "timings"


usage_string = """
USAGE
    results.py help  [ merge | save | list | clean ]
    results.py merge [OPTIONS] [file1 file2 ...]
    results.py save  [OPTIONS] [file1 file2 ...]
    results.py list  [OPTIONS] <file>
    results.py clean [OPTIONS] <file>
    results.py report [OPTIONS] <file>

Run "results.py help" for an overview, or append "merge", "save", "list",
or "clean" for a help screen on each of those subcommands.
"""

overview_string = """
OVERVIEW

This results.py file is imported into the test harness code to save the
results of running tests into a simple text file, usually named "results.*".
Using results.py as a script, these text files can then be combined/merged
into a single timings file that the test harness can use to determine the run
times of each test, usually named "timings".  Also, test results can be
written into files within the test source tree, usually named "runtimes",
which the test harness can use to determine approximate test run times when
the "timings" file is not available.  The "runtimes" files are also used to
determine the path to each test relative to the test root (this relative
directory is critical to unique test identification).

The three file formats are:

    results : this format is used by the test harness to save the test
              results for an execution of tests on some platform and compiler
    timings : this format is a merged form of test results files; it is read
              by the test harness during execution to determine the test run
              times
    runtimes : this format is written into the test source tree and committed
               to the repository to provide the test harness approximate
               run times when the timings file is unavailable; it is also used
               to get a relative directory path to each test from the test
               root for unique identification

The basic workflow is to use the test harness to create results files, then
use "results.py merge" to merge one or more of the results files into the
timings file. As a release step, use "results.py save" to write approximate
run times into the test source tree.
"""

merge_help = """
results.py merge [-x | -w] [-d <age>] [-g <glob pattern>] [file1 file2 ...]

Merges test results from the given results file(s) into the 'timings'
file located in the current working directory.  If a timings file does not
exist, one will be created.  Only those tests that passed, diffed or timed
out are merged. Also, by default, the results for each test will be the
maximum of all the tests from the given files on the command line and from
the 'timings' file.

Results files to merge in are specified by listing the files on the command
line or using the -g option to specify a glob pattern.

    -d <number_of_days>
        Filter the results files to include only those that have a date
        stamp not older than 'number_of_days', where the date stamp assumes
        the file name has the pattern "results.YYYY_MM_DD.*".  Also, tests
        in the timings file older than this will be overwritten with newer
        results (note that this behavior is overridden by -w or -x).

    -x  Select by execution date stamp.  This overwrites existing test
        results with the timing of the test that has the most recent
        execution date stamp.

    -w  Select by command line order.  This overwrites existing test results
        regardless of execution date stamp or timing value. The tests are
        overwritten in the order the results files are listed on the command
        line.

"""

save_help = """
results.py save [-w] [file1 file2 ...]

Saves (merges) the test results from the given file(s) into the test source
tree starting at the current working directory and recursing into
subdirectories.  Each runtimes file will have test results saved for tests
located in that directory or below.  The format of the file or files given
on the command line can be either results files or a timings file.

If a runtimes file does not exist in the current working directory, one is 
created, but only existing runtimes files in subdirectories are saved.

The destination test results format is not platform/compiler specific --
rather it is meant to be an approximation of the timings for the tests within
that directory.  Runtimes files also serve as a marker for determining the
directory relative to the test root.

Note that if the test root directory cannot be determined, then the current
directory is assumed to be the root and the new runtimes file marks it as
such.

    -w  Overwrite existing runtimes files rather than merging.
"""

list_help = """
results.py list  [OPTIONS]  <file>

Lists all the test results in the given file sorted by date.

-p    List the platform/compiler combinations present in the file rather
      than listing all the test results.
"""

clean_help = """
results.py clean [OPTIONS] <file>

Removes entries from the given file.  The file is modified in place.

-p <platform/compiler>
      Remove test results belonging to the given platform/compiler
      combination.
"""

report_help = """
results.py report [OPTIONS] [file1 ...]

Provides a summary of one or more test results files.  A summary of the
overall results on each platform/compiler is given, followed by details of
the history on each platform of tests that diff, fail, or timeout.  Tests
are only detailed if they diff/fail/timeout the last time they were run.

    --html <directory>
            output report as two static html files, dash.html & testrun.html
    -d <days back>
            examine results files back this many days; default is 15 days
    -D <days back>
            only itemize tests that fail/diff if they ran this many days ago;
            default is 7 days
    -r <integer>
            if the number of tests that fail/diff in a single test results
            file are greater than this value, then don't itemize each test
            from that test execution; default is 25 tests
    -g <shell glob pattern>
            use this file glob pattern to specify files to read; may be used
            with non-option files, and may be repeated
    -G <shell glob pattern>
            same as -g but for these files, do not detail the tests
    -p <platform>, --plat <platform>
            restrict the results files to this platform; may be repeated
    -P <platform>
            exclude results files with this platform name
    -o <option>
            restrict results files to ones with this option; may be repeated
    -O <option>
            exclude results files to ones without this option; may be repeated
    -t <tag> restrict results files to this tag
    -T <tag> exclude results files with this tag
"""

def results_main():
    """
    """
    if len(sys.argv) < 2:
        print3( '*** error: no arguments given' )
        print3( usage_string.strip() )
        sys.exit(1)
    elif sys.argv[1] == 'help' : help_main ( sys.argv[1:] )
    elif sys.argv[1] == 'merge': merge_main( sys.argv[1:] )
    elif sys.argv[1] == 'save' : save_main ( sys.argv[1:] )
    elif sys.argv[1] == 'list' : list_main ( sys.argv[1:] )
    elif sys.argv[1] == 'clean': clean_main( sys.argv[1:] )
    elif sys.argv[1] == 'report': report_main( sys.argv[1:] )
    else:
        print3( '*** error: unknown subcommand:', sys.argv[1] )
        print3( usage_string.strip() )
        sys.exit(1)


def help_main( argv ):
    """
    """
    if len(argv) == 1:
      print3( usage_string.strip() )
      print3( )
      print3( overview_string.strip() )
    elif argv[1] == 'merge':
      print3( merge_help.strip() )
    elif argv[1] == 'save':
      print3( save_help.strip() )
    elif argv[1] == 'list':
      print3( list_help.strip() )
    elif argv[1] == 'clean':
      print3( clean_help.strip() )
    elif argv[1] == 'report':
      print3( report_help.strip() )
    else:
      print3( usage_string.strip() )


def merge_main( argv ):
    """
    """
    import getopt
    try:
        optL,argL = getopt.getopt( argv[1:], "xwd:o:O:t:T:p:P:g:",
                                             longopts=['plat='] )
    except getopt.error:
        print3( "*** error:", sys.exc_info()[1] )
        sys.exit(1)
    
    optD = {}
    for n,v in optL:
        if n in ['-o','-O','-t','-T','-p','-P','--plat','-g']:
            optD[n] = optD.get( n, [] ) + [v]
        else:
            optD[n] = v
    
    process_option( optD, '-d', float, "positive" )

    if '-x' in optD and '-w' in optD:
        print3( "*** error: cannot use both -x and -w together" )
        sys.exit(1)
    
    warnings = multiplatform_merge( optD, argL )
    for s in warnings:
        print3( "*** Warning:", s )


def save_main( argv ):
    """
    """
    import getopt
    try:
        optL,argL = getopt.getopt( argv[1:], "w" )
    except getopt.error:
        print3( "*** error:", sys.exc_info()[1] )
        sys.exit(1)
    
    optD = {}
    for o,v in optL: optD[o] = v
    
    warnings = write_runtimes( optD, argL )
    for s in warnings:
        print3( "*** Warning:", s )


def list_main( argv ):
    """
    """
    import getopt
    
    try:
      optL,argL = getopt.getopt( sys.argv[2:], "p" )
    except getopt.error:
      sys.stderr.write( "*** results.py error: " + \
                        str(sys.exc_info()[1]) + os.linesep )
      sys.exit(1)
    
    optD = {}
    for o,v in optL:
      optD[o] = v
    
    if len(argL) != 1:
      sys.stderr.write( "*** results.py error: 'list' requires exactly " + \
                        "one file name" + os.linesep )
      sys.exit(1)
    results_listing( argL[0], optD )


def clean_main( argv ):
    """
    """
    import getopt
    
    try:
      optL,argL = getopt.getopt( sys.argv[2:], "p:" )
    except getopt.error:
      sys.stderr.write( "*** results.py error: " + \
                        str(sys.exc_info()[1]) + os.linesep )
      sys.exit(1)
    
    optD = {}
    for o,v in optL:
      optD[o] = v
    
    if len(argL) != 1:
      sys.stderr.write( "*** results.py error: 'clean' requires exactly " + \
                        "one file or directory name" + os.linesep )
      sys.exit(1)
    try:
      warnings = results_clean( argL[0], optD )
    except:
      sys.stderr.write( "*** Results clean failed: " + \
                        str(sys.exc_info()[1]) + os.linesep )
      sys.exit(1)
    for s in warnings:
      print3( "*** " + s )


def report_main( argv ):
    """
    """
    import getopt
    try:
        optL,argL = getopt.getopt( argv[1:], "d:D:r:o:O:t:T:p:P:g:G:",
                        longopts=['plat=','html=','config=','webloc='] )
    except getopt.error:
        print3( "*** error:", sys.exc_info()[1] )
        sys.exit(1)
    
    optD = {}
    for n,v in optL:
        if n in ['-o','-O','-t','-T','-p','-P','--plat','-g','-G']:
            optD[n] = optD.get( n, [] ) + [v]
        else:
            optD[n] = v
    
    process_option( optD, '-d', float, "positive" )
    process_option( optD, '-D', float, "positive" )
    process_option( optD, '-r', int, "positive" )

    if '--html' in optD:
        d = optD['--html']
        if not os.path.exists( d ):
            print3( '*** error: invalid --html directory: "'+d+'"' )
            sys.exit(1)

    warnings = report_generation( optD, argL )
    for s in warnings:
        print3( "*** Warning:", s )


#######################################################################

class MultiResults:
    
    def __init__(self, filename=None):
        """
        If the 'filename' is not None and it exists, it is read.
        """
        self.vers = 2
        
        # this dict comes from a results directory:
        #     dataD maps root-relative directory to testD
        #       testD maps test key to platD
        #         platD maps platform/compiler to attrD
        #           attrD maps attribute name to attribute value
        self.dataD = {}
        
        # 'rtimeD' comes from runtimes.txt files contained at the top of the
        # test directory, and 'rtime_roots' is a list of the top directory
        # names
        #     rtimeD maps root-relative directory to testD
        #       testD maps test key to runtime
        self.rtimeD = {}
        self.rtime_roots = []
        
        # maps test name to a list of test directories
        self.tmap = {}
        
        # cache of test file directory to root-relative directory
        self.dcache = {}
        
        if filename:
          self.readFile(filename)
    
    def dirList(self):
        """
        Return a sorted list of root-relative directories stored in the
        database.
        """
        dL = list( self.dataD.keys() )
        dL.sort()
        return dL
    
    def testList(self, rootrel):
        """
        For a given root-relative directory, return a sorted list of test
        keys contained in that directory.
        """
        tD = self.dataD.get( rootrel, {} )
        tL = list( tD.keys() )
        tL.sort()
        return tL
    
    def platformList(self, rootrel, testkey):
        """
        For a given root-relative directory and a test key, return the list
        of platform/compilers stored for the test.
        """
        tD = self.dataD.get( rootrel, {} )
        pD = tD.get( testkey, {} )
        pL = list( pD.keys() )
        pL.sort()
        return pL
    
    def testAttrs(self, rootrel, testkey, platcplr):
        """
        For a given root-relative directory, test key, and platform/compiler,
        return the test attribute dictionary.
        """
        tD = self.dataD.get( rootrel, {} )
        pD = tD.get( testkey, {} )
        aD = pD.get( platcplr, {} )
        return aD
    
    def lookupRuntime(self, testspec, platcplr):
        """
        Looks up and returns the test run time in the database of times.  If
        the test cannot be found, None is returned.
        
        Significant effort is spent to be flexible and allow for a variety of
        use cases.
        
          - If the entire test tree is checked out from version control, we
            want this routine to be fast.
          - If a subset of the test tree is checked out, we want the test
            times to still be found in the database.
          - If a test directory is tarred up and moved somewhere else (and so
            that the version control information is lost), we still want the
            test times to be found in the database.
        
        Some of the corner cases can be made to run faster and more robustly
        if special files are committed to the test tree in strategic locations.
        The file name is "rootrelative.txt" and contains the path to the
        directory it is located in relative to the top of the test tree. For
        example, the contents of this file in "Benchmarks/Regression/3D" might
        be
        
            # this file is used by the test harness and must contain the
            # path from the top of the test tree to the current directory
            Benchmarks/Regression/3D
        
        The content of the last line is used as the root-relative directory.
        Strategic places are directories that contain a lot of files and in
        directories that contain a lot of tests in subdirectories.
        """
        # Note: If performance is an issue, one idea could be to implement the
        #       following:
        #         - if a solid root-rel directory is determined, use that
        #           directory to compare future test directories to see if
        #           they are subdirectories
        #         - if a subsequent test directory is a subdirectory, then
        #           reconstruct the path from the established root-rel
        #           directory to the new test directory
        
        testkey = os.path.basename( testspec.getExecuteDirectory() )
        tdir = os.path.dirname( testspec.getFilepath() )
        
        rootrel = self.dcache.get( tdir, None )
        
        if rootrel == None:
          rootrel = self.getRootRelative( testkey )
          if rootrel == None:
            rootrel = _file_rootrel( tdir )
            if rootrel == None:
              rootrel = _svn_rootrel( tdir )
              if rootrel == None:
                rootrel = _direct_rootrel( tdir )
          if rootrel == None:
            # mark this directory so we don't waste time trying again
            rootrel = ''
          else:
            assert rootrel and not os.path.isabs(rootrel)
            rootd = os.path.normpath(rootrel).split( os.sep )[0]
            if rootd not in self.rtime_roots:
              self._load_runtimes( tdir, rootrel )
              self.rtime_roots.append( rootd )
          self.dcache[tdir] = rootrel
        
        if rootrel != '':
          testD = self.dataD.get( rootrel, None )
          if testD == None:
            # assume no test info available
            return None
          t = self._get_time( testD, testkey, platcplr )
          if t != None:
            return t
          # look for tests with the same base name and compute max
          s = testspec.getName() + '.'
          n = len(s)
          for k in testD.keys():
            if k[:n] == s:
              t2 = self._get_time( testD, k, platcplr )
              if t == None: t = t2
              else:         t = max( t, t2 )
          return t
        
        dL = self.tmap.get( testkey, None )
        if dL != None:
          # take the max over each matching test
          t = None
          for d in dL:
            testD = self.dataD[d]
            t2 = self._get_time( testD, testkey, platcplr )
            if t2 != None:
              if t == None: t = t2
              else:         t = max( t, t2 )
          return t
        
        return None
    
    def getTime(self, rootrel, testkey, platcplr):
        """
        Get the execution time of the given test.  If the test is not in the
        database, return None.
        """
        aD = self.testAttrs( rootrel, testkey, platcplr )
        t = aD.get( 'xtime', None )
        if t != None:
          return t, aD.get( 'result', None )
        return None,None
    
    def _get_time(self, testD, testkey, platcplr):
        """
        Given a test dict for a particular root-relative directory, the test
        key is used to lookup the run time.  If the test key does not exist in
        the directory, None is returned.  If the test key exists but the
        given platform/compiler combination does not, the max over each
        platform/compiler entries will be computed and returned.
        """
        pD = testD.get( testkey, None )
        if pD != None:
          # test key exists in this root-relative directory
          aD = pD.get( platcplr, None )
          if aD != None:
            # platform/compiler exists for this test
            return aD.get( 'xtime', None )
          tmax = None
          # take max of all times with the same platform but different compiler
          plat = platcplr.split('/')[0]
          for pc,aD in pD.items():
            if pc.split('/')[0] == plat:
              t = aD.get('xtime',None)
              if t != None:
                if tmax == None: tmax = t
                else: tmax = max( tmax, t )
          if tmax == None:
            # take max of all platform/compiler combinations for this test
            for aD in pD.values():
              t = aD.get('xtime',None)
              if t != None:
                if tmax == None: tmax = t
                else: tmax = max( tmax, t )
          return tmax
        
        # no entry for test key in the given directory dictionary
        return None
    
    def mergeTest(self, testspec, platcplr):
        """
        This method is to be used when merging in test results from a previous
        run.  It uses the root-relative path to the test and the test key
        (the test name plus any parameter names and values) as a unique
        identifier.
        
        The test root is the top of the test directory tree (in our case, the
        "Benchmarks" directory).  The root-relative path is the relative path
        from the root to the test specification file.  These paths are always
        as they exist under version control.
        
        This function should have a fairly high degree of confidence in
        determining the root relative directory so that the test results are
        not placed into the wrong directory.  It first tries to use the
        version control and if that fails, it looks for one of the root-
        relative files.  If both of these fail, the test is not merged in.
        
        For performance, a cache of computed root-relative directories is kept.
        """
        tdir = testspec.getDirectory()
        
        rootrel = self.dcache.get( tdir, None )
        
        if rootrel == None:
          rootrel = _svn_rootrel( tdir )
          if rootrel == None:
            rootrel = _file_rootrel( tdir )
          if rootrel == None:
            # mark this directory so we don't waste time trying again
            rootrel = ''
          self.dcache[tdir] = rootrel
        
        if rootrel != '':
          testkey = os.path.basename( testspec.getExecuteDirectory() )
          self.addTestName( rootrel, testkey, platcplr, testspec.getAttrs() )
    
    def addTestName(self, rootrel, testkey, platcplr, attrD):
        """
        The 'rootrel' is the relative path from the master root directory
        to the directory containing the test specification file.
        
        The 'testkey' is the test name together with any parameter names and
        values.
        
        If the test already exists, it is overwritten.
        """
        assert rootrel and rootrel != '.'
        
        tD = self.dataD.get( rootrel, None )
        if tD == None:
          tD = {}
          self.dataD[rootrel] = tD
        pD = tD.get( testkey, None )
        if pD == None:
          pD = {}
          tD[testkey] = pD
        aD = pD.get( platcplr, None )
        if aD == None:
          aD = {}
          pD[platcplr] = aD
        else:
          aD.clear()
        aD.update( attrD )
        
        L = self.tmap.get(testkey,None)
        if L == None:
          L = []
          self.tmap[testkey] = L
        if L.count(rootrel) == 0:
          L.append( rootrel )
    
    def writeFile(self, filename):
        """
        Writes/overwrites the given filename with the contents of this object.
        """
        fp = open( filename, 'w' )
        fp.write( 'FILE_VERSION=multi' + str(self.vers) + os.linesep )
        
        fp.write( os.linesep )
        dL = list( self.dataD.keys() )
        dL.sort()
        for d in dL:
          tD = self.dataD[d]
          tL = list( tD.keys() )
          tL.sort()
          for tn in tL:
            pD = tD[tn]
            pL = list( pD.keys() )
            pL.sort()
            for pc in pL:
              aD = pD[pc]
              s = d+'/'+tn+' '+pc + ' ' + make_attr_string(aD)
              fp.write( s + os.linesep )
        
        fp.close()
    
    def readFile(self, filename):
        """
        Loads/merges the contents of the given file name into this object.
        """
        fmt,vers,self.hdr,nskip = read_file_header( filename )
        
        if not fmt or fmt != "multi":
          raise Exception( "File format is not a multi-platform test " + \
                           "results format: " + filename )
        
        fp = open( filename, 'r' )
        n = 0
        d = None
        line = fp.readline()
        while line:
          if n < nskip:
            pass
          elif line.strip():
            if vers < 2:
              if line[:3] == "   ":
                L = line.split()
                tn = L[0]
                pc = L[1]
                aD = read_attrs( L[2:] )
                self.addTestName( d, tn, pc, aD )
              else:
                s = line.strip()
                if s: d = s
            else:
              L = line.split()
              d  = os.path.dirname( L[0] )
              tn = os.path.basename( L[0] )
              pc = L[1]
              aD = read_attrs( L[2:] )
              self.addTestName( d, tn, pc, aD )
          n += 1
          line = fp.readline()
        fp.close()
    
    def getRootRelative(self, testkey ):
        """
        If the test identifier is contained in the test-to-directory map and
        there is only one directory, then that directory is determined to be
        the root relative directory for the test.
        """
        dL = self.tmap.get( testkey, None )
        if dL != None and len(dL) == 1:
          return dL[0]
        return None
    
    def _load_runtimes(self, tdir, rootrel):
        """
        Subtract off the 'rootrel' trailing path from 'tdir' then look for a
        "runtimes.txt" file there.  If found, read it into self.rtimeD.
        """
        assert os.path.isabs(tdir) and not os.path.isabs(rootrel)
        while 1:
          d1,b1 = os.path.split( tdir )
          d2,b2 = os.path.split( rootrel )
          if b1 != b2:
            return
          if not d2 or d2 == '.':
            break
          tdir = d1
          rootrel = d2
        f = os.path.join( tdir, "runtimes.txt" )
        if os.path.exists(f):
          read_runtimes( self.rtimeD, f )


def _direct_rootrel(tdir):
    """
    Determines the root-relative directory of a test in 'tdir' by
    traversing up until the directory "Benchmarks" is found.
    """
    dirL = []
    while 1:
      d,b = os.path.split(tdir)
      if not b or d == tdir:
        break
      dirL.insert( 0, b )
      if b == "Benchmarks":
        break
      tdir = d
    if len(dirL) == 0 or dirL[0] != "Benchmarks":
      return None
    return '/'.join( dirL )

def _file_rootrel(tdir):
    """
    Determines the root-relative directory of a test in 'tdir' by looking
    for a file called "runtimes" in 'tdir'; if it exists and has the
    ROOT_RELATIVE variable set, then the root relative path for the test is
    returned.  If it does not find "runtimes" in 'tdir', it traverses up
    looking for a "runtimes" file with ROOT_RELATIVE set.
    """
    r = None
    pL = []
    for i in range(256):
      fn = os.path.join( tdir, runtimes_filename )
      if os.path.exists(fn):
        try:
          fmt,vers,hdr,n = read_file_header(fn)
          r = hdr['ROOT_RELATIVE']
        except:
          pass
        else:
          if len(pL) > 0:
            pL.insert( 0, r )
            r = os.path.join( *pL )
          break
      d,b = os.path.split( tdir )
      if not b or d == tdir:
        break
      pL.insert( 0, b )
      tdir = d
    return r


def _svn_rootrel(tdir):
    """
    Determines the root-relative directory of a test in 'tdir' by
    running svn and extracting the repository directory path, then
    applying hueristics on the path name.
    
    TODO: provide a mechanism to feed this routine the recognized
          repository roots instead of hard wiring it here
    """
    cdir = os.getcwd()
    try: os.chdir( tdir )
    except: return None
    
    # run svn info to get the relative URL and the repository URL
    try:
      import subprocess
    except:
      subprocess = None
    if subprocess:
      p = subprocess.Popen( 'svn info', shell=True,
              stdin=subprocess.PIPE, stdout=subprocess.PIPE,
              stderr=subprocess.STDOUT, close_fds=True )
      ip,fp = (p.stdin, p.stdout)
    else:
      ip,fp = os.popen4( 'svn info' )
    url = None
    relurl = None
    repo = None
    line = fp.readline()
    while line:
      if line[:4] == 'URL:':
        url = line.split()[-1]
      elif line[:13] == 'Relative URL:':
        relurl = line.split()[-1]
      elif line[:16] == 'Repository Root:':
        repo = line.split()[-1]
      line = fp.readline()
    ip.close() ; fp.close()
    os.chdir(cdir)
    if relurl == None:
      if url == None or repo == None:
        return None
      if len(url) < len(repo) or url[:len(repo)] != repo:
        return None
      relurl = '^'+url[len(repo):]
    
    # massage the relative URL to remove leading characters
    if relurl == '^':
      relurl = ''
    elif relurl[:2] == '^/':
      relurl = relurl[2:]
      if relurl:
        relurl = os.path.normpath( relurl )
        assert not os.path.isabs(relurl)
    
    if repo == None:
      # this shouldn't happen, but if it does, then assume alegra repo
      repo = "https://teamforge.sandia.gov/svn/repos/alegranevada"
    
    # remove leading URL specification; the 'X' trick is because normpath()
    # does not seem to reduce a leading '//' to just a single '/'
    repo = os.path.normpath( 'X'+repo.split(':',1)[-1] )[1:]
    
    if repo == "/teamforge.sandia.gov/svn/repos/alegranevada":
      dL = relurl.split('/')
      if len(dL) >= 2 and \
         dL[0] == 'trunk' and \
         dL[1] in ['Benchmarks','nevada','alegra']:
        return '/'.join( dL[1:] )
    
    return None


def determine_rootrel( testspec, dcache ):
    """
    Uses the directory containing the test specification file to determine
    the directory path from the root directory down to this test.  The path
    includes the top level root directory name, such as Benchmarks/Regression/
    3D/comprehensive.  Returns an empty string if the path could not be
    determined.  The 'dcache' argument is a dictionary used for caching test
    directories to rootrel directories.
    """
    tdir = testspec.getDirectory()
    
    rootrel = dcache.get( tdir, None )
    
    if rootrel == None:
      rootrel = _svn_rootrel( tdir )
      if rootrel == None:
        rootrel = _file_rootrel( tdir )
      if rootrel == None:
        # mark this directory so we don't waste time trying again
        rootrel = ''
      dcache[tdir] = rootrel
    
    return rootrel


########################################################################

class TestResults:
    
    def __init__(self, results_filename=None):
        
        self.vers = 3
        self.hdr = {}
        
        # dataD maps test rootrel directory to testD
        #   testD maps test name to attrD
        #     attrD maps attribute name to attribute value
        self.dataD = {}

        # keeps a running min & max date of all tests
        self.daterange = None

        self.dcache = {}

        if results_filename:
            if type(results_filename) == type(''):
                self.readResults( results_filename )
            else:
                # assume TestResults object, which mergeRuntimes() can handle
                self.mergeRuntimes( results_filename )
    
    def platform  (self): return self.hdr.get('PLATFORM',None)
    def compiler  (self): return self.hdr.get('COMPILER',None)
    def machine   (self): return self.hdr.get('MACHINE',None)
    def testdir   (self): return self.hdr.get('TEST_DIRECTORY',None)
    def inProgress(self): return 'IN_PROGRESS' in self.hdr
    
    def addTest(self, testspec):
        """
        Adds the test results for this test to the database.  If the root
        relative directory for the test can not be determined, then nothing
        is done.
        """
        rootrel = determine_rootrel( testspec, self.dcache )
        if rootrel:
          testkey = os.path.basename( testspec.getExecuteDirectory() )
          self.addTestName( rootrel, testkey, testspec.getAttrs() )
    
    def addTestName(self, rootrel, testkey, attrD):
        """
        The 'rootrel' is the test directory relative to the test root.  The
        'testkey' is the test name together with any parameter names and
        values.  If the test already exists, it is overwritten.
        """
        assert rootrel and rootrel != '.' and not os.path.isabs(rootrel)
        
        tD = self.dataD.get( rootrel, None )
        if tD == None:
            tD = {}
            self.dataD[rootrel] = tD
        aD = tD.get( testkey, None )
        if aD == None:
            aD = {}
            tD[testkey] = aD
        else:
            aD.clear()
        xd = attrD.get( 'xdate', 0 )
        if xd > 0:
            if self.daterange == None:
                self.daterange = [ xd, xd ]
            else:
                self.daterange[0] = min( self.daterange[0], xd )
                self.daterange[1] = max( self.daterange[1], xd )
        aD.update( attrD )
    
    def dirList(self):
        """
        Return a sorted list of root-relative directories stored in the
        database.
        """
        dL = list( self.dataD.keys() )
        dL.sort()
        return dL
    
    def testList(self, rootrel):
        """
        For a given root-relative directory, return a sorted list of test
        keys contained in that directory.
        """
        tD = self.dataD.get( rootrel, {} )
        tL = list( tD.keys() )
        tL.sort()
        return tL
    
    def testAttrs(self, rootrel, testkey):
        """
        For a given root-relative directory and a test key, return the test
        attribute dictionary.
        """
        tD = self.dataD.get( rootrel, {} )
        aD = tD.get( testkey, {} )
        return aD
    
    def getTime(self, rootrel, testkey):
        """
        Get the execution time of the given test.  If the test is not in the
        database, return None.
        """
        aD = self.testAttrs( rootrel, testkey )
        return aD.get( 'xtime', None )
    
    def dateRange(self):
        """
        Returns a pair (min date, max date) over all tests.  If there are no
        tests with a date defined, then this returns (None,None).
        """
        if self.daterange == None:
            return (None,None)
        return ( self.daterange[0], self.daterange[1] )

    def getCounts(self, tdd=False):
        """
        Counts the number of tests that pass, diff, fail, timeout, notrun,
        and unknown, and returns a tuple with the counts of each.  If 'tdd' is
        False, then tests marked TDD are excluded.  If 'tdd' is True, then
        only tests marked TDD are included.
        """
        np = nd = nf = nt = nr = unk = 0
        for d,tD in self.dataD.items():
            for tn,aD in tD.items():
                if ( tdd == False and 'TDD' not in aD ) or \
                   ( tdd == True and 'TDD' in aD ):
                    st = aD.get( 'state', '' )
                    if st == 'done':
                        rs = aD.get( 'result', '' )
                        if rs == 'pass': np += 1
                        elif rs == 'fail': nf += 1
                        elif rs == 'diff': nd += 1
                        elif rs == 'timeout': nt += 1
                        else: unk += 1
                    elif st == 'notrun': nr += 1
                    elif st == 'timeout': nt += 1
                    else: unk += 1
        return np,nd,nf,nt,nr,unk
    
    def getSummary(self):
        """
        Counts the number of tests that pass, fail, diff, timeout, etc, and
        returns a string with labels and the counts.
        """
        np, nd, nf, nt, nr, unk = self.getCounts()
        return 'pass='+str(np) + ' diff='+str(nd) + ' fail='+str(nf) + \
               ' timeout='+str(nt) + ' notrun='+str(nr) + ' ?='+str(unk)

    def collectResults(self, *args, **kwargs):
        """
        Collects all the test results into a dictionary mapping

            ( test directory, test name ) -> ( run date, result string )

        where the "run date" is zero if the test did not get run, and the
        "result string" is:

                state=<state>   : if the state matches one of the 'args'
                result=<result> : if the result matches one of the 'args'
                <empty string>  : if niether state nor result matches

        The dictionary is returned plus the number of tests that match the
        'args'.

        If 'matchlist=True' is given as a keyword argument, then the resulting
        dictionary will only contain test items if they match one of the 'args'.

        By default, tests marked TDD are ignored.  But if 'tdd=True' is given
        as a keyword argument, then only tests marked TDD are included.
        """
        getall = ( kwargs.get( 'matchlist', False ) == False )
        tdd = kwargs.get( 'tdd', False )

        nmatch = 0
        resD = {}
        for d,tD in self.dataD.items():
            for tn,aD in tD.items():
                
                if ( tdd and 'TDD' in aD ) or ( not tdd and 'TDD' not in aD ):
                    st = aD.get( 'state', '' )
                    rs = aD.get( 'result', '' )
                    if st in args:
                        res = 'state='+st
                        nmatch += 1
                    elif rs in args:
                        res = 'result='+rs
                        nmatch += 1
                    else:
                        res = ''

                    if getall or res:
                        xd = aD.get( 'xdate', 0 )
                        resD[ (d,tn) ] = ( xd, res )

        return resD,nmatch

    def writeResults(self, filename, plat_name, cplr_name,
                           mach_name, test_dir, inprogress=False):
        """
        Writes out test results for all tests, with a header that includes the
        directory in which the tests were run, the platform name, and the
        compiler name.
        """
        fp = open( filename, 'w' )
        
        fp.write( 'FILE_VERSION=results' + str(self.vers) + os.linesep )
        fp.write( 'PLATFORM=' + str(plat_name) + os.linesep )
        fp.write( 'COMPILER=' + str(cplr_name) + os.linesep )
        fp.write( 'MACHINE=' + str(mach_name) + os.linesep )
        fp.write( 'TEST_DIRECTORY=' + str(test_dir) + os.linesep )
        
        if inprogress:
            fp.write( 'IN_PROGRESS=True' + os.linesep )

        fp.write( os.linesep )
        dL = list( self.dataD.keys() )
        dL.sort()
        for d in dL:
          tD = self.dataD[d]
          tL = list( tD.keys() )
          tL.sort()
          for tn in tL:
            aD = tD[tn]
            s = d+'/'+tn + ' ' + make_attr_string( aD )
            fp.write( s + os.linesep )
        
        fp.close()
    
    def readResults(self, filename):
        """
        Loads the contents of the given file name into this object.
        A non-empty string is returned with an error message if the file
        format is unknown or not a test results format.
        """
        self.dataD = {}
        self.daterange = None
        self.dcache = {}
        
        fmt,vers,self.hdr,nskip = read_file_header( filename )
        
        if not fmt or fmt != 'results':
          raise Exception( "File format is not a single platform test " + \
                           "results format: " + filename )
        
        fp = open( filename, 'r' )
        n = 0
        d = None
        line = fp.readline()
        while line:
          if n < nskip:
            pass
          elif line.strip():
            if vers < 2:
              if line[:3] == "   ":
                L = line.split()
                tn = L[0]
                aD = read_attrs( L[1:] )
                self.addTestName( d, tn, aD )
              else:
                s = line.strip()
                if s: d = s
            else:
              L = line.split()
              d  = os.path.dirname( L[0] )
              tn = os.path.basename( L[0] )
              aD = read_attrs( L[1:] )
              self.addTestName( d, tn, aD )
          n += 1
          line = fp.readline()
        fp.close()
    
    def writeRuntimes(self, dirname, rootrel):
        """
        Writes all the tests that pass or diff in the runtimes format (which
        has a root-relative path in the header).  If 'rootrel' is None, the
        root relative path that is written is just the directory name of
        'dirname'.  This means that the resulting file would mark the
        top/root of a test source tree.
        """
        assert os.path.exists(dirname)
        assert os.path.isdir(dirname)
        
        filename = os.path.join( dirname, runtimes_filename )
        
        fp = open( filename, 'w' )
        fp.write( 'FILE_VERSION=results' + str(self.vers) + os.linesep )
        
        if rootrel == None:
            rootrel = os.path.basename( os.path.abspath(dirname) )
        fp.write( 'ROOT_RELATIVE=' + rootrel + os.linesep )
        rrL = rootrel.split('/')
        rrlen = len(rrL)
        
        fp.write( os.linesep )
        dL = list( self.dataD.keys() )
        dL.sort()
        for d in dL:
            # skip 'd' if it is not equal to or a subdirectory of rootrel
            if d.split('/')[:rrlen] == rrL:
                tD = self.dataD[d]
                tL = list( tD.keys() )
                tL.sort()
                for tn in tL:
                    aD = tD[tn]
                    # only write tests that pass or diff
                    if aD.get('result','') in ['pass','diff']:
                        s = d+'/'+tn + ' ' + make_attr_string( aD )
                        fp.write( s + os.linesep )
        
        fp.close()
    
    def mergeRuntimes(self, filename):
        """
        Reads the given results file and for each test therein, it overwrites
        the current test if the execution date is more recent.  If the test
        does not exist in this object yet, it is added.
        """
        if type(filename) == type(''):

            fmt,vers,hdr,nskip = read_file_header( filename )
            
            if not fmt or fmt != 'results':
              raise Exception( "File format is not a single platform test " + \
                               "results format: " + filename )
            
            fp = open( filename, 'r' )
            n = 0
            d = None
            line = fp.readline()
            while line:
              if n < nskip:
                pass
              elif line.strip():
                if vers < 2:
                  if line[:3] == "   ":
                    L = line.split()
                    tn = L[0]
                    aD = read_attrs( L[1:] )
                    dt1 = self.testAttrs( d, tn ).get( 'xdate', 0 )
                    dt2 = aD.get( 'xdate', 0 )
                    if dt2 >= dt1:
                      self.addTestName( d, tn, aD )
                  else:
                    s = line.strip()
                    if s: d = s
                else:
                  L = line.split()
                  d  = os.path.dirname( L[0] )
                  tn = os.path.basename( L[0] )
                  aD = read_attrs( L[1:] )
                  dt1 = self.testAttrs( d, tn ).get( 'xdate', 0 )
                  dt2 = aD.get( 'xdate', 0 )
                  if dt2 >= dt1:
                    self.addTestName( d, tn, aD )
              n += 1
              line = fp.readline()
            fp.close()

        else:
            # assume argument is a TestResults file
            tr = filename
            for d,tD in tr.dataD.items():
                for tn,aD in tD.items():
                    dt1 = self.testAttrs( d, tn ).get( 'xdate', 0 )
                    dt2 = aD.get( 'xdate', 0 )
                    if dt2 >= dt1:
                        self.addTestName( d, tn, aD )


def make_attr_string( attrD ):
    """
    Returns a string containing the important attributes.
    """
    s = ''
    v = attrD.get('xdate',None)
    if v != None and v > 0:
      s = s + ' ' + '_'.join( time.ctime(v).split() )
    v = attrD.get('xtime',None)
    if v != None:
      s = s + ' xtime=' + str(v)
    v = attrD.get('state',None)
    if v != None:
      s = s + ' ' + v
      if v == "done":
        rs = attrD.get('result',None)
        if rs != None:
          s = s + ' ' + rs
    if 'TDD' in attrD:
        s += ' TDD'
    return s.strip()


def read_attrs( attrL ):
    """
    Returns a dictionary containing the attributes given in 'attrL' list of
    strings, which is string.split() of make_attr_string().
    """
    attrD = {}
    i = 0
    if i < len(attrL) and \
       attrL[i][:3] in ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']:
        L = attrL[i].split('_')
        s = ' '.join(L)
        yr = int(L[-1])
        if yr < 2000:
            attrD['xdate'] = -1
        else:
            attrD['xdate'] = int( time.mktime( time.strptime(s) ) )
        i += 1
    if i < len(attrL) and attrL[i][:6] == "xtime=":
        attrD['xtime'] = int( attrL[i].split('=')[1] )
        i += 1
    if i < len(attrL) and attrL[i] in ['done','notrun','notdone']:
        st = attrL[i]
        attrD['state'] = st
        i += 1
        if st == "done" and i < len(attrL):
            attrD['result'] = attrL[i]
            i += 1
    if i < len(attrL) and attrL[i] == 'TDD':
        i += 1
        attrD['TDD'] = True
    return attrD


def read_file_header( filename ):
    """
    A header is:
    
      1. Any number of blank lines before the header
      2. Any number of KEY=value pairs (anything else is ignored)
      3. One or more blank lines stops the header
    
    Returns a tuple (format type, version integer, header dict, hdr lines),
    where the format type and version integer may be None if the header key
    "FILE_VERSION" was not found.  The header lines is the number of lines
    of header data in the file.
    """
    if type(filename) == type(''):
      fp = open( filename, 'r' )
    else:
      fp = filename  # assume a file object
    
    cnt = 0
    hdr = {}
    line = fp.readline()
    while line:
      line = line.strip()
      if line[:5] == 'TEST:':
        break
      elif line:
        cnt += 1
        L = line.split('=',1)
        if len(L) == 2 and L[0].strip():
          hdr[ L[0].strip() ] = L[1].strip()
      elif cnt > 0:
        break
      line = fp.readline()
    
    if type(filename) == type(''):
      fp.close()
    
    vers = hdr.get( 'FILE_VERSION', None )
    if vers:
      i = len(vers) - 1
      while i >= 0 and vers[i] in string.digits:
        i -= 1
      t = vers[:i+1]
      n = 0
      sn = vers[i+1:]
      if sn:
        n = int(sn)
      return t,n,hdr,cnt
    
    return None,None,hdr,cnt


def read_runtimes( rtimeD, filename ):
    """
    """
    pass


########################################################################


def multiplatform_merge( optD, fileL ):
    """
    Read results file(s) and merge test entries into the multi-platform
    timings file contained in the current working directory.
    
    The files in 'fileL' can be single platform or multi-platform formatted
    files.
    
    Only tests that "pass", "diff" or "timeout" will be merged in.
    """
    dcut = None
    if '-d' in optD:
        dcut = int( time.time() - optD['-d']*24*60*60 )
    wopt = '-w' in optD
    xopt = '-x' in optD

    process_files( optD, fileL, None )
    
    mr = MultiResults()
    if os.path.exists( multiruntimes_filename ):
        mr.readFile( multiruntimes_filename )
    
    warnL = []
    newtest = False
    for f in fileL:
        try:
            fmt,vers,hdr,nskip = read_file_header( f )
        except:
            warnL.append( "skipping results file: " + f + \
                          ", Exception = " + str(sys.exc_info()[1]) )
        else:
            
            if fmt and fmt == 'results':
                if merge_results_file( mr, f, warnL, dcut, xopt, wopt ):
                    newtest = True
            
            elif fmt and fmt == 'multi':
                if merge_multi_file( mr, f, warnL, dcut, xopt, wopt ):
                    newtest = True
            
            else:
                warnL.append( "skipping results source file due to " + \
                              "corrupt or unknown format: " + f )
    
    if newtest:
        mr.writeFile( multiruntimes_filename )
    
    return warnL


def merge_multi_file( multi, filename, warnL, dcut, xopt, wopt ):
    """
    """
    tr = MultiResults()
    try:
        tr.readFile( filename )
    except:
        warnL.append( "skipping multi-platform results file " + \
                      filename + ": Exception = " + str(sys.exc_info()[1]) )
        tr = None
    
    newtest = False
    if tr != None:
        for d in tr.dirList():
            for tn in tr.testList(d):
                for pc in tr.platformList( d, tn ):
                    xD = multi.testAttrs( d, tn, pc )
                    aD = tr.testAttrs( d, tn, pc )
                    if merge_check( xD, aD, dcut, xopt, wopt ):
                        newtest = True
                        multi.addTestName( d, tn, pc, aD )

    return newtest


def merge_results_file( multi, filename, warnL, dcut, xopt, wopt ):
    """
    """
    tr = TestResults()
    try:
        tr.readResults( filename )
    except:
        warnL.append( "skipping results file " + filename + \
                      ": Exception = " + str(sys.exc_info()[1]) )
        tr = None
    
    newtest = False
    if tr != None:
        plat = tr.platform()
        cplr = tr.compiler()
        if plat == None or cplr == None:
            warnL.append( "skipping results file "+filename + \
                          ": platform and/or compiler not defined" )
        else:
            pc = plat+'/'+cplr
            for d in tr.dirList():
                tL = tr.testList(d)
                for tn in tL:
                    xD = multi.testAttrs( d, tn, pc )
                    aD = tr.testAttrs( d, tn )
                    if merge_check( xD, aD, dcut, xopt, wopt ):
                        newtest = True
                        multi.addTestName( d, tn, pc, aD )

    return newtest


def merge_check( existD, newD, dcut, xopt, wopt ):
    """
    Return True if the new test should be merged in (based on the
    attribute dict of the existing and new test).
    """
    # new test must have a date, a runtime, and an acceptable result
    nd = newD.get('xdate',-1)
    nt = newD.get('xtime',-1)
    nr = newD.get('result',None)
    if nd > 0 and nt > 0 and nr in ['pass','diff','timeout']:
        
        xd = existD.get('xdate',-1)
        xt = existD.get('xtime',-1)
        xr = existD.get('result',None)

        if xd < 0 or xt < 0 or xr not in ['pass','diff','timeout']:
            return True
        
        if wopt:
            return True
        elif xopt:
            if nd >= xd:
                # new date is more recent, so take new test
                return True
        else:
            if xt < 0:
                return True
            if dcut != None:
                # with -d option, lower the precedence of old tests
                if xd < dcut and nd < dcut:
                    if nt > xt:
                        # both are old tests, so take max runtime
                        return True
                elif xd < dcut:
                    # existing test below cutoff, so take new test
                    return True
                elif nd < dcut:
                    pass  # new test below cutoff, so take old test
                else:
                    # both tests above cutoff, so take max runtime
                    if nt > xt:
                        return True
            elif nt > xt:
                # take test with maximum runtime
                return True
    
    return False


def parse_results_filename( filename ):
    """
    Assuming a file name of the form

        results.<date>.<platform>.<options>.<tag>
    
    this function returns a tuple

        ( date, platform, options, tag )

    where an entry will be None if the filename form did not have that data or
    if parsing for that entry failed.  The 'date' is seconds since epoch.
    The rest are strings.
    """
    f = os.path.basename( filename )
    L = [ s.strip() for s in f.split('.',4) ]

    ftime = None
    if len(L) >= 2:
        try:
            T = time.strptime( L[1], '%Y_%m_%d' )
            ftime = time.mktime( T )
        except:
            ftime = None
    
    platname = None
    if len(L) >= 3:
        platname = L[2]
    
    opts = None
    if len(L) >= 4:
        opts = L[3]
    
    tag = None
    if len(L) >= 5:
        tag = L[4]

    return ftime, platname, opts, tag


def date_round_down( tm ):
    """
    Given a date in seconds, this function rounds down to midnight of the
    date.  Returns a date in seconds.
    """
    s = time.strftime( "%Y %m %d", time.localtime( tm ) )
    T = time.strptime( s, "%Y %m %d" )
    return time.mktime( T )


def process_files( optD, fileL, fileG, **kwargs ):
    """
    Apply -g and -d options to the 'fileL' list, in place.  The order
    of 'fileL' is retained, but each glob list is sorted by ascending file
    date stamp.  If 'fileG' is not None, it will be filled with the files
    glob'ed using the -G option, if present.

    The -d option applies to files of form "results.YYYY_MM_DD.*".
    The -p option to form "results.YYYY_MM_DD.platform.*".
    The -o option to form "results.YYYY_MM_DD.platform.options.*", where the
    options are separated by a plus sign.
    The -t option to form "results.YYYY_MM_DD.platform.options.tag".

    If '-d' is not in 'optD' and 'default_d' is contained in 'kwargs', then
    that value is used for the -d option.
    """
    if '-g' in optD:
        gL = []
        for pat in optD['-g']:
            L = [ (os.path.getmtime(f),f) for f in glob.glob( pat ) ]
            L.sort()
            gL.extend( [ f for t,f in L ] )
        tmpL = gL + fileL
        del fileL[:]
        fileL.extend( tmpL )

    fLL = [ fileL ]
    if fileG != None and '-G' in optD:
        for pat in optD['-G']:
            L = [ (os.path.getmtime(f),f) for f in glob.glob( pat ) ]
            L.sort()
            fileG.extend( [ f for t,f in L ] )
        fLL.append( fileG )

    for fL in fLL:

        dval = optD.get( '-d', kwargs.get( 'default_d', None ) )
        if dval != None:
            dval = int(dval)
            # filter out results files that are too old
            cutoff = date_round_down( int( time.time() - dval*24*60*60 ) )
            newL = []
            for f in fL:
                ft,plat,opts,tag = parse_results_filename( f )
                if ft == None or ft >= cutoff:
                    newL.append( f )
            del fL[:]
            fL.extend( newL )

        platL = None
        if '-p' in optD or '--plat' in optD:
            platL = optD.get( '-p', [] ) + optD.get( '--plat', [] )
        xplatL = optD.get( '-P', None )
        if platL != None or xplatL != None:
            # include/exclude results files based on platform name
            newL = []
            for f in fL:
                ft,plat,opts,tag = parse_results_filename( f )
                if plat == None or \
                   ( platL == None or plat in platL ) and \
                   ( xplatL == None or plat not in xplatL ):
                    newL.append( f )
            del fL[:]
            fL.extend( newL )

        if '-o' in optD:
            # keep results files that are in the -o list
            optnL = '+'.join( optD['-o'] ).split('+')
            newL = []
            for f in fL:
                ft,plat,opts,tag = parse_results_filename( f )
                if opts != None:
                    # if at least one of the -o values from the command line
                    # is contained in the file name options, then keep the file
                    foptL = opts.split('+')
                    for op in optnL:
                        if op in foptL:
                            newL.append( f )
                            break
                else:
                    newL.append( f )  # don't apply filter to this file
            del fL[:]
            fL.extend( newL )

        if '-O' in optD:
            # exclude results files that are in the -O list
            optnL = '+'.join( optD['-O'] ).split('+')
            newL = []
            for f in fL:
                ft,plat,opts,tag = parse_results_filename( f )
                if opts != None:
                    # if at least one of the -O values from the command line is
                    # contained in the file name options, then exclude the file
                    foptL = opts.split('+')
                    keep = True
                    for op in optnL:
                        if op in foptL:
                            keep = False
                            break
                    if keep:
                        newL.append( f )
                else:
                    newL.append( f )  # don't apply filter to this file
            del fL[:]
            fL.extend( newL )

        tagL = optD.get( '-t', None )
        xtagL = optD.get( '-T', None )
        if tagL != None or xtagL != None:
            # include/exclude based on tag
            newL = []
            for f in fL:
                ft,plat,opts,tag = parse_results_filename( f )
                if tag == None or \
                   ( tagL == None or tag in tagL ) and \
                   ( xtagL == None or tag not in xtagL ):
                    newL.append( f )
            del fL[:]
            fL.extend( newL )


########################################################################

def write_runtimes( optD, fileL ):
    """
    Read test results from the list of files in 'fileL' and write to runtimes
    files in the test source tree.
    
    The list of files in 'fileL' can be either in multi-platform format or
    single platform test results format.
    
    Since each test may have multiple entries in the 'fileL' list, the run
    time of each entry is averaged, and the average is used as the run time for
    the test.
    
    If the test source root directory cannot be determined (by looking for
    an existing runtimes file), then the current working directory is assumed
    to be the root directory, and is marked as such by the new runtimes file.

    If a runtimes file does not exist in the current directory, one will be
    created.
    
    Existing runtimes files in subdirectories of the current directory are
    updated as well as the one in the current directory.
    
    New test entries in existing runtimes files may be added but none are
    removed.  If a test is contained in the 'fileL' list and in an existing
    runtimes file, then the entry is overwritten with the 'fileL' value in the
    runtimes file.
    """
    warnL = []
    
    cwd = os.getcwd()
    rootrel = _file_rootrel( cwd )
    if rootrel == None:
        # assume the current directory is the test tree root directory
        rootrel = os.path.basename( cwd )
    
    # for each (test dir, test key) pair, store a list of tests attr dicts
    testD = {}
    
    # read the tests from the source files; only save the tests that are
    # subdirectories of the rootrel (or equal to the rootrel)
    rrdirL = rootrel.split('/')
    rrlen = len(rrdirL)
    for srcf in fileL:
      try:
        fmt,vers,hdr,nskip = read_file_header( srcf )
      except:
        warnL.append( "Warning: skipping results file: " + srcf + \
                     ", Exception = " + str(sys.exc_info()[1]) )
      else:
        if fmt and fmt == 'results':
          src = TestResults()
          try:
            src.readResults(srcf)
          except:
            warnL.append( "Warning: skipping results file: " + srcf + \
                         ", Exception = " + str(sys.exc_info()[1]) )
          else:
            for d in src.dirList():
              if d.split('/')[:rrlen] == rrdirL:
                for tn in src.testList(d):
                  aD = src.testAttrs( d, tn )
                  if aD.get('result','') in ['pass','diff']:
                    k = (d,tn)
                    if k in testD: testD[k].append(aD)
                    else:          testD[k] = [aD]
        elif fmt and fmt == 'multi':
          src = MultiResults()
          try:
            src.readFile(srcf)
          except:
            warnL.append( "Warning: skipping results file: " + srcf + \
                         ", Exception = " + str(sys.exc_info()[1]) )
          else:
            for d in src.dirList():
              if d.split('/')[:rrlen] == rrdirL:
                for tn in src.testList(d):
                  for pc in src.platformList( d, tn ):
                    aD = src.testAttrs( d, tn, pc )
                    if aD.get('result','') in ['pass','diff']:
                      k = (d,tn)
                      if k in testD: testD[k].append(aD)
                      else:          testD[k] = [aD]
        else:
          warnL.append( "Warning: skipping results source file due to error: " + \
                       srcf + ", corrupt or unknown format" )
    
    # for each test, average the times found in the source files
    avgD = {}
    for k,aL in testD.items():
      d,tn = k
      tsum = 0
      tnum = 0
      save_aD = None
      for aD in aL:
        t = aD.get( 'xtime', 0 )
        if t > 0:
          tsum += t
          tnum += 1
          # use the attributes of the test with the most recent date
          if 'xdate' in aD:
            if save_aD == None or save_aD['xdate'] < aD['xdate']:
              save_aD = aD
      if save_aD != None:
        t = int( tsum/tnum )
        save_aD['xtime'] = t
        avgD[k] = save_aD
    
    tr = TestResults()
    rtdirD = {}  # runtimes directory -> root relative path
    
    # read any existing runtimes files at or below the CWD
    def read_src_dir( trs, rtD, msgs, dirname ):
        rtf = os.path.join( dirname, runtimes_filename )
        if os.path.isfile(rtf):
            try:
                fmt,vers,hdr,nskip = read_file_header( rtf )
                rr = hdr.get( 'ROOT_RELATIVE', None )
                trs.mergeRuntimes(rtf)
            except:
                msgs.append( "Warning: skipping existing runtimes file due to " + \
                             "error: " + rtf + ", Exception = " + \
                             str(sys.exc_info()[1]) )
            else:
              if rr == None:
                  msgs.append( "Warning: skipping existing runtimes file " + \
                               "because it does not contain the ROOT_RELATIVE " + \
                               "specification: " + rtf )
              else:
                  rtD[dirname] = rr

    for root,dirs,files in os.walk( cwd ):
        read_src_dir( tr, rtdirD, warnL, root )

    if '-w' in optD:
      # the -w option means don't merge
      tr = TestResults()
    
    # merge in the tests with average timings
    for k,aD in avgD.items():
      d,tn = k
      tr.addTestName( d, tn, aD )
    
    # make sure top level is included then write out the runtimes files
    rtdirD[ cwd ] = rootrel
    for rtdir,rrel in rtdirD.items():
      tr.writeRuntimes( rtdir, rrel )
    
    return warnL


########################################################################

def results_listing( fname, optD ):
    """
    by default, lists the tests by date
    the -p option means list the platform/compilers referenced by at least one
    test
    """
    fmt,vers,hdr,nskip = read_file_header( fname )
    
    if fmt and fmt == 'results':
      src = TestResults()
      src.readResults(fname)
      
      if '-p' in optD:
        p = hdr.get( 'PLATFORM', '' )
        c = hdr.get( 'COMPILER', '' )
        if p or c:
          print3( p+'/'+c )
      
      else:
        tL = []
        for d in src.dirList():
          for tn in src.testList(d):
            aD = src.testAttrs(d,tn)
            if 'xdate' in aD:
              tL.append( ( aD['xdate'], tn, d, aD ) )
        tL.sort()
        tL.reverse()
        for xdate,tn,d,aD in tL:
          print3( make_attr_string(aD), d+'/'+tn )
    
    elif fmt and fmt == 'multi':
      src = MultiResults()
      src.readFile(fname)
      
      if '-p' in optD:
        pcD = {}
        for d in src.dirList():
          for tn in src.testList(d):
            for pc in src.platformList(d,tn):
              pcD[pc] = None
        pcL = list( pcD.keys() )
        pcL.sort()
        for pc in pcL:
          print3( pc )
      
      else:
        tL = []
        for d in src.dirList():
          for tn in src.testList(d):
            for pc in src.platformList(d,tn):
              aD = src.testAttrs(d,tn,pc)
              if 'xdate' in aD:
                tL.append( ( aD['xdate'], tn, d, pc, aD ) )
        tL.sort()
        tL.reverse()
        for xdate,tn,d,pc,aD in tL:
          print3( make_attr_string(aD), pc, d+'/'+tn )
    
    else:
      sys.stderr.write( "Cannot list due to unknown file format: " + \
                        fname + os.linesep )


########################################################################

def results_clean( path, optD ):
    """
    -p <plat/cplr> means remove tests associated with that platform/compiler
    """
    if not os.path.exists(path):
      raise Exception( "Path does not exist: " + path )
    
    msgL = []
    
    if os.path.isdir(path):
      # assume path to a test source tree so look for a runtimes file
      fname = os.path.join( path, runtimes_filename )
      if os.path.exists(fname):
        path = fname
      else:
        raise Exception( "Specified directory does not contain a " + \
                         "test source tree runtimes file: " + path )
    
    if '-p' not in optD:
      msgL.append( "Warning: nothing to do without the -p option " + \
                   "(currently)" )
    
    fmt,vers,hdr,nskip = read_file_header( path )
    if fmt and fmt == 'results':
      if '-p' in optD:
        msgL.append( "Warning: the -p option has no effect on results files" )
      else:
        pass
    elif fmt and fmt == 'multi':
      if '-p' in optD:
        xpc = optD['-p']
        mr = MultiResults()
        src = MultiResults()
        src.readFile(path)
        for d in src.dirList():
          for tn in src.testList(d):
            for pc in src.platformList(d,tn):
              if pc != xpc:
                aD = src.testAttrs( d, tn, pc )
                mr.addTestName( d, tn, pc, aD )
        mr.writeFile( path )
      else:
        pass
    else:
      raise Exception( "Unknown file format: " + path )
    
    return msgL


########################################################################

def report_generation( optD, fileL ):
    """
    The results files are assumed to take the form
    
        results.YYYY_MM_DD.<platform>.<options>.<tag>
    
    where <options> is a "+" separated list and the last period and <tag>
    may not be present.

            --plat <platform>
            -p <platform>   : include platform, multiple allowed
            -P <platform>   : exclude platform, multiple allowed
            -o <options>    : include option, multiple allowed
            -O <options>    : exclude option, multiple allowed
            -t <tag>        : include tag, multiple allowed
            -T <tag>        : exclude tag, multiple allowed

          $ results.py report -O dbg -O cxx11 -T dev results.*
    """
    warnL = []
    curtm = time.time()

    if '-D' in optD:
        showage = optD['-D']
    else:
        showage = 7
    if '-r' in optD:
        maxreport = optD['-r']
    else:
        maxreport = 25  # default to 25 tests
    
    if '--html' in optD:
        dohtml = True
    else:
        dohtml = False
    
    plug = get_results_plugin( optD )

    # this collects the files and applies filters
    fileG = []
    process_files( optD, fileL, fileG, default_d=15 )

    # read all the results files
    rmat = ResultsMatrix()
    for f in fileL:
        ftime,tr,rkey = read_results_file( f, warnL )
        if ftime != None:
            tr.detail_ok = True  # inject a boolean flag to do detailing
            rmat.add( ftime, tr, rkey )
    for f in fileG:
        ftime,tr,rkey = read_results_file( f, warnL )
        if ftime != None:
            tr.detail_ok = False  # inject a boolean flag to NOT do detailing
            rmat.add( ftime, tr, rkey )

    if len( rmat.testruns() ) == 0:
        print3( 'No results files to process (after filtering)' )
        return warnL
    
    # the DateMap object helps format the test results output
    if '-d' in optD:
        df = date_round_down( curtm-optD['-d']*24*60*60 )
        dmin = min( df, rmat.minFileDate() )
    else:
        dmin = rmat.minFileDate()
    dmax = max(  0, rmat.maxFileDate() )
    dmap = DateMap( dmin, dmax )

    # write out the summary for each platform/options/tag combination

    if not dohtml:
        print3( "A summary by platform/compiler is next." )
        print3( "vvtest run codes: s=started, r=ran and finished." )

    # these for html output
    primary = []
    secondary = []
    tdd = []
    runlist = []

    # If a test gets marked TDD, it will still show up in the test detail
    # section until all test results (all platform combinations) run the
    # test again.  To prevent this, we save all the tests that are marked
    # as TDD for the most recent test results of each platform combination.
    # Then later when the test detail is being produced, this dict is used
    # to exclude tests that are marked TDD by any platform combination.
    # The 'tddmarks' dict is just a union of the dicts coming back from
    # calling TestResults.collectResults(), which is
    #      ( test dir, test name ) -> ( run date, result string )
    tddmarks = {}

    keylen = 0
    redD = {}
    for rkey in rmat.testruns():
        
        # find max plat/cplr string length for below
        keylen = max( keylen, len(rkey) )

        loc = rmat.location(rkey)

        if not dohtml:
            print3()
            print3( rkey, '@', loc )
        
        rL = []
        for fdate,tr in rmat.resultsList( rkey ):
            if tr.inProgress(): rL.append( (fdate,'start') )
            else:               rL.append( (fdate,'ran') )
        hist = dmap.history(rL)

        fdate,tr,tr2,started = rmat.latestResults( rkey )
        
        if dohtml:
            if tr.detail_ok:
                primary.append( (rkey, tr.getCounts(), rL) )
            else:
                secondary.append( (rkey, tr.getCounts(), rL) )
            tdd.append( (rkey, tr.getCounts(tdd=True), rL) )
            D,nm = tr.collectResults( tdd=True )
            tddmarks.update( D )
            runlist.append( (rkey,fdate,tr) )
        else:
            print3( '  ', dmap.legend() )
            print3( '  ', hist, '  ', tr.getSummary() )
            if not tr.detail_ok:
                s = '(tests for this platform/compiler are not detailed below)'
                print3( '  '+s )

        testD = {}  # (testdir,testname) -> (xdate,result)

        # don't itemize tests if they are still running, or if they
        # ran too long ago
        if not started and tr.detail_ok and \
           fdate > curtm - showage*24*60*60:
            
            resD,nmatch = tr.collectResults( 'fail', 'diff', 'timeout' )
            
            rD2 = None
            if tr2 != None:
                # get tests that timed out in the 2-nd most recent results
                rD2,nm2 = tr2.collectResults( 'timeout' )
            
            # do not report individual test results for a test
            # execution that has massive failures
            if nmatch <= maxreport:
                for k,T in resD.items():
                    xd,res = T
                    if xd > 0 and ( k not in testD or testD[k][0] < xd ):
                        if rD2 != None:
                            testD[k] = xd,res,rD2.get( k, None )
                        else:
                            testD[k] = xd,res,None

        for k,T in testD.items():
            xd,res,v2 = T
            if res:
                if res == 'result=timeout':
                    # only report timeouts if the 2-nd most recent test result
                    # was also a timeout
                    if v2 != None and v2[1] == 'result=timeout':
                        redD[k] = res
                else:
                    redD[k] = res

    if dohtml:

        print3( dashboard_preamble )
        if '--webloc' in optD:
            loc = optD['--webloc']
            print3( 'Go to the <a href="'+loc+ '">full report</a>.\n<br>\n' )
            loc = os.path.join( os.path.dirname( loc ), 'testrun.html' )
            print3( 'Also the <a href="'+loc+'">machine summaries</a>.\n<br>\n' )

        html_start_rollup( sys.stdout, dmap, "Production Rollup", 7 )
        for rkey,cnts,rL in primary:
            html_rollup_line( sys.stdout, plug, dmap, rkey, cnts, rL, 7 )
        html_end_rollup( sys.stdout )
        
        if len(secondary) > 0:
            html_start_rollup( sys.stdout, dmap, "Secondary Rollup", 7 )
            for rkey,cnts,rL in secondary:
                html_rollup_line( sys.stdout, plug, dmap, rkey, cnts, rL, 7 )
            html_end_rollup( sys.stdout )
        
        print3( '\n<br>\n<hr>\n' )

        fn = os.path.join( optD['--html'], 'dash.html' )
        dashfp = open( fn, 'w' )
        dashfp.write( dashboard_preamble )
        html_start_rollup( dashfp, dmap, "Production Rollup" )
        for rkey,cnts,rL in primary:
            html_rollup_line( dashfp, plug, dmap, rkey, cnts, rL )
        html_end_rollup( dashfp )
        
        if len(secondary) > 0:
            html_start_rollup( dashfp, dmap, "Secondary Rollup" )
            for rkey,cnts,rL in secondary:
                html_rollup_line( dashfp, plug, dmap, rkey, cnts, rL )
            html_end_rollup( dashfp )
        
        if len(tdd) > 0:
            html_start_rollup( dashfp, dmap, "TDD Rollup" )
            for rkey,cnts,rL in tdd:
                if sum(cnts) > 0:
                    html_rollup_line( dashfp, plug, dmap, rkey, cnts, rL )
            html_end_rollup( dashfp )
        
        dashfp.write( '\n<br>\n<hr>\n' )

        if len(redD) > 0:
            dashfp.write( \
                '<h2>Below are the tests that failed or diffed in ' + \
                'the most recent test sequence of at least one ' + \
                'Production Rollup platform combination.</h2>' + \
                '\n<br>\n<hr>\n' )
    
    if not dohtml:
        print3()
        print3( 'Tests that have diffed, failed, or timed out are next.' )
        print3( 'Result codes: p=pass, D=diff, F=fail, T=timeout, n=notrun' )
        print3()

    # for each test that fail/diff/timeout, collect and print the history of
    # the test on each plat/cplr and for each results date stamp

    detailed = {}
    tnum = 1

    keyfmt = "   %-"+str(keylen)+"s"
    redL = list( redD.keys() )
    redL.sort()
    for d,tn in redL:

        if (d,tn) in tddmarks:
            continue
        
        if dohtml:
            html_start_detail( dashfp, dmap, d+'/'+tn, tnum )
            detailed[ d+'/'+tn ] = tnum
            tnum += 1
        else:
            # print the path to the test and the date legend
            print3( d+'/'+tn )
            print3( keyfmt % ' ', dmap.legend() )

        res = redD[ (d,tn) ]
        for rkey in rmat.testruns( d, tn ):
            tests,location = rmat.resultsForTest( rkey, d, tn, result=res )
            rL = []
            for fd,aD in tests:
                if aD == None:
                    rL.append( (fd,'start') )
                else:
                    st = aD.get( 'state', '' )
                    rs = aD.get( 'result', '' )
                    if rs: rL.append( (fd,rs) )
                    else: rL.append( (fd,st) )

            if dohtml:
                html_detail_line( dashfp, dmap, rkey, rL )
            else:
                print3( keyfmt%rkey, dmap.history( rL ), location )


        if dohtml:
            dashfp.write( '\n</table>\n' )
        else:
            print3()
    
    if dohtml:
        dashfp.write( dashboard_close )
        dashfp.close()

        fn = os.path.join( optD['--html'], 'testrun.html' )
        trunfp = open( fn, 'w' )
        trunfp.write( dashboard_preamble )
        for rkey,fdate,tr in runlist:
            write_testrun_entry( trunfp, plug, rkey, fdate, tr, detailed )
        trunfp.write( dashboard_close )
        trunfp.close()
    
    return warnL


def get_results_plugin( optD ):
    """
    Looks for a config directory the same way vvtest does.  If a file called
    "results_plugin.py" exists there, it is imported and the module returned.
    """
    if '--config' in optD:
        cfg = os.path.abspath( optD['--config'] )
    else:
        d = os.getenv( 'VVTEST_CONFIGDIR' )
        if d == None:
            d = os.path.join( mydir, 'config' )
        cfg = os.path.abspath( d )
    if os.path.exists( os.path.join( d, 'results_plugin.py' ) ):
        sys.path.insert( 0, d )
        import results_plugin
        return results_plugin
    return None


def read_results_file( filename, warnL ):
    """
    Constructs a TestResults class and loads it with the contents of
    'filename', which is expected to be a results.<date>.* file.  Returns
    the file date, the TestResults object, and the results key.  If the read
    fails, then None,None,None is returned and the 'warnL' list is appended
    with the error message.
    """
    # parse the file name to get things like the date stamp
    ftime,plat,opts,tag = parse_results_filename( filename )
    
    try:
        assert ftime != None

        # try to read the file
        fmt,vers,hdr,nskip = read_file_header( filename )
        assert fmt == 'results', \
                'expected a "results" file format, not "'+str(fmt)+'"'
        tr = TestResults( filename )
        
        # the file header contains the platform & compiler names
        assert tr.platform() != None and tr.compiler() != None
    
    except:
        warnL.append( "skipping results file: " + filename + \
                                ", Exception = " + str(sys.exc_info()[1]) )
        return None,None,None
    
    results_key = plat
    if opts != None:
        results_key += '.'+opts
    if tag != None:
        results_key += '.'+tag

    return ftime,tr,results_key


class ResultsMatrix:
    """
    Helper class for collecting test results.  A matrix is stored whose rows
    are platform/compiler strings and columns are machine:directory strings.
    Each entry in the matrix is a list of (file date, TestResults object) and
    which is always kept sorted by file date.
    """

    def __init__(self):
        self.matrixD = {}
        self.daterange = None  # will be [ min date, max date ]

    def add(self, filedate, results, results_key):
        """
        Based on the 'results_key', this function determines the location in
        the matrix to append the results, and does the append.
        """
        if results_key not in self.matrixD:
            self.matrixD[results_key] = []
        
        row = self.matrixD[results_key]

        row.append( (filedate,results) )

        row.sort()  # kept sorted by increasing file date
        
        # for convenience, the track the date range of all test results files
        if self.daterange == None:
            self.daterange = [ filedate, filedate ]
        else:
            self.daterange[0] = min( self.daterange[0], filedate )
            self.daterange[1] = max( self.daterange[1], filedate )

    def minFileDate(self):
        if self.daterange != None: return self.daterange[0]
    def maxFileDate(self):
        if self.daterange != None: return self.daterange[1]

    def testruns(self, testdir=None, testname=None):
        """
        Return a sorted list of the test results keys.  That is, the rows in
        the matrix.  If 'testdir' and 'testname' are both non-None, then
        only results keys are included that have at least one test results
        object containing the specified test.
        """
        if testdir == None or testname == None:
            L = list( self.matrixD.keys() )
            L.sort()
        else:
            L = []
            for rkey,trL in self.matrixD.items():
                n = 0
                for fdate,tr in trL:
                    attrD = tr.testAttrs( testdir, testname )
                    n += len(attrD)
                if n > 0:
                    L.append( rkey )
            L.sort()

        return L

    def _get_platcplr(self, trL):
        """
        Given a row of the matrix, returns the platform and compiler names
        of the most recent test results object.  Ignores test results objects
        if either the platform name or compiler name is None or empty.
        """
        dupL = [] + trL
        dupL.reverse()

        for fdate,tr in dupL:
            p,c = tr.platform(), tr.compiler()
            if p and c:
                return p,c

        return None, None

    def location(self, platcplr):
        """
        For the given 'platcplr', return a sorted list of the
        machine:testdirectory name for most recent test results date.
        """
        row = self.matrixD[platcplr]

        tr = row[-1][1]
        mach,rdir = tr.machine(), tr.testdir()
        if mach == None: mach = '?'
        if rdir == None: rdir = '?'
        
        return mach+':'+rdir

    def resultsList(self, results_key):
        """
        Returns a list of (file date, results) pairs for the test results
        corresponding to 'results_key'.  The list is sorted by increasing date.
        """
        return [] + self.matrixD[results_key]

    def latestResults(self, results_key):
        """
        For the given test run key, finds the test results with the most
        recent date stamp, but that is not in progress.  Returns a tuple

            ( file date, TestResults, TestResults, started )

        where the first TestResults is the latest and the second TestResults
        is the second latest, and 'started' is True if the most recent test
        results are in progress.
        """
        L = [] + self.matrixD[results_key]
        L.reverse()
        started = L[0][1].inProgress()
        # pick the most recent and second most recent which is not in-progress
        frst = None
        scnd = None
        for fd,tr in L:
            if not tr.inProgress():
                if frst == None:
                    frst = ( fd, tr )
                elif scnd == None:
                    scnd = tr
                else:
                    break
        
        if frst != None:
            return frst[0], frst[1], scnd, started
        
        fd,tr = L[0]  # all are in progress? just choose most recent
        return fd,tr,None,started

    def resultsForTest(self, platcplr, testdir, testname, result=None):
        """
        For each entry in the 'platcplr' row, collect the attributes of the
        test containing the test ID 'testdir' plus 'testname'.  That is, all
        tests with the given ID are collected across each of the locations
        for the given platcplr.

        If 'result' is given, it must be a string "state=<state>" or
        "result=<result>" (as produced by TestResults.collectResults()).

        The collection is gathered as a list of (file date, test attributes)
        pairs (and sorted).  The 'test attributes' dictionary will be None
        if and only if a test results run was in progress on that date.

        Also computed is the location of the most recent execution of the test.

        The list and the location are returned.
        """
        D = {}
        maxloc = None
        for filedate,results in self.matrixD[platcplr]:
            
            mach,rdir = results.machine(), results.testdir()
            if mach == None: mach = '?'
            if rdir == None: rdir = '?'
            loc = mach+':'+rdir

            attrD = results.testAttrs( testdir, testname )
            if len(attrD) > 0:
                
                if 'xdate' not in attrD and results.inProgress():
                    if filedate not in D:
                        # mark the test on this date as in progress
                        D[filedate] = None
                
                else:
                    if filedate in D:
                        i = self._tie_break( D[filedate], attrD, result )
                        if i > 0:
                            D[filedate] = attrD  # prefer new test results
                    else:
                        D[filedate] = attrD

                    if maxloc == None:
                        maxloc = [ filedate, loc, attrD ]
                    elif filedate > maxloc[0]:
                        maxloc = [ filedate, loc, attrD ]
                    elif abs( filedate - maxloc[0] ) < 2:
                        # the test appears in more than one results file
                        # on the same file date, so try to break the tie
                        i = self._tie_break( maxloc[2], attrD, result )
                        if i > 0:
                            maxloc = [ filedate, loc, attrD ]
        
        L = list( D.items() )
        L.sort()

        if maxloc == None: loc = ''
        else:              loc = maxloc[1]
        
        return L,loc

    def _tie_break(self, attrs1, attrs2, result):
        """
        Given the result attributes from two different executions of the same
        test, this returns -1 if the first execution wins, 1 if the second
        execution wins, or zero if the tie could not be broken.  The 'result'
        argument is None or a result string produced from the
        TestResults.collectResults() method.
        """
        # None is used as an "in progress" mark; in this case, always
        # choose the other one
        if attrs1 == None:
            return 1
        elif attrs2 == None:
            return -1

        if result != None:
            # break tie using the preferred result
            if result.startswith( 'state=' ):
                rs = result.split( 'state=' )[1]
                r1 = attrs1.get( 'state', '' )
                r2 = attrs2.get( 'state', '' )
            else:
                assert result.startswith( 'result=' )
                rs = result.split( 'result=' )[1]
                r1 = attrs1.get( 'result', '' )
                r2 = attrs2.get( 'result', '' )
            if r1 == rs and r2 != rs:
                # only previous entry has preferred result
                return -1
            elif r2 == rs and r1 != rs:
                # only new entry has preferred result
                return 1

        d1 = attrs1.get( 'xdate', None )
        d2 = attrs2.get( 'xdate', None )
        if d2 == None:
            # new entry does not have an execution date
            return -1
        elif d1 == None or d2 > d1:
            # old entry does not have an execution date or new entry
            # executed more recently
            return 1

        # unable to break the tie
        return 0


class DateMap:
    """
    This is a helper class to format the test result status values, and a
    legend for the dates.
    """
    
    def __init__(self, mindate, maxdate ):
        """
        Construct with a date range.  All days in between are populated with
        a character to preserve spacing.
        """
        # initialize the list of days
        if mindate > maxdate:
            # date range not available; default to today
            self.dateL = [ DateInfoString( time.time() ) ]
        else:
            self.dateL = []
            d = mindate
            while not d > maxdate:
                day = DateInfoString( d )
                if day not in self.dateL:
                    self.dateL.append( day )
                d += 24*60*60
            day = DateInfoString( maxdate )
            if day not in self.dateL:
                self.dateL.append( day )

        # determine number of characters in first group (week)
        num1 = 0
        for day in self.dateL:
            doy,yr,dow,m,d = day.split()
            if num1 and dow == '1':
                break
            num1 += 1

        # compute the dates that start each week (or partial week)
        self.wkdateL = []
        n = 0
        for day in self.dateL:
            doy,yr,dow,m,d = day.split()
            if not n:
                self.wkdateL.append( '%-7s' % (m+'/'+d) )
            n += 1
            if dow == '0':
                n = 0
        
        # the first group is a little special; first undo the padding
        self.wkdateL[0] = self.wkdateL[0].strip()
        if len( self.wkdateL[0] ) < num1:
            # pad the first legend group on the right with spaces
            self.wkdateL[0] = ( '%-'+str(num1)+'s') % self.wkdateL[0]

    def getDateList(self, numdays=None):
        """
        Returns a list of strings of the dates in the range for the current
        report.  The strings are the output of the DateInfoString() function.

        If 'numdays' is not None, it limits the dates to this number of (most
        recent) days.
        """
        if numdays:
            return self.dateL[-numdays:]
        return [] + self.dateL

    def legend(self):
        return ' '.join( self.wkdateL )

    def history(self, resultL):
        """
        Given a list of (date,result) pairs, this function formats the
        history into a string and returns it.
        """
        # create a map of the date to the result character
        hist = {}
        for xd,rs in resultL:
            day = DateInfoString( xd )
            hist[ day ] = self._char( rs )

        # walk the full history range and accumulate the result characters
        # in order (if a test is absent on a given day, a period is used)
        cL = []
        s = ''
        for day in self.dateL:
            doy,yr,dow,m,d = day.split()
            if s and dow == '1':
                cL.append( s )
                s = ''
            s += hist.get( day, '.' )
        if s:
            cL.append( s )
        
        # may need to pad the first date group
        if len(cL[0]) < len(self.wkdateL[0]):
            fmt = '%'+str(len(self.wkdateL[0]))+'s'
            cL[0] = fmt % cL[0]
        
        return ' '.join( cL )


    def _char(self, result):
        """
        Translate the result string into a single character.
        """
        if result == 'pass': return 'p'
        if result == 'diff': return 'D'
        if result == 'fail': return 'F'
        if result == 'timeout': return 'T'
        if result == 'notrun': return 'n'
        if result == 'start': return 's'
        if result == 'ran': return 'r'
        return '?'

def DateInfoString( tm ):
    """
    Given a date in seconds, return a string that contains the day of the
    year, the year, the day of the week, the month, and the day of the month.
    These are white space separated.
    """
    return time.strftime( "%j %Y %w %m %d", time.localtime(tm) )


####################################################################

# this defines the beginning of an html file that "style" specifications
# that are used later in the tables
dashboard_preamble = '''
<!DOCTYPE html>
<html lang = "en-US">

  <head>
    <meta charset = "UTF-8">
    <title>Dashboard</title>
    <style>
      .thintable {
        border: 1px solid black;
        border-collapse: collapse;
      }

      .grptr {
        border-bottom: 4px solid black
      }
      .midtr {
        border-bottom: 1px solid black
      }

      .grpth {
        border-left: 4px solid black;
      }
      .midth {
        border-style: none;
        border-left: 1px solid black;
        text-align: center;
      }

      .grptdw {
        border-left: 4px solid black;
        text-align: center;
      }
      .midtdw {
        border-style: none;
        border-left: 1px solid black;
        text-align: center;
      }
      .grptdg {
        border-left: 4px solid black;
        text-align: center;
        background-color: lightgreen;
        color: black;
      }
      .midtdg {
        border-style: none;
        border-left: 1px solid black;
        text-align: center;
        background-color: lightgreen;
        color: black;
      }
      .grptdr {
        border-left: 4px solid black;
        text-align: center;
        background-color: tomato;
        color: black;
      }
      .midtdr {
        border-style: none;
        border-left: 1px solid black;
        text-align: center;
        background-color: tomato;
        color: black;
      }
      .grptdy {
        border-left: 4px solid black;
        text-align: center;
        background-color: yellow;
        color: black;
      }
      .midtdy {
        border-style: none;
        border-left: 1px solid black;
        text-align: center;
        background-color: yellow;
        color: black;
      }
      .grptdc {
        border-left: 4px solid black;
        text-align: center;
        background-color: cyan;
        color: black;
      }
      .midtdc {
        border-style: none;
        border-left: 1px solid black;
        text-align: center;
        background-color: cyan;
        color: black;
      }
      .grptdh {
        border-left: 4px solid black;
        text-align: center;
        background-color: wheat;
        color: black;
      }
      .midtdh {
        border-style: none;
        border-left: 1px solid black;
        text-align: center;
        background-color: wheat;
        color: black;
      }
      .grptdm {
        border-left: 4px solid black;
        text-align: center;
        background-color: magenta;
        color: black;
      }
      .midtdm {
        border-style: none;
        border-left: 1px solid black;
        text-align: center;
        background-color: magenta;
        color: black;
      }
    </style>
  </head>
  <body>
'''.lstrip()

dashboard_close = '''
  </body>
</html>
'''


def html_start_rollup( fp, dmap, title, numdays=None ):
    """
    Begin a table that contains the latest results for each test run and
    a "status" word for historical dates.
    """
    dL = dmap.getDateList( numdays )

    fp.write( '\n' + \
        '<h3>'+title+'</h3>\n' + \
        '<table class="thintable">\n' + \
        '<tr style="border-style: none;">\n' + \
        '<th></th>\n' + \
        '<th class="grpth" colspan="4" style="text-align: center;">Test Results</th>\n' + \
        '<th class="grpth" colspan="'+str(len(dL))+'">Execution Status</th>\n' + \
        '</tr>\n' )
    fp.write(
        '<tr class="grptr">\n' + \
        '<th>Platform.Options.Variation</th>\n' + \
        '<th class="grpth">pass</th>\n' + \
        '<th class="midth">diff</th>\n' + \
        '<th class="midth">fail</th>\n' + \
        '<th class="midth">othr</th>\n' )
    cl = 'grpth'
    for day in dL:
        doy,yr,dow,m,d = day.split()
        if dow == '1':
            fp.write( '<th class="grpth">'+m+'/'+d+'</th>\n' )
        else:
            fp.write( '<th class="'+cl+'">'+m+'/'+d+'</th>\n' )
        cl = 'midth'
    fp.write(
        '</tr>\n' )

html_dowmap = {
    'sunday'    : 0, 'sun': 0,
    'monday'    : 1, 'mon': 1,
    'tuesday'   : 2, 'tue': 2,
    'wednesday' : 3, 'wed': 3,
    'thursday'  : 4, 'thu': 4,
    'friday'    : 5, 'fri': 5,
    'saturday'  : 6, 'sat': 6,
}

def html_rollup_line( fp, plug, dmap, label, cnts, stats, shorten=None ):
    """
    Each entry in the rollup table is written by calling this function.  It
    is called for each test run id, which is the 'label'.

    If 'shorten' is not None, it should be the number of days to display.  It
    also prevents any html links to be written.
    """
    dL = dmap.getDateList( shorten )

    schedL = None
    if plug:
        sched = plug.get_test_run_info( label, 'schedule' )
        if sched:
            schedL = []
            for s in sched.split():
                dow = html_dowmap.get( s.lower(), None )
                if dow != None:
                    schedL.append( dow )

    # create a map of the date to the result color
    hist = {}
    for xd,rs in stats:
        day = DateInfoString( xd )
        hist[ day ] = ( rs, result_color( rs ) )
    
    np,nd,nf,nt,nr,unk = cnts
    fp.write( '\n<tr class="midtr">\n' )
    if shorten == None:
        fp.write( '<td><a href="testrun.html#'+label+'">'+label+'</a></td>\n' )
    else:
        fp.write( '<td>'+label+'</td>\n' )
    fp.write( '<td class="grptdg"><b>'+str(np)+'</b></td>\n' )
    cl = ( "midtdy" if nd > 0 else "midtdg" )
    fp.write( '<td class="'+cl+'"><b>'+str(nd)+'</b></td>\n' )
    cl = ( "midtdr" if nf > 0 else "midtdg" )
    fp.write( '<td class="'+cl+'"><b>'+str(nf)+'</b></td>\n' )
    cl = ( "midtdy" if nt+nr+unk > 0 else "midtdg" )
    fp.write( '<td class="'+cl+'"><b>'+str(nt+nr+unk)+'</b></td>\n' )

    ent = 'grptd'
    for day in dL:
        doy,yr,dow,m,d = day.split()
        if day in hist:
            rs,c = hist[day]
            #rs,c = hist.get( day, ( '', 'w' ) )
        elif schedL != None:
            if int(dow) in schedL:
                rs,c = 'MIA', result_color('MIA')
            else:
                rs,c = '','w'
        else:
            rs,c = '','w'
        if dow == '1':
            fp.write( '<td class="grptd'+c+'">'+rs+'</td>\n' )
        else:
            fp.write( '<td class="'+ent+c+'">'+rs+'</td>\n' )
        ent = 'midtd'
    fp.write( '</tr>\n' )


def html_end_rollup( fp ):
    """
    """
    fp.write( '\n</table>\n' )


def html_start_detail( fp, dmap, testid, marknum ):
    """
    Call this function for individual test to be detailed, which will show
    the result status for each of the dates.
    """
    dL = dmap.getDateList()

    fp.write( '\n' + \
        '<h3 id="test'+str(marknum)+'">' + html_escape(testid) + '</h3>\n' + \
        '<table class="thintable">\n' + \
        '<tr class="grptr">\n' + \
        '<th></th>\n' )
    cl = 'grpth'
    for day in dL:
        doy,yr,dow,m,d = day.split()
        if dow == '1':
            fp.write( '<th class="grpth">'+m+'/'+d+'</th>\n' )
        else:
            fp.write( '<th class="'+cl+'">'+m+'/'+d+'</th>\n' )
        cl = 'midth'
    fp.write(
        '</tr>\n' )


def html_detail_line( fp, dmap, label, resL ):
    """
    Called once per line for detailing a test.  The 'label' is the test run id.
    """
    dL = dmap.getDateList()

    # create a map of the date to the result color
    hist = {}
    for fd,rs in resL:
        day = DateInfoString( fd )
        hist[ day ] = ( rs, result_color( rs ) )
    
    fp.write( '\n' + \
        '<tr class="midtr">\n' + \
        '<td><a href="testrun.html#'+label+'">'+label+'</a></td>\n' )
    
    ent = 'grptd'
    for day in dL:
        doy,yr,dow,m,d = day.split()
        rs,c = hist.get( day, ( '', 'w' ) )
        if dow == '1':
            fp.write( '<td class="grptd'+c+'">'+rs+'</td>\n' )
        else:
            fp.write( '<td class="'+ent+c+'">'+rs+'</td>\n' )
        ent = 'midtd'

    fp.write( '</tr>\n' )

def html_escape( s ):
    """
    """
    s = s.replace( '&', '&amp' )
    s = s.replace( '<', '&lt' )
    s = s.replace( '>', '&gt' )
    return s

def write_testrun_entry( fp, plug, results_key, fdate, tr, detailed ):
    """
    The test run page shows information about the test run, such as which
    machine and directory, the compiler, and the schedule.  It draws on data
    from the config directory, if present.
    """
    desc = None
    log = None
    sched = None
    if plug and hasattr( plug, 'get_test_run_info' ):
        desc = plug.get_test_run_info( results_key, 'description' )
        log = plug.get_test_run_info( results_key, 'log' )
        sched = plug.get_test_run_info( results_key, 'schedule' )
    datestr = time.strftime( "%Y %m %d", time.localtime(fdate) )

    fp.write( '\n' + \
        '<h2 id="'+results_key+'">'+results_key+'</h2>\n' + \
        '<ul>\n' )
    if desc:
        fp.write( 
        '<li><b>Description:</b> '+html_escape(desc)+'</li>\n' )
    fp.write(
        '<li><b>Machine:</b> '+tr.machine()+'</li>\n' + \
        '<li><b>Compiler:</b> '+tr.compiler()+'</li>\n' + \
        '<li><b>Test Directory:</b> '+tr.testdir()+'</li>\n' )
    if log:
        fp.write(
        '<li><b>Log File:</b> '+html_escape(log)+'</li>\n' )
    if sched:
        fp.write(
        '<li><b>Schedule:</b> '+html_escape(sched)+'</li>\n' )
    
    for tdd in [False,True]:
        resD,num = tr.collectResults( 'fail', 'diff', 'timeout',
                                      'notrun', 'notdone',
                                      matchlist=True, tdd=tdd )
        if tdd:
            if len(resD) == 0:
                continue  # skip the TDD item altogether if no tests
            fp.write(
                '<li><b>Latest TDD Results:</b> '+datestr )
        else:
            fp.write(
                '<li><b>Latest Results:</b> '+datestr )
        if len(resD) > 0:
            resL = []
            for kT,vT in resD.items():
                d,tn = kT
                xd,res = vT
                resL.append( ( d+'/'+tn, res.split('=',1)[1] ) )
            resL.sort()

            fp.write( \
                '<br>\n' + \
                '<table style="border: 1px solid black; border-collapse: collapse;">\n' )
            maxlist = 40  # TODO: make this number configurable
            i = 0
            for tn,res in resL:
                if i >= maxlist:
                    i = len(resL)+1
                    break
                cl = 'midtd'+result_color(res)
                fp.write( \
                    '<tr style="border: 1px solid black;">\n' + \
                    '<td class="'+cl+'" style="border: 1px solid black;">'+res+'</td>\n' )
                tid = detailed.get( tn, None )
                if tid:
                    fp.write( \
                        '<td><a href="dash.html#test'+str(tid)+'">' + \
                        html_escape(tn) + '</a></td></tr>\n' )
                else:
                    fp.write( '<td>' + html_escape(tn) + '</td></tr>\n' )
                i += 1
            fp.write( \
                '</table>\n' )
            if i > len(resL):
                fp.write( \
                    '<br>\n' + \
                    '*** this list truncated; num entries = '+str(len(resL))+'\n' )
        fp.write( '</li>\n' )
    fp.write( '</ul>\n' )
    fp.write( '<br>\n' )


def result_color( result ):
    """
    Translate the result string into a color character.  These colors must
    be known to the preample "style" list.
    """
    if result == 'pass': return 'g'
    if result == 'ran': return 'g'
    if result == 'start': return 'c'
    if result == 'notdone': return 'c'
    if result == 'diff': return 'y'
    if result == 'fail': return 'r'
    if result == 'notrun': return 'h'
    if result == 'timeout': return 'm'
    if result == 'MIA': return 'y'
    return 'w'

########################################################################

class LookupCache:
    
    def __init__(self, platname, cplrname, resultsdir=None):
        """
        """
        self.platname = platname
        self.cplrname = cplrname

        self.multiDB = None
        if resultsdir != None:
            f = os.path.join( resultsdir, multiruntimes_filename )
            self.multiDB = MultiResults()
            if os.path.exists(f):
                self.multiDB.readFile(f)

        self.testDB = TestResults()
        self.srcdirs = {}  # set of directories scanned for TestResults
        self.rootrelD = {}  # maps absolute path to root rel directory

    def getRunTime(self, testspec):
        """
        Looks in the testing directory and the test source tree for files that
        contain a runtime for the given test.  If an entry is not found then
        None,None is returned.
        
        The 'cache' must be a LookupCache instance and should be the same instance
        for a set of tests (which helps performance).  Also, this same cache
        should be given/used by any approximate execution time algorithms if this
        function fails to find a runtime for the test.
        
        The algorithm looks for the test in this order:
        
          1. The TESTING_DIRECTORY directory multiplatform results file
          2. A test source tree runtimes file
        """
        
        platid = self.platname+'/'+self.cplrname
        
        testkey = os.path.basename( testspec.getExecuteDirectory() )
        tdir = testspec.getDirectory()
        
        # the most reliable runtime will be in the testing directory, but for
        # that we need the test root relative directory
        
        rootrel = self.rootrelD.get( tdir, None )
        
        if rootrel == None:
          rootrel = _file_rootrel( tdir )
          if rootrel == None:
            rootrel = _svn_rootrel( tdir )
            if rootrel == None:
              if self.multiDB != None:
                rootrel = self.multiDB.getRootRelative( testkey )
              if rootrel == None:
                rootrel = ''  # mark this directory so we don't try again
          self.rootrelD[tdir] = rootrel
        
        tlen = None
        result = None
        
        if rootrel and self.multiDB != None:
          tlen,result = self.multiDB.getTime( rootrel, testkey, platid )
        
        if tlen == None and rootrel:
          
          # look for runtimes in the test source tree
          
          d = testspec.getDirectory()
          if d not in self.srcdirs:
            
            while tlen == None:
              f = os.path.join( d, runtimes_filename )
              self.srcdirs[d] = None
              if os.path.exists(f):
                try:
                  fmt,vers,hdr,nskip = read_file_header( f )
                except:
                  fmt = None
                if fmt and fmt == 'results':
                  self.testDB.mergeRuntimes( f )
                  break
              
              nd = os.path.dirname(d)
              if d == nd or not nd or nd == '/' or nd in self.srcdirs:
                break
              d = nd
          
          tlen = self.testDB.getTime( rootrel, testkey )
        
        return tlen, result


########################################################################

def write_JUnit_file( test_dir, rawlist, filename, datestamp ):
    """
    This collects information from the given test list (a python list of
    TestExec objects), then writes a file in the format of JUnit XML files.
    
    The purpose is to be able to pull vvtest results into Jenkins jobs so it
    can display them in some form.  The format was determined starting with
    this link
        https://stackoverflow.com/questions/4922867/
                    junit-xml-format-specification-that-hudson-supports
    then just trial and error until Jenkins showed something reasonable.
    """
    tdir = os.path.basename( test_dir )
    tdir = tdir.replace( '.', '_' )  # a dot is a Java class separator
    
    datestr = time.strftime( "%Y-%m-%dT%H:%M:%S", time.localtime( datestamp ) )

    npass = nwarn = nfail = 0
    tsum = 0.0
    for t in rawlist:
        state = t.getAttr( 'state' )
        if state == "done":
            res = t.getAttr( 'result' )
            if res == "pass":
                npass += 1
            elif res == "diff":
                nwarn += 1
            else:
                nfail += 1
            
            xt = t.getAttr( 'xtime' )
            if xt > 0:
                tsum += xt
        else:
            nwarn += 1
    
    s = '''
<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
   <testsuite name="vvtest"
              errors="0" tests="0" failures="0"
              time="0" timestamp="DATESTAMP"/>
   <testsuite name="vvtest.TESTDIRNAME"
              errors="0" skipped="NUMWARN" tests="NUMTESTS" failures="NUMFAIL"
              time="TIMESUM" timestamp="DATESTAMP">
'''.strip()
    
    s = s.replace( 'TESTDIRNAME', tdir )
    s = s.replace( 'DATESTAMP', datestr )
    s = s.replace( 'NUMTESTS', str(npass+nwarn+nfail) )
    s = s.replace( 'NUMWARN', str(nwarn) )
    s = s.replace( 'NUMFAIL', str(nfail) )
    s = s.replace( 'TIMESUM', str(tsum) )

    for t in rawlist:
        
        xt = 0.0
        fail = ''
        warn = ''

        state = t.getAttr( 'state' )
        if state == "notrun":
            warn = 'Test was not run'
        else:
            if state == "done":
                xt = t.getAttr( 'xtime' )
                if xt < 0:
                    xt = 0.0
                
                res = t.getAttr( 'result' )
                if res == "pass":
                    pass
                elif res == "diff":
                    warn = 'Test diffed'
                elif res == "timeout":
                    fail = 'Test timed out'
                else:
                    fail = 'Test failed'
            else:
                warn = "Test did not finish"
        
        s += '\n      <testcase name="'+t.xdir+'" time="'+str(xt)+'">'
        if warn:
            s += '\n        <skipped message="'+warn+'"/>'
        elif fail:
            s += '\n        <failure message="'+fail+'"/>'
        s += '\n      </testcase>'
    
    s += '\n   </testsuite>'
    s += '\n</testsuites>\n'
    
    fp = open( filename, 'w' )
    fp.write(s)
    fp.close()


########################################################################

def print3( *args, **kwargs ):
    s = ' '.join( [ str(x) for x in args ] )
    if len(kwargs) > 0:
        s += ' ' + ' '.join( [ str(k)+'='+str(v) for k,v in kwargs.items() ] )
    sys.stdout.write( s + os.linesep )
    sys.stdout.flush()


def process_option( optD, option_name, value_type, *restrictions ):
    """
    """
    if option_name in optD:
        try:
            v = value_type( optD[option_name] )
        except:
            print3( '*** error: invalid option value "'+option_name+'":',
                    sys.exc_info()[1] )
            sys.exit(1)
        if 'positive' in restrictions and not v > 0:
            print3( '*** error: option "'+option_name+'"',
                    'value must be positive:', optD[option_name] )
            sys.exit(1)
        optD[option_name] = v


########################################################################

d = sys.path[0]
if d: mydir = os.path.abspath( d )
else: mydir = os.getcwd()

if __name__ == "__main__":
    results_main()
