"""Tests that check the shape of the generated LLVM IR (no LLVM tools needed)."""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import compile_source


def main_function(ir):
    """Return only the text of @main."""
    return ir[ir.index("define i32 @main()"):]


class CodegenTests(unittest.TestCase):
    def test_module_structure(self):
        ir = compile_source("print(1);", "demo.mini")
        self.assertIn('source_filename = "demo.mini"', ir)
        self.assertIn("define i32 @main()", ir)
        self.assertIn("ret i32 0", ir)

    def test_declaration_uses_alloca_and_store(self):
        body = main_function(compile_source("int x = 5;"))
        self.assertIn("%var.x = alloca i32", body)
        self.assertIn("store i32 5, ptr %var.x", body)

    def test_uninitialised_variable_is_zeroed(self):
        body = main_function(compile_source("int x;"))
        self.assertIn("store i32 0, ptr %var.x", body)

    def test_variable_read_uses_load(self):
        body = main_function(compile_source("int x = 1; print(x);"))
        self.assertIn("load i32, ptr %var.x", body)

    def test_arithmetic_instructions(self):
        body = main_function(compile_source(
            "int a = 8; int b = 2; print(a + b); print(a - b); "
            "print(a * b); print(a / b);"))
        for instruction in ("add i32", "sub i32", "mul i32", "sdiv i32"):
            self.assertIn(instruction, body)

    def test_unary_minus(self):
        body = main_function(compile_source("int a = 4; print(-a);"))
        self.assertIn("sub i32 0,", body)

    def test_comparison_instructions(self):
        body = main_function(compile_source(
            "int a = 1; print(a < 2); print(a > 2); print(a == 2); "
            "print(a != 2); print(a <= 2); print(a >= 2);"))
        for predicate in ("slt", "sgt", "eq", "ne", "sle", "sge"):
            self.assertIn("icmp %s i32" % predicate, body)

    def test_comparison_used_as_value_is_zero_extended(self):
        body = main_function(compile_source("int a = 1; int f = a < 2;"))
        self.assertIn("zext i1", body)

    def test_if_else_generates_conditional_branch(self):
        body = main_function(compile_source(
            "int a = 1; if (a < 2) { print(1); } else { print(2); }"))
        self.assertRegex(body, r"br i1 %t\d+, label %if\.then\.1, label %if\.else\.1")
        for label in ("if.then.1:", "if.else.1:", "if.end.1:"):
            self.assertIn(label, body)

    def test_if_without_else_skips_to_end(self):
        body = main_function(compile_source("if (1 < 2) { print(1); }"))
        self.assertRegex(body, r"label %if\.then\.1, label %if\.end\.1")
        self.assertNotIn("if.else.1", body)

    def test_while_generates_loop_blocks(self):
        body = main_function(compile_source(
            "int i = 0; while (i < 3) { i = i + 1; }"))
        for label in ("while.cond.1:", "while.body.1:", "while.end.1:"):
            self.assertIn(label, body)
        # the body jumps back to the condition
        self.assertIn("br label %while.cond.1", body)

    def test_numeric_condition_is_compared_with_zero(self):
        body = main_function(compile_source("int a = 3; if (a) { print(1); }"))
        self.assertIn("icmp ne i32", body)

    def test_all_allocas_live_in_entry_block(self):
        ir = compile_source(
            "int i = 0; while (i < 3) { int t = i; i = i + 1; }")
        body = main_function(ir)
        entry, rest = body.split("start:")
        self.assertEqual(entry.count("alloca"), 2)       # i and t
        self.assertNotIn("alloca", rest)

    def test_shadowed_variables_get_distinct_slots(self):
        body = main_function(compile_source(
            "int x = 1; { int x = 2; print(x); } print(x);"))
        self.assertIn("%var.x = alloca i32", body)
        self.assertIn("%var.x.1 = alloca i32", body)

    def test_every_block_ends_with_a_terminator(self):
        ir = compile_source(
            "int i = 0; while (i < 3) { if (i == 1) { print(i); } i = i + 1; }")
        lines = [l.strip() for l in main_function(ir).splitlines() if l.strip()]
        labels_checked = 0
        for index, line in enumerate(lines):
            # every label except the function's first block ("entry:") must be
            # preceded by a terminator instruction of the previous block
            if re.match(r"^[\w.]+:$", line) and line != "entry:":
                self.assertRegex(lines[index - 1], r"^(br|ret) ")
                labels_checked += 1
        self.assertGreater(labels_checked, 5)

    def test_default_print_uses_putchar_helper(self):
        ir = compile_source("print(7);")
        self.assertIn("@print_int", ir)
        self.assertIn("declare i32 @putchar(i32)", ir)
        self.assertNotIn("@printf", ir)

    def test_printf_mode(self):
        ir = compile_source("print(7);", use_printf=True)
        self.assertIn("declare i32 @printf(ptr, ...)", ir)
        self.assertIn("call i32 (ptr, ...) @printf(ptr @.fmt, i32 7)", ir)
        self.assertNotIn("@print_int", ir)

    def test_source_filename_is_escaped(self):
        ir = compile_source("print(1);", 'we"ird.mini')
        self.assertIn('source_filename = "we\\22ird.mini"', ir)


if __name__ == "__main__":
    unittest.main()
