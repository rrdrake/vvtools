#!/bin/sh

analyze_only() {
    # the --analyze option means only execute operations in the test that
    # analyze previously computed results, such as comparing to baseline or
    # examining order of convergence
    if [ $opt_analyze = 1 ]
    then
        return 0  # this is true as an exit status
    else
        return 1  # this is false as an exit status
    fi
}

cmdline_option() {
    # given a command line option name, this returns true if that option
    # was given on the command line
    optname=$1
    for var in $CMDLINE_VARS ; do
        eval val="\$$var"
        [ "X$val" = "X$optname" ] && return 0
    done
    return 1
}


platform_expr() {
    # Evaluates the given platform expression against the current
    # platform name.  For example, the expression could be
    # "Linux or Darwin" and would be true if the current platform
    # name is "Linux" or if it is "Darwin".
    # Returns 0 (zero) if the expression evaluates to true,
    # otherwise non-zero.
    
    result=`"$PYTHONEXE" "$VVTESTSRC/libvvtest/FilterExpressions.py" -f "$1" "$PLATFORM"`
    xval=$?
    if [ $xval -ne 0 ]
    then
        echo "$result"
        echo "*** error: failed to evaluate platform expression $1"
        exit 1
    fi
    [ "$result" = "true" ] && return 0
    return 1
}

parameter_expr() {
    # Evaluates the given parameter expression against the
    # parameters defined for the current test.  For example, the
    # expression could be "dt<0.01 and dh=0.1" where dt and dh are
    # parameters defined in the test.
    # Returns 0 (zero) if the expression evaluates to true,
    # otherwise non-zero.
    
    result=`"$PYTHONEXE" "$VVTESTSRC/libvvtest/FilterExpressions.py" -p "$1" "$PARAM_DICT"`
    xval=$?
    if [ $xval -ne 0 ]
    then
        echo "$result"
        echo "*** error: failed to evaluate parameter expression $1"
        exit 1
    fi
    [ "$result" = "true" ] && return 0
    return 1
}

option_expr() {
    # Evaluates the given option expression against the options
    # given on the vvtest command line.  For example, the expression
    # could be "not dbg and not intel", which would be false if
    # "-o dbg" or "-o intel" were given on the command line.
    # Returns 0 (zero) if the expression evaluates to true,
    # otherwise non-zero.
    
    result=`"$PYTHONEXE" "$VVTESTSRC/libvvtest/FilterExpressions.py" -o "$1" "$OPTIONS"`
    xval=$?
    if [ $xval -ne 0 ]
    then
        echo "$result"
        echo "*** error: failed to evaluate option expression $1"
        exit 1
    fi
    [ "$result" = "true" ] && return 0
    return 1
}

############################################################################

# a test can call "set_have_diff" one or more times if it
# decides the test should diff, then at the end of the test,
# call "if_diff_exit_diff"

have_diff=0
set_have_diff() {
    have_diff=1
}

exit_diff() {
    echo "*** exiting diff"
    exit $diff_exit_status
}

if_diff_exit_diff() {
    if [ $have_diff -ne 0 ]
    then
        exit_diff
    fi
}

############################################################################

sedfile() {
    # arguments are the file name then a substitution
    # expression, such as "s/pattern/replacement/"
    # additional expressions can be given but you must
    # preceed each with -e
    # note that an edit of a soft linked file will remove
    # the soft link and replace the file name with a regular
    # file with modified contents

    if [ $# -lt 2 ]
    then
        echo "*** error: sedfile() requires at least 2 arguments"
        exit 1
    fi

    fname=$1
    shift
    
    echo "sedfile: sed -e $@ $fname > $fname.sedfile_tmp"
    sed -e "$@" $fname > $fname.sedfile_tmp || exit 1

    echo "sedfile: mv $fname.sedfile_tmp $fname"
    rm -f $fname
    mv $fname.sedfile_tmp $fname
}

############################################################################

unixdiff() {
    # two arguments are accepted, 'file1' and 'file2'
    # If the filenames are different, then the differences are
    # printed and set_have_diff() is called.
    
    if [ $# -ne 2 ]
    then
        echo "*** error: unixdiff requires exactly 2 arguments"
        exit 1
    fi
    file1=$1
    file2=$2

    if [ ! -f $file1 ]
    then
        echo "*** unixdiff: file does not exist: $file1"
        exit 1
    fi
    if [ ! -f $file2 ]
    then
        echo "*** unixdiff: file does not exist: $file2"
        exit 1
    fi
    echo "unixdiff: diff $file1 $file2"
    setdiff=0
    diff $file1 $file2 || setdiff=1
    if [ $setdiff -eq 1 ]
    then
        echo "*** unixdiff: files are different, setting have_diff"
        set_have_diff
    fi
}

############################################################################

nlinesdiff() {
    # Counts the number of lines in 'filename' and if more
    # than 'maxlines' then print this fact and set have_diff
    
    if [ $# -ne 2 ]
    then
        echo "*** error: nlinesdiff requires exactly 2 arguments"
        exit 1
    fi
    filename=$1
    maxlines=$2

    if [ ! -f $filename ]
    then
        echo "*** nlinesdiff: file does not exist: $filename"
        exit 1
    fi

    nlines=`cat $filename | wc -l`
    
    echo "nlinesdiff: filename = $filename, num lines = $nlines, max lines = $maxlines"
    if [ $nlines -gt $maxlines ]
    then
        echo "*** nlinesdiff: number of lines exceeded max, setting have_diff"
        set_have_diff
    fi
}
