# $Id: exotools.py,v 1.13 2010/03/18 18:15:24 vgweirs Exp $

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import array # numpy would be better, grumble grumble...
import multiprocessing

#
# Note on indices: Since exodus was originally written in FORTRAN,
#   many of its arrays are indexed from 1; however, others are
#   indexed from 0.
#   Time steps are indexed from 1
#   Nodes are indexed from 1, howver, exodus.py translates them, so
#   e.g. exodus.readConn returns 0-based indices.
#   The lists of variables are 0-based.
#

#
# Issues with computing error norms:
# 1. element variable norms - both of these are difficult to solve without
#    a refactoring or a loss in efficiency.
#    a. ElemData2 subdiv functions return zfill=0.0 for 2D elements (quad4)
#       while without the subdiv, the zfill is set in get_element_norm
# 2. nodal variable norms
#    a. nodal variables are assumed to be constant in the dual-mesh elements
#    b. subdiv is not yet supported
#    c. at this point, the analytic solution (not meshmesh) is not well
#       tested, and might not work at all.
#
# Other issues:
# 1. Inconsistencies between generating lists and array.array objects
# 2. Inconistencies between storageType of array.array objects.
# 3. Poor comments, should make doc string accurate at least.
# 4. Error checking very weak
# 5. There are many ways to define characteristic element length; the
#    one implemented is arbitrary.
# 6. Consider logging module for output


########
# Be sure we can import the modules we need.

try:
   import exodus
   have_exodus = 1
except:
   have_exodus = 0
   
###############################################################################

def find_time_index(exoobj, desired_time, pcttol=1.0e-5):
   """Given an exodus file object and a specified time,
   return the time index.

   The time index is 1-based, i.e. the index of the first
   time step is 1.
   """

   times = exoobj.getTimes()
   n_t_sim = len(times) - 1  # the last time step index (0-based!)

   for time in times:
      if  time > desired_time:
         n_t_sim = times.index(time)
         if (time - desired_time) > (desired_time - times[n_t_sim-1]):
            n_t_sim = n_t_sim-1
            break

   # If there are a lot of closely spaced time steps a better test
   # would have, e.g. (times[n_t_sim] - times[n_t_sim - 1]) in the
   # denominator; eveutually add this as an option
   if not (desired_time == 0.0):
     if (abs(desired_time - times[n_t_sim])/ desired_time) > pcttol:
        print "Solution time differs significantly from desired solution time."

   # Add 1 to make it 1-based
   return n_t_sim+1

def get_current_coordinates(exoobj, time_idx1):
   """Return the physical coordinates at the time_idx1 specified. The
   coordinates are returned as an ndim length list, in which each list
   entry is an array.array object of length nnodes. The physical
   coordinates are the initial coordinated plus the displacements. If
   no displacement variables are found, the initial coordinates are
   returned. The time_idx1 is 1-based.
   """

   coords_initial = exoobj.readCoords()
   coords = []

   dvb = exoobj.findDisVarBase()
   lower = True
   if not dvb == None:
      displ_idx0 = exoobj.findVar( exodus.EX_NODE, dvb + "x" )
      if displ_idx0 == None:
         lower = False
         displ_idx0 = exoobj.findVar( exodus.EX_NODE, dvb + "X" )
         assert not displ_idx0 == None
      if lower:
         dvby = dvb + "y"
         dvbz = dvb + "z"
      else:
         dvby = dvb + "Y"
         dvbz = dvb + "Z"

   coordsx = array.array( exoobj.storageType() )
   objid = 0 # This is ignored because nodal variables don't have an objid
   if dvb == None:
      for n in range(len(coords_initial[0])):
         coordsx.append(coords_initial[0][n])
   else:
      # Got displ_idx0 for x above
      displ = exoobj.readVar(time_idx1, exodus.EX_NODE, objid, displ_idx0)
      for n in range(len(coords_initial[0])):
         coordsx.append(coords_initial[0][n] + displ[n])
   coords.append(coordsx)

   if exoobj.ndim > 1:
      coordsy = array.array( exoobj.storageType() )
      if dvb == None:
         for n in range(len(coords_initial[0])):
            coordsy.append(coords_initial[1][n])
      else:
         displ_idx0 = exoobj.findVar( exodus.EX_NODE, dvby )
         exoobj.readVar(time_idx1, exodus.EX_NODE, objid, displ_idx0, displ)
         for n in range(len(coords_initial[0])):
            coordsy.append(coords_initial[1][n] + displ[n])
      coords.append(coordsy)

   if exoobj.ndim > 2:
      coordsz = array.array( exoobj.storageType() )
      if dvb == None:
         for n in range(len(coords_initial[0])):
            coordsz.append(coords_initial[2][n])
      else:
         displ_idx0 = exoobj.findVar( exodus.EX_NODE, dvbz )
         exoobj.readVar(time_idx1, exodus.EX_NODE, objid, displ_idx0, displ)
         for n in range(len(coords_initial[0])):
            coordsz.append(coords_initial[2][n] + displ[n])
      coords.append(coordsz)

   return coords

def restructure_coordinates(x):
   """Given x, a list of length 1, 2, or 3, with each list entry a
   list of length n, return a list of length n, with each list entry a
   list of length 1, 2, or 3 (length of the input list.)

   The input lists of length n can actually be any iterables, but the
   returned object is always a list of lists.
   """

   x_len = len(x)
   if x_len<1 or x_len>3:
      print "Input list length is not in the expected range!"
   num = len(x[0])
   for xd in x:
      if not len(xd) == num:
         print "Input lists have different lengths!"

   # Reorder.
   r_coords = []
   for n in range(num):
      r_n = []
      for d in range(x_len):
         r_n.append(x[d][n])
      r_coords.append(r_n)

   return r_coords

def get_element_volumes(exoobj, block_id, time_idx1, vol_array = None):
   """Return the element volumes for block block_id at the time index
   time_idx1 specified; time_idx1 is 1-based. If provided, vol_array
   must be an array.array object of type storageType(), which is
   filled with the values; otherwise it is created."""

   # Add optional argument: input current reordered coordinates.
   # this allows greater efficiency when there are a large number of blocks

   import ElemData2
   
   # First get the current coordinates. Restructure from ndim arrays
   # of length num_nodes to one array (loosely)
   coords_1_ndim_nnodes = get_current_coordinates(exoobj, time_idx1)
   coords_1_nnodes_ndim = restructure_coordinates(coords_1_ndim_nnodes)

   # Make an array if needed
   if vol_array == None:
      vol_array = array.array( exoobj.storageType() )
   # and check errors if not...

   # What kind of element? How Many?
   (id,
    count,
    type_name,
    nodes_per,
    edges_per,
    faces_per,
    attrs_per) = exoobj.getBlock(exodus.EX_ELEM_BLOCK, block_id)

   # etype_info contains the function which calculates the volume
   etype_info = ElemData2.GetEtypeInfo(type_name)
   # Add error check: getEtypeInfo returns None if the element type is
   # not found...
   etype_info.keys()

   # Get the connectivity array for the block of interest
   # The returned node indices are zero-based
   conn = exoobj.readConn(exodus.EX_ELEM_BLOCK, block_id, exodus.EX_NODE)

   # Now, compute the volumes.
   for element in range(count):
      ecoords = []
      for node in range(nodes_per):
         ecoords.append(coords_1_nnodes_ndim[conn[element*nodes_per + node]])

      vol_array.append( etype_info['vol_func']( ecoords ) )

   return vol_array

def get_node_volumes(exoobj, time_idx1, vol_array = None):
   """Get the node volumes at the time index specified.  The time
   index is 1-based. If provided, vol_array must be an array.array
   object of type storageType(), which is filled with the values;
   otherwise it is created."""

   # Add optional argument: input current reordered coordinates.
   # this allows greater efficiency when there are a large number of blocks
   # current reordered coordinates would be passed to get_element_volumes

   # Basic strategy: For each block, first get the element volumes
   # then distribute the element volumes to the nodes.

   # Make an array if needed
   if vol_array == None:
      vol_array = array.array( exoobj.storageType() )
      for node in range(exoobj.getNumber(exodus.EX_NODE)):
         vol_array.append(0.0)
   # and check errors if not...

   for block_idx0 in range(exoobj.getNumber(exodus.EX_ELEM_BLOCK)):
      block_id = exoobj.getId(exodus.EX_ELEM_BLOCK, block_idx0)

      # What kind of element? How Many?
      (id,
       count,
       type_name,
       nodes_per,
       edges_per,
       faces_per,
       attrs_per) = exoobj.getBlock(exodus.EX_ELEM_BLOCK, block_id)

      nodes_per_i = 1.0/nodes_per

      # Get the element volumes for a block, then partition the volume
      # tothe element's nodes
      element_volumes = get_element_volumes(exoobj,
                                            block_id,
                                            time_idx1)

      # Get the connectivity array for the block
      # The returned node indices are zero-based
      conn = exoobj.readConn(exodus.EX_ELEM_BLOCK, block_id, exodus.EX_NODE)

      # Now, partition the element volume and distribute it to the nodes.
      for element in range(count):
         node_vol_part = nodes_per_i*element_volumes[element]
         for node in range(nodes_per):
            vol_array[conn[element*nodes_per + node]] += node_vol_part

   return vol_array

def construct_evar_array(typecode, func, idx_start, idx_end, nodes_per, subel_ints, rcoords, conn, etype_info, exact_time):
    'Construct evar_array'

    evar_array = array.array(typecode)

    for element in range(idx_start, idx_end):
        ecoords = []
        for node in range(nodes_per):
            ecoords.append(rcoords[ conn[element*nodes_per + node] ] )

        # subdivide element - this returns coordinates of centers of subelements
        subel_ctrs = etype_info['subdiv_func']( ecoords, subel_ints )

        # the exact solution at all subelement centers
        subel_exact = map((lambda x:func(x, exact_time)), subel_ctrs)

        # Now get subelement volumes.
        subel_vols = etype_info['subel_vols']( ecoords, subel_ints )

        # element average of exact solution:
        val_vol = 0.0
        for i in range(len(subel_exact)):
           val_vol += subel_exact[i]*subel_vols[i]
        elem_avg = val_vol/sum(subel_vols)

        evar_array.append( elem_avg )

    return evar_array

def construct_evar_array_parallel(conn_obj, typecode, func, idx_start, idx_end, nodes_per, subel_ints, rcoords, conn, etype_info, exact_time):
    'Multiprocessing worker function that constructs part of evar_array.'

    evar_array = construct_evar_array(typecode, func, idx_start, idx_end, nodes_per, subel_ints, rcoords, conn, etype_info, exact_time)

    conn_obj.send(evar_array)
    conn_obj.close()
    return

def avg_evar_on_block(processes,
                      exoobj,
                      block_id,
                      comp_t_idx1,
                      restructured_coords,
                      func_direct,
                      subel_ints = 5,
                      zfill=None,
                      evar_array = None):
   """Get the cell-average of a variable for block block_id at the
   time index comp_t_idx1 specified.

   If provided, evar_array must be an array.array object of type
   storageType(), which is filled with the values; otherwise it is
   created.

   If the exoobj mesh is 2D and zfill is provided, zfill is appended
   to the x and y values in restructured_coords for all nodes.
   """

   import operator
   import ElemData2

   # Get the time that matches the solution time_index (which
   # might not be the same as the test_time)
   exact_time = exoobj.getTimes()[comp_t_idx1 - 1]

   # Make an array if needed
   if evar_array == None:
      evar_array = array.array( exoobj.storageType() )
   # and check errors if not...

   # What kind of element? How Many?
   (id,
    count,
    type_name,
    nodes_per,
    edges_per,
    faces_per,
    attrs_per) = exoobj.getBlock(exodus.EX_ELEM_BLOCK, block_id)

   # etype_info contains the function which calculates the volume
   etype_info = ElemData2.GetEtypeInfo(type_name)
   # Add error check: getEtypeInfo returns None if the element type is
   # not found...
   if etype_info == None:
      print "Error: Element type not found!"

   # Make a deep copy of the restructured coordinates if we will have
   # to fill; if we don't fill, we can just use
   # restructured_coordinates because we don't modify it
   if exoobj.getDimension()==2 and not zfill==None:
      from copy import deepcopy
      rcoords = deepcopy(restructured_coords)
      for nc in rcoords:
         nc.append(zfill)
   else:
      rcoords = restructured_coords

   # Get the connectivity array for the block; this is needed to get
   # the node coordinates for each element
   conn = exoobj.readConn(exodus.EX_ELEM_BLOCK, block_id, exodus.EX_NODE)

   # Now, compute the element average of the variable.
   if processes <= 2:
       # No point in parallelizing for 2 processes, since only 1 child process would be created.
       evar_array.extend(construct_evar_array(evar_array.typecode, func_direct, 0, count, nodes_per, subel_ints, rcoords, conn, etype_info, exact_time))
   else:
       child_processes = processes - 1
       pipes = [(None, None) for i in range(child_processes)]
       process_list = [None for i in range(child_processes)]
       for process_number in range(child_processes):
           idx_start = (process_number * count) / child_processes
           idx_end = ((process_number+1) * count) / child_processes
           pipes[process_number] = multiprocessing.Pipe(False)
           p = multiprocessing.Process(target=construct_evar_array_parallel, args=(pipes[process_number][1], evar_array.typecode, func_direct, idx_start, idx_end, nodes_per, subel_ints, rcoords, conn, etype_info, exact_time,))
           process_list[process_number] = p
           p.start()
       for process_number in range(child_processes):
           p = process_list[process_number]
           idx_start = (process_number * count) / child_processes
           idx_end = ((process_number+1) * count) / child_processes
           conn_obj = pipes[process_number][0]
           evar_array_local = conn_obj.recv()
           evar_array.extend(evar_array_local)
           conn_obj.close()
           p.join()

   return evar_array

def get_element_length(exoobj, time):
   """Calculate the characteristic element length.

   The length of a 3D element is the cube root of the volume; for a 2D
   element it is the square root of the area.

   The characteristic element length is the average element length
   over the mesh.
   """

   from math import pow

   time_idx1 = find_time_index(exoobj, time)
   
   ndim = exoobj.getDimension()
   dexp = 1.0/ndim

   l_sum = 0.0
   e_sum = 0.0
   for block_idx0 in range(exoobj.getNumber(exodus.EX_ELEM_BLOCK)):
      block_id = exoobj.getId(exodus.EX_ELEM_BLOCK, block_idx0)
      element_volumes = get_element_volumes(exoobj,
                                            block_id,
                                            time_idx1)

      e_sum += len(element_volumes)

      for vol in element_volumes:
         l_sum += pow(abs(vol), dexp)

   return l_sum/e_sum

def element_norm_spatial(processes,
                         computed_solution,
                         test_time,
                         test_var_list,
                         exact_solution,
                         subel_ints = 1,
                         zfill=None,
                         block_ids=[]):
   """
   """

   # Accept a filename (string) or exodus object as the computed solution.
   comp_file_loaded = False
   if isinstance(computed_solution, str):
      comp_sol = exodus.ExodusFile(computed_solution)
      comp_file_loaded = True
   elif isinstance(computed_solution, exodus.ExodusFile):
      comp_sol = computed_solution
   else:
      # Unrecognized type
      print "Computed solution is not a recognized type."
      print "It should be either an exodus filename or an exodus file object."


   # Get the (1-based) index of the time for the computed solution
   comp_t_idx1 = find_time_index(comp_sol, test_time)
      
   # The (0-based) index of the variable in the computed solution
   comp_var_idx0  = comp_sol.findVar(exodus.EX_ELEM_BLOCK,
                                     test_var_list[0])

   # Add error checking for test_var_list?

   # If no list of block ids is given, generate a list including all blocks
   # We are matching block ids in the computed solution, but we already assume
   #   the mesh for the exact solution is (topologically) the same.
   if block_ids == []:
     for block_idx0 in range(comp_sol.getNumber(exodus.EX_ELEM_BLOCK)):
        block_ids.append(comp_sol.getId(exodus.EX_ELEM_BLOCK, block_idx0) )

   # Accept a filename or an exodus object or a solution object
   # as the exact solution
   exact_file_loaded = False
   meshmesh = False
   if isinstance(exact_solution, str):
      exact_sol = exodus.ExodusFile(exact_solution)
      exact_file_loaded = True
      meshmesh = True
      exact_t_idx1 = find_time_index(exact_sol, test_time)

      exact_var_idx0 = exact_sol.findVar(exodus.EX_ELEM_BLOCK,
                                         test_var_list[1])
   elif isinstance(exact_solution, exodus.ExodusFile):
      exact_sol = exact_solution
      meshmesh = True
      exact_t_idx1 = find_time_index(exact_sol, test_time)

      exact_var_idx0 = exact_sol.findVar(exodus.EX_ELEM_BLOCK,
                                         test_var_list[1])
   elif hasattr(exact_solution, test_var_list[1]):
      exact_sol = exact_solution

      # Ensure the analytic solution time matches the simulation data time
      exact_time = comp_sol.getTimes()[comp_t_idx1 - 1]

      # Refer directly to the attribute (method) we want
      func_direct = getattr(exact_sol, test_var_list[1])

      # Get nodal coords here rather than over and over for each element block
      # for subel_ints == 1 restructure after computing center coordinates,
      #   which happens in the block loop
      current_coordinates = get_current_coordinates(comp_sol, comp_t_idx1)
      if subel_ints > 1:
         restructured_coords = restructure_coordinates(current_coordinates)

   else:
      # Unrecognized type
      print "Exact solution is not a recognized type."
      print "It should be either an exodus filename, an exodus file object,"
      print "or an analytic solution object."


   # Add error check: See if we can actually compare data on different meshes
  
   # Initialize
   varET = WeightedErrorTally()

   ######## The work proper ########
   
   for block_id in block_ids:
      
      element_volumes = get_element_volumes(comp_sol,
                                            block_id,
                                            comp_t_idx1)

      comp_var = comp_sol.readVar(comp_t_idx1,
                                  exodus.EX_ELEM_BLOCK,
                                  block_id,
                                  comp_var_idx0)
      
      exact_var = array.array('d')

      if meshmesh:   # exact solution is already on the mesh; read it
         exact_sol.readVar(exact_t_idx1,
                           exodus.EX_ELEM_BLOCK,
                           block_id,
                           exact_var_idx0,
                           exact_var)
      else:          # exact solution will be calculated from a function

         if subel_ints == 1:
            # Evaluate the exact solution at the center of the element
            ctr_coords = comp_sol.computeCenters(exodus.EX_ELEM_BLOCK,
                                                 block_id,
                                                 current_coordinates)

            # Have to add the fill here because computeCenters knows
            #   the true number of dimensions
            if comp_sol.getDimension()==2 and not zfill==None:
               x2_fill = array.array(comp_sol.storageType())
               for i in range(len(ctr_coords[0])):
                  x2_fill.append(zfill)
               ctr_coords.append(x2_fill)
               
            r_coords = restructure_coordinates(ctr_coords)

            exact_var = map((lambda x:func_direct(x, exact_time)), r_coords)

         else:
            avg_evar_on_block(processes,
                              comp_sol,
                              block_id,
                              comp_t_idx1,
                              restructured_coords,
                              func_direct,
                              subel_ints,
                              zfill,
                              evar_array = exact_var)

      varET.w_accumulate(exact_var, comp_var, element_volumes)

   return varET

def element_norm_spatial_exofo(comp_sol,
                               comp_time,
                               comp_evar,
                               exact_sol,
                               exact_time=None,
                               exact_evar=None,
                               block_ids=[]):
   """
   Like element_norm_spatial but restricted input solution types.
   comp_sol and exact_sol must each be exodus.ExodusFile objects.

   exact_time and exact_evar are optional
   If exact_time is not given, comp_time is used as exact_time.
   If exact_evar is not given, comp_evar is used as exact_evar.
   """

   # Accept an exodus object as the computed solution.
   if not isinstance(comp_sol, exodus.ExodusFile):
      # Unrecognized type
      print "Computed solution is not a recognized type."
      print "It should be either an exodus.ExodusFile object."
      sys.exit(1)

   # Get the (1-based) index of the time for the computed solution
   comp_t_idx1 = find_time_index(comp_sol, comp_time)

   # The (0-based) index of the variable in the computed solution
   comp_var_idx0  = comp_sol.findVar(exodus.EX_ELEM_BLOCK, comp_evar)

   # If no list of block ids is given, generate a list including all blocks
   # We are matching block ids in the computed solution, but we already assume
   #   the mesh for the exact solution is (topologically) the same.
   if block_ids == []:
     for block_idx0 in range(comp_sol.getNumber(exodus.EX_ELEM_BLOCK)):
        block_ids.append(comp_sol.getId(exodus.EX_ELEM_BLOCK, block_idx0) )

   # Accept an exodus object as the exact solution
   if not isinstance(exact_sol, exodus.ExodusFile):
      # Unrecognized type
      print "Exact solution is not a recognized type."
      print "It should be an exodus.ExodusFile object."
      sys.exit(1)

   # Get the (1-based) index of the time for the exact solution
   if exact_time == None:
     exact_t_idx1 = find_time_index(exact_sol, comp_time)
   else:
     exact_t_idx1 = find_time_index(exact_sol, exact_time)

   # The (0-based) index of the variable in the exact solution
   if exact_evar == None: exact_evar = comp_evar
   exact_var_idx0 = exact_sol.findVar(exodus.EX_ELEM_BLOCK, exact_evar)

   # Add error check: See if we can actually compare data on different meshes
  
   # Initialize
   varET = WeightedErrorTally()

   ######## The work proper ########
   
   for block_id in block_ids:
      
      element_volumes = get_element_volumes(comp_sol,
                                            block_id,
                                            comp_t_idx1)

      comp_var = comp_sol.readVar(comp_t_idx1,
                                  exodus.EX_ELEM_BLOCK,
                                  block_id,
                                  comp_var_idx0)

      exact_var = exact_sol.readVar(exact_t_idx1,
                                    exodus.EX_ELEM_BLOCK,
                                    block_id,
                                    exact_var_idx0)
      
      varET.w_accumulate(exact_var, comp_var, element_volumes)
   return varET


def map_func(func, idx_start, idx_end, r_coords, exact_time):
    'map r_coords to val using func'

    val = map((lambda x:func(x, exact_time)), r_coords[idx_start:idx_end])

    return val

def map_func_parallel(conn_obj, func, idx_start, idx_end, r_coords, exact_time):
    'Multiprocessing worker function that maps r_coords to exact_var using func_direct.'

    val = map_func(func, idx_start, idx_end, r_coords, exact_time)

    conn_obj.send(val)
    conn_obj.close()

    return

def element_norm_spatial_exoao(processes,
                               comp_sol,
                               test_time,
                               test_var_list,
                               exact_solution,
                               subel_ints = 1,
                               zfill=None,
                               exact_time=None,
                               block_ids=[]):
   """
   This is element_norm_spatial but input solution types are limited. An
   exodus.ExodusFile object is expected for the computed solution, and an
   analytic solution object is expected for the exact solution.

   if exact_time is not given, the exact_solution is evaluated at test_time
   """

   # Accept an exodus object as the computed solution.
   if not isinstance(comp_sol, exodus.ExodusFile):
      # Unrecognized type
      print "Computed solution is not a recognized type."
      print "It should be either an exodus.ExodusFile object."
      sys.exit(1)

   # Get the (1-based) index of the time for the computed solution
   comp_t_idx1 = find_time_index(comp_sol, test_time)
      
   # The (0-based) index of the variable in the computed solution
   comp_var_idx0  = comp_sol.findVar(exodus.EX_ELEM_BLOCK,
                                     test_var_list[0])

   # Add error checking for test_var_list?

   # If no list of block ids is given, generate a list including all blocks
   if block_ids == []:
     for block_idx0 in range(comp_sol.getNumber(exodus.EX_ELEM_BLOCK)):
        block_ids.append(comp_sol.getId(exodus.EX_ELEM_BLOCK, block_idx0) )

   # Accept a solution object as the exact solution
   if hasattr(exact_solution, test_var_list[1]):
      exact_sol = exact_solution

      # If not overridden by exact_time argument, ensure the
      # analytic solution time matches the simulation data time
      if exact_time == None:
        exact_time = comp_sol.getTimes()[comp_t_idx1 - 1]

      # Refer directly to the attribute (method) we want
      func_direct = getattr(exact_sol, test_var_list[1])

      # Get nodal coords here rather than over and over for each element block
      # for subel_ints == 1 restructure after computing center coordinates,
      #   which happens in the block loop
      current_coordinates = get_current_coordinates(comp_sol, comp_t_idx1)
      if subel_ints > 1:
         restructured_coords = restructure_coordinates(current_coordinates)

   else:
      # Unrecognized type
      print "Exact solution is not a recognized type."
      print "It should be an analytic solution object."
      sys.exit(1)

   # Initialize
   varET = WeightedErrorTally()

   ######## The work proper ########
   
   for block_id in block_ids:
      
      element_volumes = get_element_volumes(comp_sol,
                                            block_id,
                                            comp_t_idx1)

      comp_var = comp_sol.readVar(comp_t_idx1,
                                  exodus.EX_ELEM_BLOCK,
                                  block_id,
                                  comp_var_idx0)
      
      exact_var = array.array('d')

      # exact solution will be calculated from a function
      if subel_ints == 1:
         # Evaluate the exact solution at the center of the element
         ctr_coords = comp_sol.computeCenters(exodus.EX_ELEM_BLOCK,
                                              block_id,
                                              current_coordinates)

         # Have to add the fill here because computeCenters knows
         #   the true number of dimensions
         if comp_sol.getDimension()==2 and not zfill==None:
            x2_fill = array.array(comp_sol.storageType())
            for i in range(len(ctr_coords[0])):
               x2_fill.append(zfill)
            ctr_coords.append(x2_fill)
               
         r_coords = restructure_coordinates(ctr_coords)

         len_r_coords = len(r_coords)
         if processes <= 2:
             # No point in parallelizing for 2 processes, since only 1 child process would be created.
             exact_var = map_func(func_direct, 0, len_r_coords, r_coords, exact_time)
         else:
             child_processes = processes - 1
             exact_var = [None for i in range(len_r_coords)]
             pipes = [(None, None) for i in range(child_processes)]
             process_list = [None for i in range(child_processes)]
             for process_number in range(child_processes):
                 idx_start = (process_number * len_r_coords) / child_processes
                 idx_end = ((process_number+1) * len_r_coords) / child_processes
                 pipes[process_number] = multiprocessing.Pipe(False)
                 p = multiprocessing.Process(target=map_func_parallel, args=(pipes[process_number][1], func_direct, idx_start, idx_end, r_coords, exact_time,))
                 process_list[process_number] = p
                 p.start()
             for process_number in range(child_processes):
                 p = process_list[process_number]
                 idx_start = (process_number * len_r_coords) / child_processes
                 idx_end = ((process_number+1) * len_r_coords) / child_processes
                 conn_obj = pipes[process_number][0]
                 exact_var_local = conn_obj.recv()
                 for idx in range(idx_start, idx_end):
                   exact_var[idx] = exact_var_local[idx - idx_start]
                 conn_obj.close()
                 p.join()


      else:
         avg_evar_on_block(processes,
                           comp_sol,
                           block_id,
                           comp_t_idx1,
                           restructured_coords,
                           func_direct,
                           subel_ints,
                           zfill,
                           evar_array = exact_var)

      varET.w_accumulate(exact_var, comp_var, element_volumes)

   return varET

def node_norm_spatial(computed_solution,
                      test_time,
                      test_var_list,
                      exact_solution,
                      subel_ints = 1,
                      zfill=None):
   """
   At this time, subel_ints is ignored.
   """

   # Accept a filename (string) as the computed solution.
   comp_file_loaded = False
   if isinstance(computed_solution, str):
      comp_sol = exodus.ExodusFile(computed_solution)
      comp_file_loaded = True
   else:
      # Unrecognized type
      print "Computed solution is not a recognized type."
      print "It should be either an exodus filename or an exodus file object."

   # Get the (1-based) index of the time for the computed solution
   comp_t_idx1 = find_time_index(comp_sol, test_time)
      
   # The (0-based) index of the variable in the computed solution
   comp_var_idx0  = comp_sol.findVar(exodus.EX_NODE,
                                     test_var_list[0])

   # Add error check: test_var not found?

   # Accept a filename or an exodus object or a solution object
   # as the exact solution
   exact_file_loaded = False
   meshmesh = False
   if isinstance(exact_solution, str):
      exact_sol = exodus.ExodusFile(exact_solution)
      exact_file_loaded = True
      meshmesh = True
      exact_t_idx1 = find_time_index(exact_sol, test_time)
      exact_var_idx0 = exact_sol.findVar(exodus.EX_NODE,
                                         test_var_list[1])
   elif isinstance(exact_solution,exodus.ExodusFile):
      exact_sol = exact_solution
      meshmesh = True
      exact_t_idx1 = find_time_index(exact_sol, test_time)
      exact_var_idx0 = exact_sol.findVar(exodus.EX_NODE,
                                         test_var_list[1])
   elif hasattr(exact_solution, test_var_list[1]):
      exact_sol = exact_solution

      # Ensure the analytic solution time matches the simulation data time
      exact_time = comp_sol.getTimes()[comp_t_idx1 - 1]

      # Refer directly to the attribute (method) we want
      func_direct = getattr(exact_sol, test_var_list[1])

      # Get nodal coords here rather than over and over for each element block
      # for subel_ints == 1 restructure after computing center coordinates,
      #   which happens in the block loop
      current_coordinates = get_current_coordinates(comp_sol, comp_t_idx1)
      restructured_coords = restructure_coordinates(current_coordinates)
      if comp_sol.getDimension()==2 and not zfill==None:
         for nc in restructured_coords:
            nc.append(zfill)
      
   else:
      # Unrecognized type
      print "Exact solution is not a recognized type."
      print "It should be either an exodus filename, an exodus file object,"
      print "or an analytic solution object."

   # Add error check: See if we can actually compare data on different meshes
  
   # Initialize
   varET = WeightedErrorTally()

   ######## The work proper ########

   node_volumes = get_node_volumes(comp_sol, comp_t_idx1)

   # Sweep over the nodes and compute the norms

   comp_var = comp_sol.readVar(comp_t_idx1,
                               exodus.EX_NODE,
                               0,
                               comp_var_idx0)

   if meshmesh:   # exact solution is already on the mesh; read it
      exact_var = array.array(exact_sol.storageType())
      exact_sol.readVar(exact_t_idx1,
                        exodus.EX_NODE,
                        0,
                        exact_var_idx0,
                        exact_var)
   else:          # exact solution will be calculated from a function
      exact_var =  map((lambda x:func_direct(x, exact_time)),
                       restructured_coords)

   varET.w_accumulate(exact_var, comp_var, node_volumes)


def node_norm_spatial_exofo(comp_sol,
                            comp_time,
                            comp_nvar,
                            exact_sol,
                            exact_time=None,
                            exact_nvar=None):
   """
   This is node_norm_spatial but input solution types are limited.
   Both comp_sol and exact_sol must be exodus.ExodusFile objects.

   exact_time and exact_nvar are optional
   If exact_time is not given, comp_time is used as exact_time.
   If exact_nvar is not given, comp_nvar is used as exact_nvar.
   """

   # Accept an exodus object as the computed solution.
   if not isinstance(comp_sol, exodus.ExodusFile):
      # Unrecognized type
      print "Computed solution is not a recognized type."
      print "It should be either an exodus.ExodusFile object."
      sys.exit(1)

   # Get the (1-based) index of the time for the computed solution
   comp_t_idx1 = find_time_index(comp_sol, comp_time)

   # The (0-based) index of the variable in the computed solution
   comp_var_idx0  = comp_sol.findVar(exodus.EX_NODE, comp_nvar)

   # Accept an exodus object as the exact solution
   if not isinstance(exact_sol, exodus.ExodusFile):
      # Unrecognized type
      print "Exact solution is not a recognized type."
      print "It should be an exodus.ExodusFile object."
      sys.exit(1)

   # Get the (1-based) index of the time for the exact solution
   if exact_time == None: 
     exact_t_idx1 = find_time_index(exact_sol, comp_time)
   else:
     exact_t_idx1 = find_time_index(exact_sol, exact_time)

   # The (0-based) index of the variable in the exact solution
   if exact_nvar == None: exact_nvar = comp_nvar
   exact_var_idx0 = exact_sol.findVar(exodus.EX_NODE, exact_nvar)

   # Add error check: See if we can actually compare data on different meshes
  
   # Initialize
   varET = WeightedErrorTally()

   ######## The work proper ########

   node_volumes = get_node_volumes(comp_sol, comp_t_idx1)

   # Sweep over the nodes and compute the norms

   comp_var = comp_sol.readVar(comp_t_idx1,
                               exodus.EX_NODE,
                               0,
                               comp_var_idx0)

   exact_var = exact_sol.readVar(exact_t_idx1,
                                 exodus.EX_NODE,
                                 0,
                                 exact_var_idx0)

   varET.w_accumulate(exact_var, comp_var, node_volumes)

   return varET

def node_norm_spatial_exoao(comp_sol,
                            test_time,
                            test_var_list,
                            exact_solution,
                            subel_ints = 1,
                            zfill=None,
                            exact_time=None):
   """
   This is node_norm_spatial but input solution types are limited. A
   (string) exodus filename is expected for the computed solution, and an
   analytic solution object is expected for the exact solution.

   if exact_time is not given, the exact_solution is evaluated at test_time
   At this time, subel_ints is ignored.
   """

   # Accept an exodus object as the computed solution.
   if not isinstance(comp_sol, exodus.ExodusFile):
      # Unrecognized type
      print "Computed solution is not a recognized type."
      print "It should be either an exodus.ExodusFile object."
      sys.exit(1)

   # Get the (1-based) index of the time for the computed solution
   comp_t_idx1 = find_time_index(comp_sol, test_time)
      
   # The (0-based) index of the variable in the computed solution
   comp_var_idx0  = comp_sol.findVar(exodus.EX_NODE,
                                     test_var_list[0])

   # Add error check: test_var not found?

   # Accept a solution object as the exact solution
   if hasattr(exact_solution, test_var_list[1]):
      exact_sol = exact_solution

      # If not overridden by exact_time argument, ensure the
      # analytic solution time matches the simulation data time
      if exact_time == None:
        exact_time = comp_sol.getTimes()[comp_t_idx1 - 1]

      # Refer directly to the attribute (method) we want
      func_direct = getattr(exact_sol, test_var_list[1])

      # Get nodal coords here rather than over and over for each element block
      # for subel_ints == 1 restructure after computing center coordinates,
      #   which happens in the block loop
      current_coordinates = get_current_coordinates(comp_sol, comp_t_idx1)
      restructured_coords = restructure_coordinates(current_coordinates)
      if comp_sol.getDimension()==2 and not zfill==None:
         for nc in restructured_coords:
            nc.append(zfill)
      
   else:
      # Unrecognized type
      print "Exact solution is not a recognized type."
      print "It should be an analytic solution object."
      sys.exit(1)

   # Initialize
   varET = WeightedErrorTally()

   ######## The work proper ########

   node_volumes = get_node_volumes(comp_sol, comp_t_idx1)

   # Sweep over the nodes and compute the norms

   comp_var = comp_sol.readVar(comp_t_idx1,
                               exodus.EX_NODE,
                               0,
                               comp_var_idx0)

   # exact solution will be calculated from a function
   exact_var =  map( (lambda x:func_direct(x, exact_time)),
                     restructured_coords)

   varET.w_accumulate(exact_var, comp_var, node_volumes)

   return varET

##############################################################################

def WriteGlobalsToExodusFile(data, times, ftitle="", fname="Globals.exo"):
   """Write an exodus file which contains only global variables.

   times - the list of times (same for all variables in data).
   data - a list of dictionaries, each dictionary corresponding
     to a global variable to be written. The dictionary keys and
     values are:
     "varname"    (string) variable name (exodus requires 32 characters
                     or less)
     "varvals"    a list of variable values corresponding to times

   """

   # always write double precision exodus
   storage_type = 'd'

   nt = len(times)

   # Make the list of variables so we can put them in the header
   # Also, minimal checks on data
   varnames = []
   for vn in data.keys():
      # Check that varnames are 32 chars or less
      if len(vn) > 32:
        print "Variable name " + vn + " is to long."
        print "Exodus limit is 32 characters"
        sys.exit(1)
      else:
        varnames.append(vn)
      # Check that there are the right number of values
      nvals = len(data[vn])
      if not nvals == nt:
        print "There are " + str(nvals) + " values for " + vn + " but " + \
              str(nt) + " were expected."
        sys.exit(1)
      

   # Initial header info.
   newf = exodus.ExodusFile()
   newf.createFile( fname, storage_type=storage_type )
   newf.setDimension(1)
   newf.setTitle(ftitle)
   newf.setSizes( 0, 0, 0, 0,
                  0, 0, 0,
                  0, 0, 0, 0, 0,
                  0, 0, 0, 0 )
   newf.putInit()
   newf.putVarNames( exodus.EX_GLOBAL, varnames )

   times.sort()  # Just in case, sort the times.
   i=0

   for time in times:
      newf.putTime(i+1,time)             # For putTime and putVar (below), 
                                         #   shift i by one for exodus indices
      a = array.array( storage_type )
      for vn in varnames:  # varnames list preserves order; data dict may not
         a.append(data[vn][i])    # list index i is zero-based
      newf.putVar( a, i+1, exodus.EX_GLOBAL, 0, 0 )
      i=i+1

   newf.closefile()

   return

##############################################################################

def hardDiff(value1, value2):
    return abs(value1 - value2)


def softDiff(value1, value2, \
             abs_tolerance=1.0e-12, rel_tolerance=1.0e-12, \
             floor=1.0e-15):
    diff = 0.0
    adiff = abs(value1-value2)
    if  value1 != 0.0 :
      rdiff = abs((value1-value2)/value1)
    elif value2 != 0.0 :
      rdiff = abs((value1-value2)/value2)
    else :
      rdiff = 0.0

    if abs(value1) > floor or abs(value2) > floor :
      if adiff > abs_tolerance: diff = adiff

      if rdiff > rel_tolerance: diff = rdiff

    return diff

def CompareSList(sl1, sl2, case=True, sort=True):
    """Compare two lists of strings. Return True or False depending
    on whether the lists match.

    Each string from the first list is compared to the corresponding
    string from the second list.

    If case is True, the corresponding strings must match in case.
    If sort is True, both lists will be sorted before comparing strings.
    """

    if not len(sl1) == len(sl2):
      return False

    if case:
      first = sl1[:]    # Make a copy; otherwise you may
      second = sl2[:]   # inadvertently sort the list
    else:
      first = []
      second = []
      for s in sl1:
        first.append(s.lower())
      for s in sl2:
        second.append(s.lower())

    if not sort:
      return first==second
    else:
      return first.sort()==second.sort()

def CompareFList(fl1, fl2, sort=False, soft=True, atol=1.0e-12,
                                                  rtol=1.0e-12,
                                                  floor=1.0e-15):
    """Compare two lists of floats or ints. Return True or False
    depending on whether the lists match.

    Each number from the first list is compared to the corresponding
    number from the second list.

    If sort is True, both lists will be sorted before comparing numbers.
    If soft is True, a softDiff will be used to compare the numbers,
      and the optional parameters atol, rtol, and floor will be relevant.
      Otherwise the comparison will be absolute and even roundoff-level
      differences in the numbers will cause the comparision to return
      False.
    """

    if not len(fl1) == len(fl2):
      return False
    
    if sort:
      first=fl1.sort()
      second=fl2.sort()
    else:
      first = fl1
      second = fl2

    if not soft:
      return first==second
    else:
      for i in range(len(first)):
        sdiff = softDiff(first[i], second[i], abs_tolerance=atol,
                                              rel_tolerance=rtol,
                                              floor=floor)
    # return what?


def varCompare( varnames_1, varnames_2 ):
    Pass = True
    for var1 in varnames_1:
      found = False
      for var2 in varnames_2:
        if var1.lower() == var2.lower():
          found = True
          break
      if not found:
        Pass = False
        break

    return Pass


def timesCompare( times_1, times_2, times ):
    Pass = True

    found1 = False
    found2 = False
    for item in times:
      time = item[1]
      for index in range(len(times_1)):
        if not softDiff(time, times_1[index]):
          found1 = True
          break
      for index in range(len(times_2)):
        if not softDiff(time, times_2[index]):
          found2 = True
          break

    if found1 and found2:
      Pass = True
    else :
      Pass = False

    return Pass

def coordsCompare( ndims, coords_1, coords_2 ):
    Pass = True

    if len(coords_1[0]) != len(coords_2[0]) :
      Pass = False
      print "Number of nodes does not match:", \
            str(len(coords_1[0])), " != ", str(len(coords_2[0]))
      return Pass

    for dim in range(ndims):
      coord1 = coords_1[dim]
      coord2 = coords_2[dim]
      for index in range(len(coord1)):
        diff = softDiff(coord1[index], coord2[index])
        if diff:
          Pass = False
          if dim == 0 : print "  Following x coordinates do not match!"
          if dim == 1 : print "  Following y coordinates do not match!"
          if dim == 2 : print "  Following z coordinates do not match!"
          print "  ", coord1[index], "  ", coord2[index], " diff = ", diff
          return Pass

    return Pass

def compare_exoduses( exoapi_1, file1, exoapi_2, file2, times):
##def compare_exoduses( file1, file2, times):
    """
    Compare everything between two Exodus files, except the solution.
    If anything differs, the return value is False, otherwise it is True.
    Currently this means an exact match!
    """
##
##    exoapi_1 = exodus.ExodusFile(file1)
##    exoapi_2 = exodus.ExodusFile(file2)
##

    error_found = False

    ndim_1 = exoapi_1.getDimension()
    ndim_2 = exoapi_1.getDimension()
    if hardDiff ( ndim_1, ndim_2 ) :
      error_found = True
      print "Number of dimensions do not match between"
      print "    " + file1 + ": Number of dimensions = " + str(ndim_1)
      print "    " + file2 + ": Number of dimensions = " + str(ndim_2)

    exdict = {}
    exdict[exodus.EX_ELEM_BLOCK] = 'EX_ELEM_BLOCK'
    #exdict[exodus.EX_EDGE_BLOCK] = 'EX_EDGE_BLOCK'
    #exdict[exodus.EX_FACE_BLOCK] = 'EX_FACE_BLOCK'
    exdict[exodus.EX_NODE      ] = 'EX_NODE'
    #exdict[exodus.EX_EDGE      ] = 'EX_EDGE'
    #exdict[exodus.EX_FACE      ] = 'EX_FACE'
    exdict[exodus.EX_ELEM      ] = 'EX_ELEM'
    for exs in exdict.keys():
      ex_str = exdict[exs]
      number_1 = exoapi_1.getNumber(exs)
      number_2 = exoapi_2.getNumber(exs)
      if hardDiff ( number_1, number_2 ) :
        error_found = True
        print "Number of objects (" + ex_str + ") do not match between"
        print "    " + file1 + ": Number of objects = " + str(number_1)
        print "    " + file2 + ": Number of objects = " + str(number_2)

    exlist = []
    exlist.append(exodus.EX_NODE)
    exlist.append(exodus.EX_EDGE)
    exlist.append(exodus.EX_FACE)
    exlist.append(exodus.EX_ELEM)
    for exs in exlist:
      varnames_1 = exoapi_1.varNames(exs)
      varnames_2 = exoapi_2.varNames(exs)
      if not varCompare( varnames_1, varnames_2 ):
        error_found = True
        print "Variable names do not match."
        print "    Variable names: " + file1
        for vname in varnames_1:
           print "      " + vname
        print "    Variable names: " + file2
        for vname in varnames_2:
           print "      " + vname

    times_1 = exoapi_1.getTimes()
    times_2 = exoapi_2.getTimes()
    if not timesCompare( times_1, times_2, times ):
      error_found = True
      print "Not all times are in common between files."
      print "     Time stamps:"
      for time in times:
         print "      ", time[1]
      print "     Time stamps:" + file1
      for time in times_1:
         print "      ", time
      print "     Time stamps:" + file2
      for time in times_2:
         print "      ", time

    bid_1 = exoapi_1.getIds( exodus.EX_ELEM_BLOCK )
    bid_2 = exoapi_2.getIds( exodus.EX_ELEM_BLOCK )
    if ( bid_1 != bid_2 ):
      error_found = True
      print "Element Block Ids do not match between"
      print "    " + file1 + ": Element Block Ids"
      for bid in bid_1:
         print "      " + str(bid)
      print "    " + file2 + ": Element Block Ids"
      for bid in bid_2:
         print "      " + str(bid)

    for bid in bid_1:
      conn_1 = exoapi_1.readConn( exodus.EX_ELEM_BLOCK, bid, exodus.EX_NODE )
      conn_2 = exoapi_2.readConn( exodus.EX_ELEM_BLOCK, bid, exodus.EX_NODE )
      if ( conn_1 != conn_2 ):
        error_found = True
        print "Node Connectivity for Element Block Id=" + str(bid) + \
              ", do not match between"
        print "    " + file1 + ": Length of connectivity array = " + \
              str(len(conn_1))
        print "    " + file2 + ": Length of connectivity array = " + \
              str(len(conn_2))

    coords_1 = exoapi_1.readCoords()
    coords_2 = exoapi_2.readCoords()
    if not coordsCompare( ndim_1, coords_1, coords_2 ): error_found = True

    if error_found:
      sys.exit(1)

    return True

##############################################################################

class WeightedErrorTally:
   """ Tally errors without storing much data.

   Computes L1, L2, and L-Infinity norms.

   These Norms are weighted by the weights passed in with the computed
   and analytic solutions.  This allows computing, e.g. error norms
   integrated over a mesh of elements of different sizes, where the
   element volumes are the weights.

   Also tracks max and min values of the analytic and computed solutions
   and the sum of the weights.
   """

   def __init__(self):

      self.N = 0
      self.W_sum = 0.0
      self.E1_sum = 0.0
      self.E2_sum = 0.0
      self.E_max = 0.0
      self.A1_sum = 0.0
      self.A2_sum = 0.0
      self.A_min = 1.0e300
      self.A_max = -1.0e300
      self.A_abs_max = -1.0e300
      self.C1_sum = 0.0
      self.C2_sum = 0.0
      self.C_min = 1.0e300
      self.C_max = -1.0e300

   def L2(self):
      """The standard L2 norm. Weighted integral over sum of weights."""
      from math import sqrt
      return sqrt( self.E2_sum / self.W_sum )

   def L1(self):
      """The standard L1 norm. Weighted integral over sum of weights."""
      return  self.E1_sum / self.W_sum 

   def L_inf(self):
      """The standard L-Infinity norm. Maximum error."""
      return  self.E_max

   def RL2(self):
      """The relative L2 norm. Weighted error integral over weighted
      reference integral."""
      if (self.A2_sum == 0.0): RL2 = self.L2()
      else:
                               from math import sqrt
                               RL2 = sqrt( self.E2_sum / self.A2_sum )
      return RL2

   def RL1(self):
      """The relative L1 norm. Weighted error integral over weighted
      reference integral."""
      if (self.A1_sum == 0.0): RL1 = self.L1()
      else:                    RL1 = self.E1_sum / self.A1_sum 
      return RL1

   def RL_inf(self):
      """The relative L-Infinity norm. Maximum error over maximum
      reference value. """
      if (self.A_abs_max == 0.0): RL_inf = self.L_inf()
      else:                   RL_inf = self.E_max/self.A_abs_max
      return RL_inf

   def w_accumulate( self, analytic, code, weight ):
      """Add error contribution to various totals.

      Input analytic, code, and weight are all lists which should
      be the same length; this allows accumulating many points
      with a single call.
      """

      # make sure list lengths are the same
      if ( len(analytic) != len(code) or
           len(analytic) != len(weight) ):
        print "   Error in w_accumulate! "
        print "   List lengths do not match! "

      self.N += len(code)

      for i in range(len(code)):
         
         error = abs( analytic[i] - code[i] )
         self.W_sum += weight[i]

         self.E1_sum += weight[i] *  error 
         self.E2_sum += weight[i] *  error**2
         self.E_max  = max( self.E_max,  error ) 

         self.A1_sum += weight[i] *  abs( analytic[i] )
         self.A2_sum += weight[i] *  ( analytic[i] )**2
         self.A_min  = min( self.A_min, analytic[i] )
         self.A_max  = max( self.A_max, analytic[i] )
         self.A_abs_max  = max( self.A_abs_max, abs( analytic[i] ) )

         self.C1_sum += weight[i] *  abs( code[i] )
         self.C2_sum += weight[i] *  ( code[i] )**2
         self.C_min  = min( self.C_min, code[i] )
         self.C_max  = max( self.C_max, code[i] )

   def w_accumulate_vec( self, analytic, code, weight, dim ):
      """Add error contribution to various totals.

      Input analytic, code, and weight are all lists which should
      be the same length; this allows accumulating many points
      with a single call. Also, elements of analytic and code should
      be lists of dim variables.
      """

      # make sure list lengths are the same
      if ( len(analytic) != len(code) != len(weight) ):
        print "   Error in w_accumulate! "
        print "   List lengths do not match! "

      self.N += len(code)
      for i in range(len(code)):
         error1=0
         error2=0
         for j in range(0,dim):
            error1+=abs( analytic[i][j] - code[i][j])
         for j in range(0,dim):
            error1+=abs( analytic[i][j] - code[i][j])
            error2+=abs( analytic[i][j] - code[i][j])**2

         self.W_sum += weight[i]

         self.E1_sum += weight[i] *  error1
         self.E2_sum += weight[i] *  error2
         self.E_max  = max( self.E_max,  error1 )

# Can't get the min of a scalar and a vector. Commented out until I decide what
# to do about it.

#         self.A_min  = min( self.A_min, analytic[i] )
#         self.A_max  = max( self.A_max, analytic[i] )

#         self.C_min  = min( self.C_min, code[i] )
#         self.C_max  = max( self.C_max, code[i] )


   

