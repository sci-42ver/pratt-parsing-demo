#!/usr/bin/python3
"""
tdop.py
"""

import re


class ParseError(Exception):
  pass


#
# Default parsing functions give errors
#

def NullError(p, token, bp):
  raise ParseError("%s can't be used in prefix position" % token)


def LeftError(p, token, left, rbp):
  # Hm is this not called because of binding power?
  raise ParseError("%s can't be used in infix position" % token)


#
# Input
#

class Token:
  def __init__(self, type, val, loc=None):
    self.type = type
    self.val = val

  def __repr__(self):
    return '<Token %s %s>' % (self.type, self.val)


#
# Using the pattern here: https://web.archive.org/web/20161202072939/http://effbot.org/zone/xml-scanner.htm (mainly based on xml-scanner-example-4.py for infix expression. xml-scanner-example-5/6 are for XML)
#

# 0. NOTE: () and [] need to be on their own so (-1+2) works
# 1. triple quoted exp is string but not one comment 
# 2. re.VERBOSE https://docs.python.org/3/library/re.html#re.VERBOSE
# implies that we "separate logical sections" (i.e. \n newline) and "Whitespace within the pattern" are "ignored".
TOKEN_RE = re.compile(r"""
\s* 
(?: 
  # See the following about '",*"'. Here number must be firsted matched against "(\d+)".
  (\d+)
  | (\w+)
  # | ( [\-\+\*/%!~<>=&^|?:,]+ ) 
  # IGNORE Here I changed to only allow the string with duplicate same characters.
  # -=,+= etc should be allowed.
  # 1. %% https://stackoverflow.com/a/25901868/21294350
  # 2. ~ is unary https://stackoverflow.com/questions/8305199/the-tilde-operator-in-python#comment10234779_8305199 Similarly ^ is binary XOR.
  | ([\-\+\*/%!~<>=&^|?:]+) # only remove ",".
  # | ((?:\-|\+|\*|/|%|<|>|=|&|\|)+| :=)
  # !!, ?? are in ipython https://stackoverflow.com/q/70833723/21294350
  # :: is used as 2 :s https://python-reference.readthedocs.io/en/latest/docs/brackets/slicing.html
  | ([\(\)\[\]~^!?:,])
  # match kwargs
  # 0. Assume no weird format strings like "arg1 **arg2" for "arg1**arg2"
  # 1. IGNORE: Here order of or elems doesn't imply their matching order.
  # If this is put before some pat able to match ",*", then ",*arg" won't be splitted into "," and "*arg" because ,* will be always matched first. See https://docs.python.org/3/library/re.html#regular-expression-syntax
  # > As the target string is scanned, REs separated by '|' are tried from left to right. When one pattern completely matches, that branch is accepted.
  # > In other words, the '|' operator is never greedy.
  | ((?<!\w)(?:\*|\*\*)\w+))
""", re.VERBOSE)

# TOKEN_RE.findall("""fact := lambda n, a,**kwargs,*args:
# if n == 0
# then 1
# else n*fact(n-1)"""
# )
# Using the original, it won't match **kwargs but match ,** and kwargs...
# Anyway here "," should not consume more.

# generator https://stackoverflow.com/a/45621089/21294350
# https://stackoverflow.com/questions/50573100/using-next-on-generator-function#comment124667820_50573153 https://docs.python.org/3/glossary.html#term-generator
def Tokenize(s):
  # IMHO here we have no need for lazy evaluation since findall is not lazy.
  # In Python we can use finditer and the wrap __next__ with the following operation.
  for item in TOKEN_RE.findall(s):
    # Also see https://docs.python.org/3/library/re.html#writing-a-tokenizer
    # using named group.
    if item[0]:
      typ = 'number'
      val = int(item[0])
    elif item[1]:
      typ = 'name'
      val = item[1]
    elif item[2]:
      typ = item[2]
      val = item[2]
    elif item[3]:
      typ = item[3]
      val = item[3]
    elif item[4]:
      typ = item[4]
      val = item[4]
    # loc is unused but it is useful for compiler etc to show where the error is etc.
    yield Token(typ, val, loc=(0, 0))


#
# Simple and Composite AST nodes
#

class Node(object):
  def __init__(self, token):
    """
    Args:
      type: token type (operator, etc.)
      val: token val, only important for number and string
    """
    self.token = token

  def __repr__(self):
    return str(self.token.val)


class CompositeNode(Node):
  def __init__(self, token, children):
    """
    Args:
      type: token type (operator, etc.)
    """
    Node.__init__(self, token)
    self.children = children

  def __repr__(self):
    args = ''.join([" " + repr(c) for c in self.children])
    return "(" + self.token.type + args + ")"


#
# Parser definition
#

class LeftInfo(object):
  """Row for operator.

  In C++ this should be a big array.

  Here it is one dict with val as class (actually like one one-dimensional array).
  """
  def __init__(self, led=None, lbp=0, rbp=0):
    # None => false https://docs.python.org/3/library/stdtypes.html#truth-value-testing
    self.led = led or LeftError
    self.lbp = lbp
    self.rbp = rbp


class NullInfo(object):
  """Row for operator.

  In C++ this should be a big array.
  """
  def __init__(self, nud=None, bp=0):
    self.nud = nud or NullError
    self.bp = bp


class ParserSpec(object):
  """Specification for a TDOP parser."""

  def __init__(self):
    self.null_lookup = {}
    self.left_lookup = {}

  def Null(self, bp, nud, tokens):
    """Register a token that doesn't take anything on the left.
    
    Examples: constant, prefix operator, error.
    """
    for token in tokens:
      self.null_lookup[token] = NullInfo(nud=nud, bp=bp)
      if token not in self.left_lookup:
        self.left_lookup[token] = LeftInfo()  # error

  # https://peps.python.org/pep-0008/#descriptive-naming-styles
  def _RegisterLed(self, lbp, rbp, led, tokens):
    for token in tokens:
      if token not in self.null_lookup:
        self.null_lookup[token] = NullInfo(NullError)
      self.left_lookup[token] = LeftInfo(lbp=lbp, rbp=rbp, led=led)

  def Left(self, bp, led, tokens):
    """Register a token that takes an expression on the left."""
    self._RegisterLed(bp, bp, led, tokens)

  def LeftRightAssoc(self, bp, led, tokens):
    """Register a right associative operator."""
    self._RegisterLed(bp, bp-1, led, tokens)

  def LookupNull(self, token):
    """Get the parsing function and precedence for a null position token."""
    try:
      nud = self.null_lookup[token]
    except KeyError:
      raise ParseError('Unexpected token %r' % token)
    return nud

  def LookupLeft(self, token):
    """Get the parsing function and precedence for a left position token."""
    try:
      led = self.left_lookup[token]
    except KeyError:
      raise ParseError('Unexpected token %r' % token)
    return led


EOF_TOKEN = Token('eof', 'eof')


class Parser(object):
  """Recursive TDOP parser."""

  def __init__(self, spec, lexer):
    self.spec = spec
    self.lexer = lexer  # iterable
    self.token = None  # current token

  def AtToken(self, token_type):
    """Test if we are looking at a token."""
    return self.token.type == token_type

  def Next(self):
    """Move to the next token."""
    try:
      t = self.lexer.__next__()
    except StopIteration:
      t = EOF_TOKEN
    self.token = t

  def Eat(self, val):
    """Assert the value of the current token, then move to the next token."""
    if val and not self.AtToken(val):
      raise ParseError('expected %s, got %s' % (val, self.token))
    self.Next()

  def ParseUntil(self, rbp):
    """
    Parse to the right, eating tokens until we encounter a token with binding
    power LESS THAN OR EQUAL TO rbp.
    """
    if self.AtToken('eof'):
      raise ParseError('Unexpected end of input')

    t = self.token
    self.Next()  # skip over the token, e.g. ! ~ + -

    null_info = self.spec.LookupNull(t.type)
    node = null_info.nud(self, t, null_info.bp)

    while True:
      t = self.token
      left_info = self.spec.LookupLeft(t.type)

      # Examples:
      # If we see 1*2+  , rbp = 27 and lbp = 25, so stop.
      # If we see 1+2+  , rbp = 25 and lbp = 25, so stop.
      # If we see 1**2**, rbp = 26 and lbp = 27, so keep going.
      if rbp >= left_info.lbp:
        break
      self.Next()  # skip over the token, e.g. / *

      node = left_info.led(self, t, node, left_info.rbp)

    return node

  def Parse(self):
    # get the 1st token
    self.Next()
    return self.ParseUntil(0)
