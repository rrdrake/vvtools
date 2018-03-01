#!/usr/bin/env python

import sys, os
import array
import string
import types

import exomod

wrapper_version = 13

# these constants are from exodus API version 4.68 which can be found
# in the exodus/cbind/include header files

EX_NOCLOBBER          =  0
EX_CLOBBER            =  1
EX_NORMAL_MODEL       =  2
EX_LARGE_MODEL        =  4
EX_NETCDF4            =  8
EX_NOSHARE            = 16
EX_SHARE              = 32

EX_READ               =  0
EX_WRITE              =  1

EX_ELEM_BLOCK         =  1
EX_NODE_SET           =  2
EX_SIDE_SET           =  3
EX_ELEM_MAP           =  4
EX_NODE_MAP           =  5
EX_EDGE_BLOCK         =  6
EX_EDGE_SET           =  7
EX_FACE_BLOCK         =  8
EX_FACE_SET           =  9
EX_ELEM_SET           = 10
EX_EDGE_MAP           = 11
EX_FACE_MAP           = 12
EX_GLOBAL             = 13
EX_NODE               = 15  # not defined in exodus
EX_EDGE               = 16  # not defined in exodus
EX_FACE               = 17  # not defined in exodus
EX_ELEM               = 18  # not defined in exodus

MAX_STR_LENGTH        =  32
MAX_VAR_NAME_LENGTH   =  20
MAX_LINE_LENGTH       =  80
MAX_ERR_LENGTH        =  256

EX_VERBOSE     = 1
EX_DEBUG       = 2
EX_ABORT       = 4


class ExodusFile:
   
    def __init__(self, filename=None, mode=EX_READ):
        """
        If a filename is given, it is opened for reading with EX_READ or for
        reading and writing with EX_WRITE.

        If no filename is given, an empty ExodusFile object is created;
        to create the actual file, use createFile
        """
        self.save_exomod = exomod  # save this for the __del__ method
        # look at the _reset() method to see what variables are always defined
        if mode != EX_READ and mode != EX_WRITE:
          raise ValueError( "arg2 must be EX_READ or EX_WRITE" )
        if filename != None and filename:
          self.exoid = None
          self._open_file( filename, mode )
        else:
          self._reset()
    
    def openfile(self, filename, mode=EX_READ):
        """
        The given file name is opened for reading with EX_READ or for reading
        and writing with EX_WRITE.
        """
        if filename == None or len(filename) == 0:
          raise ValueError( "arg1 must be a non-empty string" )
        if mode != EX_READ and mode != EX_WRITE:
          raise ValueError( "arg2 must be EX_READ or EX_WRITE" )
        self._open_file( filename, mode )
    
    def parallelRead(self, file_list):
        """
        Reads each file and treates them as pieces of a single file.
        If list has length one, then performs the same as openfile().
        """
        self.closefile()  # just in case
        if len(file_list) == 0:
          raise ValueError( 'no files to read' )
        elif len(file_list) == 1:
          self.parlist = None
          self.exoid = None
          self._open_file( file_list[0], EX_READ )
        else:
          self.parlist = []
          for f in file_list:
            if not os.path.isfile(f):
              raise ValueError( 'directory found in file list: "' + \
                                string.join(file_list) + '"' )
            self.parlist.append( ExodusFile(f) )
          self._process_parlist()
    
    def parallelRead1(self, file_glob):
        """
        Grabs all files matching the glob pattern and treats them as pieces
        of a single file.  If only one file is matched, then performs the
        same as openfile().
        """
        self.closefile()  # just in case
        import glob
        files = glob.glob( file_glob )
        if len(files) == 0:
          raise ValueError( 'no files match file glob: "' + file_glob + '"' )
        elif len(files) == 1:
          self.parlist = None
          self.exoid = None
          self._open_file( files[0], EX_READ )
        else:
          self.parlist = []
          for f in files:
            if not os.path.isfile(f):
              raise ValueError( 'directory found in file glob: "' + \
                                file_glob + '"' )
            self.parlist.append( ExodusFile(f) )
          self._process_parlist()
    
    def parallelRead2(self, base, num_procs):
        """
        Assumes names are "<base>.<num procs>.<proc num>" where <proc num> runs
        from zero to num procs less one.
        """
        pass  # TODO:
    
    def closefile(self):
        """
        Closes the exodus file, if it is still open.
        """
        if self.exoid != None:
          exomod.exm_close( self.exoid )
          self.exoid = None
    
    def fileName(self):
        """
        """
        return self.filename
    
    def storageType(self):
        """
        An exodus file can store float or double data.  This function will
        return 'f' if the data is stored as float data and 'd' if double.
        """
        return self.storage_type
    
    def getTitle(self):
        """
        The title string.
        """
        return self.title
    
    def getDimension(self): return self.ndim
    
    def getQA(self):
        """
        Returns a list of 4-tuples, one for each QA record.
        """
        return self.qa_records
    
    def getInfo(self):
        """
        Returns a list of strings, one for each line of the info records.
        """
        if self.parlist != None:
          return self.parlist[0].getInfo()
        if self.exoid == None: raise IOError( "exodus file not open" )
        num_info = self.inq_cnts[10]
        L = []
        if num_info > 0:
          a = array.array('c')
          resize_array( a, num_info * (MAX_LINE_LENGTH+1) )
          exomod.exm_get_info( self.exoid, num_info, a )
          k = 0
          for i in xrange(num_info):
            L.append( string.rstrip(a[k:k+MAX_LINE_LENGTH+1].tostring(), '\0') )
            k = k + MAX_LINE_LENGTH + 1
        return L
    
    def getNumber(self, objtype):
        """
        Get the count of a given object type, such as EX_NODE, EX_ELEM_BLOCK,
        EX_EDGE_SET, EX_FACE_MAP, etc.
        """
        if objtype < 0 or objtype > max_type_index:
          raise ValueError( "unknown object type" )
        return self.num[objtype]
    
    def getCoordNames(self):
        """
        The names given to the coordinate directions.  If not stored in the
        file, None is returned.  Otherwise, a tuple of strings is returned
        whose length is equal to the spatial dimension.
        """
        return self.coornames
    
    def readCoords(self, coords=None):
        """
        Reads the x,y,z coordinate arrays from the file and returns a list
        of array.array, one for each spatial dimension.  If a list is given
        as an argument, then it must contain
          [ array.array(storageType()) ]
        if dimension is one,
          [ array.array(storageType()), array.array(storageType()) ]
        if dimension is two, etc.  In this case, the given array is returned.
        """
        if coords != None and len(coords) != self.getDimension():
          raise TypeError( "coords must be a list of array.array objects " + \
                           "equal to the dimension" )
        if coords != None and \
           ( type(coords[0]) != array.ArrayType or \
             (self.ndim > 1 and type(coords[1]) != array.ArrayType) or \
             (self.ndim > 2 and type(coords[2]) != array.ArrayType) ):
          raise TypeError( "coords entries must be array.array objects" )
        if coords != None and \
           ( coords[0].typecode != self.storageType() or \
             (self.ndim > 1 and coords[1].typecode != self.storageType()) or \
             (self.ndim > 2 and coords[2].typecode != self.storageType()) ):
          raise ValueError( \
                  "coord array typecodes must agree with the file storage" )
        if coords != None:
          coordsx = coords[0]
          if self.ndim > 1: coordsy = coords[1]
          else:             coordsy = array.array( self.storageType() )
          if self.ndim > 2: coordsz = coords[2]
          else:             coordsz = array.array( self.storageType() )
        else:
          coordsx = array.array( self.storageType() )
          coordsy = array.array( self.storageType() )
          coordsz = array.array( self.storageType() )
          coords = [ coordsx ]
          if self.ndim > 1: coords.append( coordsy )
          if self.ndim > 2: coords.append( coordsz )
        if self.parlist == None:
          if self.exoid == None: raise IOError( "exodus file not open" )
          resize_array( coordsx, self.num[EX_NODE] )
          if self.ndim > 1: resize_array( coordsy, self.num[EX_NODE] )
          if self.ndim > 2: resize_array( coordsz, self.num[EX_NODE] )
          exomod.exm_get_coord( self.exoid, coordsx, coordsy, coordsz )
        else:
          resize_array( coordsx, self.num[EX_NODE] )
          if self.ndim > 1: resize_array( coordsy, self.num[EX_NODE] )
          if self.ndim > 2: resize_array( coordsz, self.num[EX_NODE] )
          for exof in self.parlist:
            fcoords = exof.readCoords()
            i = 0
            while i < exof.num[EX_NODE]:
              # translate index from file local to global then to total local
              j = self.g2l[EX_NODE][ exof.l2g[EX_NODE][i] ]
              coordsx[j] = fcoords[0][i]
              if self.ndim > 1: coordsy[j] = fcoords[1][i]
              if self.ndim > 2: coordsz[j] = fcoords[2][i]
              i = i + 1
        return coords
    
    def getIds(self, objtype):
        """
        Returns a list of ids for blocks, sets and maps in order they are
        contained in the file.  No ids are defined for EX_NODE, EX_EDGE,
        EX_FACE or EX_ELEM.
        """
        if objtype < 0 or objtype > max_type_index or \
           objtype in [EX_NODE, EX_EDGE, EX_FACE, EX_ELEM, EX_GLOBAL]:
          raise ValueError( "invalid object type" )
        ids = []
        for L in self.meta[objtype]:
          ids.append( L[0] )
        return ids
    
    def getId(self, objtype, index):
        """
        Returns the id of the given block, set or map index.
        """
        if objtype < 0 or objtype > max_type_index or \
           objtype in [EX_NODE, EX_EDGE, EX_FACE, EX_ELEM, EX_GLOBAL]:
          raise ValueError( "invalid object type" )
        return self.meta[objtype][index][0]
    
    def getIndex(self, objtype, objid):
        """
        Returns the block, set or map index for the given id.  None is returned
        if the id is not found.  Thus, this method can be used to test for the
        existence of an id.
        """
        if objtype < 0 or objtype > max_type_index or \
           objtype in [EX_NODE, EX_EDGE, EX_FACE, EX_ELEM, EX_GLOBAL]:
          raise ValueError( "invalid object type" )
        return self.idmap[objtype].get(objid,None)
    
    def getBlock(self, blk_type, blk_id):
        """
        Returns a tuple containing meta data for the block,
          (id, count, type name, nodes per, edges per, faces per, attrs per )
        """
        if not blk_type in [EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_ELEM_BLOCK]:
          raise ValueError( "unknown block type" )
        idx = self.idmap[blk_type].get(blk_id,None)
        if idx == None:
          raise ValueError( "block id " + str(blk_id) + " not found" )
        return self.meta[blk_type][idx]
    
    def getSet(self, set_type, set_id):
        """
        Returns a tuple containing meta data for the set,
          (id, count, num dist factors)
        """
        if not set_type in [EX_NODE_SET,EX_EDGE_SET,EX_FACE_SET, \
                            EX_ELEM_SET,EX_SIDE_SET]:
          raise ValueError( "unknown set type" )
        idx = self.idmap[set_type].get(set_id,None)
        if idx == None:
          raise ValueError( "set id " + str(set_id) + " not found" )
        return self.meta[set_type][idx]
    
    def getCount(self, objtype, objid):
        """
        Returns the number of nodes/edges/faces/elems in a block, set or map.
        The objtype is EX_ELEM_BLOCK, EX_NODE_SET, EX_EDGE_MAP, etc.  Note
        that to get the total number of nodes, edges, faces, or elements, you
        would use getNumber() instead.
        """
        if objtype < 0 or objtype > max_type_index or \
           objtype in [EX_NODE, EX_EDGE, EX_FACE, EX_ELEM, EX_GLOBAL]:
          raise ValueError( "invalid object type: " + type_map[objtype] )
        idx = self.idmap[objtype].get(objid,None)
        if idx == None:
          raise ValueError( "objid " + str(objid) + " not found" )
        return self.meta[objtype][idx][1]
    
    def readConn(self, blk_type, blk_id, conn_type, conn=None ):
        """
        Get the connectivity array for the given block type and block id.
        Valid block types are EX_ELEM_BLOCK, EX_FACE_BLOCK, EX_EDGE_BLOCK.
        Valid connectivity types are EX_NODE, EX_EDGE, EX_FACE.
        
        If provided, the last argument must be an array of type 'i' and is
        filled with the connectivity (the node/edge/face index cycles faster
        than the object index).  If not provided, one is created and returned.
        
        The number of nodes/edges/faces per object is returned, or zero if
        that connectivity is not stored.  Note that the connectivity values
        are local, 0-offset based (the default storage for Exodus is local,
        1-offset based).
        
        For example, (EX_ELEM_BLOCK, 100, EX_NODE) will read and return the
        node connectivity array for element block id 100.
        """
        if not blk_type in [EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_ELEM_BLOCK]:
          raise ValueError( "arg1 must be a block type" )
        if not conn_type in [EX_NODE, EX_EDGE, EX_FACE]:
          raise ValueError( "arg3 must be EX_NODE, EX_EDGE or EX_FACE" )
        if conn != None and \
           ( type(conn) != array.ArrayType or conn.typecode != 'i' ):
          raise ValueError( "arg4 must be an array.array with typecode 'i'" )
        
        if conn == None:
          conn = array.array('i')
        
        idx = self.idmap[blk_type].get(blk_id,None)
        if idx == None:
          raise ValueError( "block id " + str(blk_id) + " not found" )
        
        bL = self.meta[blk_type][idx]
        cnt = bL[1]
        if   conn_type == EX_NODE: n_per = bL[3]  # nodes per
        elif conn_type == EX_EDGE: n_per = bL[4]  # edges per
        elif conn_type == EX_FACE: n_per = bL[5]  # faces per
        
        if n_per > 0:
          if self.parlist == None:
            if self.exoid == None: raise IOError( "exodus file not open" )
            resize_array( conn, cnt*n_per )
            exomod.exm_get_conn( self.exoid, blk_type, blk_id, conn_type, conn )
            for i in xrange(cnt*n_per):
              conn[i] = conn[i] - 1
          else:
            resize_array( conn, cnt*n_per )
            if cnt > 0:
              if   blk_type == EX_EDGE_BLOCK: obtype = EX_EDGE
              elif blk_type == EX_FACE_BLOCK: obtype = EX_FACE
              elif blk_type == EX_ELEM_BLOCK: obtype = EX_ELEM
              g2l = self.g2l[conn_type]
              for exof in self.parlist:
                fconn = exof.readConn(blk_type, blk_id, conn_type)
                # translate each entry to total index
                l2g = exof.l2g[conn_type]
                i = 0
                while i < len(fconn):
                  fconn[i] = g2l[ l2g[ fconn[i] ] ]
                  i = i + 1
                # translate block object index to total index and copy the
                # connectivity for that index
                off = exof.blockoff[blk_type][blk_id]
                i = 0
                n = exof.getCount(blk_type, blk_id)
                while i < n:
                  gi = exof.l2g[obtype][off+i]
                  li = self.g2l[obtype][gi] - self.blockoff[blk_type][blk_id]
                  conn[li*n_per:(li+1)*n_per] = fconn[i*n_per:(i+1)*n_per]
                  i = i + 1
        
        return conn
    
    def readSet(self, set_type, set_id):
        """
        Reads the set of a given type (EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,
        EX_ELEM_SET, EX_SIDE_SET) with the given ID.  Returns a pair of integer
        arrays.  The first contains local 0-offset indexes.  The second is
        unused except for:
          EX_SIDE_SET: contains the 0-offset based side numbers of the element
          EX_EDGE_SET,EX_FACE_SET: +1 or -1 is stored indicating orientation
        """
        if not set_type in [EX_NODE_SET,EX_EDGE_SET,EX_FACE_SET,
                            EX_ELEM_SET,EX_SIDE_SET]:
          raise ValueError( "arg1 must be a set type" )
        
        idx = self.idmap[set_type].get(set_id,None)
        if idx == None:
          raise ValueError( "set id " + str(set_id) + " not found" )
        T = self.meta[set_type][idx]
        
        set = array.array('i')
        resize_array( set, T[1] )
        aux = array.array('i')
        if set_type not in [EX_NODE_SET,EX_ELEM_SET]:
          resize_array( aux, T[1] )
        
        if self.parlist == None:
          if self.exoid == None: raise IOError( "exodus file not open" )
          exomod.exm_get_set( self.exoid, set_type, set_id, set, aux )
          if set_type == EX_SIDE_SET:
            for i in xrange(T[1]):
              set[i] = set[i] - 1
              aux[i] = aux[i] - 1
          else:
            for i in xrange(T[1]):
              set[i] = set[i] - 1
        else:
          if T[1] > 0:
            g2l = self.g2l[EX_ELEM]
            if   set_type == EX_NODE_SET: g2l = self.g2l[EX_NODE]
            elif set_type == EX_EDGE_SET: g2l = self.g2l[EX_EDGE]
            elif set_type == EX_FACE_SET: g2l = self.g2l[EX_FACE]
            L = self.setg2l[set_type][set_id].keys()
            L.sort()
            n = len(L)
            assert T[1] == len(L)
            if set_type in [EX_NODE_SET,EX_ELEM_SET]:
              for i in xrange(n):
                set[i] = g2l[ L[i] ]
            else:
              for i in xrange(n):
                set[i] = g2l[ L[i][0] ]
                aux[i] = L[i][1]
            L = None
        
        return [set,aux]
    
    def readDistributionFactors(self, set_type, set_id):
        """
        Reads the distribution factors for a given type (EX_NODE_SET,
        EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET) with the given
        ID.  Returns an array.array of floating point values.
        """
        if not set_type in [EX_NODE_SET,EX_EDGE_SET,EX_FACE_SET,
                            EX_ELEM_SET,EX_SIDE_SET]:
          raise ValueError( "first argument must be a set type" )
        
        idx = self.idmap[set_type].get(set_id,None)
        if idx == None:
          raise ValueError( "set id " + str(set_id) + " not found" )
        T = self.meta[set_type][idx]
        
        if T[1] > 0 and T[2] <= 0:
          raise ValueError( "distribution factors not stored for " + \
                            type_map[set_type] + " id " + str(set_id) )
        
        df = array.array( self.storageType() )
        resize_array( df, T[2] )
        
        if self.parlist == None:
          if self.exoid == None: raise IOError( "exodus file not open" )
          exomod.exm_get_set_dist_fact( self.exoid, set_type, set_id, df )
        elif T[1] > 0:
          obj_t = EX_ELEM
          if   set_type == EX_NODE_SET: obj_t = EX_NODE
          elif set_type == EX_EDGE_SET: obj_t = EX_EDGE
          elif set_type == EX_FACE_SET: obj_t = EX_FACE
          assert T[2] % T[1] == 0
          ndper = T[2] / T[1]
          sg2l = self.setg2l[set_type][set_id]
          for exof in self.parlist:
            file_df = exof.readDistributionFactors(set_type, set_id)
            l2g = exof.l2g[obj_t]
            ids,aux = exof.readSet( set_type, set_id )
            if len(ids) > 0:
              assert len(file_df) % len(ids) == 0
              assert len(file_df) / len(ids) == ndper
              if set_type in [EX_NODE_SET,EX_ELEM_SET]:
                for i in xrange(len(ids)):
                  ioff = sg2l[ l2g[ ids[i] ] ] * ndper
                  for j in range(ndper):
                    df[ioff+j] = file_df[i*ndper+j]
              else:
                for i in xrange(len(ids)):
                  p = ( l2g[ ids[i] ], aux[i] )
                  ioff = sg2l[p] * ndper
                  for j in range(ndper):
                    df[ioff+j] = file_df[i*ndper+j]
        
        return df
    
    def readMap(self, map_type, map_id):
        """
        Reads the map of a given type (EX_NODE_MAP, EX_EDGE_MAP, EX_FACE_MAP,
        EX_ELEM_MAP) with the given ID.  If the ID is negative, the map
        without an ID is read (using ex_get_node_num_map/ex_get_elem_num_map/
        ex_get_id_map) which is the parallel local to global mappings.  An
        integer array is returned.
        
        Note that there is no support for parallel read of maps due to the
        ambiguity of their meaning in this case.  However, the local to global
        id maps can be read (that is, when map_id < 0).
        """
        if not map_type in [EX_NODE_MAP,EX_EDGE_MAP,EX_FACE_MAP,EX_ELEM_MAP]:
          raise ValueError( "arg1 must be a map type" )
        
        if map_id < 0:
          if   map_type == EX_NODE_MAP: cnt = self.num[EX_NODE]
          elif map_type == EX_EDGE_MAP: cnt = self.num[EX_EDGE]
          elif map_type == EX_FACE_MAP: cnt = self.num[EX_FACE]
          else:                         cnt = self.num[EX_ELEM]
        else:
          idx = self.idmap[map_type].get(map_id,None)
          if idx == None:
            raise ValueError( "map id " + str(map_id) + " not found" )
          T = self.meta[map_type][idx]
          cnt = T[1]
        
        map_array = array.array('i')
        
        if cnt > 0:
          resize_array( map_array, cnt )
          if self.parlist == None:
            if self.exoid == None: raise IOError( "exodus file not open" )
            exomod.exm_get_map( self.exoid, map_type, map_id, map_array )
          elif map_id < 0:
            if   map_type == EX_NODE_MAP: L = self.gids[EX_NODE]
            elif map_type == EX_EDGE_MAP: L = self.gids[EX_EDGE]
            elif map_type == EX_FACE_MAP: L = self.gids[EX_FACE]
            else:                         L = self.gids[EX_ELEM]
            for i in xrange(cnt):
              map_array[i] = L[i]
          else:
            raise IOError( "Parallel read of an exodus map is not supported" )
        
        return map_array
    
    def getTimes(self):
        """
        Returns the set of output times that are stored in the file.
        """
        return self.times
    
    def varNames(self, objtype):
        """
        Returns a list of names for elements, nodes, edges, faces, or sets.
        They are in the same order as is stored in the exodus file.  Note that
        for this function, EX_ELEM and EX_ELEM_BLOCK return the same names,
        as do EX_FACE/EX_FACE_BLOCK and EX_EDGE/EX_EDGE_BLOCK.
        """
        if objtype < 0 or objtype > max_type_index or \
           objtype in [EX_NODE_MAP, EX_EDGE_MAP, EX_FACE_MAP, EX_ELEM_MAP]:
          raise ValueError( "invalid object type" )
        if   objtype == EX_ELEM: objtype = EX_ELEM_BLOCK
        elif objtype == EX_FACE: objtype = EX_FACE_BLOCK
        elif objtype == EX_EDGE: objtype = EX_EDGE_BLOCK
        return self.vars[objtype]
    
    def findVar(self, objtype, varname, case=1, underscore=1):
        """
        Searches the variable names for varname and returns the variable index
        or None if not found.  If case is false, a case insensitive search is
        performed.  If underscore is false, underscores and spaces are treated
        the same.
        """
        vL = self.varNames(objtype)
        if case:
          if underscore:
            for i in xrange(len(vL)):
              if vL[i] == varname:
                return i
          else:
            vn = string.join( string.split( varname, ' ' ), '' )
            vn = string.join( string.split( vn, '_' ), '' )
            for i in xrange(len(vL)):
              n = string.join( string.split( vL[i], ' ' ), '' )
              n = string.join( string.split( n, '_' ), '' )
              if n == vn:
                return i
        else:
          if underscore:
            vn = varname.lower()
            for i in xrange(len(vL)):
              if vL[i].lower() == vn:
                return i
          else:
            # no case and no underscore
            vn = string.join( string.split( varname, ' ' ), '' )
            vn = string.join( string.split( vn, '_' ), '' )
            vn = vn.lower()
            for i in xrange(len(vL)):
              n = string.join( string.split( vL[i], ' ' ), '' )
              n = string.join( string.split( n, '_' ), '' )
              if vn == n.lower():
                return i
        return None
    
    def findDisVarBase(self):
        """
        Searches the node variable names for displacement variables
        and returns the basename or None if not found. The search
        specifically looks for node variable names of the form
        <base><sepchar>{x,y,z}; where <base>.lower() is "dis" or "displ",
        and <sepchar> is one of {"", "_", " "}. The basename returned is
        <base><sepchar>, with the case preserved. If the dataset is 2D, both
        basename + "x" and basename + "y" must be found, and the case of "x"
        and "y" must be the same. If the dataset is 3D, then basename + "z"
        must also be found and the case of "z" match that of "x" and "y".
        """
        vL = self.varNames(EX_NODE)
        nd = self.getDimension()

        basename = None
        match = []
        base = ["dis","displ"]
        sepchar = ["","_"," "]
        for nv_name in vL:
            for b in base:
                for s in sepchar:
                    if nv_name.lower() == b + s + "x":
                        match.append(nv_name)
        if len(match) == 0: return None
        else:
            while len(match) > 0:
                nv_name = match.pop()
                if nd>1:
                    if ( nv_name[-1] == 'x' and
                        (not nv_name[:-1] + "y" in vL) ): break
                    elif ( nv_name[-1] == 'X' and
                        (not nv_name[:-1] + "Y" in vL) ): break
                if nd==3:
                    if ( nv_name[-1] == 'x' and
                        (not nv_name[:-1] + "z" in vL) ): break
                    elif ( nv_name[-1] == 'X' and
                        (not nv_name[:-1] + "Z" in vL)): break
                basename = nv_name[:-1]
            return basename
    
    def getTruthTable(self, objtype):
        """
        """
        if not objtype in [ EX_ELEM_BLOCK, EX_FACE_BLOCK, EX_EDGE_BLOCK, \
                            EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET, \
                            EX_ELEM_SET, EX_SIDE_SET ]:
          raise ValueError( "invalid object type" )
        return self.var_tt[objtype]
    
    def variableStored(self, objtype, objid, var_index):
        """
        An edge/face/elem block or node/edge/face/elem/side set may not have
        all variables stored on it.  This function will return true if the
        variable is stored on the block/set id.  The objid is a block or set
        id and var_index is the variable to check.
        """
        if not objtype in [ EX_ELEM_BLOCK, EX_FACE_BLOCK, EX_EDGE_BLOCK, \
                            EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET, \
                            EX_ELEM_SET, EX_SIDE_SET ]:
          raise ValueError( "invalid object type" )
        idx = self.idmap[objtype].get(objid,None)
        if idx == None:
          raise ValueError( "block/set/map id " + str(objid) + " not found" )
        return self.var_tt[objtype][var_index][idx]
    
    def readVar(self, time_step, objtype, objid, var_index, values=None ):
        """
        Return an array with the variable values at the given time step.  The
        first time step has value 1, one.  The objid is the block or set id,
        and the var_index is the variable to get.  The 'values' argument must
        be None or an array.array object with typecode equal to storageType().
        
        If 'time_step' is negative, then the last time step is read.
        
        If 'objid' is None, then the values are read for all object ids (such
        as all element blocks.)  If the variable is not stored on some blocks,
        then zeros will be inserted.
        
        For objtype EX_GLOBAL, the var_index and objid are ignored and all
        variable values are read and loaded into the values array.
        
        For objtype EX_NODE, the objid is ignored because there is no concept
        of node blocks.
        
        Note that EX_ELEM and EX_ELEM_BLOCK are treated as the same thing. So
        are EX_FACE/EX_FACE_BLOCK and EX_EDGE/EX_EDGE_BLOCK.
        """
        if values != None and (type(values) != array.ArrayType or \
           values.typecode != self.storageType()):
          raise ValueError( "the 'values' argument must be an " + \
                            "array.array with typecode == storageType()" )
        if objtype < 0 or objtype > max_type_index or \
           objtype in [EX_NODE_MAP, EX_EDGE_MAP, EX_FACE_MAP, EX_ELEM_MAP]:
          raise ValueError( "invalid object type" )
        
        if time_step < 0:
          time_step = len(self.times)
        
        if time_step == 0 or time_step > len(self.times):
          raise ValueError( "time step " + str(time_step) + " out of bounds" )
        
        if   objtype == EX_ELEM: objtype = EX_ELEM_BLOCK
        elif objtype == EX_FACE: objtype = EX_FACE_BLOCK
        elif objtype == EX_EDGE: objtype = EX_EDGE_BLOCK
        if objtype != EX_GLOBAL and \
           ( var_index < 0 or var_index >= len(self.vars[objtype]) ):
          raise ValueError( "var_index out of bounds" )
        if objtype != EX_GLOBAL and objtype != EX_NODE and objid != None and \
           self.getIndex(objtype, objid) == None:
          raise ValueError( "block or set id " + str(objid) + " not found" )
        if objtype != EX_GLOBAL and objtype != EX_NODE and objid != None and \
           not self.variableStored(objtype, objid, var_index):
          raise ValueError( "variable index " + str(var_index) + \
                            " not stored on block/set id " + str(objid) )
        
        if values == None:
          values = array.array( self.storageType() )
        
        if objtype == EX_GLOBAL:
          exof = self
          if self.parlist != None:
            exof = self.parlist[0]
          if exof.exoid == None: raise IOError( "exodus file not open" )
          resize_array( values, len(self.vars[EX_GLOBAL]) )
          exomod.exm_get_glob_vars( exof.exoid, time_step,
                                    len(self.vars[EX_GLOBAL]), values )
        elif self.parlist == None:
          if self.exoid == None: raise IOError( "exodus file not open" )
          if objtype == EX_NODE:
            resize_array( values, self.num[EX_NODE] )
            exomod.exm_get_nodal_var( self.exoid, time_step, var_index+1,
                                      self.num[EX_NODE], values )
          elif objid != None:
            resize_array( values, self.getCount(objtype,objid) )
            exomod.exm_get_var( self.exoid, time_step, objtype,
                                var_index+1, objid,
                                self.getCount(objtype,objid), values )
          else:
            # read the values for all blocks
            values = self.readBlockVar( time_step, objtype, var_index, values )
          
        else:
          
          if objtype != EX_NODE and objid == None:
            # read the values for all blocks
            values = self.readBlockVar( time_step, objtype, var_index, values )
          else:
            if objtype == EX_NODE:
              resize_array( values, self.getNumber(EX_NODE) )
            else:
              resize_array( values, self.getCount(objtype, objid) )
            
            for exof in self.parlist:
              
              fvals = exof.readVar(time_step, objtype, objid, var_index)
              
              if   objtype in [EX_ELEM_BLOCK,EX_ELEM_SET]:
                l2g = exof.l2g[EX_ELEM]
                g2l = self.g2l[EX_ELEM]
                goff = self.blockoff[EX_ELEM_BLOCK][objid]
                foff = exof.blockoff[EX_ELEM_BLOCK][objid]
              elif objtype in [EX_FACE_BLOCK,EX_FACE_SET]:
                l2g = exof.l2g[EX_FACE]
                g2l = self.g2l[EX_FACE]
                goff = self.blockoff[EX_FACE_BLOCK][objid]
                foff = exof.blockoff[EX_FACE_BLOCK][objid]
              elif objtype in [EX_EDGE_BLOCK,EX_EDGE_SET]:
                l2g = exof.l2g[EX_EDGE]
                g2l = self.g2l[EX_EDGE]
                goff = self.blockoff[EX_EDGE_BLOCK][objid]
                foff = exof.blockoff[EX_EDGE_BLOCK][objid]
              else:
                l2g = exof.l2g[EX_NODE]
                g2l = self.g2l[EX_NODE]
                goff = 0
                foff = 0
              
              i = 0
              n = len(fvals)
              while i < n:
                values[ g2l[ l2g[foff+i] ] - goff ] = fvals[i]
                i = i + 1
        
        return values
    
    def readVars(self, time_step, objtype, objid, var_indexL, values=None ):
        """
        Same as readVar() except that the variable index is a list.  It reads
        a list of variables.  Returns a list equal in length to the number of
        variable indexes, where each entry is an array of the values.
        """
        if values != None:
          assert len(values) == len(var_indexL), "the 'values' argument " + \
                 "must have the same length as 'var_indexL'"
        
        if values == None:
          values = []
          for vi in var_indexL:
            values.append( array.array( self.storageType() ) )
        
        for i in range(len(var_indexL)):
          self.readVar( time_step, objtype, objid, var_indexL[i], values[i] )
        
        return values
    
    def readBlockVar(self, time_step, block_type, var_index, values=None ):
        """
        Same as readVar() except applies only to block variables (EX_ELEM_BLOCK,
        EX_FACE_BLOCK, EX_EDGE_BLOCK) and it reads the values for all blocks.
        Note that EX_NODE is allowed for convenience (it just calls readVar).
        Also note that EX_ELEM and EX_ELEM_BLOCK are treated as the same thing.
        So are EX_FACE/EX_FACE_BLOCK and EX_EDGE/EX_EDGE_BLOCK.  Lastly, for
        blocks that do not store the variable, zeros will be filled in.
        """
        if values != None and (type(values) != array.ArrayType or \
           values.typecode != self.storageType()):
          raise ValueError( "the 'values' argument must be an " + \
                            "array.array with typecode == storageType()" )
        if block_type not in [EX_NODE, EX_EDGE, EX_FACE, EX_ELEM,
                              EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_ELEM_BLOCK]:
          raise ValueError( "invalid block type: " + type_map[block_type] )
        
        if time_step < 0:
          time_step = len(self.times)
        
        if time_step == 0 or time_step > len(self.times):
          raise ValueError( "time step " + str(time_step) + " out of bounds" )
        if   block_type == EX_ELEM: block_type = EX_ELEM_BLOCK
        elif block_type == EX_FACE: block_type = EX_FACE_BLOCK
        elif block_type == EX_EDGE: block_type = EX_EDGE_BLOCK
        if var_index < 0 or var_index >= len(self.vars[block_type]):
          raise ValueError( "var_index out of bounds" )
        
        if block_type == EX_NODE:
          return self.readVar( time_step, EX_NODE, -1, var_index, values )
        
        if values == None:
          values = array.array( self.storageType() )
        
        if block_type == EX_ELEM_BLOCK:
          resize_array( values, self.getNumber(EX_ELEM) )
        elif block_type == EX_FACE_BLOCK:
          resize_array( values, self.getNumber(EX_FACE) )
        else:
          resize_array( values, self.getNumber(EX_EDGE) )
        
        if self.parlist == None:
          if self.exoid == None: raise IOError( "exodus file not open" )
          if len(values) > 0:
            ids = array.array('i')
            cnts = array.array('i')
            stored = array.array('i')
            for T in self.meta[block_type]:
              ids.append( T[0] )
              cnts.append( T[1] )
              if self.variableStored( block_type, T[0], var_index ):
                stored.append(1)
              else:
                stored.append(0)
            exomod.exm_get_block_var( self.exoid, time_step, block_type,
                                      var_index+1, len(ids), ids, cnts,
                                      stored, self.storageType(), values )
        else:
          
          for exof in self.parlist:
            
            fvals = exof.readBlockVar(time_step, block_type, var_index)
            
            if   block_type == EX_ELEM_BLOCK:
              l2g = exof.l2g[EX_ELEM]
              g2l = self.g2l[EX_ELEM]
            elif block_type == EX_FACE_BLOCK:
              l2g = exof.l2g[EX_FACE]
              g2l = self.g2l[EX_FACE]
            else:
              l2g = exof.l2g[EX_EDGE]
              g2l = self.g2l[EX_EDGE]
            
            i = 0
            n = len(fvals)
            while i < n:
              values[ g2l[ l2g[i] ] ] = fvals[i]
              i = i + 1
        
        return values
    
    def readVarTime(self, objtype, var_index, obj_index,
                          begin_time_step, end_time_step ):
        """
        Reads variable values for an object over multiple time steps.  The
        'objtype' is one of EX_NODE, EX_EDGE, EX_FACE, EX_ELEM and 'var_index'
        is the index of a stored variable.  The 'obj_index' is a local 0-offset
        based index.  The given time steps are an inclusive range, where the
        first time step is 1, one.  If the 'end_time_step' is negative, then
        the last time step in the database is used.
        """
        if objtype not in [ EX_GLOBAL, EX_NODE, EX_EDGE, EX_FACE, EX_ELEM,
                            EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_ELEM_BLOCK,
                            EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET, EX_SIDE_SET,
                            EX_ELEM_SET ]:
          raise ValueError( "invalid object type" )
        if var_index < 0 or var_index >= len(self.varNames(objtype)):
          raise ValueError( "var_index out of bounds" )
        if objtype != EX_GLOBAL and \
           ( obj_index < 0 or obj_index >= self.num[objtype] ):
          raise ValueError( "obj_index out of bounds" )
        if begin_time_step < 1 or begin_time_step > len(self.times):
          raise ValueError( "begin_time_step out of bounds" )
        if end_time_step >= 0 and end_time_step < begin_time_step:
          raise ValueError( "end_time_step cannot be < begin_time_step" )
        
        if   objtype == EX_EDGE: objtype = EX_EDGE_BLOCK
        elif objtype == EX_FACE: objtype = EX_FACE_BLOCK
        elif objtype == EX_ELEM: objtype = EX_ELEM_BLOCK
        
        if end_time_step < 0: end_time_step = len(self.times)
        vals = array.array( self.storageType() )
        resize_array( vals, end_time_step-begin_time_step+1 )
        
        # TODO: if parallel read, find file containing the obj_index
        
        exomod.exm_get_var_time( self.exoid, objtype, var_index+1,
                                 obj_index+1, begin_time_step,
                                 end_time_step, vals )
        
        return vals
    
    def computeCenters(self, blk_type, blk_id, \
                             coords=None, conn=None, centers=None ):
        """
        Computes the geometric centers for each object in an element, face,
        or edge block.  The blk_type is one of EX_ELEM_BLOCK, EX_FACE_BLOCK,
        or EX_EDGE_BLOCK.  The blk_id is the block id.  If provided, the
        coords are the nodal coordinates as given by the readCoords() method.
        If given, the conn is the block connectivity as given by the readConn()
        method.  If given, the centers must be a list of length equal to the
        dimension and each entry is an array.array with typecode storageType().
        Returns the centers list as just described.  Each array will have
        length equal to the number of objects in the block.
        
        If 'blk_id' is None, then all blocks are computed.  In this case,
        the 'conn' argument is ignored even if it is not None.  Similarly,
        the 'centers' argument is ignored in this case.
        """
        if not blk_type in [EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_ELEM_BLOCK]:
          raise ValueError( "arg1 must be a block type" )
        if coords != None and len(coords) != self.getDimension():
          raise TypeError( "coords must be a list of array.array objects " + \
                           "equal to the dimension" )
        if coords != None and \
           ( type(coords[0]) != array.ArrayType or \
             (self.ndim > 1 and type(coords[1]) != array.ArrayType) or \
             (self.ndim > 2 and type(coords[2]) != array.ArrayType) ):
          raise TypeError( "coords entries must be array.array objects" )
        if coords != None and \
           ( coords[0].typecode != self.storageType() or \
             (self.ndim > 1 and coords[1].typecode != self.storageType()) or \
             (self.ndim > 2 and coords[2].typecode != self.storageType()) ):
          raise ValueError( \
                  "coord array typecodes must agree with the file storage" )
        if coords != None and \
           ( len(coords[0]) != self.getNumber(EX_NODE) or \
            ( self.ndim > 1 and len(coords[1]) != self.getNumber(EX_NODE) ) or \
            ( self.ndim > 2 and len(coords[2]) != self.getNumber(EX_NODE) ) ):
          raise ValueError( \
                  "coord array lengths must equal number of nodes" )
        if conn != None and \
           ( type(conn) != array.ArrayType or conn.typecode != 'i' ):
          raise ValueError( "arg4 must be an array.array with typecode 'i'" )
        if centers != None and len(centers) != self.getDimension():
          raise TypeError( "centers must be a list of array.array objects " + \
                           "equal to the dimension" )
        if centers != None and \
           ( type(centers[0]) != array.ArrayType or \
             (self.ndim > 1 and type(centers[1]) != array.ArrayType) or \
             (self.ndim > 2 and type(centers[2]) != array.ArrayType) ):
          raise TypeError( "each centers entry must be an array.array object" )
        if centers != None and \
           ( centers[0].typecode != self.storageType() or \
             (self.ndim > 1 and centers[1].typecode != self.storageType()) or \
             (self.ndim > 2 and centers[2].typecode != self.storageType()) ):
          raise TypeError( "centers array typecode must be self.storageType()" )
        
        if blk_id == None:
          # compute centers for all blocks
          first = 1
          for bid in self.getIds( blk_type ):
            if first:
              centers = self.computeCenters( blk_type, bid,
                                             coords, None, None )
              first = 0
            else:
              vals2 = self.computeCenters( blk_type, bid,
                                           coords, None, None )
              centers[0].extend( vals2[0] )
              if self.ndim > 1: centers[1].extend( vals2[1] )
              if self.ndim > 2: centers[2].extend( vals2[2] )
        else:
          idx = self.idmap[blk_type].get(blk_id,None)
          if idx == None:
            raise ValueError( "block id " + str(blk_id) + " not found" )
          L = self.meta[blk_type][idx]
          nume = L[1]
          n_per = L[3]
          
          if conn != None:
            if len(conn) != nume * n_per:
              raise ValueError( "conn array must have length nume*n_per = " + \
                                str(nume*n_per) )
          else:
            conn = self.readConn( blk_type, blk_id, EX_NODE )
          
          if coords == None:
            coords = self.readCoords()
          
          if centers == None:
            a = array.array( self.storageType() )
            resize_array( a, nume )
            centers = [ a ]
            if self.ndim > 1:
              a = array.array( self.storageType() )
              resize_array( a, nume )
              centers.append( a )
            if self.ndim > 2:
              a = array.array( self.storageType() )
              resize_array( a, nume )
              centers.append( a )
          
          fnper = float(n_per)
          npL = range(n_per)
          
          cx = coords[0]
          xctr = centers[0]
          ni = 0
          for e in xrange(nume):
            x = 0.0
            for n in npL:
              x += cx[ conn[ni] ]
              ni += 1
            xctr[e] = x / fnper
          
          if self.ndim > 1:
            cy = coords[1]
            yctr = centers[1]
            ni = 0
            for e in xrange(nume):
              y = 0.0
              for n in npL:
                y += cy[ conn[ni] ]
                ni += 1
              yctr[e] = y / fnper
          
          if self.ndim > 2:
            cz = coords[2]
            zctr = centers[2]
            ni = 0
            for e in xrange(nume):
              z = 0.0
              for n in npL:
                z += cz[ conn[ni] ]
                ni += 1
              zctr[e] = z / fnper
        
        return centers
    
    ########## write methods
    
    def createFile(self, filename, clobber=EX_CLOBBER, storage_type='d'):
        """
        Creates the exodus file from the ExodusFile object. (First create
        the object with exoobj = ExodusFile(); then exoobj.createFile(...).)

        If 'clobber' is EX_CLOBBER and the file exists, it will be overwirtten.
        If it is EX_NOCLOBBER and the file exists, an IOError exception will be
        raised.  The 'storage_type' determines whether floating point data is
        stored as floats, 'f', or doubles, 'd'.
        """
        if filename == None or len(filename) == 0:
          raise ValueError( "arg1 must be a non-empty string" )
        if clobber != EX_CLOBBER and clobber != EX_NOCLOBBER:
          raise ValueError( "arg2 must be EX_CLOBBER or EX_NOCLOBBER" )
        if storage_type not in ['d','f']:
          raise ValueError( "arg3 must be 'd' or 'f'" )
        if clobber == EX_NOCLOBBER and os.path.exists(filename):
          raise IOError( "file exists but EX_NOCLOBBER was given, " + filename )
        self.closefile()
        self._reset()
        ws = 8
        if storage_type == 'f': ws = 4
        ta = array.array( 'i', [0] )
        exomod.exm_create( filename, clobber, ws, ws, ta )
        self.exoid = ta[0]
        self.storage_type = storage_type
    
    def setDimension(self, dim):
        """
        Must be called before putInit().
        """
        self.ndim = dim
    
    def setTitle(self, title):
        """
        Must be called before putInit().
        """
        self.title = title
    
    def setSizes(self, nnodes, nedges, nfaces, nelems,
                       nedgeblocks, nfaceblocks, nelemblocks,
                       nnodesets, nedgesets, nfacesets, nelemsets, nsidesets,
                       nnodemaps, nedgemaps, nfacemaps, nelemmaps ):
        """
        Must be called before putInit().  The nnodes/nedges/nfaces/nelems are
        the total number across all blocks.
        
        This resets the meta data in this object for blocks, sets, and maps.
        """
        self.num[EX_NODE]       = nnodes
        self.num[EX_EDGE]       = nedges
        self.num[EX_FACE]       = nfaces
        self.num[EX_ELEM]       = nelems
        self.num[EX_EDGE_BLOCK] = nedgeblocks
        self.num[EX_FACE_BLOCK] = nfaceblocks
        self.num[EX_ELEM_BLOCK] = nelemblocks
        self.num[EX_NODE_SET]   = nnodesets
        self.num[EX_EDGE_SET]   = nedgesets
        self.num[EX_FACE_SET]   = nfacesets
        self.num[EX_ELEM_SET]   = nelemsets
        self.num[EX_SIDE_SET]   = nsidesets
        self.num[EX_NODE_MAP]   = nnodemaps
        self.num[EX_EDGE_MAP]   = nedgemaps
        self.num[EX_FACE_MAP]   = nfacemaps
        self.num[EX_ELEM_MAP]   = nelemmaps
        
        # reset the metadata
        self.idmap = [{}]
        self.meta = [[]]
        for i in range(max_type_index):
          self.idmap.append({})
          self.meta.append([])
    
    def putInit(self):
        """
        Writes the meta data sizes set by setSizes() to the file.
        """
        if self.exoid == None: raise IOError( "exodus file not open" )
        
        ca = array.array('i',[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
        ca[ 0] = self.ndim
        ca[ 1] = self.num[EX_NODE]
        ca[ 2] = self.num[EX_EDGE]
        ca[ 3] = self.num[EX_EDGE_BLOCK]
        ca[ 4] = self.num[EX_FACE]
        ca[ 5] = self.num[EX_FACE_BLOCK]
        ca[ 6] = self.num[EX_ELEM]
        ca[ 7] = self.num[EX_ELEM_BLOCK]
        ca[ 8] = self.num[EX_NODE_SET]
        ca[ 9] = self.num[EX_EDGE_SET]
        ca[10] = self.num[EX_FACE_SET]
        ca[11] = self.num[EX_SIDE_SET]
        ca[12] = self.num[EX_ELEM_SET]
        ca[13] = self.num[EX_NODE_MAP]
        ca[14] = self.num[EX_EDGE_MAP]
        ca[15] = self.num[EX_FACE_MAP]
        ca[16] = self.num[EX_ELEM_MAP]
        exomod.exm_put_init(  self.exoid, self.title, ca )
    
    def putQA(self, qa_list):
        """
        The 'qa_list' must be a list of 4-tuples, one for each QA record.
        The exodus document has these meanings for the 4-tuple:
          1) the analysis code name
          2) the analysis code QA descriptor
          3) the analysis date
          4) the analysis time
        """
        if self.exoid == None: raise IOError( "exodus file not open" )
        if type(qa_list) != types.ListType and type(qa_list) != types.TupleType:
          raise IOError( "the 'qa_list' must be a python list" )
        for T in qa_list:
          if type(T) != types.ListType and type(T) != types.TupleType:
            raise IOError( "the entries of 'qa_list' must be tuples" )
          if len(T) != 4:
            raise IOError( "the entries of 'qa_list' must have length 4" )
          for s in T:
            if type(s) != types.StringType:
              raise IOError( "each QA record must be a string" )
        
        self.qa_records = []
        buf = array.array('c')
        for T in qa_list:
          self.qa_records.append( (T[0],T[1],T[2],T[3]) )
          for s in T:
            buf.fromstring( s[:MAX_STR_LENGTH] + '\0' )
        nrec = len(self.qa_records)
        exomod.exm_put_qa( self.exoid, nrec, buf )
    
    def putInfo(self, info_list):
        """
        Write a list of strings (lines) to the file.  Each string will be
        truncated to MAX_LINE_LENGTH characters.
        """
        if self.exoid == None: raise IOError( "exodus file not open" )
        if type(info_list) != types.ListType and \
           type(info_list) != types.TupleType:
          raise IOError( "the 'info_list' must be a python list" )
        for s in info_list:
          if type(s) != types.StringType:
            raise IOError( "the entries of 'info_list' must be strings" )
        
        buf = array.array('c')
        for s in info_list:
          buf.fromstring( s[:MAX_LINE_LENGTH] + '\0' )
        exomod.exm_put_info( self.exoid, len(info_list), buf )
        self.inq_cnts[10] = len(info_list)
    
    def putCoordNames(self, coord_names):
        """
        Write the names of the coordinate directions to the file.  If
        'coord_names' is None, nothing is done.  If not None, then 'coord_names'
        must be a tuple of strings with length equal to the spatial dimension.
        """
        if self.exoid == None: raise IOError( "exodus file not open" )
        if coord_names != None:
          if type(coord_names) != types.TupleType and \
             type(coord_names) != types.ListType:
            raise ValueError( "coord_names must be a tuple of strings" )
          if len(coord_names) != self.ndim:
            raise ValueError( "coord_names must be a tuple of strings of " + \
                               "length equal to the spatial dimension" )
          if type(coord_names[0]) != types.StringType or \
             (self.ndim > 1 and type(coord_names[1]) != types.StringType) or \
             (self.ndim > 2 and type(coord_names[2]) != types.StringType):
            raise ValueError( "coord_names entries must be strings" )
          xn = coord_names[0][:MAX_STR_LENGTH]
          yn = ""
          if self.ndim > 1: yn = coord_names[1][:MAX_STR_LENGTH]
          zn = ""
          if self.ndim > 2: zn = coord_names[2][:MAX_STR_LENGTH]
          exomod.exm_put_coord_names( self.exoid, self.ndim, xn, yn, zn )
    
    def putCoords(self, coordsL):
        """
        Writes the geometric coordinates to the file.  The 'coordsL' argument
        must be a list of array.array of length at least the number of spatial
        dimensions.  The type of storage in the arrays must be the same as
        the file storage, storageType().  The length of each of the arrays must
        be equal to the number of nodes.
        """
        if self.exoid == None: raise IOError( "exodus file not open" )
        if len(coordsL) < self.ndim:
          raise ValueError( "length of coords array must be at least as " + \
                            "big as the spatial dimension" )
        if type(coordsL[0]) != array.ArrayType or \
             (self.ndim > 1 and type(coordsL[1]) != array.ArrayType) or \
             (self.ndim > 2 and type(coordsL[2]) != array.ArrayType):
          raise TypeError( "coords entries must be array.array objects" )
        if coordsL[0].typecode != self.storageType() or \
             (self.ndim > 1 and coordsL[1].typecode != self.storageType()) or \
             (self.ndim > 2 and coordsL[2].typecode != self.storageType()):
          raise ValueError( \
                  "coord array typecodes must agree with the file storage" )
        if len(coordsL[0]) != self.num[EX_NODE] or \
             (self.ndim > 1 and len(coordsL[1]) != self.num[EX_NODE]) or \
             (self.ndim > 2 and len(coordsL[2]) != self.num[EX_NODE]):
          raise ValueError( \
                  "coord array lengths must equal the number of nodes" )
        if self.ndim > 0 and self.num[EX_NODE] > 0:
          cx = coordsL[0]
          cy = array.array( self.storageType() )
          cz = array.array( self.storageType() )
          if self.ndim > 1: cy = coordsL[1]
          if self.ndim > 2: cz = coordsL[2]
          exomod.exm_put_coord( self.exoid, cx, cy, cz )
    
    def putBlock(self, block_type, block_id, num_objs, type_name,
                       nodes_per_obj, edges_per_obj, faces_per_obj,
                       num_attrs_per_obj ):
        """
        Stores the block information in this object and also writes it to
        the exodus output file.
        """
        if block_type not in [EX_EDGE_BLOCK,EX_FACE_BLOCK,EX_ELEM_BLOCK]:
          raise IOError( "arg1 must be a block type" )
        idmap = self.idmap[block_type]
        meta = self.meta[block_type]
        tn = type_name[:MAX_STR_LENGTH]
        bT = (block_id, num_objs, tn,
              nodes_per_obj, edges_per_obj, faces_per_obj, num_attrs_per_obj)
        replace = 0
        for i in xrange(len(meta)):
          T = meta[i]
          if T[0] == block_id:
            assert idmap[block_id] == i
            meta[i] = bT  # overwrite the meta data for this block id
            replace = 1
            break
        if not replace:
          idmap[block_id] = len(meta)
          meta.append( bT )
        exomod.exm_put_block( self.exoid, block_type, block_id, tn, num_objs,
                              nodes_per_obj, edges_per_obj, faces_per_obj,
                              num_attrs_per_obj )
    
    def putConn(self, block_type, block_id,
                      node_conn, edge_conn=None, face_conn=None):
        """
        """
        if block_type not in [EX_EDGE_BLOCK,EX_FACE_BLOCK,EX_ELEM_BLOCK]:
          raise IOError( "arg1 must be a block type" )
        bidx = self.idmap[block_type].get(block_id,None)
        if bidx == None:
          raise IOError( "block id not found: " + str(block_id) )
        if edge_conn == None: edge_conn = array.array( 'i' )
        if face_conn == None: face_conn = array.array( 'i' )
        bT = self.meta[block_type][bidx]
        if bT[3] > 0:
          ncnt = bT[1]*bT[3]
          if len(node_conn) != ncnt:
            IOError( "length of node connectivity array != count*nodes_per_obj" )
          for n in xrange(ncnt):
            node_conn[n] = node_conn[n] + 1
        if bT[4] > 0:
          if len(edge_conn) != bT[1]*bT[4]:
            IOError( "length of edge connectivity array != count*edges_per_obj" )
        if bT[5] > 0:
          if len(face_conn) != bT[1]*bT[5]:
            IOError( "length of face connectivity array != count*faces_per_obj" )
        try:
          exomod.exm_put_conn( self.exoid,
                               block_type,
                               block_id,
                               bT[3],  # nodes per
                               bT[4],  # edges per
                               bT[5],  # faces per
                               node_conn,
                               edge_conn,
                               face_conn )
        except:
          if bT[3] > 0:
            for n in xrange(ncnt):
              node_conn[n] = node_conn[n] - 1
          raise
        else:
          if bT[3] > 0:
            for n in xrange(ncnt):
              node_conn[n] = node_conn[n] - 1
    
    def putSet(self, set_type, set_id, arrayL, num_distribution_factors=0):
        """
        Writes the set of a given type (EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET,
        EX_ELEM_SET, EX_SIDE_SET) with the given ID.  The 'arrayL' argument
        must be a pair of integer arrays.  The first contains local 0-offset
        indexes.  The second array is unused except for:
          EX_SIDE_SET: contains the 0-offset based side numbers of the element
          EX_EDGE_SET,EX_FACE_SET: +1 or -1 is stored indicating orientation
        This function also sets the number of distribution factors for the
        set.  For node sets, the number of dist factors must be zero or equal
        to the number of nodes in the set.  For all other set types, the
        number of dist factors must be zero or a multiple of the number of
        objects in the set.
        """
        if self.exoid == None: raise IOError( "exodus file not open" )
        if not set_type in [EX_NODE_SET,EX_EDGE_SET,EX_FACE_SET,
                            EX_ELEM_SET,EX_SIDE_SET]:
          raise ValueError( "arg1 must be a set type" )
        if len(arrayL) != 2:
          raise ValueError( "arg3 must be a pair of arrays" )
        if type(arrayL[0]) != array.ArrayType or \
           type(arrayL[1]) != array.ArrayType:
          raise TypeError( "arrayL entries must be array.array objects" )
        if arrayL[0].typecode != 'i' or arrayL[1].typecode != 'i':
          raise ValueError( "arrayL entry typecodes must be 'i'" )
        if set_type in [EX_EDGE_SET,EX_FACE_SET,EX_SIDE_SET] and \
           len(arrayL[0]) != len(arrayL[1]):
          raise ValueError( "arrayL entries must have the same length" )
        if num_distribution_factors < 0:
          raise ValueError( "number of distribution factors must be >= 0" )
        if len(arrayL[0]) > 0 and num_distribution_factors > 0:
          if set_type == EX_NODE_SET and \
             num_distribution_factors != len(arrayL[0]):
            raise ValueError( "for node sets, the number of distribution " + \
                              "factors must be zero or equal to the " + \
                              "number of nodes in the set" )
          if num_distribution_factors % len(arrayL[0]) != 0:
            raise ValueError( "the number of distribution factors must " + \
                              "be zero or a multiple of the " + \
                              "number of objects in the set" )
        
        idx = self.idmap[set_type].get(set_id,None)
        if idx == None:
          if len(self.meta[set_type]) < self.num[set_type]:
            idx = len(self.meta[set_type])
            self.idmap[set_type][set_id] = idx
            self.meta[set_type].append( \
                  (set_id, len(arrayL[0]), num_distribution_factors) )
          else:
            raise ValueError( "set id " + str(set_id) + " not found and " \
                              "no room for new sets" )
        T = self.meta[set_type][idx]
        
        if len(arrayL[0]) < T[1]:
          raise ValueError( "arrayL entries must have length >= set count" )
        
        exomod.exm_put_set_param( self.exoid,
                                  set_type,      # set type
                                  T[0],          # set id
                                  T[1],          # count
                                  T[2] )         # num dist factors
        
        n = T[1]
        a = arrayL[0]
        for i in xrange(n):
          a[i] = a[i] + 1
        if set_type == EX_SIDE_SET:
          a2 = arrayL[1]
          for i in xrange(n):
            a2[i] = a2[i] + 1
        
        try:
          exomod.exm_put_set( self.exoid, set_type, set_id,
                              arrayL[0], arrayL[1] )
        except:
          for i in xrange(n):
            a[i] = a[i] - 1
          if set_type == EX_SIDE_SET:
            for i in xrange(n):
              a2[i] = a2[i] - 1
          raise
        else:
          for i in xrange(n):
            a[i] = a[i] - 1
          if set_type == EX_SIDE_SET:
            for i in xrange(n):
              a2[i] = a2[i] - 1
    
    def putDistributionFactors(self, set_type, set_id, dist_factors):
        """
        Writes distribution factors for the given set type and id.  Type must
        be one of EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET,
        EX_SIDE_SET.  For set types other than node sets, if the number of
        dist factors is greater than the number of objects in the set, the
        given array is actually a matrix where the dist factors for each
        object cycles faster than the index for each object.
        """
        if self.exoid == None: raise IOError( "exodus file not open" )
        if not set_type in [EX_NODE_SET,EX_EDGE_SET,EX_FACE_SET,
                            EX_ELEM_SET,EX_SIDE_SET]:
          raise ValueError( "first argument must be a set type" )
        if type(dist_factors) != array.ArrayType or \
           dist_factors.typecode != self.storageType():
          raise ValueError( \
             "the 'dist_factors' argument must be an array.array with " + \
             "typecode == storageType()" )
        
        idx = self.idmap[set_type].get(set_id,None)
        if idx == None:
          raise ValueError( "set id " + str(set_id) + " not found" )
        T = self.meta[set_type][idx]
        
        if T[2] <= 0:
          raise ValueError( "set id " + str(set_id) + " was not defined " + \
                            "with distribution factors" )
        if len(dist_factors) != T[2]:
          raise ValueError( "set id " + str(set_id) + " requires " + \
                            str(T[2]) + " distribution factors but the " + \
                            "'dist_factors' array has length " + \
                            str(len(dist_factors)) )
        
        exomod.exm_put_set_dist_fact( self.exoid, set_type, set_id,
                                      dist_factors )
    
    def putMap(self, map_type, map_id, map_array):
        """
        Writes the map of a given type (EX_NODE_MAP, EX_EDGE_MAP, EX_FACE_MAP,
        EX_ELEM_MAP) with the given ID.  If the ID is negative, the map
        without an ID is written, using ex_put_node_num_map/ex_put_elem_num_map.
        The length of 'map_array' must be equal to the number of objects of
        the corresponding type, EX_NODE_MAP <-> number of nodes, etc.
        """
        if self.exoid == None: raise IOError( "exodus file not open" )
        if not map_type in [EX_NODE_MAP,EX_EDGE_MAP,EX_FACE_MAP,EX_ELEM_MAP]:
          raise ValueError( "arg1 must be a map type" )
        if type(map_array) != array.ArrayType:
          raise TypeError( "map_array must be an array.array object" )
        if map_array.typecode != 'i':
          raise ValueError( "map_array typecode must be 'i'" )
        if map_type == EX_NODE_MAP and len(map_array) != self.num[EX_NODE]:
          raise ValueError( "map_array length must equal num nodes" )
        if map_type == EX_EDGE_MAP and len(map_array) != self.num[EX_EDGE]:
          raise ValueError( "map_array length must equal num edges" )
        if map_type == EX_FACE_MAP and len(map_array) != self.num[EX_FACE]:
          raise ValueError( "map_array length must equal num faces" )
        if map_type == EX_ELEM_MAP and len(map_array) != self.num[EX_ELEM]:
          raise ValueError( "map_array length must equal num elements" )
        
        if map_id < 0:
          exomod.exm_put_map(self.exoid, map_type, map_id, map_array)
        
        else:
          idx = self.idmap[map_type].get(map_id,None)
          if idx == None:
            if len(self.meta[map_type]) < self.num[map_type]:
              idx = len(self.meta[map_type])
              self.idmap[map_type][map_id] = idx
              self.meta[map_type].append( (map_id, len(map_array)) )
            else:
              raise ValueError( "map id " + str(map_id) + " not found and " \
                                "no room for new maps" )
          exomod.exm_put_map(self.exoid, map_type, map_id, map_array)
    
    def copyMesh(self, source_exoobj):
        """
        Copies all data comprising the mesh from the given ExodusFile object
        and writes it into the current file.  Does not include variables nor
        time steps.
        """
        if self.exoid == None: raise IOError( "exodus file not open" )
        
        self.setTitle(source_exoobj.title)
        self.ndim = source_exoobj.ndim
        
        self.num = []
        for n in source_exoobj.num:
          self.num.append(n)
        
        self.idmap = []
        for D in source_exoobj.idmap:
          newD = {}
          for (k,v) in D.items():
            newD[k] = v
          self.idmap.append(newD)
        
        self.meta = []
        for L in source_exoobj.meta:
          newL = []
          for L2 in L:
            newL2 = []
            for T in L2:
              newL2.append(T)  # this references the tuple, which is immutable
            newL.append( newL2 )
          self.meta.append( newL )
        
        self.putInit()
        
        self.putCoords( source_exoobj.readCoords() )
        
        conn_n = array.array( 'i' )
        conn_g = array.array( 'i' )
        conn_f = array.array( 'i' )
        for t in [EX_EDGE_BLOCK,EX_FACE_BLOCK,EX_ELEM_BLOCK]:
          for T in self.meta[t]:
            self.putBlock( t, T[0], T[1], T[2], T[3], T[4], T[5], T[6] )
          for T in self.meta[t]:
            source_exoobj.readConn( t, T[0], EX_NODE, conn_n )
            source_exoobj.readConn( t, T[0], EX_EDGE, conn_g )
            source_exoobj.readConn( t, T[0], EX_FACE, conn_f )
            assert T[3] == 0 or len(conn_n) == T[1]*T[3]
            assert T[4] == 0 or len(conn_g) == T[1]*T[4]
            assert T[5] == 0 or len(conn_f) == T[1]*T[5]
            self.putConn( t, T[0], conn_n, conn_g, conn_f )
        
        for t in [EX_NODE_SET,EX_EDGE_SET,EX_FACE_SET,EX_ELEM_SET,EX_SIDE_SET]:
          for T in self.meta[t]:
            self.putSet( t, T[0], source_exoobj.readSet( t, T[0] ), T[2] )
            if T[2] > 0:
              df = source_exoobj.readDistributionFactors( t, T[0] )
              self.putDistributionFactors( t, T[0], df )
        
        self.putMap(EX_NODE_MAP, -1, source_exoobj.readMap(EX_NODE_MAP, -1))
        self.putMap(EX_EDGE_MAP, -1, source_exoobj.readMap(EX_EDGE_MAP, -1))
        self.putMap(EX_FACE_MAP, -1, source_exoobj.readMap(EX_FACE_MAP, -1))
        self.putMap(EX_ELEM_MAP, -1, source_exoobj.readMap(EX_ELEM_MAP, -1))
        for t in [EX_NODE_MAP,EX_EDGE_MAP,EX_FACE_MAP,EX_ELEM_MAP]:
          for T in self.meta[t]:
            self.putMap( t, T[0], source_exoobj.readMap( t, T[0] ) )
    
    def putVarNames(self, objtype, name_list):
        """
        Writes the variable names for globals, elements, nodes, edges, faces,
        or sets.  Note that for this function, EX_ELEM and EX_ELEM_BLOCK are
        the same thing, as are EX_FACE/EX_FACE_BLOCK and EX_EDGE/EX_EDGE_BLOCK.
        """
        if self.exoid == None: raise IOError( "exodus file not open" )
        if objtype < 0 or objtype > max_type_index or \
           objtype in [EX_NODE_MAP, EX_EDGE_MAP, EX_FACE_MAP, EX_ELEM_MAP]:
          raise ValueError( "invalid object type" )
        if   objtype == EX_ELEM: objtype = EX_ELEM_BLOCK
        elif objtype == EX_FACE: objtype = EX_FACE_BLOCK
        elif objtype == EX_EDGE: objtype = EX_EDGE_BLOCK
        
        if len(name_list) > 0:
          ar = array.array('c')
          for name in name_list:
            ar.fromstring( name[:MAX_STR_LENGTH] + '\0' )
          exomod.exm_put_vars( self.exoid, objtype, len(name_list), ar )
          self.vars[objtype] = [] + name_list
          
          # by default, all variables are stored in all blocks
          self.var_tt[objtype] = []
          for v in name_list:
            L = []
            for i in range(self.num[objtype]):
              L.append(1)  # true
            self.var_tt[objtype].append(L)
    
    def putTruthTable(self, objtype, true_false_matrix):
        """
        Call this after putVarNames() but before a call to putVar().  For
        elements, nodes, edges, faces, or sets, the variables can be stored
        or not stored on specific blocks or set ids.  The 'true_false_matrix'
        must be a two dimensional matrix indexed first by variable index then
        by block index or set index.  So the i-th variable on the j-th
        block (or set) is to be stored if true_false_matrix[i][j] is true.
        """
        if self.exoid == None: raise IOError( "exodus file not open" )
        if objtype not in [EX_ELEM_BLOCK, EX_EDGE_BLOCK, EX_FACE_BLOCK,
                           EX_NODE_SET, EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET,
                           EX_SIDE_SET]:
          raise ValueError( "invalid object type" )
        if   objtype == EX_ELEM: objtype = EX_ELEM_BLOCK
        elif objtype == EX_FACE: objtype = EX_FACE_BLOCK
        elif objtype == EX_EDGE: objtype = EX_EDGE_BLOCK
        
        nvar = len(self.vars[objtype])
        nblk = self.num[objtype]
        if nvar > 0 and nblk > 0:
          # note that exodus wants the variable index to cycle faster than
          # the block index, so the temp array is filled up that way
          a = array.array('i')
          resize_array( a, nvar*nblk )
          k = 0
          for j in range(nblk):
            for i in range(nvar):
              if true_false_matrix[i][j]:
                self.var_tt[objtype][i][j] = 1
                a[k] = 1
              else:
                self.var_tt[objtype][i][j] = 0
                a[k] = 0
              k = k + 1
          exomod.exm_put_truth_table( self.exoid, objtype, nblk, nvar, a )
    
    def putTime(self, time_step, time_value):
        """
        Time steps begin at one, 1.
        """
        if self.exoid == None: raise IOError( "exodus file not open" )
        if time_step < 1:
          raise ValueError( "time_step must be >= 1" )
        v = float(time_value)
        
        # first, add the time value onto the python list of times
        idx = time_step - 1
        if idx >= len(self.times):
          i = len(self.times)
          while i <= idx:
            self.times.append( 0.0 )
            i = i + 1
        self.times[idx] = v
        
        # then write the value to the exodus file
        ar = array.array( self.storageType() )
        ar.append( v )
        exomod.exm_put_time( self.exoid, time_step, ar )
    
    def putVar(self, values, time_step, objtype, objid, var_index ):
        """
        Write an array with the variable values to the given time step.  The
        first time step has value one, 1.  The objtype is the object type,
        such as EX_GLOBAL, EX_NODE, etc.  The objid is the block or set id,
        and the var_index is the variable index to write (the first index is
        zero, 0).  The first argument must be an array.array object with
        typecode equal to storageType() at least as long as the number of
        objects.
        
        For objtype EX_GLOBAL, the var_index and objid are ignored and all
        variable values are written to the file for the given time step.
        
        For objtype EX_NODE, the objid is ignored because there is no concept
        of node blocks.
        
        Note that EX_ELEM and EX_ELEM_BLOCK are treated as the same thing. So
        are EX_FACE/EX_FACE_BLOCK and EX_EDGE/EX_EDGE_BLOCK.
        """
        if self.exoid == None: raise IOError( "exodus file not open" )
        if type(values) != array.ArrayType or \
           values.typecode != self.storageType():
          raise ValueError( \
             "arg1 must be an array.array with typecode == storageType()" )
        if objtype < 0 or objtype > max_type_index or \
           objtype in [EX_NODE_MAP, EX_EDGE_MAP, EX_FACE_MAP, EX_ELEM_MAP]:
          raise ValueError( "invalid object type" )
        if time_step < 1:
          raise ValueError( "time_step must be >= 1" )
        if time_step > len(self.times):
          raise ValueError( "time step is greater than number of current " + \
                            "time values (add a time with putTime first)" )
        if   objtype == EX_ELEM: objtype = EX_ELEM_BLOCK
        elif objtype == EX_FACE: objtype = EX_FACE_BLOCK
        elif objtype == EX_EDGE: objtype = EX_EDGE_BLOCK
        if objtype != EX_GLOBAL and \
           ( var_index < 0 or var_index >= len(self.vars[objtype]) ):
          raise ValueError( "var_index out of bounds" )
        if objtype != EX_GLOBAL and objtype != EX_NODE and \
           self.getIndex(objtype, objid) == None:
          raise ValueError( "block or set id " + str(objid) + " not found" )
        if objtype != EX_GLOBAL and objtype != EX_NODE and \
           not self.variableStored(objtype, objid, var_index):
          raise ValueError( "variable index " + str(var_index) + \
                            " not stored on block/set id " + str(objid) )
        if objtype == EX_GLOBAL and len(values) < len(self.vars[EX_GLOBAL]):
          raise ValueError( "values array must have length at least " + \
                            "as big as the number of global variables" )
        if objtype == EX_NODE and len(values) < self.num[EX_NODE]:
          raise ValueError( "values array must have length at least " + \
                            "as big as the number of nodes" )
        if objtype != EX_GLOBAL and objtype != EX_NODE and \
           len(values) < self.getCount(objtype,objid):
          raise ValueError( "values array must have length at least " + \
                            "as big as the number of objects in the set/block" )
        
        if   objtype == EX_GLOBAL:
          exomod.exm_put_glob_vars( self.exoid, time_step,
                                    len(self.vars[EX_GLOBAL]), values )
        elif objtype == EX_NODE:
          exomod.exm_put_nodal_var( self.exoid, time_step, var_index+1,
                                    self.num[EX_NODE], values )
        else:
          exomod.exm_put_var( self.exoid, time_step, objtype, var_index+1,
                              objid, self.getCount(objtype,objid), values )
    
    ########## internal implementation:
    
    def _reset(self):
        self.parlist = None
        self.filename = None
        self.exoid = None      # integer exodus id
        self.storage_type = None    # data type stored in file, 'f' or 'd'
        self.db_version = 0.0  # floating point file database version number
        self.title = ""
        self.ndim = 0      # num spatial dimensions
        self.coornames = None
        
        # each of these contain enough entries to be indexed by the objtype
        # enum values;  self.num is indexed by objtype, self.idmap by objtype;
        # self.meta first by objtype, then by block/set/map index, then by meta
        # tuple index
        self.num = [0]      # num nodes/edges/faces/elems, blocks, sets and maps
        self.idmap = [{}]   # maps block/set/map ids to indexes
        self.meta = [[]]    # each entry is a list of block/set/map tuples;
                            # block tuple: ( id, count, type name, nodes per,
                            #                edges per, faces per, num attr )
                            # set tuple: ( id, count, num dist factors )
                            # map tuple: ( id, count )
        self.vars = [[]]    # each entry is a list of variable names
        self.var_tt = [[]]  # each entry is matrix of true/false values which
                            # is indexed first by the variable index then by
                            # the block or set index
        for i in range(max_type_index):
          self.num.append(0)
          self.idmap.append({})
          self.meta.append([])
          self.vars.append([])
          self.var_tt.append([])
        
        self.qa_records = []  # list of 4-tuples, one for each QA record
        
        self.times = []  # time slice values (time step values); doubles
        
        self.inq_cnts = array.array('i')
        resize_array( self.inq_cnts, 41 )
        for i in xrange(41):
          self.inq_cnts[i] = 0
    
    def _open_file(self, filename, mode):
        assert mode == EX_READ or mode == EX_WRITE
        
        if self.exoid != None: self.closefile()
        self._reset()
        
        fwsa = array.array('i',[0])
        va = array.array('f',[0.0])
        xa = array.array('i',[0])
        exomod.exm_open( filename, mode, 0, fwsa, va, xa )
        iows = fwsa[0]
        assert iows == 4 or iows == 8
        dbv = va[0]
        self.exoid = xa[0]
        
        self.filename = filename
        self.storage_type = 'f'
        if iows == 8:
          self.storage_type = 'd'
        self.db_version = float( int(dbv*10000+0.5) )/10000;
        
        ta = array.array('c') ; resize_array( ta, MAX_LINE_LENGTH+1 )
        ca = array.array('i',[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
        exomod.exm_get_init( self.exoid, ta, ca )
        self.title              = string.rstrip( ta.tostring(), '\0' )
        self.ndim               = ca[ 0]
        self.num[EX_NODE]       = ca[ 1]
        self.num[EX_EDGE]       = ca[ 2]
        self.num[EX_EDGE_BLOCK] = ca[ 3]
        self.num[EX_FACE]       = ca[ 4]
        self.num[EX_FACE_BLOCK] = ca[ 5]
        self.num[EX_ELEM]       = ca[ 6]
        self.num[EX_ELEM_BLOCK] = ca[ 7]
        self.num[EX_NODE_SET]   = ca[ 8]
        self.num[EX_EDGE_SET]   = ca[ 9]
        self.num[EX_FACE_SET]   = ca[10]
        self.num[EX_SIDE_SET]   = ca[11]
        self.num[EX_ELEM_SET]   = ca[12]
        self.num[EX_NODE_MAP]   = ca[13]
        self.num[EX_EDGE_MAP]   = ca[14]
        self.num[EX_FACE_MAP]   = ca[15]
        self.num[EX_ELEM_MAP]   = ca[16]
        
        exomod.exm_inquire_counts( self.exoid, self.inq_cnts )
        
        for i in [EX_EDGE_BLOCK,EX_FACE_BLOCK,EX_ELEM_BLOCK]:
          if self.num[i] > 0:
            self._fill_blocks( i, self.meta[i], self.num[i], self.idmap[i] )
        
        for i in [EX_NODE_SET,EX_EDGE_SET,EX_FACE_SET,EX_ELEM_SET,EX_SIDE_SET]:
          if self.num[i] > 0:
            self._fill_sets( i, self.meta[i], self.num[i], self.idmap[i] )
        
        for i in [EX_NODE_MAP,EX_EDGE_MAP,EX_FACE_MAP,EX_ELEM_MAP]:
          if self.num[i] > 0:
            self._fill_maps( i, self.meta[i], self.num[i], self.idmap[i] )
        
        self.qa_records = []
        nrec = self.inq_cnts[9]
        if nrec > 0:
          a = array.array('c')
          resize_array( a, 4*nrec*(MAX_STR_LENGTH+1) )
          exomod.exm_get_qa( self.exoid, nrec, a )
          k = 0
          for i in xrange(nrec):
            s0 = a[k:k+MAX_STR_LENGTH+1].tostring()
            s0 = string.rstrip( s0, '\0' )
            k = k + MAX_STR_LENGTH + 1
            s1 = a[k:k+MAX_STR_LENGTH+1].tostring()
            s1 = string.rstrip( s1, '\0' )
            k = k + MAX_STR_LENGTH + 1
            s2 = a[k:k+MAX_STR_LENGTH+1].tostring()
            s2 = string.rstrip( s2, '\0' )
            k = k + MAX_STR_LENGTH + 1
            s3 = a[k:k+MAX_STR_LENGTH+1].tostring()
            s3 = string.rstrip( s3, '\0' )
            k = k + MAX_STR_LENGTH + 1
            self.qa_records.append( (s0,s1,s2,s3) )
        
        ra = array.array( self.storage_type )
        ntime = self.inq_cnts[11]  # slot 11 is number of time steps
        if ntime > 0:
          resize_array( ra, ntime )
          exomod.exm_get_all_times( self.exoid, ra )
          for i in range(ntime):
            self.times.append( ra[i] )
        
        nvars = array.array('i',[0,0,0,0,0,0,0,0,0,0])
        exomod.exm_get_var_params( self.exoid, nvars )
        slen = MAX_STR_LENGTH+1
        aL = []
        for i in xrange(10):
          a = array.array('c') ; resize_array( a, nvars[i]*slen )
          aL.append( a )
        exomod.exm_get_all_var_names( self.exoid, aL[0], aL[1], aL[2],
                                       aL[3], aL[4], aL[5], aL[6], aL[7],
                                       aL[8], aL[9] )
        L = [nvars[0],nvars[1],nvars[2],nvars[3],nvars[4],nvars[5],
             nvars[6],nvars[7],nvars[8],nvars[9]]
        j = 0
        for i in [EX_GLOBAL,EX_NODE,EX_EDGE_BLOCK,EX_FACE_BLOCK,EX_ELEM_BLOCK, \
                  EX_NODE_SET,EX_EDGE_SET,EX_FACE_SET,EX_ELEM_SET,EX_SIDE_SET]:
          self._fill_vars( L[j], self.vars[i], aL[j].tostring() )
          j = j + 1
        
        for i in [EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_ELEM_BLOCK,EX_NODE_SET, \
                  EX_EDGE_SET, EX_FACE_SET, EX_ELEM_SET, EX_SIDE_SET ]:
          self._fill_truthtab( i, len(self.vars[i]),
                               self.num[i], self.var_tt[i] )
        
        self.coornames = None
        if self.ndim > 0 and self.ndim <= 3:
          ca = array.array('c')
          resize_array( ca, self.ndim * (MAX_STR_LENGTH+1) )
          exomod.exm_get_coord_names( self.exoid, self.ndim, ca )
          s = string.rstrip( ca[:MAX_STR_LENGTH+1].tostring(), '\0' )
          if s != "_not_stored_":
            self.coornames = [s]
            if self.ndim > 1:
              s = ca[MAX_STR_LENGTH+1:2*(MAX_STR_LENGTH+1)].tostring()
              self.coornames.append( string.strip(s,'\0') )
            if self.ndim > 2:
              s = ca[2*(MAX_STR_LENGTH+1):].tostring()
              self.coornames.append( string.rstrip(s,'\0') )
    
    def _fill_blocks(self, btype, blist, numblocks, idmap):
        ids = array.array('i')
        resize_array( ids, numblocks )
        exomod.exm_get_ids( self.exoid, btype, ids )
        for i in range(numblocks):
          idmap[ ids[i] ] = i
          t = array.array('c') ; resize_array( t, MAX_STR_LENGTH+1 )
          L = array.array('i',[0,0,0,0,0])
          exomod.exm_get_block( self.exoid, btype, ids[i], t, L )
          t = string.strip( string.rstrip( t.tostring(), '\0' ) )
          blist.append( (ids[i], L[0], t, L[1], L[2], L[3], L[4]) )
    
    def _fill_sets(self, stype, slist, numsets, idmap):
        ids = array.array('i')
        resize_array( ids, numsets )
        exomod.exm_get_ids( self.exoid, stype, ids )
        for i in range(numsets):
          idmap[ ids[i] ] = i
          na = array.array('i',[0])
          nda = array.array('i',[0] )
          exomod.exm_get_set_param( self.exoid, stype, ids[i], na, nda )
          if nda[0] < 0:
            nda[0] = 0
          slist.append( (ids[i], na[0], nda[0]) )
    
    def _fill_maps(self, mtype, mlist, nummaps, idmap):
        ids = array.array('i')
        resize_array( ids, nummaps )
        exomod.exm_get_ids( self.exoid, mtype, ids )
        for i in range(nummaps):
          idmap[ ids[i] ] = i
          if   mtype == EX_NODE_MAP: cnt = self.num[EX_NODE]
          elif mtype == EX_EDGE_MAP: cnt = self.num[EX_EDGE]
          elif mtype == EX_FACE_MAP: cnt = self.num[EX_FACE]
          else:                      cnt = self.num[EX_ELEM]
          mlist.append( (ids[i], cnt) )
    
    def _fill_vars(self, cnt, vlist, buf):
        k = 0
        for i in xrange(cnt):
          vlist.append( string.rstrip( buf[k:k+MAX_STR_LENGTH+1], '\0' ) )
          k = k + MAX_STR_LENGTH+1
    
    def _fill_truthtab(self, vartype, nvars, nids, tt):
        if nvars > 0:
          if nids == 0:
            for i in range(nvars):
              tt.append( [] )
          else:
            assert nids > 0
            ia = array.array('i')
            resize_array( ia, nvars*nids )
            exomod.exm_get_truth_table(self.exoid, vartype, nids, nvars, ia)
            for v in range(nvars):
              L = []
              for i in range(nids):
                L.append( ia[ i*nvars + v ] )
              tt.append(L)
    
    def _block2str(self, num, L, name):
        assert num == len(L)
        s = ''
        for i in range(num):
          bL = L[i]
          if i == 0: s = s + '\n' + name + ' blocks:'
          else:      s = s + '\n            '
          s = s + ' id ' + str(bL[0]) + \
                  ' type ' + bL[2] + \
                  ' count ' + str(bL[1]) + \
                  ' nnodes ' + str(bL[3]) + \
                  ' nedges ' + str(bL[4]) + \
                  ' nfaces ' + str(bL[5]) + \
                  ' nattrs ' + str(bL[6])
        return s
    
    def _set2str(self, num, L, name):
        assert num == len(L)
        s = ''
        for i in range(num):
          sid, cnt, ndist = L[i]
          if i == 0: s = s + '\n' + name + ' sets:'
          else:      s = s + '\n          '
          s = s + ' id '+str(sid) + ' count '+str(cnt) + ' ndist '+str(ndist)
        return s
    
    def _varL2str(self, L, name):
        s = ''
        for i in range(len(L)):
          if i == 0: s = s + '\n' + name + ': ' + str(i+1) + ') ' + L[i]
          else:      s = s + '\n         ' + str(i+1) + ') ' + L[i]
        return s
    
    def _process_parlist(self):
        """
        """
        assert len(self.parlist) > 0
        
        self.title = ''
        self.storage_type = self.parlist[0].storage_type
        self.ndim = self.parlist[0].ndim
        for i in range(max_type_index):
          self.num[i] = self.parlist[0].num[i]
        self.num[EX_NODE] = 0
        self.num[EX_EDGE] = 0
        self.num[EX_FACE] = 0
        self.num[EX_ELEM] = 0
        self.idmap = self.parlist[0].idmap
        
        # need to copy the meta data because the total counts need adjustment
        self.meta = []
        for L in self.parlist[0].meta:
          newL = []
          for L2 in L:
            newL2 = []
            for T in L2:
              newL2.append(T)  # this references the tuple, which is immutable
            newL.append( newL2 )
          self.meta.append( newL )
        
        # block information may not be contained in some of the parallel files;
        # use "NULL" element type as an indicator
        for exof in self.parlist:
          for t in [EX_EDGE_BLOCK, EX_FACE_BLOCK, EX_ELEM_BLOCK]:
            for bid in exof.getIds(t):
              T = exof.getBlock(t,bid)
              if T[2] != "" and T[2] != "NULL":
                self.meta[t][ exof.getIndex(t,bid) ] = T
        
        self.vars       = self.parlist[0].vars
        self.var_tt     = self.parlist[0].var_tt
        self.qa_records = []
        self.times      = self.parlist[0].times
        
        # collect unique global ids for each type
        maps = {}
        for t in [EX_NODE, EX_EDGE, EX_FACE, EX_ELEM]:
          maps[t] = {}
        
        # collect unique global ids for each block id
        blockmaps = {}
        for t in [EX_ELEM_BLOCK, EX_EDGE_BLOCK, EX_FACE_BLOCK]:
          blockmaps[t] = {}
          for bid in self.parlist[0].getIds(t):
            blockmaps[t][bid] = {}
        
        # collect unique global ids in each set
        setmaps = {}
        setdist = {}
        for t in [EX_NODE_SET,EX_SIDE_SET,EX_EDGE_SET,EX_FACE_SET,EX_ELEM_SET]:
          setmaps[t] = {}
          setdist[t] = {}
          for sid in self.parlist[0].getIds(t):
            setmaps[t][sid] = {}
            setdist[t][sid] = 0
        
        for exof in self.parlist:
          
          if len(self.title) < len(exof.title):
            self.title = exof.title
          
          if exof.storage_type != self.storage_type:
            raise Exception( "floating point storage types are not " + \
                             "consistent across parallel files" )
          
          if exof.ndim != self.ndim:
            raise Exception( "spatial dimension is not " + \
                             "consistent across parallel files" )
          
          for t in [ EX_ELEM_BLOCK, EX_NODE_SET, EX_SIDE_SET, EX_ELEM_MAP, \
                     EX_NODE_MAP, EX_EDGE_BLOCK, EX_EDGE_SET, EX_FACE_BLOCK, \
                     EX_FACE_SET, EX_ELEM_SET, EX_EDGE_MAP, EX_FACE_MAP, \
                     EX_GLOBAL ]:
            if exof.num[t] != self.num[t]:
              raise Exception( "number of " + type_map[t] + " are not " + \
                               "consistent across parallel files" )
          
          # use the qa records from the file that has the most
          if len(self.qa_records) < len(exof.qa_records):
            self.qa_records = exof.qa_records
          
          if len(self.times) != len(exof.times):
            raise Exception( "number of time steps are not " + \
                             "consistent across parallel files: " + \
                     str(len(self.times)) + " != " + str(len(exof.times)) )
          
          # read and store the local to global map for each file
          exof.l2g = {}
          exof.l2g[EX_NODE] = exof.readMap( EX_NODE_MAP, -1 )
          exof.l2g[EX_EDGE] = exof.readMap( EX_EDGE_MAP, -1 )
          exof.l2g[EX_FACE] = exof.readMap( EX_FACE_MAP, -1 )
          exof.l2g[EX_ELEM] = exof.readMap( EX_ELEM_MAP, -1 )
          
          # accumulate the unique global ids for each type
          for t in [EX_NODE, EX_EDGE, EX_FACE, EX_ELEM]:
            i = 0
            while i < len(exof.l2g[t]):
              maps[t][ exof.l2g[t][i] ] = None
              i = i + 1
          
          # accumulate the unique global ids in each block
          exof.blockoff = {}
          for tb,t in [ (EX_ELEM_BLOCK, EX_ELEM),
                        (EX_EDGE_BLOCK, EX_EDGE),
                        (EX_FACE_BLOCK, EX_FACE) ]:
            exof.blockoff[tb] = {}
            e = 0
            for (bid,cnt,typename,n_per,g_per,f_per,nattr) in exof.meta[tb]:
              i = 0
              while i < cnt:
                blockmaps[tb][bid][ exof.l2g[t][e+i] ] = None
                i = i + 1
              exof.blockoff[tb][bid] = e  # the elem offset for each block
              e = e + cnt
          
          # accumulate the unique global ids in each set
          for t,to in [ (EX_NODE_SET, EX_NODE),
                        (EX_SIDE_SET, EX_ELEM),
                        (EX_EDGE_SET, EX_EDGE),
                        (EX_FACE_SET, EX_FACE),
                        (EX_ELEM_SET, EX_ELEM) ]:
            for sid in exof.getIds(t):
              d1,cnt,ndist = exof.getSet(t,sid)
              if cnt > 0 and ndist > 0:
                assert ndist % cnt == 0
                setdist[t][sid] = ndist/cnt
              set,aux = exof.readSet(t,sid)
              l2g = exof.l2g[to]
              n = len(set)
              i = 0
              if t in [EX_NODE_SET,EX_ELEM_SET]:
                while i < n:
                  setmaps[t][sid][ l2g[ set[i] ] ] = None
                  i = i + 1
              else:
                while i < n:
                  p = ( l2g[ set[i] ], aux[i] )
                  setmaps[t][sid][ p ] = None
                  i = i + 1
        
        # these map total local indexes to global numbers
        self.gids = {}
        for t in [EX_NODE, EX_EDGE, EX_FACE, EX_ELEM]:
          self.gids[t] = maps[t].keys()
          self.gids[t].sort()
          self.num[t] = len(self.gids[t])  # also set the total count here
        maps = None
        
        # compute map from global numbers to total local indexes
        self.g2l = {}
        for t in [EX_NODE, EX_EDGE, EX_FACE, EX_ELEM]:
          self.g2l[t] = {}
          i = 0
          while i < len(self.gids[t]):
            self.g2l[t][ self.gids[t][i] ] = i
            i = i + 1
        
        # set block counts and store block local index offsets
        self.blockoff = {}
        for tb in [EX_ELEM_BLOCK, EX_EDGE_BLOCK, EX_FACE_BLOCK]:
          self.blockoff[tb] = {}
          off = 0
          for i in range(len(self.meta[tb])):
            T = self.meta[tb][i]
            bid = T[0]
            newcnt = len(blockmaps[tb][bid])
            self.meta[tb][i] = (T[0],newcnt,T[2],T[3],T[4],T[5],T[6])
            self.blockoff[tb][bid] = off
            off = off + newcnt
        blockmaps = None
        
        # do the set counts and keep a map of set global ids to set indexes
        self.setg2l = {}
        for t in [EX_NODE_SET, EX_SIDE_SET,EX_EDGE_SET,EX_FACE_SET,EX_ELEM_SET]:
          self.setg2l[t] = {}
          for i in range(len(self.meta[t])):
            T = self.meta[t][i]
            sid = T[0]
            newcnt = len(setmaps[t][sid])
            ndist = setdist[t][sid] * newcnt
            self.meta[t][i] = (T[0],newcnt,ndist)
            L = setmaps[t][sid].keys()
            L.sort()
            D = {}
            for i in xrange(len(L)):
              D[L[i]] = i
            self.setg2l[t][sid] = D
            L = None
        setmaps = None
        setdist = None
        
        # set map counts
        for t,to in [ (EX_ELEM_MAP, EX_ELEM),
                      (EX_NODE_MAP, EX_NODE),
                      (EX_EDGE_MAP, EX_EDGE),
                      (EX_FACE_MAP, EX_FACE) ]:
          for i in range(len(self.meta[t])):
            T = self.meta[t][i]
            self.meta[t][i] = ( T[0], self.num[to] )
    
    def __str__(self):
        s = "Title:           " + self.title + '\n' + \
            "Storage:         " + self.storage_type + '\n' + \
            "Dimension:       " + str(self.ndim) + '\n' + \
            "Num nodes:       " + str(self.num[EX_NODE]) + '\n' + \
            "Num edges:       " + str(self.num[EX_EDGE]) + '\n' + \
            "Num faces:       " + str(self.num[EX_FACE]) + '\n' + \
            "Num elems:       " + str(self.num[EX_ELEM]) + '\n' + \
            "Num edge blocks: " + str(self.num[EX_EDGE_BLOCK]) + '\n' + \
            "Num face blocks: " + str(self.num[EX_FACE_BLOCK]) + '\n' + \
            "Num elem blocks: " + str(self.num[EX_ELEM_BLOCK]) + '\n' + \
            "Num node sets:   " + str(self.num[EX_NODE_SET]) + '\n' + \
            "Num edge sets:   " + str(self.num[EX_EDGE_SET]) + '\n' + \
            "Num face sets:   " + str(self.num[EX_FACE_SET]) + '\n' + \
            "Num elem sets:   " + str(self.num[EX_ELEM_SET]) + '\n' + \
            "Num side sets:   " + str(self.num[EX_SIDE_SET])
        for (i,nm) in [ (EX_EDGE_BLOCK,"Edge"),(EX_FACE_BLOCK,"Face"), \
                        (EX_ELEM_BLOCK,"Elem") ]:
          if self.num[i] > 0:
            s = s + self._block2str( self.num[i], self.meta[i], nm )
        
        for (i,nm) in [ (EX_NODE_SET,"Node"), (EX_EDGE_SET,"Edge"), \
                        (EX_FACE_SET,"Face"), (EX_ELEM_SET,"Elem"), \
                        (EX_SIDE_SET,"Side") ]:
          if self.num[i] > 0:
            s = s + self._set2str( self.num[i], self.meta[i], nm )
        
        if len(self.times) > 0:
          s = s + '\nTimes: num ' + str(len(self.times)) + \
                  " first " + ('%.1g' % self.times[0]) + \
                  " last " + ('%.1g' % self.times[-1])
        
        for (i,nm) in [ (EX_GLOBAL,"Globals"),(EX_NODE,"Nodals "), \
                        (EX_EDGE_BLOCK,"Edge   "),(EX_FACE_BLOCK,"Face   "), \
                        (EX_ELEM_BLOCK,"Element"),(EX_NODE_SET,"Node Set"), \
                        (EX_EDGE_SET,"Edge Set"),(EX_FACE_SET,"Face Set"), \
                        (EX_ELEM_SET,"Elem Set"),(EX_SIDE_SET,"Side Set") ]:
          if len(self.vars[i]) > 0:
            s = s + self._varL2str( self.vars[i], nm )
        
        return s
    
    def __del__(self):
        """
        This function is called when an ExodusFile object is garbage collected.
        To avoid open files, we make sure this one is closed.
        """
        if self.exoid != None:
          self.save_exomod.exm_close( self.exoid )
          self.exoid = None


# compute max value of all the object types
max_type_index = 0
for i in [ EX_ELEM_BLOCK, EX_NODE_SET, EX_SIDE_SET, EX_ELEM_MAP, EX_NODE_MAP, \
           EX_EDGE_BLOCK, EX_EDGE_SET, EX_FACE_BLOCK, EX_FACE_SET, \
           EX_ELEM_SET, EX_EDGE_MAP, EX_FACE_MAP, EX_GLOBAL, \
           EX_NODE, EX_EDGE, EX_FACE, EX_ELEM ]:
  assert i >= 0
  if i > max_type_index: max_type_index = i


type_map = {}
type_map[EX_ELEM_BLOCK] = 'EX_ELEM_BLOCK'
type_map[EX_NODE_SET]   = 'EX_NODE_SET'
type_map[EX_SIDE_SET]   = 'EX_SIDE_SET'
type_map[EX_ELEM_MAP]   = 'EX_ELEM_MAP'
type_map[EX_NODE_MAP]   = 'EX_NODE_MAP'
type_map[EX_EDGE_BLOCK] = 'EX_EDGE_BLOCK'
type_map[EX_EDGE_SET]   = 'EX_EDGE_SET'
type_map[EX_FACE_BLOCK] = 'EX_FACE_BLOCK'
type_map[EX_FACE_SET]   = 'EX_FACE_SET'
type_map[EX_ELEM_SET]   = 'EX_ELEM_SET'
type_map[EX_EDGE_MAP]   = 'EX_EDGE_MAP'
type_map[EX_FACE_MAP]   = 'EX_FACE_MAP'
type_map[EX_GLOBAL]     = 'EX_GLOBAL'
type_map[EX_NODE]       = 'EX_NODE'
type_map[EX_EDGE]       = 'EX_EDGE'
type_map[EX_FACE]       = 'EX_FACE'
type_map[EX_ELEM]       = 'EX_ELEM'


def resize_array( ar, newlength ):
    """
    Sizes the given array to the given length.  It exploits coding in the
    array repeat operator to allocate the data array at one time then
    initialize the items to some value.
    
    The repeat operator coding is essentially
    
        newarray = malloc( repeat_length * current_length );
        for ( i = 0; i < repeat_length; ++i )
            memcpy( newarray+offset, current_data, current_length );
            offset += current_length
    
    so the allocation happens all at once then each item is memcopied.
    """
    assert type(ar) == array.ArrayType
    if newlength <= 0:
      if len(ar) > 0:
        del ar[0:]
    else:
      if len(ar) < newlength:
        if len(ar) > 1:
          del ar[1:]
        elif len(ar) == 0:
          if   ar.typecode in ['c','u']: ar.append(' ')
          elif ar.typecode in ['f','d']: ar.append(0.0)
          else:                          ar.append(0)
        if newlength > 1:
          try:
            # in-place repeat operator appeared in python 2.0
            ar *= newlength
          except:
            # not as memory efficient, but exploit the string.center method
            # to allocate a string then copy its memory onto the array
            s = string.center( '', (length-1) * a.itemsize, '\0' )
            a.fromstring(s)
            s = ''
      elif len(ar) > newlength:
        del ar[newlength:]


#############################################################################

#def tfunc( frame, event, arg ):
#  fname = frame.f_code.co_filename
#  if event == 'call' and sys.prefix != fname[:len(sys.prefix)]:
#    print fname + ':' + str(frame.f_lineno), frame.f_code.co_name + '()'
#sys.settrace(tfunc)

if __name__ == "__main__":
  
  exof = ExodusFile( "noh.exo" )
  T = exof.getCoordNames()
  print "coord names", T
  exof.closefile()
  #exof.parallelRead( sys.argv[1:] )
  #for t in [EX_ELEM_BLOCK,EX_FACE_BLOCK,EX_EDGE_BLOCK]:
  #  nameL = exof.varNames(t)
  #  for i in range(len(nameL)):
  #    print "var", i, nameL[i]
  #    vals = array.array( exof.storageType() )
  #    for bid in exof.getIds(t):
  #      vals = vals + exof.readVar( -1, t, bid, i )
  #    vals2 = exof.readBlockVar( -1, t, i )
  #    assert len(vals) == len(vals2)
  #    for i in range(len(vals)):
  #      assert vals[i] == vals2[i]
