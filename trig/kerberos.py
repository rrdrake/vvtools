#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys

help_string = """
USAGE
    kerberos.py [OPTIONS] {init|destroy|renew}

    Ticket path: TICKETPATH

    init    : generates a ticket
    destroy : removes the ticket
    renew   : renews an existing ticket

OPTIONS
    -h, --help : this help
    -q : no output unless a failure occurs

QUICK START
    Steps to establish an automated process that can authenticate:

    1. Make sure the /home/$USER/.ssh directory is read & write only by you.
    2. Run "kerberos.py init"
    3. Run "crontab -e" and add something like this:
            09 10 * * * /path/to/kerberos.py -q renew
            09 22 * * * /path/to/kerberos.py -q renew
    4. Set variable KRB5CCNAME in scripts to /home/$USER/.ssh/krb5ticket, or
       add this to python scripts:
            import kerberos
            kerberos.set_ticket()
    5. Every 90 days or less, manually run "kerberos.py init" again

BACKGROUND
    One can initialize a Kerberos authentication ticket then use that ticket
for a period of time to ssh to other machines or checkout from a
repository without entering your password.  The period of time is 24 hours
or less, but you can renew the ticket for up to 90 days.  So a technique is
to manually initialize a ticket (and enter your password), then add the
renew command in a cron table that executes twice once a day.

There is a default location for a Kerberos ticket, but adding the -c
option to Kerberos commands overrides the default location.  Also, setting
the KRB5CCNAME environment variable will also override the default location.

On RHEL6 machines, the Kerberos commands from /usr/bin should work, such as
kinit, kdestroy, and klist.

To initialize a ticket:
  $ kinit -f -r 90d -l 1d -c /home/$USER/.ssh/krb5ticket

To remove it
  $ kdestroy -c /home/$USER/.ssh/krb5ticket

To renew a ticket
  $ kinit -R -c /home/$USER/.ssh/krb5ticket

Note that the above examples and this script places the ticket in your .ssh
directory because it should already be protected, but that choice is arbitrary.
The important thing is that the directory is only read/write by the owner.
"""


def main():
    ""
    import getopt
    optL,argL = getopt.getopt( sys.argv[1:], 'hq', ['help'] )

    if ('-h','') in optL or ('--help','') in optL:
        s = help_string.replace( 'TICKETPATH', ticketpath )
        sys.stdout.write(s)
        return

    echo = 'echo'
    if ('-q','') in optL:
        echo = 'none'

    for s in argL:
        if   s == "init": init_ticket( echo=echo )
        elif s == "destroy": destroy_ticket( echo=echo )
        elif s == "renew": renew_ticket( echo=echo )


def set_ticket():
    """
    Sets the KRB5CCNAME environment variable to the Kerberos ticket path.
    """
    os.environ['KRB5CCNAME'] = ticketpath


def init_ticket( echo="echo" ):
    ""
    from command import Command
    destroy_ticket()
    Command( 'kinit -f -r 90d -l 1d -c $ticketpath' ).run( echo=echo )


def destroy_ticket( echo="echo" ):
    ""
    from command import Command
    Command( 'kdestroy -c $ticketpath' ).run_timeout( 60, echo=echo )


def renew_ticket( echo="echo" ):
    ""
    from command import Command
    Command( 'kinit -R -c $ticketpath' ).run_timeout( 60, echo=echo )


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


################################################################

ticketpath = '/home/' + get_user_name() + '/.ssh/krb5ticket'

if __name__ == "__main__":
    main()

