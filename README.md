The SCIDEV project is currently used to store and share a few software
development utilities.  Visit the
[Wiki](https://gitlab.sandia.gov/rrdrake/scidev/wikis/home)
for more documentation.

## The `vvtest` test harness

Vvtest evolved from Mike Wong's test
infrastructure in the late 1990s, through a python rewrite in the
mid 2000s, to a refactoring in 2016 to make it a project independent
utility.

Vvtest is contained in the `vvt` subdirectory.

## The `trigger` job control utility

For larger projects, automated process management gets quite involved.
Interdependent jobs can become complex very quickly.
When things do go according to plan, searching for and reading log files are
essential.  Finally, version controlling all the automated scripts being used
provides the team much needed communication and history.

The `trigger` utilities are contained in the `trig` subdirectory.
