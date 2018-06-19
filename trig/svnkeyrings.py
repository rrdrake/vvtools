#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import glob
import time
import getopt
import subprocess
import shutil
import shlex
from os.path import join as pjoin


help_string = """
USAGE
    svnkeyrings.py {-h|--help}
    svnkeyrings.py [--sessionless] reset
    svnkeyrings.py [--bash|--csh]

SYNOPSIS

    This script helps set up for passwordless subversion access using
gnome-keyring.  Use the "reset" mode to reset your login keyring and
initialize for subversion access.  Afterward, your shells originating from
an X session should be able to access the subversion repository without
entering a password.

    Shells originating from cron or ssh will need to set a few variables in
order to communicate with the gnome-keyring utility running in the X session.
This script without any arguments will print the variables to stdout which
the shell can eval.  For example, for bash use

    $ eval $(keyringvars.py)

or for csh/tcsh use

    $ eval `keyringvars.py --csh`

Python programs can do

    import svnkeyrings
    svnkeyrings.set_environ()

To automate this in your shell logins, you can add to a bash login file,

    if [ -z "$GNOME_KEYRING_SOCKET" -o -z "$SSH_AUTH_SOCK" ]; then
      eval $(keyringvars.py)
    fi

or for csh/tcsh,

    if ( ! $?GNOME_KEYRING_SOCKET || ! $?SSH_AUTH_SOCK ) then
      eval `keyringvars.py --csh`
    endif

    To setup for a machine that is not running an X session, add the
--sessionless option to the reset command.  The shell eval and python
set_environ() will prefer a sessionless configuration if one exists for
the machine.

    Note that gnome-keyring data does not survive a reboot.  For X sessions,
you just need to log back in to the X session.  For sessionless machines, you
will want to run "svnkeyrings.py --sessionless reset" again.
"""


def main():
    ""
    optL,argL = getopt.getopt( sys.argv[1:], 'h',
                               ['help','sessionless','csh','bash'] )

    if ('-h','') in optL or ('--help','') in optL:
        print help_string
        return

    sessionless = ('--sessionless','') in optL

    if 'reset' in argL:
        remove_progress_file()

        if sessionless:
            run_reset_machine_sequence()

        else:
            run_reset_sequence()

    else:
        state = read_last_state_from_progress_file()

        if state == 'seahorse':
            run_subversion_sequence()

        elif state == 'svnconfig':
            initialize_subversion_password_in_keyring()
            write_session_info_file()

        else:
            syntax = 'csh' if ('--csh','') in optL else 'bash'
            print_keyring_variables( syntax )


############################################################################

def run_reset_sequence():
    """
    """
    ok = introduction()

    if ok:
        initialize_progress_file()

        ok = run_seahorse()

        if ok:
            print3( logout_string )


intro_string = """
=============================================================================

Meant to work in RHEL 6 with a GNOME windows environment.  The keyrings will
be reset, Subversion settings adjusted, and the login keyring will be
initialized using Subversion.

Subversion 1.8 is recommended to be in your PATH when running this script.
Version 1.7 may or may not work to initialize the keyring, but it should work
after using 1.8 to initialize the keyring.

Note that initializing the 'login' keyring requires you to log out of your
X session and log back in again, so be prepared to close all your running
programs.
"""

logout_string = """
=============================================================================

Now log out of this X session, log back in, start a terminal, and run this
script again without any arguments.
"""


def introduction():
    """
    """
    response = prompt_for_input( intro_string )

    ok = response_is_yes( response )
    
    return ok


############################################################################

seahorse_string = """
=============================================================================

This calls the "seahorse" GUI program for manipulating keyrings and such.
When it comes up, go to the Passwords tab and delete the 'login' and 'default'
entries.  You may experience a glitch in seahorse where the keyring entry does
not disappear right after you delete it.  Also note that you may see some
error/warning messages on the terminal coming from seahorse, but they should
be benign.

When done deleting the keyrings, exit the seahorse GUI.
"""

def run_seahorse():
    """
    """
    response = prompt_for_input( seahorse_string )

    ok = response_is_yes( response )

    if ok:
        x = subprocess.call( 'seahorse', shell=True )

        if x == 0:
            append_progress_file( 'seahorse' )
    
    return ok


############################################################################

mach_intro_string = """
=============================================================================

This will reset the subversion config directory and gnome-keyring daemon
specific to the current machine.  It will not survive reboots, so rerun in
this mode each time.

Subversion 1.8 is recommended to be in your PATH when running this script.
Version 1.7 may or may not work to initialize the keyring, but it should work
after using 1.8 to initialize the keyring.
"""

def run_reset_machine_sequence():
    ""
    response = prompt_for_input( mach_intro_string )
    ok = response_is_yes( response )

    if ok:
        ok,evars = start_gnome_keyring()

    if ok:
        initialize_subversion_password_in_keyring()
        write_keyring_info_file( evars, True )


def start_gnome_keyring():
    ""
    vars1 = launch_dbus()
    os.environ.update( vars1 )

    keyring_vars = launch_keyring()
    os.environ.update( keyring_vars )

    vars1.update( keyring_vars )

    return True, vars1


def launch_dbus():
    ""
    x,out = run_capture( 'dbus-launch --sh-syntax' )
    varD = parse_shell_output_for_variables( out )
    return varD


def parse_shell_output_for_variables( output ):
    ""
    varD = {}

    cmdL = shlex.split( output )
    for keyval in cmdL:
        kvL = keyval.split('=',1)
        if len(kvL) == 2:
            k = kvL[0].split()[-1]
            v = kvL[1].strip().strip(';').strip()
            varD[k] = v

    return varD


def launch_keyring():
    ""
    x,out = run_capture( 'gnome-keyring-daemon' )
    varD = parse_shell_output_for_variables( out )
    return varD


def write_keyring_info_file( evars, sessionless ):
    ""
    fname = keyring_info_filename( sessionless )

    fp = open( fname, 'w' )
    try:
        for k,v in evars.items():
            fp.write( k + '=' + v + '\n' )

    finally:
        fp.close()


def read_keyring_info_file():
    ""
    fname = keyring_info_filename( True )
    if not os.path.exists( fname ):
        fname = keyring_info_filename( False )

    varD = {}

    if os.path.exists( fname ):

        fp = open( fname, 'r' )
        try:
            for line in fp.readlines():
                line = line.strip()
                if line:
                    kvL = line.split('=',1)
                    if len(kvL) == 2:
                        varD[ kvL[0] ] = kvL[1]

        finally:
            fp.close()

    return varD


def keyring_info_filename( sessionless ):
    ""
    if sessionless:
        mach = os.uname()[1]
        fname = os.path.expanduser( '~/.subversion/keyring_info.'+mach )

    else:
        fname = os.path.expanduser( '~/.subversion/keyring_info.xsession' )

    return fname


############################################################################

svndir_string = """
=============================================================================

Subversion caches data in ~/.subversion, including ways to access your
password.  You can choose to wipe and refresh your ~/.subversion directory
or have this script modify it with settings for getting your password from
gnome-keyring.  Note that this script turns off plain text password store.

The only reason not to wipe is if you made changes to the config or servers
files that you want to retain.  FYI, this script is a little more robust
when it starts from the subversion defaults.

Finally, backups are made of the files that are modified.
"""


def run_subversion_sequence():
    """
    """
    svndir = os.path.expanduser( '~/.subversion' )

    ok = True

    if os.path.exists( svndir ):

        response = prompt_for_input( svndir_string,
                                     'Type "wipe", "modify", or "quit":',
                                     'wipe' )

        if response.lower() == 'modify':
            modify_subversion_configuration( svndir )

        elif response.lower() == 'wipe':
            shutil.rmtree( svndir )
            generate_subversion_files( svndir )
            modify_subversion_configuration( svndir )

        else:
            ok = False

    else:
        generate_subversion_files( svndir )
        modify_subversion_configuration( svndir )

    if ok:
        initialize_subversion_password_in_keyring()
        write_session_info_file()


def write_session_info_file():
    ""
    varD = get_session_keyring_variables()
    write_keyring_info_file( varD, False )


def get_session_keyring_variables():
    ""
    varD = {}

    for k in ['GNOME_KEYRING_SOCKET','SSH_AUTH_SOCK']:
        varD[k] = os.environ[k]

    return varD


def modify_subversion_configuration( svndir ):
    ""
    modify_subversion_config_file( svndir )
    modify_subversion_servers_file( svndir )
    append_progress_file( 'svnconfig' )


def generate_subversion_files( svndir ):
    ""
    print3( 'Generating subversion configuration files...' )

    majr,minr,micr = get_subversion_version()

    check_subversion_version( majr, minr )

    cfg = os.path.expanduser( pjoin( svndir, 'config' ) )
    srv = os.path.expanduser( pjoin( svndir, 'servers' ) )

    assert os.path.exists( cfg ) and os.path.exists( srv ), \
        'Running "svn --version" failed to regenerate files: ' + \
        cfg + ', ' + srv


def check_subversion_version( majr, minr ):
    ""
    if majr == 1 and minr <= 6:
        print3( '*** Warning: subversion version 1.6 or less probably '
                'will not work with gnome-keyring (1.8 or higher recommended)' )
        time.sleep(1)

    elif majr == 1 and minr == 7:
        print3( '*** Warning: subversion version 1.7 may not work with '
                'gnome-keyring (1.8 or higher recommended)' )
        time.sleep(1)


def modify_subversion_config_file( svndir ):
    ""
    config = pjoin( svndir, 'config' )

    lineL = read_file_lines( config )

    done = False

    for i in range( len(lineL) ):
        sline = lineL[i].strip()
        if sline.startswith( 'password-stores =' ) or \
           sline.startswith( 'password-stores=' ):
            lineL[i] = 'password-stores = gnome-keyring\n'
            done = True
            break

    if not done:
        for i in range( len(lineL) ):
            sline = lineL[i].strip()
            if sline.startswith( '# password-stores =' ) or \
               sline.startswith( '# password-stores=' ) or \
               sline.startswith( '#password-stores =' ) or \
               sline.startswith( '#password-stores=' ):
                lineL[i] = 'password-stores = gnome-keyring\n'
                done = True
                break

    assert done, 'Failed to set password-stores in config file: '+config

    bak = config+'.bak_'+str(time.time())
    os.rename( config, bak )

    write_lines_to_file( config, lineL )


def modify_subversion_servers_file( svndir ):
    ""
    serv = pjoin( svndir, 'servers' )

    lineL = read_file_lines( serv )

    done = False

    global_section = False
    for i in range( len(lineL) ):
        sline = lineL[i].strip()

        if not global_section:
            if sline.startswith( '[global]' ):
                global_section = True

        elif sline.startswith( 'store-passwords =' ) or \
             sline.startswith( 'store-passwords=' ) or \
             sline.startswith( '# store-passwords =' ) or \
             sline.startswith( '# store-passwords=' ):
            lineL[i] = 'store-passwords = yes\n'
            done = True

        elif sline.startswith( 'store-plaintext-passwords =' ) or \
             sline.startswith( 'store-plaintext-passwords=' ) or \
             sline.startswith( '# store-plaintext-passwords =' ) or \
             sline.startswith( '# store-plaintext-passwords=' ):
            lineL[i] = 'store-plaintext-passwords = no\n'

    assert done, 'Failed to set store-passwords in servers file: '+serv

    bak = serv+'.bak_'+str(time.time())
    os.rename( serv, bak )

    write_lines_to_file( serv, lineL )


def read_file_lines( filename ):
    ""
    fp = open( filename, 'r' )
    try:
        lineL = [ line for line in fp.readlines() ]
    finally:
        fp.close()

    return lineL


def write_lines_to_file( fname, linelist ):
    ""
    fp = open( fname, 'w' )
    try:
        fp.write( ''.join( linelist ) )
    finally:
        fp.close()


############################################################################

init_string = """
=============================================================================

Now we run svn list on a repository URL to initialize the keyring and cache
some data in the ~/.subversion area.

The expected behavior is that you will have to enter your password the first
time, the second time the command is run may or may not ask for your password,
and the third time should definitely not require a password.
"""

def initialize_subversion_password_in_keyring():
    """
    """
    url = prompt_for_input( init_string,
                            'Enter your https repository URL:', 
                            default=None )

    if url and url.strip():

        cmd = 'svn list '+url

        print3( cmd )
        subprocess.call( cmd, shell=True )

        while True:

            print3( cmd )
            subprocess.call( cmd, shell=True )

            rtn = prompt_for_input( None, 'Run again?', default='n' )

            if not response_is_yes(rtn):
                break

        remove_progress_file()


def get_subversion_version():
    ""
    try:
        cmd = 'svn --version --quiet'
        x,out = run_capture( cmd )

        assert x == 0, \
            'svn --version command returned nonzero exit: '+str(pop.returncode)

        majr,minr,micr = [ int(v) for v in out.strip().split('.') ]

    except Exception:
        raise Exception( 'unable to determine svn version: ' + \
                         str(sys.exc_info()[1]) )

    return majr,minr,micr


############################################################################

if sys.version_info[0] > 2:
    raw_input = input


def prompt_for_input( info_string, prompt_string='Continue?', default='y' ):
    """
    """
    if info_string:
        print3( info_string )

    msg = prompt_string.rstrip() + ' '
    if default:
        msg += '['+default+'] '

    try:
        rtn = raw_input( msg )

        if not rtn.strip() and default:
            rtn = default

    except EOFError:
        rtn = ''

    return rtn


def response_is_yes( response ):
    ""
    if response and response.lower() in ['y','yes']:
        return True

    return False


############################################################################

def print_keyring_variables( syntax ):
    """
    """
    varD = read_keyring_info_file()

    vL = []
    for k,v in varD.items():
        if syntax == 'csh':
            vL.append( 'setenv '+k+' "'+v+'"' )
        else:
            vL.append( 'export '+k+'="'+v+'"' )

    sys.stdout.write( '; '.join( vL ) )
    sys.stdout.flush()


def set_environ():
    """
    """
    varD = read_keyring_info_file()
    os.environ.update( varD )


###########################################################################

def get_progress_file_name():
    ""
    return os.path.expanduser( '~/svnkeyrings.log' )


def initialize_progress_file():
    ""
    fp = open( get_progress_file_name(), 'w' )
    try:
        fp.write( 'reset\n' )
    finally:
        fp.close()


def append_progress_file( progress_string ):
    """
    """
    fp = open( get_progress_file_name(), 'a' )
    try:
        fp.write( progress_string + '\n' )
    finally:
        fp.close()


def read_last_state_from_progress_file():
    ""
    state = None

    fn = get_progress_file_name()

    if os.path.exists( fn ):
        fp = open( fn, 'r' )
        try:
            for line in fp.readlines():
                state = line.strip()
        finally:
            fp.close()

    return state

def remove_progress_file():
    ""
    fn = get_progress_file_name()

    if os.path.exists( fn ):
        os.remove( fn )


def print3( *args ):
    ""
    sys.stdout.write( ' '.join( [ str(arg) for arg in args ] ) + '\n' )
    sys.stdout.flush()


def run_capture( cmd ):
    ""
    proc = subprocess.Popen( cmd, shell=True, stdout=subprocess.PIPE )

    out,err = proc.communicate()
    x = proc.returncode

    if out != None:
        if sys.version_info[0] > 2:
            out = out.decode()

    return x,out


###########################################################################

if __name__ == "__main__":
    main()
