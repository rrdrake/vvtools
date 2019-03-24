#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

import os, sys
import re
import fnmatch

try:
  from teststatus import RESULTS_KEYWORDS
except ImportError:
  from .teststatus import RESULTS_KEYWORDS


class WordExpression:
    """
    Takes a string consisting of words, parentheses, and the operators "and",
    "or", and "not".  A word is any sequence of characters not containing
    a space or a parenthesis except the special words "and", "or", and "not".
    The initial string is parsed during construction then later evaluated
    with the evaluate() method.  Each word is evaluated to true or false
    based on an evaluator function given to the evaluate() method.

    Without an expression (a None), the evaluate method will always return
    True, while an empty string for an expression will always evaluate to
    False.
    """
    
    def __init__(self, expr=None):
        ""
        self.expr = None

        self.words = set()   # the words in the expression
        
        self.evalexpr = None
        self.nr_evalexpr = None

        if expr != None:
            self.append( expr )

    def append(self, expr, operator='or'):
        """
        Appends the given expression string using an 'and' or 'or' operator.
        """
        assert operator in ['or','and']

        if expr != None:

            expr = expr.strip()

            if self.expr != None:
                expr = combine_two_expressions( self.expr, expr, operator )

            self.expr = expr

            self.evalexpr = parse_word_expression( self.expr, self.words )
            self.nr_evalexpr = parse_non_results_expression( self.expr )

    def getWordList(self):
        """
        Returns a list containing the words in the current expression.
        """
        return list( self.words )

    def containsResultsKeywords(self):
        ""
        return len( set( RESULTS_KEYWORDS ).intersection( self.words ) ) > 0

    def keywordEvaluate(self, keyword_list):
        """
        Returns the evaluation of the expression against a simple keyword list.
        """
        return self.evaluate( lambda k: k in keyword_list )

    def evaluate(self, evaluator_func, include_results=True):
        """
        Evaluates the expression from left to right using the given
        'evaluator_func' to evaluate True/False of each word.  If the original
        expression string is empty, false is returned.  If no expression was
        set in this object, true is returned.

        If 'include_results' is False, the original expression is stripped
        of results keywords and the resulting expression is evaluated.
        """
        if include_results:
            evex = self.evalexpr
        else:
            evex = self.nr_evalexpr

        if evex == None:
            return True

        def evalfunc(tok):
            if evaluator_func(tok): return True
            return False

        r = eval( evex )

        return r

    def __repr__(self):
        if self.expr == None:return 'WordExpression=None'
        return 'WordExpression="' + self.expr + '"'
    
    def __str__(self): return self.__repr__()


def combine_two_expressions( expr1, expr2, operator ):
    ""
    if operator == 'or':

        if expr1 and expr2:
            expr = expr1 + ' or ' + conditional_paren_wrap( expr2 )
        elif expr1:
            expr = expr1
        else:
            expr = expr2

    else:
        if expr1 and expr2:
            expr = expr1 + ' and ' + conditional_paren_wrap( expr2 )
        else:
            # one expression is empty, which is always false,
            # so replace the whole thing with an empty expr
            expr = ''

    return expr


def conditional_paren_wrap( expr ):
    ""
    if ' ' in expr:
        return '( '+expr+' )'
    return expr


def parse_word_expression( expr, wordset=None ):
    """
    Throws a ValueError if the string is an invalid expression.
    Returns the final expression string (which may be modified from the
    original).
    """
    if wordset != None:
        wordset.clear()

    toklist = separate_expression_into_tokens( expr )
    evalexpr = convert_token_list_into_eval_string( toklist )

    if wordset != None:
        add_words_to_set( toklist, wordset )

    def evalfunc(tok):
        return True
    try:
        # evaluate the expression to test validity
        v = eval( evalexpr )
        assert type(v) == type(False)
    except Exception:
        raise ValueError( 'invalid option expression: "' + expr + '"' )

    return evalexpr


def parse_non_results_expression( expr ):
    ""
    nrmod = NonResultsExpressionModifier( expr )
    toklist = nrmod.getNonResultsTokenList()

    if len( toklist ) == 0:
        return None

    else:
        evalexpr = convert_token_list_into_eval_string( toklist )
        return evalexpr


class NonResultsExpressionModifier:

    def __init__(self, expr):
        ""
        self.toklist = separate_expression_into_tokens( expr )
        self.toki = 0

        self.nonresults_toklist = self.parse_subexpr()

        trim_leading_binary_operator( self.nonresults_toklist )

    def getNonResultsTokenList(self):
        ""
        return self.nonresults_toklist

    def parse_subexpr(self):
        ""
        toklist = []
        oplist = []

        while self.toki < len( self.toklist ):

            tok = self.toklist[ self.toki ]
            self.toki += 1

            if tok in _OPERATOR_LIST:
                if tok == ')':
                    break
                elif tok == '(':
                    sublist = self.parse_subexpr()
                    if sublist:
                        append_sublist( toklist, oplist, sublist )
                    oplist = []
                else:
                    oplist.append( tok )

            elif tok in RESULTS_KEYWORDS:
                oplist = []

            else:
                append_token( toklist, oplist, tok )
                oplist = []

        return toklist


def trim_leading_binary_operator( toklist ):
    ""
    if toklist:
        if toklist[0] == 'and' or toklist[0] == 'or':
            toklist.pop( 0 )


def append_sublist( toklist, oplist, sublist ):
    ""
    append_operator( toklist, oplist )

    if oplist and len( sublist ) > 1:
        sublist = ['(']+sublist+[')']

    toklist.extend( sublist )


def append_token( toklist, oplist, tok ):
    ""
    append_operator( toklist, oplist )
    toklist.append( tok )


def append_operator( toklist, oplist ):
    ""
    if oplist:
        toklist.extend( oplist )


_OPERATOR_LIST = ['(',')','not','and','or']

def convert_token_list_into_eval_string( toklist ):
    ""
    modified_toklist = []

    for tok in toklist:
        if tok in _OPERATOR_LIST:
            modified_toklist.append( tok )
        elif tok:
            modified_toklist.append( '(evalfunc("'+tok+'")==True)' )
        else:
            modified_toklist.append( 'False' )

    return ' '.join( modified_toklist )


def add_words_to_set( toklist, wordset ):
    ""
    for tok in toklist:
        if tok and tok not in _OPERATOR_LIST:
            wordset.add( tok )


def separate_expression_into_tokens( expr ):
    ""
    toklist = []

    if expr.strip():

        for whitetok in expr.strip().split():
            for lptok in split_but_retain_separator( whitetok, '(' ):
                for rptok in split_but_retain_separator( lptok, ')' ):
                    rptok = rptok.strip()
                    if rptok:
                        toklist.append( rptok )

    else:
        toklist.append( '' )

    return toklist


def split_but_retain_separator( expr, separator ):
    ""
    seplist = []

    splitlist = list( expr.split( separator ) )
    last_token = len(splitlist) - 1

    for i,tok in enumerate( splitlist ):
        seplist.append( tok )
        if i < last_token:
            seplist.append( separator )

    return seplist


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
        if type(expr) == type([]):
          # 'expr' is a list of strings that are AND'ed together
          self.wexpr = WordExpression()
          for ors in expr:
            # the divide character is used as an OR operator
            L = []
            for s in ors.split('/'):
              if s.strip():
                L.append(s)
            x = ' or '.join( L )
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
        L = word.split( '<=', 1 )
        if len(L) > 1:
          return ParamFilter.EvalLE( L[0], L[1] )
        L = word.split( '>=', 1 )
        if len(L) > 1:
          return ParamFilter.EvalGE( L[0], L[1] )
        L = word.split( '!=', 1 )
        if len(L) > 1:
          return ParamFilter.EvalNE( L[0], L[1] )
        L = word.split( '<', 1 )
        if len(L) > 1:
          return ParamFilter.EvalLT( L[0], L[1] )
        L = word.split( '>', 1 )
        if len(L) > 1:
          return ParamFilter.EvalGT( L[0], L[1] )
        L = word.split( '=', 1 )
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
              if type(v) == type(2): return v == int(self.v)
              elif type(v) == type(2.2): return v == float(self.v)
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
              if type(v) == type(2): return v != int(self.v)
              elif type(v) == type(2.2): return v != float(self.v)
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
            if type(v) == type(2): return v <= int(self.v)
            elif type(v) == type(2.2): return v <= float(self.v)
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
            if type(v) == type(2): return v >= int(self.v)
            elif type(v) == type(2.2): return v >= float(self.v)
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
            if type(v) == type(2): return v < int(self.v)
            elif type(v) == type(2.2): return v < float(self.v)
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
            if type(v) == type(2): return v > int(self.v)
            elif type(v) == type(2.2): return v > float(self.v)
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

