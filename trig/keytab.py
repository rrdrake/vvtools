#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import tempfile
import shutil

from command import Command


help_string = """
USAGE
    keytab.py [OPTIONS] {generate|init|destroy}

    Keytab path: KEYTABPATH

    generate : generates a new keytab file (must be run interactively)
    init     : initializes a Kerberos ticket using the keytab file
    destroy  : destroys the Kerberos ticket

OPTIONS
    -h, --help : this help
    -q : no output unless a failure occurs

QUICK START
    Steps to establish an automated process that can authenticate:

    1. Make sure the /home/$USER/.ssh directory is read & write only by you
    2. Run "keytab.py generate"
    3. Do this in python scripts:

            import keytab
            keytab.init_ticket()
            try:
                do_stuff()
            finally:
                keytab.destroy_ticket()

       or this in bash scripts:

            export KRB5CCNAME="`keytab.py init`"
            do stuff
            keytab.py destroy

BACKGROUND
    The Kerberos keytab file is a table of credentials/keys that can be used
to initialize a Kerberos ticket, which will allow ssh authentication  without
entering a password.  You have to enter your password a few times to generate
the keytab, but it lasts until your password changes.

The ktutil program (companion to kinit, kdestroy, etc) is used to generate
the keytab file.  It is interactive only (as far as I can tell).

The kinit program is used with certain flags to initialize a Kerberos ticket
using a keytab file.  This can be done in scripts.  Treat a ticket the same
as any other.

This script stores the keytab file in /home/$USER/.ssh because it should
already be protected, but that choice is arbitrary.  The important thing is
that the directory is only read/write by the owner.
"""


def main():
    ""
    import getopt
    optL,argL = getopt.getopt( sys.argv[1:], 'hq', ['help'] )

    if ('-h','') in optL or ('--help','') in optL:
        s = help_string.replace( 'KEYTABPATH', keytabpath )
        sys.stdout.write(s)
        return

    echo = 'echo'
    if ('-q','') in optL:
        echo = 'none'

    for s in argL:
        if   s == "generate":
            generate_keytab()


        elif s == "init"    :
            tic = init_ticket( echo='none' )
            print3( tic )

        elif s == "destroy" :
            destroy_ticket( echo=echo )

        else:
            sys.stderr.write( 'error: unknown mode: '+repr(s)+'\n' )
            sys.stderr.flush()
            sys.exit(1)


KTUTIL_INSTRUCTION_TEMPLATE = """
Running ktutil to create keytab file.  Enter the following one at a time
at the ktutil: prompts.

    add_entry -password -p USERNAME -k 3 -e des-cbc-crc
    add_entry -password -p USERNAME -k 3 -e des3-hmac-sha1
    add_entry -password -p USERNAME -k 3 -e rc4-hmac
    add_entry -password -p USERNAME -k 3 -e aes256-cts
    add_entry -password -p USERNAME -k 3 -e des-cbc-md5
    write_kt KEYTABPATH
    exit
"""

def generate_keytab():
    ""
    delete_keytab_file( keytabpath )

    usr = get_user_name()
    msg = KTUTIL_INSTRUCTION_TEMPLATE.replace( 'USERNAME', usr )
    msg = msg.replace( 'KEYTABPATH', keytabpath )
    print3( msg )

    Command( 'ktutil' ).run( raise_on_error=True )

    ktdir = os.path.dirname( keytabpath )
    Command( 'ls -ld $ktdir $keytabpath' ).run()


def delete_keytab_file( filename, echo="echo" ):
    ""
    if os.path.exists( filename ):
        if echo != "none":
            print3( 'rm '+filename )
        if 'COMMAND_DRYRUN' not in os.environ:
            os.remove( filename )


def init_ticket( echo="echo" ):
    """
    Generates a random filename for the Kerberos cache file then runs kinit
    to initialize it using the keytab file.  The KRB5CCNAME environment
    variable is set to the name of the cache file name.
    """
    usr = get_user_name()
    tmpdir = tempfile.mkdtemp( prefix=usr+'_krb5tmp_' )

    cachefname = os.path.join( tmpdir, 'krb5ccache' )

    cmd = Command( 'kinit -f -l 24h -c $cachefname',
                   '-k -t $keytabpath ${usr}@dce.sandia.gov' )
    cmd.run( echo=echo, raise_on_error=True )

    if 'KRB5CCNAME' in os.environ:
        os.environ['PREVIOUS_KRB5CCNAME'] = os.environ['KRB5CCNAME']

    os.environ['KRB5CCNAME'] = cachefname

    return cachefname


def destroy_ticket( echo="echo" ):
    """
    Calls kdestroy on the KRB5CCNAME cache file, then removes it.  The
    KRB5CCNAME environment variable is set to PREVIOUS_KRB5CCNAME if defined.
    """
    cachefname = os.environ.get( 'KRB5CCNAME', None )

    if cachefname and os.path.exists( cachefname ):

        Command( 'kdestroy -c $cachefname' ).run( echo=echo )

        # only remove the cache file if it was created with init_cache_file()

        usr = get_user_name()
        prefix = usr+'_krb5tmp_'
        tmpdir = os.path.dirname( cachefname )

        if os.path.basename( tmpdir ).startswith( prefix ):
            if echo != "none":
                print3( 'rm -rf '+tmpdir )
            shutil.rmtree( tmpdir, ignore_errors=True )

        os.environ.pop( 'KRB5CCNAME' )

    if 'PREVIOUS_KRB5CCNAME' in os.environ:
        os.environ['KRB5CCNAME'] = os.environ.pop( 'PREVIOUS_KRB5CCNAME' )



def get_user_name():
    """
    Returns the user name associated with this process, or raises an
    exception if it fails to determine the user name.
    """
    try:
        import getpass
        return getpass.getuser()
    except Exception:
        pass

    try:
        usr = os.path.expanduser( '~' )
        if usr != '~':
            return os.path.basename( usr )
    except Exception:
        pass

    raise Exception( "could not determine the user name of this process" )


def print3( *args ):
    ""
    sys.stdout.write( ' '.join( [ str(arg) for arg in args ] ) + '\n' )
    sys.stdout.flush()


################################################################

keytabpath = '/home/' + get_user_name() + '/.ssh/krb5keytab'

if __name__ == "__main__":
    main()

