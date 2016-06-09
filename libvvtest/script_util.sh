#!/bin/sh

############################################################################

# a test can call "set_have_diff" one or more times if it
# decides the test should diff, then at the end of the test,
# call "if_diff_exit_diff"

diff_exit_status=64
have_diff=0

set_have_diff() {
    have_diff=1
}

exit_diff() {
    echo "*** exitting diff"
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
