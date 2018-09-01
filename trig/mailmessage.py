#!/usr/bin/env python

import os
import traceback
import socket
import smtplib
from email.mime.text import MIMEText

try:
  from StringIO import StringIO
except Exception:
  from io import StringIO


DEFAULT_SMTP_HOSTS = ['localhost']


class Message:

    def __init__(self, recvaddrs=None, subject=None, sendaddr=None):
        ""
        self.sendaddr = None
        self.recvaddrs = []
        self.subject = ''
        self.content = ''
        self.subtype = 'plain'

        self.set( sendaddr=sendaddr, recvaddrs=recvaddrs, subject=subject )

    def set(self, recvaddrs=None, subject=None, sendaddr=None):
        ""
        if recvaddrs!= None: self.recvaddrs = _make_list( recvaddrs )
        if subject != None : self.subject   = subject
        if sendaddr != None: self.sendaddr  = sendaddr

    def setContent(self, content, subtype='plain'):
        ""
        self.content = content
        self.subtype = subtype

    def send(self, smtphosts=None, timeout=None, smtpclass=smtplib.SMTP ):
        """
        Note: Using "localhost" for 'smtphosts' can work, but if the receiver
              email is unknown, then the mail can appear to succeed but just
              get dropped.  Whereas when using "real" smtp hosts, an error will
              be generated.
        """
        if self.recvaddrs:

            msg = _make_message( self.content, self.subtype )

            msg['From']    = create_sender_address( self.sendaddr )
            msg['To']      = ', '.join( self.recvaddrs )
            msg['Subject'] = self.subject

            body = msg.as_string()
            self._send_mail_message( smtphosts, smtpclass, body, timeout )

    def _send_mail_message(self, smtphosts, smtpclass, msg_as_string, timeout):
        ""
        sender = create_sender_address( self.sendaddr )

        if not smtphosts:
            smtphosts = DEFAULT_SMTP_HOSTS

        err = ''

        for host in smtphosts:

            tbfile = StringIO()
            try:
                if timeout:
                    sm = smtpclass( host, timeout=timeout )
                else:
                    sm = smtpclass( host )

                #sm.set_debuglevel( 1 )
                sm.sendmail( sender, self.recvaddrs, msg_as_string )

                sm.close()

            except Exception:
                traceback.print_exc( 50, tbfile )
                err += tbfile.getvalue() + '\n'
                tbfile.close()

            else:
                err = ''
                break

        assert not err, 'Could not send to '+str(self.recvaddrs)+'\n:'+err


def _make_message( content, subtype ):
    ""
    if subtype == 'html':

        body = '<html>\n' + \
               '<body>\n' + \
               content + \
               '\n</body>\n' + \
               '</html>\n'

        msg = MIMEText( body, 'html' )

    else:
        msg = MIMEText( content, subtype )

    return msg


def _make_list( recvaddrs ):
    ""
    if type(recvaddrs) == type(''):
        return recvaddrs.strip().split()
    else:
        return list( recvaddrs )


def create_sender_address( addr=None ):
    ""
    if addr:
        return addr
    else:
        return get_current_user_name() + '@' + socket.getfqdn()


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

    if usr == None:
        usr = 'unknown'

    return usr


####################################################

if __name__ == '__main__':
    pass
