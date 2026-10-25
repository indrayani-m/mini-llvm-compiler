"""Tests for the lexer, parser and semantic analyzer."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ast_nodes import (Assign, BinaryOp, Block, If, Number, Print, UnaryOp,
                       VarDecl, Variable, While)
from errors import LexError, ParseError, SemanticError
from lexer import tokenize
from parser import Parser
from semantic import SemanticAnalyzer


def parse(source):
    return Parser(tokenize(source)).parse_program()


def analyze(source):
    program = parse(source)
    SemanticAnalyzer().analyze(program)
    return program


class LexerTests(unittest.TestCase):
    def types(self, source):
        return [t.type for t in tokenize(source)]

    def test_declaration_tokens(self):
        self.assertEqual(self.types("int x = 5;"),
                         ["int", "IDENT", "=", "NUMBER", ";", "EOF"])

    def test_keywords_vs_identifiers(self):
        self.assertEqual(self.types("if else while print int iffy"),
                         ["if", "else", "while", "print", "int", "IDENT", "EOF"])

    def test_two_char_operators(self):
        self.assertEqual(self.types("== != <= >= < > ="),
                         ["==", "!=", "<=", ">=", "<", ">", "=", "EOF"])

    def test_number_value_is_int(self):
        token = tokenize("123")[0]
        self.assertEqual(token.type, "NUMBER")
        self.assertEqual(token.value, 123)

    def test_comments_are_skipped(self):
        self.assertEqual(self.types("1 // ignore me\n2"), ["NUMBER", "NUMBER", "EOF"])

    def test_line_and_column_tracking(self):
        tokens = tokenize("int x;\n  y")
        y = tokens[3]
        self.assertEqual((y.type, y.line, y.col), ("IDENT", 2, 3))

    def test_unexpected_character(self):
        with self.assertRaises(LexError) as ctx:
            tokenize("int x = 5 @ 2;")
        self.assertEqual((ctx.exception.line, ctx.exception.col), (1, 11))

    def test_lone_bang_is_an_error(self):
        with self.assertRaises(LexError):
            tokenize("a ! b")

    def test_number_followed_by_letters(self):
        with self.assertRaises(LexError):
            tokenize("12abc")


class ParserTests(unittest.TestCase):
    def test_declaration_with_and_without_init(self):
        program = parse("int a = 1; int b;")
        self.assertIsInstance(program.statements[0], VarDecl)
        self.assertIsInstance(program.statements[0].init, Number)
        self.assertIsNone(program.statements[1].init)

    def test_assignment_and_print(self):
        program = parse("int a; a = 2; print(a);")
        self.assertIsInstance(program.statements[1], Assign)
        self.assertIsInstance(program.statements[2], Print)

    def test_multiplication_binds_tighter_than_addition(self):
        expr = parse("print(2 + 3 * 4);").statements[0].value
        self.assertEqual(expr.op, "+")
        self.assertIsInstance(expr.right, BinaryOp)
        self.assertEqual(expr.right.op, "*")

    def test_parentheses_override_precedence(self):
        expr = parse("print((2 + 3) * 4);").statements[0].value
        self.assertEqual(expr.op, "*")
        self.assertEqual(expr.left.op, "+")

    def test_subtraction_is_left_associative(self):
        expr = parse("print(10 - 4 - 3);").statements[0].value
        self.assertEqual(expr.op, "-")
        self.assertEqual(expr.left.op, "-")      # (10 - 4) - 3
        self.assertEqual(expr.right.value, 3)

    def test_arithmetic_binds_tighter_than_comparison(self):
        expr = parse("print(1 + 2 < 3 * 4);").statements[0].value
        self.assertEqual(expr.op, "<")

    def test_unary_minus(self):
        expr = parse("print(-5);").statements[0].value
        self.assertIsInstance(expr, UnaryOp)

    def test_if_else(self):
        node = parse("if (1 < 2) { print(1); } else { print(2); }").statements[0]
        self.assertIsInstance(node, If)
        self.assertIsInstance(node.then_body, Block)
        self.assertIsInstance(node.else_body, Block)

    def test_else_if_chain(self):
        node = parse("if (1) { } else if (2) { } else { }").statements[0]
        self.assertIsInstance(node.else_body, If)
        self.assertIsInstance(node.else_body.else_body, Block)

    def test_while(self):
        node = parse("while (1 < 2) { print(1); }").statements[0]
        self.assertIsInstance(node, While)
        self.assertEqual(len(node.body.statements), 1)

    def test_missing_semicolon_reports_end_of_previous_line(self):
        with self.assertRaises(ParseError) as ctx:
            parse("int x = 5\nprint(x);")
        err = ctx.exception
        self.assertIn("expected ';'", err.message)
        self.assertEqual((err.line, err.col), (1, 10))

    def test_missing_closing_brace(self):
        with self.assertRaises(ParseError) as ctx:
            parse("while (1 < 2) { print(1);")
        self.assertIn("expected '}'", ctx.exception.message)

    def test_missing_closing_paren(self):
        with self.assertRaises(ParseError):
            parse("print((1 + 2);")

    def test_if_requires_braces(self):
        with self.assertRaises(ParseError) as ctx:
            parse("if (1 < 2) print(1);")
        self.assertIn("expected '{'", ctx.exception.message)

    def test_stray_else(self):
        with self.assertRaises(ParseError):
            parse("else { }")

    def test_incomplete_expression(self):
        with self.assertRaises(ParseError):
            parse("int x = 1 + ;")

    def test_declaration_needs_a_name(self):
        with self.assertRaises(ParseError):
            parse("int = 5;")


class SemanticTests(unittest.TestCase):
    def test_valid_program_passes(self):
        analyze("int x = 1; x = x + 1; print(x);")

    def test_use_of_undeclared_variable(self):
        with self.assertRaises(SemanticError) as ctx:
            analyze("print(y);")
        self.assertIn("'y'", ctx.exception.message)

    def test_assignment_to_undeclared_variable(self):
        with self.assertRaises(SemanticError):
            analyze("y = 1;")

    def test_variable_cannot_use_itself_in_its_initializer(self):
        with self.assertRaises(SemanticError):
            analyze("int x = x + 1;")

    def test_redeclaration_in_same_scope(self):
        with self.assertRaises(SemanticError) as ctx:
            analyze("int x = 1;\nint x = 2;")
        self.assertEqual(ctx.exception.line, 2)
        self.assertIn("already declared", ctx.exception.message)

    def test_shadowing_in_inner_block_is_allowed(self):
        program = analyze("int x = 1; { int x = 2; print(x); } print(x);")
        outer = program.statements[0].ir_name
        inner = program.statements[1].statements[0].ir_name
        self.assertNotEqual(outer, inner)
        # the last print refers to the outer variable again
        self.assertEqual(program.statements[2].value.ir_name, outer)

    def test_same_name_in_sibling_blocks_is_allowed(self):
        analyze("if (1) { int t = 1; } else { int t = 2; }")

    def test_variable_not_visible_after_its_block(self):
        with self.assertRaises(SemanticError):
            analyze("{ int inner = 1; } print(inner);")

    def test_division_by_literal_zero(self):
        with self.assertRaises(SemanticError) as ctx:
            analyze("print(10 / 0);")
        self.assertIn("division by zero", ctx.exception.message)

    def test_literal_too_large_for_int(self):
        with self.assertRaises(SemanticError):
            analyze("int x = 2147483648;")

    def test_largest_int_literal_is_accepted(self):
        analyze("int x = 2147483647;")


if __name__ == "__main__":
    unittest.main()
