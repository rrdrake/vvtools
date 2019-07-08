#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import time

from . import fmtresults


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
                        i = select_test_based_on_attributes(
                                    D[filedate],
                                    attrD,
                                    result )
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
                        i = select_test_based_on_attributes(
                                    maxloc[2],
                                    attrD,
                                    result )
                        if i > 0:
                            maxloc = [ filedate, loc, attrD ]
        
        L = list( D.items() )
        L.sort()

        if maxloc == None: loc = ''
        else:              loc = maxloc[1]
        
        return L,loc


def select_test_based_on_attributes( attrs1, attrs2, result ):
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

def read_all_results_files( files, globfiles, warnL ):
    ""
    rmat = ResultsMatrix()

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

    dmap = DateMap( dmin, dmax )

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
        print3( dashboard_preamble )
        if self.webloc != None:
            print3( 'Go to the <a href="'+self.webloc+ '">full report</a>.\n<br>\n' )
            loc = os.path.join( os.path.dirname( self.webloc ), 'testrun.html' )
            print3( 'Also the <a href="'+loc+'">machine summaries</a>.\n<br>\n' )

        html_start_rollup( sys.stdout, self.dmap, "Production Rollup", 7 )
        for rkey,cnts,rL in self.primary:
            html_rollup_line( sys.stdout, self.plug, self.dmap, rkey, cnts, rL, 7 )
        html_end_rollup( sys.stdout )
        
        if len(self.secondary) > 0:
            html_start_rollup( sys.stdout, self.dmap, "Secondary Rollup", 7 )
            for rkey,cnts,rL in self.secondary:
                html_rollup_line( sys.stdout, self.plug, self.dmap, rkey, cnts, rL, 7 )
            html_end_rollup( sys.stdout )
        
        print3( '\n<br>\n<hr>\n' )

        fn = os.path.join( self.htmloc, 'dash.html' )
        self.dashfp = open( fn, 'w' )
        self.dashfp.write( dashboard_preamble )
        html_start_rollup( self.dashfp, self.dmap, "Production Rollup" )
        for rkey,cnts,rL in self.primary:
            html_rollup_line( self.dashfp, self.plug, self.dmap, rkey, cnts, rL )
        html_end_rollup( self.dashfp )
        
        if len(self.secondary) > 0:
            html_start_rollup( self.dashfp, self.dmap, "Secondary Rollup" )
            for rkey,cnts,rL in self.secondary:
                html_rollup_line( self.dashfp, self.plug, self.dmap, rkey, cnts, rL )
            html_end_rollup( self.dashfp )
        
        if len(self.tdd) > 0:
            html_start_rollup( self.dashfp, self.dmap, "TDD Rollup" )
            for rkey,cnts,rL in self.tdd:
                if sum(cnts) > 0:
                    html_rollup_line( self.dashfp, self.plug, self.dmap, rkey, cnts, rL )
            html_end_rollup( self.dashfp )
        
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
            
            html_start_detail( self.dashfp, self.dmap, d+'/'+tn, tnum )
            detailed[ d+'/'+tn ] = tnum
            tnum += 1

            res = redD[ (d,tn) ]
            for rkey in self.rmat.testruns( d, tn ):
                tests,location = self.rmat.resultsForTest( rkey, d, tn, result=res )
                rL = test_list_with_results_details( tests )

                html_detail_line( self.dashfp, self.dmap, rkey, rL )

            self.dashfp.write( '\n</table>\n' )
        
        self.dashfp.write( dashboard_close )
        self.dashfp.close()

        fn = os.path.join( self.htmloc, 'testrun.html' )
        trunfp = open( fn, 'w' )
        trunfp.write( dashboard_preamble )
        for rkey,fdate,tr in self.runlist:
            write_testrun_entry( trunfp, self.plug, rkey, fdate, tr, detailed )
        trunfp.write( dashboard_close )
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


def print3( *args ):
    ""
    sys.stdout.write( ' '.join( [ str(x) for x in args ] ) + os.linesep )
    sys.stdout.flush()
