#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.


# this section adjusts sys.path to work around python's algorithm for
# processing PYTHONPATH, which does weird things if paths contain colons.
# the logic here assumes all paths in PYTHONPATH are absolute

import os as _os
import sys as _sys

dL = _os.environ.get( 'PYTHONPATH', '' ).split( ':/' )

cnt = 0
for i,d in enumerate(dL):
    if i > 0:
        dL[i] = '/'+dL[i]
    cnt += d.count( ':' )

if cnt > 0:
    dL.reverse()
    for d in dL:
        _sys.path.insert( 1, d )


# for convenience, add symbols from each submodule

from .standard_utilities import *
from .simple_aprepro import simple_aprepro
from .simple_aprepro import main as simple_aprepro_main
