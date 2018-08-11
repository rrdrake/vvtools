#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import re
import time
import getopt
import subprocess
import shutil
import shlex
from os.path import join as pjoin


help_string = """
USAGE
    svnkeyrings.py {-h|--help}
    svnkeyrings.py reset

SYNOPSIS

    This script helps set up for passwordless subversion access using
gnome-keyring.  Use the "reset" mode to reset your login keyring and
initialize for subversion access.  Afterward, use the svnwrap script to
run svn commands without having to enter a password.

The setup is specific to each machine.  On machines not running an X session,
the configuration will not survive reboots, so you have to run "reset" again.
On machines running an X session, a reboot just requires that you log back
into the desktop session.

To summarize, do this

    1. In a shell on the target machine, run "svnkeyrings.py reset"
    2. Copy the svnwrap script into a bin directory in your PATH
    3. Optionally, edit the svnwrap script to set the SVNEXE variable
    4. Use svnwrap in place of the svn program
"""


def main():
    ""
    optL,argL = getopt.getopt( sys.argv[1:], 'h', ['help'] )

    if ('-h','') in optL or ('--help','') in optL:
        print3( help_string )
        return

    if 'reset' in argL:

        remove_progress_file()

        if running_in_a_desktop_session():
            run_reset_desktop_session()
        else:
            run_reset_machine_sequence()

    else:
        state = read_last_state_from_progress_file()

        if state == 'seahorse':
            run_subversion_sequence()

        elif state == 'svnconfig':
            configdir = construct_subversion_config_dir_name()
            initialize_subversion_password_in_keyring( configdir )

        else:
            configdir = construct_subversion_config_dir_name()
            print3( configdir )


##################################################################

def reset_subversion_config( configdir ):
    ""
    if os.path.exists( configdir ):
        shutil.rmtree( configdir )
        time.sleep(1)

    generate_subversion_files( configdir )

    modify_subversion_config_file( configdir )
    modify_subversion_servers_file( configdir )


def construct_subversion_config_dir_name():
    ""
    mach = os.uname()[1]
    path = os.path.expanduser( '~/.subversion_'+mach )
    return path


def running_in_a_desktop_session():
    ""
    if 'DESKTOP_SESSION' in os.environ or \
       'GDMSESSION' in os.environ:
        return True

    return False


def kill_dbus_and_keyring_daemons():
    ""
    cmd = construct_ps_command()

    x,out = run_capture( cmd )

    proclist = extract_processes_to_kill( out )

    for spid,args in proclist:
        print3( 'Killing:', spid, '=', args )
        subprocess.call( 'kill -9 '+spid, shell=True )


def construct_ps_command():
    ""
    cmd = 'ps'

    usr = get_current_user_name()
    if usr:
        cmd += ' -u '+usr
    else:
        cmd += ' -A'

    if sys.platform == 'darwin':
        cmd += ' -o "pid,ppid,command"'
    else:
        cmd += ' -o "pid,ppid,args"'

    return cmd


def extract_processes_to_kill( ps_out ):
    ""
    wspat = re.compile('[ \t]+')

    proclist = []

    for line in re.split( '[\n\r]+', ps_out ):

        lineL = wspat.split( line.strip(), 2 )

        if len( lineL ) == 3:

            spid,sppid,args = lineL

            if should_kill_process( sppid, args ):
                proclist.append( [spid,args] )

    return proclist


def should_kill_process( sppid, args ):
    ""
    basenames = [ 'dbus-daemon', 'gnome-keyring-daemon' ]

    killit = False

    try:
        ppid = int( sppid )

    except Exception:
        pass

    else:
        if ppid == 1:
            prog = args.split()[0]
            if os.path.basename( prog ) in basenames:
                killit = True

    return killit


def get_current_user_name( try_getpass=True, try_homedir=True ):
    ""
    usr = None

    if try_getpass:
        try:
            import getpass
            usr = getpass.getuser()
        except Exception:
            usr = None

    if usr == None and try_homedir:
        try:
            usrdir = os.path.expanduser( '~' )
            if usrdir != '~':
                usr = os.path.basename( usrdir )
        except Exception:
            usr = None

    return usr


############################################################################

def run_reset_desktop_session():
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
        kill_dbus_and_keyring_daemons()

        configdir = construct_subversion_config_dir_name()
        print3( '\nSubversion config dir:', configdir )
        reset_subversion_config( configdir )

        evars = start_dbus_and_gnome_keyring()

        initialize_subversion_password_in_keyring( configdir )

        write_keyring_variable_files( configdir, evars )


def start_dbus_and_gnome_keyring():
    ""
    vars1 = launch_dbus()
    os.environ.update( vars1 )

    keyring_vars = launch_keyring()
    os.environ.update( keyring_vars )

    vars1.update( keyring_vars )

    return vars1


def launch_dbus():
    ""
    x,out = run_capture( 'dbus-launch --sh-syntax' )
    assert x == 0, "dbus-launch failed (non-zero exit status)"
    varD = parse_shell_output_for_variables( out )
    assert len( varD ) > 0, 'dbus-launch did not return any variables'
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
    assert x == 0, "gnome-keyring-daemon failed (non-zero exit status)"
    varD = parse_shell_output_for_variables( out )
    assert len( varD ) > 0, 'gnome-keyring-daemon did not return any variables'
    return varD


def write_keyring_variable_files( configdir, evars ):
    ""
    fname = pjoin( configdir, 'keyring_vars.sh' )

    fp = open( fname, 'w' )
    try:
        for k,v in evars.items():
            fp.write( 'export ' + k + '="' + v + '"\n' )

    finally:
        fp.close()

    fname = pjoin( configdir, 'keyring_vars.csh' )

    fp = open( fname, 'w' )
    try:
        for k,v in evars.items():
            fp.write( 'setenv ' + k + ' "' + v + '"\n' )

    finally:
        fp.close()

    fname = pjoin( configdir, 'keyring_vars.py' )

    fp = open( fname, 'w' )
    try:
        fp.write( '\nimport os\n' )
        for k,v in evars.items():
            fp.write( 'os.environ[ "'+k+'" ] = "'+v+'"\n' )

    finally:
        fp.close()


############################################################################

configdir_string = """
=============================================================================

Subversion caches data in a configuration directory (by default ~/.subversion).
This next step will select a machine specific configuration directory, wipe
it (if it exists), regenerate it, and modify it to get your password from
gnome keyring.
"""


def run_subversion_sequence():
    """
    """
    response = prompt_for_input( configdir_string )

    ok = response_is_yes( response )

    if ok:

        configdir = construct_subversion_config_dir_name()
        print3( '\nSubversion config dir:', configdir )

        reset_subversion_config( configdir )

        initialize_subversion_password_in_keyring( configdir )


def generate_subversion_files( configdir ):
    ""
    print3( 'Generating subversion configuration files...' )

    majr,minr,micr = get_subversion_version( configdir )

    check_subversion_version( majr, minr )

    cfg = os.path.expanduser( pjoin( configdir, 'config' ) )
    srv = os.path.expanduser( pjoin( configdir, 'servers' ) )

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


def modify_subversion_config_file( configdir ):
    ""
    config = pjoin( configdir, 'config' )

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


def modify_subversion_servers_file( configdir ):
    ""
    serv = pjoin( configdir, 'servers' )

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

def initialize_subversion_password_in_keyring( configdir ):
    """
    """
    url = prompt_for_input( init_string,
                            'Enter your https repository URL:', 
                            default=None )

    if url and url.strip():

        cmd = 'svn --config-dir ' + configdir + ' list '+url

        print3( cmd )
        subprocess.call( cmd, shell=True )

        while True:

            print3( cmd )
            subprocess.call( cmd, shell=True )

            rtn = prompt_for_input( None, 'Run again?', default='n' )

            if not response_is_yes(rtn):
                break

    remove_progress_file()


def get_subversion_version( configdir ):
    ""
    try:
        cmd = 'svn --config-dir '+configdir+' --version --quiet'
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
