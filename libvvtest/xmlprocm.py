#!/usr/bin/env python

#############################################################################
#
# This file is a modification of the xmlproc distribution.  Network URL
# support has been stripped.  Also, DTDs have been disabled.
#
# The main class is XmlProcDocReader below.
#
# Use would be:    doc = XmlProcDocReader()
#                  doc.setErrorHandler (func)
#                  doc.setBeginHandler (func)
#                  doc.setContentHandler (func)  # and other handlers
#                  doc.readDoc("filename.xml")
#
#############################################################################

import os, sys, string, re, urlparse


error_lists={}  # The hash of errors

def add_error_list(language,list):
    error_lists[string.lower(language)]=list

def get_error_list(language):
    return error_lists[string.lower(language)]

def get_language_list():
    return error_lists.keys()

# Errors in English

english={

    # --- Warnings: 1000-1999
    1000: "Undeclared namespace prefix '%s'",
    1002: "Unsupported encoding '%s'",
    1003: "Obsolete namespace syntax",
    1005: "Unsupported character number '%d' in character reference",
    1006: "Element '%s' has attribute list, but no element declaration",
    1007: "Attribute '%s' defined more than once",
    1008: "Ambiguous content model",

    # --- Namespace warnings
    1900: "Namespace prefix names cannot contain ':'s.",
    1901: "Namespace URI cannot be empty",
    1902: "Namespace prefix not declared",
    1903: "Attribute names not unique after namespace processing",

    # --- Validity errors: 2000-2999
    2000: "Actual value of attribute '%s' does not match fixed value",
    2001: "Element '%s' not allowed here",
    2002: "Document root element '%s' does not match declared root element",
    2003: "Element '%s' not declared",
    2004: "Element '%s' ended, but not finished",
    2005: "Character data not allowed in the content of this element",
    2006: "Attribute '%s' not declared",
    2007: "ID '%s' appears more than once in document",
    2008: "Only unparsed entities allowed as the values of ENTITY attributes",
    2009: "Notation '%s' not declared",
    2010: "Required attribute '%s' not present",
    2011: "IDREF referred to non-existent ID '%s'",
    2012: "Element '%s' declared more than once",
    2013: "Only one ID attribute allowed on each element type",
    2014: "ID attributes cannot be #FIXED or defaulted",
    2015: "xml:space must be declared an enumeration type",
    2016: "xml:space must have exactly the values 'default' and 'preserve'",
    2017: "'%s' is not an allowed value for the '%s' attribute",
    2018: "Value of '%s' attribute must be a valid name",
    2019: "Value of '%s' attribute not a valid name token",
    2020: "Value of '%s' attribute not a valid name token sequence",
    2021: "Token '%s' in the value of the '%s' attribute is not a valid name",
    2022: "Notation attribute '%s' uses undeclared notation '%s'",
    2023: "Unparsed entity '%s' uses undeclared notation '%s'",

    # --- Well-formedness errors: 3000-3999
    # From xmlutils
    3000: "Couldn't open resource '%s'",
    3001: "Construct started, but never completed",
    3002: "Whitespace expected here",
    3003: "Didn't match '%s'",   ## FIXME: This must be redone
    3004: "One of %s or '%s' expected",
    3005: "'%s' expected",

    # From XMLCommonParser
    3006: "SYSTEM or PUBLIC expected",
    3007: "Text declaration must appear first in entity",
    3008: "XML declaration must appear first in document",
    3009: "Multiple text declarations in a single entity",
    3010: "Multiple XML declarations in a single document",
    3011: "XML version missing on XML declaration",
    3012: "Standalone declaration on text declaration not allowed",
    3045: "Processing instruction target names beginning with 'xml' are reserved",
    3046: "Unsupported XML version",
    
    # From XMLProcessor
    3013: "Illegal construct",
    3014: "Premature document end, element '%s' not closed",
    3015: "Premature document end, no root element",
    3016: "Attribute '%s' occurs twice",
    3017: "Elements not allowed outside root element",
    3018: "Illegal character number '%d' in character reference",
    3019: "Entity recursion detected",
    3020: "External entity references not allowed in attribute values",
    3021: "Undeclared entity '%s'",
    3022: "'<' not allowed in attribute values",
    3023: "End tag for '%s' seen, but '%s' expected",
    3024: "Element '%s' not open",
    3025: "']]>' must not occur in character data",
    3027: "Not a valid character number",
    3028: "Character references not allowed outside root element",
    3029: "Character data not allowed outside root element",
    3030: "Entity references not allowed outside root element",
    3031: "References to unparsed entities not allowed in element content",
    3032: "Multiple document type declarations",
    3033: "Document type declaration not allowed inside root element",
    3034: "Premature end of internal DTD subset",
    3042: "Element crossed entity boundary",

    # From DTDParser
    3035: "Parameter entities cannot be unparsed",
    3036: "Parameter entity references not allowed in internal subset declarations",
    3037: "External entity references not allowed in entity replacement text",
    3038: "Unknown parameter entity '%s'",
    3039: "Expected type or alternative list",
    3040: "Choice and sequence lists cannot be mixed",
    3041: "Conditional sections not allowed in internal subset",
    3043: "Conditional section not closed",
    3044: "Token '%s' defined more than once",
    # next: 3047
    
    # From regular expressions that were not matched
    3900: "Not a valid name",
    3901: "Not a valid version number (%s)",
    3902: "Not a valid encoding name",
    3903: "Not a valid comment",
    3905: "Not a valid hexadecimal number",
    3906: "Not a valid number",
    3907: "Not a valid parameter reference",
    3908: "Not a valid attribute type",
    3909: "Not a valid attribute default definition",
    3910: "Not a valid enumerated attribute value",
    3911: "Not a valid standalone declaration",
    
    # --- Internal errors: 4000-4999
    4000: "Internal error: Entity stack broken",
    4001: "Internal error: Entity reference expected.",
    4002: "Internal error: Unknown error number.",
    4003: "Internal error: External PE references not allowed in declarations",

    # --- XCatalog errors: 5000-5099
    5000: "Uknown XCatalog element: %s.",
    5001: "Required XCatalog attribute %s on %s missing.",
     
    # --- SOCatalog errors: 5100-5199
    5100: "Invalid or unsupported construct: %s.",
    }

# Updating the error hash

add_error_list("en",english)

#############################################################################

# Standard exceptions

class OutOfDataException(Exception):
    """An exception that signals that more data is expected, but the current
    buffer has been exhausted."""
    pass

# ==============================
# The general entity parser
# ==============================

class EntityParser:
    """A generalized parser for XML entities, whether DTD, documents or even
    catalog files."""

    def __init__(self):
        # --- Creating support objects
	self.err=ErrorHandler(self)
	self.ent=EntityHandler(self.err)
        self.isf=InputSourceFactory()
        self.pubres=PubIdResolver()
        self.err_lang="en"
        self.errors=get_error_list(self.err_lang)
        
        self.reset()

    def set_error_language(self,language):
        """Sets the language in which errors are reported. (ISO 3166 codes.)
        Throws a KeyError if the language is not supported."""
        self.errors=errors.get_error_list(string.lower(language))
        self.err_lang=string.lower(language) # only set if supported

    def set_error_handler(self,err):
	"Sets the object to send error events to."
	self.err=err

    def set_pubid_resolver(self,pubres):
        self.pubres=pubres
        
    def set_entity_handler(self,ent):
	"Sets the object that resolves entity references."
	self.ent=ent

    def set_inputsource_factory(self,isf):
        "Sets the object factory used to create input sources from sysids."
        self.isf=isf

    def parse_resource(self,sysID,bufsize=16384):
	"""Begin parsing an XML entity with the specified system
	identifier.  Only used for the document entity, not to handle
	subentities, which open_entity takes care of."""

	self.current_sysID=sysID
	try:
	    infile=self.isf.create_input_source(sysID)
	except IOError,e:
	    self.report_error(3000,sysID)
	    return
	
	self.read_from(infile,bufsize)
	infile.close()
	self.flush()
	self.parseEnd()

    def open_entity(self,sysID,name="None"):
	"""Starts parsing a new entity, pushing the old onto the stack. This
	method must not be used to start parsing, use parse_resource for
	that."""

	sysID=join_sysids(self.get_current_sysid(),sysID)
	    
	try:
	    inf=self.isf.create_input_source(sysID)
	except IOError,e:
	    self.report_error(3000,sysID)
	    return

	self._push_ent_stack(name)
	self.current_sysID=sysID
	self.pos=0
	self.line=1
	self.last_break=0
	self.data=""
	
	self.read_from(inf)

	self.flush()
	self.pop_entity()

    def push_entity(self,sysID,contents,name="None"):
	"""Parse some text and consider it a new entity, making it possible
	to return to the original entity later."""
        self._push_ent_stack(name)
	self.data=contents
	self.current_sysID=sysID
	self.pos=0
	self.line=1
	self.last_break=0
	self.datasize=len(contents)
	self.last_upd_pos=0
        self.final=1

    def pop_entity(self):
	"Skips out of the current entity and back to the previous one."
	if self.ent_stack==[]: self.report_error(4000)

        self._pop_ent_stack()
	self.final=0
	
    def read_from(self,fileobj,bufsize=16384):
	"""Reads data from a file-like object until EOF. Does not close it.
	**WARNING**: This method does not call the parseStart/parseEnd methods,
	since it does not know if it may be called several times. Use
	parse_resource if you just want to read a file."""
	while 1:
	    buf=fileobj.read(bufsize)
	    if buf=="": break

            try:
                self.feed(buf)
            except OutOfDataException,e:
                break

    def reset(self):
        """Resets the parser, losing all unprocessed data."""
	self.ent_stack=[]
	self.open_ents=[]  # Used to test for entity recursion
        self.current_sysID="Unknown"
        self.first_feed=1

	# Block information
	self.data=""
	self.final=0
	self.datasize=0
	self.start_point=-1
	
	# Location tracking
	self.line=1
	self.last_break=0
	self.block_offset=0 # Offset from start of stream to start of cur block
	self.pos=0
	self.last_upd_pos=0
            
    def feed(self,new_data):
	"""Accepts more data from the data source. This method must
	set self.datasize and correctly update self.pos and self.data.
        It also does character encoding translation."""
        if self.first_feed:
            self.first_feed=0                    
            self.parseStart()

	self.update_pos() # Update line/col count

	if self.start_point==-1:
	    self.block_offset=self.block_offset+self.datasize
	    self.data=self.data[self.pos:]
	    self.last_break=self.last_break-self.pos  # Keep track of column
	    self.pos=0
	    self.last_upd_pos=0

        # Adding new data and doing line end normalization
        self.data=string.replace(self.data+new_data,
                                 "\015\012","\012")
        self.datasize=len(self.data)

	self.do_parse()
        
    def close(self):
        "Closes the parser, processing all remaining data. Calls parseEnd."
	self.flush()
	self.parseEnd()        
        
    def parseStart(self):
	"Called before the parse starts to notify subclasses."
	pass

    def parseEnd(self):
	"Called when there are no more data to notify subclasses."
	pass

    def flush(self):
	"Parses any remnants of data in the last block."
	if not self.pos+1==self.datasize:
	    self.final=1
            pos=self.pos
 	    try:
		self.do_parse()
	    except OutOfDataException,e:
                if pos!=self.pos:
                    self.report_error(3001)
                
    # --- GENERAL UTILITY
    
    # --- LOW-LEVEL SCANNING METHODS

    def set_start_point(self):
	"""Stores the current position and tells the parser not to forget any
	of the data beyond this point until get_region is called."""
	self.start_point=self.pos

    def store_state(self):
        """Makes the parser remember where we are now, so we can go back
        later with restore_state."""
        self.set_start_point()
        self.old_state=(self.last_upd_pos,self.line,self.last_break)

    def restore_state(self):
        """Goes back to a state previously remembered with store_state."""
        self.pos=self.start_point
        self.start_point=-1
        (self.last_upd_pos,self.line,self.last_break)=self.old_state
        
    def get_region(self):
	"""Returns the area from start_point to current position and remove
	start_point."""
	data=self.data[self.start_point:self.pos]
	self.start_point=-1
	return data

    def find_reg(self,regexp,required=1):
	"""Moves self.pos to the first character that matches the regexp and
	returns everything from pos and up to (but not including) that
	character."""
	oldpos=self.pos
	mo=regexp.search(self.data,self.pos)
	if mo==None:
            if self.final and not required:                
                self.pos=len(self.data)   # Just moved to the end
                return self.data[oldpos:]            
                
            raise OutOfDataException()
                
	self.pos=mo.start(0)
	return self.data[oldpos:self.pos]
    
    def scan_to(self,target):
	"Moves self.pos to beyond target and returns skipped text."
	new_pos=string.find(self.data,target,self.pos)
	if new_pos==-1:
	    raise OutOfDataException()
	res=self.data[self.pos:new_pos]
	self.pos=new_pos+len(target)
	return res

    def get_index(self,target):
	"Finds the position where target starts and returns it."
	new_pos=string.find(self.data,target,self.pos)
	if new_pos==-1:
	    raise OutOfDataException()
	return new_pos
    
    def test_str(self,test_str):
	"See if text at current position matches test_str, without moving."
	if self.datasize-self.pos<len(test_str) and not self.final:
	    raise OutOfDataException()
	return self.data[self.pos:self.pos+len(test_str)]==test_str
    
    def now_at(self,test_str):
	"Checks if we are at this string now, and if so skips over it."
        pos=self.pos
	if self.datasize-pos<len(test_str) and not self.final:
	    raise OutOfDataException()
	
	if self.data[pos:pos+len(test_str)]==test_str:
	    self.pos=self.pos+len(test_str)
	    return 1
	else:
	    return 0
    
    def skip_ws(self,necessary=0):
	"Skips over any whitespace at this point."
        start=self.pos
        
        try:
            while self.data[self.pos] in whitespace:
                self.pos=self.pos+1
        except IndexError:
	    if necessary and start==self.pos:
                if self.final:
                    self.report_error(3002)
                else:
                    raise OutOfDataException()

    def test_reg(self,regexp):
	"Checks if we match the regexp."
	if self.pos>self.datasize-5 and not self.final:
	    raise OutOfDataException()
	
	return regexp.match(self.data,self.pos)!=None
	    
    def get_match(self,regexp):
	"Returns the result of matching the regexp and advances self.pos."
	if self.pos>self.datasize-5 and not self.final:
	    raise OutOfDataException()

	ent=regexp.match(self.data,self.pos)
	if ent==None:
	    self.report_error(reg2code[regexp.pattern])
	    return ""

        end=ent.end(0) # Speeds us up slightly
	if end==self.datasize:
	    raise OutOfDataException()

	self.pos=end
	return ent.group(0)

    def update_pos(self):
	"Updates (line,col)-pos by checking processed blocks."
	breaks=string.count(self.data,"\n",self.last_upd_pos,self.pos)
	self.last_upd_pos=self.pos

	if breaks>0:
	    self.line=self.line+breaks
	    self.last_break=string.rfind(self.data,"\n",0,self.pos)

    def get_wrapped_match(self,wraps):
	"Returns a contained match. Useful for regexps inside quotes."
	found=0
	for (wrap,regexp) in wraps:
	    if self.test_str(wrap):
		found=1
		self.pos=self.pos+len(wrap)
		break

	if not found:
	    msg=""
	    for (wrap,regexp) in wraps[:-1]:
		msg="%s'%s', " % (msg,wrap)
            self.report_error(3004,(msg[:-2],wraps[-1][0]))

	data=self.get_match(regexp)
	if not self.now_at(wrap):
	    self.report_error(3005,wrap)

	return data

    #--- ERROR HANDLING

    def report_error(self,number,args=None):
        try:
            msg=self.errors[number]
            if args!=None:
                msg=msg % args
        except KeyError:
            msg=self.errors[4002] # Unknown err msg :-)
        
        if number<2000:
            self.err.warning(msg)
        elif number<3000:
            self.err.error(msg)
        else:
            self.err.fatal(msg)
    
    #--- USEFUL METHODS

    def get_current_sysid(self):
	"Returns the sysid of the file we are reading now."
	return self.current_sysID

    def set_sysid(self,sysID):
	"Sets the current system identifier. Does not store the old one."
	self.current_sysID=sysID

    def get_offset(self):
	"Returns the current offset from the start of the stream."
	return self.block_offset+self.pos
	
    def get_line(self):
	"Returns the current line number."
	self.update_pos()
	return self.line

    def get_column(self):
	"Returns the current column position."
	self.update_pos()
	return self.pos-self.last_break  

    def is_root_entity(self):
        "Returns true if the current entity is the root entity."
        return self.ent_stack==[]

    def is_external(self):
        """Returns true if the current entity is an external entity. The root
        (or document) entity is not considered external."""
        return self.ent_stack!=[] and \
               self.ent_stack[0][0]!=self.get_current_sysid()

    # --- Internal methods

    def _push_ent_stack(self,name="None"):
	self.ent_stack.append((self.get_current_sysid(),self.data,self.pos,\
                               self.line,self.last_break,self.datasize,\
                               self.last_upd_pos,self.block_offset,self.final,
                               name))

    def _pop_ent_stack(self):
	(self.current_sysID,self.data,self.pos,self.line,self.last_break,\
	 self.datasize,self.last_upd_pos,self.block_offset,self.final,dummy)=\
         self.ent_stack[-1]
	del self.ent_stack[-1]

# ==============================
# Common code for some parsers
# ==============================

class XMLCommonParser(EntityParser):

    def parse_external_id(self,required=0,sysidreq=1):
        """Parses an external ID declaration and returns a tuple consisting
        of (pubid,sysid). If the required attribute is false neither SYSTEM
        nor PUBLIC identifiers are required. If sysidreq is false a SYSTEM
        identifier is not required after a PUBLIC one."""

        pub_id=None
        sys_id=None
        
	if self.now_at("SYSTEM"):
	    self.skip_ws(1)
	    sys_id=self.get_wrapped_match([("\"",reg_sysid_quote),\
					   ("'",reg_sysid_apo)])
	elif self.now_at("PUBLIC"):
	    self.skip_ws(1)
	    pub_id=self.get_wrapped_match([("\"",reg_pubid_quote),\
					   ("'",reg_pubid_apo)])
            pub_id=string.join(string.split(pub_id))

            if sysidreq:
                self.skip_ws(1)
                sys_id=self.get_wrapped_match([("\"",reg_sysid_quote),\
                                               ("'",reg_sysid_apo)])
            else:
                if self.test_str("'") or self.test_str('"'):
                    self.report_error(3002)
                self.skip_ws()
                if self.test_str("'") or self.test_str('"'):
                    sys_id=self.get_wrapped_match([("\"",reg_sysid_quote),\
                                                   ("'",reg_sysid_apo)])
	else:
            if required: self.report_error(3006)

        return (pub_id,sys_id)

    def __get_quoted_string(self):
        "Returns the contents of a quoted string at current position."
        try:
            quo=self.data[self.pos]
        except IndexError:
            raise OutOfDataException()
            
        if not (self.now_at('"') or self.now_at("'")):
            self.report_error(3004,("'\"'","'"))
            self.scan_to(">")
            return ""

        return self.scan_to(quo)
    
    def parse_xml_decl(self,handler=None):
	"Parses the contents of the XML declaration from after the '<?xml'."

        textdecl=self.is_external() # If this is an external entity, then this
                                    # is a text declaration, not an XML decl

	self.update_pos()
	if self.get_column()!=5 or self.get_line()!=1 or \
           (self.ent_stack!=[] and not textdecl):
            if textdecl:
                self.report_error(3007)
            else:    
                self.report_error(3008)                
            
	if self.seen_xmldecl: # Set in parse_pi, to avoid block problems
            if textdecl:
                self.report_error(3009)
            else:
                self.report_error(3010)

	enc=None
	sddecl=None
        ver=None
	self.skip_ws()
        
	if self.now_at("version"):
	    self.skip_ws()
	    if not self.now_at("="): self.report_error(3005,"=")
	    self.skip_ws()
            ver=self.__get_quoted_string()

            m=reg_ver.match(ver)
            if m==None or m.end()!=len(ver):
                self.report_error(3901,ver)
            elif ver!="1.0":
		self.report_error(3046)                

            if self.test_str("encoding") or self.test_str("standalone"):
                self.report_error(3002)
	    self.skip_ws()
	elif not textdecl:
            self.report_error(3011)

	if self.now_at("encoding"):
	    self.skip_ws()
	    if not self.now_at("="): self.report_error(3005,"=")
	    self.skip_ws()
            enc=self.__get_quoted_string()
            if reg_enc_name.match(enc)==None:
                self.report_error(3902)

            self.report_error(1002,enc)
            
	    self.skip_ws()	    

	if self.now_at("standalone"):
            if textdecl:
                self.report_error(3012)
                sddecl="yes"
            else:
                self.skip_ws()
                if not self.now_at("="): self.report_error(3005,"=")
                self.skip_ws()
                sddecl=self.__get_quoted_string()
                if reg_std_alone.match(sddecl)==None:
                    self.report_error(3911)
                    
                self.standalone= sddecl=="yes"

                self.skip_ws()

	self.skip_ws()

        if handler!=None:
            handler.set_entity_info(ver,enc,sddecl)

    def parse_pi(self,handler,report_xml_decl=0):
	"""Parses a processing instruction from after the '<?' to beyond
	the '?>'."""
	trgt=self._get_name()

	if trgt=="xml":
            if report_xml_decl:
                self.parse_xml_decl(handler)
            else:
                self.parse_xml_decl()
                
	    if not self.now_at("?>"):
		self.report_error(3005,"?>")
	    self.seen_xmldecl=1
	else:
            if self.now_at("?>"):
                rem=""
            else:
                self.skip_ws(1)
                rem=self.scan_to("?>") # OutOfDataException if not found

	    if reg_res_pi.match(trgt)!=None:
		if trgt=="xml:namespace":
		    self.report_error(1003)
                elif trgt!="xml-stylesheet":
		    self.report_error(3045)
                
            handler.handle_pi(trgt,rem)   

    def parse_comment(self,handler):
	"Parses the comment from after '<!--' to beyond '-->'."
        try:
          handler.handle_comment(self.get_match(reg_comment_content))
        except RuntimeError, e:
          if str(e) == "maximum recursion limit exceeded":
            # RRD: the regex match function in get_match can fail with a
            # "maximum recursion limit exceeded" RuntimeError, which is most
            # common when parsing to the end of a long comment.  In this case,
            # search manually
            pos = self.pos
            while pos + 1 < self.datasize and \
                  ( self.data[pos] != '-' or self.data[pos+1] != '-' ):
              pos = pos + 1
            if pos == self.datasize or pos == self.datasize - 1:
              raise OutOfDataException()
            cmt = self.data[self.pos:pos]
    	    self.pos = pos
            handler.handle_comment(cmt)
          else:
            raise
	if not self.now_at("-->"):
	    self.report_error(3005,"-->")

    def _read_char_ref(self):
        "Parses a character reference and returns the character."
        if self.now_at("x"):
            digs=unhex(self.get_match(reg_hex_digits))
        else:
            digs=int(self.get_match(reg_digits))

        if not (digs==9 or digs==10 or digs==13 or \
                (digs>=32 and digs<=255)):
            if digs>255:
                self.report_error(1005,digs)
            else:
                self.report_error(3018,digs)
            return ""
        else:
            return chr(digs)

    def _get_name(self):
        """Parses the name at the current position and returns it. An error
        is reported if no name is present."""
	if self.pos>self.datasize-5 and not self.final:
	    raise OutOfDataException()

        data=self.data
        pos=self.pos
        if data[pos] in namestart:
            start=pos
            pos=pos+1

            try:
                while data[pos] in namechars:
                    pos=pos+1

                self.pos=pos
                return intern(data[start:pos])
            except IndexError:
                self.pos=pos
                if self.final:
                    return intern(data[start:])
                else:
                    raise OutOfDataException()
        else:
            self.report_error(3900)
            return ""            
    
# --- A collection of useful functions

# Utility functions

def unhex(hex_value):
    "Converts a string hex-value to an integer."

    sum=0
    for char in hex_value:
	sum=sum*16
	char=ord(char)
	
	if char<58 and char>=48:
	    sum=sum+(char-48)
	elif char>=97 and char<=102:
	    sum=sum+(char-87)
	elif char>=65 and char<=70:
	    sum=sum+(char-55)
	# else ERROR, but it can't occur here

    return sum

def matches(regexp,str):
    mo=regexp.match(str)
    return mo!=None and len(mo.group(0))==len(str)

def join_sysids_general(base,url):
    if urlparse.urlparse(base)[0]=="":
        if urlparse.urlparse(url)[0]=="":
            return os.path.join(os.path.split(base)[0],url)
        else:
            return url
    else:
        return urlparse.urljoin(base,url)

def join_sysids_win32(base,url):
    if len(urlparse.urlparse(base)[0])<2: # Handles drive identifiers correctly
        if len(urlparse.urlparse(url)[0])<2:
            return os.path.join(os.path.split(base)[0],url)
        else:
            return url
    else:
        return urlparse.urljoin(base,url)    

# here join_sysids(base,url): is set to the correct function

if sys.platform=="win32":
    join_sysids=join_sysids_win32
else:
    join_sysids=join_sysids_general
    
# --- Some useful regexps

namestart="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_:"+\
          "ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ"
namechars=namestart+"0123456789.·-"
whitespace="\n\t \r"

reg_ws=re.compile("[\n\t \r]+")
reg_ver=re.compile("[-a-zA-Z0-9_.:]+")
reg_enc_name=re.compile("[A-Za-z][-A-Za-z0-9._]*")
reg_std_alone=re.compile("yes|no")
reg_comment_content=re.compile("([^-]|-[^-])*")
reg_name=re.compile("["+namestart+"]["+namechars+"]*")
reg_names=re.compile("["+namestart+"]["+namechars+"]*"
		     "([\n\t \r]+["+namestart+"]["+namechars+"]*)*")
reg_nmtoken=re.compile("["+namechars+"]+")
reg_nmtokens=re.compile("["+namechars+"]+([\n\t \r]+["+namechars+"]+)*")
reg_sysid_quote=re.compile("[^\"]*")
reg_sysid_apo=re.compile("[^']*")
reg_pubid_quote=re.compile("[- \n\t\ra-zA-Z0-9'()+,./:=?;!*#@$_%]*")
reg_pubid_apo=re.compile("[- \n\t\ra-zA-Z0-9()+,./:=?;!*#@$_%]*")
reg_start_tag=re.compile("<[A-Za-z_:]")
reg_quoted_attr=re.compile("[^<\"]*")
reg_apo_attr=re.compile("[^<']*")
reg_c_data=re.compile("[<&]")
reg_pe_ref=re.compile("%["+namestart+"]["+namechars+"]*;")

reg_ent_val_quote=re.compile("[^\"]+")
reg_ent_val_apo=re.compile("[^\']+")

reg_attr_type=re.compile(r"CDATA|IDREFS|IDREF|ID|ENTITY|ENTITIES|NMTOKENS|"
			 "NMTOKEN") # NOTATION support separate
reg_attr_def=re.compile(r"#REQUIRED|#IMPLIED")

reg_digits=re.compile("[0-9]+")
reg_hex_digits=re.compile("[0-9a-fA-F]+")

reg_res_pi=re.compile("xml",re.I)

reg_int_dtd=re.compile("\"|'|<\\?|<!--|\\]|<!\\[")

reg_attval_stop_quote=re.compile("<|&|\"")
reg_attval_stop_sing=re.compile("<|&|'")

reg_decl_with_pe=re.compile("<(![^-\[]|\?)")
reg_subst_pe_search=re.compile(">|%")

reg_cond_sect=re.compile("<!\\[|\\]\\]>")
reg_litval_stop=re.compile("%|&#")

# RFC 1766 language codes

reg_lang_code=re.compile("([a-zA-Z][a-zA-Z]|[iIxX]-([a-zA-Z])+)(-[a-zA-Z])*")

# Mapping regexps to error codes
# NB: 3900 is reported directly from _get_name

reg2code={
    reg_name.pattern : 3900, reg_ver.pattern : 3901,
    reg_enc_name.pattern : 3902, reg_std_alone.pattern : 3903,
    reg_comment_content.pattern : 3904, reg_hex_digits.pattern : 3905,
    reg_digits.pattern : 3906, reg_pe_ref.pattern : 3907,
    reg_attr_type.pattern : 3908, reg_attr_def.pattern : 3909,
    reg_nmtoken.pattern : 3910}
    
# Some useful variables

class InternalEntity:

    def __init__(self,name,value):
        self.name=name
        self.value=value

    def is_internal(self):
        return 1

    def get_value(self):
        "Returns the replacement text of the entity."
        return self.value

predef_ents={"lt":"&#60;","gt":"&#62;","amp":"&#38;","apos":"&#39;",
             "quot":'&#34;'}

# Translation tables

ws_trans=string.maketrans("\r\t\n","   ")  # Whitespace normalization
id_trans=string.maketrans("","")           # Identity transform 

#############################################################################

# ==============================
# The default application class
# ==============================

class Application:
    """This is the class that represents the application that receives
    parsed data from the parser. It is meant to be subclassed by users."""

    def __init__(self):
	self.locator=None

    def set_locator(self,locator):
	"""Gives the application an object to ask for the current location.
	Called automagically by the parser."""
	self.locator=locator
    
    def doc_start(self):
	"Notifies the application of the start of the document."
	pass

    def doc_end(self):
	"Notifies the application of the end of the document."
	pass
	
    def handle_comment(self,data):
	"Notifies the application of comments."
	pass

    def handle_start_tag(self,name,attrs):
	"Notifies the application of start tags (and empty element tags)."
	pass

    def handle_end_tag(self,name):
	"Notifies the application of end tags (and empty element tags)."
	pass
    
    def handle_data(self,data,start,end):
	"Notifies the application of character data."
	pass

    def handle_ignorable_data(self,data,start,end):
	"Notifies the application of character data that can be ignored."
	pass
    
    def handle_pi(self,target,data):
	"Notifies the application of processing instructions."
	pass    

    def handle_doctype(self,root,pubID,sysID):
	"Notifies the application of the document type declaration."
	pass
    
    def set_entity_info(self,xmlver,enc,sddecl):
	"""Notifies the application of information about the current entity
	supplied by an XML or text declaration. All three parameters will be
        None, if they weren't present."""
	pass

# ==============================
# The public identifier resolver
# ==============================

class PubIdResolver:
    """An application class that resolves public identifiers to system
    identifiers."""

    def resolve_pe_pubid(self,pubid,sysid):
        """Maps the public identifier of a parameter entity to a system
        identifier. The default implementation just returns the system
        identifier."""
        return sysid
    
    def resolve_doctype_pubid(self,pubid,sysid):
        """Maps the public identifier of the DOCTYPE declaration to a system
        identifier. The default implementation just returns the system
        identifier."""
        return sysid

    def resolve_entity_pubid(self,pubid,sysid):
        """Maps the public identifier of an external entity to a system
        identifier. The default implementation just returns the system
        identifier."""
        return sysid
    
# ==============================
# The default error handler
# ==============================

class ErrorHandler:
    """An error handler for the parser. This class can be subclassed by clients
    that want to use their own error handlers."""

    def __init__(self,locator):
	self.locator=locator	

    def set_locator(self,loc):
	self.locator=loc

    def get_locator(self):
	return self.locator
	
    def warning(self,msg):
	"Handles a non-fatal error message."
	pass

    def error(self,msg):
	self.fatal(msg)

    # "The reports of the error's fatality are much exaggerated"
    # --Paul Prescod 
    
    def fatal(self,msg):
	"Handles a fatal error message."
        if self.locator==None:
            print "ERROR: "+msg
        else:
            print "ERROR: "+msg+" at %s:%d:%d" % (self.locator.get_current_sysid(),\
						  self.locator.get_line(),\
						  self.locator.get_column())
            print "TEXT: '%s'" % (self.locator.data[self.locator.pos:\
                                                    self.locator.pos+10])
        sys.exit(1)

# ==============================
# The default entity handler
# ==============================

class EntityHandler:
    "An entity handler for the parser."

    def __init__(self,parser):
	self.parser=parser
    
    def resolve_ent_ref(self,entname):
	"""Resolves a general entity reference and returns its contents. The
	default method only resolves the predefined entities. Returns a
	2-tuple (n,m) where n is true if the entity is internal. For internal
	entities m is the value, for external ones it is the system id."""

	try:
	    return (1,predef_ents[entname])
	except KeyError,e:
	    self.parser.report_error(3021,entname)
	    return (1,"")

# ==============================
# An inputsource factory
# ==============================

class InputSourceFactory:
    """
    A class that creates file-like objects from system identifiers.
    Note: this method has been modified to exclude the need for urllib, which
    means that general URL reads are disabled.
    """

    def create_input_source(self,sysid):
        if sysid[1:3]==":\\":
            return open(sysid)
        else:
            try:
              f = open(sysid)
            except:
              raise
            
            return f

#############################################################################

string_translate=string.translate # optimization. made 10% difference!
string_find     =string.find

version="0.70"
revision="$Revision: 1.2 $"
        
# ==============================
# A full well-formedness parser
# ==============================

class XMLProcessor(XMLCommonParser):
    "A parser that performs a complete well-formedness check."

    def __init__(self):        
	EntityParser.__init__(self)

	# Various handlers
	self.app = Application()
        self.stop_on_wf = 1
        self.pubres = PubIdResolver()
        
    def set_application(self,app):
	"Sets the object to send data events to."
	self.app = app
	app.set_locator(self)
        
    def set_data_after_wf_error(self,stop_on_wf=0):
        """Sets the parser policy on well-formedness errors. If this is set to
        0 data events are still delivered, even after well-formedness errors.
        Otherwise no more data events reach the application after such erors.
        """
        self.stop_on_wf=stop_on_wf

    def set_read_external_subset(self,read_it):
        """Tells the parser whether to read the external subset of documents
        or not."""
        self.read_external_subset=read_it
        
    def report_error(self,number,args=None):
        if self.stop_on_wf and number>2999:
            self.app=Application() # No more data events reported
        EntityParser.report_error(self,number,args)
        
    def reset(self):
        EntityParser.reset(self)

	# State vars
	self.stack=[]
	self.seen_root=0
	self.seen_doctype=0
	self.seen_xmldecl=0
        self.stop_on_wf=1
        self.read_external_subset=0

    def deref(self):
        "Deletes circular references."
        self.err = self.app = None

    def do_parse(self):
	"Does the actual parsing."
	try:
	    while self.pos<self.datasize:
		self.prepos=self.pos

		if self.data[self.pos]=="<":
                    t=self.data[self.pos+1] # Optimization
                    if t=="/":
                        self.parse_end_tag()
                    elif t!="!" and t!="?":
                        self.parse_start_tag()                        
                    elif self.now_at("<!--"):
                        self.parse_comment(self.app)
                    elif self.now_at("<?"): # FIXME: use t and modify self.pos?
                        self.parse_pi(self.app,1)
                    elif self.now_at("<![CDATA["):
                        self.parse_cdata()
                    elif self.now_at("<!DOCTYPE"):
                        self.parse_doctype()
                    else:
                        self.report_error(3013)
                        self.scan_to(">") # Avoid endless loops
                elif self.data[self.pos]=="&":
                    if self.now_at("&#"):
                        self.parse_charref()
                    else:
                        self.pos=self.pos+1  # Skipping the '&'
                        self.parse_ent_ref()
                else:
                    self.parse_data()

        except IndexError,e:            
            # Means self.pos was outside the buffer when we did a raw
            # compare.  This is both a little ugly and fragile to
            # changes, but this loop is rather time-critical, so we do
            # raw compares anyway.
            # Should try to lose this since it gets very hard to find
            # problems if the user throws an IndexError...
            
	    if self.final:
		raise OutOfDataException()
	    else:
		self.pos=self.prepos  # Didn't complete the construct        
	except OutOfDataException,e:
	    if self.final:
		raise e
	    else:
		self.pos=self.prepos  # Didn't complete the construct

    def parseStart(self):
	"Must be called before parsing starts. (Notifies application.)"        
	self.app.doc_start()

    def parseEnd(self):
	"""Must be called when parsing is finished. (Does some checks and "
	"notifies the application.)"""	    
	if self.stack!=[] and self.ent_stack==[]:
	    self.report_error(3014,self.stack[-1])
	elif not self.seen_root:
	    self.report_error(3015)

	self.app.doc_end()
	    
    def parse_start_tag(self):
	"Parses the start tag."
	self.pos=self.pos+1 # Skips the '<'
        name=self._get_name()
	self.skip_ws()

        attrs={}
        fixeds={}

        if self.data[self.pos]!=">" and self.data[self.pos]!="/":
            seen={}
            while not self.test_str(">") and not self.test_str("/>"):
                a_name=self._get_name()
                self.skip_ws()
                if not self.now_at("="):
                    self.report_error(3005,"=")
                    self.scan_to(">") ## Panic! Get out of the tag!
                    a_val=""
                    break
                self.skip_ws()

                a_val=self.parse_att_val()
                if a_val==-1:
                    # WF error, we've skipped the rest of the tag
                    self.pos=self.pos-1      # Lets us find the '>'
                    if self.data[self.pos-1]=="/":
                        self.pos=self.pos-1  # Gets the '/>' cases right
                    break  

                if seen.has_key(a_name):
                    self.report_error(3016,a_name)
                else:
                    seen[a_name]=1

                attrs[a_name]=a_val
                if fixeds.has_key(a_name) and fixeds[a_name]!=a_val:
                    self.report_error(2000,a_name)
                self.skip_ws()

	# --- Take care of the tag

	if self.stack==[] and self.seen_root:
	    self.report_error(3017)
	    
	self.seen_root=1
        
	if self.now_at(">"):
	    self.app.handle_start_tag(name,attrs)
            self.stack.append(name)
	elif self.now_at("/>"):
	    self.app.handle_start_tag(name,attrs)
	    self.app.handle_end_tag(name)
        else:
            self.report_error(3004,("'>'","/>"))

    def parse_att_val(self):
	"Parses an attribute value and resolves all entity references in it."

	val=""
        if self.now_at('"'):
            delim='"'
            reg_attval_stop=reg_attval_stop_quote
        elif self.now_at("'"):
            delim="'"
            reg_attval_stop=reg_attval_stop_sing
        else:
            self.report_error(3004,("'","\""))
            self.scan_to(">")
            return -1 # FIXME: Ugly. Should throw an exception instead       
	        
        while 1:
            piece=self.find_reg(reg_attval_stop)
            val=val+string_translate(piece,ws_trans)

	    if self.now_at(delim):
                break

	    if self.now_at("&#"):
                val=val+self._read_char_ref()
	    elif self.now_at("&"):
                name=self._get_name()

                if name in self.open_ents:
                    self.report_error(3019)
                    return
                else:
                    self.open_ents.append(name)
                
                try:
                    ent=InternalEntity(name, predef_ents[name])
                    if ent.is_internal():
                        # Doing all this here sucks a bit, but...
                        self.push_entity(self.get_current_sysid(),\
                                         ent.value,name)

                        self.final=1 # Only one block

                        val=val+self.parse_literal_entval()
                        if not self.pos==self.datasize:
                            self.report_error(3001) # Thing started, not compl

                        self.pop_entity()
                    else:
                        self.report_error(3020)
                except KeyError,e:
                    self.report_error(3021,name) ## FIXME: Check standalone dcl

                del self.open_ents[-1]

            elif self.now_at("<"):
                self.report_error(3022)
                continue
	    else:
		self.report_error(4001)
                self.pos=self.pos+1    # Avoid endless loop
                continue
		
	    if not self.now_at(";"):
		self.report_error(3005,";")
            
        return val

    def parse_literal_entval(self):
	"Parses a literal entity value for insertion in an attribute value."

	val=""
        reg_stop=re.compile("&")
	        
        while 1:
            try:
                piece=self.find_reg(reg_stop)
            except OutOfDataException,e:
                # Only character data left
                val=val+string_translate(self.data[self.pos:],ws_trans)
                self.pos=self.datasize
                break
            
            val=val+string_translate(piece,ws_trans)

	    if self.now_at("&#"):
                val=val+self._read_char_ref()		
	    elif self.now_at("&"):
                name=self._get_name()

                if name in self.open_ents:
                    self.report_error(3019)
                    return ""
                else:
                    self.open_ents.append(name)
                
                try:
                    ent=InternalEntity(name, predef_ents[name])
                    if ent.is_internal():
                        # Doing all this here sucks a bit, but...
                        self.push_entity(self.get_current_sysid(),\
                                         ent.value,name)

                        self.final=1 # Only one block

                        val=val+self.parse_literal_entval()
                        if not self.pos==self.datasize:
                            self.report_error(3001)

                        self.pop_entity()
                    else:
                        self.report_error(3020)
                except KeyError,e:
                    self.report_error(3021,name)	       

                del self.open_ents[-1]
                    
	    else:
		self.report_error(4001)
		
	    if not self.now_at(";"):
		self.report_error(3005,";")
		self.scan_to(">")
                            
	return val
    
    def parse_end_tag(self):
	"Parses the end tag from after the '</' and beyond '>'."
        self.pos=self.pos+2 # Skips the '</'
        name=self._get_name()
        
	if self.data[self.pos]!=">":
            self.skip_ws() # Probably rare to find whitespace here
            if not self.now_at(">"): self.report_error(3005,">")
        else:
            self.pos=self.pos+1

	try:
            elem=self.stack[-1]
            del self.stack[-1]
            if name!=elem:
		self.report_error(3023,(name,elem))

		# Let's do some guessing in case we continue
		if len(self.stack)>0 and self.stack[-1]==name:
                    del self.stack[-1]
                else:
                    self.stack.append(elem) # Put it back

	except IndexError,e:
	    self.report_error(3024,name)

        self.app.handle_end_tag(name)

    def parse_data(self):
	"Parses character data."
        start=self.pos
        end=string_find(self.data,"<",self.pos)
        if end==-1:
            end=string_find(self.data,"&",self.pos)
            
            if end==-1:
                if not self.final:
                    raise OutOfDataException()

                end=self.datasize
        else:
            ampend=string_find(self.data,"&",self.pos,end)
            if ampend!=-1:
                end=ampend

        self.pos=end
        
	if string_find(self.data,"]]>",start,end)!=-1:
	    self.pos=string_find(self.data,"]]>",start,end)
	    self.report_error(3025)
            self.pos=self.pos+3 # Skipping over it

	if self.stack==[]:
	    res=reg_ws.match(self.data,start)                
	    if res==None or res.end(0)!=end:
		self.report_error(3029)
        else:
            self.app.handle_data(self.data,start,end)

    def parse_charref(self):
	"Parses a character reference."
	if self.now_at("x"):
	    digs=unhex(self.get_match(reg_hex_digits))
	else:
            try:
                digs=int(self.get_match(reg_digits))
            except ValueError,e:
                self.report_error(3027)
                digs=None

	if not self.now_at(";"): self.report_error(3005,";")
        if digs==None: return
	    
	if not (digs==9 or digs==10 or digs==13 or \
		(digs>=32 and digs<=255)):
	    if digs>255:
		self.report_error(1005,digs)
	    else:
		self.report_error(3018,digs)
	else:
	    if self.stack==[]:
		self.report_error(3028)
	    self.app.handle_data(chr(digs),0,1)

    def parse_cdata(self):
	"Parses a CDATA marked section from after the '<![CDATA['."
	new_pos=self.get_index("]]>")
	if self.stack==[]:
	    self.report_error(3029)
	self.app.handle_data(self.data,self.pos,new_pos)
	self.pos=new_pos+3

    def parse_ent_ref(self):
	"Parses a general entity reference from after the '&'."
        name=self._get_name()
	if not self.now_at(";"): self.report_error(3005,";")

        try:
            ent=InternalEntity(name, predef_ents[name])
	except KeyError,e:
	    self.report_error(3021,name)
            return

	if ent.name in self.open_ents:
	    self.report_error(3019)
	    return
        
        self.open_ents.append(ent.name)
        
	if self.stack==[]:
	    self.report_error(3030)

        # Storing size of current element stack
        stack_size=len(self.stack)
            
	if ent.is_internal():
	    self.push_entity(self.get_current_sysid(),ent.value,name)
            try:
                self.do_parse()
            except OutOfDataException: # Ran out of data before done
                self.report_error(3001)
            
	    self.flush()
	    self.pop_entity()
	else:
	    if ent.notation!="":
		self.report_error(3031)

            tmp=self.seen_xmldecl
            self.seen_xmldecl=0 # Avoid complaints
            self.seen_root=0    # Haven't seen root in the new entity yet
            self.open_entity(self.pubres.resolve_entity_pubid(ent.get_pubid(),
                                                              ent.get_sysid()),
                             name)
            self.seen_root=1 # Entity references only allowed inside elements
            self.seen_xmldecl=tmp

        # Did any elements cross the entity boundary?
        if stack_size!=len(self.stack):
            self.report_error(3042)
            
	del self.open_ents[-1]
	
    def parse_doctype(self):
	"Parses the document type declaration."

	if self.seen_doctype:
	    self.report_error(3032)
	if self.seen_root:
	    self.report_error(3033)
	
	self.skip_ws(1)
        rootname=self._get_name()
	self.skip_ws(1)

        (pub_id,sys_id)=self.parse_external_id()
	self.skip_ws()

        self.app.handle_doctype(rootname, pub_id, sys_id)
        
	if self.now_at("["):
            raise DTDDisabledError, "DTD parsing disabled"
	elif not self.now_at(">"):
            self.report_error(3005,">")

        # External subset must be parsed _after_ the internal one
	if pub_id!=None or sys_id!=None: # Was there an external id at all?
            if self.read_external_subset:
                raise DTDDisabledError, "DTD parsing disabled"

        if (pub_id == None and sys_id == None) or \
           not self.read_external_subset:
            # If we parse the external subset dtd_end is called for us by
            # the dtd parser. If we don't we must call it ourselves.
              raise DTDDisabledError, "DTD parsing disabled"
            
	self.seen_doctype=1 # Has to be at the end to avoid block trouble
    
    # ===== The introspection methods =====
        
    def get_elem_stack(self):
        "Returns the internal element stack. Note: this is a live list!"
        return self.stack

    def get_data_buffer(self):
        "Returns the current data buffer."
        return self.data

    def get_construct_start(self):
        """Returns the start position of the current construct (tag, comment,
        etc)."""
        return self.prepos

    def get_construct_end(self):
        """Returns the end position of the current construct (tag, comment,
        etc)."""
        return self.pos

    def get_raw_construct(self):
        "Returns the raw form of the current construct."
        return self.data[self.prepos:self.pos]

    def get_current_ent_stack(self):
        """Returns a snapshot of the entity stack. A list of the system
        identifier of the entity and its name, if any."""
        return map(lambda ent: (ent[0],ent[9]),self.ent_stack)

#############################################################################

class XmlProcErrorHandler(ErrorHandler):

    def __init__(self, locator, parser, warnings, entstack, rawxml):
        ErrorHandler.__init__(self,locator)
        self.show_warnings=warnings
        self.show_entstack=entstack
        self.show_rawxml=rawxml
        self.parser=parser
        self.messages = '\n'
        self.reset()
    
    def __format_message(self, msg, warning=0):
        
        if warning:
          s = "%s: Warning: %s\n" % (self.get_location(),msg)
        else:
          s = "%s: Error: %s\n" % (self.get_location(),msg)
        
        if self.show_entstack:
            for item in self.parser.get_current_ent_stack():
                s = s + "  %s: %s\n" % item
        
        if self.show_rawxml:
            try:
              raw=self.parser.get_raw_construct()
              if len(raw)>50:
                  s = s + "  Raw construct too big, suppressed.\n"
              else:
                  s = s + "  '%s'\n" % raw
            except:
              pass
        
        return s

    def get_location(self):
        return "%s:%d:%d" % (self.locator.get_current_sysid(), \
                             self.locator.get_line(), \
                             self.locator.get_column())
    
    def warning(self,msg):
        if self.show_warnings:
            self.messages = self.messages + \
                            self.__format_message(msg, warning=1)
            self.warnings=self.warnings+1
    
    def error(self,msg):
        self.fatal(msg)
    
    def fatal(self,msg):
        self.messages = self.messages + self.__format_message(msg)
        self.errors=self.errors+1
    
    def reset(self):
        self.errors=0
        self.warnings=0        

#############################################################################

class XmlProcError(Exception):
    def __init__(self, msg=""): self.msg = msg
    def __str__(self): return self.msg


class XmlProcDocReader(Application):
    """
    The handler functions, if set, have the following meaning and arguments:
    
        error_function (err_msg)      - called when an XML syntax error occurs
        begin_function (tag_name,
                        line_number,
                        attr_dict)    - called for begin tags
        content_function (data)       - called when content is encountered;
                                        may be called multiple times for a
                                        given tag
        end_function (tag_name)       - called for end tags
    
    If a function is not set, the data is ignored.  If the error function
    is not set and an error occurs, an XmlProcError is raised.
    """
    
    def __init__(self):
        Application.__init__(self)
        self.processor = XMLProcessor()
        self.err = XmlProcErrorHandler(self.processor, self.processor, 1, 1, 1)
        self.processor.set_error_handler(self.err)
        self.processor.set_application(self)
        self.errfunc = None
        self.beginfunc = None
        self.contentfunc = None
        self.endfunc = None
        self.commentfunc = None
    
    def setErrorHandler (self, errfunc):       self.errfunc = errfunc
    def setBeginHandler (self, beginfunc):     self.beginfunc = beginfunc
    def setContentHandler (self, contentfunc): self.contentfunc = contentfunc
    def setEndHandler (self, endfunc):         self.endfunc = endfunc
    def setCommentHandler (self, commentfunc): self.commentfunc = commentfunc
    
    def readDoc(self, filename):
        self.err.reset()
        self.processor.reset()
        self.processor.parse_resource(filename)
        if self.err.errors > 0:
          if self.errfunc != None:
            self.errfunc(self.err.messages)
          else:
            raise XmlProcError, self.err.messages
    
    def handle_start_tag(self,name,amap):
        attrs = {}
        line_no = self.locator.get_line()
        for (name, value) in amap.items():
            attrs[name] = value
        if self.beginfunc != None:
          self.beginfunc(name, line_no, attrs)
    
    def handle_data(self,data,start_ix,end_ix):
        if self.contentfunc != None:
          self.contentfunc(data[start_ix:end_ix])
    
    def handle_end_tag(self,name):
        if self.endfunc != None:
          self.endfunc(name)
    
    def handle_comment(self,data):
        if self.commentfunc != None:
          self.commentfunc(data)

#############################################################################

class AReceiver:
  def __init__(self):
    pass
  def error(self, msg):
    print "error:", msg
  def begin(self, tag, line, attrs):
    print "tag", tag, "line", line, "attrs", attrs
  def content(self, data):
    print "content:", data
  def end(self, tag):
    print "end:", tag

def commenthandler(cmt):
  print 'comment:"' + cmt + '"'

if __name__ == "__main__":
    
    if len(sys.argv) < 2:
      print "*** error: please specify a file to parse"
      sys.exit(1)
    
    print "xmlproc version %s" % version
    
    recv = AReceiver()
    
    doc = XmlProcDocReader()
    
    doc.setErrorHandler (recv.error)
    doc.setBeginHandler (recv.begin)
    doc.setContentHandler (recv.content)
    doc.setEndHandler (recv.end)
    doc.setCommentHandler(commenthandler)
    
    doc.readDoc(sys.argv[1])
    
    print "Parse complete, %d error(s) and %d warning(s)" % \
          (doc.err.errors, doc.err.warnings)
    print " "
