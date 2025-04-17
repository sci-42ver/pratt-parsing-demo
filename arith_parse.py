#!/usr/bin/python3
"""
arith_parse.py: Parse shell-like and C-like arithmetic.
"""

import sys

import tdop
from tdop import Node, CompositeNode

#
# Null Denotation -- token that takes nothing on the left
#

def NullConstant(p, token, bp):
  return Node(token)


def NullParen(p, token, bp):
  """ Arithmetic grouping """
  r = p.ParseUntil(bp)
  p.Eat(')')
  return r


def NullPrefixOp(p, token, bp):
  """Prefix operator.
  
  Low precedence:  return, raise, etc.
    return x+y is return (x+y), not (return x) + y

  High precedence: logical negation, bitwise complement, etc.
    !x && y is (!x) && y, not !(x && y)
  
  Here we only consider expr due to "a POSIX-compatible shell *arithmetic* parser", so no need for return etc (raise is not in Shell, at least for bash).
  """
  r = p.ParseUntil(bp)
  return CompositeNode(token, [r])


def NullIncDec(p, token, bp):
  """ ++x or ++x[1] """
  right = p.ParseUntil(bp)
  if right.token.type not in ('name', 'get'):
    # https://docs.python.org/3/library/stdtypes.html#str
    # > If object does not have a __str__() method, then str() falls back to returning repr(object).
    # https://docs.python.org/3/library/string.html#format-examples for %.
    raise tdop.ParseError("Can't assign to %r (%s)" % (right, right.token))
  return CompositeNode(token, [right])


#
# Left Denotation -- token that takes an expression on the left
#

def LeftIncDec(p, token, left, rbp):
  """ For i++ and i-- (not in Python https://stackoverflow.com/a/1485854/21294350 but in Shell/C)
  """
  if left.token.type not in ('name', 'get'):
    raise tdop.ParseError("Can't assign to %r (%s)" % (left, left.token))
  token.type = 'post' + token.type
  return CompositeNode(token, [left])


def LeftIndex(p, token, left, unused_bp):
  """ index f[x+1] """
  # f[x] or f[x][y]
  if left.token.type not in ('name', 'get'):
    raise tdop.ParseError("%s can't be indexed" % left)
  index = p.ParseUntil(0) # implicit parenthesis pair
  p.Eat("]")

  token.type = 'get'
  return CompositeNode(token, [left, index])


def LeftTernary(p, token, left, bp):
  """ e.g. a > 1 ? x : y """
  # 0 binding power since any operators allowed until ':'.  See:
  #
  # http://en.cppreference.com/w/c/language/operator_precedence#cite_note-2
  #
  # "The expression in the middle of the conditional operator (between ? and
  # :) is parsed as if parenthesized: its precedence relative to ?: is
  # ignored."
  # See precedence_tests.c for why this is useful.
  true_expr = p.ParseUntil(0)

  p.Eat(':')
  false_expr = p.ParseUntil(bp)
  children = [left, true_expr, false_expr]
  return CompositeNode(token, children)


def LeftBinaryOp(p, token, left, rbp):
  """ Normal binary operator like 1+2 or 2*3, etc. """
  return CompositeNode(token, [left, p.ParseUntil(rbp)])


def LeftAssign(p, token, left, rbp):
  """ Normal binary operator like 1+2 or 2*3, etc. """
  # x += 1, or a[i] += 1
  if left.token.type not in ('name', 'get'):
    raise tdop.ParseError("Can't assign to %r (%s)" % (left, left.token))
  return CompositeNode(token, [left, p.ParseUntil(rbp)])


def LeftComma(p, token, left, rbp):
  """ foo, bar, baz 

  Could be sequencing operator, or tuple without parens

  tuple is inherent supported in Python. For bash, see https://stackoverflow.com/a/9713142/21294350 based on IFS.
  """
  # Here bash doesn't support trailing comma
  r = p.ParseUntil(rbp)
  # Due to using Left since Left-to-right, the above ParseUntil will stop at the next comma.
  # So this will happen after having consumed one comma, e.g. (foo, bar), baz.
  if left.token.type == ',':  # Keep adding more children
    left.children.append(r)
    return left
  children = [left, r]
  return CompositeNode(token, children)


# For overloading of , inside function calls
COMMA_PREC = 1

def LeftFuncCall(p, token, left, unused_bp):
  """ Function call f(a, b). """
  children = [left]
  # f(x) or f[i](x)
  if left.token.type not in ('name', 'get'):
    raise tdop.ParseError("%s can't be called" % left)
  
  while not p.AtToken(')'):
    # # We don't want to grab the comma, e.g. it is NOT a sequence operator.  So
    # # set the precedence to 5.
    # children.append(p.ParseUntil(COMMA_PREC))
    # # Here implicitly allow trailing comma which is unsupported by C (You can check online with godbolt).
    # if p.AtToken(','):
    #   p.Next()

    ## IMHO the above is same as (although not supporting trailing comma by only running "p.Next()")
    comma_list = p.ParseUntil(0) # NullParen rbp
    # children = children + (comma_list.children if hasattr(comma_list, 'children') else [comma_list])
    children = children + (comma_list.children if comma_list.token.type == ',' else [comma_list])

  p.Eat(")")
  token.type = 'call'
  return CompositeNode(token, children)


def MakeShellParserSpec():
  """
  Create a parser.

  Compare the code below with this table of C operator precedence:
  http://en.cppreference.com/w/c/language/operator_precedence

  It is same for bash https://www.gnu.org/software/bash/manual/bash.html#Shell-Arithmetic
  """
  spec = tdop.ParserSpec()

  spec.Left(31, LeftIncDec, ['++', '--']) # postfix
  spec.Left(31, LeftFuncCall, ['('])
  spec.Left(31, LeftIndex, ['['])

  # 29 -- binds to everything except function call, indexing, prefix ops
  # 0. Here all are Right-to-left (Notice "info bash" has no sizeof although opengroup standard shows that), but due to unary there is no ambiguity for bp comparison since no other operators will compete for grabbing that value https://stackoverflow.com/a/12963342/21294350.
  # > With unary operators it would be more than surprising to group !!a as (!!)a, the language would also have to supply a meaning for the sub-expression !!
  # So we don't need do something similar to **.
  # This is also implied in Python https://docs.python.org/3/reference/expressions.html#operator-precedence for -x etc.
  # 0.a. But obviously it needs bp to restrict what in the latter it can grab.
  spec.Null(29, NullIncDec, ['++', '--'])
  spec.Null(29, NullPrefixOp, ['+', '!', '~', '-'])

  # Right associative: 2 ** 3 ** 2 == 2 ** (3 ** 2)
  # Binds less strongly than negation. See `info bash` 
  spec.LeftRightAssoc(27, LeftBinaryOp, ['**'])

  spec.Left(25, LeftBinaryOp, ['*', '/', '%'])

  spec.Left(23, LeftBinaryOp, ['+', '-'])
  spec.Left(21, LeftBinaryOp, ['<<', '>>']) 
  spec.Left(19, LeftBinaryOp, ['<', '>', '<=', '>='])
  spec.Left(17, LeftBinaryOp, ['!=', '=='])

  spec.Left(15, LeftBinaryOp, ['&'])
  spec.Left(13, LeftBinaryOp, ['^'])
  spec.Left(11, LeftBinaryOp, ['|'])
  spec.Left(9, LeftBinaryOp, ['&&'])
  spec.Left(7, LeftBinaryOp, ['||'])

  spec.LeftRightAssoc(5, LeftTernary, ['?'])

  # Right associative: a = b = 2 is a = (b = 2)
  spec.LeftRightAssoc(3, LeftAssign, [
      '=',
      '+=', '-=', '*=', '/=', '%=',
      '<<=', '>>=', '&=', '^=', '|='])

  spec.Left(COMMA_PREC, LeftComma, [','])

  # 0. 0 precedence -- doesn't bind until )
  # 0.a. Although this is at the top of the precedence order list *implicitly* (see the standard https://stackoverflow.com/a/79544622/21294350)
  # ( should not binds anything from other op's like + etc.
  spec.Null(0, NullParen, ['('])  # for grouping

  # -1 precedence -- never used (actually it can be any number since it is not used by NullConstant etc and later)
  # This means it won't have any children.
  spec.Null(-1, NullConstant, ['name', 'number']) # consider nud number etc.
  # 0. avoid unmatched paren etc.
  # 1. Due to -1 < all rbp's, led won't be called. So only care about nud's.
  spec.Null(-1, tdop.NullError, [')', ']', ':', 'eof'])

  return spec


def MakeParser(s):
  """Used by tests."""
  spec = MakeShellParserSpec()
  lexer = tdop.Tokenize(s)
  p = tdop.Parser(spec, lexer)
  return p


def ParseShell(s, expected=None):
  """Used by tests."""
  p = MakeParser(s)
  tree = p.Parse()

  sexpr = repr(tree)
  if expected is not None:
    assert sexpr == expected, '%r != %r' % (sexpr, expected)

  print('%-40s %s' % (s, sexpr))
  return tree


def main(argv):
  try:
    s = argv[1]
  except IndexError:
    print('Usage: ./arith_parse.py EXPRESSION')
  else:
    try:
      tree = ParseShell(s)
    except tdop.ParseError as e:
      print('Error parsing %r: %s' % (s, e), file=sys.stderr)


if __name__ == '__main__':
  main(sys.argv)
