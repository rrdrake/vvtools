#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys, os
import string
import struct
import types
import array
import re
import time

# this is needed in order to check the buffer types and in order to know
# how much data is to be sent/recved with the pipe interface
# it maps exoid to "computer word size", either 'f' or 'd'
_comp_ws_ = {}

class PipeDispatch:
    
    vgcmd = [ 'valgrind', '--leak-check=full', '--show-reachable=yes' ]
    
    def __init__(self, prog, argL, valgrind=0 ):
        
        if struct.calcsize('c') != 1 or struct.calcsize('i') != 4 or \
           struct.calcsize('f') != 4 or struct.calcsize('d') != 8:
          raise Exception("unexpected C language data type size")
        
        self.cpid = -1
        
        sendr, sendw = os.pipe()
        recvr, recvw = os.pipe()
        
        cmd = []
        if valgrind:
          cmd.extend( PipeDispatch.vgcmd )
        
        if not os.path.isabs(prog):
          # look in PATH, current working directory, and the path to this file
          L = string.split( os.environ.get('PATH','/usr/bin'), ':' )
          L.append( '.' )
          if _mydir_: L.append( _mydir_ )
          for d in L:
            dp = os.path.join( os.path.abspath(d), prog )
            if os.path.exists(dp) and os.access(dp,os.X_OK):
              prog = dp
              break
        
        cmd.extend( [ prog, '-d', os.getcwd(),
                            '-i', str(sendr),
                            '-o', str(recvw) ] )
        cmd.extend( argL )
        #print "PipeDispatch: executing", string.join(cmd)
        
        self.cpid = os.fork()
        if self.cpid == 0:
          # child
          os.close(sendw)
          os.close(recvr)
          os.execvp( cmd[0], cmd )
          sys.exit(1)
        
        # parent
        os.close(sendr)
        os.close(recvw)
        
        # turn the pipe file descriptors into file objects, which allows
        # buffering when writing and the use of array.fromfile on read
        self.sendfp = os.fdopen( sendw, "w" )
        self.recvfp = os.fdopen( recvr, "r" )
        
        import atexit
        atexit.register( self.close )
    
    def kill(self):
        '''
        Forcibly kills the child process and closes the connection.
        '''
        if self.cpid >= 0:
          try:
            import signal
          except:
            os.kill( self.cpid, 9 )
          else:
            os.kill( self.cpid, signal.SIGKILL )
          self.close()
    
    def close(self):
        """
        Sends a "stop" code to the child process then closes the 
        pipe and waits for the child to exit.
        """
        buf = struct.pack( 'i', 0 )
        buf = buf + '                                            '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        time.sleep(1)
        self.sendfp.close()
        self.recvfp.close()
        # TODO: add a timeout here and call kill() instead
        p,x = os.waitpid( self.cpid, 0 )
        self.cpid = -1
        return x
    
    def exm_create(self, arg0, arg1, arg2, arg3, arg4):
        funcid = 1
        funcname = 'exm_create'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', len(arg0) )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        buf = buf + struct.pack( 'i', arg3 )
        arg4_len = len(arg4)
        buf = buf + struct.pack( 'i', arg4_len*4)
        buf = buf + '                        '  # padding
        self.sendfp.write( buf )
        self.sendfp.write( arg0 )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg4_len > 0:
            del arg4[0:]
            arg4.fromfile( self.recvfp, arg4_len )
    
    def exm_open(self, arg0, arg1, arg2, arg3, arg4, arg5):
        funcid = 2
        funcname = 'exm_open'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', len(arg0) )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        arg3_len = len(arg3)
        buf = buf + struct.pack( 'i', arg3_len*4)
        arg4_len = len(arg4)
        buf = buf + struct.pack( 'i', arg4_len*4)
        arg5_len = len(arg5)
        buf = buf + struct.pack( 'i', arg5_len*4)
        buf = buf + '                    '  # padding
        self.sendfp.write( buf )
        self.sendfp.write( arg0 )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg3_len > 0:
            del arg3[0:]
            arg3.fromfile( self.recvfp, arg3_len )
          if arg4_len > 0:
            del arg4[0:]
            arg4.fromfile( self.recvfp, arg4_len )
          if arg5_len > 0:
            del arg5[0:]
            arg5.fromfile( self.recvfp, arg5_len )
    
    def exm_close(self, arg0):
        funcid = 3
        funcname = 'exm_close'
        if self.cpid < 0: return
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + '                                        '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
    
    def exm_get_init(self, arg0, arg1, arg2):
        funcid = 4
        funcname = 'exm_get_init'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        arg1_len = len(arg1)
        buf = buf + struct.pack( 'i', arg1_len*1)
        arg2_len = len(arg2)
        buf = buf + struct.pack( 'i', arg2_len*4)
        buf = buf + '                                '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg1_len > 0:
            del arg1[0:]
            arg1.fromfile( self.recvfp, arg1_len )
          if arg2_len > 0:
            del arg2[0:]
            arg2.fromfile( self.recvfp, arg2_len )
    
    def exm_inquire_counts(self, arg0, arg1):
        funcid = 5
        funcname = 'exm_inquire_counts'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        arg1_len = len(arg1)
        buf = buf + struct.pack( 'i', arg1_len*4)
        buf = buf + '                                    '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg1_len > 0:
            del arg1[0:]
            arg1.fromfile( self.recvfp, arg1_len )
    
    def exm_get_info(self, arg0, arg1, arg2):
        funcid = 6
        funcname = 'exm_get_info'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        arg2_len = len(arg2)
        buf = buf + struct.pack( 'i', arg2_len*1)
        buf = buf + '                                '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg2_len > 0:
            del arg2[0:]
            arg2.fromfile( self.recvfp, arg2_len )
    
    def exm_get_ids(self, arg0, arg1, arg2):
        funcid = 7
        funcname = 'exm_get_ids'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        arg2_len = len(arg2)
        buf = buf + struct.pack( 'i', arg2_len*4)
        buf = buf + '                                '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg2_len > 0:
            del arg2[0:]
            arg2.fromfile( self.recvfp, arg2_len )
    
    def exm_get_block(self, arg0, arg1, arg2, arg3, arg4):
        funcid = 8
        funcname = 'exm_get_block'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        arg3_len = len(arg3)
        buf = buf + struct.pack( 'i', arg3_len*1)
        arg4_len = len(arg4)
        buf = buf + struct.pack( 'i', arg4_len*4)
        buf = buf + '                        '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg3_len > 0:
            del arg3[0:]
            arg3.fromfile( self.recvfp, arg3_len )
          if arg4_len > 0:
            del arg4[0:]
            arg4.fromfile( self.recvfp, arg4_len )
    
    def exm_get_set_param(self, arg0, arg1, arg2, arg3, arg4):
        funcid = 9
        funcname = 'exm_get_set_param'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        arg3_len = len(arg3)
        buf = buf + struct.pack( 'i', arg3_len*4)
        arg4_len = len(arg4)
        buf = buf + struct.pack( 'i', arg4_len*4)
        buf = buf + '                        '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg3_len > 0:
            del arg3[0:]
            arg3.fromfile( self.recvfp, arg3_len )
          if arg4_len > 0:
            del arg4[0:]
            arg4.fromfile( self.recvfp, arg4_len )
    
    def exm_get_qa(self, arg0, arg1, arg2):
        funcid = 10
        funcname = 'exm_get_qa'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        arg2_len = len(arg2)
        buf = buf + struct.pack( 'i', arg2_len*1)
        buf = buf + '                                '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg2_len > 0:
            del arg2[0:]
            arg2.fromfile( self.recvfp, arg2_len )
    
    def exm_get_all_times(self, arg0, arg1):
        funcid = 11
        funcname = 'exm_get_all_times'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        arg1_len = len(arg1)
        buf = buf + struct.pack( 'i', arg1_len*_comp_ws_[arg0])
        buf = buf + '                                    '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg1_len > 0:
            del arg1[0:]
            arg1.fromfile( self.recvfp, arg1_len )
    
    def exm_get_var_params(self, arg0, arg1):
        funcid = 12
        funcname = 'exm_get_var_params'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        arg1_len = len(arg1)
        buf = buf + struct.pack( 'i', arg1_len*4)
        buf = buf + '                                    '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg1_len > 0:
            del arg1[0:]
            arg1.fromfile( self.recvfp, arg1_len )
    
    def exm_get_all_var_names(self, arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10):
        funcid = 13
        funcname = 'exm_get_all_var_names'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        arg1_len = len(arg1)
        buf = buf + struct.pack( 'i', arg1_len*1)
        arg2_len = len(arg2)
        buf = buf + struct.pack( 'i', arg2_len*1)
        arg3_len = len(arg3)
        buf = buf + struct.pack( 'i', arg3_len*1)
        arg4_len = len(arg4)
        buf = buf + struct.pack( 'i', arg4_len*1)
        arg5_len = len(arg5)
        buf = buf + struct.pack( 'i', arg5_len*1)
        arg6_len = len(arg6)
        buf = buf + struct.pack( 'i', arg6_len*1)
        arg7_len = len(arg7)
        buf = buf + struct.pack( 'i', arg7_len*1)
        arg8_len = len(arg8)
        buf = buf + struct.pack( 'i', arg8_len*1)
        arg9_len = len(arg9)
        buf = buf + struct.pack( 'i', arg9_len*1)
        arg10_len = len(arg10)
        buf = buf + struct.pack( 'i', arg10_len*1)
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg1_len > 0:
            del arg1[0:]
            arg1.fromfile( self.recvfp, arg1_len )
          if arg2_len > 0:
            del arg2[0:]
            arg2.fromfile( self.recvfp, arg2_len )
          if arg3_len > 0:
            del arg3[0:]
            arg3.fromfile( self.recvfp, arg3_len )
          if arg4_len > 0:
            del arg4[0:]
            arg4.fromfile( self.recvfp, arg4_len )
          if arg5_len > 0:
            del arg5[0:]
            arg5.fromfile( self.recvfp, arg5_len )
          if arg6_len > 0:
            del arg6[0:]
            arg6.fromfile( self.recvfp, arg6_len )
          if arg7_len > 0:
            del arg7[0:]
            arg7.fromfile( self.recvfp, arg7_len )
          if arg8_len > 0:
            del arg8[0:]
            arg8.fromfile( self.recvfp, arg8_len )
          if arg9_len > 0:
            del arg9[0:]
            arg9.fromfile( self.recvfp, arg9_len )
          if arg10_len > 0:
            del arg10[0:]
            arg10.fromfile( self.recvfp, arg10_len )
    
    def exm_get_truth_table(self, arg0, arg1, arg2, arg3, arg4):
        funcid = 14
        funcname = 'exm_get_truth_table'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        buf = buf + struct.pack( 'i', arg3 )
        arg4_len = len(arg4)
        buf = buf + struct.pack( 'i', arg4_len*4)
        buf = buf + '                        '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg4_len > 0:
            del arg4[0:]
            arg4.fromfile( self.recvfp, arg4_len )
    
    def exm_get_coord_names(self, arg0, arg1, arg2):
        funcid = 15
        funcname = 'exm_get_coord_names'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        arg2_len = len(arg2)
        buf = buf + struct.pack( 'i', arg2_len*1)
        buf = buf + '                                '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg2_len > 0:
            del arg2[0:]
            arg2.fromfile( self.recvfp, arg2_len )
    
    def exm_get_coord(self, arg0, arg1, arg2, arg3):
        funcid = 16
        funcname = 'exm_get_coord'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        arg1_len = len(arg1)
        buf = buf + struct.pack( 'i', arg1_len*_comp_ws_[arg0])
        arg2_len = len(arg2)
        buf = buf + struct.pack( 'i', arg2_len*_comp_ws_[arg0])
        arg3_len = len(arg3)
        buf = buf + struct.pack( 'i', arg3_len*_comp_ws_[arg0])
        buf = buf + '                            '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg1_len > 0:
            del arg1[0:]
            arg1.fromfile( self.recvfp, arg1_len )
          if arg2_len > 0:
            del arg2[0:]
            arg2.fromfile( self.recvfp, arg2_len )
          if arg3_len > 0:
            del arg3[0:]
            arg3.fromfile( self.recvfp, arg3_len )
    
    def exm_get_conn(self, arg0, arg1, arg2, arg3, arg4):
        funcid = 17
        funcname = 'exm_get_conn'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        buf = buf + struct.pack( 'i', arg3 )
        arg4_len = len(arg4)
        buf = buf + struct.pack( 'i', arg4_len*4)
        buf = buf + '                        '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg4_len > 0:
            del arg4[0:]
            arg4.fromfile( self.recvfp, arg4_len )
    
    def exm_get_set(self, arg0, arg1, arg2, arg3, arg4):
        funcid = 18
        funcname = 'exm_get_set'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        arg3_len = len(arg3)
        buf = buf + struct.pack( 'i', arg3_len*4)
        arg4_len = len(arg4)
        buf = buf + struct.pack( 'i', arg4_len*4)
        buf = buf + '                        '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg3_len > 0:
            del arg3[0:]
            arg3.fromfile( self.recvfp, arg3_len )
          if arg4_len > 0:
            del arg4[0:]
            arg4.fromfile( self.recvfp, arg4_len )
    
    def exm_get_set_dist_fact(self, arg0, arg1, arg2, arg3):
        funcid = 19
        funcname = 'exm_get_set_dist_fact'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        arg3_len = len(arg3)
        buf = buf + struct.pack( 'i', arg3_len*_comp_ws_[arg0])
        buf = buf + '                            '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg3_len > 0:
            del arg3[0:]
            arg3.fromfile( self.recvfp, arg3_len )
    
    def exm_get_map(self, arg0, arg1, arg2, arg3):
        funcid = 20
        funcname = 'exm_get_map'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        arg3_len = len(arg3)
        buf = buf + struct.pack( 'i', arg3_len*4)
        buf = buf + '                            '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg3_len > 0:
            del arg3[0:]
            arg3.fromfile( self.recvfp, arg3_len )
    
    def exm_get_glob_vars(self, arg0, arg1, arg2, arg3):
        funcid = 21
        funcname = 'exm_get_glob_vars'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        arg3_len = len(arg3)
        buf = buf + struct.pack( 'i', arg3_len*_comp_ws_[arg0])
        buf = buf + '                            '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg3_len > 0:
            del arg3[0:]
            arg3.fromfile( self.recvfp, arg3_len )
    
    def exm_get_nodal_var(self, arg0, arg1, arg2, arg3, arg4):
        funcid = 22
        funcname = 'exm_get_nodal_var'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        buf = buf + struct.pack( 'i', arg3 )
        arg4_len = len(arg4)
        buf = buf + struct.pack( 'i', arg4_len*_comp_ws_[arg0])
        buf = buf + '                        '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg4_len > 0:
            del arg4[0:]
            arg4.fromfile( self.recvfp, arg4_len )
    
    def exm_get_var(self, arg0, arg1, arg2, arg3, arg4, arg5, arg6):
        funcid = 23
        funcname = 'exm_get_var'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        buf = buf + struct.pack( 'i', arg3 )
        buf = buf + struct.pack( 'i', arg4 )
        buf = buf + struct.pack( 'i', arg5 )
        arg6_len = len(arg6)
        buf = buf + struct.pack( 'i', arg6_len*_comp_ws_[arg0])
        buf = buf + '                '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg6_len > 0:
            del arg6[0:]
            arg6.fromfile( self.recvfp, arg6_len )
    
    def exm_get_block_var(self, arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9):
        funcid = 24
        funcname = 'exm_get_block_var'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        buf = buf + struct.pack( 'i', arg3 )
        buf = buf + struct.pack( 'i', arg4 )
        buf = buf + struct.pack( 'i', len(arg5)*4)
        buf = buf + struct.pack( 'i', len(arg6)*4)
        buf = buf + struct.pack( 'i', len(arg7)*4)
        buf = buf + arg8[0]
        arg9_len = len(arg9)
        buf = buf + struct.pack( 'i', arg9_len*_comp_ws_[arg0])
        buf = buf + '       '  # padding
        self.sendfp.write( buf )
        arg5.tofile( self.sendfp )
        arg6.tofile( self.sendfp )
        arg7.tofile( self.sendfp )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg9_len > 0:
            del arg9[0:]
            arg9.fromfile( self.recvfp, arg9_len )
    
    def exm_get_var_time(self, arg0, arg1, arg2, arg3, arg4, arg5, arg6):
        funcid = 25
        funcname = 'exm_get_var_time'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        buf = buf + struct.pack( 'i', arg3 )
        buf = buf + struct.pack( 'i', arg4 )
        buf = buf + struct.pack( 'i', arg5 )
        arg6_len = len(arg6)
        buf = buf + struct.pack( 'i', arg6_len*_comp_ws_[arg0])
        buf = buf + '                '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
        else:
          if arg6_len > 0:
            del arg6[0:]
            arg6.fromfile( self.recvfp, arg6_len )
    
    def exm_put_init(self, arg0, arg1, arg2):
        funcid = 26
        funcname = 'exm_put_init'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', len(arg1) )
        buf = buf + struct.pack( 'i', len(arg2)*4)
        buf = buf + '                                '  # padding
        self.sendfp.write( buf )
        self.sendfp.write( arg1 )
        arg2.tofile( self.sendfp )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
    
    def exm_put_qa(self, arg0, arg1, arg2):
        funcid = 27
        funcname = 'exm_put_qa'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        arg2_len = len(arg2)
        buf = buf + struct.pack( 'i', arg2_len*1)
        buf = buf + '                                '  # padding
        self.sendfp.write( buf )
        arg2.tofile( self.sendfp )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
    
    def exm_put_info(self, arg0, arg1, arg2):
        funcid = 28
        funcname = 'exm_put_info'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        arg2_len = len(arg2)
        buf = buf + struct.pack( 'i', arg2_len*1)
        buf = buf + '                                '  # padding
        self.sendfp.write( buf )
        arg2.tofile( self.sendfp )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
    
    def exm_put_coord_names(self, arg0, arg1, arg2, arg3, arg4):
        funcid = 29
        funcname = 'exm_put_coord_names'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', len(arg2) )
        buf = buf + struct.pack( 'i', len(arg3) )
        buf = buf + struct.pack( 'i', len(arg4) )
        buf = buf + '                        '  # padding
        self.sendfp.write( buf )
        self.sendfp.write( arg2 )
        self.sendfp.write( arg3 )
        self.sendfp.write( arg4 )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
    
    def exm_put_coord(self, arg0, arg1, arg2, arg3):
        funcid = 30
        funcname = 'exm_put_coord'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', len(arg1)*_comp_ws_[arg0])
        buf = buf + struct.pack( 'i', len(arg2)*_comp_ws_[arg0])
        buf = buf + struct.pack( 'i', len(arg3)*_comp_ws_[arg0])
        buf = buf + '                            '  # padding
        self.sendfp.write( buf )
        arg1.tofile( self.sendfp )
        arg2.tofile( self.sendfp )
        arg3.tofile( self.sendfp )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
    
    def exm_put_block(self, arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8):
        funcid = 31
        funcname = 'exm_put_block'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        buf = buf + struct.pack( 'i', len(arg3) )
        buf = buf + struct.pack( 'i', arg4 )
        buf = buf + struct.pack( 'i', arg5 )
        buf = buf + struct.pack( 'i', arg6 )
        buf = buf + struct.pack( 'i', arg7 )
        buf = buf + struct.pack( 'i', arg8 )
        buf = buf + '        '  # padding
        self.sendfp.write( buf )
        self.sendfp.write( arg3 )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
    
    def exm_put_conn(self, arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8):
        funcid = 32
        funcname = 'exm_put_conn'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        buf = buf + struct.pack( 'i', arg3 )
        buf = buf + struct.pack( 'i', arg4 )
        buf = buf + struct.pack( 'i', arg5 )
        buf = buf + struct.pack( 'i', len(arg6)*4)
        buf = buf + struct.pack( 'i', len(arg7)*4)
        buf = buf + struct.pack( 'i', len(arg8)*4)
        buf = buf + '        '  # padding
        self.sendfp.write( buf )
        arg6.tofile( self.sendfp )
        arg7.tofile( self.sendfp )
        arg8.tofile( self.sendfp )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
    
    def exm_put_set_param(self, arg0, arg1, arg2, arg3, arg4):
        funcid = 33
        funcname = 'exm_put_set_param'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        buf = buf + struct.pack( 'i', arg3 )
        buf = buf + struct.pack( 'i', arg4 )
        buf = buf + '                        '  # padding
        self.sendfp.write( buf )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
    
    def exm_put_set(self, arg0, arg1, arg2, arg3, arg4):
        funcid = 34
        funcname = 'exm_put_set'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        buf = buf + struct.pack( 'i', len(arg3)*4)
        buf = buf + struct.pack( 'i', len(arg4)*4)
        buf = buf + '                        '  # padding
        self.sendfp.write( buf )
        arg3.tofile( self.sendfp )
        arg4.tofile( self.sendfp )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
    
    def exm_put_set_dist_fact(self, arg0, arg1, arg2, arg3):
        funcid = 35
        funcname = 'exm_put_set_dist_fact'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        buf = buf + struct.pack( 'i', len(arg3)*_comp_ws_[arg0])
        buf = buf + '                            '  # padding
        self.sendfp.write( buf )
        arg3.tofile( self.sendfp )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
    
    def exm_put_map(self, arg0, arg1, arg2, arg3):
        funcid = 36
        funcname = 'exm_put_map'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        buf = buf + struct.pack( 'i', len(arg3)*4)
        buf = buf + '                            '  # padding
        self.sendfp.write( buf )
        arg3.tofile( self.sendfp )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
    
    def exm_put_vars(self, arg0, arg1, arg2, arg3):
        funcid = 37
        funcname = 'exm_put_vars'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        arg3_len = len(arg3)
        buf = buf + struct.pack( 'i', arg3_len*1)
        buf = buf + '                            '  # padding
        self.sendfp.write( buf )
        arg3.tofile( self.sendfp )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
    
    def exm_put_truth_table(self, arg0, arg1, arg2, arg3, arg4):
        funcid = 38
        funcname = 'exm_put_truth_table'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        buf = buf + struct.pack( 'i', arg3 )
        buf = buf + struct.pack( 'i', len(arg4)*4)
        buf = buf + '                        '  # padding
        self.sendfp.write( buf )
        arg4.tofile( self.sendfp )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
    
    def exm_put_time(self, arg0, arg1, arg2):
        funcid = 39
        funcname = 'exm_put_time'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', len(arg2)*_comp_ws_[arg0])
        buf = buf + '                                '  # padding
        self.sendfp.write( buf )
        arg2.tofile( self.sendfp )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
    
    def exm_put_glob_vars(self, arg0, arg1, arg2, arg3):
        funcid = 40
        funcname = 'exm_put_glob_vars'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        buf = buf + struct.pack( 'i', len(arg3)*_comp_ws_[arg0])
        buf = buf + '                            '  # padding
        self.sendfp.write( buf )
        arg3.tofile( self.sendfp )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
    
    def exm_put_nodal_var(self, arg0, arg1, arg2, arg3, arg4):
        funcid = 41
        funcname = 'exm_put_nodal_var'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        buf = buf + struct.pack( 'i', arg3 )
        buf = buf + struct.pack( 'i', len(arg4)*_comp_ws_[arg0])
        buf = buf + '                        '  # padding
        self.sendfp.write( buf )
        arg4.tofile( self.sendfp )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)
    
    def exm_put_var(self, arg0, arg1, arg2, arg3, arg4, arg5, arg6):
        funcid = 42
        funcname = 'exm_put_var'
        buf = struct.pack( 'i', funcid )
        buf = buf + struct.pack( 'i', arg0 )
        buf = buf + struct.pack( 'i', arg1 )
        buf = buf + struct.pack( 'i', arg2 )
        buf = buf + struct.pack( 'i', arg3 )
        buf = buf + struct.pack( 'i', arg4 )
        buf = buf + struct.pack( 'i', arg5 )
        buf = buf + struct.pack( 'i', len(arg6)*_comp_ws_[arg0])
        buf = buf + '                '  # padding
        self.sendfp.write( buf )
        arg6.tofile( self.sendfp )
        self.sendfp.flush()
        err = struct.unpack( 'i', self.recvfp.read(4) )[0]
        if err > 0:
          errstr = self.recvfp.read( err )
          raise Exception(errstr)

_mydir_ = None
if '__file__' in dir():
  f = __file__
  if os.path.isabs(f):
    _mydir_ = os.path.dirname(f)
  else:
    for d in sys.path:
      if not d: d = '.'
      df = os.path.join( os.path.abspath(d), f )
      if os.path.exists(df):
        _mydir_ = os.path.dirname(df)

if os.environ.has_key( "EXOMOD_USE_PIPE" ):
  exomod_lib = PipeDispatch( "exomod_pipe", [], 0 )
else:
  try:
    import exomod_lib
  except ImportError:
    if os.environ.has_key( "EXOMOD_NO_PIPE" ):
      raise
    exomod_lib = PipeDispatch( "exomod_pipe", [], 0 )
    
def exm_create(arg0, arg1, arg2, arg3, arg4):
    """
  exm_create(string filename, int create_mode,
             int convert_word_size, int file_word_size, int* exoid )
    
    filename: the string file name to create
    create_mode: bit packed from EX_NOCLOBBER=0, EX_CLOBBER=1,
                 EX_NORMAL_MODEL=2, EX_LARGE_MODEL=4, EX_NETCDF4=8,
                 EX_NOSHARE=16, EX_SHARE=32 
    convert_word_size: either 4 or 8; all floating point arrays passed
                       through this interface are expected to have this
                       storage size; so if the 'file_word_size' value is 
                       different, then the data will be converted
    file_word_size: size of floating point data stored in the file (4 or 8)
    exoid (OUT): the integer file descriptor of the new file
    """
    assert type(arg0) == types.StringType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == types.IntType
    assert type(arg4) == array.ArrayType and arg4.typecode == 'i'
    exomod_lib.exm_create(arg0, arg1, arg2, arg3, arg4)
    _comp_ws_[arg4[0]] = arg2
    
def exm_open(arg0, arg1, arg2, arg3, arg4, arg5):
    """
  exm_open(string filename, int open_mode, int convert_word_size,
           int* file_word_size, float* version, int* exoid)
     
     filename: the string file name of an existing exodus file
     open_mode: either EX_READ=0 or EX_WRITE=1
     convert_word_size: if non-zero, then all floating point arrays passed
                        through this interface are expected to have this
                        storage size (either 4 or 8 bytes);  so if the file
                        has a different size, then the data will be converted
     file_word_size (OUT): 4 if the file stores single precision, 8 if double
     version (OUT): the Exodus version (a float)
     exoid (OUT): the integer file descriptor of the opened file
    """
    assert type(arg0) == types.StringType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == array.ArrayType and arg3.typecode == 'i'
    assert type(arg4) == array.ArrayType and arg4.typecode == 'f'
    assert type(arg5) == array.ArrayType and arg5.typecode == 'i'
    exomod_lib.exm_open(arg0, arg1, arg2, arg3, arg4, arg5)
    if arg2 == 0:
      _comp_ws_[arg5[0]] = arg3[0]
    else:
      _comp_ws_[arg5[0]] = arg2
    
def exm_close(arg0):
    """
  exm_close(int exoid)
  
     exoid: an integer file descriptor of an open exodus file
    """
    assert type(arg0) == types.IntType
    exomod_lib.exm_close(arg0)
    
def exm_get_init(arg0, arg1, arg2):
    """
  exm_get_init(int exoid, char* title, int* counts)
  
     'exoid' is an integer file descriptor of an open exodus file
     'title' a char buffer of length MAX_LINE_LENGTH+1 to hold the title
     'counts' an integer buffer of length 17 to hold each count:
         [ 0] = num_dim
         [ 1] = num_nodes
         [ 2] = num_edges
         [ 3] = num_edge_blk
         [ 4] = num_faces
         [ 5] = num_face_blk
         [ 6] = num_elems
         [ 7] = num_elem_blk
         [ 8] = num_node_sets
         [ 9] = num_edge_sets
         [10] = num_face_sets
         [11] = num_side_sets
         [12] = num_elem_sets
         [13] = num_node_maps
         [14] = num_edge_maps
         [15] = num_face_maps
         [16] = num_elem_maps
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == array.ArrayType and arg1.typecode == 'c'
    assert type(arg2) == array.ArrayType and arg2.typecode == 'i'
    exomod_lib.exm_get_init(arg0, arg1, arg2)
    
def exm_inquire_counts(arg0, arg1):
    """
  exm_inquire_counts(int exoid, int* counts_array)
  
     exoid: an open exodus file descriptor
     counts_array: an integer buffer of length 41 filled with the following
       [ 0] = number of dimensions
       [ 1] = number of nodes
       [ 2] = number of elements
       [ 3] = number of element blocks
       [ 4] = number of node sets
       [ 5] = length of node set node list
       [ 6] = number of side sets
       [ 7] = length of side set node list
       [ 8] = length of side set element list
       [ 9] = number of QA records
       [10] = number of info records
       [11] = number of time steps in the database
       [12] = number of element block properties
       [13] = number of node set properties
       [14] = number of side set properties
       [15] = length of node set distribution factor list
       [16] = length of side set distribution factor list
       [17] = number of element map properties
       [18] = number of node map properties
       [19] = number of element maps
       [20] = number of node maps
       [21] = number of edges
       [22] = number of edge blocks
       [23] = number of edge sets
       [24] = length of concat edge set edge list
       [25] = length of concat edge set dist factor list
       [26] = number of properties stored per edge block
       [27] = number of properties stored per edge set
       [28] = number of faces
       [29] = number of face blocks
       [30] = number of face sets
       [31] = length of concat face set face list
       [32] = length of concat face set dist factor list
       [33] = number of properties stored per face block
       [34] = number of properties stored per face set
       [35] = number of element sets
       [36] = length of concat element set element list
       [37] = length of concat element set dist factor list
       [38] = number of properties stored per elem set
       [39] = number of edge maps
       [40] = number of face maps
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == array.ArrayType and arg1.typecode == 'i'
    exomod_lib.exm_inquire_counts(arg0, arg1)
    
def exm_get_info(arg0, arg1, arg2):
    """
  exm_get_info(int exoid, int num_info, char* info)
  
     exoid: an open exodus file descriptor
     num_info: the number of info records in the file
     info: a char buffer of size num_info*(MAX_LINE_LENGTH+1) where each
           line is sequential and uses MAX_LINE_LENGTH+1 characters and
           is padded with null characters
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == array.ArrayType and arg2.typecode == 'c'
    exomod_lib.exm_get_info(arg0, arg1, arg2)
    
def exm_get_ids(arg0, arg1, arg2):
    """
  exm_get_ids(int exoid, int idtype, int* ids)
  
     exoid: an open exodus file descriptor
     idtype: one of EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_ELEM_BLOCK, EX_NODE_SET
             EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET, EX_NODE_MAP
             EX_EDGE_MAP, EX_FACE_MAP, or EX_ELEM_MAP
     ids: an integer buffer with length large enough to store the ids
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == array.ArrayType and arg2.typecode == 'i'
    exomod_lib.exm_get_ids(arg0, arg1, arg2)
    
def exm_get_block(arg0, arg1, arg2, arg3, arg4):
    """
  exm_get_block(int exoid, int block_type, int block_id,
                char* type_name, int* counts)
  
     exoid: an open exodus file descriptor
     block_type: one of EX_EDGE_BLOCK, EX_FACE_BLOCK, or EX_ELEM_BLOCK
     block_id: integer block id
     type_name: a char buffer to store the type of objects in the block, such
                as 'HEX'; must have length MAX_STR_LENGTH+1
     counts: an integer buffer of length 5
               [0] = num objects in the block
               [1] = num nodes per object
               [2] = num edges per object
               [3] = num faces per object
               [4] = num attributes per object
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == array.ArrayType and arg3.typecode == 'c'
    assert type(arg4) == array.ArrayType and arg4.typecode == 'i'
    exomod_lib.exm_get_block(arg0, arg1, arg2, arg3, arg4)
    
def exm_get_set_param(arg0, arg1, arg2, arg3, arg4):
    """
  exm_get_set_param(int exoid, int set_type, int set_id,
                    int* num_objs, int* num_dist_factors)
  
     exoid: an open exodus file descriptor
     set_type: one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET,
               EX_SIDE_SET
     set_id: integer set id
     num_objs (OUT): number of objects in the set
     num_dist_factors (OUT): number of distribution factors
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == array.ArrayType and arg3.typecode == 'i'
    assert type(arg4) == array.ArrayType and arg4.typecode == 'i'
    exomod_lib.exm_get_set_param(arg0, arg1, arg2, arg3, arg4)
    
def exm_get_qa(arg0, arg1, arg2):
    """
  exm_get_qa(int exoid, int num_qa, char* qa_records)
  
     exoid: an open exodus file descriptor
     num_qa: the number of QA records stored in the file
     qa_records: a char buffer with length 4*num_qa*(MAX_STR_LENGTH+1);
                 so that each record has 4 sequential entries each of length
                 MAX_STR_LENGTH+1 and the records are stored sequentially
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == array.ArrayType and arg2.typecode == 'c'
    exomod_lib.exm_get_qa(arg0, arg1, arg2)
    
def exm_get_all_times(arg0, arg1):
    """
  exm_get_all_times(int exoid, REAL* times)
  
     exoid: an open exodus file descriptor
     times: a floating point buffer of length equal to the number of time
            values; if the file stores doubles, then the buffer must store
            doubles, otherwise floats
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == array.ArrayType
    if _comp_ws_[arg0] == 4:
      assert arg1.typecode == 'f'
    else:
      assert arg1.typecode == 'd'
    exomod_lib.exm_get_all_times(arg0, arg1)
    
def exm_get_var_params(arg0, arg1):
    """
  exm_get_var_params(int exoid, int* counts)
  
     exoid: an open exodus file descriptor
     counts: an integer buffer of length 10 to store the number of variables
             of each type:
               [0] = num global vars,
               [1] = num node vars,
               [2] = num edge vars,
               [3] = num face vars,
               [4] = num element vars,
               [5] = num nodeset vars,
               [6] = num edgeset vars,
               [7] = num faceset vars,
               [8] = num element set vars,
               [9] = num sideset vars
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == array.ArrayType and arg1.typecode == 'i'
    exomod_lib.exm_get_var_params(arg0, arg1)
    
def exm_get_all_var_names(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10):
    """
  exm_get_all_var_names(int exoid,  char* global,  char* node, char* edge,
                        char* face, char* element, char* nodeset,
                        char* edgeset, char* faceset, char* elemset,
                        char* sideset )
  
     exoid: an open exodus file descriptor
     the rest are char buffers to hold the variable names for each var type;
     each must have length MAX_STR_LENGTH+1 times the number of variables
     of that type; they get filled with the names and padded on the right
     with NUL chars
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == array.ArrayType and arg1.typecode == 'c'
    assert type(arg2) == array.ArrayType and arg2.typecode == 'c'
    assert type(arg3) == array.ArrayType and arg3.typecode == 'c'
    assert type(arg4) == array.ArrayType and arg4.typecode == 'c'
    assert type(arg5) == array.ArrayType and arg5.typecode == 'c'
    assert type(arg6) == array.ArrayType and arg6.typecode == 'c'
    assert type(arg7) == array.ArrayType and arg7.typecode == 'c'
    assert type(arg8) == array.ArrayType and arg8.typecode == 'c'
    assert type(arg9) == array.ArrayType and arg9.typecode == 'c'
    assert type(arg10) == array.ArrayType and arg10.typecode == 'c'
    exomod_lib.exm_get_all_var_names(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9, arg10)
    
def exm_get_truth_table(arg0, arg1, arg2, arg3, arg4):
    """
  exm_get_truth_table(int exoid, int var_type, int num_blocks,
                      int num_vars, int* table )
  
     exoid: an open exodus file descriptor
     var_type: one of EX_ELEM_BLOCK, EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_NODE_SET,
               EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET
     num_blocks: the number of blocks or sets stored for the var_type
     num_vars: the number of variables stored for the var_type
     table: an integer buffer of length num_blocks*num_vars to recieve the
            truth table values
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == types.IntType
    assert type(arg4) == array.ArrayType and arg4.typecode == 'i'
    exomod_lib.exm_get_truth_table(arg0, arg1, arg2, arg3, arg4)
    
def exm_get_coord_names(arg0, arg1, arg2):
    """
  exm_get_coord_names(int exoid, int ndim, char* names)
  
     exoid: an open exodus file descriptor
     ndim: the spatial dimension stored in the file
     names: char buffer to store the coordinate names;  must have length
            ndim*(MAX_STR_LENGTH+1); the name for the X coordinate is stored
            in the first MAX_STR_LENGTH+1 characters, then Y then Z.
            If the names are not stored in the file, then the string
            "_not_stored_" will be placed in the names buffer
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == array.ArrayType and arg2.typecode == 'c'
    exomod_lib.exm_get_coord_names(arg0, arg1, arg2)
    
def exm_get_coord(arg0, arg1, arg2, arg3):
    """
  exm_get_coord(int exoid, REAL* xbuf, REAL* ybuf, REAL* zbuf)
  
     exoid: an open exodus file descriptor
     xbuf, ybuf, zbuf: buffers for the X-, Y-, and Z-coordinates; the ybuf is
                       only used if the spatial dimension is 2 or 3; zbuf only
                       if dim is 3; if the file stores doubles, then the
                       buffers must store doubles as well, otherwise floats
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == array.ArrayType
    if _comp_ws_[arg0] == 4:
      assert arg1.typecode == 'f'
    else:
      assert arg1.typecode == 'd'
    assert type(arg2) == array.ArrayType
    if _comp_ws_[arg0] == 4:
      assert arg2.typecode == 'f'
    else:
      assert arg2.typecode == 'd'
    assert type(arg3) == array.ArrayType
    if _comp_ws_[arg0] == 4:
      assert arg3.typecode == 'f'
    else:
      assert arg3.typecode == 'd'
    exomod_lib.exm_get_coord(arg0, arg1, arg2, arg3)
    
def exm_get_conn(arg0, arg1, arg2, arg3, arg4):
    """
  exm_get_conn(int exoid, int block_type, int block_id, int conn_type,
               int* conn)
  
     exoid: an open exodus file descriptor
     block_type: one of  EX_EDGE_BLOCK, EX_FACE_BLOCK, or EX_ELEM_BLOCK
     block_id: the target block id
     conn_type: type of connections (one of EX_NODE, EX_EDGE, EX_FACE)
     conn: an integer buffer to store the connectivity matrix; the length
           must be num_objects*num_connections_per_object (such as
           num_elements*num_nodes_per_element)
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == types.IntType
    assert type(arg4) == array.ArrayType and arg4.typecode == 'i'
    exomod_lib.exm_get_conn(arg0, arg1, arg2, arg3, arg4)
    
def exm_get_set(arg0, arg1, arg2, arg3, arg4):
    """
  exm_get_set(int exoid, int set_type, int set_id,
              int* set_values, int* auxiliary)
     
     exoid: an open exodus file descriptor
     set_type: one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,
               EX_SIDE_SET, EX_ELEM_SET
     set_id: the target set id
     set_values: the set values; length is the number of objects in the set
     auxiliary: unused for EX_NODE_SET and EX_ELEM_SET; must have same length
                as 'set_values' otherwise; stores +/- orientations for
                EX_EDGE_SET and EX_FACE_SET, or local side numbers for
                EX_SIDE_SET
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == array.ArrayType and arg3.typecode == 'i'
    assert type(arg4) == array.ArrayType and arg4.typecode == 'i'
    exomod_lib.exm_get_set(arg0, arg1, arg2, arg3, arg4)
    
def exm_get_set_dist_fact(arg0, arg1, arg2, arg3):
    """
  exm_get_set_dist_fact(int exoid, int set_type, int set_id, REAL* values)
     
     exoid: an open exodus file descriptor
     set_type: one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,
               EX_SIDE_SET, EX_ELEM_SET
     set_id: the target set id
     values: the distribution factors; length is the number of objects in the
             set; the type is float if the file stores float, otherwise double
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == array.ArrayType
    if _comp_ws_[arg0] == 4:
      assert arg3.typecode == 'f'
    else:
      assert arg3.typecode == 'd'
    exomod_lib.exm_get_set_dist_fact(arg0, arg1, arg2, arg3)
    
def exm_get_map(arg0, arg1, arg2, arg3):
    """
  exm_get_map(int exoid, int map_type, int map_id, int* map_values)
     
     exoid: an open exodus file descriptor
     map_type: one of EX_NODE_MAP, EX_EDGE_MAP, EX_FACE_MAP, EX_ELEM_MAP
     map_id: the target map id
     map_values: the map values; length is the number of objects in the map
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == array.ArrayType and arg3.typecode == 'i'
    exomod_lib.exm_get_map(arg0, arg1, arg2, arg3)
    
def exm_get_glob_vars(arg0, arg1, arg2, arg3):
    """
  exm_get_glob_vars(int exoid, int time_step, int num_global_vars, REAL* values)
     
     exoid: an open exodus file descriptor
     time_step: time step number (they start at 1)
     num_global_vars: the number of global variables in the file
     values: the variable values; length must be 'num_global_vars'; the type
             is float if the file stores float, otherwise double
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == array.ArrayType
    if _comp_ws_[arg0] == 4:
      assert arg3.typecode == 'f'
    else:
      assert arg3.typecode == 'd'
    exomod_lib.exm_get_glob_vars(arg0, arg1, arg2, arg3)
    
def exm_get_nodal_var(arg0, arg1, arg2, arg3, arg4):
    """
  exm_get_nodal_var(int exoid, int time_step, int var_idx,
                    int num_nodes, REAL* values)
     
     exoid: an open exodus file descriptor
     time_step: time step number (they start at 1)
     var_idx: the variable index
     num_nodes: the number of nodes in the file
     values: the variable values; length must be 'num_nodes'; the type is
             float if the file stores float, otherwise double
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == types.IntType
    assert type(arg4) == array.ArrayType
    if _comp_ws_[arg0] == 4:
      assert arg4.typecode == 'f'
    else:
      assert arg4.typecode == 'd'
    exomod_lib.exm_get_nodal_var(arg0, arg1, arg2, arg3, arg4)
    
def exm_get_var(arg0, arg1, arg2, arg3, arg4, arg5, arg6):
    """
  exm_get_var(int exoid, int time_step, int var_type, int var_idx,
              int block_id, int num_objects, REAL* values)
     
     exoid: an open exodus file descriptor
     time_step: time step number (they start at 1)
     var_type: one of EX_ELEM_BLOCK, EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_NODE_SET,
               EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET
     var_idx: the variable index
     block_id: the id of the block or set
     num_objects: the number of objects in the block or set
     values: the variable values; length must be 'num_objects'; the type is
             float if the file stores float, otherwise double
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == types.IntType
    assert type(arg4) == types.IntType
    assert type(arg5) == types.IntType
    assert type(arg6) == array.ArrayType
    if _comp_ws_[arg0] == 4:
      assert arg6.typecode == 'f'
    else:
      assert arg6.typecode == 'd'
    exomod_lib.exm_get_var(arg0, arg1, arg2, arg3, arg4, arg5, arg6)
    
def exm_get_block_var(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9):
    """
  exm_get_block_var(int exoid, int time_step, int var_type,
                    int var_idx, int num_ids, const int* block_ids,
                    const int* num_objects, const int* is_stored,
                    char storage, REAL* values)
     
     exoid: an open exodus file descriptor
     time_step: time step number (they start at 1)
     var_type: one of EX_ELEM_BLOCK, EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_NODE_SET,
               EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET
     var_idx: the variable index
     num_ids: the number of block or set ids
     block_id: length 'num_ids'; the ids of each block or set
     num_objects: length 'num_ids'; the number of objects in each block or set
     is_stored: length 'num_ids'; the truth table (true if the variable is
                stored in a given block id, false otherwise)
     storage: 'f' if the file stores floats, otherwise 'd' for double
     values: the variable values; length must be the sum of the entries in
             the 'num_objects' array; the type is float if the file stores
             float, otherwise double
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == types.IntType
    assert type(arg4) == types.IntType
    assert type(arg5) == array.ArrayType and arg5.typecode == 'i'
    assert type(arg6) == array.ArrayType and arg6.typecode == 'i'
    assert type(arg7) == array.ArrayType and arg7.typecode == 'i'
    assert type(arg8) == types.StringType and len(arg8) == 1
    assert type(arg9) == array.ArrayType
    if _comp_ws_[arg0] == 4:
      assert arg9.typecode == 'f'
    else:
      assert arg9.typecode == 'd'
    exomod_lib.exm_get_block_var(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9)
    
def exm_get_var_time(arg0, arg1, arg2, arg3, arg4, arg5, arg6):
    """
  exm_get_var_time(int exoid, int var_type, int var_idx, int obj_index,
                   int beg_time_step, int end_time_step, REAL* values)
     
     exoid: an open exodus file descriptor
     var_type: one of EX_GLOBAL, EX_NODE, EX_ELEM_BLOCK, EX_EDGE_BLOCK,
               EX_FACE_BLOCK, EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,
               EX_ELEM_SET, EX_SIDE_SET
     var_idx: the variable index
     obj_index: the 0-offset index of the desired object (the internal index)
     beg_time_step: staring time step number (time steps start at 1)
     end_time_step: ending time step number
     values: the variable values; length must be end_time_step-beg_time_step+1;
             the type is float if the file stores float, otherwise double
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == types.IntType
    assert type(arg4) == types.IntType
    assert type(arg5) == types.IntType
    assert type(arg6) == array.ArrayType
    if _comp_ws_[arg0] == 4:
      assert arg6.typecode == 'f'
    else:
      assert arg6.typecode == 'd'
    exomod_lib.exm_get_var_time(arg0, arg1, arg2, arg3, arg4, arg5, arg6)
    
def exm_put_init(arg0, arg1, arg2):
    """
  exm_put_init(int exoid, string title, int* counts)
  
     'exoid' is an integer file descriptor of an open exodus file
     'title' is the title string (only MAX_LINE_LENGTH characters are written)
     'counts' an integer buffer of length 17 containing each count:
         [ 0] = num_dim
         [ 1] = num_nodes
         [ 2] = num_edges
         [ 3] = num_edge_blk
         [ 4] = num_faces
         [ 5] = num_face_blk
         [ 6] = num_elems
         [ 7] = num_elem_blk
         [ 8] = num_node_sets
         [ 9] = num_edge_sets
         [10] = num_face_sets
         [11] = num_side_sets
         [12] = num_elem_sets
         [13] = num_node_maps
         [14] = num_edge_maps
         [15] = num_face_maps
         [16] = num_elem_maps
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.StringType
    assert type(arg2) == array.ArrayType and arg2.typecode == 'i'
    exomod_lib.exm_put_init(arg0, arg1, arg2)
    
def exm_put_qa(arg0, arg1, arg2):
    """
  exm_put_qa(int exoid, int num_qa, char* qabuf)
  
     exoid: an open exodus file descriptor
     num_qa: the number of QA records to store
     qabuf: a char buffer containing the QA records;  there must be
            4*num_qa null terminated strings concatenated together
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == array.ArrayType and arg2.typecode == 'c'
    exomod_lib.exm_put_qa(arg0, arg1, arg2)
    
def exm_put_info(arg0, arg1, arg2):
    """
  exm_put_info(int exoid, int num_info, char* info)
  
     exoid: an open exodus file descriptor
     num_info: the number of info records in the file
     info: a char buffer containing the QA records;  there must be
            num_info null terminated strings concatenated together
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == array.ArrayType and arg2.typecode == 'c'
    exomod_lib.exm_put_info(arg0, arg1, arg2)
    
def exm_put_coord_names(arg0, arg1, arg2, arg3, arg4):
    """
  exm_put_coord_names(int exoid, int ndim, const char* xname,
                      const char* yname, const char* zname)
  
     exoid: an open exodus file descriptor
     ndim: the spatial dimension stored in the file
     xname, yname, zname: char buffers containing the coordinate names;  only
                          xname used if dim is one, xname and yname if dim is
                          two, and all three if dim is three
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.StringType
    assert type(arg3) == types.StringType
    assert type(arg4) == types.StringType
    exomod_lib.exm_put_coord_names(arg0, arg1, arg2, arg3, arg4)
    
def exm_put_coord(arg0, arg1, arg2, arg3):
    """
  exm_put_coord(int exoid, REAL* xbuf, REAL* ybuf, REAL* zbuf)
  
     exoid: an open exodus file descriptor
     xbuf, ybuf, zbuf: buffers for the X-, Y-, and Z-coordinates; the ybuf is
                       only used if the spatial dimension is 2 or 3; zbuf only
                       if dim is 3; if the file stores doubles, then the
                       buffers must store doubles as well, otherwise floats
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == array.ArrayType
    if _comp_ws_[arg0] == 4:
      assert arg1.typecode == 'f'
    else:
      assert arg1.typecode == 'd'
    assert type(arg2) == array.ArrayType
    if _comp_ws_[arg0] == 4:
      assert arg2.typecode == 'f'
    else:
      assert arg2.typecode == 'd'
    assert type(arg3) == array.ArrayType
    if _comp_ws_[arg0] == 4:
      assert arg3.typecode == 'f'
    else:
      assert arg3.typecode == 'd'
    exomod_lib.exm_put_coord(arg0, arg1, arg2, arg3)
    
def exm_put_block(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8):
    """
  exm_put_block(int exoid, int block_type, int block_id,
                const char* block_type_name, int num_objects,
                int num_nodes_per_object, int num_edges_per_object,
                int num_faces_per_object, int num_attrs_per_object)
  
     exoid: an open exodus file descriptor
     block_type:  one of EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_ELEM_BLOCK
     block_id:  the integer block id
     block_type_name:  a string describing the object types (such as HEX8)
     num_objects:  number of objects/entries in this block
     num_nodes_per_object:  local number of nodes per object
     num_edges_per_object:  local number of edges per object
     num_faces_per_object:  local number of faces per object
     num_attrs_per_object:  number of attributes for each object
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == types.StringType
    assert type(arg4) == types.IntType
    assert type(arg5) == types.IntType
    assert type(arg6) == types.IntType
    assert type(arg7) == types.IntType
    assert type(arg8) == types.IntType
    exomod_lib.exm_put_block(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8)
    
def exm_put_conn(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8):
    """
  exm_put_conn(int exoid, int block_type, int block_id,
               int nodes_per_obj, int edges_per_obj, int faces_per_obj,
               const int* node_conn, const int* edge_conn,
               const int* face_conn)
  
     exoid: an open exodus file descriptor
     block_type: one of  EX_EDGE_BLOCK, EX_FACE_BLOCK, or EX_ELEM_BLOCK
     block_id: the target block id
     nodes_per_obj: number of local nodes per object
     edges_per_obj: number of local edges per object
     faces_per_obj: number of local faces per object
     node_conn: an integer buffer to store the node connectivity matrix;
                the length must be num_objects*nodes_per_object
                (such as num_elements*num_nodes_per_element)
     edge_conn: an integer buffer to store the edge connectivity matrix;
                the length must be num_objects*edges_per_object
     face_conn: an integer buffer to store the face connectivity matrix;
                the length must be num_objects*faces_per_object
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == types.IntType
    assert type(arg4) == types.IntType
    assert type(arg5) == types.IntType
    assert type(arg6) == array.ArrayType and arg6.typecode == 'i'
    assert type(arg7) == array.ArrayType and arg7.typecode == 'i'
    assert type(arg8) == array.ArrayType and arg8.typecode == 'i'
    exomod_lib.exm_put_conn(arg0, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8)
    
def exm_put_set_param(arg0, arg1, arg2, arg3, arg4):
    """
  exm_put_set_param(int exoid, int set_type, int set_id,
                    int num_objs, int num_dist_factors)
  
     exoid: an open exodus file descriptor
     set_type: one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET,
               EX_SIDE_SET
     set_id: integer set id
     num_objs: number of objects in the set
     num_dist_factors: number of distribution factors
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == types.IntType
    assert type(arg4) == types.IntType
    exomod_lib.exm_put_set_param(arg0, arg1, arg2, arg3, arg4)
    
def exm_put_set(arg0, arg1, arg2, arg3, arg4):
    """
  exm_put_set(int exoid, int set_type, int set_id,
              const int* set_values, const int* auxiliary)
     
     exoid: an open exodus file descriptor
     set_type: one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,
               EX_SIDE_SET, EX_ELEM_SET
     set_id: the target set id
     set_values: the set values; length is the number of objects in the set
     auxiliary: unused for EX_NODE_SET and EX_ELEM_SET; must have same length
                as 'set_values' otherwise; stores +/- orientations for
                EX_EDGE_SET and EX_FACE_SET, or local side numbers for
                EX_SIDE_SET
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == array.ArrayType and arg3.typecode == 'i'
    assert type(arg4) == array.ArrayType and arg4.typecode == 'i'
    exomod_lib.exm_put_set(arg0, arg1, arg2, arg3, arg4)
    
def exm_put_set_dist_fact(arg0, arg1, arg2, arg3):
    """
  exm_put_set_dist_fact(int exoid, int set_type, int set_id, const REAL* values)
     
     exoid: an open exodus file descriptor
     set_type: one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,
               EX_SIDE_SET, EX_ELEM_SET
     set_id: the target set id
     values: the distribution factors; length is the number of objects in the
             set; the type is float if the file stores float, otherwise double
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == array.ArrayType
    if _comp_ws_[arg0] == 4:
      assert arg3.typecode == 'f'
    else:
      assert arg3.typecode == 'd'
    exomod_lib.exm_put_set_dist_fact(arg0, arg1, arg2, arg3)
    
def exm_put_map(arg0, arg1, arg2, arg3):
    """
  exm_put_map(int exoid, int map_type, int map_id, const int* map_values)
     
     exoid: an open exodus file descriptor
     map_type: one of EX_NODE_MAP, EX_EDGE_MAP, EX_FACE_MAP, EX_ELEM_MAP
     map_id: the target map id
     map_values: the map values; length is the number of objects in the map
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == array.ArrayType and arg3.typecode == 'i'
    exomod_lib.exm_put_map(arg0, arg1, arg2, arg3)
    
def exm_put_vars(arg0, arg1, arg2, arg3):
    """
  exm_put_vars(int exoid, int var_type, int num_vars, char* namebuf)
  
     exoid: an open exodus file descriptor
     var_type: one of EX_GLOBAL, EX_NODAL, EX_ELEM_BLOCK, EX_EDGE_BLOCK,
               EX_FACE_BLOCK, EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,
               EX_ELEM_SET, EX_SIDE_SET, where EX_NODAL == 15
     num_vars: number of variable names to be written
     namebuf: a char buffer containing the sequence of names, each string
              must be terminated with a NUL char; the number of names must
              match the 'num_vars' value; note that the char buffer may be
              modified to restrict the name lengths to a max of MAX_STR_LENGTH
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == array.ArrayType and arg3.typecode == 'c'
    exomod_lib.exm_put_vars(arg0, arg1, arg2, arg3)
    
def exm_put_truth_table(arg0, arg1, arg2, arg3, arg4):
    """
  exm_put_truth_table(int exoid, int var_type, int num_blocks,
                      int num_vars, const int* table )
  
     exoid: an open exodus file descriptor
     var_type: one of EX_ELEM_BLOCK, EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_NODE_SET,
               EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET
     num_blocks: the number of blocks or sets stored for the var_type
     num_vars: the number of variables stored for the var_type
     table: an integer buffer of length num_blocks*num_vars containing the
            truth table values; the variable index cycles faster than the
            block index
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == types.IntType
    assert type(arg4) == array.ArrayType and arg4.typecode == 'i'
    exomod_lib.exm_put_truth_table(arg0, arg1, arg2, arg3, arg4)
    
def exm_put_time(arg0, arg1, arg2):
    """
  exm_put_time(int exoid, int time_step, const REAL* time)
  
     exoid: an open exodus file descriptor
     time_step: time steps begin at one (1)
     time: a length one array storing the floating point time value;  if the
           file stores doubles, then it must store a double, otherwise a float
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == array.ArrayType
    if _comp_ws_[arg0] == 4:
      assert arg2.typecode == 'f'
    else:
      assert arg2.typecode == 'd'
    exomod_lib.exm_put_time(arg0, arg1, arg2)
    
def exm_put_glob_vars(arg0, arg1, arg2, arg3):
    """
  exm_put_glob_vars(int exoid, int time_step, int num_vars, const REAL* values)
     
     exoid: an open exodus file descriptor
     time_step: time step number (they start at 1)
     num_vars: the number of global variables in the file
     values: the variable values; length must be 'num_vars'; the type
             is float if the file stores float, otherwise double
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == array.ArrayType
    if _comp_ws_[arg0] == 4:
      assert arg3.typecode == 'f'
    else:
      assert arg3.typecode == 'd'
    exomod_lib.exm_put_glob_vars(arg0, arg1, arg2, arg3)
    
def exm_put_nodal_var(arg0, arg1, arg2, arg3, arg4):
    """
  exm_put_nodal_var(int exoid, int time_step, int var_idx,
                    int num_nodes, const REAL* values)
     
     exoid: an open exodus file descriptor
     time_step: time step number (they start at 1)
     var_idx: the variable index
     num_nodes: the number of nodes in the file
     values: the variable values; length must be 'num_nodes'; the type is
             float if the file stores float, otherwise double
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == types.IntType
    assert type(arg4) == array.ArrayType
    if _comp_ws_[arg0] == 4:
      assert arg4.typecode == 'f'
    else:
      assert arg4.typecode == 'd'
    exomod_lib.exm_put_nodal_var(arg0, arg1, arg2, arg3, arg4)
    
def exm_put_var(arg0, arg1, arg2, arg3, arg4, arg5, arg6):
    """
  exm_put_var(int exoid, int time_step, int var_type, int var_idx,
              int block_id, int num_objects, const REAL* values)
     
     exoid: an open exodus file descriptor
     time_step: time step number (they start at 1)
     var_type: one of EX_ELEM_BLOCK, EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_NODE_SET,
               EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET
     var_idx: the variable index
     block_id: the id of the block or set
     num_objects: the number of objects in the block or set
     values: the variable values; length must be 'num_objects'; the type is
             float if the file stores float, otherwise double
    """
    assert type(arg0) == types.IntType
    assert type(arg1) == types.IntType
    assert type(arg2) == types.IntType
    assert type(arg3) == types.IntType
    assert type(arg4) == types.IntType
    assert type(arg5) == types.IntType
    assert type(arg6) == array.ArrayType
    if _comp_ws_[arg0] == 4:
      assert arg6.typecode == 'f'
    else:
      assert arg6.typecode == 'd'
    exomod_lib.exm_put_var(arg0, arg1, arg2, arg3, arg4, arg5, arg6)
