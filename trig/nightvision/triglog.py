#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import time
import traceback
import re
import json


helpstr = \
"""
USAGE:
    triglog.py [OPTIONS] filename

SYNOPSIS:
    Does stuff.

OPTIONS:
    -h, --help             : this help

    -T <seconds>           : apply timeout to each remote command
    --sshexe <path to ssh> : use this ssh
"""

############################################################################

def main():

    import getopt
    optL,argL = getopt.getopt( sys.argv[1:], 'hd',
                   longopts=['help', 'date='] )

    optD ={}
    for n,v in optL:
        if n == '-h' or n == '--help':
            print3( helpstr )
            return 0
        elif n in []:
            optD[n] = optD.get(n,[]) + [v]
        else:
            optD[n] = v

    root = JobLog()

    if '--date' in optD.keys():
        date_in_secs_since_epoch = float(optD['--date'])

    for tlog in argL:
        try:
            jobs = read_trigger_log( tlog, root )
        except:
            print3( '*** triglog.py: '+str( sys.exc_info()[1] ) )

        for logf, jlog in jobs.items():
            try:
                readlog_recurse( jlog )
            except:
                print3( '*** triglog.py: '+str( sys.exc_info()[1] ) )



    root_dict = {"root": job_dict_recurse(root, date_in_secs_since_epoch)}
    
    filepath = os.path.join( "resources", "logs.json")
    with open(filepath.replace(' ', '_'), "w") as jsonfile:
        json.dump(root_dict, jsonfile, indent=4, sort_keys=True)


def print_recurse( jtree, indent=0 ):
    """
    """
    print3( ' '*indent, jtree )
    for j in jtree.subjobs.values():
        print_recurse( j, indent + 2 )

def job_dict_recurse(jtree, seconds):
    """
    """
    job = jtree.attrs
    job['subjobs'] = []
    for subjob in jtree.subjobs.values():
        if time.ctime(subjob.attrs['start'])[:10] != time.ctime(seconds)[:10]:
            continue
        job['subjobs'].append(job_dict_recurse(subjob, seconds))
    return job
###########################################################################

class JobLog:

    def __init__(self, **kwargs):
        self.attrs = {}  # arbitrary key -> value
        self.subjobs = {}  # maps job identifier to JobLog instances
        for k,v in kwargs:
            self.set( k, v )

    def set(self, name, value):
        """
        """
        self.attrs[name] = value

    def get(self, name, *default):
        """
        Common attributes are:

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

    def add(self, jobid, subjob):
        """
        """
        self.subjobs[jobid] = subjob

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


###########################################################################

def read_trigger_log( logfile, jtree ):
    """
    Reads the log file (with name 'logfile') produced from the trigger.py
    script.  The jobs are added as children to 'jtree', which should be a
    JobLog object.

    Returns a dictionary mapping the log file names to JobLog instances.
    These only contain the jobs represented in the current log file.
    """
    fp = open( logfile, 'rb' )
    jobs = {}  # maps log filename to JobLog instance

    try:
        T = trigger_log_readline(fp)
        while T != None:
            try:
                if T[1] == 'launch':
                    j = JobLog()
                    j.set( 'start', T[0] )
                    b = os.path.basename( get_log_attr( T, 'file' ) )
                    j.set( 'name', b )
                    f = os.path.join( get_log_attr( T, 'logdir' ), 'log.txt' )
                    j.set( 'logfile', f )
                    jobid = f
                    jobs[f] = j
                    jtree.add( f, j )

                elif T[1] == 'finish':
                    f = os.path.join( get_log_attr( T, 'logdir' ), 'log.txt' )
                    j = jobs[f]
                    j.set( 'finish', T[0] )
                    j.set( 'exit', get_log_attr( T, 'exit' ) )
                    t = os.path.getmtime( j.get('logfile') )
                    j.set( 'logdate', t )

            except:
                traceback.print_exc()  # magic
                pass

            T = trigger_log_readline(fp)
    finally:
        fp.close()

    return jobs



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
                line = line.rstrip()
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


def readlog_recurse( jlog ):
    """
    """
    try:
        logf = jlog.get( 'logfile' )

        for jD in log_readlines( logf ):
            sublogf = jD.get( 'logfile', None )
            if sublogf != None and os.path.exists(sublogf):
                jD['logdate'] = os.path.getmtime(sublogf)

    except:
        # TODO: print a warning here?
        pass


readnames = [ 'RunJob: ',
              'JobID: ',
              'LogFile: ',
#              'Connect machine: ',
#              'Remote command: ',
#              'Remote dir: ',
#              'Remote timeout: ',
              'JobDone: ',
              'runcmd: ',
              'return: ',
            ]

def log_readlines( filename ):
    """
    Returns a list of dictionaries, each of which contain the attributes for
    the jobs.
    """
    logdir = os.path.dirname(filename)

    fp = open( filename, 'rb' )

    lines = logreadfilelines( fp )

    jobL = []
    jobD = {}

    i = 0
    while i < len(lines):

        tm,ln,data = lines[i]

        if ln == 'RunJob':
            try:
                attrs = get_job_data( i, lines )
                if 'logfile' in attrs:
                    f = attrs['logfile']
                    if not os.path.isabs(f):
                        attrs['logfile'] = os.path.join( logdir, f )
            except:
                pass
            else:
                jobD[ attrs['jobid'] ] = attrs
                jobL.append( attrs )

        elif ln == 'JobDone':
            try:
                jid,x,ex = get_done_data( data )
                attrs = jobD[ jid ]
            except:
                pass
            else:
                attrs['exit'] = x
                attrs['except'] = ex
                attrs['finished'] = tm

        elif ln == 'runcmd':
            try:
                jid,x,ex = get_done_data( data )
                attrs = jobD[ jid ]
            except:
                pass
            else:
                attrs['exit'] = x
                attrs['except'] = ex
                attrs['finished'] = tm

        i += 1


def logreadfilelines( fp ):
    """
    Collects the lines from the file that are relevant to job launch and job
    finish.  Returns a list of

            [ epoch time, line name, line data ]
    """
    lines = []

    while True:

        try:
            line = fp.readline()
        except:
            return lines

        if not line:
            return lines

        line = line.rstrip()
        m = datemark.match( line )
        if m != None:
            try:
                ts = line[:m.end()].strip().strip('[').strip(']')
                tm = time.mktime( time.strptime( ts ) )
                line = line[m.end():].strip()
                for n in readnames:
                    if line.startswith(n):
                        data = line.split(n,1)[1].strip()
                        L = [ tm, n.strip().rstrip(':'), data ]
                        lines.append( L )
                        break
            except:
                pass


def get_job_data( i, lines ):
    """
    Reads the job data from a RunJob: section.  The 'lines' must be the list
    produced by the logreadfilelines() function.  The index 'i' is the start
    of the RunJob: section which is being read.

    Returns a key/value dictionary storing the attributes of the job.
    """
    assert lines[i][1] == 'RunJob'

    D = {}
    jn = None
    logf = None
    j = i
    while j < len(lines):
        t,n,d = lines[j]
        if n == 'RunJob':
            D['start'] = t
            D['command'] = d.strip()
        elif n == 'JobID':
            D['jobid'] = d.strip()
            if jn == None:
                s = d.strip().strip('(').split(',',1)[0]
                jn = s.strip('"').strip("'")
        elif n == 'LogFile':
            logf = d.strip()
        else:
            break
        j += 1

    if jn != None:
        D['name'] = jn

    if logf != None:
        D['logfile'] = logf
    elif 'jobid' in D:
        # the older format did not have LogFile, so try to compute the basename
        try:
            n,m,d = eval( D['jobid'] )
            if m: n += '-' + m
            D['logfile'] = n + '-' + d + '.log'
        except:
            pass

    return D


def get_done_data( datastr ):
    """
    """
    L = datastr.split( 'exit=', 1 )
    x,ex = [ s.strip() for s in L[1].split( 'exc=', 1 ) ]
    if not ex: ex = None
    return L[0].strip().lstrip('jobid='), x, ex


def get_runcmd_data( datastr ):
    """
    """
    i = datastr.find( ' logfile=' )
    if i > 0:
        j = datastr.find( ' start=', i )
        logf = datastr[i+9:j].strip()
    jid = datastr[j+7:].split()[0]

    x,ex = [ s.strip() for s in L[1].split( 'exc=', 1 ) ]
    if not ex: ex = None
    return L[0].strip().lstrip('jobid='), x, ex


def print3( *args ):
    """
    Python 2 & 3 compatible print function.
    """
    s = ' '.join( [ str(x) for x in args ] )
    sys.stdout.write( s + '\n' )
    sys.stdout.flush()

###########################################################################

if __name__ == "__main__":
    mydir = os.path.abspath( sys.path[0] )
    main()
