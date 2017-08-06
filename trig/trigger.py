#!/usr/bin/env python

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import traceback
import re
import glob
import time
import subprocess
import getopt
import signal


help_string = \
"""
USAGE
    trigger.py [OPTIONS] -r <directory> [jobs [jobs ...] ]

SYNOPSIS

    This is a job script launch, logging, and monitoring tool.  Job scripts
specify a launch time of day, day of week, etc using a comment at the top of
the script.  When a job is launched, all output is logged (to files in the
directory specified by the -r option).  The arguments to this script are the
job files or directories containing the job files.

    This script should be placed in a cron table so that it is run every five
minutes or so.  There is a built in mechanism to only allow one trigger.py to
run in the same -r directory at any one time.

    The 'jobs' arguments can either be directories or glob patterns.  If a
directory, files that match the pattern "job_*.py" in the directory are
globbed.  If no 'jobs' arguments are given, the current working directory is
assumed.

OPTIONS

  -r <directory> : run directory (required); this is the directory that
                   contains the main log file as well as the individual job
                   log directories

  -C <directory> : change to this directory first thing;  relative paths given
                   by -r and the 'jobs' arguments are affected

  -g <integer> : granularity in seconds (default 15); this is the time between
                 job file scans (which then may result in job launches)

  -a <integer> : seconds between activity log messages (default one hour);
                 a short message is periodically written to the log file in
                 order to detect hangs; this is the time between messages

  -S : show errors; by default, exceptions are suppressed (although they are
       logged once logging starts); this option will show exceptions, which
       can be useful for diagnosing startup errors

  -Q <integer> : quit after this number of seconds; used in unit testing

  -E <integer> : error reset value, in hours.  Job trigger syntax errors are
                 logged, so without a throttle, the same error can flood the
        log file.  To avoid this, the same error will not be logged repeatedly.
        After the number of hours given by the -E option, however, the same
        error will be logged again.  The default is one hour.

TRIGGER SYNTAX:

    Job scripts are only executed if a JOB TRIGGER specification is provided
at the top of the script.  One or more lines must exist with this syntax:

# JOB TRIGGER <specification string>

The parsing for job triggers will stop at the first non-comment, non-empty
line.  So the job trigger specification must occur before such a line.

To run every day at one or more specified times, use:

    <time> [, <time> [, ...] ]

where the <time> syntax can be a number of hours past midnight, such as "1" or
"18".  It can be a 12 hour time, such as "1am" or "1:30am" or "6:30pm".  It can
be military time, such as "1:00" or "18:30" or "22:00".

To run on a particular day of the week, use:

    <DOW> [, <DOW> [, ...] ] [ <time> [, <time> ;, ...] ]

where <DOW> is a day of the week, such as "Monday", "monday", "Mon", "mon".
A time of day specification is optional, and if not given, 5 seconds past
midnight is assumed.

To run every hour on the hour, use:

    hourly

To run every hour at a specified number of minutes past the hour, use:

    hourly <minute> [, <minute> [, ...] ]

where <minute> is an integer number of minutes past the hour.  For example,
"hourly 0, 20, 40" will trigger on the hour, 20 minutes past the hour, and 40
minutes past the hour.

To run on the first day of each month, use:

    monthly [ <time> ]

If a <time> specification is not given, then it will run at 5 seconds past
midnight.

To run on the first day of the week of each month, use:

    monthly <DOW> [ <time> ]

For example, "monthly Mon" will run on the first Monday of each month at 5
seconds past midnight.  And "monthly sun 1am" will run on the first Sunday of
each month at one AM.
"""


DEFAULT_GRANULARITY = 15
DEFAULT_ACTIVITY = 60*60  # one hour
DEFAULT_ERROR_REPEAT = 1  # hours


def main( arglist ):
    """
    TODO:   - could check if a checkRun() takes longer than window and if so
              then print a warning about possible missed job triggers
    """
    optL,argL = getopt.getopt( arglist, 'hSr:C:g:Q:a:E:', ['help'] )

    optD = {}
    for n,v in optL:
        if n in ['-g','-Q','-a']:
            v = int( v )
            assert v > 0
        optD[n] = v

    if '-h' in optD or '--help' in optD:
        print3( help_string.rstrip() )
        return

    assert '-r' in optD, "the -r option is required"

    if '-S' in optD:
        if '-C' in optD:
            os.chdir( optD['-C'] )
        if activate( optD, argL ):
            mainloop( optD, argL )
    else:
        try:
            if '-C' in optD:
                os.chdir( optD['-C'] )
            if activate( optD, argL ):
                mainloop( optD, argL )
        except:
            pass


def activate( optD, argL ):
    """
    Returns False if there is already a trigger process running and active.
    It does this by reading the trigger.log file and checking date stamps.
    """
    logdir = os.path.abspath( optD['-r'] )
    logfile = os.path.join( logdir, 'trigger.log' )

    if os.path.exists( logfile ):

        last = None
        fp = open( logfile, 'r' )
        while True:
            logL = logreadline( fp )
            if not logL:
                break
            # look for startup and alive messages
            if len( logL ) > 1:
                L = logL[2].split()
                if len(logL) >= 3 and len(L) == 2 and \
                   (logL[1] == 'startup' or logL[1] == 'alive') and \
                   L[0].startswith( 'mach=' ) and L[1].startswith( 'pid=' ):
                    try:
                        tm = logL[0]
                        mach = L[0].split('mach=',1)[1]
                        assert mach
                        pid = int( L[1].split('pid=',1)[1] )
                    except:
                        pass  # hopefully ignoring corrupted messages is ok
                    else:
                        last = ( tm, mach, pid )
        fp.close()

        if last != None:
            tm,mach,pid = last

            ps = None
            if mach == os.uname()[1]:
                ps = processes( pid=pid ).strip()

            if ps == None or ps:
                # process is on another machine or the process exists on this
                # machine; in either case, determine if the last activity is
                # recent enough
                tactive = optD.get( '-a', DEFAULT_ACTIVITY )
                tgrain = optD.get( '-g', DEFAULT_GRANULARITY )
                tspan = max( 3*tgrain, 3*tactive )
                if time.time() - tm < tspan:
                    # the only return of False from this function; it means
                    # the last active message in the log file is too long ago
                    # (the assumption is that it is hung somehow)
                    return False

    return True


readpat = re.compile( r'\[(Mon|Tue|Wed|Thu|Fri|Sat|Sun)([^]]*20[0-9][0-9]\])+?' )

def logreadline( fp ):
    """
    Given an open file pointer, this will read one printlog() line (which may
    contain multiple newlines).  Returns a list

        [ seconds since epoch, arg1, arg2, ... ]

    or None if there are no more lines in the file.
    """
    val = None

    try:
        line = None
        while True:

            if line == None:
                line = fp.readline()
            if not line:
                break

            val = None
            try:
                line = line.rstrip()
                m = readpat.match( line )
                if m != None:
                    L = line[m.end():].strip().split( ' ', 1 )
                    n = int( L.pop(0) )
                    assert n < 1000  # if large, probably corruption
                    ts = line[:m.end()].strip().strip('[').strip(']')
                    tm = time.mktime( time.strptime( ts ) )
                    val = [ tm ]
                    if n > 0:
                        aL = L[0].split( ':', 1 )
                        val.append( aL[0].strip() )
                        if n > 1:
                            val.append( aL[1].strip() )
            except:
                val = None
            line = None

            if val != None:
                if n > 2:
                    for i in range(n-2):
                        line = fp.readline()
                        assert line
                        if line.startswith( '    ' ):
                            val.append( line[4:].rstrip() )
                        else:
                            val = None
                            break
                if val != None:
                    break
    except:
        val = None

    return val


# use signals to implement a timeout mechanism
class TimeoutException(Exception): pass
def timeout_handler( signum, frame ):
    raise TimeoutException( "timeout" )


def mainloop( optD, argL ):
    """
    """
    logdir = os.path.abspath( optD['-r'] )
    logfile = os.path.join( logdir, 'trigger.log' )

    redir = Redirect( logfile, append=True )

    printlog( 'startup', 'mach='+os.uname()[1]+' pid='+str( os.getpid() ),
                         'argv='+repr( sys.argv ) )

    signal.signal( signal.SIGALRM, timeout_handler )

    tgrain = optD.get( '-g', DEFAULT_GRANULARITY )
    tlimit = optD.get( '-Q', None )
    tactive = optD.get( '-a', DEFAULT_ACTIVITY )
    v = optD.get( '-E', DEFAULT_ERROR_REPEAT )
    erreset = int( max( 0, float(v) ) * 60*60 )

    if len(argL) == 0:
        argL = ['.']
    argL = [ os.path.abspath(p) for p in argL ]

    rjobs = FileJobs( logdir, argL, erreset )

    try:
        tlimit_0 = time.time()
        tactive_0 = time.time()
        while tlimit == None or time.time()-tlimit_0 < tlimit:

            # use alarm to timeout the file and subprocess work (resilience)
            signal.alarm( 2*tgrain )
            rjobs.checkRun( tgrain )
            signal.alarm(0)

            if time.time()-tactive_0 > tactive:
                # log an "I'm alive" message every so often
                printlog( 'alive', 'mach='+os.uname()[1] + \
                                   ' pid='+str( os.getpid() ) )
                tactive_0 = time.time()

            time.sleep( tgrain )
    except:
        # all exceptions are caught and logged, before returning (exiting)
        traceback.print_exc()
        printlog( 'exception', str( sys.exc_info()[1] ) )
        rjobs.waitChildren()

    redir.close()


#########################################################################

class FileJobs:
    
    def __init__(self, logdir, jobsrcs, error_reset):
        """
        """
        self.logdir = logdir
        self.jobsrcs = jobsrcs
        self.erreset = error_reset

        self.trigpat = re.compile( ' *# *JOB TRIGGER *[=:]' )

        self.recent = {}  # maps job filename to launch time
        self.jobs = {}  # maps log directory to subprocess.Popen instance
        self.errD = {}  # maps job files to dictionaries, which map error
                        # strings to time stamps

    def checkRun(self, granularity):
        """
        Scans the root job source directories for files named job_*.py and
        for each one calls self.processFile().
        """
        self.reapChildren()

        for src in self.jobsrcs:
            if os.path.isdir( src ):
                src = os.path.join( src, 'job_*.py' )
            for f in glob.glob( src ):
                curtm = int( time.time() )
                self.pruneJobs( curtm, granularity )
                self.pruneErrors( curtm, granularity, f )
                self.processFile( curtm, granularity, f )

    def pruneJobs(self, tm, granularity):
        """
        Jobs that ran more than 3 grains in the past are removed from the
        recent job dict.  Those jobs will then be allowed to run again
        depending on their trigger specifications.
        """
        D = {}
        for jfile,jt in self.recent.items():
            if jt > tm - 3*granularity:
                D[jfile] = jt
        self.recent = D

    def pruneErrors(self, curtm, granularity, jfile):
        """
        """
        jD = self.errD.get( jfile, None )
        if jD != None:
            try:
                ft = os.path.getmtime( jfile )
            except:
                self.errD.pop( jfile )
            else:
                if ft + granularity > curtm:
                    # recent enough time stamp, so reset history for the file
                    self.errD.pop( jfile )
                else:
                    # prune entries for this file if they are too old
                    newD = {}
                    for err,tm in jD.items():
                        if tm + self.erreset > curtm:
                            newD[ err ] = tm
                    self.errD[ jfile ] = newD

    def processFile(self, curtm, granularity, jfile):
        """
        Reads the given job file for the JOB TRIGGER specification, and if
        time, the job is run using self.launchFile().
        """
        joberrD = self.errD.get( jfile, None )
        if joberrD == None:
            joberrD = {}
            self.errD[ jfile ] = joberrD

        try:
            if jfile not in self.recent:
                for errL in self.errD.get( jfile, [] ):
                    pass
                trigL = []
                fp = open( jfile, 'r' )
                try:
                    line = fp.readline()
                    while line:
                        line = line.strip()
                        m = self.trigpat.match( line )
                        if m:
                            trigL.append( line[m.end():].split('#')[0].strip() )
                        elif line and not line.startswith('#'):
                            break
                        elif line.startswith( '#TRIGGER_TEST_HANG_READ=' ):
                            time.sleep( int( line.split( '=' )[1] ) )
                        line = fp.readline()
                finally:
                    fp.close()

                for trig in trigL:
                    trigtm = next_trigger_time( trig, curtm )

                    if trigtm and trigtm < curtm + 2*granularity:
                        self.launchFile( jfile, trig )
                        self.recent[jfile] = time.time()
                        break

        except TimeoutException:
            raise
        except:
            err = str( sys.exc_info()[1] )
            if err not in joberrD:
                traceback.print_exc()
                printlog( 'exception', 'while processing file '+jfile,
                                       'exc='+err )
                joberrD[ err ] = time.time()

    def launchFile(self, jobfile, trigspec ):
        """
        Executes the given root job file as a subprocess.
        """
        # determine and make the job log subdirectory
        name = os.path.basename( jobfile )
        date = time.strftime( "%a_%b_%d_%Y_%H:%M:%S_%Z" )
        joblogdir = os.path.join( self.logdir, name+'_'+date )
        os.mkdir( joblogdir )
        os.chdir( joblogdir )
        logfp = open( 'log.txt', 'w' )

        printlog( 'launch', 'trigger='+trigspec,
                            'file='+jobfile,
                            'logdir='+joblogdir )

        # TODO: allow the scripts to be bash or just executable

        p = subprocess.Popen( [sys.executable,jobfile],
                              stdout=logfp.fileno(),
                              stderr=subprocess.STDOUT )

        self.jobs[ joblogdir ] = ( jobfile, p )
        logfp.close()

        # ensure that each new job gets a different time stamp
        time.sleep( 1 )

    def reapChildren(self):
        """
        Checks each subprocess for completion.
        """
        pD = {}
        for d in self.jobs.keys():
            jf,p = self.jobs[d]
            x = p.poll()
            if x == None:
                pD[d] = ( jf, p )
            else:
                printlog( 'finish', 'exit='+str(x),
                                    'file='+jf,
                                    'logdir='+d )
        self.jobs = pD

    def waitChildren(self):
        """
        Waits on each subprocess for completion.
        """
        for d in self.jobs.keys():
            jf,p = self.jobs[d]
            x = p.wait()
            printlog( 'finish', 'exit='+str(x),
                                'file='+jf,
                                'logdir='+d )
        self.jobs = {}


def next_trigger_time( spec, curtm ):
    """
    Given a string specification 'spec', this returns seconds since epoch
    for the next trigger event.  If no event will occur on the current day or
    the next day, then None is returned.

    See the help page for the syntax.
    """
    tm = None
    if spec:

        # current midnight and day of week
        epoch0 = chop_midnight( curtm )
        dow0 = day_of_week( curtm )

        # upcoming midnight and day of week
        epoch1 = chop_midnight( epoch0 + 26*60*60 )
        dow1 = day_of_week( epoch0 + 26*60*60 )

        sL = [ s.strip() for s in spec.split(',') ]
        s0 = sL[0].split()[0].lower()

        if s0 == 'hourly':
            epoch_hr0 = chop_hour( curtm )
            epoch_hr1 = chop_hour( epoch_hr0 + 65*60 )

            # a comma after hourly is optional, so handle both cases here
            L = sL[0].split( None, 1 )
            if len(L) > 1:
                sL[0] = L[1].strip()
            else:
                sL.pop( 0 )
            if len(sL) == 0:
                sL.append( '0' )  # default is on the hour

            for s in sL:
                try:
                    m = int( float(s) * 60 + 0.5 )
                    # TODO: could also allow minutes:seconds format here
                except:
                    raise Exception( 'bad number of minutes syntax: '+s )

                tm = check_time( curtm, epoch_hr0 + m, tm )
                tm = check_time( curtm, epoch_hr1 + m, tm )

        elif s0 == 'monthly':

            d0 = first_day_of_month( epoch0+10*60*60 )
            d1 = first_day_of_month( d0 + 45*24*60*60 + 10*60*60 )

            # a comma after monthly is optional, so handle both cases here
            L = sL[0].split( None, 1 )
            if len(L) > 1:
                sL[0] = L[1].strip()
            else:
                sL.pop( 0 )

            dowL = []
            sL = recurse_dow( sL, dowL )
            dow = None
            if len(dowL) == 1:
                dow = dowL[0]
                if dow not in daysofweek:
                    raise Exception( "unknown day of week: "+dowL[0] )
            elif len(dowL) > 1:
                raise Exception( "only zero or one day-of-week allowed: "+spec )

            tod = 5
            if len(sL) > 1:
                raise Exception( "only zero or one time-of-day allowed: "+spec )
            elif len(sL) == 1:
                try:
                    tod = seconds_since_midnight( sL[0] )
                except:
                    raise Exception( 'bad time syntax: '+sL[0] )

            if dow == None:
                tm = check_time( curtm, d0+tod, tm )
                tm = check_time( curtm, d1+tod, tm )

            else:
                t = next_day_of_week( dow, d0 + 10*60*60 )
                tm = check_time( curtm, t+tod, tm )
                t = next_day_of_week( dow, d1 + 10*60*60 )
                tm = check_time( curtm, t+tod, tm )

        else:
            # determine the days of week for which this specification is valid
            dowL = []
            sL = recurse_dow( sL, dowL )
            if len(dowL) == 0:
                # no spec means no restriction, so include all days of week
                dowL = daysofweekL

            if len(sL) == 0:
                if dow0 in dowL:
                    # 5 seconds past midnight
                    tm = check_time( curtm, epoch0 + 5, tm )
                if dow1 in dowL:
                    tm = check_time( curtm, epoch1 + 5, tm )

            else:
                for s in sL:
                    try:
                        t = seconds_since_midnight( s )
                    except:
                        raise Exception( 'bad time syntax: '+s )

                    if dow0 in dowL:
                        tm = check_time( curtm, epoch0 + t, tm )
                    if dow1 in dowL:
                        tm = check_time( curtm, epoch1 + t, tm )
    
    return tm


def check_time( curtm, newtm, prevtm ):
    """
    If 'newtm' is >= 'curtm', then the minimum of 'newtm' and 'prevtm' is
    returned.
    """
    if newtm >= curtm:
        if prevtm == None:
            return newtm
        return min( prevtm, newtm )
    return prevtm


daysofweek = set( 'mon tue wed thu fri sat sun'.split() )
daysofweekL = 'mon tue wed thu fri sat sun'.split()


def recurse_dow( sL, dowL ):
    """
    Removes leading days-of-the-week strings from the list 'sL' and adds them
    to the 'dowL' list.  Returns the remaining strings in a list.  The days
    in 'dowL' are abbreviated and lower case.
    """
    if len(sL) > 0:
        s = sL.pop(0)
        if s[:3].lower() in daysofweek:
            dowL.append( s[:3].lower() )
            iL = s.split( None, 1 )
            if len(iL) > 1:
                s = iL[1]
                return recurse_dow( [s]+sL, dowL )
            
            return recurse_dow( []+sL, dowL )

        return [s]+sL

    return []


def chop_midnight( tsecs ):
    """
    Returns the epoch time at midnight for the given day.
    """
    tup = time.localtime( tsecs )
    tup = ( tup[0], tup[1], tup[2], 0, 0, 0, tup[6], tup[7], tup[8] )
    return int( time.mktime( tup ) + 0.5 )


def chop_hour( tsecs ):
    """
    Returns the epoch time at the most recent hour for the given time.
    """
    tup = time.localtime( tsecs )
    tup = ( tup[0], tup[1], tup[2], tup[3], 0, 0, tup[6], tup[7], tup[8] )
    return int( time.mktime( tup ) + 0.5 )


def day_of_week( tsecs ):
    """
    Returns the day of the week for the given day, in lower case and first
    three letters.
    """
    tup = time.localtime( tsecs )
    return daysofweekL[ tup[6] ]


def first_day_of_month( tsecs ):
    """
    Returns the epoch time at midnight of the first day of the month.
    """
    for i in range(40):
        tup = time.localtime( tsecs )
        if tup[2] == 1:
            # found first day of the month; now chop to midnight
            return chop_midnight( tsecs )
        tsecs -= 24*60*60

    raise Exception( 'the algorithm failed' )


def next_day_of_week( dow, tsecs ):
    """
    Returns the epoch time at midnight of the next 'dow' day of the week.
    """
    for i in range(40):
        tup = time.localtime( tsecs )
        if dow == daysofweekL[ tup[6] ]:
            # found first upcoming day; now chop to midnight
            return chop_midnight( tsecs )
        tsecs += 24*60*60

    raise Exception( 'the algorithm failed' )


def seconds_since_midnight( time_spec ):
    """
    Interprets the argument as a time of day specification.  The 'time_spec'
    can be a number between zero and 24 or a string containing am, pm, and
    colons (such as "3pm" or "21:30").  If the interpretation fails, an
    exception is raised.  Returns the number of seconds since midnight.
    """
    orig = time_spec

    try:
        if type(time_spec) == type(''):

            assert '-' not in time_spec
            
            ampm = None
            time_spec = time_spec.strip()
            if time_spec[-2:].lower() == 'am':
              ampm = "am"
              time_spec = time_spec[:-2]
            elif time_spec[-2:].lower() == 'pm':
              ampm = "pm"
              time_spec = time_spec[:-2]
            elif time_spec[-1:].lower() == 'a':
              ampm = "am"
              time_spec = time_spec[:-1]
            elif time_spec[-1:].lower() == 'p':
              ampm = "pm"
              time_spec = time_spec[:-1]
            
            L = [ s.strip() for s in time_spec.split(':') ]
            assert len(L) == 1 or len(L) == 2 or len(L) == 3
            L2 = [ int(i) for i in L ]
            
            hr = L2[0]
            mn = 0
            sc = 0
            
            if ampm:
                if ampm == 'am':
                    if hr == 12:
                        hr = 0
                    else:
                        assert hr < 12
                else:
                    if hr == 12:
                        hr = 12
                    else:
                        assert hr < 12
                        hr += 12
            else:
                assert hr < 24
            
            if len(L2) > 1:
                mn = L2[1]
                assert mn < 60
            
            if len(L2) > 2:
                sc = L2[2]
                assert sc < 60

            nsecs = hr*60*60 + mn*60 + sc
              
        else:
            # assume number of hours since midnight
            assert not time_spec < 0 and time_spec < 24
            nsecs = int(time_spec)*60*60

    except:
        raise Exception( "invalid time-of-day specification: "+str(orig) )

    return nsecs


#########################################################################

def print3( *args ):
    """
    Python 2 & 3 compatible print function.
    """
    s = ' '.join( [ str(x) for x in args ] )
    sys.stdout.write( s + '\n' )
    sys.stdout.flush()


def printlog( *args ):
    """
    Prints the date to stdout followed by the arguments in a human readable
    format but also one that can be read by the logreadline() function.
    """
    s = '['+time.ctime()+'] '+str(len(args))
    if len(args) > 0: s += ' '+str(args[0])+':'
    if len(args) > 1: s += ' '+str(args[1])
    for v in args[2:]:
        s += '\n    '+str(v)
    sys.stdout.write( s + '\n' )
    sys.stdout.flush()


class Redirect:
    """
    A convenience class to redirect the current process's stdout & stderr
    to a file.
    """
    
    def __init__(self, filename, append=False):
        """
        If the 'append' value is True, the filename is appended rather than
        overwritten.  Call the close() method to stop the redirection.
        """
        self.orig_fname = filename
        self.fname = filename

        mode = "w"
        if append: mode = "a"

        self.filep = open( self.fname, mode )
        self.save_stdout_fd = os.dup(1)
        self.save_stderr_fd = os.dup(2)
        os.dup2( self.filep.fileno(), 1 )
        os.dup2( self.filep.fileno(), 2 )
    
    def close(self):
        """
        Call this to stop the redirection and reset stdout & stderr.
        """
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2( self.save_stdout_fd, 1 )
        os.dup2( self.save_stderr_fd, 2 )
        os.close( self.save_stdout_fd )
        os.close( self.save_stderr_fd )
        self.filep.close()


def processes( pid=None, user=None, showall=False, fields=None, noheader=True ):
    """
    The 'fields' defaults to 'user,pid,ppid,etime,pcpu,vsz,args'.
    """
    plat = sys.platform.lower()
    if fields == None:
        fields = 'user,pid,ppid,etime,pcpu,vsz,args'
    if plat.startswith( 'darwin' ):
        cmd = 'ps -o ' + fields.replace( 'args', 'command' )
    elif plat.startswith( 'sunos' ):
        cmd = '/usr/bin/ps -o ' + fields
    else:
        cmd = 'ps -o ' + fields

    if pid != None:
        cmd += ' -p '+str(pid)
    elif user:
        cmd += ' -u '+str(user)
    elif showall:
        cmd += ' -e'

    x,out = runout( cmd )

    if noheader:
        # strip off first non-empty line
        out = out.strip() + os.linesep
        i = 0
        while i < len(out):
            if out[i:].startswith( os.linesep ):
                out = out[i:].lstrip()
                break
            i += 1

    out = out.strip()
    if out:
        out += os.linesep

    return out


def runout( cmd, include_stderr=False ):
    """
    Run a command and return the exit status & output as a pair.
    """
    argD = {}

    if type(cmd) == type(''):
        argD['shell'] = True

    fp = None
    argD['stdout'] = subprocess.PIPE
    if include_stderr:
        argD['stderr'] = subprocess.STDOUT
    else:
        fp = open( os.devnull, 'w' )
        argD['stderr'] = fp.fileno()

    try:
        p = subprocess.Popen( cmd, **argD )
        out,err = p.communicate()
    except:
        fp.close()
        raise

    if fp != None:
        fp.close()

    x = p.returncode

    if type(out) != type(''):
        out = out.decode()  # convert bytes to a string

    return x, out


#########################################################################

mydir = os.path.dirname( os.path.abspath( __file__ ) )

if __name__ == "__main__":
    main( sys.argv[1:] )
