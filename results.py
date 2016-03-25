#!/usr/bin/env python

import os, sys
import string
import time
import types
import StringIO
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

Provides a short summary of results files in the current working directory,
then details the history on each platform of tests that diff, fail, or timeout
as the last execution on at least one platform.

    -d <days back>
            examine results files back this many days; default is 15 days
    -D <days back>
            only itemize tests that fail/diff if they ran this many days ago;
            default is 7 days
    -r <integer>
            if the number of tests that fail/diff in a single test results
            file are greater than this value, then don't itemize each test
            from that test execution; default is 25 tests
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
    except getopt.error, e:
        print3( "*** error:", e )
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
    except getopt.error, e:
        print3( "*** error:", e )
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
    except getopt.error, e:
      sys.stderr.write( "*** results.py error: " + str(e) + os.linesep )
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
    except getopt.error, e:
      sys.stderr.write( "*** results.py error: " + str(e) + os.linesep )
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
    except Exception, e:
      sys.stderr.write( "*** Results clean failed: " + str(e) + os.linesep )
      sys.exit(1)
    for s in warnings:
      print "*** " + s


def report_main( argv ):
    """
    """
    import getopt
    try:
        optL,argL = getopt.getopt( argv[1:], "d:D:r:o:O:t:T:p:P:g:",
                                             longopts=['plat='] )
    except getopt.error, e:
        print3( "*** error:", e )
        sys.exit(1)
    
    optD = {}
    for n,v in optL:
        if n in ['-o','-O','-t','-T','-p','-P','--plat','-g']:
            optD[n] = optD.get( n, [] ) + [v]
        else:
            optD[n] = v
    
    process_option( optD, '-d', float, "positive" )
    process_option( optD, '-D', float, "positive" )
    process_option( optD, '-r', int, "positive" )

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
        dL = self.dataD.keys()
        dL.sort()
        return dL
    
    def testList(self, rootrel):
        """
        For a given root-relative directory, return a sorted list of test
        keys contained in that directory.
        """
        tD = self.dataD.get( rootrel, {} )
        tL = tD.keys()
        tL.sort()
        return tL
    
    def platformList(self, rootrel, testkey):
        """
        For a given root-relative directory and a test key, return the list
        of platform/compilers stored for the test.
        """
        tD = self.dataD.get( rootrel, {} )
        pD = tD.get( testkey, {} )
        pL = pD.keys()
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
        fp = open( filename, 'wb' )
        fp.write( 'FILE_VERSION=multi' + str(self.vers) + os.linesep )
        
        fp.write( os.linesep )
        dL = self.dataD.keys()
        dL.sort()
        for d in dL:
          tD = self.dataD[d]
          tL = tD.keys()
          tL.sort()
          for tn in tL:
            pD = tD[tn]
            pL = pD.keys()
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
        
        fp = open( filename, 'rb' )
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
    return string.join( dirL, '/' )

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
        return string.join( dL[1:], '/' )
    
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
    
    def platform(self):  return self.hdr.get('PLATFORM',None)
    def compiler(self):  return self.hdr.get('COMPILER',None)
    def machine (self):  return self.hdr.get('MACHINE',None)
    def testdir (self):  return self.hdr.get('TEST_DIRECTORY',None)
    
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
        dL = self.dataD.keys()
        dL.sort()
        return dL
    
    def testList(self, rootrel):
        """
        For a given root-relative directory, return a sorted list of test
        keys contained in that directory.
        """
        tD = self.dataD.get( rootrel, {} )
        tL = tD.keys()
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

    def getSummary(self):
        """
        Counts the number of tests that pass, fail, diff, timeout, notrun,
        and notdone, and returns a string with the counts.
        """
        np = nf = nd = nr = nt = unk = 0
        for d,tD in self.dataD.items():
            for tn,aD in tD.items():
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
        return 'pass='+str(np) + ' diff='+str(nd) + ' fail='+str(nf) + \
               ' timeout='+str(nt) + ' notrun='+str(nr) + ' ?='+str(unk)

    def collect(self, *args, **kwargs):
        """
        All tests that contain a result in the given list of result keywords
        are collected into a string and returned.  If the keyword argument
        'limit' is given, the list will stop collecting at that amount and
        return (the default is 50).
        """
        lim = kwargs.get( 'limit', 50 )

        tL = []
        for d,tD in self.dataD.items():
            for tn,aD in tD.items():
                st = aD.get( 'state', '' )
                rs = aD.get( 'result', '' )
                if st in args or rs in args:
                    if len(tL) < lim:
                        tL.append( (d,tn) )
        tL.sort()
        return tL

    def writeResults(self, filename, plat_name, cplr_name,
                           mach_name, test_dir):
        """
        Writes out test results for all tests, with a header that includes the
        directory in which the tests were run, the platform name, and the
        compiler name.
        """
        fp = open( filename, 'wb' )
        
        fp.write( 'FILE_VERSION=results' + str(self.vers) + os.linesep )
        fp.write( 'PLATFORM=' + str(plat_name) + os.linesep )
        fp.write( 'COMPILER=' + str(cplr_name) + os.linesep )
        fp.write( 'MACHINE=' + str(mach_name) + os.linesep )
        fp.write( 'TEST_DIRECTORY=' + str(test_dir) + os.linesep )
        
        fp.write( os.linesep )
        dL = self.dataD.keys()
        dL.sort()
        for d in dL:
          tD = self.dataD[d]
          tL = tD.keys()
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
        
        fp = open( filename, 'rb' )
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
        
        fp = open( filename, 'wb' )
        fp.write( 'FILE_VERSION=results' + str(self.vers) + os.linesep )
        
        if rootrel == None:
            rootrel = os.path.basename( os.path.abspath(dirname) )
        fp.write( 'ROOT_RELATIVE=' + rootrel + os.linesep )
        rrL = rootrel.split('/')
        rrlen = len(rrL)
        
        fp.write( os.linesep )
        dL = self.dataD.keys()
        dL.sort()
        for d in dL:
            # skip 'd' if it is not equal to or a subdirectory of rootrel
            if d.split('/')[:rrlen] == rrL:
                tD = self.dataD[d]
                tL = tD.keys()
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
            
            fp = open( filename, 'rb' )
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
      s = s + ' ' + string.join( time.ctime(v).split(), '_' )
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
    return string.strip(s)


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
        attrD['state'] = attrL[i]
        if attrL[i] == "done":
            i += 1
            if i < len(attrL):
                attrD['result'] = attrL[i]
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
      fp = open( filename, 'rb' )
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

    fileL = process_files( optD, fileL )
    
    mr = MultiResults()
    if os.path.exists( multiruntimes_filename ):
        mr.readFile( multiruntimes_filename )
    
    warnL = []
    newtest = False
    for f in fileL:
        try:
            fmt,vers,hdr,nskip = read_file_header( f )
        except Exception, e:
            warnL.append( "skipping results file: " + f + \
                          ", Exception = " + str(e) )
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
    except Exception, e:
        warnL.append( "skipping multi-platform results file " + \
                      filename + ": Exception = " + str(e) )
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
    except Exception, e:
        warnL.append( "skipping results file " + filename + \
                      ": Exception = " + str(e) )
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


def process_files( optD, fileL ):
    """
    Apply -g and -d options to 'fileL', and return a new list.  The order
    of 'fileL' is retained, but each glob list is sorted by ascending file
    date stamp.

    The -d option applies to files of form "results.YYYY_MM_DD.*".
    The -p option to form "results.YYYY_MM_DD.platform.*".
    The -o option to form "results.YYYY_MM_DD.platform.options.*", where the
    options are separated by a plus sign.
    The -t option to form "results.YYYY_MM_DD.platform.options.tag".
    """
    if '-g' in optD:
        gL = []
        for pat in optD['-g']:
            L = [ (os.path.getmtime(f),f) for f in glob.glob( pat ) ]
            L.sort()
            gL.extend( [ f for t,f in L ] )
        fileL = gL + fileL

    if '-d' in optD:
        # filter out results files that are too old
        cutoff = int( time.time() - optD['-d']*24*60*60 )
        newL = []
        for f in fileL:
            try:
                L = os.path.basename(f).split('.')
                T = time.strptime( L[1], '%Y_%m_%d' )
                ftime = time.mktime( T )
            except:
                newL.append( f )  # don't apply filter to this file
            else:
                if ftime >= cutoff:
                    newL.append( f )
        fileL = newL

    platL = None
    if '-p' in optD or '--plat' in optD:
        platL = optD.get( '-p', [] ) + optD.get( '--plat', [] )
    xplatL = optD.get( '-P', None )
    if platL != None or xplatL != None:
        # include/exclude results files based on platform name
        newL = []
        for f in fileL:
            try:
                platname = os.path.basename(f).split('.')[2]
            except:
                newL.append( f )  # don't apply filter to this file
            else:
                if ( platL == None or platname in platL ) and \
                   ( xplatL == None or platname not in xplatL ):
                    newL.append( f )
        fileL = newL

    if '-o' in optD:
        # keep results files that are in the -o list
        optnL = '+'.join( optD['-o'] ).split('+')
        newL = []
        for f in fileL:
            try:
                foptL = os.path.basename(f).split('.')[3].split('+')
            except:
                newL.append( f )  # don't apply filter to this file
            else:
                # if at least one of the -o values from the command line
                # is contained in the file name options, then keep the file
                for op in optnL:
                    if op in foptL:
                        newL.append( f )
                        break
        fileL = newL

    if '-O' in optD:
        # exclude results files that are in the -O list
        optnL = '+'.join( optD['-O'] ).split('+')
        newL = []
        for f in fileL:
            try:
                foptL = os.path.basename(f).split('.')[3].split('+')
            except:
                newL.append( f )  # don't apply filter to this file
            else:
                # if at least one of the -O values from the command line is
                # contained in the file name options, then exclude the file
                keep = True
                for op in optnL:
                    if op in foptL:
                        keep = False
                        break
                if keep:
                    newL.append( f )
        fileL = newL

    tagL = optD.get( '-t', None )
    xtagL = optD.get( '-T', None )
    if tagL != None or xtagL != None:
        # include/exclude based on tag
        newL = []
        for f in fileL:
            try:
                tag = os.path.basename(f).split('.')[4]
            except:
                newL.append( f )  # don't apply filter to this file
            else:
                if ( tagL == None or tag in tagL ) and \
                   ( xtagL == None or tag not in xtagL ):
                    newL.append( f )
        fileL = newL

    return fileL


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
      except Exception, e:
        warnL.append( "Warning: skipping results file: " + srcf + \
                     ", Exception = " + str(e) )
      else:
        if fmt and fmt == 'results':
          src = TestResults()
          try:
            src.readResults(srcf)
          except Exception, e:
            warnL.append( "Warning: skipping results file: " + srcf + \
                         ", Exception = " + str(e) )
          else:
            for d in src.dirList():
              if d.split('/')[:rrlen] == rrdirL:
                for tn in src.testList(d):
                  aD = src.testAttrs( d, tn )
                  if aD.get('result','') in ['pass','diff']:
                    k = (d,tn)
                    if testD.has_key(k): testD[k].append(aD)
                    else:                testD[k] = [aD]
        elif fmt and fmt == 'multi':
          src = MultiResults()
          try:
            src.readFile(srcf)
          except Exception, e:
            warnL.append( "Warning: skipping results file: " + srcf + \
                         ", Exception = " + str(e) )
          else:
            for d in src.dirList():
              if d.split('/')[:rrlen] == rrdirL:
                for tn in src.testList(d):
                  for pc in src.platformList( d, tn ):
                    aD = src.testAttrs( d, tn, pc )
                    if aD.get('result','') in ['pass','diff']:
                      k = (d,tn)
                      if testD.has_key(k): testD[k].append(aD)
                      else:                testD[k] = [aD]
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
          if aD.has_key( 'xdate' ):
            if save_aD == None or save_aD['xdate'] < aD['xdate']:
              save_aD = aD
      if save_aD != None:
        t = int( tsum/tnum )
        save_aD['xtime'] = t
        avgD[k] = save_aD
    
    tr = TestResults()
    rtdirD = {}  # runtimes directory -> root relative path
    
    # read any existing runtimes files at or below the CWD
    def read_src_dir( args, dirname, fnames ):
      trs,rtD,msgs = args
      rtf = os.path.join( dirname, runtimes_filename )
      if os.path.isfile(rtf):
        try:
          fmt,vers,hdr,nskip = read_file_header( rtf )
          rr = hdr.get( 'ROOT_RELATIVE', None )
          trs.mergeRuntimes(rtf)
        except Exception, e:
          msgs.append( "Warning: skipping existing runtimes file due to " + \
                       "error: " + rtf + ", Exception = " + str(e) )
        else:
          if rr == None:
            msgs.append( "Warning: skipping existing runtimes file " + \
                         "because it does not contain the ROOT_RELATIVE " + \
                         "specification: " + rtf )
          else:
            rtD[dirname] = rr
    os.path.walk( cwd, read_src_dir, (tr,rtdirD,warnL) )
    
    if optD.has_key('-w'):
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
      
      if optD.has_key('-p'):
        p = hdr.get( 'PLATFORM', '' )
        c = hdr.get( 'COMPILER', '' )
        if p or c:
          print p+'/'+c
      
      else:
        tL = []
        for d in src.dirList():
          for tn in src.testList(d):
            aD = src.testAttrs(d,tn)
            if aD.has_key('xdate'):
              tL.append( ( aD['xdate'], tn, d, aD ) )
        tL.sort()
        tL.reverse()
        for xdate,tn,d,aD in tL:
          print make_attr_string(aD), d+'/'+tn
    
    elif fmt and fmt == 'multi':
      src = MultiResults()
      src.readFile(fname)
      
      if optD.has_key('-p'):
        pcD = {}
        for d in src.dirList():
          for tn in src.testList(d):
            for pc in src.platformList(d,tn):
              pcD[pc] = None
        pcL = pcD.keys()
        pcL.sort()
        for pc in pcL:
          print pc
      
      else:
        tL = []
        for d in src.dirList():
          for tn in src.testList(d):
            for pc in src.platformList(d,tn):
              aD = src.testAttrs(d,tn,pc)
              if aD.has_key('xdate'):
                tL.append( ( aD['xdate'], tn, d, pc, aD ) )
        tL.sort()
        tL.reverse()
        for xdate,tn,d,pc,aD in tL:
          print make_attr_string(aD), pc, d+'/'+tn
    
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
    
    if not optD.has_key('-p'):
      msgL.append( "Warning: nothing to do without the -p option " + \
                   "(currently)" )
    
    fmt,vers,hdr,nskip = read_file_header( path )
    if fmt and fmt == 'results':
      if optD.has_key('-p'):
        msgL.append( "Warning: the -p option has no effect on results files" )
      else:
        pass
    elif fmt and fmt == 'multi':
      if optD.has_key('-p'):
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

    if '-d' not in optD:
        optD['-d'] = 15.0  # default to 15 days old
    if '-D' in optD:
        showage = optD['-D']
    else:
        showage = 7
    if '-r' in optD:
        maxreport = optD['-r']
    else:
        maxreport = 25  # default to 25 tests
    
    # this collects the files and applies filters
    fileL = process_files( optD, fileL )

    # read all the results files that fall within the -d range
    rmat = ResultsMatrix()
    for f in fileL:
        try:
            # get the date stamp on the file
            L = os.path.basename(f).split('.')
            T = time.strptime( L[1], '%Y_%m_%d' )
            ftime = time.mktime( T )

            # try to read the file
            fmt,vers,hdr,nskip = read_file_header( f )
            assert fmt == 'results', \
                    'expected a "results" file format, not "'+str(fmt)+'"'
            tr = TestResults( f )
            
            # the file header contains the platform & compiler names
            assert tr.platform() != None and tr.compiler() != None
        
        except Exception, e:
            warnL.append( "skipping results file: " + f + \
                          ", Exception = " + str(e) )
        else:
            rmat.add( ftime, tr )

    # the DateMap object helps format the test results output
    dmin = min( curtm-optD['-d']*24*60*60, rmat.minFileDate() )
    dmax = max( 0                        , rmat.maxFileDate() )
    dmap = DateMap( dmin, dmax )

    # write out the summary for each plat/cplr combination; use the machine
    # and location of the run to separate the vvtest executions

    print3( "A summary by platform/compiler is next." )
    print3( "An 'r' code means a vvtest execution was run on that date." )

    pclen = 0
    redD = {}
    for pc in rmat.platcplrs():
        
        # find max plat/cplr string length for below
        pclen = max( pclen, len(pc) )

        for loc in rmat.locations(pc):
            
            print3()
            print3( pc, '@', loc )
            
            dL = rmat.dateList( pc, loc )
            rL = zip( dL, [ 'run' for i in range(len(dL)) ] )
            hist = dmap.history(rL)

            fdate,tr = rmat.latestResults( pc, loc )
            
            print3( '  ', dmap.legend() )
            print3( '  ', hist, '  ', tr.getSummary() )

            # limit itemization of tests to results that ran recently enough
            if fdate > curtm - showage*24*60*60:
                L = tr.collect( 'fail', 'diff', 'timeout' )
                # do not report individual test results for a test
                # execution that has massive failures
                if len(L) <= maxreport:
                    for d,tn in L:
                        redD[ (d,tn) ] = None
    
    print3()
    print3( 'Tests that have diffed, failed, or timed out are next.' )
    print3( 'Result codes: p=pass, D=diff, F=fail, T=timeout, n=notrun' )
    print3()

    # for each test that fail/diff/timeout, collect and print the history of
    # the test on each plat/cplr and for each results date stamp

    pcfmt = "   %-"+str(pclen)+"s"
    redL = redD.keys()
    redL.sort()
    for d,tn in redL:
        
        # print the path to the test and the date legend
        print3( d+'/'+tn )
        print3( pcfmt % ' ', dmap.legend() )

        for pc in rmat.platcplrs():
            tests,location = rmat.resultsForTest( pc, d, tn )
            rL = []
            for fd,aD in tests:
                st = aD.get( 'state', '' )
                rs = aD.get( 'result', '' )
                if rs: rL.append( (fd,rs) )
                else: rL.append( (fd,st) )
            print3( pcfmt%pc, dmap.history( rL ), location )

        print3()

    return warnL


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

    def add(self, filedate, results):
        """
        Based on the 'results' instance (of a TestResults class), this function
        determines the location in the matrix to append the results, and does
        the append.
        """
        plat,cplr = results.platform(), results.compiler()
        if plat == None: plat = '?'
        if cplr == None: cplr = '?'
        
        mach,rdir = results.machine(), results.testdir()
        if mach == None: mach = '?'
        if rdir == None: rdir = '?'
        
        rowk = plat+'/'+cplr
        colk = mach+':'+rdir
        
        if rowk not in self.matrixD:
            self.matrixD[rowk] = {}
        row = self.matrixD[rowk]

        if colk not in row:
            row[colk] = []

        row[colk].append( (filedate,results) )

        row[colk].sort()  # kept sorted by increasing file date
        
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

    def platcplrs(self):
        """
        Return a sorted list of the platform/compiler names.  That is, the
        rows in the matrix.
        """
        L = self.matrixD.keys()
        L.sort()
        return L

    def locations(self, platcplr):
        """
        For the given 'platcplr', return a sorted list of the
        machine:testdirectory names.  That is, the columns of the matrix for
        that row.
        """
        L = self.matrixD[platcplr].keys()
        L.sort()
        return L

    def dateList(self, platcplr, location):
        """
        Returns a list of file dates for the test results in the 'platcplr'
        row and 'location' column.  The list is sorted by increasing date.
        """
        L = [ pair[0] for pair in self.matrixD[platcplr][location] ]
        return L

    def latestResults(self, platcplr, location):
        """
        Returns the (file date, TestResults) pair with the most recent file
        date stamp for the given 'platcplr' row and 'location' column.
        """
        L = self.matrixD[platcplr][location]
        return L[-1]

    def resultsForTest(self, platcplr, testdir, testname):
        """
        For each entry in the 'platcplr' row, collect the attributes of the
        test containing the test ID 'testdir' plus 'testname'.  That is, all
        tests with the given ID are collected across each of the locations
        for the given platcplr.

        The collection is gathered as a list of (file date, test attributes)
        pairs (and sorted).

        Also computed is the location of the most recent execution of the test.

        The list and the location are returned.
        """
        D = {}
        maxloc = None
        for loc,L in self.matrixD[platcplr].items():
            for filedate,results in L:
                attrD = results.testAttrs( testdir, testname )
                if len(attrD) > 0:
                    D[ filedate ] = attrD
                    if maxloc == None:
                        maxloc = [ filedate, loc, attrD ]
                    elif filedate > maxloc[0]:
                        maxloc = [ filedate, loc, attrD ]
                    elif abs( filedate - maxloc[0] ) < 2:
                        # the test appears in more than one results file, so
                        # choose the test that executed most recently
                        d1 = attrD.get( 'xdate', None )
                        d2 = maxloc[2].get( 'xdate', None )
                        if d1 == None:
                            pass
                        elif d2 == None or d1 > d2:
                            maxloc = [ filedate, loc, attrD ]
        
        L = D.items()
        L.sort()

        if maxloc == None: loc = ''
        else:              loc = maxloc[1]
        
        return L,loc


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
            self.histL = [ self._day( time.localtime() ) ]
        else:
            self.histL = []
            d = mindate
            while not d > maxdate:
                day = self._day( time.localtime(d) )
                if day not in self.histL:
                    self.histL.append( day )
                d += 24*60*60
            day = self._day( time.localtime(maxdate) )
            if day not in self.histL:
                self.histL.append( day )

        # determine number of characters in first group (week)
        num1 = 0
        for day in self.histL:
            doy,yr,dow,m,d = day.split()
            if num1 and dow == '1':
                break
            num1 += 1

        # compute the dates that start each week (or partial week)
        self.dateL = []
        n = 0
        for day in self.histL:
            doy,yr,dow,m,d = day.split()
            if not n:
                self.dateL.append( '%-7s' % (m+'/'+d) )
            n += 1
            if dow == '0':
                n = 0
        
        # the first group is a little special; first undo the padding
        self.dateL[0] = self.dateL[0].strip()
        if len( self.dateL[0] ) < num1:
            # pad the first legend group on the right with spaces
            self.dateL[0] = ( '%-'+str(num1)+'s') % self.dateL[0]

    def legend(self):
        return ' '.join( self.dateL )

    def history(self, resultL):
        """
        Given a list of (date,result) pairs, this function formats the
        history into a string and returns it.
        """
        # create a map of the date to the result character
        hist = {}
        for xd,rs in resultL:
            day = self._day( time.localtime(xd) )
            hist[ day ] = self._char( rs )

        # walk the full history range and accumulate the result characters
        # in order (if a test is absent on a given day, a period is used)
        cL = []
        s = ''
        for day in self.histL:
            doy,yr,dow,m,d = day.split()
            if s and dow == '1':
                cL.append( s )
                s = ''
            s += hist.get( day, '.' )
        if s:
            cL.append( s )
        
        # may need to pad the first date group
        if len(cL[0]) < len(self.dateL[0]):
            fmt = '%'+str(len(self.dateL[0]))+'s'
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
        if result == 'run': return 'r'   # this is for vvtest runs
        return '?'

    def _day(self, tm):
        """
        Return a time tuple for the given time, with strategic entries.
        """
        return time.strftime( "%j %Y %w %m %d", tm )


########################################################################

class LookupCache:
    
    def __init__(self, resultsdir=None):
        
        self.multiDB = None
        if resultsdir != None:
            f = os.path.join( resultsdir, multiruntimes_filename )
            self.multiDB = MultiResults()
            if os.path.exists(f):
                self.multiDB.readFile(f)
        
        self.testDB = TestResults()
        self.srcdirs = {}  # set of directories scanned for TestResults
        
        self.rootrelD = {}  # maps absolute path to root rel directory


def get_execution_time(testspec, pname, cplr, cache):
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
    
    platid = pname+'/'+cplr
    
    testkey = os.path.basename( testspec.getExecuteDirectory() )
    tdir = testspec.getDirectory()
    
    # the most reliable runtime will be in the testing directory, but for
    # that we need the test root relative directory
    
    rootrel = cache.rootrelD.get( tdir, None )
    
    if rootrel == None:
      rootrel = _file_rootrel( tdir )
      if rootrel == None:
        rootrel = _svn_rootrel( tdir )
        if rootrel == None:
          if cache.multiDB != None:
            rootrel = cache.multiDB.getRootRelative( testkey )
          if rootrel == None:
            rootrel = ''  # mark this directory so we don't try again
      cache.rootrelD[tdir] = rootrel
    
    tlen = None
    result = None
    
    if rootrel and cache.multiDB != None:
      tlen,result = cache.multiDB.getTime( rootrel, testkey, platid )
    
    if tlen == None and rootrel:
      
      # look for runtimes in the test source tree
      
      d = testspec.getDirectory()
      if not cache.srcdirs.has_key(d):
        
        while tlen == None:
          f = os.path.join( d, runtimes_filename )
          cache.srcdirs[d] = None
          if os.path.exists(f):
            try:
              fmt,vers,hdr,nskip = read_file_header( f )
            except:
              fmt = None
            if fmt and fmt == 'results':
              cache.testDB.mergeRuntimes( f )
              break
          
          nd = os.path.dirname(d)
          if d == nd or not nd or nd == '/' or cache.srcdirs.has_key(nd):
            break
          d = nd
      
      tlen = cache.testDB.getTime( rootrel, testkey )
    
    return tlen, result


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

if __name__ == "__main__":
    results_main()
