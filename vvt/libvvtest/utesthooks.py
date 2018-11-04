#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import signal
import time


def construct_unit_testing_hook( hooktype, job_qid=None ):
    """
    Examples of environ variable VVTEST_UNIT_TEST_SPEC:

        run:count=2,signum=SIGTERM
        batch:count=1
        run:count=2,signum=SIGTERM|batch:count=1
    """
    envspec = os.environ.get( 'VVTEST_UNIT_TEST_SPEC', '' )
    specL = envspec.strip().split('|')

    for spec in [ sp.strip() for sp in specL ]:

        if hooktype == 'run' and spec.startswith('run:'):
            return UnitTestingRunHook( spec[4:], job_qid )

        elif hooktype == 'batch' and spec.startswith('batch:'):
            return UnitTestingBatchHook( spec[6:] )

    return UnitTestingEmptyHook()


class UnitTestingRunHook:

    def __init__(self, spec, job_qid):
        """
        Examples:  count=2
                   count=2,signum=SIGINT
                   count=2,qid=5
        """
        self.count = 2**31
        self.signum = signal.SIGINT
        self.qid = None

        for n,v in [ s.split('=') for s in spec.split(',') ]:
            if n == 'count':
                self.count = int( v )
            elif n == 'signum':
                self.signum = eval( 'signal.'+v )
            elif n == 'qid':
                self.qid = int( v.strip() )

        self.job_qid = job_qid

    def check(self, numrun, numdone):
        ""
        qok = True
        if self.qid != None and self.job_qid != None:

            assert type( self.job_qid ) == type(3)

            # if the QID is defined and equal to this batch job's queue id
            # then the interrupt will take place; if it is defined but
            # not equal to this job's queue id then no interrupt will occur
            if self.qid != self.job_qid:
                qok = False

        if qok and numdone >= self.count:
            os.kill( os.getpid(), self.signum )
            time.sleep(60)
            sys.exit(1)


class UnitTestingBatchHook:

    def __init__(self, spec):
        """
        Examples:  count=2
                   count=2,signum=SIGINT"
        """
        self.count = 2**31
        self.signum = signal.SIGINT

        for n,v in [ s.split('=') for s in spec.split(',') ]:
            if n == 'count':
                self.count = int( v )
            elif n == 'signum':
                self.signum = eval( 'signal.'+v )

    def check(self, numrun, numdone):
        ""
        if numdone >= self.count:
            os.kill( os.getpid(), self.signum )
            time.sleep(60)
            sys.exit(1)


class UnitTestingEmptyHook:
    def check(self, *args):
        pass
