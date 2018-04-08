#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import string, re
import types
import fnmatch

import TestSpec


alphanum_chars = 'abcdefghijklmnopqrstuvwxyz' + \
                 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' + \
                 '0123456789_'

extra_chars = '-+=#@%^:.~'

alphanum_chars_dict = {}
for c in alphanum_chars:
  alphanum_chars_dict[c] = None

extra_chars_dict = {}
for c in extra_chars:
  extra_chars_dict[c] = None

def allowableKeyword(s):
    for c in s:
      if not alphanum_chars_dict.has_key(c) and \
         not extra_chars_dict.has_key(c):
        return 0
    return 1


###########################################################################

class WordExpression:
    """
    Takes a string consisting of words, parentheses, and the operators "and",
    "or", and "not".  A word is any sequence of characters not containing
    a space or a parenthesis except the special words "and", "or", and "not".
    The initial string is parsed during construction then later evaluated
    with the evaluate() method.  Each word is evaluated to true or false
    based on an evaluator function given to the evaluate() method.
    """
    
    def __init__(self, expr=None):
        """
        Throws a ValueError if the first argument is an invalid expression.
        """
        self.expr = None

        self.wordL = []   # list of the words in the expression
        
        self.has_results_keywords = 0
        
        self.evalexpr = None
        self.nr_evalexpr = None
        if expr != None:
          self.append(expr)
    
    def append(self, expr, operator='or'):
        """
        Appends the given expression string using an 'and' or 'or' operator.
        If the 'expr' is a python list, then the "k-format" is assumed, where
        k-format is, for example, ["key1/key2", "!key3"] and comes from a
        command line such as "-k key1/key2 -k !key3".
        """
        if operator not in ['or','and']:
          raise ValueError( "the 'operator' argument must be 'or' or 'and'" )
        
        if expr != None:
          
          if type(expr) == types.ListType:
            # convert from k-format
            S = '' ; altS = ''
            for grp in expr:
              L = [] ; altL = []
              for k in grp.split('/'):
                k = string.strip(k)
                bang = ''
                while k[:1] == '!':
                  k = k[1:].strip()
                  if bang: bang = ''  # two bangs in a row cancel out
                  else: bang = 'not '
                if k and allowableKeyword(k):
                  if k in TestSpec.results_keywords:
                    self.has_results_keywords = 1
                  else:
                    altL.append( bang + k )
                  L.append( bang + k )
                else:
                  pass  # should be an error but is currently ignored
              if len(L) > 0:
                if S: S += ' and '
                S += '( ' + string.join(L,' or ') + ' )'
              if len(altL) > 0:
                if altS: altS += ' and '
                altS += '( ' + string.join(altL,' or ') + ' )'
            expr = string.join( S.split() )
          
          else:
            expr = string.join( expr.split() )
          
          # note that empty expressions or subexpressions evaluate to false;
          # however, for non-results expressions or subexpressions they
          # are ignored
          
          if operator == 'or':
            if self.expr and expr:
              if len(expr.split()) == 1:
                expr = self.expr+' or '+expr
              else:
                expr = self.expr+' or ('+expr+')'
            elif self.expr:
              expr = self.expr
          else:
            if self.expr and expr:
              if len(expr.split()) == 1:
                expr = self.expr+' and '+expr
              else:
                expr = self.expr+' and ('+expr+')'
            elif self.expr != None:
              # empty expressions evaluate to false so no point in
              # combining the two expressions
              expr = ''

          # parse both expressions
          self.expr = expr
          self.evalexpr = self._parse( expr, self.wordL )
    
    def getWordList(self):
        """
        Returns a list containing the words in the current expression.
        """
        return [] + self.wordL

    def containsResultsKeywords(self):
        """
        """
        return self.has_results_keywords
    
    def keywordEvaluate(self, keyword_list):
        """
        Returns the evaluation of the expression against a simple keyword list.
        """
        return self.evaluate( lambda k: k in keyword_list )
    
    def evaluate(self, evaluator_func):
        """
        Evaluates the expression from left to right using the given
        'evaluator_func' to evaluate each value string.  If the original
        expression string is empty, false is returned.  If no expression was
        set in this object, true is returned.
        """
        if self.evalexpr == None: return 1
        if not self.expr: return 0
        
        def evalfunc(tok):
          if evaluator_func(tok): return 1
          return 0
        r = eval( self.evalexpr )
        
        return r

    def __repr__(self):
        if self.expr == None:return 'WordExpression=None'
        return 'WordExpression="' + self.expr + '"'
    
    def __str__(self): return self.__repr__()
    
    def _parse(self, expr, wordL):
        """
        Throws a ValueError if the string is an invalid expression.
        Returns the final expression string (which may be modified from the
        original).
        """
        if len(wordL) > 0: del wordL[:]
        if expr:
          
          L1 = []
          for tok1 in expr.split():
            L2 = []
            for tok2 in tok1.split('('):
              L3 = []
              for tok3 in tok2.split(')'):
                if tok3 in ['','(',')','not','and','or']:
                  L3.append(tok3)
                else:
                  wordL.append( tok3 )
                  L3.append( '(evalfunc("'+tok3+'")==1)' )
              L2.append( string.join( L3, ')' ) )
            L1.append( string.join( L2, '(' ) )
          
          if len(L1) == 0:
            raise ValueError( 'invalid option expression: <empty expression>' )
          
          s = string.join( L1 )
          
          # evaluate the expression to test validity
          try:
            def evalfunc(tok): return 1
            v = eval( s )
            if hasattr(types, 'BooleanType'):
              assert type(v) == types.BooleanType
            else:
              assert type(v) == types.IntType
          except Exception, e:
            raise ValueError( 'invalid option expression: "' + expr + '"' )
          
          expr = s
        
        return expr


##############################################################################

class ParamFilter:
    
    def __init__(self, expr=None):
        """
        If 'expr' is not None, load() is called.
        """
        self.wexpr = None
        self.wordD = {}
        if expr != None:
          self.load(expr)
    
    def load(self, expr):
        """
        Loads the parameter specifications.  The 'expr' argument can be either
        a string word expression or a list of strings.
        
        If a list, each string is composed of parameter specifications
        separated by a '/' character.  A parameter specification is of the
        form:
          
          np        parameter np is defined
          np=       same as "np"
          !np       parameter np is not defined
          np!=      same as "!np"
          np<=4     parameter is less than or equal to four
          np>=4     parameter is greater than or equal to four
          np<4      parameter is less than four
          np>4      parameter is greater than four
          !np=4     not parameter is equal to four
        
        The parameter specifications separated by '/' are OR'ed together and
        the list entries are AND'ed together.
        
        Raises a ValueError if the expression contains a syntax error.
        """
        if type(expr) == types.ListType:
          # 'expr' is a list of strings that are AND'ed together
          self.wexpr = WordExpression()
          for ors in expr:
            # the divide character is used as an OR operator
            L = []
            for s in string.split(ors,'/'):
              if string.strip(s):
                L.append(s)
            x = string.join( L, ' or ' )
            self.wexpr.append(x, 'and')
        else:
          self.wexpr = WordExpression(expr)
        
        # map each word that appears to an evaluation function object instance
        self.wordD = {}
        for w in self.wexpr.getWordList():
          self.wordD[w] = self._make_func(w)
    
    def evaluate(self, paramD):
        """
        Evaluate the expression previously loaded against the given parameter
        values.  Returns true or false.
        """
        if self.wexpr == None:
          return 1
        evalobj = ParamFilter.Evaluator(self.wordD, paramD)
        return self.wexpr.evaluate( evalobj.evaluate )
    
    class Evaluator:
        def __init__(self, wordD, paramD):
            self.wordD = wordD
            self.paramD = paramD
        def evaluate(self, word):
            return self.wordD[word].evaluate(self.paramD)
    
    def _make_func(self, word):
        """
        Returns an instance of an evaluation class based on the word.
        """
        if not word: raise ValueError( 'empty word (expected a word)' )
        if word[0] == '!':
          f = self._make_func( word[1:] )
          if isinstance(f, ParamFilter.EvalLE):
            return ParamFilter.EvalGT(f.p, f.v)
          if isinstance(f, ParamFilter.EvalGE):
            return ParamFilter.EvalLT(f.p, f.v)
          if isinstance(f, ParamFilter.EvalNE):
            return ParamFilter.EvalEQ(f.p, f.v)
          if isinstance(f, ParamFilter.EvalLT):
            return ParamFilter.EvalGE(f.p, f.v)
          if isinstance(f, ParamFilter.EvalGT):
            return ParamFilter.EvalLE(f.p, f.v)
          if isinstance(f, ParamFilter.EvalEQ):
            return ParamFilter.EvalNE(f.p, f.v)
        L = string.split( word, '<=', 1 )
        if len(L) > 1:
          return ParamFilter.EvalLE( L[0], L[1] )
        L = string.split( word, '>=', 1 )
        if len(L) > 1:
          return ParamFilter.EvalGE( L[0], L[1] )
        L = string.split( word, '!=', 1 )
        if len(L) > 1:
          return ParamFilter.EvalNE( L[0], L[1] )
        L = string.split( word, '<', 1 )
        if len(L) > 1:
          return ParamFilter.EvalLT( L[0], L[1] )
        L = string.split( word, '>', 1 )
        if len(L) > 1:
          return ParamFilter.EvalGT( L[0], L[1] )
        L = string.split( word, '=', 1 )
        if len(L) > 1:
          return ParamFilter.EvalEQ( L[0], L[1] )
        return ParamFilter.EvalEQ( word, '' )
    
    class EvalEQ:
        def __init__(self, param, value):
            if not param: raise ValueError( 'parameter name is empty' )
            self.p = param ; self.v = value
        def evaluate(self, paramD):
            v = paramD.get(self.p,None)
            if self.v:
              if v == None: return 0  # paramD does not have the parameter
              if type(v) == types.IntType: return v == int(self.v)
              elif type(v) == types.FloatType: return v == float(self.v)
              if v == self.v: return 1
              try:
                if int(v) == int(self.v): return 1
              except: pass
              try:
                if float(v) == float(self.v): return 1
              except: pass
              return 0
            return v != None  # true if paramD has the parameter name
    
    class EvalNE:
        def __init__(self, param, value):
            if not param: raise ValueError( 'parameter name is empty' )
            self.p = param ; self.v = value
        def evaluate(self, paramD):
            v = paramD.get(self.p,None)
            if self.v:
              if v == None: return 0  # paramD does not have the parameter
              if type(v) == types.IntType: return v != int(self.v)
              elif type(v) == types.FloatType: return v != float(self.v)
              if v == self.v: return 0
              try:
                if int(v) == int(self.v): return 0
              except: pass
              try:
                if float(v) == float(self.v): return 0
              except: pass
              return 1
            return v == None  # true if paramD does not have the parameter name
    
    class EvalLE:
        def __init__(self, param, value):
            if not param: raise ValueError( 'parameter name is empty' )
            if not value: raise ValueError( "empty less-equal value" )
            self.p = param ; self.v = value
        def evaluate(self, paramD):
            v = paramD.get(self.p,None)
            if v == None: return 0
            if type(v) == types.IntType: return v <= int(self.v)
            elif type(v) == types.FloatType: return v <= float(self.v)
            if v == self.v: return 1
            try:
              if int(v) > int(self.v): return 0
              return 1
            except: pass
            try:
              if float(v) > float(self.v): return 0
              return 1
            except: pass
            return v <= self.v
    
    class EvalGE:
        def __init__(self, param, value):
            if not param: raise ValueError( 'parameter name is empty' )
            if not value: raise ValueError( "empty greater-equal value" )
            self.p = param ; self.v = value
        def evaluate(self, paramD):
            v = paramD.get(self.p,None)
            if v == None: return 0
            if type(v) == types.IntType: return v >= int(self.v)
            elif type(v) == types.FloatType: return v >= float(self.v)
            if v == self.v: return 1
            try:
              if int(v) < int(self.v): return 0
              return 1
            except: pass
            try:
              if float(v) < float(self.v): return 0
              return 1
            except: pass
            return v >= self.v
    
    class EvalLT:
        def __init__(self, param, value):
            if not param: raise ValueError( 'parameter name is empty' )
            if not value: raise ValueError( "empty less-than value" )
            self.p = param ; self.v = value
        def evaluate(self, paramD):
            v = paramD.get(self.p,None)
            if v == None: return 0
            if type(v) == types.IntType: return v < int(self.v)
            elif type(v) == types.FloatType: return v < float(self.v)
            if v == self.v: return 0
            try:
              if int(v) >= int(self.v): return 0
              return 1
            except: pass
            try:
              if not float(v) < float(self.v): return 0
              return 1
            except: pass
            return v < self.v
    
    class EvalGT:
        def __init__(self, param, value):
            if not param: raise ValueError( 'parameter name is empty' )
            if not value: raise ValueError( "empty greater-than value" )
            self.p = param ; self.v = value
        def evaluate(self, paramD):
            v = paramD.get(self.p,None)
            if v == None: return 0
            if type(v) == types.IntType: return v > int(self.v)
            elif type(v) == types.FloatType: return v > float(self.v)
            if v == self.v: return 0
            try:
              if int(v) <= int(self.v): return 0
              return 1
            except: pass
            try:
              if not float(v) > float(self.v): return 0
              return 1
            except: pass
            return v > self.v


######################################################################

if __name__ == "__main__":

    # this component is called as a 

    import getopt
    optL,argL = getopt.getopt( sys.argv[1:], "p:o:f:" )
    for n,v in optL:
        if n == '-p':
            pD = {}
            for param,value in [ s.split('/') for s in argL[0].split() ]:
                pD[param] = value
            pf = ParamFilter( v )
            if pf.evaluate( pD ):
                sys.stdout.write( 'true' )
            else:
                sys.stdout.write( 'false' )
            break

        elif n == '-f':
            wx = WordExpression( v )
            if wx.evaluate( lambda wrd: wrd == argL[0] ):
                sys.stdout.write( 'true' )
            else:
                sys.stdout.write( 'false' )
            break

        elif n == '-o':
            opts = argL[0].split()
            wx = WordExpression( v )
            if wx.evaluate( opts.count ):
                sys.stdout.write( 'true' )
            else:
                sys.stdout.write( 'false' )
            break

