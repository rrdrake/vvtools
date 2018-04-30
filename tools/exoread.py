#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import string
import array
import types

version = 0.4

help_string = """
NAME
      exoread.py - exodus file reader helper, version """ + str(version) + """

SYNOPSIS
      exoread.py [OPTIONS] <filename>
      
DESCRIPTION
      The command line mode for 'exoread.py' extracts specified variable
      values from a given file name and writes them to stdout in tabular
      form.  If no variables are selected, then the file meta data is
      written instead.
      
      Default for global variables is to write out the values for all times.
      
      Default for spatial variables is to write out the values for each object
      for the last time slab.
      
      Special nodal variable names are the geometry coordinates, "COORDINATES",
      and the motion displacements, "DISPLACEMENTS".  When you ask for one of
      them, you get each component of the vector.

OPTIONS
      -h, --help
           Print man page then exit.
      -V, --version
           Print version number and exit.
      -g, --global <variable name>
           Select a mesh global variable name to extract.
      -e, --element <variable name>
           Select a mesh element variable name to extract.
      -f, --face <variable name>
           Select a mesh face variable name to extract.
      -d, --edge <variable name>
           Select a mesh edge variable name to extract.
      -n, --node <variable name>
           Select a mesh node variable name to extract.
      -t, --time <float>
           Output the variable at this time.  Closest time value is chosen.
      -i, --index <integer>
           Output the variable at this time step index.  A value of -1 means
           the last time step in the file.  Note that exodus time steps start
           at one, while this starts at zero.
      -c, --cycle <integer>
           Output the variable at this cycle number.  Numbers start at zero.
           A value of -1 means the last time step in the file.
      --object-index
           For non-global variables, include the object index in the output.
      -L, --lineout {x|X|<real>}/{y|Y|<real>}/{z|Z|<real>}[/T<real tolerance>]
           Restrict the nodes/elements/edges/faces to those whose coordinates
           are along a line parallel to an axis.  Use lower case x/y/z for
           original or material coordinates and upper case for displaced or
           Lagrangian coordinates.  In 2D, both an X and a Y entry are
           required and for 3D, a Z entry.  So "x/1.0" in 2D would be a
           lineout along x with y=1.0, while "2.0/y" would be a lineout in y
           with x=2.0.  The last number with a "T" in front is an optional
           tolerance used in selecting the coordinate locations.  A 3D example
           is "1.0/Y/3.0/T0.1" which is a lineout in y using displaced
           coordinates with x in the range (0.9,1.1) and z in (2.9,3.1).
      --nolabels
           Do not write the variable names and units to the output.
      
TODO
      Add time step skipping.
      Handle multiple files.
      Maybe add other output formats, like CSV or XMGR.
"""

# add directories to import path to help find the exodus.py module
sys.path.append( os.path.dirname(sys.argv[0]) )
sys.path.extend( string.split(os.environ.get('PATH',''),':') )
import exodus


def meta_data( filename ):
    """
    Writes out the number of objects and the variable names for the file.
    """
    exof = exodus.ExodusFile( filename )
    
    print "Title:", exof.getTitle()
    
    if exof.storageType() == 'f': print "Storage type: float"
    else:                         print "Storage type: double"
    
    print "Num info strings:", len(exof.getInfo())
    print "Dimension:", exof.getDimension()
    
    print "Num nodes   :", exof.getNumber(exodus.EX_NODE)
    print "Num edges   :", exof.getNumber(exodus.EX_EDGE)
    print "Num faces   :", exof.getNumber(exodus.EX_FACE)
    print "Num elements:", exof.getNumber(exodus.EX_ELEM)
    
    for t,s in [(exodus.EX_ELEM_BLOCK,'Elem blocks'),
                (exodus.EX_FACE_BLOCK,'Face blocks'),
                (exodus.EX_EDGE_BLOCK,'Edge blocks'),
                (exodus.EX_NODE_SET,'Node sets'),
                (exodus.EX_SIDE_SET,'Side sets'),
                (exodus.EX_EDGE_SET,'Edge sets'),
                (exodus.EX_FACE_SET,'Face sets'),
                (exodus.EX_ELEM_SET,'Elem sets')]:
      L = exof.getIds(t)
      if len(L) == 0:
        print s+':', len(L)
      else:
        print s+':', len(L), "Ids =", string.join( map(lambda x: str(x), L) )
    
    for t,s in [(exodus.EX_GLOBAL,'Global vars'),
                (exodus.EX_ELEM,'Elem vars'),
                (exodus.EX_FACE,'Face vars'),
                (exodus.EX_EDGE,'Edge vars'),
                (exodus.EX_NODE,'Node vars'),
                (exodus.EX_NODE_SET,'Node set vars'),
                (exodus.EX_SIDE_SET,'Side set vars'),
                (exodus.EX_EDGE_SET,'Edge set vars'),
                (exodus.EX_FACE_SET,'Face set vars'),
                (exodus.EX_ELEM_SET,'Elem set vars')]:
      L = exof.varNames(t)
      print s+':', len(L)
      if len(L) > 0:
        for i in range(len(L)):
          print "  ", i, L[i]
    
    L = exof.getTimes()
    print 'Time steps:', len(L)
    if len(L) > 0:
      for i in range(len(L)):
        print "  ", (i+1), L[i]


#########################################################################

def extract_data( vartype, varL, exofile, t_opt, i_opt, c_opt, add_index=0 ):
    """
    Finds the variables in the file and returns the values in a list of rows,
    where each row is a list of values.  The first row contains the labels.
      
      vartype: 'g'=global, 'e'=element, 'f'=face, 'd'=edge, 'n'=node
      varL:    a list of variable names of type 'vartype'
      t_opt:   if not None, specifies the time slab to extract from the file
      i_opt:   if not None, specifies the output index to extract
      c_opt:   if not None, specifies the output cycle to extract
    
    The 'exofile' argument is either a filename or an open exodus.ExodusFile
    instance.  Two special variable names:
    
      'coordinates': reads the nodal coordinates for type 'n' or computes the
                     centers for types 'e', 'f', and 'd'
      'displacements': reads the nodal displacements for type 'n' or computes
                       the average dislacements for types 'e', 'f', and 'd'
    
    Returns a list of
      
      [ time, value1, value2, ... ]
    
    for global variables, or
      
      [ index, value1, value2, ... ]
    
    for spatial variables.  The 'index' is the element/node/edge/face object
    index and will be an integer.  However, if the 'add_index' argument is
    false, then the index is not included as the first column.  Each value
    corresponds to the variable name given in 'varL' (in order.) Note that
    the very first line entry will be the labels for the columns of data.
    """
    if isinstance( exofile, exodus.ExodusFile ):
      closefile = 0
      exof = exofile
    else:
      exof = exodus.ExodusFile( exofile )
      closefile = 1
    
    lineL = []
    
    try:
      
      exotype = vartype_map[vartype]
      
      idxL  = []  # index list
      idxD  = {}  # for special variables; maps negative markers to indexes
      nameL = []  # variable name list (as stored in the file)
      
      nL = exof.varNames(exotype)
      for n in varL:
        
        if vartype != 'g' and name_compare( n, "coordinates" ):
          if exof.getDimension() > 0:
            idxL.append(-1)
            nameL.append("COORDX")
          if exof.getDimension() > 1:
            idxL.append(-2)
            nameL.append("COORDY")
          if exof.getDimension() > 2:
            idxL.append(-3)
            nameL.append("COORDZ")
        
        elif vartype != 'g' and name_compare( n, "displacements" ):
          L1,L2 = displacement_indexes( exof )
          if L1 == None:
            print "*** error: could not determine displacement variables"
            if closefile: exof.closefile()
            return None
          idxL.append(-4) ; idxD[-4] = L1[0]
          if exof.getDimension() > 1:
            idxL.append(-5) ; idxD[-5] = L1[1]
          if exof.getDimension() > 2:
            idxL.append(-6) ; idxD[-6] = L1[2]
          nameL.extend( L2 )
        
        else:
          i = name_search( n, nL )
          if i == None:
            print '*** error: variable name "' + n + '" not found'
            if closefile: exof.closefile()
            return None
          idxL.append( i )
          nameL.append( nL[i] )
      
      tL = exof.getTimes()
      
      if len(tL) == 0:
        print "*** error: no time steps found in file"
        if closefile: exof.closefile()
        return None
      
      vals = None
      
      # process a specific time slab specification, if given
      ival = None
      if t_opt != None:
        ival = time_search( t_opt, tL )
      elif i_opt != None:
        ival = i_opt
        if ival < 0: ival = len(tL)-1
        elif ival >= len(tL): ival = len(tL)-1
      elif c_opt != None:
        ival = cycle_search( int(c_opt+0.5), exof )
        if ival == None:
          print "*** error: could not find cycle number", c_opt
          if closefile: exof.closefile()
          return None
      
      if vartype == 'g':
        
        lineL.append( ["Time"] + nameL )
        
        if ival == None:
          for i in range(len(tL)):
            tstep = i + 1
            L = [ tL[i] ]
            vals = exof.readVar( tstep, exotype, 0, 0, vals )
            for vi in idxL:
              L.append( vals[vi] )
            lineL.append( L )
        
        else:
          L = [ tL[ival] ]
          vals = exof.readVar( ival+1, exotype, 0, 0, vals )
          for vi in idxL:
            L.append( vals[vi] )
          lineL.append( L )
      
      else:
        
        # if no time slab specified, select the last one
        if ival == None:
          ival = len(tL)-1
        
        if add_index:
          lineL.append( ["index"] + nameL )
        else:
          lineL.append( nameL )
        
        if vartype == 'n':
          
          coords = None
          dataL = []
          for vi in idxL:
            if vi in [-1,-2,-3]:
              if coords == None:
                coords = exof.readCoords()
              if   vi == -1: vals = coords[0]
              elif vi == -2: vals = coords[1]
              elif vi == -3: vals = coords[2]
            elif vi in [-4,-5,-6]:  # displacements
              vals = exof.readVar( ival+1, exotype, 0, idxD[vi] )
            else:
              vals = exof.readVar( ival+1, exotype, 0, vi )
            dataL.append(vals)
            nrows = len(vals)
          
        else:
          
          cntrs = None
          displ = None
          dataL = []
          for vi in idxL:
            
            if vi in [-1,-2,-3]:
              if cntrs == None:
                cntrs = exof.computeCenters( exotype, None )
              if   vi == -1: vals = cntrs[0]
              elif vi == -2: vals = cntrs[1]
              elif vi == -3: vals = cntrs[2]
            
            elif vi in [-4,-5,-6]:  # displacements
              if displ == None:
                dx = exof.readVar( ival+1, exodus.EX_NODE, 0, idxD[-4] )
                ndispL = [dx]
                if exof.getDimension() > 1:
                  dy = exof.readVar( ival+1, exodus.EX_NODE, 0, idxD[-5] )
                  ndispL.append( dy )
                if exof.getDimension() > 2:
                  dz = exof.readVar( ival+1, exodus.EX_NODE, 0, idxD[-6] )
                  ndispL.append( dz )
                displ = exof.computeCenters( exotype, None, ndispL )
              if   vi == -4: vals = displ[0]
              elif vi == -5: vals = displ[1]
              elif vi == -6: vals = displ[2]
            
            else:
              vals = exof.readVar( ival+1, exotype, None, vi )
            
            dataL.append(vals)
            nrows = len(vals)
          
        for i in xrange(nrows):
          if add_index: L = [ i ]
          else:         L = []
          for j in xrange(len(idxL)):
            L.append( dataL[j][i] )
          lineL.append( L )
  
    except:
      if closefile: exof.closefile()
      raise
    
    if closefile: exof.closefile()
    
    return lineL


#########################################################################

def name_compare( n1, n2 ):
    """
    Case insensitive.  Strips space, '-', '_' from both ends.  Treats '-', '_'
    as a space.  Multiple spaces treated as one space.
    """
    n1 = string.lower( string.strip(n1) )
    n2 = string.lower( string.strip(n2) )
    n1 = string.strip( string.strip( n1, '-' ), '_' )
    n2 = string.strip( string.strip( n2, '-' ), '_' )
    n1 = string.join( string.split( n1 ) )
    n1 = string.join( string.split( n1, '-' ) )
    n1 = string.join( string.split( n1, '_' ) )
    n2 = string.join( string.split( n2 ) )
    n2 = string.join( string.split( n2, '-' ) )
    n2 = string.join( string.split( n2, '_' ) )
    return n1 == n2


def name_search( aname, nameL ):
    """
    Searches for 'aname' in the list of names 'nameL' using the name_compare()
    function.  Returns the index into the 'nameL' list if found, or None if not.
    """
    i = 0
    for ntest in nameL:
      if name_compare( aname, ntest ):
        return i
      i = i + 1
    return None


def time_search( tval, timeL ):
    """
    Determine the time closest to 'tval' in the list of times 'timeL'.  These
    times are assumed to be monotonically increasing.  Returns the index in
    'timeL' corresponding to the closest time.
    """
    if   tval < timeL[0]:  ival = 0
    elif tval > timeL[-1]: ival = len(timeL)-1
    elif len(timeL) == 1:  ival = 0
    else:
      # determine index value with time closest to 'tval'
      i = 1
      while i < len(timeL):
        if tval < timeL[i]:
          if tval - timeL[i-1] < timeL[i] - tval:
            ival = i - 1
          else:
            ival = i
          break
        i = i + 1
      if ival == None:
        ival = len(timeL)-1
    
    return ival


def cycle_search( cycle, exofile ):
    """
    Finds the given cycle number in an exodus file.  'exofile' must be an open
    exodus.ExodusFile instance.  Returns the (zero based) time index
    corresponding to the given cycle value, or None if it was not found.
    """
    ival = None
    
    if cycle < 0:
      tL = exofile.getTimes()
      ival = len(tL)-1
    
    else:
      # first, need the global variable for storing the cycle number
      idx = None
      for n in ['cycle','nsteps']:
        idx = exofile.findVar( exodus.EX_GLOBAL, n, 0, 0 )
        if idx != None:
          break
      if idx != None:
        # then search the cycles for a match
        nt = len(exofile.getTimes())
        vals = None
        for i in xrange(nt):
          vals = exofile.readVar( i+1, exodus.EX_GLOBAL, 0, 0, vals )
          if cycle == int(vals[idx]+0.5):
            ival = i
            break
    
    return ival


vartype_map = { 'g':exodus.EX_GLOBAL,
                'e':exodus.EX_ELEM_BLOCK,
                'f':exodus.EX_FACE_BLOCK,
                'd':exodus.EX_EDGE_BLOCK,
                'n':exodus.EX_NODE }


def displacement_indexes( exofile ):
    """
    Obtains the nodal variable indexes corresponding to the displacement of
    the motion.  The 'exofile' must be an open exodus.ExodusFile instance.
    Returns two lists, var index list and var name list.  If one or more of
    the indexes could not be determined, then None,None is returned.
    """
    bn = exofile.findDisVarBase()
    if bn == None:
      # could not determine displacement base name"
      return None,None
    
    if   exofile.getDimension() == 1: L = ['X']
    elif exofile.getDimension() == 2: L = ['X','Y']
    else:                             L = ['X','Y','Z']
    
    idxL = []
    nameL = []
    nL = exofile.varNames(exodus.EX_NODE)
    for x in L:
      i = name_search( bn+x, nL )
      if i == None:
        # could not determine index for this component of displacement
        return None,None
      idxL.append( i )
      nameL.append( nL[i] )
    
    return idxL, nameL

#########################################################################

def apply_lineout( lflag, lineL, specL, index_first ):
    """
    Using the output from extract_data(), this function removes points that
    are not along a line.  The line is specified by the specL list.
    
    If lflag is 2, the displacements are added to the coordinates first.  In
    this case, the columns are expected to be:
    
              0     1      2      3      4      5      6
       1D   index DISPLX COORDX
       2D   index DISPLX DISPLY COORDX COORDY
       3D   index DISPLX DISPLY DISPLZ COORDX COORDY COORDZ
    
    If lflag is 1, the columns are expected to be:
    
              0     1      2      3   
       1D   index COORDX
       2D   index COORDX COORDY
       3D   index COORDX COORDY COORDZ
    
    If 'index_first' is false, then the first column is not the object index
    (the columns are shifted left by one.)
    
    A new line list is returned.
    """
    i = 0
    if index_first: i = 1
    if "COORDZ" in lineL[0]:
      dim = 3
      DX = i ; DY = i+1 ; DZ = i+2 ; CX = i+3 ; CY = i+4 ; CZ = i+5
    elif "COORDY" in lineL[0]:
      dim = 2
      DX = i ; DY = i+1 ; CX = i+2 ; CY = i+3
    else:
      dim = 1
      DX = i ; CX = i+1
    
    n = len(lineL) - 1
    
    if lflag == 2:
      # add the displacements to the coordinates, then remove the displacements
      if dim == 1:
        lineL[0].pop(DX)
        lineL[0][DX] = "LOCATIONX"
        for i in xrange(n):
          L = lineL[i+1]
          L[CX] = L[CX] + L[DX]
          L.pop(DX)
      elif dim == 2:
        lineL[0].pop(DX) ; lineL[0].pop(DX)
        lineL[0][DX] = "LOCATIONX"
        lineL[0][DY] = "LOCATIONY"
        for i in xrange(n):
          L = lineL[i+1]
          L[CX] = L[CX] + L[DX]
          L[CY] = L[CY] + L[DY]
          L.pop(DY) ; L.pop(DX)
      else:
        lineL[0].pop(DX) ; lineL[0].pop(DX) ; lineL[0].pop(DX)
        lineL[0][DX] = "LOCATIONX"
        lineL[0][DY] = "LOCATIONY"
        lineL[0][DZ] = "LOCATIONZ"
        for i in xrange(n):
          L = lineL[i+1]
          L[CX] = L[CX] + L[DX]
          L[CY] = L[CY] + L[DY]
          L[CZ] = L[CZ] + L[DZ]
          L.pop(DZ) ; L.pop(DY) ; L.pop(DX)
    
    # at this point, the coordinates to use are now in the displacements slot
    if   dim == 1: CX = DX
    elif dim == 2: CX = DX ; CY = DY
    else:          CX = DX ; CY = DY ; CZ = DZ
    
    if specL[3] == None and len(lineL) >= 2:
      # tolerance not given; first compute mesh bounding box
      if dim == 1:
        bbox = [ lineL[1][CX], lineL[1][CX] ]
        for i in xrange(n):
          L = lineL[i+1]
          bbox[0] = min( bbox[0], L[CX] )
          bbox[1] = max( bbox[1], L[CX] )
      elif dim == 2:
        bbox = [ lineL[1][CX], lineL[1][CX],
                 lineL[1][CY], lineL[1][CY] ]
        for i in xrange(n):
          L = lineL[i+1]
          bbox[0] = min( bbox[0], L[CX] )
          bbox[1] = max( bbox[1], L[CX] )
          bbox[2] = min( bbox[2], L[CY] )
          bbox[3] = max( bbox[3], L[CY] )
      else:
        bbox = [ lineL[1][CX], lineL[1][CX],
                 lineL[1][CY], lineL[1][CY],
                 lineL[1][CZ], lineL[1][CZ] ]
        for i in xrange(n):
          L = lineL[i+1]
          bbox[0] = min( bbox[0], L[CX] )
          bbox[1] = max( bbox[1], L[CX] )
          bbox[2] = min( bbox[2], L[CY] )
          bbox[3] = max( bbox[3], L[CY] )
          bbox[4] = min( bbox[4], L[CZ] )
          bbox[5] = max( bbox[5], L[CZ] )
      # from the direction(s) being restricted, compute tolerance
      tol = None
      for i in range(len(specL)):
        if i < 3 and type(specL[i]) == types.FloatType:
          if i == 0: # x
            tol = 1.e-4 * max( bbox[1] - bbox[0], 1.e-30 )
          elif i == 1: # y
            if tol == None:
              tol = 1.e-4 * max( bbox[3] - bbox[2], 1.e-30 )
            else:
              tol = min( tol, 1.e-4 * max( bbox[3] - bbox[2], 1.e-30 ) )
          else: # z
            if tol == None:
              tol = 1.e-4 * max( bbox[5] - bbox[4], 1.e-30 )
            else:
              tol = min( tol, 1.e-4 * max( bbox[5] - bbox[4], 1.e-30 ) )
      specL[3] = tol
    
    sortidx = []
    rmidx = []
    for i in range(dim):
      if   i == 0: idx = CX
      elif i == 1: idx = CY
      else:        idx = CZ
      if type(specL[i]) == types.FloatType:
        val = specL[i]
        tol = specL[3]
        rmidx.insert( 0, idx )  # want largest index first
        # compute new list excluding points that are not within tolerance
        newL = [ lineL[0] ]
        for j in xrange(n):
          L = lineL[j+1]
          if abs(val-L[idx]) < tol:
            newL.append(L)
        lineL = newL
        n = len(lineL) - 1
      else:
        sortidx.append(idx)
    
    if len(sortidx) > 0:
      # sort by the free column(s)
      if len(sortidx) == 1:
        i1 = sortidx[0]
        def linecmp( a, b ):
          if type(a[0]) == types.StringType: return -1
          if type(b[0]) == types.StringType: return  1
          return cmp( a[i1], b[i1] )
      elif len(sortidx) == 2:
        i1 = sortidx[0]
        i2 = sortidx[1]
        def linecmp( a, b ):
          if type(a[0]) == types.StringType: return -1
          if type(b[0]) == types.StringType: return  1
          c = cmp( a[i1], b[i1] )
          if c == 0:
            return cmp( a[i2], b[i2] )
          return c
      else:
        i1 = sortidx[0]
        i2 = sortidx[1]
        i3 = sortidx[2]
        def linecmp( a, b ):
          if type(a[0]) == types.StringType: return -1
          if type(b[0]) == types.StringType: return  1
          c = cmp( a[i1], b[i1] )
          if c == 0:
            c = cmp( a[i2], b[i2] )
            if c == 0:
              return cmp( a[i3], b[i3] )
          return c
      lineL.sort( linecmp )
    
    if len(rmidx) > 0:
      # remove the LOCATION columns of restricted coordinates
      for L in lineL:
        for i in rmidx:
          L.pop(i)
    
    return lineL


#########################################################################

if __name__ == "__main__":
  
  import getopt
  try:
    optL, argL = getopt.getopt( sys.argv[1:], "hVg:e:f:d:n:t:i:c:L:",
                                longopts=['help','version',
                                'global=','element=','face=','edge=',
                                'node=','nolabels','object-index','time=',
                                'index=','cycle=','lineout='] )
  except getopt.error, e:
    print "*** exoread.py error: " + str(e)
    sys.exit(1)
  
  def vget( t, vtype, name, vL ):
      if vtype and t != vtype:
        print "*** exoread.py error: only one type of variable " + \
                                    "allowed at a time"
        sys.exit(1)
      name = string.strip(name)
      if not name:
        print "*** exoread.py error: varaible name specification " + \
                                    "cannot be empty"
        sys.exit(1)
      vL.append(name)
      return t
  
  optD = {}
  vtype = ''
  varL = []
  for n,v in optL:
    if n in ['-h','--help']:
      print help_string
      sys.exit(0)
    if n in ['-V','--version']:
      print version
      sys.exit(0)
    if   n == '-g' or n == '--global':
      vtype = vget( 'g', vtype, v, varL )
    elif n == '-e' or n == '--element':
      vtype = vget( 'e', vtype, v, varL )
    elif n == '-f' or n == '--face':
      vtype = vget( 'f', vtype, v, varL )
    elif n == '-d' or n == '--edge':
      vtype = vget( 'd', vtype, v, varL )
    elif n == '-n' or n == '--node':
      vtype = vget( 'n', vtype, v, varL )
    elif n in ['-t','--time']:
      try: t = float(v)
      except:
        print "*** exoread.py error: time value must be a number"
        sys.exit(1)
      optD['-t'] = t
    elif n in ['-i','--index']:
      try: i = int(v)
      except:
        print "*** exoread.py error: index value must be an integer"
        sys.exit(1)
      optD['-i'] = i
    elif n in ['-c','--cycle']:
      try: i = int(v)
      except:
        print "*** exoread.py error: cycle value must be an integer"
        sys.exit(1)
      optD['-c'] = i
    elif n == '--object-index':
      optD['--object-index'] = 1
    elif n in ['-L','--lineout']:
      vL = [None,None,None,None]
      v = string.strip(v)
      if not v:
        print "*** exoread.py error: --lineout argument cannot be empty"
        sys.exit(1)
      L = string.split(v,'/')
      for i in xrange(len(L)):
        s = string.strip(L[i])
        if not s:
          print "*** exoread.py error: malformed --lineout argument"
          sys.exit(1)
        if s[0] in ['t','T']:
          try: vL[3] = float( s[1:] )
          except:
            print "*** exoread.py error: malformed --lineout argument"
            sys.exit(1)
          break
        if s in ['x','X']:
          if i != 0:
            print "*** exoread.py error: malformed --lineout argument"
            sys.exit(1)
          vL[0] = s
        elif s in ['y','Y']:
          if i != 1:
            print "*** exoread.py error: malformed --lineout argument"
            sys.exit(1)
          vL[1] = s
        elif s in ['z','Z']:
          if i != 2:
            print "*** exoread.py error: malformed --lineout argument"
            sys.exit(1)
          vL[2] = s
        else:
          try: f = float(s)
          except:
            print "*** exoread.py error: malformed --lineout argument"
            sys.exit(1)
          vL[i] = f
      optD['-L'] = vL
    else:
      optD[n] = optD.get(n,[]) + [v]
  
  if len(argL) == 0:
    print "*** exoread.py error: expected a filename"
    sys.exit(1)
  
  if len(varL) > 0:
    
    lflag = 0
    if optD.has_key('-L') and vtype != 'g':
      lflag = 1  # turn on lineout flag
      # add coordinates to var list for lineout algorithm
      varL.insert( 0, "coordinates" )
      for v in optD['-L']:
        if type(v) == types.StringType and v in ['X','Y','Z']:
          lflag = 2  # add displacements for lineout algorithm
          varL.insert( 0, "displacements" )
          break
    
    lineL = extract_data( vtype, varL, argL[0],
                          optD.get('-t',None),
                          optD.get('-i',None),
                          optD.get('-c',None),
                          optD.get('--object-index',0) )
    
    if lineL != None:
      
      if lflag > 0:
        lineL = apply_lineout( lflag, lineL, optD['-L'],
                               optD.get('--object-index',0) )
      
      label_line = 1
      for Lfloat in lineL:
        if label_line:
          label_line = 0
          if not optD.has_key('--nolabels'):
            L = []
            for label in Lfloat:
              L.append( "%24s"%label )
            print string.join(L)
        else:
          L = []
          if optD.has_key('--object-index'):
            L.append( "%24d"%Lfloat[0] )  # first column is integer index
            for f in Lfloat[1:]:
              L.append( "%24.16e"%f )
          else:
            for f in Lfloat:
              L.append( "%24.16e"%f )
          print string.join(L)
      
  else:
    meta_data( argL[0] )
