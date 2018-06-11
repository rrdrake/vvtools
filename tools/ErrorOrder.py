#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

# Error and Order class for use by tools like vcomp and vdiff.

from math import *
import exotools
import exodus
import array
import copy
import sys
import os

def Get_EO_CFName(cfname,fname=None):
    (dirname, basename) = os.path.split(cfname)
    (head, ext) = os.path.splitext(basename)
    if fname == None:
      head = head + "_eo" + ext
    else:
      head = head + "_" + fname + "_eo" + ext
    return os.path.join(dirname,head)


class ErrorOrder(object):
    """
    Container class of the error norms and order of accuracies between
    the reference solution and the computed solutions.
    """
    def __init__(self, ref_type):
        self.reference_type = ref_type
        self.computed_filenames = []
        self.resolutions = {}
        self.norms = {}
        self.orders = {}
        self.times = []
        self.varnames = []

    def SetComparisonFileNames(self, cfname, h, dt):
        try:
          index = self.computed_filenames.index(cfname)
        except:
          self.computed_filenames.append(cfname)

        self.resolutions[cfname] = (float(h), float(dt))

    def SetTimes(self, times):
        """'times' is a list of time index and time pairs."""
        self.times = times

    def SetOrders(self, orders):
        self.orders = orders

    def SetObjectTypes(self, ots):
        self.objtypes = ots

    def SetVarNames(self, varnames):
        self.varnames = varnames

    def setNorm(self, cfname, time, var, varET):

        try:
          index = self.computed_filenames.index(cfname)
        except:
          self.computed_filenames.append(cfname)

        try:
          index = self.times.index(time)
        except:
          self.times.append(time)

        try:
          index = self.varnames.index(var)
        except:
          self.varnames.append(var)

        varNorms = {}
        timeNorms = {}
        if self.norms.has_key(cfname):
          timeNorms = self.norms[comparison_filename]
          if timeNorms.has_key(time): varNorms = timeNorms[time]

        varNorms[var.lower()] = (varET.L_inf(), varET.L1(), varET.L2(),\
                                 varET.RL_inf(), varET.RL1(), varET.RL2())
        timeNorms[time] = varNorms
        self.norms[cfname] = timeNorms


    def CalculateNormsFromExtrapolated(self, tovb_var_values_e, bid_list=[]):
        """
        Generate the error norms between solutions.
        """
    
        for cfname in self.computed_filenames:
          exoapi_c = exodus.ExodusFile(cfname)

          timeNorms = {}
          for item in self.times:
            time       = item[1]

            times_c = exoapi_c.getTimes()
            time_index_c = 0
            for index in range(len(times_c)):
              if not exotools.softDiff(time, times_c[index]):
                time_index_c = index 
                break

            ovb_var_values_e = tovb_var_values_e[time]
            varNorms = {}
            for objtype in self.objtypes:
              vb_var_values_e = ovb_var_values_e[objtype]
              cvars = exoapi_c.varNames( objtype )
              myvars = self.varnames
              obvars = []
              for cvar in cvars:
                for myvar in myvars:
                  if cvar.lower() == myvar.lower(): obvars.append(cvar)
      
              for var in obvars:
                b_var_values_e = vb_var_values_e[var.lower()]
                var_index_c  = exoapi_c.findVar( objtype, var )
                var_values_c = array.array( exoapi_c.storageType() )
      
                # bids = []
                if objtype == exodus.EX_NODE : bids=[0]
                if objtype == exodus.EX_ELEM :
                  if bid_list==[]:
                    bids = exoapi_c.getIds( exodus.EX_ELEM_BLOCK )
                  else:
                    bids = bid_list

                varET = exotools.WeightedErrorTally()      
                for bid in bids:
                  var_values_e = b_var_values_e[bid]
                  exoapi_c.readVar(time_index_c+1, objtype,
                                   bid, var_index_c, var_values_c)
      
                  if objtype == exodus.EX_ELEM :
                    volumes = exotools.get_element_volumes(exoapi_c, bid, 
                                                           time_index_c+1)
                  if objtype == exodus.EX_NODE :
                    volumes = exotools.get_node_volumes(exoapi_c, 
                                                        time_index_c+1)
      
                  varET.w_accumulate(var_values_e, var_values_c, volumes)
      
                varNorms[var.lower()] = (varET.L_inf(),
                                         varET.L1(), 
                                         varET.L2(),
                                         varET.RL_inf(), 
                                         varET.RL1(), 
                                         varET.RL2())
      
            timeNorms[time] = varNorms
      
          self.norms[cfname] = timeNorms
          exoapi_c.closefile()
    
        return


    def CalculateNormsFromFiles(self, file_sols, file_times=[], bid_list=[]):
        """
        Generate the error norms between solutions.
        """

        n_fsols = len(file_sols)
        if n_fsols == 1:
           exact_sol = exodus.ExodusFile( file_sols[0][0] )
        n=0

        # Now, for each computed solution compute the error norms
        for cfname in self.computed_filenames:
          if n_fsols != 1:
            exact_sol = exodus.ExodusFile( file_sols[n][0] )
            n = n+1
     
          comp_sol = exodus.ExodusFile(cfname)

          # get list of element and node variables
          elem_vars = comp_sol.varNames( exodus.EX_ELEM )
          node_vars = comp_sol.varNames( exodus.EX_NODE )

          # Get the lists of variables to compare
          elem_var_list = []
          node_var_list = []
          for var in self.varnames:
             if var in elem_vars:
               elem_var_list.append(var)
             elif var in node_vars:
               node_var_list.append(var)
             else:
               print "Error: Variable " + var +" not found in " + cfname
               sys.exit(1)
          # Assume that check for var in exact solution file was done earlier
            
          timeNorms = {}
          m = 0
          for item in self.times:
            time       = item[1]
            if not file_times==[]:
               etime = file_times[m]
            else:
               etime = time

            varNorms = {}

            # Element variables
            for comp_evar in elem_var_list:
              varET = exotools.element_norm_spatial_exofo(comp_sol,
                                                          time,
                                                          comp_evar,
                                                          exact_sol,
                                                          exact_time=etime,
                                                          block_ids=bid_list)
              varNorms[comp_evar.lower()] = ( varET.L_inf(),
                                              varET.L1(), 
                                              varET.L2(), 
                                              varET.RL_inf(), 
                                              varET.RL1(), 
                                              varET.RL2() )
            
            # Nodal variables
            for comp_nvar in node_var_list:
              varET = exotools.node_norm_spatial_exofo(comp_sol,
                                                       time,
                                                       comp_nvar,
                                                       exact_sol,
                                                       exact_time=etime)
              varNorms[comp_nvar.lower()] = ( varET.L_inf(),
                                              varET.L1(), 
                                              varET.L2(), 
                                              varET.RL_inf(), 
                                              varET.RL1(), 
                                              varET.RL2() )

            timeNorms[time] = varNorms
            m = m+1
      
          self.norms[cfname] = timeNorms
          comp_sol.closefile()
          if n_fsols != 1: exact_sol.closefile()

        if n_fsols == 1: exact_sol.closefile()

        return

    def CalculateNormsFromAnalytic(self, processes, a_module, exact_times=[], bid_list=[]):
        """
        Generate the error norms between solutions.
        """

        # Import the wrapper for the analytic solution
        # Before CalculateNormsFromAnalytic is called, error
        #   checking on a_module is done in vcomp.ValidateAnalytic
        exec('import ' + a_module.exact_class )
        exact_sol = eval( a_module.instantiator )
        test_var_list = a_module.test_var_list
        zfill=a_module.zfill
        subel_ints=a_module.subel_ints
        
        # Now, for each computed solution compute the error norms
        for cfname in self.computed_filenames:
          comp_sol = exodus.ExodusFile(cfname)

          # get list of element and node variables
          elem_vars = comp_sol.varNames( exodus.EX_ELEM )
          node_vars = comp_sol.varNames( exodus.EX_NODE )

          elem_var_list = []
          node_var_list = []
          not_found_pair_list = copy.deepcopy(test_var_list)
          for pair in test_var_list:
            comp_var_requested = pair[0]
            exact_var_requested = pair[1]
            if ( (comp_var_requested in elem_vars) and
                 hasattr(exact_sol, exact_var_requested) ):
              elem_var_list.append(pair)
              not_found_pair_list.remove(pair) 
            elif ( (comp_var_requested in node_vars) and
                   hasattr(exact_sol, exact_var_requested) and 
	           (len(pair)<=2 or (pair[2] in node_vars)) ):
              node_var_list.append(pair)
              not_found_pair_list.remove(pair)
          if len(not_found_pair_list) > 0:
              print "Variable not found in exodus file or analytic definition"
              for pair in not_found_pair_list:
                print "Some part of the list " + str(pair) + " was not found!"
	      sys.exit(1)
            
          timeNorms = {}
          m=0
          for item in self.times:
            time       = item[1]
            if not exact_times==[]:
               etime = exact_times[m]
            else:
               etime = time


#            times_c = computed_solution.getTimes()
#            time_index_c = 0
#            for index in range(len(times_c)):
#              if not exotools.softDiff(time, times_c[index]):
#                time_index_c = index 
#                break

            varNorms = {}

            # Element variables
            for elem_pair in elem_var_list:
              varET = exotools.element_norm_spatial_exoao(processes,
                                                          comp_sol,
                                                          time,
                                                          elem_pair,
                                                          exact_sol,
                                                          subel_ints=subel_ints,
                                                          zfill=zfill,
                                                          exact_time=etime,
                                                          block_ids=bid_list)
              varNorms[elem_pair[0].lower()] = ( varET.L_inf(),
                                                 varET.L1(), 
                                                 varET.L2(), 
                                                 varET.RL_inf(), 
                                                 varET.RL1(), 
                                                 varET.RL2() )
            
            # Nodal variables
            for node_pair in node_var_list:
              varET = exotools.node_norm_spatial_exoao(comp_sol,
                                                       time,
                                                       node_pair,
                                                       exact_sol,
                                                       subel_ints=subel_ints,
                                                       zfill=zfill,
                                                       exact_time=etime)
              varNorms[node_pair[0].lower()] = ( varET.L_inf(),
                                                 varET.L1(), 
                                                 varET.L2(), 
                                                 varET.RL_inf(), 
                                                 varET.RL1(), 
                                                 varET.RL2() )

            timeNorms[time] = varNorms
            m=m+1
      
          self.norms[cfname] = timeNorms
          comp_sol.closefile()
    
        return


    def getNorms(self, comparison_filename, time, variable):

        timeNorms = {}
        varNorms = {}
        try:    timeNorms = self.norms[comparison_filename]
        except:
          print '*** ErrorOrder: error: '
          print 'Cannot find in comparison file, ' + comparison_filename + \
                ', the time norms.'     
          sys.exit(1)

        try:    varNorms = timeNorms[time]
        except:
          print '*** ErrorOrder: error: '
          print 'Cannot find in comparison file, ' + comparison_filename + \
                ', the variable norms for time = ', time     
          sys.exit(1)

        try:    norms = varNorms[variable.lower()]
        except:
          print '*** ErrorOrder: error: '
          print 'Cannot find in comparison file, ' + comparison_filename + \
                ', for time = ', time, ', the variable, ', variable   
          sys.exit(1)

        return norms


    def PrintNorms(self, printTotals=1):
        """
        Generate the error norms between two solutions.
        """

        print 80*"="
        print "  Reference type: ", self.reference_type
        for comparison_filename in self.computed_filenames:
          print "  Comparison files:  ", comparison_filename, \
                "   h = ", self.resolutions[comparison_filename][0], \
                "  dt = ", self.resolutions[comparison_filename][1]

        for item in self.times:
          time       = item[1]
          print 
          print "  Time = ", time
          print
          print "Error Norms     h           dt   L_inf_norm      L1_norm      L2_norm" \
                "  RL_inf_norm     RL1_norm     RL2_norm"
          print 80*"-"

          varnames = self.varnames
          varnames.sort()
          for var in varnames:

            print "  %-15s" % (var)

            for comparison_filename in self.computed_filenames:

              norms = self.getNorms(comparison_filename, time, var)
              res = self.resolutions[comparison_filename]

              L_inf  = float(norms[0])
              L1     = float(norms[1])
              L2     = float(norms[2])
              RL_inf = float(norms[3])
              RL1    = float(norms[4])
              RL2    = float(norms[5])
    
              print "     %12.5e %12.5e %12.5e %12.5e %12.5e %12.5e %12.5e %12.5e"\
                    % (res[0], res[1], L_inf, L1, L2, RL_inf, RL1, RL2)
    
          print 80*"="


    def WriteNormsToMPL(self,mpl_fn="vcomp_norms_mpl.py"):
        """
        Write the error norms to a file for easy plotting by matplotlib.
        """

        mplfile = open(mpl_fn,'w')

        mplfile.write('# Error norms computed by vcomp\n')
        mplfile.write('reference_type=' + repr(self.reference_type) + '\n')

        mplfile.write("computed_filenames="
                      + repr(self.computed_filenames) + '\n') 

        mplfile.write("varnames=" + repr(self.varnames) + '\n') 

        times=[]
        for titem in self.times:
           times.append(titem[1])
        mplfile.write("times=" + repr(times) + '\n')

        h=[]
        dt=[]
        for comparison_filename in self.computed_filenames:
            res=self.resolutions[comparison_filename]
            h.append(  res[0] )
            dt.append( res[1] )
        mplfile.write("h=" + repr(h) + '\n')
        mplfile.write("dt=" + repr(dt) + '\n')

        mplfile.write('cnames=["L_inf_norm", "L1_norm", "L2_norm", "RL_inf_norm", "RL1_norm", "RL2_norm"]\n')

        for var in self.varnames:

            var_times_norms=[]   # a list of dictionaries
                                 # each dictionary holds the norms
                                 #   at a given time
            for titem in self.times:

                time = titem[1]

                # a dictionary, that will hold lists of norm values 
                normD={}

                # a list for each norm, with one list entry for each resolution
                L_inf=[]
                L1=[]
                L2=[]
                RL_inf=[]
                RL1=[]
                RL2=[]

                for comparison_filename in self.computed_filenames:

                    norms = self.getNorms(comparison_filename, time, var)
  
                    L_inf.append(   float(norms[0]) )
                    L1.append(      float(norms[1]) )
                    L2.append(      float(norms[2]) )
                    RL_inf.append(  float(norms[3]) )
                    RL1.append(     float(norms[4]) )
                    RL2.append(     float(norms[5]) )
    
                normD['L_inf_norm']=L_inf
                normD['L1_norm']=L1
                normD['L2_norm']=L2
                normD['RL_inf_norm']=RL_inf
                normD['RL1_norm']=RL1
                normD['RL2_norm']=RL2

                var_times_norms.append(normD)

            mplfile.write(var + "=" + repr(var_times_norms) + '\n')

        mplfile.close()


    def CalculateOrder(self, refinement):
        """
        Calculate the order of accuracy and print it out.
        """
    
        self.orders = {}
        coeff_refinement = 1.0/log(refinement)
        for item in self.times:
          time       = item[1]
    
          varOrders = {}
          for var in self.varnames:
    
            fileOrders = {}
            for file_index in range(len(self.computed_filenames)-1):
              lo_filename = self.computed_filenames[file_index]
              hi_filename = self.computed_filenames[file_index+1]
    
              time_norms_lo = self.norms[lo_filename]
              time_norms_hi = self.norms[hi_filename]
    
              vars_norms_lo = time_norms_lo[time]
              vars_norms_hi = time_norms_hi[time]
    
              norms_lo = vars_norms_lo[var.lower()]
              norms_hi = vars_norms_hi[var.lower()]
              if ( norms_lo[0] != 0.0 ):
                order_Linf =  log( norms_hi[0]/norms_lo[0] )*coeff_refinement
              else: order_Linf = 0.0
              if ( norms_lo[1] != 0.0 ):
                order_L1   =  log( norms_hi[1]/norms_lo[1] )*coeff_refinement
              else: order_L1 = 0.0
              if ( norms_lo[2] != 0.0 ):
                order_L2   =  log( norms_hi[2]/norms_lo[2] )*coeff_refinement
              else: order_L2 = 0.0
    
              fileOrders[lo_filename] = (order_Linf, order_L1, order_L2)
              if file_index == len(self.computed_filenames)-2:
                fileOrders[hi_filename] = (order_Linf, order_L1, order_L2)
            varOrders[var.lower()] = fileOrders
          self.orders[time] = varOrders
    
        return


    def getOrders(self, comparison_filename, time, variable):

        timeNorms = {}
        varNorms = {}

        if self.orders == {}:
          # there are no orders for this object
          return None

        try:    varOrders = self.orders[time]
        except:
          print '*** ErrorOrder: error: '
          print 'Cannot find in comparison file, ' + comparison_filename + \
                ', the variable orders for time = ', time     
          sys.exit(1)

        try:    fileOrders = varOrders[variable.lower()]
        except:
          print '*** ErrorOrder: error: '
          print 'Cannot find in comparison file, ' + comparison_filename + \
                ', for time = ', time, ', the variable, ', variable   
          sys.exit(1)

        try:    orders = fileOrders[comparison_filename]
        except:
          print '*** ErrorOrder: error: '
          print 'Cannot find in comparison file, ' + comparison_filename + \
                ', for time = ', time, ', the variable, ', variable   
          sys.exit(1)

        return orders


    def PrintOrders(self, printHiName=1):
        """
        Print the order of accuracy.
        """
  
        for item in self.times:
          time       = item[1]
          print "\n"
          print "  Time = ", time
          print "\n"
          print 80*"="
          print "  Order        h             dt     L_inf_norm        L1_norm        L2_norm"
      
          varOrders = self.orders[time]
          self.varnames.sort()
          for var in self.varnames:
            print 80*"-"
            print "  %-15s" % (var)
      
            fileOrders = varOrders[var.lower()]
            for file_index in range(len(self.computed_filenames)-1):
              lo_filename = self.computed_filenames[file_index]
              hi_filename = self.computed_filenames[file_index+1]
      
              try :
                order_Linf = fileOrders[lo_filename][0]
                order_L1   = fileOrders[lo_filename][1]
                order_L2   = fileOrders[lo_filename][2]
              except :
                continue
              print "    %12.5e   %12.5e   %12.5e   %12.5e   %12.5e" \
                    % (self.resolutions[lo_filename][0], \
                       self.resolutions[lo_filename][1], \
                       order_Linf, order_L1, order_L2)
            if printHiName :
              print "    %12.5e   %12.5e   %12.5e   %12.5e   %12.5e" \
                    % (self.resolutions[hi_filename][0], \
                       self.resolutions[hi_filename][1], \
                       order_Linf, order_L1, order_L2)
          print 80*"="
      
        return

    def WriteOrdersToMPL(self,mpl_fn="vcomp_orders_mpl.py"):
        """
        Write the orders of accuracy to a file for easy plotting by matplotlib.
        """

        mplfile = open(mpl_fn,'w')

        mplfile.write('# Orders of accuracy computed by vcomp\n')
        mplfile.write('reference_type=' + repr(self.reference_type) + '\n')

        mplfile.write("computed_filenames="
                      + repr(self.computed_filenames) + '\n') 

        mplfile.write("varnames=" + repr(self.varnames) + '\n') 

        times=[]
        for titem in self.times:
           times.append(titem[1])
        mplfile.write("times=" + repr(times) + '\n')

        h=[]
        dt=[]
        for comparison_filename in self.computed_filenames:
            res=self.resolutions[comparison_filename]
            h.append(  res[0] )
            dt.append( res[1] )
        mplfile.write("h=" + repr(h) + '\n')
        mplfile.write("dt=" + repr(dt) + '\n')

        mplfile.write('cnames=["L_inf_order", "L1_order", "L2_order"]\n')

        if self.orders == None:
            mplfile.write("No orders found in the peo file.")
            mplfile.close()
            return

        for var in self.varnames:

            var_times_orders=[]   # a list of dictionaries
                                  # each dictionary holds the orders
                                  #   at a given time
            for titem in self.times:

                time = titem[1]

                # a dictionary, that will hold lists of order values 
                orderD={}

                # a list of orders for each norm, with one list entry for each resolution
                L_inf=[]
                L1=[]
                L2=[]

                for comparison_filename in self.computed_filenames:

                    orders = self.getOrders(comparison_filename, time, var)
  
                    L_inf.append(   float(orders[0]) )
                    L1.append(      float(orders[1]) )
                    L2.append(      float(orders[2]) )
    
                orderD['L_inf_order']=L_inf
                orderD['L1_order']=L1
                orderD['L2_order']=L2

                var_times_orders.append(orderD)

            mplfile.write(var + "=" + repr(var_times_orders) + '\n')

        mplfile.close()


    def WriteOrdersToTex(self,tex_fn="vcomp_orders.tex"):
        """
        Write the orders of accuracy to a file as a LaTex table
        """

        # Sanity check
        if self.orders == None:
            return

        # Measure orders at last time
        time = self.times[len(self.times)-1][1];

        # Compute h, dt, orders, norms
        h=[]
        dt=[]
        orders = [[[0 for _ in range(3)] for _ in range(len(self.computed_filenames))] for _ in range(len(self.varnames))]
        norms  = [[[0 for _ in range(3)] for _ in range(len(self.computed_filenames))] for _ in range(len(self.varnames))]

        for J in range(0, len(self.computed_filenames)): 
            comparison_filename = self.computed_filenames[J]
            res=self.resolutions[comparison_filename]
            h.append(  res[0] )
            dt.append( res[1] )
            for I in range(0, len(self.varnames)): 
                var = self.varnames[I]
                myorders = self.getOrders(comparison_filename, time, var)
                mynorms = self.getNorms(comparison_filename, time, var)
                for K in range(0, len(myorders)):
                    orders[I][J][K] = myorders[K]
                    norms[I][J][K]  = mynorms[3+K]   # Use the relative not absolute norms
        
        # Are we in a dt or h mode?
        if (dt[0] == dt[1]):
            h_mode = True
        else:
            h_mode = False
    
        # Table header
        texfile = open(tex_fn,'w')
        texfile.write('\\begin{table}[htb]\n')
        texfile.write('% reference_type=' + repr(self.reference_type) + '\n')

        texfile.write("% computed_filenames="
                      + repr(self.computed_filenames) + '\n') 

        # Table labels
        cnames=["$L_\infty$", "$L_1$", "$L_2$"]
        texfile.write("\\begin{center}\\begin{tabular}{|lr|")
        for I in range(0, len(cnames)):
            texfile.write("l");
        texfile.write("|}\n\\hline\n")

        # Title Line
        texfile.write("Variable & ");
        if(h_mode):
            texfile.write(" h ")
        else: 
            texfile.write(" dt ")
        for order in cnames:
            texfile.write("& " + order )
        texfile.write("\\\\\n\\hline\\hline\n")

        # Variables = Block rows 
        for I in range(0, len(self.varnames)): 
            var = self.varnames[I]
            texfile.write(var.replace("_","\\_") + "& ")
            
            # h = Rows
            for J in range(len(h)-1,-1,-1):                               
                if(J != len(h)-1):
                    texfile.write(" &")
                if(h_mode):
                    texfile.write(repr(h[J]) + " ")
                else:
                    texfile.write(repr(dt[J]) + " ")
                # norm = cols
                for K in range(0,len(cnames)):
                    if(J == len(h)-1 ):
                        texfile.write("& %6.4e (---) " % norms[I][J][K])
                    else:
                        texfile.write("& %6.4e (%4.2f) " % (norms[I][J][K], orders[I][J][K]))
                texfile.write("\\\\\n")
            texfile.write("\\hline\n")
                        
        # Footer
        texfile.write("\end{tabular}\n% FOOTER_PLACEHOLDER\n\\end{center}\end{table}\n")
        texfile.close()


    def WriteExodusFiles(self, storage_type, fname=None):

        eo_varnames = []
        eo_varnames.append('h')
        eo_varnames.append('dt')
        varnames = self.varnames
        varnames.sort()
        have_orders = True
        if self.orders == {}:
          have_orders = False
        prefixes = []
        prefixes.append('Li_')
        prefixes.append('L1_')
        prefixes.append('L2_')
        prefixes.append('RLi_')
        prefixes.append('RL1_')
        prefixes.append('RL2_')
        if have_orders:
          prefixes.append('Ord_Li_')
          prefixes.append('Ord_L1_')
          prefixes.append('Ord_L2_')
        error_found = 0
        for var in varnames:
          if len('Ord_Li_'+var) > 32:
            print '*** ErrorOrder: error: '
            print 'Created too long (>32) of a variable name, ' \
                  + 'Ord_Li_'+var + '.  Please shorten, ' + var \
                  + '.  This is an Exodus limit.'    
            error_found =1
          else:
            for prefix in prefixes:
              eo_varnames.append(prefix+var)

        if error_found:
          sys.exit(1)

#       magic
        try:
          fnlist = self.computed_filenames
        except:
          fnlist = self.comparison_filenames

        for cfname in fnlist:
#        for cfname in self.computed_filenames:
          newf = exodus.ExodusFile()
          eo_fname = Get_EO_CFName(cfname, fname)
          newf.createFile( eo_fname, storage_type=storage_type)
          newf.setDimension(1)
          newf.setTitle('Error norms and orders for ' + cfname)
          newf.setSizes( 0, 0, 0, 0,
                         0, 0, 0,
                         0, 0, 0, 0, 0,
                         0, 0, 0, 0 )
          newf.putInit()
          newf.putVarNames( exodus.EX_GLOBAL, eo_varnames )

          (h, dt) = self.resolutions[cfname]

          for i in range(len(self.times)):
            time = self.times[i][1]
            newf.putTime(i+1,time)

            a = array.array( storage_type )
            a.append(h)
            a.append(dt)
            
            for var in varnames:
              a.fromlist(list(self.getNorms (cfname, time, var)))
              if have_orders:
                a.fromlist(list(self.getOrders(cfname, time, var)))

            newf.putVar( a, i+1, exodus.EX_GLOBAL, 0, 0 )
          newf.closefile()

        return
