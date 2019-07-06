#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import time
import glob

import libvvtest.fmtresults as fmtresults
import libvvtest.reports as reports


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
    except Exception:
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
    
    mr = fmtresults.MultiResults()
    if os.path.exists( fmtresults.multiruntimes_filename ):
        mr.readFile( fmtresults.multiruntimes_filename )
    
    warnL = []
    newtest = False
    for f in fileL:
        try:
            fmt,vers,hdr,nskip = fmtresults.read_file_header( f )
        except Exception:
            warnL.append( "skipping results file: " + f + \
                          ", Exception = " + str(sys.exc_info()[1]) )
        else:
            
            if fmt and fmt == 'results':
                if fmtresults.merge_results_file( mr, f, warnL, dcut, xopt, wopt ):
                    newtest = True
            
            elif fmt and fmt == 'multi':
                if fmtresults.merge_multi_file( mr, f, warnL, dcut, xopt, wopt ):
                    newtest = True
            
            else:
                warnL.append( "skipping results source file due to " + \
                              "corrupt or unknown format: " + f )
    
    if newtest:
        mr.writeFile( fmtresults.multiruntimes_filename )
    
    return warnL


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
            cutoff = fmtresults.date_round_down( int( time.time() - dval*24*60*60 ) )
            newL = []
            for f in fL:
                ft,plat,opts,tag = fmtresults.parse_results_filename( f )
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
                ft,plat,opts,tag = fmtresults.parse_results_filename( f )
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
                ft,plat,opts,tag = fmtresults.parse_results_filename( f )
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
                ft,plat,opts,tag = fmtresults.parse_results_filename( f )
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
                ft,plat,opts,tag = fmtresults.parse_results_filename( f )
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
    rootrel = fmtresults.file_rootrel( cwd )
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
        fmt,vers,hdr,nskip = fmtresults.read_file_header( srcf )
      except Exception:
        warnL.append( "Warning: skipping results file: " + srcf + \
                     ", Exception = " + str(sys.exc_info()[1]) )
      else:
        if fmt and fmt == 'results':
          src = fmtresults.TestResults()
          try:
            src.readResults(srcf)
          except Exception:
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
          src = fmtresults.MultiResults()
          try:
            src.readFile(srcf)
          except Exception:
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
    
    tr = fmtresults.TestResults()
    rtdirD = {}  # runtimes directory -> root relative path
    
    # read any existing runtimes files at or below the CWD
    def read_src_dir( trs, rtD, msgs, dirname ):
        rtf = os.path.join( dirname, fmtresults.runtimes_filename )
        if os.path.isfile(rtf):
            try:
                fmt,vers,hdr,nskip = fmtresults.read_file_header( rtf )
                rr = hdr.get( 'ROOT_RELATIVE', None )
                trs.mergeRuntimes(rtf)
            except Exception:
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
      tr = fmtresults.TestResults()
    
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
    fmt,vers,hdr,nskip = fmtresults.read_file_header( fname )
    
    if fmt and fmt == 'results':
      src = fmtresults.TestResults()
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
          print3( fmtresults.make_attr_string(aD), d+'/'+tn )
    
    elif fmt and fmt == 'multi':
      src = fmtresults.MultiResults()
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
          print3( fmtresults.make_attr_string(aD), pc, d+'/'+tn )
    
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
      fname = os.path.join( path, fmtresults.runtimes_filename )
      if os.path.exists(fname):
        path = fname
      else:
        raise Exception( "Specified directory does not contain a " + \
                         "test source tree runtimes file: " + path )
    
    if '-p' not in optD:
      msgL.append( "Warning: nothing to do without the -p option " + \
                   "(currently)" )
    
    fmt,vers,hdr,nskip = fmtresults.read_file_header( path )
    if fmt and fmt == 'results':
      if '-p' in optD:
        msgL.append( "Warning: the -p option has no effect on results files" )
      else:
        pass
    elif fmt and fmt == 'multi':
      if '-p' in optD:
        xpc = optD['-p']
        mr = fmtresults.MultiResults()
        src = fmtresults.MultiResults()
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

    plug = get_results_plugin( optD )

    # this collects the files and applies filters
    fileG = []
    process_files( optD, fileL, fileG, default_d=15 )

    rmat = read_all_results_files( fileL, fileG, warnL )

    if len( rmat.testruns() ) == 0:
        print3( 'No results files to process (after filtering)' )
        return warnL

    # the DateMap object helps format the test results output
    dmap = create_date_map( curtm, optD.get( '-d', None ), rmat )

    if '--html' in optD:
        htmloc = optD['--html']
        webloc = optD.get( '--webloc', None )
        reporter = HTMLReporter( rmat, dmap, plug, htmloc, webloc )
    else:
        reporter = ConsoleReporter( rmat, dmap )

    make_report_from_results( reporter, rmat, maxreport, showage, curtm )

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


def read_all_results_files( files, globfiles, warnL ):
    ""
    rmat = reports.ResultsMatrix()

    for f in files:
        ftime,tr,rkey = fmtresults.read_results_file( f, warnL )
        if ftime != None:
            tr.detail_ok = True  # inject a boolean flag to do detailing
            rmat.add( ftime, tr, rkey )

    for f in globfiles:
        ftime,tr,rkey = fmtresults.read_results_file( f, warnL )
        if ftime != None:
            tr.detail_ok = False  # inject a boolean flag to NOT do detailing
            rmat.add( ftime, tr, rkey )

    return rmat


def create_date_map( curtm, daysback, rmat ):
    ""
    if daysback == None:
        dmin = rmat.minFileDate()
    else:
        df = fmtresults.date_round_down( curtm-optD['-d']*24*60*60 )
        dmin = min( df, rmat.minFileDate() )

    dmax = max(  0, rmat.maxFileDate() )

    dmap = reports.DateMap( dmin, dmax )

    return dmap


def mark_tests_for_detailing( redD, tr, tr2, started,
                              fdate, curtm,
                              maxreport, showage ):
    ""
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


def make_report_from_results( reporter, rmat, maxreport, showage, curtm ):
    ""
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

    reporter.writePreamble()

    redD = {}
    for rkey in rmat.testruns():

        fdate,tr,tr2,started = rmat.latestResults( rkey )

        D,nm = tr.collectResults( tdd=True )
        tddmarks.update( D )

        reporter.processDetails( rkey )

        mark_tests_for_detailing( redD, tr, tr2, started,
                                  fdate, curtm,
                                  maxreport, showage )

    reporter.finalizeRollups( rkey, redD )

    # for each test that fail/diff/timeout, collect and print the history of
    # the test on each plat/cplr and for each results date stamp
    reporter.writeDetailedTestGroups( tddmarks, redD )


class HTMLReporter:

    def __init__(self, rmat, dmap, plug, htmloc, webloc):
        ""
        self.rmat = rmat
        self.dmap = dmap
        self.plug = plug
        self.htmloc = htmloc
        self.webloc = webloc

        self.primary = []
        self.secondary = []
        self.tdd = []
        self.runlist = []

        self.dashfp = None

    def writePreamble(self):
        ""
        pass

    def processDetails(self, rkey):
        ""
        loc = self.rmat.location(rkey)
        rundates = get_run_dates( self.rmat, rkey )
        fdate,tr,tr2,started = self.rmat.latestResults( rkey )
        if tr.detail_ok:
            self.primary.append( (rkey, tr.getCounts(), rundates) )
        else:
            self.secondary.append( (rkey, tr.getCounts(), rundates) )
        self.tdd.append( (rkey, tr.getCounts(tdd=True), rundates) )
        self.runlist.append( (rkey,fdate,tr) )

    def finalizeRollups(self, rkey, redD):
        ""
        print3( reports.dashboard_preamble )
        if self.webloc != None:
            print3( 'Go to the <a href="'+self.webloc+ '">full report</a>.\n<br>\n' )
            loc = os.path.join( os.path.dirname( self.webloc ), 'testrun.html' )
            print3( 'Also the <a href="'+loc+'">machine summaries</a>.\n<br>\n' )

        reports.html_start_rollup( sys.stdout, self.dmap, "Production Rollup", 7 )
        for rkey,cnts,rL in self.primary:
            reports.html_rollup_line( sys.stdout, self.plug, self.dmap, rkey, cnts, rL, 7 )
        reports.html_end_rollup( sys.stdout )
        
        if len(self.secondary) > 0:
            reports.html_start_rollup( sys.stdout, self.dmap, "Secondary Rollup", 7 )
            for rkey,cnts,rL in self.secondary:
                reports.html_rollup_line( sys.stdout, self.plug, self.dmap, rkey, cnts, rL, 7 )
            reports.html_end_rollup( sys.stdout )
        
        print3( '\n<br>\n<hr>\n' )

        fn = os.path.join( self.htmloc, 'dash.html' )
        self.dashfp = open( fn, 'w' )
        self.dashfp.write( reports.dashboard_preamble )
        reports.html_start_rollup( self.dashfp, self.dmap, "Production Rollup" )
        for rkey,cnts,rL in self.primary:
            reports.html_rollup_line( self.dashfp, self.plug, self.dmap, rkey, cnts, rL )
        reports.html_end_rollup( self.dashfp )
        
        if len(self.secondary) > 0:
            reports.html_start_rollup( self.dashfp, self.dmap, "Secondary Rollup" )
            for rkey,cnts,rL in self.secondary:
                reports.html_rollup_line( self.dashfp, self.plug, self.dmap, rkey, cnts, rL )
            reports.html_end_rollup( self.dashfp )
        
        if len(self.tdd) > 0:
            reports.html_start_rollup( self.dashfp, self.dmap, "TDD Rollup" )
            for rkey,cnts,rL in self.tdd:
                if sum(cnts) > 0:
                    reports.html_rollup_line( self.dashfp, self.plug, self.dmap, rkey, cnts, rL )
            reports.html_end_rollup( self.dashfp )
        
        self.dashfp.write( '\n<br>\n<hr>\n' )

        if len(redD) > 0:
            self.dashfp.write( \
                '<h2>Below are the tests that failed or diffed in ' + \
                'the most recent test sequence of at least one ' + \
                'Production Rollup platform combination.</h2>' + \
                '\n<br>\n<hr>\n' )

    def writeDetailedTestGroups(self, tddmarks, redD):
        ""
        detailed = {}
        tnum = 1

        redL = list( redD.keys() )
        redL.sort()
        for d,tn in redL:

            if (d,tn) in tddmarks:
                continue
            
            reports.html_start_detail( self.dashfp, self.dmap, d+'/'+tn, tnum )
            detailed[ d+'/'+tn ] = tnum
            tnum += 1

            res = redD[ (d,tn) ]
            for rkey in self.rmat.testruns( d, tn ):
                tests,location = self.rmat.resultsForTest( rkey, d, tn, result=res )
                rL = test_list_with_results_details( tests )

                reports.html_detail_line( self.dashfp, self.dmap, rkey, rL )

            self.dashfp.write( '\n</table>\n' )
        
        self.dashfp.write( reports.dashboard_close )
        self.dashfp.close()

        fn = os.path.join( self.htmloc, 'testrun.html' )
        trunfp = open( fn, 'w' )
        trunfp.write( reports.dashboard_preamble )
        for rkey,fdate,tr in self.runlist:
            reports.write_testrun_entry( trunfp, self.plug, rkey, fdate, tr, detailed )
        trunfp.write( reports.dashboard_close )
        trunfp.close()


class ConsoleReporter:

    def __init__(self, rmat, dmap):
        ""
        self.rmat = rmat
        self.dmap = dmap

        self.keylen = 0

    def writePreamble(self):
        ""
        # write out the summary for each platform/options/tag combination
        print3( "A summary by platform/compiler is next." )
        print3( "vvtest run codes: s=started, r=ran and finished." )

    def processDetails(self, rkey):
        ""
        # find max plat/cplr string length for below
        self.keylen = max( self.keylen, len(rkey) )

        rundates = get_run_dates( self.rmat, rkey )
        fdate,tr,tr2,started = self.rmat.latestResults( rkey )
        loc = self.rmat.location(rkey)
        hist = self.dmap.history(rundates)
        print3()
        print3( rkey, '@', loc )
        print3( '  ', self.dmap.legend() )
        print3( '  ', hist, '  ', tr.getSummary() )
        if not tr.detail_ok:
            s = '(tests for this platform/compiler are not detailed below)'
            print3( '  '+s )

    def finalizeRollups(self, rkey, redD):
        ""
        pass

    def writeDetailedTestGroups(self, tddmarks, redD):
        ""
        print3()
        print3( 'Tests that have diffed, failed, or timed out are next.' )
        print3( 'Result codes: p=pass, D=diff, F=fail, T=timeout, n=notrun' )
        print3()

        detailed = {}
        tnum = 1

        keyfmt = "   %-"+str(self.keylen)+"s"
        redL = list( redD.keys() )
        redL.sort()
        for d,tn in redL:

            if (d,tn) in tddmarks:
                continue

            # print the path to the test and the date legend
            print3( d+'/'+tn )
            print3( keyfmt % ' ', self.dmap.legend() )

            res = redD[ (d,tn) ]
            for rkey in self.rmat.testruns( d, tn ):
                tests,location = self.rmat.resultsForTest( rkey, d, tn, result=res )
                rL = test_list_with_results_details( tests )

                print3( keyfmt%rkey, self.dmap.history( rL ), location )

            print3()


def get_run_dates( rmat, rkey ):
    ""
    rundates = []

    for fdate,tr in rmat.resultsList( rkey ):
        if tr.inProgress(): rundates.append( (fdate,'start') )
        else:               rundates.append( (fdate,'ran') )

    return rundates


def test_list_with_results_details( tests ):
    ""
    rL = []

    for fd,aD in tests:
        if aD == None:
            rL.append( (fd,'start') )
        else:
            st = aD.get( 'state', '' )
            rs = aD.get( 'result', '' )
            if rs: rL.append( (fd,rs) )
            else: rL.append( (fd,st) )

    return rL


########################################################################

def print3( *args ):
    ""
    s = ' '.join( [ str(x) for x in args ] )
    sys.stdout.write( s + os.linesep )
    sys.stdout.flush()


def process_option( optD, option_name, value_type, *restrictions ):
    ""
    if option_name in optD:
        try:
            v = value_type( optD[option_name] )
        except Exception:
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
