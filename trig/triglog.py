#!/usr/bin/env python

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import time
import traceback
import re


helpstr = \
"""
USAGE:
    triglog.py [OPTIONS] filename

SYNOPSIS:
    Reads the log files produced by trigger.py, runjob.py, and runcmd.py.
    The functional interface provides a tree of job objects, while the
    command line interface writes the tree to stdout.

OPTIONS:
    -h, --help      : this help

    -d <num days>   : only include top level jobs that started this many
                      days ago
"""

############################################################################

def main():

    import getopt
    optL,argL = getopt.getopt( sys.argv[1:], 'hd:',
                   longopts=['help'] )

    optD ={}
    for n,v in optL:
        if n == '-h' or n == '--help':
            print3( helpstr )
            return 0
        elif n in []:
            optD[n] = optD.get(n,[]) + [v]
        else:
            optD[n] = v

    age = None
    if '-d' in optD:
        try:
            age = float( optD['-d'] )
        except:
            print3( '*** triglog.py: the -d argument must be a number' )
            sys.exit(1)

    jobs = recurse_trigger_logs( argL, age )

    for jb in jobs:
        print_recurse( jb )


def recurse_trigger_logs( trigfiles, age=None ):
    """
    Reads one or more log files produced by trigger.py.  The jobs in each
    file are read and recursed.

    If 'age' is not None, it must be a number - the number of days back that
    the root level jobs started.  If they started after the current time
    minus 'age' days, then the job is included in the returned list and
    recursed.

    A list of JobLog instances is returned.
    """
    tlimit = None
    if age != None:
        tlimit = time.time() - age * 24*60*60

    jobs = []

    for tlog in trigfiles:
        try:
            jobL = read_trigger_log( tlog )
        except:
            print3( '*** triglog.py: '+str( sys.exc_info()[1] ) )

        for jb in jobL:
            if tlimit == None or jb.get( 'start', 0 ) >= tlimit:
                jobs.append( jb )
                try:
                    readlogfile_recurse( jb.get( 'logfile' ), jb )
                except:
                    print3( '*** triglog.py: '+str( sys.exc_info()[1] ) )

    return jobs


def print_recurse( jtree, indent=0 ):
    """
    """
    s = '                                        '[:indent]
    print3( s+str(jtree) )
    for j in jtree.getSubJobs():
        print_recurse( j, indent + 2 )


###########################################################################

class JobLog:

    def __init__(self, attrs={}):
        self.attrs = {}  # arbitrary key -> value
        self.subjobs = []  # JobLog instances
        self.attrs.update( attrs )

    def set(self, name, value):
        """
        Set a name/value attribute for this job.
        """
        self.attrs[name] = value

    def get(self, name, *default):
        """
        Get an attribute of this job.  If 'name' does not exist and a 'default'
        value is given, then that default is returned.

        Common attributes names are:

            logfile : log file name
            logdate : the modification date on the log file
            name    : a name given to the job
            start   : the start time (epoch seconds) of the job
            finish  : the finish time (epoch seconds) of the job
            exit    : the exit status (integer or "None", which means timeout)
        """
        if len(default) == 0:
            return self.attrs[name]
        return self.attrs.get( name, default[0] )

    def getSubJobs(self):
        """
        Returns a list of JobLog instances of the subjobs of this job.
        """
        return []+self.subjobs

    def addSubJob(self, subjob):
        """
        Appends the given job to the list of subjobs.
        """
        self.subjobs.append( subjob )

    def __str__(self):
        L = []
        n = self.attrs.get( 'name', None )
        if n != None: L.append( 'name='+n )
        s = self.attrs.get( 'start', None )
        if s != None: L.append( 'start='+time.ctime(s) )
        f = self.attrs.get( 'finish', None )
        if f != None: L.append( 'finish='+time.ctime(f) )
        x = self.attrs.get( 'exit', None )
        if x != None: L.append( 'exit='+str(x) )
        return 'JobLog('+', '.join(L)+')'

    def __repr__(self):
        return self.__str__()


###########################################################################

def read_trigger_log( logfile, jlog=None ):
    """
    Reads the log file (with name 'logfile') produced from the trigger.py
    script.  The jobs in 'logfile' collected and returned in list of JobLog
    instances.

    If 'jlog' is not None, it must be a JobLog instance, and the list of jobs
    are added to it as subjobs.
    """
    fp = open( logfile, 'rb' )

    newjobs = []  # JobLog instances
    match = {}  # maps log filename to JobLog instance

    try:
        T = trigger_log_readline(fp)
        while T != None:
            try:
                if T[1] == 'launch':
                    j = JobLog()
                    j.set( 'start', T[0] )
                    script = get_log_attr( T, 'file' )
                    assert script
                    b = os.path.basename( script )
                    j.set( 'name', b )
                    d = get_log_attr( T, 'logdir' )
                    assert d
                    logf = os.path.join( d, 'log.txt' )
                    j.set( 'logfile', logf )
                    if os.path.exists(logf):
                        t = os.path.getmtime( logf )
                        j.set( 'logdate', t )
                    newjobs.append( j )
                    match[logf] = j
                    if jlog != None:
                        jlog.addSubJob( j )

                elif T[1] == 'finish':
                    d = get_log_attr( T, 'logdir' )
                    assert d
                    logf = os.path.join( d, 'log.txt' )
                    j = match[logf]
                    j.set( 'finish', T[0] )
                    x = get_log_attr( T, 'exit' )
                    assert x
                    if x == 'None': j.set( 'exit', None )
                    else:           j.set( 'exit', int(x) )
                    assert logf == j.get('logfile')
                    if os.path.exists( logf ):
                        t = os.path.getmtime( logf )
                        j.set( 'logdate', t )

            except:
                #traceback.print_exc()  # uncomment to debug
                pass

            T = trigger_log_readline(fp)
    finally:
        fp.close()

    return newjobs



datemark = re.compile( r'\[(Mon|Tue|Wed|Thu|Fri|Sat|Sun)([^]]*20[0-9][0-9]\])+?' )

def trigger_log_readline( fp ):
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
                line = _STRING_(line).rstrip()
                m = datemark.match( line )
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
                #traceback.print_exc()  # uncomment to debug
                val = None
            line = None

            if val != None:
                if n > 2:
                    for i in range(n-2):
                        line = fp.readline()
                        assert line
                        line = _STRING_(line)
                        if line.startswith( '    ' ):
                            val.append( line[4:].rstrip() )
                        else:
                            val = None
                            break
                if val != None:
                    break
    except:
        #traceback.print_exc()  # uncomment to debug
        val = None

    return val


def get_log_attr( logline, attrname ):
    """
    Looks for 'attrname' in the list of fields 'logline'.  If found, the
    value for the attribute is returned, otherwise None.  For example, if

        logline = [ 'launch', 'file=/my/file' ]
        attrname = 'file'

    will return "/my/file".
    """
    pfx = attrname + '='
    for s in logline:
        try:
            if s.startswith(pfx):
                return s.split(pfx,1)[1]
        except:
            pass
    return None


###########################################################################

def readlogfile_recurse( logfile, jlog=None ):
    """
    Scans the given log file for sub-job launches that use the runjob.py
    and/or runcmd.py modules.  Each sub-job log file is then read, recursively.

    The list of jobs in 'logfile' is returned.

    If 'jlog' is not None, it should be a JobLog instance, and the jobs in
    'logfile' are added to it.
    """
    reader = RunLogReader( logfile )
    jobL = reader.readlogfile()

    for jb in jobL:

        if jlog != None:
            jlog.addSubJob( jb )

        sublogf = jb.get( 'logfile', None )
        if sublogf != None:
            try:
                readlogfile_recurse( sublogf, jb )
            except:
                # putting a try/except here allows errors from the root log
                # file to be raised, but not errors from reading sub-log files
                pass

    return jobL


class RunLogReader:

    def __init__(self, filename):
        """
        """
        self.fname = filename
        self.fileptr = None

    def readlogfile(self):
        """
        Scans the given log file for sub job launches that use the runjob.py
        and/or runcmd.py modules.  A list of JobLog instances is returned.
        """
        jobL = []

        for jD in self.log_readlines():

            # record the log file date stamp, if available
            logf = jD.get( 'logfile', None )
            if logf != None:
                try:
                    jD['logdate'] = os.path.getmtime(logf)
                except:
                    pass

            jobL.append( JobLog( jD ) )

        return jobL

    def log_readlines(self):
        """
        Returns a list of dictionaries, each of which contain the attributes
        for the jobs.
        """
        logdir = os.path.dirname(self.fname)

        self.fileptr = open( self.fname, 'rb' )
        try:
            lines = self.logreadfilelines()
        finally:
            self.fileptr.close()
            self.fileptr = None

        jobL = []
        jobD = {}

        itr = LogLineIterator( lines )

        while itr.morelines():

            tm,ln,data = itr.getline()

            if ln == 'RunJob':
                try:
                    attrs = self.get_runjob_data( itr )
                    if 'logfile' in attrs:
                        # an old format did not specify LogFile, so it had to
                        # be calculated; the abs path is performed here
                        f = attrs['logfile']
                        if not os.path.isabs(f):
                            attrs['logfile'] = os.path.join( logdir, f )
                except:
                    #traceback.print_exc()  # uncomment to debug
                    pass
                else:
                    jobD[ attrs['jobid'] ] = attrs
                    jobL.append( attrs )

            elif ln == 'JobDone':
                try:
                    jid,x,ex = self.get_runjob_done_data( data )
                    attrs = jobD[ jid ]
                except:
                    #traceback.print_exc()  # uncomment to debug
                    pass
                else:
                    attrs['exit'] = x
                    attrs['except'] = ex
                    attrs['finish'] = tm

            elif ln == 'runcmd':
                try:
                    attrs = self.get_runcmd_data( data )
                except:
                    #traceback.print_exc()  # uncomment to debug
                    pass
                else:
                    jobD[ attrs['jobid'] ] = attrs
                    # the start= time is used by runcmd for a jobid, override
                    # with the time in brackets to be consistent
                    attrs['start'] = tm
                    jobL.append( attrs )

            elif ln == 'return':
                try:
                    jid,x = self.get_runcmd_done_data( data )
                    attrs = jobD[ jid ]
                except:
                    #traceback.print_exc()  # uncomment to debug
                    pass
                else:
                    attrs['exit'] = x
                    attrs['finish'] = tm

            itr.advance()

        return jobL

    def logreadfilelines(self):
        """
        Collects the lines from the file that are relevant to job launch and
        job finish.  Returns a list of

                [ epoch time, line name, line data ]
        """
        relevant_markers = [
                            'RunJob: ',
                            'JobID: ',
                            'LogFile: ',
                            'Machine: ',
                            'Directory: ',
                            'JobDone: ',
                            'runcmd: ',
                            'return: ',
                           ]

        lines = []

        while True:

            try:
                line = self.fileptr.readline()
            except:
                return lines

            if not line:
                return lines

            line = _STRING_(line).rstrip()
            m = datemark.match( line )
            if m != None:
                try:
                    ts = line[:m.end()].strip().strip('[').strip(']')
                    tm = time.mktime( time.strptime( ts ) )
                    line = line[m.end():].strip()
                    for n in relevant_markers:
                        if line.startswith(n):
                            data = line.split(n,1)[1].strip()
                            L = [ tm, n.strip().rstrip(':'), data ]
                            lines.append( L )
                            break
                except:
                    #traceback.print_exc()  # uncomment to debug
                    pass


    def get_runjob_data(self, itr):
        """
        Reads the job data from a RunJob: section.  The iterator must be at
        the start of a RunJob: section.

        Returns a key/value dictionary storing the attributes of the job.
        """
        jobD = {}
        repeatD = {}  
        jn = None
        logf = None

        t,n,d = itr.getline()
        assert n == 'RunJob'
        repeatD[n] = d
        jobD['start'] = t
        jobD['command'] = d.strip()

        while itr.morelines(1):

            t,n,d = itr.lookahead()

            # a repeat of any marker means the end of the current job
            if n in repeatD:
                break
            repeatD[n] = d

            if n == 'JobID':
                jobD['jobid'] = d.strip()
                if jn == None:
                    # extract the job name from the job id tuple
                    s = d.strip().strip('(').split(',',1)[0]
                    jn = s.strip('"').strip("'")

            elif n == 'LogFile':
                logf = d.strip()

            elif n == 'Machine':
                jobD['machine'] = d.strip()

            elif n == 'Directory':
                jobD['directory'] = d.strip()

            else:
                break
            
            itr.advance()

        if jn != None:
            jobD['name'] = jn

        if logf != None:
            jobD['logfile'] = logf
        elif 'jobid' in jobD:
            # an old format did not use LogFile, so try to compute the basename
            try:
                n,m,d = eval( jobD['jobid'] )
                if m: n += '-' + m
                jobD['logfile'] = n + '-' + d + '.log'
            except:
                pass

        return jobD

    def get_runjob_done_data(self, datastr):
        """
        Extracts the ( jobid, exit status, exception ) from the given data
        string.
        """
        L = datastr.split( 'exit=', 1 )
        x,ex = [ s.strip() for s in L[1].split( 'exc=', 1 ) ]

        if x:
            if x == 'None': x = None
            else:           x = int(x)

        if not ex: ex = None

        return L[0].strip().lstrip('jobid='), x, ex


    def get_runcmd_data(self, datastr):
        """
        Reads the job data from a "runcmd:" line produced from runcmd.py module.
        Returns a key/value dictionary storing the attributes of the jobs.
        """
        D = {}

        L = eval( datastr )
        for s in L:
            if   s.startswith( 'dir=' ):     D['directory'] = s[4:]
            elif s.startswith( 'logfile=' ): D['logfile']   = s[8:]
            elif s.startswith( 'start=' ):   D['start']     = s[6:]
            elif s.startswith( 'cmd=' ):     D['command']   = s[4:]
            elif s.startswith( 'timeout=' ): D['timeout']   = s[8:]

        if 'command' in D:
            try:
                n = os.path.basename( D['command'].split()[0] )
            except:
                n = 'anonymous'
        else:
            n = 'anonymous'
        D['name'] = n

        if 'start' in D:
            D['jobid' ] = D['start']
        elif 'command' in D:
            D['jobid'] = D['command']
        else:
            D['jobid'] = ''

        return D


    def get_runcmd_done_data(self, datastr):
        """
        Extracts the ( job id, exit status ) from the given data string.
        """
        x = jid = cmd = None

        L = eval( datastr )
        for s in L:
            if s.startswith( 'exit=' ):
                x = s[5:]
            elif s.startswith( 'start=' ):
                jid = s[6:]
            elif s.startswith( 'command=' ):
                cmd = s[8:]

        if jid == None:
            jid = cmd

        if x:
            if x == 'None': x = None
            else:           x = int(x)

        return jid,x


class LogLineIterator:
    """
    Given a list of lines, this forms an old fashion iterator with a "look
    ahead" function.
    """

    def __init__(self, line_list):
        self.lines = line_list
        self.i = 0

    def morelines(self, lookahead=0):
        """
        Returns true if the current iterator location plus 'lookahead' is
        valid (i.e., would not index off the end of the lines array).
        """
        return self.i+lookahead < len(self.lines)

    def getline(self):
        return self.lines[ self.i ]

    def lookahead(self):
        return self.lines[self.i+1]

    def advance(self):
        self.i += 1


###########################################################################

def print3( *args ):
    """
    Python 2 & 3 compatible print function.
    """
    s = ' '.join( [ str(x) for x in args ] )
    sys.stdout.write( s + '\n' )
    sys.stdout.flush()

if sys.version_info[0] < 3:
    # with python 2.x, files, pipes, and sockets work naturally
    def _BYTES_(s): return s
    def _STRING_(b): return b

else:
    # with python 3.x, read/write to files, pipes, and sockets is tricky
    bytes_type = type( ''.encode() )

    def _BYTES_(s):
        if type(s) == bytes_type:
            return s
        return s.encode( 'ascii' )

    def _STRING_(b):
        if type(b) == bytes_type:
            return b.decode()
        return b


###########################################################################

if __name__ == "__main__":
    mydir = os.path.abspath( sys.path[0] )
    main()
