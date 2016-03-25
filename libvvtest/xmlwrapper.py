#!/usr/bin/env python

#############################################################################
#
#   The xmlwrapper module provides a uniform and simplified interface for
# XML parsing.  It will find a valid XML parser object even for old python
# versions.  If all else fails, it will try for a local parser called
# xmlprocm.
#
#   The XmlDocReader class contains the logic to find a parser and provides
# a readDoc() method returning an XmlNode object which is used to access the
# entire document in an XML DOM paradigm.
#
#############################################################################

import os, sys
import string, re


class XmlError(Exception):
    def __init__(self, msg=""): self.msg = "XML: " + msg
    def __str__(self): return self.msg


class XmlNode:
    
    def __init__(self, name, attr_dict):
        self.name = name
        self.line_no = 0
        self.attrs = attr_dict
        self.content = ''
        self.parent = None
        self.kids = []
    
    def getAttrs(self):
        """Returns the dictionary of attribute names to attribute values."""
        return self.attrs
    
    def getContent(self):
        """Returns the string of accumulated content."""
        return self.content
    
    def getSubNodes(self):
        """Returns the list of XmlNode children to this XmlNode."""
        return self.kids
    
    def hasAttr(self, name):
        """Returns true if the XML node has an attribute with the given name."""
        return self.attrs.has_key(name)
    
    def getAttr(self, name, *args):
        """
        Returns the value of the attribute with the given name.  If the
        attribute does not exist and a default value is not given, a KeyError
        exception is thrown.
        """
        if len(args) > 0:
          return self.attrs.get( name, args[0] )
        return self.attrs[name]
    
    def subNode(self, name):
        """Returns the child node with the given name.  Raises a LookupError
           exception if a child with the given name does not exist."""
        for nd in self.kids:
          if nd.name == name:
            return nd
        raise LookupError, 'name not found "' + name + '"'
    
    def matchNodes(self, node_path_list):
        """
        Search and return all sub nodes which match the node path.
        Each element of the list is matched against sub node names of
        increasing depth.  Regular expression pattern matching is used
        for each name.
        
        For example, the list ['sub.*', 'level2_name'] will match all
        nodes whose first level child name matches 'sub.*' and whose second
        level child matches 'level2_name'.
        """
        
        if type(node_path_list) != type([]):
          raise TypeError, 'argument not a list: "' + str(node_path_list) + '"'
        
        nodes = [self,]
        
        for pat in node_path_list:
          cpat = re.compile(pat)
          new_nodes = []
          for nd in nodes:
            for kid in nd.getSubNodes():
              if cpat.match(kid.name):
                new_nodes.append(kid)
          nodes = new_nodes
          if len(nodes) == 0:
            break
        
        return nodes
    
    def toString(self, recursive=1, indent=""):
        """
        Writes this XML node into string form.  If the recursive flag is true,
        writes all subnodes recursively too.  The indent string is prepended
        to each line.  Returns the total string.
        """
        s = indent + '<' + self.name
        for (n,v) in self.attrs.items():
          s = s + ' ' + n + '="' + v + '"'
        c = string.strip(self.content)
        if c or len(self.kids) > 0:
          s = s + '>\n'
          if c: s = s + indent + "  " + c + '\n'
          if recursive:
            for nd in self.kids:
              s = s + nd.toString(recursive,indent=indent+"  ")
          s = s + indent + '</' + self.name + '>\n'
        else:
          s = s + '/>\n'
        
        return s
    
    ########### creation methods
    
    def appendContent(self, more):
        self.content = self.content + more
    
    def addSubNode(self, nd):
        self.kids.append( nd )


def printXmlNode(nd, indent=''):
    if nd.name != None:
      print indent + nd.name + ' ' + str(nd.line_no) + ': ' + \
            str(nd.attrs) + ' ' + nd.content
      for kid in nd.kids:
        printXmlNode(kid, indent + '  ')


#############################################################################

class XmlReadAbort(Exception):
    def __init__(self, msg=None): self.msg = "abort read"
    def __str__(self): return self.msg

class XmlDocReader:
    """
    Attempts to find an available XML parser.  Currently, it looks for
    xml.sax, xmllib, then one that does not belong to python distributions
    called xmlprocm.
    
    Construct an XmlDocReader, call its readDoc(filename) method, then
    access the resulting DOM structure using XmlNode methods.  If more than
    one document must be parsed, it is faster to repeatedly call the readDoc
    method rather than constructing a new XmlDocReader each time.
    """
    
    def __init__(self):
        
        self.xmlsax_parser = None
        self.xmllib_parser = None
        self.xmlproc_parser = None
        
        try:
          import xml
          import xml.sax
          self.xmlsax_parser = xml.sax.make_parser()
          
          eh = self.xmlsax_parser.getErrorHandler()
          eh.error = self.xmlsax_error
          eh.fatalError = self.xmlsax_error
          ch = self.xmlsax_parser.getContentHandler()
          ch.startElement = self.xmlsax_startElement
          ch.characters = self.handle_data
          ch.endElement = self.handle_end_tag
        except:
          self.xmlsax_parser = None
        
        if self.xmlsax_parser == None:
          try:
            # xmllib is deprecated since python 2.0
            import xmllib
            self.xmllib_parser = xmllib.XMLParser()
            self.xmllib_parser.syntax_error = self.handle_error
            self.xmllib_parser.unknown_charref = self.xmllib_unknown_charref
            self.xmllib_parser.unknown_entityref = self.xmllib_unknown_entityref
            self.xmllib_parser.unknown_starttag = self.xmllib_handle_start_tag
            self.xmllib_parser.handle_data = self.handle_data
            self.xmllib_parser.handle_cdata = self.handle_data
            self.xmllib_parser.unknown_endtag = self.handle_end_tag
          except:
            self.xmllib_parser = None
        
        if self.xmlsax_parser == None and self.xmllib_parser == None:
          try:
            # a parser distribution that RRD stripped and placed into one file
            import xmlprocm
            self.xmlproc_parser = xmlprocm.XmlProcDocReader()
            self.xmlproc_parser.setErrorHandler (self.handle_error)
            self.xmlproc_parser.setBeginHandler (self.handle_start_tag)
            self.xmlproc_parser.setContentHandler (self.handle_data)
            self.xmlproc_parser.setEndHandler (self.handle_end_tag)
          except:
            self.xmlproc_parser = None
        
        if self.xmlsax_parser == None and \
           self.xmllib_parser == None and \
           self.xmlproc_parser == None:
          raise RuntimeException, 'could not initialize an XML parser'
    
    def readDoc(self, filename, initial_tag_name=None):
        """
        Open the XML file and read its contents into an XML DOM type structure.
        If the initial tag name is not None, the first tag encountered in
        the file must be equal to this value.  If not, None is returned.
        """
        
        self.dom = None
        self.read_stack = []
        self.init_tag = initial_tag_name
        
        try:
          
          if self.xmlsax_parser != None:
            ff = open(filename,"rb")
            self.xmlsax_parser.parse(ff)
            ff.close()
            
          elif self.xmllib_parser != None:
            try:
              self.xmllib_parser.reset()
              MAX_BUF_SIZE = 10000
              sz = os.path.getsize(filename)
              if sz > MAX_BUF_SIZE: sz = MAX_BUF_SIZE
              elif sz == 0:         sz = 1
              f = open(filename, 'r')
              while 1:
                buf = f.read(sz)
                if buf: self.xmllib_parser.feed(buf)
                if len(buf) < sz:
                  break
              f.close()
              self.xmllib_parser.close()
            except XmlReadAbort:
              raise
            except IOError, e:
              raise
            except Exception, e:
              self.handle_error(str(e))
            
          elif self.xmlproc_parser != None:
            self.xmlproc_parser.readDoc(filename)
          
          addParentPointers(self.dom)
        
        except XmlReadAbort:
          self.dom = None
        
        dom = self.dom
        self.dom = None  # allow garbage collection
        return dom
    
    ########### handlers
    
    def handle_error(self, msg):
        raise XmlError, msg
    
    def handle_start_tag(self, tag_name, line_number, attrs_dict):
        
        if len(self.read_stack) == 0:
          if self.init_tag != None and self.init_tag != tag_name:
            raise XmlReadAbort()
          self.dom = XmlNode(tag_name, attrs_dict)
          nd = self.dom
        else:
          nd = XmlNode(tag_name, attrs_dict)
          self.read_stack[-1].addSubNode( nd )
        
        self.read_stack.append( nd )
        
        nd.line_no = line_number
    
    def handle_data(self, data):
        if len(self.read_stack) > 0:
          self.read_stack[-1].appendContent(data)
    
    def handle_end_tag(self, tag_name):
        self.read_stack.pop()
    
    ########### handler wrappers
    
    def xmllib_handle_start_tag(self, tag_name, attrs):
      self.handle_start_tag(tag_name, self.xmllib_parser.lineno, attrs)
    
    def xmllib_unknown_charref(self, ref):
      self.handle_error( 'unknown character reference "' + ref + '", line ' + \
                         str(self.xmllib_parser.lineno) )
    
    def xmllib_unknown_entityref(self, ref):
      self.handle_error( 'unknown entity reference "' + ref + '", line ' + \
                         str(self.xmllib_parser.lineno) )
    
    def xmlsax_startElement(self, tag_name, attrs):
      attrs_dict = {}
      for itr in attrs.items(): attrs_dict[itr[0]] = itr[1]
      self.handle_start_tag(
             tag_name,
             self.xmlsax_parser.getContentHandler()._locator.getLineNumber(),
             attrs_dict )
    
    def xmlsax_error(self, exception):
        self.handle_error( str(exception) )
    
    ###########


def addParentPointers(xnd):
    for nd in xnd.getSubNodes():
      nd.parent = xnd
      addParentPointers(nd)


#############################################################################

if __name__ == "__main__":
    
    if len(sys.argv) < 2:
      print "*** error: please specify a file to parse"
      sys.exit(1)
    
    doc = XmlDocReader()
    
    dom = doc.readDoc(sys.argv[1])
    printXmlNode(dom)
    print "========================================== again:"
    dom = doc.readDoc(sys.argv[1])
    printXmlNode(dom)
