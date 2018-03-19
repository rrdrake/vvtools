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
When things do not go according to plan, searching for and reading log files is
essential.  Finally, version controlling all the automated scripts being used
provides the team much needed communication and history.

The `trigger` utilities are contained in the `trig` subdirectory.

## The `vvtools` V&V testing utilities

This is a collection of Exodus-based utilities for running verification analyses
on simulation output. It has its origins in ALEGRA but is much more generally
applicable. The main tools here are `exodus.py`, not to be confused with the 
seacas file of the same name, and `vcomp`, a convergence analysis tool.

The `vvtools` utilities are contained in the `tools` subdirectory. 
