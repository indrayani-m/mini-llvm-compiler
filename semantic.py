"""Semantic analysis: checks the AST for meaning errors before code generation.

Checks performed:
  * use or assignment of an undeclared variable
  * declaring the same variable twice in the same scope
  * division by the literal 0
  * integer literals that do not fit in 32 bits

It also resolves every variable to a unique LLVM stack-slot name and stores
it in `node.ir_name`, so the code generator never has to think about scopes.

Scoping rules: every `{ ... }` block (and the whole program) is a scope.
An inner scope may redeclare ("shadow") a name from an outer scope.
"""

from ast_nodes import (Assign, BinaryOp, Block, If, Number, Print, Program,
                       UnaryOp, VarDecl, Variable, While)
from errors import SemanticError

INT_MAX = 2147483647


class SemanticAnalyzer:
    def __init__(self):
        self.scopes = []        # stack of {name: (ir_name, declared_line)}
        self.name_counts = {}   # how many times each name has been declared

    # ----- scopes -----

    def declare(self, node):
        scope = self.scopes[-1]
        if node.name in scope:
            first_line = scope[node.name][1]
            raise SemanticError(
                "variable '%s' is already declared in this scope (line %d)"
                % (node.name, first_line),
                node.line, node.col)
        count = self.name_counts.get(node.name, 0)
        self.name_counts[node.name] = count + 1
        # "var." can never clash with a temporary (%t1) or a label.
        ir_name = "var." + node.name if count == 0 else "var.%s.%d" % (node.name, count)
        scope[node.name] = (ir_name, node.line)
        node.ir_name = ir_name

    def lookup(self, name, line, col):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name][0]
        raise SemanticError("variable '%s' is used before it is declared" % name,
                            line, col)

    # ----- traversal -----

    def analyze(self, program):
        self.scopes.append({})
        for statement in program.statements:
            self.visit(statement)
        self.scopes.pop()

    def visit(self, node):
        if isinstance(node, VarDecl):
            if node.init is not None:
                self.visit(node.init)      # before declare: "int x = x;" is an error
            self.declare(node)
        elif isinstance(node, Assign):
            self.visit(node.value)
            node.ir_name = self.lookup(node.name, node.line, node.col)
        elif isinstance(node, Print):
            self.visit(node.value)
        elif isinstance(node, Block):
            self.scopes.append({})
            for statement in node.statements:
                self.visit(statement)
            self.scopes.pop()
        elif isinstance(node, If):
            self.visit(node.condition)
            self.visit(node.then_body)
            if node.else_body is not None:
                self.visit(node.else_body)
        elif isinstance(node, While):
            self.visit(node.condition)
            self.visit(node.body)
        elif isinstance(node, Number):
            if node.value > INT_MAX:
                raise SemanticError(
                    "number %d is too large for a 32-bit int (max %d)"
                    % (node.value, INT_MAX), node.line, node.col)
        elif isinstance(node, Variable):
            node.ir_name = self.lookup(node.name, node.line, node.col)
        elif isinstance(node, UnaryOp):
            self.visit(node.operand)
        elif isinstance(node, BinaryOp):
            self.visit(node.left)
            self.visit(node.right)
            if (node.op == "/" and isinstance(node.right, Number)
                    and node.right.value == 0):
                raise SemanticError("division by zero", node.line, node.col)
        else:
            raise SemanticError("internal error: unknown node %r" % (node,))


def analyze(program):
    SemanticAnalyzer().analyze(program)
