#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import sys
sys.dont_write_bytecode = True
sys.excepthook = sys.__excepthook__
import os
import string


class CommonSpecError(Exception):
    def __init__(self, msg=None):
      if msg != None:
        self.msg = "Error: " + msg
      else:
        self.msg = "Error: (unknown)"
    def __str__(self): return self.msg


class CommonSpec:
    """
    Stores an execution specification which can be used by the test scripts.
    There are 3 types:
      
      1) definition: just a script fragment; no name, variable, or path list
      2) variable: a variable is defined by either a path list or simple a
                   script fragment; no CommonSpec name will be defined; if the
                   variable name is None, then only a script fragment is
                   meaningful
      3) content: an identifying name combined with a variable set with a
                  path list or script fragment and, separately, a content
                  script fragment
    
    The variable and content types can coexist in the same instance.
    The content script fragment may have special strings substituted for them
    when written to the test script, such as $(CONTENT) and $(EXPECT_STATUS).
    """
    
    def Name(self): return self.name
    
    def getDefine(self, platform_name):
        """
        Returns a script fragment or None if this CommonSpec does not
        represent a simple definition script fragment.  Filters by platform
        name.
        """
        if self.name == None and self.var == None and self.script != None:
          dflt = self.script.get('','')
          return self.script.get(platform_name,dflt)
        return None
    
    def getVariable(self, platform_name):
        """
        Returns a pair equal to either
           ( varname, (path list, flags) ) or
           ( varname, (script fragment,) )
        where the sub-pair contains a list of paths to check and flags to
        append to the result, or a plain script fragment.  Note that the
        varname may be None, in which case the second element of the pair
        will always be (script fragment,).  If no variable name and value was
        set for this CommonSpec, None is returned.  Filters by platform name.
        """
        if self.define != None:
          dflt = self.define.get('','')
          return ( self.var, self.define.get(platform_name,dflt) )
        return None
    
    def getContent(self, platform_name):
        """
        Returns a script fragment representing the content of a named
        execution block.  Returns None if this CommonSpec has no name.
        Filters by platform name.
        """
        if self.name != None:
          dflt = self.script.get('','')
          return self.script.get(platform_name,dflt)
        return None
    
    def isAnalyze(self):
        """
        """
        return self.analyze == "yes"
    
    #######################################################
    
    def __init__(self):
        
        # a string that identifies the content script fragment
        self.name = None
        
        # a string that defines the variable that is to be defined
        self.var = None
        
        # dictionary maps platform name to a list of (path list,flags) or
        # (string,) pairs; the empty string maps to default; the single string
        # is a script fragment to be used instead of a path list
        self.define = None
        
        # dictionary maps platform name to a string (ie, a script fragment);
        # the empty string maps to default
        self.script = None
        
        # for named blocks, value "yes" means is post processes for diffs
        self.analyze = "no"
    
    def __repr__(self):
        s = "CommonSpec: type = "
        if self.name == None and self.var == None: s = s + "definition"
        elif self.define != None: s = s + "variable"
        if self.name != None: s = s + "/content, name = " + self.name
        if self.var != None:
          s = s + "\n  Variable name: " + self.var
        if self.define != None:
          for (k,v) in self.define.items():
            if k: s = s + "\n  Define: " + k + " "
            else: s = s + "\n  Define: (default) "
            if len(v) == 1: s = s + "<path list plus flags>"
            else: s = s + "script fragment"
        if self.script != None:
          for (k,v) in self.script.items():
            if k: s = s + "\n  Script: " + k
            else: s = s + "\n  Script: (default)"
        return s
    
    def setDefinition(self, script_dict):
        """
        Sets all data members to None except the script dictionary, which
        maps platform strings to script fragments.  An empty string maps
        to the default script fragment.  A copy of the dictionary is made.
        """
        self.name = None
        self.var = None
        self.define = None
        self.script = {}
        for (n,v) in script_dict.items():
          self.script[n] = v
    
    def setVariable(self, varname, define_dict):
        """
        Sets the variable name and the definition dictionary.  Does not
        touch any other data members.  The define_dict must map platform
        strings to either a (path list, flags) pair or a (script frag, )
        length one tuple.  The path list is a list of search paths, and
        the flags is a string to be appended.  The length one tuple is just
        a script fragment.  A copy of the dictionary is made.  Note that
        the varname may be None, but if so, then none of the define_dict
        values can be (path list, flags).
        """
        self.var = varname
        self.define = {}
        for (n,v) in define_dict.items():
          assert varname != None or len(v) == 1, \
                "varname == None can have only script fragments"
          self.define[n] = v
    
    def setContent(self, name, script_dict):
        """
        Sets the name of this specification and the content script dictionary.
        Does not touch any other data members.  The script dictionary maps
        platform names to script fragments.  A copy of the dictionary is made.
        """
        self.name = name
        assert name != None, "name cannot be None"
        self.script = {}
        for (n,v) in script_dict.items():
          self.script[n] = v
    
    def setAnalyze(self):
        """
        """
        self.analyze = "yes"


class CommonSpecDB:
    """
    Stores a set of CommonSpec objects plus (optionally) a special "clear"
    script fragment.
    """
    
    def getClear(self):
        """
        If defined, returns a simple script fragment.  Otherwise returns None.
        """
        return self.clear
    
    def getDefines(self):
        """
        Returns a list of CommonSpec objects (in order) that only contain
        simple definitions.
        """
        L = []
        for cs in self.specs:
          if cs.name == None and cs.var == None and cs.script != None:
            L.append(cs)
        return L
    
    def getVariables(self):
        """
        Returns a list of CommonSpec objects (in order) that contain variable
        definitions.
        """
        L = []
        for cs in self.specs:
          if cs.define != None:
            L.append(cs)
        return L
    
    def findContent(self, name):
        """
        Returns the CommonSpec object with the given identifying name, or
        None if the name is not in the database of CommonSpec objects.
        """
        assert name != None
        return self.named_specs.get( name, None )
    
    #######################################################
    
    def __init__(self):
        self.clear = None
        self.specs = []
        self.named_specs = {}
    
    def addClear(self, clear_frag):
        """
        Sets the clear fragment if not defined yet.  If defined already, then
        the given fragment is appended to the current clear fragment, separated
        by two newlines.
        """
        if self.clear == None:
          self.clear = clear_frag
        else:
          self.clear = self.clear + "\n\n" + clear_frag
    
    def addSpec(self, spec):
        self.specs.append( spec )
        if spec.Name() != None:
          self.named_specs[ spec.Name() ] = spec


########################################################################

def scanCommonSpecs( filedoc, common_db ):
    """
    Scans filedoc (an XmlNode object) and extends/overwrites the common_db
    (a CommonSpecDB object) with common test specifications.
    
    Raises a CommonSpecError if the filedoc contains an error.
    """
    
    ndL = filedoc.matchNodes( ['clear'] )
    if len(ndL) > 1:
      raise CommonSpecError( \
              'more than one "clear" block not allowed, line ' + \
              str(ndL[-1].getLineNumber()) )
    if len(ndL) == 1:
      common_db.addClear( string.strip( ndL[0].getContent() ) )
    
    for nd in filedoc.getSubNodes():
      
      if nd.getName() == "define":
        D = {}
        for snd in nd.getSubNodes():
          if snd.getName() == "default":
            D[''] = string.strip( snd.getContent() )
          else:
            D[snd.getName()] = string.strip( snd.getContent() )
        if len(D) > 0:
          cs = CommonSpec()
          cs.setDefinition(D)
          common_db.addSpec(cs)
        else:
          raise CommonSpecError( \
                   'a <define> block must have at least one sub-block, ' + \
                   'line ' + str(nd.getLineNumber()) )
        
      elif nd.getName() == "executable":
        
        xname = nd.getAttr( "name", None )
        pname = nd.getAttr( "product", None )
        varname = nd.getAttr( "variable", None )
        
        if xname != None or varname != None:
          
          defineD = {}
          scriptD = {}
          
          for snd in nd.getSubNodes():
            
            if snd.getName() == "default": k = ''
            else:                          k = snd.getName()
            
            locL = snd.matchNodes( ['location'] )
            if len(locL) > 0:
              locnd = locL[0]
              if locnd.hasAttr( "search" ):
                if varname != None:
                  flags = locnd.getAttr( "flags", "" )
                  searchL = string.split( locnd.getAttr( "search" ) )
                  defineD[k] = ( searchL, flags )
                else:
                  raise CommonSpecError( \
                    'a <location> block cannot have a "search" attribute ' + \
                    'when the <execute> block does not have a "variable" ' + \
                    'attribute, ' + str(locnd.getLineNumber()) )
              else:
                defineD[k] = ( string.strip(locnd.getContent()), )
            
            scrL = snd.matchNodes( ['script'] )
            if len(scrL) > 0:
              scriptD[k] = string.strip( scrL[0].getContent() )
          
          cs = CommonSpec()
          
          if varname != None or len(defineD) > 0:
            cs.setVariable(varname, defineD)
          
          if xname != None:
            cs.setContent(xname, scriptD)
          
          if string.strip( nd.getAttr('analyze','') ) in ['yes','YES','Yes']:
            cs.setAnalyze()
          
          common_db.addSpec(cs)
        
        else:
          raise CommonSpecError( \
            'an <executable> block must have a "name" or "variable" ' + \
            'attribute, ' + str(nd.getLineNumber()) )


###########################################################################

def loadCommonSpec( specdir, configdir ):
    """
    """
    import xmlwrapper
    xmldocreader = xmlwrapper.XmlDocReader()
    
    xdb = CommonSpecDB()
    f1 = os.path.join( specdir, 'exeDB.xml' )
    f2 = os.path.join( configdir, 'exeDB.xml' )
    for xdbf in [f1,f2]:
        if os.path.exists( xdbf ):
            try:
                doc = xmldocreader.readDoc( xdbf )
                scanCommonSpecs( doc, xdb )
            except:
                sys.stderr.write( "*** error: failed to read " + xdbf + \
                                  os.linesep )
                sys.stderr.flush()
                raise
    
    return xdb


###########################################################################

if __name__ == "__main__":
    
    import sys
    sys.path.append( os.path.abspath( '../makemflib' ) )
    import xmlwrapper
    docreader = xmlwrapper.XmlDocReader()
    filedoc = docreader.readDoc( "exeDB.xml" )
    common_db = CommonSpecDB()
    scanCommonSpecs( filedoc, common_db )
    for cs in common_db.specs:
      print cs
