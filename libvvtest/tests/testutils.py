import os, sys
import re
import shutil
import stat

# this file is expected to be imported from a script that was run
# within the tests directory (which is how all the tests are run)
testdir = os.path.dirname( os.path.abspath( sys.argv[0] ) )

srcdir = os.path.normpath( os.path.join( testdir, '..' ) )
topdir = os.path.normpath( os.path.join( srcdir, '..' ) )

sys.path.insert( 0, srcdir )
sys.path.insert( 0, topdir )

vvtest = os.path.join( topdir, 'vvtest' )
resultspy = os.path.join( topdir, 'results.py' )

arglist = sys.argv[1:]

def get_arg_list(): return arglist

def get_test_dir():  # magic: is this still needed ??
    return testdir

def print3( *args ):
    sys.stdout.write( ' '.join( [ str(x) for x in args ] ) + os.linesep )
    sys.stdout.flush()

def writefile( fname, content, header=None ):
    """
    Open and write 'content' to file 'fname'.  The content is modified to
    remove leading spaces on each line.  The first non-empty line is used
    to determine how many spaces to remove.
    """
    # determine indent pad of the given content
    pad = None
    lineL = []
    for line in content.split( '\n' ):
        line = line.strip( '\r' )
        lineL.append( line )
        if pad == None and line.strip():
            for i in range(len(line)):
                if line[i] != ' ':
                    pad = i
                    break
    # make the directory to contain the file, if not already exist
    d = os.path.dirname( fname )
    if os.path.normpath(d) not in ['','.']:
      if not os.path.exists(d):
        os.makedirs(d)
    # open and write contents
    fp = open( fname, 'w' )
    if header != None:
        fp.write( header.strip() + os.linesep + os.linesep )
    for line in lineL:
        if pad != None: fp.write( line[pad:] + os.linesep )
        else:           fp.write( line + os.linesep )
    fp.close()

def writescript( fname, content ):
    writefile( fname, content )
    perm = stat.S_IMODE( os.stat(fname)[stat.ST_MODE] )
    perm = perm | stat.S_IXUSR
    try: os.chmod(fname, perm)
    except: pass

def run_cmd( cmd, directory=None ):
    """
    """
    print3( 'RUN:', cmd )
    
    saved = None
    if directory:
      saved = os.getcwd()
      os.chdir( directory )

    pread, pwrite = os.pipe()
    pid = os.fork()
    if pid == 0:
      os.close(pread)  # child does not read from parent
      os.dup2(pwrite, sys.stdout.fileno())
      os.dup2(pwrite, sys.stderr.fileno())
      cmdL = cmd.split()
      os.execvpe( cmdL[0], cmdL, os.environ )
    os.close(pwrite)   # parent does not write to child
    out = ''
    while 1:
      buf = os.read(pread, 1024)
      if len(buf) == 0: break;
      out = out + buf
    os.close(pread)  # free up file descriptor
    pid,x = os.waitpid(pid,0)
    print3( out )
    
    if saved:
      os.chdir( saved )

    if os.WIFEXITED(x) and os.WEXITSTATUS(x) == 0:
      return True, out
    return False, out

def run_vvtest( argstr='', ignore_errors=0, directory=None ):
    """
    Runs vvtest with the given argument string and returns
      ( command output, num pass, num diff, num fail, num notrun )
    If the exit status is not zero, an assertion is raised.
    """
    if directory:
      curdir = os.getcwd()
      os.chdir( directory )
    x,out = run_cmd( vvtest + ' ' + argstr )
    if directory:
      os.chdir( curdir )
    if not x and not ignore_errors:
      raise Exception( "vvtest command failed: " + vvtest + ' ' + argstr )
    return out,numpass(out),numdiff(out),numfail(out),numnotrun(out)

def platform_name( test_out ):
    """
    After running the 'run_vvtest' command, give the output (the first return
    argument) to this function and it will return the platform name.  It
    throws an exception if the platform name cannot be determined.
    """
    platname = None
    for line in test_out.split( os.linesep ):
      line = line.strip()
      if line.startswith( 'Test directory:' ):
        L = line.split()
        if len(L) >= 3:
          L2 = L[2].split('.')
          if len(L2) >= 2:
            platname = L2[1]
    if platname == None:
      raise Exception( "Could not determine the platform name from output" )
    return platname

def results_dir():
    """
    After running vvtest, this will return the TestResults directory.
    """
    for f in os.listdir('.'):
      if f[:12] == 'TestResults.':
        return f
        break
    return ''

def remove_results():
    """
    Removes all TestResults from the current working directory.
    If a TestResults directory is a soft link, the link destination is
    removed as well.
    """
    for f in os.listdir('.'):
      if f[:12] == 'TestResults.':
        if os.path.islink(f):
          dest = os.readlink(f)
          print 'rm -r ' + dest
          shutil.rmtree(dest)
          print 'rm ' + f
          os.remove(f)
        else:
          print 'rm -r ' + f
          shutil.rmtree( f, 1 )

def rmallfiles():
    for f in os.listdir("."):
      if f != "conflicts.out":
        if not os.path.islink(f) and os.path.isdir(f):
          shutil.rmtree(f)
        else:
          os.remove(f)

# these have to be modified if/when the output format changes in vvtest
def check_pass(L): return len(L) >= 5 and L[2] == 'pass'
def check_fail(L): return len(L) >= 5 and L[2][:4] == 'fail'
def check_diff(L): return len(L) >= 5 and L[2] == 'diff'
def check_notrun(L): return len(L) >= 3 and L[1] == 'NotRun'
def check_timeout(L): return len(L) >= 5 and L[1] == 'TimeOut'
#def check_pass(L): return len(L) >= 4 and L[1] == 'pass'
#def check_fail(L): return len(L) >= 4 and L[1] == 'fail'
#def check_diff(L): return len(L) >= 4 and L[1] == 'diff'
#def check_notrun(L): return len(L) >= 3 and L[1] == 'notrun'
#def check_timeout(L): return len(L) >= 3 and L[1] == 'timeout'

def numpass(out):
    cnt = 0
    mark = 0
    for line in out.split( os.linesep ):
      if mark:
        if line[:10] == "==========":
          mark = 0
        else:
          L = line.split()
          if check_pass(L):
            cnt = cnt + 1
      elif line[:10] == "==========":
        mark = 1
        cnt = 0  # reset count so only the last cluster is considered
    return cnt

def numfail(out):
    cnt = 0
    mark = 0
    for line in out.split( os.linesep ):
      if mark:
        if line[:10] == "==========":
          mark = 0
        else:
          L = line.split()
          if check_fail(L):
            cnt = cnt + 1
      elif line[:10] == "==========":
        mark = 1
        cnt = 0  # reset count so only the last cluster is considered
    return cnt

def numdiff(out):
    cnt = 0
    mark = 0
    for line in out.split( os.linesep ):
      if mark:
        if line[:10] == "==========":
          mark = 0
        else:
          L = line.split()
          if check_diff(L):
            cnt = cnt + 1
      elif line[:10] == "==========":
        mark = 1
        cnt = 0  # reset count so only the last cluster is considered
    return cnt

def numnotrun(out):
    cnt = 0
    mark = 0
    for line in out.split( os.linesep ):
      if mark:
        if line[:10] == "==========":
          mark = 0
        else:
          L = line.split()
          if check_notrun(L):
            cnt = cnt + 1
      elif line[:10] == "==========":
        mark = 1
        cnt = 0  # reset count so only the last cluster is considered
    return cnt

def numtimeout(out):
    cnt = 0
    mark = 0
    for line in out.split( os.linesep ):
      if mark:
        if line[:10] == "==========":
          mark = 0
        else:
          L = line.split()
          if check_timeout(L):
            cnt = cnt + 1
      elif line[:10] == "==========":
        mark = 1
        cnt = 0  # reset count so only the last cluster is considered
    return cnt

def testlist(out):
    L = []
    mark = 0
    for line in out.split( os.linesep ):
      if mark:
        if line[:10] == "==========":
          mark = 0
        else:
          L.append( line.split() )
      elif line[:10] == "==========":
        mark = 1
        L = []  # reset list so only last cluster is considered
    return L

def filegrep(fname, pat):
    L = []
    fp = open(fname,"r")
    repat = re.compile(pat)
    for line in fp.readlines():
      line = line.rstrip()
      if repat.search(line):
        L.append(line)
    fp.close()
    return L

def grep(out, pat):
    L = []
    repat = re.compile(pat)
    for line in out.split( os.linesep ):
      line = line.rstrip()
      if repat.search(line):
        L.append(line)
    return L

def greptestlist(out, pat):
    repat = re.compile(pat)
    L = []
    mark = 0
    for line in out.split( os.linesep ):
      if mark:
        if line[:10] == "==========":
          mark = 0
        elif repat.search( line.rstrip() ):
          L.append( line.rstrip() )
      elif line[:10] == "==========":
        mark = 1
        L = []  # reset list so only last cluster is considered
    return L

def testlines(out):
    L = []
    mark = 0
    for line in out.split( os.linesep ):
      if mark:
        if line.startswith( "==========" ):
          mark = 0
        else:
          L.append( line.rstrip() )
      elif line.startswith( "==========" ):
        mark = 1
        L = []  # reset list so only last cluster is considered
    return L

if not os.environ.has_key('TOOLSET_RUNDIR'):
    # directly executing a test script can be done but rm -rf * is performed;
    # to avoid accidental removal of files, cd into a working directory
    d = os.path.join( os.path.basename( sys.argv[0] )+'_dir' )
    if not os.path.exists(d):
        os.mkdir(d)
    os.environ['TOOLSET_RUNDIR'] = d
    os.chdir(d)
