#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import fnmatch
import glob

debug = False

uname = os.uname()
osname,nodename,osrelease,machine = uname[0], uname[1], uname[2], uname[4]

def platform( opts ):
    """
    """
    if '--plat' in opts:
        return opts['--plat']

    pbshost = os.environ.get('PBS_O_HOST','')
    cluster = os.environ.get('SNLCLUSTER','')

    if debug:
        print 'idplatform.platform: uname =', osname, nodename, osrelease, machine
        print 'idplatform.platform: pbshost, cluster', pbshost, cluster

    if base_match( [nodename,pbshost],
                   ['ci-fe','ci-login','ci-vizlogin','mzlogin'] ) or \
       shell_match( [nodename,pbshost], ['batch[0-9][0-9]-wlm'] ):
        # old Cray machines
        return 'Cray'

    if shell_match( [nodename,pbshost],
                    ['excalibur[0-9]*','batch[0-9]*','clogin*','nid*'] ):
        # DoD Cray XC 40
        return 'Cray'

    if shell_match( [nodename,pbshost],
                    ['mutrino*','tr-login[0-9]*','mom[0-9]*'] ):
        # the login nodes start with 'tr-login' (or 'mom'?)
        # the front end nodes start with 'mutrino' at Sandia, or ?? on Trinity
        return 'CrayXC'

    if shell_match( [nodename,pbshost], ['hercules[0-9]*'] ):
        # DoD IBM DataPlex ?
        return 'IBMidp'

    if base_match( [nodename,pbshost,cluster],
                   ['solo','serrano','cayenne','ghost'] ):
        # Capacity Technology System, running TOSS
        return 'CTS1'

    if base_match( [nodename,pbshost,cluster],
                   ['chama','uno','pecos','jemez','skybridge'] ) or \
       shell_match( [nodename], ['sb[0-9]*'] ):
        # Tri-Lab Computing Cluster, running TOSS
        return 'TLCC2'

    if base_match( [nodename,pbshost,cluster], ['godzilla'] ) or \
       shell_match( [nodename], ['gn[0-9]','gn[0-9][0-9]'] ):
        # see Kyle Cochrane
        return 'Godzilla'

    if base_match( [osname], ['CYGWIN'] ):
        return 'CYGWIN'

    if osname == "Darwin" and machine in ["i386","i686","x86_64"]:
        return "iDarwin"

    if osname == 'Linux' and machine == 'ia64':
        return 'Altix'

    if osname == 'Linux' and CEELAN():
        # Sandia CEE LAN
        return 'ceelan'

    if debug:
        print 'idplatform.platform: returning'


def CEELAN():
    """
    Returns True if the current machine appears to be on the Sandia CEE LAN.
    """
    netfile = '/etc/sysconfig/network'
    if os.path.exists( netfile ):
        try:
            fp = open( netfile, 'r' )
            L = fp.readlines()
            fp.close()
        except:
            pass
        else:
            for line in L:
                if line.strip() in [ 'NISDOMAIN=hotair.engsci.sandia.gov',
                                     'NISDOMAIN=wizard.sandia.gov' ]:
                    return True

    return False

#       rhat = 0
#       rhfile = '/etc/redhat-release'
#       if os.path.exists( rhfile ):
#         try:
#           fp = open( rhfile, 'rb' ) ; s = fp.read() ; fp.close()
#         except:
#           pass
#         else:
#           L = s.split()
#           if L.count('5.7') > 0:
#             rhat = 5
#           elif L.count('6.4') > 0 or L.count('6.3') > 0:
#             rhat = 6


#######################################################################

def base_match( namelist, matchlist ):
    """
    Looks for a name in 'namelist' whose first part matches a word in
    'matchlist'.
    """
    for n in namelist:
        for m in matchlist:
            tn = n[:len(m)]  # truncate the actual name to the match name length
            if tn == m:
                return 1
    return 0


def shell_match( namelist, matchlist ):
    """
    Looks for a name in 'namelist' that matches a word in 'matchlist' which
    can contain shell wildcard characters.
    """
    for n in namelist:
        for m in matchlist:
            if fnmatch.fnmatch( n, m ):
                return 1
    return 0


#######################################################################

if __name__ == "__main__":
    """
    Can execute this script as a quick check of the logic and results.
    """
    import getopt
    optL,argL = getopt.getopt( sys.argv[1:], 'o:', ['plat='] )
    optD = {}
    for n,v in optL:
        optD[n] = v
    p = platform( optD )
    print p
