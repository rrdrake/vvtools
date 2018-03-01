#!/usr/bin/env python

# ElemData2.py is associated with and used by anpy. It is almost the same
# as the ElemData.py associated with and used by tampa and TampaDSTKTools.py
# and will eventually superseed it.

# This first function maps vtkCellTypes to exodus element definitions.

def GetvtkEtypeInfo(vtkCellType):
    """Determine the element type and return a dictionary containing
    functions for that element.

    vtkCellType can be either 'vtkQuad' or 'vtkHexahedron'

    For these Cell Types the dictionary returns
    ndim                       the number of dimensions
    vol_func(X)                the volume (or area) of the cell
    subdiv_func(X,intervals)   coordinates of centers of an equispaced
                                 subdivision of the original cell,
                                 where intervals is the number of subcells
                                 in each dimension
    ctr_func(X)                the center (average of coordinates)
    subel_func(X, intervals)   nodal coordinates of a uniformly refined
                                 element. In contrast, subdiv_func gives
                                 the coordinates of the centers of these
                                 subelements.
    subel_conn_func(intervals,elem_coords) the connectivity array mapping the
                                 nodes returned by subel_func to the
                                 corresponding subelements

    In each of these functions, X contains the coordinates of the cell
    vertices, X[vertex_index][dimension]
    """

# A dictionary providing the data for each element type
    supported_elements = {'vtkQuad':
                            {'ndim': quad4_ndim,
                             'vol_func': quad4_vol,
                             'subdiv_func': quad4_subdiv,
                             'ctr_func': quad4_ctr,
                             'subel_nodes': quad4_subel_nodes,
                             'subel_conn': quad4_subel_conn,
                             'subel_vols': quad4_subel_vols},
                          'vtkHexahedron':
                            {'ndim': hex8_ndim,
                             'vol_func': hex8_vol,
                             'subdiv_func': hex8_subdiv,
                             'ctr_func': hex8_ctr,
                             'subel_nodes': hex8_subel_nodes,
                             'subel_conn': hex8_subel_conn,
                             'subel_vols': hex8_subel_vols},
                          'vtkTetra':
                            {'ndim': tet4_ndim,
                             'vol_func': tet4_vol,
                             'subdiv_func': tet4_subdiv,
                             'ctr_func': tet4_ctr,
                             'subel_nodes': tet4_subel_nodes,
                             'subel_conn': tet4_subel_conn,
                             'subel_vols': tet4_subel_vols},
                          'vtkWedge':
                            {'ndim': wedge6_ndim,
                             'vol_func': wedge6_vol,
                             'subdiv_func': wedge6_subdiv,
                             'ctr_func': wedge6_ctr,
                             'subel_nodes': wedge6_subel_nodes,
                             'subel_conn': wedge6_subel_conn,
                             'subel_vols': wedge6_subel_vols} }

    etype_info = supported_elements.get(vtkCellType, 'fail')

    if etype_info == 'fail':
        print 'Element Data not found for element type ', vtkCellType

    return etype_info

# This second function maps exodus element names (used by ALEGRA,
# anyway) to exodus element definitions.

def GetEtypeInfo(ALEGRAType):
    """Determine the element type and return a dictionary containing
    functions for that element.

    vtkCellType can be either 'vtkQuad' or 'vtkHexahedron'

    For these Cell Types the dictionary returns
    ndim                       the number of dimensions
    vol_func(X)                the volume (or area) of the cell
    subdiv_func(X,intervals)   coordinates of centers of an equispaced
                                 subdivision of the original cell,
                                 where intervals is the number of subcells
                                 in each dimension
    ctr_func(X)                the center (average of coordinates)
    subel_func(X, intervals)   nodal coordinates of a uniformly refined
                                 element. In contrast, subdiv_func gives
                                 the coordinates of the centers of these
                                 subelements.
    subel_conn_func(intervals) the connectivity array mapping the
                                 nodes returned by subel_func to the
                                 corresponding subelements

    In each of these functions, X contains the coordinates of the cell
    vertices, X[vertex_index][dimension]
    """


    def a_names(name_string):
        if name_string.lower() in ['quad','quad4']: return 'QUAD4'
        elif name_string.lower() in ['hex','hex8']: return 'HEX8'
        elif name_string.lower() in ['tet','tet4','tetra']: return 'TET4'
	elif name_string.lower() in ['wedge','wedge6']: return 'WEDGE6'
        else: return None


# A dictionary providing the data for each element type
    supported_elements = {'QUAD4':
                            {'ndim': quad4_ndim,
                             'vol_func': quad4_vol,
                             'subdiv_func': quad4_subdiv,
                             'ctr_func': quad4_ctr,
                             'subel_nodes': quad4_subel_nodes,
                             'subel_conn': quad4_subel_conn,
                             'subel_vols': quad4_subel_vols},
                          'HEX8':
                            {'ndim': hex8_ndim,
                             'vol_func': hex8_vol,
                             'subdiv_func': hex8_subdiv,
                             'ctr_func': hex8_ctr,
                             'subel_nodes': hex8_subel_nodes,
                             'subel_conn': hex8_subel_conn,
                             'subel_vols': hex8_subel_vols},
                          'TET4':
                            {'ndim': tet4_ndim,
                             'vol_func': tet4_vol,
                             'subdiv_func': tet4_subdiv,
                             'ctr_func': tet4_ctr,
                             'subel_nodes': tet4_subel_nodes,
                             'subel_conn': tet4_subel_conn,
                             'subel_vols': tet4_subel_vols},
			  'WEDGE6':
                            {'ndim': wedge6_ndim,
                             'vol_func': wedge6_vol,
                             'subdiv_func': wedge6_subdiv,
                             'ctr_func': wedge6_ctr,
                             'subel_nodes': wedge6_subel_nodes,
                             'subel_conn': wedge6_subel_conn,
                             'subel_vols': wedge6_subel_vols},}

    etype_info = supported_elements.get(a_names(ALEGRAType), 'fail')

    if etype_info == 'fail':
        print 'Element Data not found for element type ', ALEGRAType
        return None

    return etype_info






# Volume calclations are taken directly from element files in alegra/framework

quad4_ndim = 2

def quad4_vol(X):
  vol  = (X[0][0] - X[2][0]) * (X[1][1] - X[3][1])
  vol += (X[1][0] - X[3][0]) * (X[2][1] - X[0][1])
  return 0.5*vol

def quad4_subdiv(elem_coords, intervals):
    """Compute an equispaced subdivision of a quad4 element.

    Quadrature points are equispaced, rather than Gaussian; improved
    order of accuracy of Gaussian quadrature is not achieved for
    discontinuous data.

    Input:
    elem_coords:  coordinates of element's nodes, assuming exodus
                    node order convention - (counter clockwise around
                    the element)
    intervals:    The element will be subdivided into nx*ny equispaced
                    subelements, where nx = ny = intervals
    """

    subelem_coords = []

    for jj in range(intervals):
        j = (0.5 + jj)/intervals
        for ii in range(intervals):
            i = (0.5 + ii)/intervals
            X_pt = (   (1-j)*(1-i)*elem_coords[0][0]
                     + (1-j)*   i *elem_coords[1][0]
                     +    j *   i *elem_coords[2][0]
                     +    j *(1-i)*elem_coords[3][0] )
            Y_pt = (   (1-j)*(1-i)*elem_coords[0][1]
                     + (1-j)*   i *elem_coords[1][1]
                     +    j *   i *elem_coords[2][1]
                     +    j *(1-i)*elem_coords[3][1] )
            subelem_coords.append( [X_pt, Y_pt, 0.0] )

    return subelem_coords

def quad4_ctr(elem_coords):
    """Compute the coordinates of the center of a quad4 element.

    Simple average in physical space.

    The result is the same as for quad4_subdiv with intervals=1.

    Input:
    elem_coords:  coordinates of element's nodes, assuming exodus
                    node order convention - (counter clockwise around
                    the element)
    """
    X_pt = 0.25*(   elem_coords[0][0]
                  + elem_coords[1][0]
                  + elem_coords[2][0]
                  + elem_coords[3][0] )
    Y_pt = 0.25*(   elem_coords[0][1]
                  + elem_coords[1][1]
                  + elem_coords[2][1]
                  + elem_coords[3][1] )
    return [ X_pt, Y_pt, 0.0 ]

def quad4_subel_nodes(elem_coords, intervals):
    """Compute an equispaced subdivision of a quad4 element. Return
    the nodal coordinates of the subelements.

    Input:
    elem_coords:  coordinates of element's nodes, assuming exodus
                    node order convention - (counter clockwise around
                    the element)
    intervals:    The element will be subdivided into nx*ny equispaced
                    subelements, where nx = ny = intervals
    """

    subelem_coords = []

    for jj in range(intervals+1):
        j = float(jj)/intervals
        for ii in range(intervals+1):
            i = float(ii)/intervals
            X_pt = (   (1-j)*(1-i)*elem_coords[0][0]
                     + (1-j)*   i *elem_coords[1][0]
                     +    j *   i *elem_coords[2][0]
                     +    j *(1-i)*elem_coords[3][0] )
            Y_pt = (   (1-j)*(1-i)*elem_coords[0][1]
                     + (1-j)*   i *elem_coords[1][1]
                     +    j *   i *elem_coords[2][1]
                     +    j *(1-i)*elem_coords[3][1] )
            subelem_coords.append( [X_pt, Y_pt] )

    return subelem_coords

def quad4_subel_conn(intervals,elem_coords=[]):
    """Compute the connectivity matrix relating the subelements to the
    nodes produced by quad4_subel_nodes. Node indices are 0-based.

    Input:
    intervals:    The element will be subdivided into nx*ny equispaced
                    subelements, where nx = ny = intervals
    """

    subelem_conn = []

    n = intervals + 1
    for j in range(intervals):
        jn =   j   *n
        j1n = (j+1)*n
        for i in range(intervals):
            i1 = i + 1
            # 0-based element number is j*intervals + i
            # local node numbers n1, n2, n3, n4
            n1 = i  + jn
            n2 = i1 + jn
            n3 = i1 + j1n
            n4 = i  + j1n

            subelem_conn.extend([n1, n2, n3, n4])

    return subelem_conn

def quad4_subel_vols(elem_coords, intervals):
    """Compute the subelement volumes of an equispaced subdivision of
    a quad4 element. Return the volumes of the subelements.

    Input:
    elem_coords:  coordinates of element's nodes, assuming exodus
                    node order convention - (counter clockwise around
                    the element)
    intervals:    The element will be subdivided into nx*ny equispaced
                    subelements, where nx = ny = intervals
    """

    subel_nodes = quad4_subel_nodes( elem_coords, intervals )
    subel_conn = quad4_subel_conn( intervals )
    nodes_per = 4

    subel_vols = []
    for subel in range(intervals*intervals):
        loc_coords= []
        for node in range(nodes_per):
            loc_coords.append(subel_nodes[subel_conn[subel*nodes_per + node]])
        subel_vols.append(quad4_vol(loc_coords))

    return subel_vols


hex8_ndim = 3

def hex8_vol(X):

  x1 = X[0][0]
  x2 = X[1][0]
  x3 = X[2][0]
  x4 = X[3][0]
  x5 = X[4][0]
  x6 = X[5][0]
  x7 = X[6][0]
  x8 = X[7][0]

  y1 = X[0][1]
  y2 = X[1][1]
  y3 = X[2][1]
  y4 = X[3][1]
  y5 = X[4][1]
  y6 = X[5][1]
  y7 = X[6][1]
  y8 = X[7][1]

  z1 = X[0][2]
  z2 = X[1][2]
  z3 = X[2][2]
  z4 = X[3][2]
  z5 = X[4][2]
  z6 = X[5][2]
  z7 = X[6][2]
  z8 = X[7][2]

  rx0 = (  y2*((z6-z3)-(z4-z5))
          +y3*(z2-z4)
          +y4*((z3-z8)-(z5-z2))
          +y5*((z8-z6)-(z2-z4))
          +y6*(z5-z2)
          +y8*(z4-z5) )
  rx1 = (  y3*((z7-z4)-(z1-z6))
          +y4*(z3-z1)
          +y1*((z4-z5)-(z6-z3))
          +y6*((z5-z7)-(z3-z1))
          +y7*(z6-z3)
          +y5*(z1-z6) )
  rx2 = (  y4*((z8-z1)-(z2-z7))
          +y1*(z4-z2)
          +y2*((z1-z6)-(z7-z4))
          +y7*((z6-z8)-(z4-z2))
          +y8*(z7-z4)
          +y6*(z2-z7) )
  rx3 = (  y1*((z5-z2)-(z3-z8))
          +y2*(z1-z3)
          +y3*((z2-z7)-(z8-z1))
          +y8*((z7-z5)-(z1-z3))
          +y5*(z8-z1)
          +y7*(z3-z8) )
  rx4 = (  y8*((z4-z7)-(z6-z1))
          +y7*(z8-z6)
          +y6*((z7-z2)-(z1-z8))
          +y1*((z2-z4)-(z8-z6))
          +y4*(z1-z8)
          +y2*(z6-z1) )
  rx5 = (  y5*((z1-z8)-(z7-z2))
          +y8*(z5-z7)
          +y7*((z8-z3)-(z2-z5))
          +y2*((z3-z1)-(z5-z7))
          +y1*(z2-z5)
          +y3*(z7-z2) )
  rx6 = (  y6*((z2-z5)-(z8-z3))
          +y5*(z6-z8)
          +y8*((z5-z4)-(z3-z6))
          +y3*((z4-z2)-(z6-z8))
          +y2*(z3-z6)
          +y4*(z8-z3) )
  rx7 = (  y7*((z3-z6)-(z5-z4))
          +y6*(z7-z5)
          +y5*((z6-z1)-(z4-z7))
          +y4*((z1-z3)-(z7-z5))
          +y3*(z4-z7)
          +y1*(z5-z4) )

  vol = (   x1*rx0
          + x2*rx1
          + x3*rx2
          + x4*rx3
          + x5*rx4
          + x6*rx5
          + x7*rx6
          + x8*rx7 ) / 12.0

  return vol



def hex8_subdiv(elem_coords, intervals):
    """Compute an equispaced subdivision of a hex8 element.

    Quadrature points are equispaced, rather than Gaussian; improved
    order of accuracy of Gaussian quadrature is not achieved for
    discontinuous data.

    Input:
    elem_coords:  coordinates of element's nodes, assuming exodus
                    node order convention - (counter clockwise around
                    the element)
    intervals:    The element will be subdivided into nx*ny*nz equispaced
                    subelements, where nx = ny = nz = intervals
    """

    subelem_coords = []

    for kk in range(intervals):
        k = (0.5 + kk)/intervals
        for jj in range(intervals):
            j = (0.5 + jj)/intervals
            for ii in range(intervals):
               i = (0.5 + ii)/intervals
               X_pt = (   (1-k)*(1-j)*(1-i)*elem_coords[0][0]
                        + (1-k)*(1-j)*   i *elem_coords[1][0]
                        + (1-k)*   j *   i *elem_coords[2][0]
                        + (1-k)*   j *(1-i)*elem_coords[3][0]
                        +    k *(1-j)*(1-i)*elem_coords[4][0]
                        +    k *(1-j)*   i *elem_coords[5][0]
                        +    k *   j *   i *elem_coords[6][0]
                        +    k *   j *(1-i)*elem_coords[7][0] )
               Y_pt = (   (1-k)*(1-j)*(1-i)*elem_coords[0][1]
                        + (1-k)*(1-j)*   i *elem_coords[1][1]
                        + (1-k)*   j *   i *elem_coords[2][1]
                        + (1-k)*   j *(1-i)*elem_coords[3][1]
                        +    k *(1-j)*(1-i)*elem_coords[4][1]
                        +    k *(1-j)*   i *elem_coords[5][1]
                        +    k *   j *   i *elem_coords[6][1]
                        +    k *   j *(1-i)*elem_coords[7][1] )
               Z_pt = (   (1-k)*(1-j)*(1-i)*elem_coords[0][2]
                        + (1-k)*(1-j)*   i *elem_coords[1][2]
                        + (1-k)*   j *   i *elem_coords[2][2]
                        + (1-k)*   j *(1-i)*elem_coords[3][2]
                        +    k *(1-j)*(1-i)*elem_coords[4][2]
                        +    k *(1-j)*   i *elem_coords[5][2]
                        +    k *   j *   i *elem_coords[6][2]
                        +    k *   j *(1-i)*elem_coords[7][2] )
               subelem_coords.append( [X_pt, Y_pt, Z_pt] )

    return subelem_coords

def hex8_ctr(elem_coords):
    """Compute the coordinates of the center of a hex8 element.

    Simple average in physical space.

    The result is the same as for hex8_subdiv with intervals=1.

    Input:
    elem_coords:  coordinates of element's nodes, assuming exodus
                    node order convention - (counter clockwise around
                    the element)
    """
    X_pt = 0.125*(   elem_coords[0][0]
                   + elem_coords[1][0]
                   + elem_coords[2][0]
                   + elem_coords[3][0]
                   + elem_coords[4][0]
                   + elem_coords[5][0]
                   + elem_coords[6][0]
                   + elem_coords[7][0] )
    Y_pt = 0.125*(   elem_coords[0][1]
                   + elem_coords[1][1]
                   + elem_coords[2][1]
                   + elem_coords[3][1]
                   + elem_coords[4][1]
                   + elem_coords[5][1]
                   + elem_coords[6][1]
                   + elem_coords[7][1] )
    Z_pt = 0.125*(   elem_coords[0][2]
                   + elem_coords[1][2]
                   + elem_coords[2][2]
                   + elem_coords[3][2]
                   + elem_coords[4][2]
                   + elem_coords[5][2]
                   + elem_coords[6][2]
                   + elem_coords[7][2] )
    return [ X_pt, Y_pt, Z_pt ]

def hex8_subel_nodes(elem_coords, intervals):
    """Compute an equispaced subdivision of a hex8 element. Return
    the nodal coordinates of the subelements.

    Input:
    elem_coords:  coordinates of element's nodes, assuming exodus
                    node order convention - (counter clockwise around
                    the element)
    intervals:    The element will be subdivided into nx*ny equispaced
                    subelements, where nx = ny = intervals
    """

    subelem_coords = []

    for kk in range(intervals+1):
        k = float(kk)/intervals
        for jj in range(intervals+1):
            j = float(jj)/intervals
            for ii in range(intervals+1):
                i = float(ii)/intervals
                X_pt = (   (1-k)*(1-j)*(1-i)*elem_coords[0][0]
                         + (1-k)*(1-j)*   i *elem_coords[1][0]
                         + (1-k)*   j *   i *elem_coords[2][0]
                         + (1-k)*   j *(1-i)*elem_coords[3][0]
                         +    k *(1-j)*(1-i)*elem_coords[4][0]
                         +    k *(1-j)*   i *elem_coords[5][0]
                         +    k *   j *   i *elem_coords[6][0]
                         +    k *   j *(1-i)*elem_coords[7][0] )
                Y_pt = (   (1-k)*(1-j)*(1-i)*elem_coords[0][1]
                         + (1-k)*(1-j)*   i *elem_coords[1][1]
                         + (1-k)*   j *   i *elem_coords[2][1]
                         + (1-k)*   j *(1-i)*elem_coords[3][1]
                         +    k *(1-j)*(1-i)*elem_coords[4][1]
                         +    k *(1-j)*   i *elem_coords[5][1]
                         +    k *   j *   i *elem_coords[6][1]
                         +    k *   j *(1-i)*elem_coords[7][1] )
                Z_pt = (   (1-k)*(1-j)*(1-i)*elem_coords[0][2]
                         + (1-k)*(1-j)*   i *elem_coords[1][2]
                         + (1-k)*   j *   i *elem_coords[2][2]
                         + (1-k)*   j *(1-i)*elem_coords[3][2]
                         +    k *(1-j)*(1-i)*elem_coords[4][2]
                         +    k *(1-j)*   i *elem_coords[5][2]
                         +    k *   j *   i *elem_coords[6][2]
                         +    k *   j *(1-i)*elem_coords[7][2] )
                subelem_coords.append( [X_pt, Y_pt, Z_pt] )

    return subelem_coords

def hex8_subel_conn(intervals,elem_coords=[]):
    """Compute the connectivity matrix relating the subelements to the
    nodes produced by hex8_subel_nodes. Node indices are 0-based.

    Input:
    intervals:    The element will be subdivided into nx*ny*nz equispaced
                    subelements, where nx = ny = nz = intervals
    """

    subelem_conn = []

    n  = intervals + 1
    nn = n*n
    for k in range(intervals):
        knn  =  k   *nn         #    k *(intervals+1)^2
        k1nn = (k+1)*nn         # (k+1)*(intervals+1)^2
        for j in range(intervals):
            jn_knn   = j*n     + knn   #    j *(intervals+1) +    k *(intervals+1)^2
            j1n_knn  = (j+1)*n + knn   # (j+1)*(intervals+1) +    k *(intervals+1)^2
            jn_k1nn  = j*n     + k1nn  #    j *(intervals+1) + (k+1)*(intervals+1)^2
            j1n_k1nn = (j+1)*n + k1nn  # (j+1)*(intervals+1) + (k+1)*(intervals+1)^2
            for i in range(intervals):
                i1 = i+1
                # 0-based element number is j*intervals + i
                # local node numbers n1, n2, n3, n4, n5, n6, n7, n8
                n1 = i  +   jn_knn
                n2 = i1 +   jn_knn
                n3 = i1 +   j1n_knn
                n4 = i  +   j1n_knn
                n5 = i  +   jn_k1nn
                n6 = i1 +   jn_k1nn
                n7 = i1 +   j1n_k1nn
                n8 = i  +   j1n_k1nn

                subelem_conn.extend([n1, n2, n3, n4, n5, n6, n7, n8])

    return subelem_conn


def hex8_subel_vols(elem_coords, intervals):
    """Compute the subelement volumes of an equispaced subdivision of
    a hex8 element. Return the volumes of the subelements.

    Input:
    elem_coords:  coordinates of element's nodes, assuming exodus
                    node order convention - (counter clockwise around
                    the element)
    intervals:    The element will be subdivided into nx*ny*nz equispaced
                    subelements, where nx = ny = nz = intervals
    """

    subel_nodes = hex8_subel_nodes( elem_coords, intervals )
    subel_conn = hex8_subel_conn( intervals )
    nodes_per = 8

    subel_vols = []
    for subel in range(intervals*intervals*intervals):
        loc_coords= []
        for node in range(nodes_per):
            loc_coords.append(subel_nodes[subel_conn[subel*nodes_per + node]])
        subel_vols.append(hex8_vol(loc_coords))

    return subel_vols


#################### utility functions for tetrahedrons #################
def _crossproduct(a,b):
    if not len(a) == 3 or not len(b) == 3:
        print "cross product is only defined for two 3d vectors"
    x = a[1]*b[2]-a[2]*b[1]
    y = -a[0]*b[2]+a[2]*b[0]
    z = a[0]*b[1]-a[1]*b[0]
    return [x, y, z]

def _dotproduct(a,b):
    sum = 0
    if not len(a) == len(b):
        print "tried to take the dot product of two vectors of different dimension"
    for i in range(len(a)):
        sum += a[i]*b[i]
    return sum

def _midpoint(a,b):
    return [(a[0]+b[0])/2.0,(a[1]+b[1])/2.0,(a[2]+b[2])/2.0]

def _distsquare(a,b):
    return ((a[0]-b[0])*(a[0]-b[0]) + (a[1]-b[1])*(a[1]-b[1]) + (a[2]-b[2])*(a[2]-b[2]))

def _unravel(nodes,tets,index):
    """Returns a list containing the node coordinates of the tet
    stored in the 'index' position in the 'tets' list."""
    return [nodes[tets[index][0]],nodes[tets[index][1]],nodes[tets[index][2]],nodes[tets[index][3]]]

def _tet_subel_nodes_recurse(nodes,tets,iterations):
    """Main subivision function.  'nodes' contains a list of nodes, and 'tets'
    is a list containing objects like [2,5,7,8], where nodes[2],nodes[5],nodes[7]
    and nodes[8] would give the nodes of a tetrahedron.  This function divides
    each tetrahedron in half recursively, up to 'iterations' recursion levels.
    Each tetrahedron is divided in half on its longest edge, so the final tetrahedrons
    should have similar dimensions.

    After running, the lists passed as 'nodes' and 'tets' will contain the node locations
    and indexes respectively for the subdivided tetrahedrons"""
    if iterations == 0:
        return
    newtets = []
    for tet in tets:
        #find longest edge
        longest = 0
        longi1 = 0
        longi2 = 0
        i3 = 0
        i4 = 0
        for a in tet:
            for b in tet:
                ds = _distsquare(nodes[a],nodes[b])
                if ds > longest:
                    longest = ds
                    longi1 = a
                    longi2 = b

        for a in tet:
            if a != longi1 and a != longi2:
                if i3 == 0:
                    i3 = a
                else:
                    i4 = a
        #split it
        mp = _midpoint(nodes[longi1],nodes[longi2])
        nodes.append(mp)
        mpnode = len(nodes) - 1
        #replace it with the two new tets
        newtets.append([longi1,mpnode,i3,i4])
        newtets.append([longi2,mpnode,i3,i4])
    #recurse
    _tet_subel_nodes_recurse(nodes,newtets,iterations-1)
    tets[:] = newtets



tet4_ndim = 3

def tet4_vol(X):
    amd = [X[0][i] - X[3][i] for i in range(3)]
    bmd = [X[1][i] - X[3][i] for i in range(3)]
    cmd = [X[2][i] - X[3][i] for i in range(3)]
    V = abs(_dotproduct(amd,_crossproduct(bmd,cmd))/6.)
    return V

def tet4_subel_nodes(elem_coords, intervals):
    """Divides the tet into 4^(intervals-1) new tetrahedrons, each with equal volume.
    The tetrahedrons are recursively divided along their longest edge to create two
    smaller tetrahedrons.

    Input:
    elem_coords:  coordinates of element's nodes, assuming exodus
                    node order convention - (counter clockwise around
                    the element)
    intervals:    The element will be subdivided into nx*ny*nz equispaced
                    subelements, where nx = ny = nz = intervals
    """
    if intervals <= 1:
        return elem_coords
    else:
        tetindices = [[0,1,2,3]]
        nodes = [i for i in elem_coords] #deepcopy
        _tet_subel_nodes_recurse(nodes,tetindices,intervals*2-2)
        return nodes

def tet4_subdiv(elem_coords, intervals):
    """Compute node center list for a subdivided tet element"""
    tetindices = [[0,1,2,3]]
    nodes = [i for i in elem_coords] #deepcopy
    if intervals > 1:
        _tet_subel_nodes_recurse(nodes,tetindices,intervals*2-2)
    return [tet4_ctr(_unravel(nodes,tetindices,i)) for i in range(len(tetindices))]

def tet4_subel_vols(elem_coords, intervals):
    """Compute volumes of the subdivided tets"""
    tetindices = [[0,1,2,3]]
    if intervals <= 1:
        nodes = elem_coords
    else:
        nodes = [i for i in elem_coords] #deepcopy
        _tet_subel_nodes_recurse(nodes,tetindices,intervals*2-2)
    return [tet4_vol(_unravel(nodes,tetindices,i)) for i in range(len(tetindices))]

def tet4_subel_conn(intervals,elem_coords=[]):
    """Compute connectivity map for subdivided tets.  elem_coords must be supplied."""
    tetindices = [[0,1,2,3]]
    if intervals > 1:
        nodes = [i for i in elem_coords] #deepcopy
        _tet_subel_nodes_recurse(nodes,tetindices,intervals*2-2)
    conn = []
    for tet in tetindices:
        conn.extend(tet)
    return conn


def tet4_ctr(elem_coords):
    """Compute the coordinates of the center of a tet element.

    Simple average in physical space.

    Input:
    elem_coords:  coordinates of element's nodes, assuming exodus
                    node order convention - (counter clockwise around
                    the element)
    """
    X_pt = 0.25*(   elem_coords[0][0]
                  + elem_coords[1][0]
                  + elem_coords[2][0]
                  + elem_coords[3][0] )
    Y_pt = 0.25*(   elem_coords[0][1]
                  + elem_coords[1][1]
                  + elem_coords[2][1]
                  + elem_coords[3][1] )
    Z_pt = 0.25*(   elem_coords[0][2]
                  + elem_coords[1][2]
                  + elem_coords[2][2]
                  + elem_coords[3][2] )
    return [ X_pt, Y_pt, Z_pt ]



wedge6_ndim = 6

def _wedge_subel_nodes_recurse(nodes,wedges,iterations):

  if iterations == 0:
     return

  newwedges=[]
  for wedge in wedges:
    longest=0
    ni=0
    nj=0
    nk=0

    for i in range (0,2):
      for j in range (i+1,3):
        ds = _distsquare(nodes[wedge[i]],nodes[wedge[j]])
        if ds > longest:
          longest=ds
  	  ni=i
	  nj=j

    for k in range (0,2):
      if k != ni and k!= nj:
        nk = k


    gi=wedge[ni]
    gj=wedge[nj]
    gk=wedge[nk]
    giu=wedge[ni+3]
    gju=wedge[nj+3]
    gku=wedge[nk+3]

    #SPLIT
    mpbtri = _midpoint(nodes[gi],nodes[gj])
    mpttri = _midpoint(nodes[giu],nodes[gju])
    mpvi  = _midpoint(nodes[gi],nodes[giu])
    mpvj  = _midpoint(nodes[gj],nodes[gju])
    mpvk  = _midpoint(nodes[gk],nodes[gku])
    mpvm  = _midpoint(mpbtri, mpttri)

    old_max = len(nodes);
    nodes.append(mpbtri) #old_max+1
    nodes.append(mpttri) #old_max+2
    nodes.append(mpvi)   #old_max+3
    nodes.append(mpvj)   #old_max+4
    nodes.append(mpvk)   #old_max+5
    nodes.append(mpvm)   #old_max+6


    # wedge [ni, mpb, nk, vi, vm, vk]
    newwedges.append([gi,old_max+1,gk,old_max+3,old_max+6, old_max+5])
    # wedge [mpb, nj, nk, vm, vj, vk]
    newwedges.append([old_max+1,gj,gk,old_max+6,old_max +4, old_max+5])
    # wedge [vi, vm, vk, ni+3, mpt, nk+3]
    newwedges.append([old_max+3,old_max+6, old_max+5,giu, old_max+2, gku])
    #wedge [vm, vj, vk, mpt, nj+3, nk+3]
    newwedges.append([old_max+6,old_max +4, old_max+5, old_max+2, gju, gku])

  #RECURSE
  _wedge_subel_nodes_recurse(nodes,newwedges,iterations-1)
  wedges[:]=newwedges


def wedge6_subel_nodes(elem_coords, intervals):
    """Divides the wedge into 4^(intervals) new wedges.
    The wedges are recursively divided along their bottom triangular face's longest edge
    to create two and through the middle of vertical extrusion to produce 4
    sub wedges

    Input:
    elem_coords:  coordinates of element's nodes, assuming exodus
                    node order convention - (counter clockwise around
                    the element)
    intervals:    The element will be subdivided into nx*ny*nz equispaced
                    subelements, where nx = ny = nz = intervals
    """
    if intervals <= 1:
        return elem_coords
    else:
        wedgeindices = [[0,1,2,3,4,5]]
        nodes = [i for i in elem_coords] #deepcopy
        _wedge_subel_nodes_recurse(nodes,wedgeindices,intervals*2-2)
        return nodes

def wedge6_subdiv(elem_coords, intervals):
    """Compute node center list for a subdivided wedges element"""
    wedgeindices = [[0,1,2,3,4,5]]
    nodes = [i for i in elem_coords] #deepcopy
    if intervals > 1:
        _wedge_subel_nodes_recurse(nodes,wedgeindices,intervals*2-2)
    return [wedge6_ctr(_unravel(nodes,wedgeindices,i)) for i in range(len(wedgeindices))]

def wedge6_subel_vols(elem_coords, intervals):
    """Compute volumes of the subdivided wedges"""
    wedgeindices = [[0,1,2,3,4,5]]
    if intervals <= 1:
        nodes = elem_coords
    else:
        nodes = [i for i in elem_coords] #deepcopy
        _wedge_subel_nodes_recurse(nodes,tetindices,intervals*2-2)
    return [wedge6_vol(_unravel(nodes,wedgeindices,i)) for i in range(len(wedgeindices))]

def wedge6_subel_conn(intervals,elem_coords=[]):
    """Compute connectivity map for subdivided wedges.  elem_coords must be supplied."""
    wedgeindices = [[0,1,2,3,4,5]]
    if intervals > 1:
        nodes = [i for i in elem_coords] #deepcopy
        _wedge_subel_nodes_recurse(nodes,wedgeindices,intervals*2-2)
    conn = []
    for wedge in wedgeindices:
        conn.extend(wedge)
    return conn

def wedge6_vol(X):
  """Computes volume of the wedge given nodes.

     Calculates volume by cutting into three tetrahedra
  """
  ux=X[2][0]-X[0][0]
  uy=X[2][1]-X[0][1]
  uz=X[2][2]-X[0][2]

  vx=X[1][0]-X[0][0]
  vy=X[1][1]-X[0][1]
  vz=X[1][2]-X[0][2]

  wx=X[4][0]-X[0][0]
  wy=X[4][1]-X[0][1]
  wz=X[4][2]-X[0][2]

  vol = wx*(uy*vz-uz*vy)+wy*(vx*uz-ux*vz)+wz*(ux*vy-uy*vx)

  ux=X[3][0]-X[0][0]
  uy=X[3][1]-X[0][1]
  uz=X[3][2]-X[0][2]

  vx=X[5][0]-X[0][0]
  vy=X[5][1]-X[0][1]
  vz=X[5][2]-X[0][2]

  wx=X[4][0]-X[0][0]
  wy=X[4][1]-X[0][1]
  wz=X[4][2]-X[0][2]

  vol += wx*(uy*vz-uz*vy)+wy*(vx*uz-ux*vz)+wz*(ux*vy-uy*vx)

  ux=X[5][0]-X[0][0]
  uy=X[5][1]-X[0][1]
  uz=X[5][2]-X[0][2]

  vx=X[2][0]-X[0][0]
  vy=X[2][1]-X[0][1]
  vz=X[2][2]-X[0][2]

  wx=X[4][0]-X[0][0]
  wy=X[4][1]-X[0][1]
  wz=X[4][2]-X[0][2]

  vol += wx*(uy*vz-uz*vy)+wy*(vx*uz-ux*vz)+wz*(ux*vy-uy*vx)

  return vol

def wedge6_ctr(X):
  X_pt=1/6*( X[0][0]
            +X[1][0]
	    +X[2][0]
	    +X[3][0]
	    +X[4][0]
	    +X[5][0])
  Y_pt=1/6*( X[0][1]
            +X[1][1]
	    +X[2][1]
	    +X[3][1]
	    +X[4][1]
	    +X[5][1])
  Z_pt=1/6*( X[0][2]
            +X[1][2]
	    +X[2][2]
	    +X[3][2]
	    +X[4][2]
	    +X[5][2])
  return [X_pt, Y_pt, Z_pt]


#testing

mynodes = [[0, 0, 0], [0, 0, 1], [0, 1, 0], [1, 1, 1]]
mytets = [[0, 1, 2, 3]]
