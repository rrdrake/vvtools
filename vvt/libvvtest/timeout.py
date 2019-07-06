#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys

from .fmtresults import LookupCache


class TimeHandler:

    def __init__(self, userplugin, platobj, cmdline_timeout,
                       timeout_multiplier, max_timeout):
        ""
        self.plugin = userplugin
        self.platobj = platobj
        self.cmdline_timeout = cmdline_timeout
        self.tmult = timeout_multiplier
        self.maxtime = max_timeout

    def load(self, tlist):
        """
        For each test, a 'runtimes' file will be read (if it exists) and the
        run time for this platform extracted.  This run time is saved as the
        test execute time.  Also, a timeout is calculated for each test and
        placed in the 'timeout' attribute.
        """
        pname = self.platobj.getName()
        cplr = self.platobj.getCompiler()

        cache = LookupCache( pname, cplr, self.platobj.testingDirectory() )

        for tcase in tlist.getTests():

            tspec = tcase.getSpec()

            tout = self.plugin.testTimeout( tcase )
            if tout == None:
                # grab explicit timeout value, if the test specifies it
                tout = tspec.getTimeout()

            # look for a previous runtime value
            tlen,tresult = cache.getRunTime( tspec )

            if tlen != None:

                rt = tcase.getStat().getRuntime( None )
                if rt == None:
                    tcase.getStat().setRuntime( int(tlen) )

                if tout == None:
                    if tresult == "timeout":
                        tout = self._timeout_if_test_timed_out( tlen )
                    else:
                        tout = self._timeout_from_previous_runtime( tlen )

            elif tout == None:
                tout = self._default_timeout( tspec )

            tout = self._apply_timeout_options( tout )

            tcase.getSpec().setAttr( 'timeout', tout )

        cache = None

    def _timeout_if_test_timed_out(self, runtime):
        ""
        # for tests that timed out, make timeout much larger
        if t.hasKeyword( "long" ):
            # only long tests get timeouts longer than an hour
            if runtime < 60*60:
                tm = 4*60*60
            elif runtime < 5*24*60*60:  # even longs are capped
                tm = 4*runtime
            else:
                tm = 5*24*60*60
        else:
            tm = 60*60

        return tm

    def _timeout_from_previous_runtime(self, runtime):
        ""
        # pick timeout to allow for some runtime variability
        if runtime < 120:
            tm = max( 120, 2*runtime )
        elif runtime < 300:
            tm = max( 300, 1.5*runtime )
        elif runtime < 4*60*60:
            tm = int( float(runtime)*1.5 )
        else:
            tm = int( float(runtime)*1.3 )

        return tm

    def _default_timeout(self, tspec):
        ""
        # with no information, the default depends on 'long' keyword
        if tspec.hasKeyword("long"):
            tm = 5*60*60  # five hours
        else:
            tm = 60*60  # one hour

        return tm

    def _apply_timeout_options(self, timeout):
        ""
        if self.cmdline_timeout != None:
            timeout = int( float(self.cmdline_timeout) )

        if self.tmult != None:
            timeout = int( float(timeout) * self.tmult )

        if self.maxtime != None:
            timeout = min( timeout, float(self.maxtime) )

        return timeout

