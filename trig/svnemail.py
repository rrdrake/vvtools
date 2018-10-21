#!/usr/bin/env python

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import time
import signal

from mailmessage import Message, get_current_user_name


SEND_MAIL_TIMEOUT = 30
DEFAULT_SMTPHOSTS = ['smtp.sandia.gov','localhost']
EMAIL_DOMAIN = 'sandia.gov'


class CommitEmailComposer:

    def __init__(self, cmt):
        ""
        self.cmt = cmt
        self.msg = None

    def compose(self, recipients=None, subject=None):
        ""
        self.msg = Message()

        addr = self.cmt.getAuthor()
        if '@' not in addr:
            addr += '@'+EMAIL_DOMAIN
        self.msg.set( sendaddr=addr )

        if subject:
            sbj = subject
        else:
            reponame = os.path.basename( self.cmt.getRepoURL() )
            sbj = '['+reponame+':'+self.cmt.getBranch()+'] ' + \
                  self.cmt.getShortMessage()
        self.msg.set( subject=sbj )

        if recipients:
            recv = recipients
        else:
            usr = get_current_user_name()
            recv = usr+'@'+EMAIL_DOMAIN
        self.msg.set( recvaddrs=recv )

        self.msg.setContent( self.cmt.asMultiLineString() )

    def send(self, smtp_hosts=None, debug=False):
        ""
        return send_message( self.msg, smtp_hosts, debug )


# use signals to implement a timeout mechanism
class TimeoutException(Exception): pass
def timeout_handler( signum, frame ):
    raise TimeoutException( "timeout" )


def send_message( msg, smtp_hosts, debug ):
    ""
    rtn = None

    if smtp_hosts:
        hosts = smtp_hosts
    else:
        hosts = DEFAULT_SMTPHOSTS

    prev = signal.signal( signal.SIGALRM, timeout_handler )

    timeout = int( SEND_MAIL_TIMEOUT * 0.9 )
    signal.alarm( SEND_MAIL_TIMEOUT )
    try:
        if debug:
            rtn = msg.send( smtphosts=hosts, timeout=timeout, smtpclass=None )
        else:
            msg.send( smtphosts=hosts, timeout=timeout )
    finally:
        signal.alarm(0)
        signal.signal( signal.SIGALRM, prev )

    return rtn
