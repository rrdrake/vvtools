#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys, os
import re
import time

from . import argutil
from . import FilterExpressions


def parse_command_line( argvlist, vvtest_version=None ):
    ""
    psr = create_parser( argvlist, vvtest_version )

    opts = psr.parse_args( argvlist )

    args = opts.directory

    check_print_help_section( psr, args )

    check_deprecated_option_use( opts )

    check_print_version( opts, vvtest_version )

    derived_opts = adjust_options_and_create_derived_options( opts )

    return opts, derived_opts, args


##############################################################################

help_intro = """

The vvtest program generates and runs a set of scripts, called tests.
In normal operation, a list of tests to run is determined by recursively
scanning the directory arguments (or the current working directory if
none are given).  The tests are filtered using the command line options,
then run in a subdirectory prefixed with "TestResults".

The available options are listed below.  Additional help is available as
subhelp sections, which are displayed using "vvtest help <name>".  Available
subhelp section names are HELP_SECTION_LIST.
"""


help_filters = """

Tests can define arbitrary keywords, parameters with values, and can restrict
a test to run on specific platforms.  Tests can be selected (filtered) on the
command line using these keywords, parameter names, parameter values, and
platform names.

>  Options -k, -K, -R filter by keyword expression
>  Options -p, -P, -S filter by parameter name/value
>  Options -x, -X, -A select by platform name
>  Options --tmin, --tmax, --tsum select based on previous runtime

Also, the -s, --search option can be used to search input files for regular
expression patterns.

The "TDD" keyword is special.  If a test adds TDD to its keyword list, then
that test is not run by default.  To run tests that have the TDD keyword, add
the --include-tdd option.  The idea is that these tests are a work-in-progress
and are not expected to pass yet.  They are not "production".
"""


help_keywords = """

Keywords are arbitrary words defined in each test.  A vvtest command line
can include or exclude tests based on the keywords they define.
For example, using "-k fast" will only include tests that contain the keyword
"fast".

Each test defines implicit keywords, including the name of the test and
results keywords:

>  notrun  : test was in the test list but was not launched
>  notdone : test was launched but did not finish
>  fail    : test finished and returned a fail status
>  diff    : test finished with a diff status
>  pass    : test finished with a pass status
>  timeout : test finished by running out of time

Entire expressions can be built up by using multiple -k & -K options, using
the "/" operator, and using the "!" operator.  Examples:

>  -k key1/key2    means key1 OR key2
>  -K key1/key2    means ( NOT key1 ) OR ( NOT key2 )
>  -k key1 -k key2 means key1 AND key2
>  -k key1 -K key2 means key1 AND ( NOT key2 )
>  -k key1/!key2   means key1 OR ( NOT key2 )
>  -k key1 -K key2 means key1 AND ( NOT key2 )

Information on the keywords of tests as a whole can be gained by using the
--keys option.  When the --keys option is given, no tests are run.  It causes
vvtest to gather all the keywords for each of the tests and write them to
stdout.  Note that keyword filtering is applied before the keywords are
gathered.

The --files option is similar to --keys, except the test file names are
written instead of the collection of keywords.
"""


help_parameters = """

A test can define parameter names together with values.  A common (and
special) one is the number of processors, np, with values 1, 2, and 4, for
example.  At run time, the test expands into multiple tests, one for each
parameter value.

Tests can be selected based on their parameter names and values using the
-p and -P options.  Examples:

>  -p np=2         means include tests defining np and only value of 2
>  -p np           means include tests that define the parameter name np
>  -P np           means exclude tests that define the parameter name np
>  -p np<16        means include tests with np less than 16
>  -P np<=16       means exclude tests with np less than or equal to 16
>  -p np!=4        means include tests with np not equal to 4
>  -p np>4 -p np<8 means include tests with np>4 AND np<8
>  -p np<4/np>8    means include tests with np<4 OR np>8
>  -p np=1/!np     means include tests with np=1 OR (param np is not defined)
"""


help_platforms = """

The platform name defaults to the shell command uname, but may be overridden
by a project specific configuration.  In either case, the name is arbitrary
as far as test filtering goes.

Tests can add specifications that include or exclude platform names, so that
the test will run or will not run for a platform name.  The options -x and
-X can be used use include or exclude tests that would run on a platform
different from the current platform.  Examples,

>  -x Linux           means include tests that would run on Linux
>  -X Linux           means exclude tests that would run on Linux
>  -x Linux/Darwin    means include tests that would run on Linux OR Darwin
>  -x Linux -X Darwin means include if they would run on Linux AND ( NOT Darwin )

The -A option means ignore platform restrictions, so no tests will be excluded
due to platform names or expressions.
"""


help_runtimes = """

The total time each test takes to run is recorded and can be used to filter
the tests.

Using --tmin and --tmax will filter tests by previous runtime.
One or both --tmin and --tmax can be specified.  Tests are not run if the
previous runtime is below the minimum or above the maximum.  Tests that do
not have a previous runtime are not filtered out.

Using --tsum will filter tests by accumulated previous runtime.  Tests will be
sorted by previous runtime (in ascending order), then accumulated
until the sum of the runtimes is above the --tsum value.  Tests
that do not have a previous runtime are given the value zero.
"""


help_config = """

The vvtest logic is separated from configuration settings, although it comes
with defaults in the "config" subdirectory of the source.  A config directory
can be provided at runtime using the --config option or defining the
VVTEST_CONFIGDIR environment variable.  If so, vvtest will look at that
directory first when configuring the platform, batch queueing system, etc.

The --config option specifies the directory containing the platform
configuration and test helpers.  Vvtest looks for a file called
platform_plugin.py in that directory.  An environment variable can be used
instead, VVTEST_CONFIGDIR.

The -e option means use environment variable overrides.  By default, all
environment variables that can influence the execution of the tests are
cleared.  This switch will allow certain environment variables
to take precedence over the defaults determined by each platform
plugin.
"""


help_behavior = """

The first call to vvtest will scan for tests, filter, and run them.
Subsequent calls will also scan, but will merge in the previous results,
which can be used to filter by result keyword, such as "fail" or "notdone".

You can also change into the TestResults directory and run vvtest.  In this
case, no directory scanning is done.  Also, implicit filtering is done by
the subdirectory you are in - only tests at that directory level or below
will be run.

The test results directory will be called
>    TestResults.<platform name>.ON=<on options>.OFF=<off options>
where ON and OFF are only added if you specify -o or -O.  This name can be
overridden using the --run-dir option.

By default, tests that have already run will not be run again unless the -R
option is given.  Actually what happens is -k notdone/notrun is automatically
added, and specifying -R prevents that.  In fact, specifying a -k or -K option
with a results keyword (such as notrun or fail), will also prevent
-k notdone/notrun from being added.

To only scan for and filter tests, use -g.  This creates the test results
directories, but does not run the tests.


The -m option means do not overwrite existing scripts and no clean out.  By
default, the generated test scripts are always overritten and all files
in the test directory are removed.  Turning this option on
will prevent a test script that exists from being overwritten
and the test directory will not be cleaned out.

The --perms option will apply permission settings to files and directories in
the test execution area.  Multiple --perms options can be used and/or the
specifications can be comma separated.  If the specifcation starts
with "g=" then the group permissions are set.  If it starts with
"o=" then the world permissions are set.  If not one of these,
then it must be the name of a UNIX group, and the files and
directories have their group set.  Examples are "o=-", "g=rx,o=",
"wg-alegra,g=rws,o=---".

The -C or --postclean option will clean out the test directory of each test
after it shows a "pass".  Only those tests that "pass" are cleaned out after
they run.  The execute.log file is not removed.

The --force option will force vvtest to run.  When vvtest finishes running
tests, a mark is placed in the testlist file.  If another vvtest execution is
started while the first is still running, the second will refuse
to run because it cannot find the mark.  It is possible that vvtest
dies badly and the mark is never placed (and never will be).  So
vvtest can be forced to run in this case by using --force.

The -M option will use the given directory to actually contain the test
results. The tests will run faster if a local disk is used to write to.
The special value "any" will search for a scratch disk.

The --run-dir option will override the default test results directory naming
mechanism of TestResults.platform.ON=...  It is the subdirectory under the
current working directory in which all the tests will be run.

The -L option means to not use log files.  By default, each test output is
sent to a log file contained in the run directory.  This option turns
off this redirection.  This can be used to debug a single test
for example, so that the results of the run are seen immediately.
Note that "-n 1" can be used with the -L option to send many test
results to stdout/stderr without interleaving the output (the
"-n 1" prevents multiple tests from being run simultaneously).

The -a or --analyze option will only execute the analysis portions of the
tests (and skip running the main code again).  This is only useful if the
tests have already been run previously.
"""


help_resources = """

By default, vvtest will try not to oversubscribe the current machine.
It does this by limiting the tests in flight to use equal or fewer processors
than are available.  Each test is assumed to need one CPU core, unless the
test specifies a larger value.

The -n option will set the number of processers to utilize to the given value.
By default, this number is set to the maximum number of processors on the
platform.
      
The -N option will wet the maximum number of processers available on the
current platform.  By default, the system is probed to determine this value.
Note that tests requiring more than this number of processors are not run.
      
The --plat option sets the platform name for use by plugins and default
resource settings. This can be used to specify the platform name,
thus overriding the default platform name.  For example, you could use
"--plat Linux".
      
The --platopt option specifies platform options.
Some platform plugins understand special
options.  Use this to send command line options into the platform
plugin.  For example, use "--platopt ppn=4" to set the number
of processors per node to an artificial value of 4.
      
The -T option will apply a timeout value in seconds to each test.  Zero means
no timeout.  In batch mode, note that the time given to the batch
queue for each batch job is the sum of the timeouts of each test.
      
The --timeout-multiplier option will
apply a float multiplier to the timeout value for each test.

The --max-timeout option will
apply a maximum timeout value for each test and for batch jobs.
It is the last operation performed when computing timeouts.
"""


help_batch = """

Tests can be run under a batch queue server (such as SLURM or LSF).

The --batch option will
collect sets of tests in and submit them to a batch queue rather
than executing individual tests as resources become open.  In
order to use the queue submit capability of batch systems, the
plugin for the platform must be set up to launch batch jobs.

The --batch-limit option will will limit the number of batch jobs submitted
to the queue at any one time.  The default is 5 concurrent batch jobs.

The --batch-length option limits the
number of tests that are placed into each batch set.  The sum
of the timeouts of the tests in each set will be less than the
given number of seconds.  The default is 30 minutes.  The longer
the length, the more tests will go in each batch job; the shorter
the length, the fewer.  A value of zero will force each test to
run in a separate batch job.
"""


help_results = """

To display information on a previous test run, use vvtest -i.  When
the current working directory is not a TestResults directory, the same
-o & -O options and --plat option must be given on the command line.
It is safe to run vvtest -i even when another process is running vvtest to
execute tests.

When listing the tests, the --sort option can be used to control the order.
When test results are printed to the screen, they are sorted by
their test name by default.  Use this option to sort by other fields:
>   n : test name (the default)
>   x : execution directory name
>   t : test run time
>   d : execution date
>   s : test status (such as pass, fail, diff, etc)
>   r : reverse the order
If more than one character is given, then ties on the first
ordering are broken by subsquent orderings.  For example,
"--sort txr" would sort first by runtime, then by execution
directory name, and would reverse the order (so largest runtimes
first, smallest runtimes last).

The --save-results option.  If used with the -i option, this saves test
results for an existing run to the testing directory in a file called
'results.<date>.<platform>.<compiler>.<tag>' where the "tag" is
an optional, arbitrary string determined by the --results-tag
option.  The testing directory is determined by the platform
plugins, but can be overridden by defining the environment
variable TESTING_DIRECTORY to the desired absolute path name.

If used without the -i option, this causes an empty results
file to be written at the start of the testing sequence, and a
final results file to be written when the test sequence finishes.

When the --results-tag=<string> option is used with --save-results, this adds
a string to the results file name within the testing directory.

The --junit=<filename> option will write a test summary to a file in the
JUnit XML format.  Should be compatible with Jenkins JUnit test results plugin.
Can be used as part of the vvtest run, or given with the -i option.
"""


help_baseline = """

Rebaseline generated files from a previous run by copying them over
the top of the files in the directory which contain the XML test
description.  Keywords and parameter options can be given to control
which tests get rebaselined, including results keywords like "diff".
If no keyword options are specified, then all tests that show a diff
status are rebaselined, which would be equivalent to running the
command "vvtest -b -k diff".

The rebaseline option can be given when the current working directory is
a TestResults directory with the same behavior.
"""


help_extract = """

Extract tests from a test tree.  This mode copies the files from the
test source directory into the 'to_directory' given as the argument to
the --extract option.  Keyword filtering can be applied, and is often
used to pull tests that can be distributed to various customers.
"""


help_deprecated = """

>DEPRECATED BUT STILL AVAILABLE:

The -v option used to print the program version, but now means "verbose".
Use --version instead to get the version.

The --pipeline option is deprecated.  It is equivalent to --batch.

The --check=<name> option activates optional sections in the test files.
You should migrate use of this option to the --test-args option.
The execution blocks in the test files may have an ifdef="CHECK_NAME" attribute,
where the NAME portion is just upper case of <name>.  Those blocks
are not active by default.  Using this option will cause those
blocks to be executed as part of the test.

The --qsub-limit option is being deprecated in favor of --batch-limit (with
the same meaning).

The --qsub-length option is being deprecated in favor of --batch-length (with
the same meaning).

>DEPRECATED AND REMOVED:

The option --vg could be used to pass the -vg option to each test script.
It has been replaced by the --test-args option.

The -G option has been removed.  It is the same as -g.

The -F option is now an error; it has been replaced with -R.

The -H option has been removed.  It is the same as --help.
"""


def create_parser( argvlist, vvtest_version ):
    ""
    argutil.set_num_columns_for_help_formatter()

    names = ', '.join( get_help_section_list() )
    intro = help_intro.replace( 'HELP_SECTION_LIST', names )
    psr = argutil.ArgumentParser( prog='vvtest',
                        description=intro,
                        formatter_class=argutil.ParagraphHelpFormatter )

    psr.add_argument( '--version', action='store_true',
        help='Print the version of vvtest and exit.' )
    psr.add_argument( '-v', dest='dash_v', action='count',
        help='Add verbosity to console output.  Can be repeated, which gives '
             'even more verbosity.' )

    grp = psr.add_argument_group( 'Test selection / filters (subhelp: filters)' )

    # keyword filtering
    grp.add_argument( '-k', dest='dash_k', action='append',
        help='Filter tests by including those with a keyword or keyword '
              'expression, such as "-k fast" or "-k fail/diff" '
              '(subhelp: keywords).' )
    grp.add_argument( '-K', dest='dash_K', action='append',
        help='Filter tests by including those with a keyword or keyword '
             'expression, such as "-K long" or "-K fail/notdone".' )
    grp.add_argument( '-R', dest='dash_R', action='store_true',
        help='Rerun tests.  Normally tests are not run if they previously '
             'completed.' )
    grp.add_argument( '-F', dest='dash_F', action='store_true',
        help='Deprecated; use -R.' )

    # parameter filtering
    grp.add_argument( '-p', dest='dash_p', action='append',
        help='Filter tests by parameter name and value, such as '
             '"-p np=8" or "-p np<8" or "-p np" '
             '(subhelp: parameters).' )
    grp.add_argument( '-P', dest='dash_P', action='append',
        help='Filter the set of tests by excluding those with a parameter '
             'name and value, such as "-P np".' )
    grp.add_argument( '-S', dest='dash_S', action='append',
        help='Using name=value will set the parameter name to that value in '
             'any test that defines the parameter, such as "-S np=16".' )

    # platform filtering
    grp.add_argument( '-x', dest='dash_x', action='append',
        help='Include tests that would, by default, run for the given '
             'platform name, such as "-x Linux" or "-x TLCC2/CTS1" '
             '(subhelp: platforms).' )
    grp.add_argument( '-X', dest='dash_X', action='append',
        help='Exclude tests that would, by default, run for the given '
             'platform name, such as "-X Linux" or "-X TLCC2/CTS1".' )
    grp.add_argument( '-A', dest='dash_A', action='store_true',
        help='Ignore platform exclusions specified in the tests.' )

    # runtime filtering
    grp.add_argument( '--tmin',
        help='Only include tests whose previous runtime is greater than '
             'the given number of seconds (subhelp: runtimes).' )
    grp.add_argument( '--tmax',
        help='Only include tests whose previous runtime is less than the '
             'given number of seconds.' )
    grp.add_argument( '--tsum',
        help='Include as many tests as possible such that the sum of their '
             'runtimes is less than the given number of seconds.' )

    # more filtering
    grp.add_argument( '-s', '--search', metavar='REGEX', dest='search',
                      action='append',
        help='Include tests that have an input file containing the '
             'given regular expression.' )
    grp.add_argument( '--include-tdd', action='store_true',
        help='Include tests that contain the keyword "TDD", which are '
             'normally not included.' )

    # behavior
    grp = psr.add_argument_group( 'Runtime behavior (subhelp: behavior)' )
    grp.add_argument( '-o', dest='dash_o', action='append',
        help='Turn option(s) on, such as "-o dbg" or "-o intel17+dbg" '
             '(subhelp: options).' )
    grp.add_argument( '-O', dest='dash_O', action='append',
        help='Turn option(s) off if they would be on by default.' )
    grp.add_argument( '-w', dest='dash_w', action='store_true',
        help='Wipe previous test results, if present.' )
    grp.add_argument( '-m', dest='dash_m', action='store_true',
        help='Do not clean out test result directories before running.' )
    grp.add_argument( '--perms', action='append',
        help='Apply permission settings to files and directories in the '
             'test execution area.' )
    grp.add_argument( '-C', '--postclean', dest='postclean', action='store_true',
        help='Clean the test execution directory after a "pass".' )
    grp.add_argument( '--force', action='store_true',
        help='Force vvtest to run even if it appears to be running in '
             'another process.' )
    grp.add_argument( '-M', dest='dash_M',
        help='Use this path to contain the test executions.' )
    grp.add_argument( '--run-dir',
        help='The name of the subdir under the current working '
             'directory to contain the test execution results.' )
    grp.add_argument( '-L', dest='dash_L', action='store_true',
        help='Do not redirect test output to log files.' )
    grp.add_argument( '-a', '--analyze', dest='analyze', action='store_true',
        help='Pass option to tests to only execute sections marked analysis.' )
    grp.add_argument( '--check', action='append',
        help='This option is deprecated (subhelp: deprecated).' )
    grp.add_argument( '--test-args', metavar='ARGS', action='append',
        help='Pass options and/or arguments to each test script.' )

    # resources
    grp = psr.add_argument_group( 'Resource controls (subhelp: resources)' )
    grp.add_argument( '-n', dest='dash_n', type=int,
        help='Set the number of processors to use at one time.' )
    grp.add_argument( '-N', dest='dash_N', type=int,
        help='Set the maximum number of processors to use, and filter out '
             'tests requiring more.' )
    grp.add_argument( '--plat',
        help='Use this platform name for defaults and plugins.' )
    grp.add_argument( '--platopt', action='append',
        help='Pass through name=value settings to the platform, such '
             'as "--platopt ppn=4".' )
    grp.add_argument( '-T', dest='dash_T',
        help='Apply timeout in seconds to each test.' )
    grp.add_argument( '--timeout-multiplier', type=float,
        help='Apply a float multiplier to the timeout value for each test.' )
    grp.add_argument( '--max-timeout',
        help='Maximum timeout value for each test and for batch jobs.' )

    # config
    grp = psr.add_argument_group( 'Runtime configuration (subhelp: config)' )
    grp.add_argument( '-j', '--bin-dir', dest='bin_dir', metavar='BINDIR',
        help='Specify the directory containing the project executables.' )
    grp.add_argument( '--config', action='append',
        help='Directory containing testing plugins and helpers. '
             'Same as VVTEST_CONFIGDIR environment variable.' )
    grp.add_argument( '-e', dest='dash_e', action='store_true',
        help='Prevents test harness from overwriting environment '
             'variables prior to each test.' )

    # batch
    grp = psr.add_argument_group( 'Batching / queuing (subhelp: batch)' )
    grp.add_argument( '--batch', action='store_true',
        help='Groups tests, submits to the batch queue manager, and '
             'monitors for completion.' )
    grp.add_argument( '--pipeline', action='store_true',
        help='Deprecated.  Use --batch instead.' )
    grp.add_argument( '--batch-limit', type=int,
        help='Limit the number of batch jobs in the queue at any one time. '
             'Default is 5.' )
    grp.add_argument( '--qsub-limit', type=int,
        help='Deprecated; use --batch-limit.' )
    grp.add_argument( '--batch-length', type=int,
        help='Limit the number of tests in each job group such that the '
             'sum of their runtimes is less than the given value. '
             'Default is 30 minutes.' )
    grp.add_argument( '--qsub-length', type=int,
        help='Deprecated; use --batch-length.' )
    psr.add_argument( '--qsub-id', type=int, help=argutil.SUPPRESS )

    # results
    grp = psr.add_argument_group( 'Results handling (subhelp: results)' )
    grp.add_argument( '-i', dest='dash_i', action='store_true',
        help='Read and display testing results. Can be run while another '
             'vvtest is running.' )
    grp.add_argument( '--sort', metavar='LETTERS', action='append',
        help='Sort test listings.  Letters include n=name, '
             'x=execution name, t=runtime, d=execution date, '
             's=status, r=reverse the order.' )
    grp.add_argument( '--save-results', action='store_true',
        help='Save the test results to the TESTING_DIRECTORY.' )
    grp.add_argument( '--results-tag',
        help='Add an arbitrary tag to the --save-results output file.' )
    grp.add_argument( '--results-date', metavar='DATE',
        help='Specify the testing date, used as a marker or file name in some '
             'output formats. Can be seconds since epoch or a date string.' )
    grp.add_argument( '--junit', metavar='FILENAME',
        help='Writes a test summary file in the JUnit XML format.' )
    grp.add_argument( '--html', metavar='FILENAME',
        help='Write a test summary file in HTML format.' )
    grp.add_argument( '--gitlab', metavar='DIRECTORY',
        help='Write test summary as a set of files in the GitLab '
             'Flavored Markdown format.' )

    grp = psr.add_argument_group( 'Other operating modes' )
    grp.add_argument( '-b', dest='dash_b', action='store_true',
        help='Rebaseline tests that have diffed (subhelp: baseline).' )

    grp.add_argument( '-g', dest='dash_g', action='store_true',
        help='Scan for tests and populate the test results tree, '
             'but do not run any tests (subhelp: behavior).' )

    grp.add_argument( '--extract', metavar='DESTDIR',
        help='Extract test files from their source to the DESTDIR '
             'directory (subhelp; extract).' )

    grp.add_argument( '--keys', action='store_true',
        help='Gather and print all the keywords in each test, after '
             'filtering (subhelp: keywords).' )
    grp.add_argument( '--files', action='store_true',
        help='Gather and print the file names that would be run, after '
             'filtering (subhelp: keywords).' )

    psr.add_argument( 'directory', nargs='*' )

    return psr


##############################################################################

def check_print_version( opts, vvtest_version ):
    ""
    if opts.version:
        print3( vvtest_version )
        sys.exit(0)


def check_deprecated_option_use( opts ):
    ""
    if opts.dash_F:
        errprint( '*** error: the -F option is deprecated (use -R instead).' )
        sys.exit(1)

    if opts.qsub_limit and opts.batch_limit:
        errprint( '*** error: cannot use --qsub-limit and --batch-limit '
                  'at the same time; --qsub-limit is deprecated.' )
        sys.exit(1)

    if opts.qsub_length and opts.batch_length:
        errprint( '*** error: cannot use --qsub-length and --batch-length '
                  'at the same time; --qsub-length is deprecated.' )
        sys.exit(1)

    if opts.pipeline:
        opts.batch = True  # --pipeline replaced with --batch

    if opts.qsub_limit:
        # --qsub-limit replaced with --batch-limit
        opts.batch_limit = opts.qsub_limit

    if opts.qsub_length:
        # --batch-limit replaced with --batch-limit
        opts.batch_length = opts.qsub_length


def adjust_options_and_create_derived_options( opts ):
    ""
    derived_opts = {}

    try:

        errtype = 'keyword options'
        expr = create_keyword_expression( opts.dash_k, opts.dash_K )
        derived_opts['keyword_expr'] = expr

        errtype = 'parameter options'
        params = create_parameter_list( opts.dash_p, opts.dash_P )
        derived_opts['param_list'] = params

        errtype = 'setting paramters'
        paramD = create_parameter_settings( opts.dash_S )
        derived_opts['param_dict'] = paramD

        errtype = 'search option'
        rxL = create_search_regex_list( opts.search )
        derived_opts['search_regexes'] = rxL

        errtype = 'platform options'
        expr = create_platform_expression( opts.dash_x, opts.dash_X )
        derived_opts['platform_expr'] = expr

        errtype = 'the sort option'
        letters = clean_sort_options( opts.sort )
        derived_opts['sort_letters'] = letters

        errtype = 'platopts'
        platD = create_platform_options( opts.platopt )
        derived_opts['platopt_dict'] = platD

        errtype = 'batch-limit'
        if opts.batch_limit != None and opts.batch_limit < 0:
            raise Exception( 'limit cannot be negative' )

        errtype = 'batch-length'
        if opts.batch_length != None and opts.batch_length < 0:
            raise Exception( 'length cannot be negative' )

        errtype = 'on/off options'
        onL,offL = clean_on_off_options( opts.dash_o, opts.dash_O )
        derived_opts['onopts'] = onL
        derived_opts['offopts'] = offL

        errtype = '--run-dir'
        if opts.run_dir != None:
            d = opts.run_dir
            if os.sep in d or d != os.path.basename(d):
                raise Exception( 'must be a non-empty, single path segment' )

        errtype = 'num procs'
        if opts.dash_n != None and opts.dash_n <= 0:
            raise Exception( 'must be positive' )

        errtype = 'max procs'
        if opts.dash_N != None and float(opts.dash_N) <= 0:
            raise Exception( 'must be positive' )

        errtype = 'timeout'
        if opts.dash_T and float(opts.dash_T) < 0.0:
            opts.dash_T = 0.0

        errtype = 'timeout multiplier'
        if opts.timeout_multiplier and not float(opts.timeout_multiplier) > 0.0:
            raise Exception( 'must be positive' )

        errtype = 'max timeout'
        if opts.max_timeout and not float(opts.max_timeout) > 0.0:
            raise Exception( 'must be positive' )

        errtype = 'tmin/tmax/tsum'
        mn,mx,sm = convert_test_time_options( opts.tmin, opts.tmax, opts.tsum )
        opts.tmin = mn
        opts.tmax = mx
        opts.tsum = sm

        errtype = '-j option'
        if opts.bin_dir != None:
            opts.bin_dir = os.path.normpath( os.path.abspath( opts.bin_dir ) )

        errtype = 'config directory'
        if opts.config != None:
            for i,d in enumerate( opts.config ):
                opts.config[i] = os.path.normpath( os.path.abspath( d ) )

        errtype = '--results-date'
        if opts.results_date != None:
            opts.results_date = check_convert_date_spec( opts.results_date )

    except Exception:
        errprint( '*** error: command line problem with', errtype+':',
                  sys.exc_info()[1] )
        sys.exit(1)

    return derived_opts


def create_keyword_expression( keywords, not_keywords ):
    ""
    keywL = []

    if keywords:
        keywL.extend( keywords )

    # change -K into -k expressions by using the '!' operator
    if not_keywords:
        for s in not_keywords:
            bangL = map( lambda k: '!'+k, s.split('/') )
            keywL.append( '/'.join( bangL ) )

    expr = FilterExpressions.WordExpression()

    if len(keywL) > 0:
        expr.append( keywL, 'and' )

    return expr


def create_parameter_list( params, not_params ):
    ""
    # construction will check for validity
    FilterExpressions.ParamFilter( params )
    FilterExpressions.ParamFilter( not_params )

    plist = []

    if params:
        plist.extend( params )

    if not_params:
        # convert -P values into -p values
        for s in not_params:
            s = s.strip()
            if s:
                orL = []
                for p in s.split('/'):
                    p = p.strip()
                    if p:
                        orL.append( '!' + p )

                if len(orL) > 0:
                    plist.append( '/'.join( orL ) )

    return plist


def create_platform_expression( platforms, not_platforms ):
    ""
    expr = None

    if platforms or not_platforms:
        expr = FilterExpressions.WordExpression( platforms )

    if not_platforms:
        # convert -X values into -x values
        exprL = []
        for s in not_platforms:
            s = s.strip()
            if s:
                orL = []
                for p in s.split('/'):
                    p = p.strip()
                    if p:
                        orL.append( '!' + p )

                if len( orL ) > 0:
                    exprL.append( '/'.join( orL ) )

        if len( exprL ) > 0:
            expr.append( exprL, 'and' )

    return expr


def create_search_regex_list( pattern_list ):
    ""
    regexL = None

    if pattern_list != None:

        regexL = []

        for pat in pattern_list:
            regexL.append( re.compile( pat, re.IGNORECASE | re.MULTILINE ) )

    return regexL


def create_parameter_settings( set_param ):
    ""
    pD = None

    if set_param:
        pD = {}
        for s in set_param:
            L = s.split( '=', 1 )
            if len(L) < 2 or not L[0].strip() or not L[1].strip():
                raise Exception( 'expected form "param=value"' )

            n,v = [ s.strip() for s in L ]

            if n in pD:
                pD[n].extend( v.split() )
            else:
                pD[n] = v.split()

    return pD


def clean_sort_options( sort ):
    ""
    letters = None

    if sort:

        letters = ''.join( [ s.strip() for s in sort ] )
        for c in letters:
            if c not in 'nxtdsr':
                raise Exception( 'invalid --sort character: ' + c )
    
    return letters


def create_platform_options( platopt ):
    ""
    pD = {}

    if platopt:
        for po in platopt:

            po = po.strip()
            if not po:
                raise Exception( 'value cannot be empty' )

            L = po.split( '=', 1 )
            if len(L) == 1:
                pD[ po ] = ''
            else:
                n = L[0].strip()
                if not n:
                    raise Exception( 'option name cannot be empty: '+po )

                pD[n] = L[1].strip()

    return pD


def clean_on_off_options( on_options, off_options ):
    ""
    onL = []
    offL = []

    if on_options:
        onL = gather_on_off_values( on_options )

    if off_options:
        offL = gather_on_off_values( off_options )

    return onL, offL


def gather_on_off_values( onoff ):
    ""
    S = set()
    for o1 in onoff:
        for o2 in o1.split( '+' ):
            for o3 in o2.split():
                S.add( o3 )
    L = list( S )
    L.sort()

    return L


def convert_test_time_options( tmin, tmax, tsum ):
    ""
    if tmin != None:
        tmin = float(tmin)

    if tmax != None:
        tmax = float(tmax)
        if tmax < 0.0:
            raise Exception( 'tmax cannot be negative' )

    if tsum != None:
        tsum = float(tsum)

    return tmin, tmax, tsum


def check_convert_date_spec( date_spec ):
    ""
    spec = date_spec.strip()

    if not spec:
        raise Exception( 'cannot be empty' )

    if '_' not in spec:
        try:
            secs = float( spec )
            if secs > 0:
                tup = time.localtime( secs )
                tmstr = time.strftime( "%a %b %d %H:%M:%S %Y", tup )
                spec = secs  # becomes a float right here
        except Exception:
            pass

    return spec


def check_print_help_section( psr, args ):
    """
    If args=["help"] then the parser is run with -h (and sys.exit called).
    If args=["help","section name"] then that help section is written and
    sys.exit called.
    """
    if len(args) > 0 and args[0] == 'help':

        if len(args) == 1:
            psr.parse_args( ['-h'] )

        else:
            print_help_section( args[1] )
            sys.exit(0)


def print_help_section( section_name ):
    ""
    try:
        text = eval( 'help_'+section_name )
    except Exception:
        print_help_section_list()
    else:
        ncol = int( os.environ.get( 'COLUMNS', 80 ) ) - 2
        print3( argutil.format_text( text, ncol, '' ) )


def print_help_section_list():
    """
    Gather then print the list of available help sections.
    """
    namelist = get_help_section_list()
    text = 'Available help sections: ' + ', '.join( namelist )
    ncol = int( os.environ.get( 'COLUMNS', 80 ) ) - 2
    print3( argutil.format_text( text, ncol, '' ) )


def get_help_section_list():
    """
    Use introspection to gather all variables in this module which start with
    "help_" and whose value is a string.  Return as a list.
    """
    namelist = []

    for attrname in dir( sys.modules[__name__] ):
        if attrname.startswith( 'help_' ) and len(attrname) > 5:
            try:
                val = eval( attrname )
            except Exception:
                pass
            else:
                if type(val) == type(''):
                    namelist.append( attrname[5:] )

    return namelist


def print3( *args ):
    sys.stdout.write( ' '.join( [ str(x) for x in args ] ) + os.linesep )
    sys.stdout.flush()


def errprint( *args ):
    sys.stderr.write( ' '.join( [ str(x) for x in args ] ) + os.linesep )
    sys.stderr.flush()
