#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys

def runcmd( cmdL, changedir=None ):
    """
    """
    sys.stdout.flush()
    sys.stderr.flush()
    
    outRead, outWrite = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(outRead)
        os.dup2(outWrite, sys.stdout.fileno())
        os.dup2(outWrite, sys.stderr.fileno())
        if changedir != None:
            os.chdir(changedir)
        os.execvp( cmdL[0], cmdL )
    
    os.close(outWrite)
    out = ''
    while True:
        buf = os.read(outRead,2048)
        if not buf:
            break

        if sys.version_info[0] < 3:
            out += buf
        else:
            try:
                out += buf.decode( 'ascii', errors='ignore' )
            except Exception:
                out += buf.decode( 'ascii' )

    os.close(outRead)
    (cpid, xs) = os.waitpid(pid,0)
    
    if os.WIFEXITED(xs):
        return os.WEXITSTATUS(xs), out.strip()
    return 1, out.strip()


####################################################################

if __name__ == "__main__":
    if len( sys.argv ) > 1:
        runcmd( sys.argv[1:] )
