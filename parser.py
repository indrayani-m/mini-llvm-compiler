"""Recursive-descent parser: tokens -> AST.

Grammar (EBNF):

    program     = { statement } EOF
    statement   = declaration | assignment | print_stmt | if_stmt
                | while_stmt | block
    declaration = "int" IDENT [ "=" expr ] ";"
    assignment  = IDENT "=" expr ";"
    print_stmt  = "print" "(" expr ")" ";"
    if_stmt     = "if" "(" expr ")" block [ "else" ( if_stmt | block ) ]
    while_stmt  = "while" "(" expr ")" block
    block       = "{" { statement } "}"

    expr        = additive { ("<" | ">" | "<=" | ">=" | "==" | "!=") additive }
    additive    = term { ("+" | "-") term }
    term        = unary { ("*" | "/") unary }
    unary       = "-" unary | primary
    primary     = NUMBER | IDENT | "(" expr ")"

Operators lower in the grammar bind tighter, which gives the usual
precedence: unary minus > * / > + - > comparisons.
"""

from ast_nodes import (Assign, BinaryOp, Block, If, Number, Print, Program,
                       UnaryOp, VarDecl, Variable, While)
from errors import ParseError

COMPARISON_OPS = ("<", ">", "<=", ">=", "==", "!=")


def describe(token):
    """Human-friendly name of a token for error messages."""
    if token.type == "EOF":
        return "end of file"
    if token.type == "NUMBER":
        return "number %s" % token.value
    if token.type == "IDENT":
        return "name '%s'" % token.value
    return "'%s'" % token.value


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # ----- token helpers -----

    def peek(self):
        return self.tokens[self.pos]

    def check(self, *types):
        return self.peek().type in types

    def advance(self):
        token = self.tokens[self.pos]
        if token.type != "EOF":
            self.pos += 1
        return token

    def match(self, *types):
        if self.check(*types):
            return self.advance()
        return None

    def expect(self, type, context=""):
        if self.check(type):
            return self.advance()
        found = self.peek()
        message = "expected '%s'" % type
        if context:
            message += " " + context
        message += " but found " + describe(found)

        # A missing ';' or ')' is easiest to spot at the end of the previous
        # token, not at the start of whatever comes next (maybe a later line).
        line, col = found.line, found.col
        if self.pos > 0:
            prev = self.tokens[self.pos - 1]
            if found.line > prev.line or found.type == "EOF":
                line, col = prev.line, prev.col + prev.length
        raise ParseError(message, line, col)

    # ----- program and statements -----

    def parse_program(self):
        statements = []
        while not self.check("EOF"):
            statements.append(self.parse_statement())
        return Program(statements)

    def parse_statement(self):
        token = self.peek()
        if token.type == "int":
            return self.parse_declaration()
        if token.type == "print":
            return self.parse_print()
        if token.type == "if":
            return self.parse_if()
        if token.type == "while":
            return self.parse_while()
        if token.type == "{":
            return self.parse_block("block")
        if token.type == "IDENT":
            return self.parse_assignment()
        raise ParseError(
            "unexpected %s (expected a statement)" % describe(token),
            token.line, token.col)

    def parse_declaration(self):
        start = self.advance()                       # 'int'
        name = self.expect("IDENT", "(a variable name) after 'int'")
        init = None
        if self.match("="):
            init = self.parse_expression()
        self.expect(";", "after variable declaration")
        return VarDecl(name.value, init, name.line, name.col)

    def parse_assignment(self):
        name = self.advance()                        # IDENT
        self.expect("=", "after variable '%s'" % name.value)
        value = self.parse_expression()
        self.expect(";", "after assignment")
        return Assign(name.value, value, name.line, name.col)

    def parse_print(self):
        start = self.advance()                       # 'print'
        self.expect("(", "after 'print'")
        value = self.parse_expression()
        self.expect(")", "after the value to print")
        self.expect(";", "after print statement")
        return Print(value, start.line, start.col)

    def parse_if(self):
        start = self.advance()                       # 'if'
        self.expect("(", "after 'if'")
        condition = self.parse_expression()
        self.expect(")", "after the if condition")
        then_body = self.parse_block("if")
        else_body = None
        if self.match("else"):
            if self.check("if"):
                else_body = self.parse_if()          # "else if" chain
            else:
                else_body = self.parse_block("else")
        return If(condition, then_body, else_body, start.line, start.col)

    def parse_while(self):
        start = self.advance()                       # 'while'
        self.expect("(", "after 'while'")
        condition = self.parse_expression()
        self.expect(")", "after the while condition")
        body = self.parse_block("while")
        return While(condition, body, start.line, start.col)

    def parse_block(self, owner):
        start = self.expect("{", "to start the %s body" % owner)
        statements = []
        while not self.check("}", "EOF"):
            statements.append(self.parse_statement())
        self.expect("}", "to close the %s body" % owner)
        return Block(statements, start.line, start.col)

    # ----- expressions -----

    def parse_expression(self):
        left = self.parse_additive()
        while self.check(*COMPARISON_OPS):
            op = self.advance()
            right = self.parse_additive()
            left = BinaryOp(op.type, left, right, op.line, op.col)
        return left

    def parse_additive(self):
        left = self.parse_term()
        while self.check("+", "-"):
            op = self.advance()
            right = self.parse_term()
            left = BinaryOp(op.type, left, right, op.line, op.col)
        return left

    def parse_term(self):
        left = self.parse_unary()
        while self.check("*", "/"):
            op = self.advance()
            right = self.parse_unary()
            left = BinaryOp(op.type, left, right, op.line, op.col)
        return left

    def parse_unary(self):
        if self.check("-"):
            op = self.advance()
            operand = self.parse_unary()
            return UnaryOp("-", operand, op.line, op.col)
        return self.parse_primary()

    def parse_primary(self):
        token = self.peek()
        if token.type == "NUMBER":
            self.advance()
            return Number(token.value, token.line, token.col)
        if token.type == "IDENT":
            self.advance()
            return Variable(token.value, token.line, token.col)
        if token.type == "(":
            self.advance()
            expr = self.parse_expression()
            self.expect(")", "to close the parenthesis")
            return expr
        raise ParseError(
            "expected a number, variable or '(' but found " + describe(token),
            token.line, token.col)


def parse(tokens):
    return Parser(tokens).parse_program()
