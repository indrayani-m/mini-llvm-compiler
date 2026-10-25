"""End-to-end tests: compile .mini programs and actually run the LLVM IR.

Programs are run with `clang` (native build) and/or `lli` (LLVM interpreter),
whichever is installed. Tests are skipped if neither tool is available.
Expected outputs below were worked out by hand from the sample programs.
"""

import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from main import compile_source, find_tool, main as cli_main

CLANG = find_tool("clang")
LLI = find_tool("lli")
LLVM_AS = find_tool("llvm-as")
EXAMPLES = os.path.join(ROOT, "examples")

SAMPLE_OUTPUT = {
    "arithmetic.mini": [13, 7, 30, 3, 14, 20, -5, 5, 2],
    "variables.mini": [0, 10, 15, -5, 2, 1],
    "conditionals.mini": [1, 100, 2, 555, 1, 0],
    "loops.mini": [55, 120, 3, 2, 1],
    "fibonacci.mini": [0, 1, 1, 2, 3, 5, 8, 13, 21, 34],
    "primes.mini": [2, 3, 5, 7, 11, 13, 17, 19, 23, 29],
}

ERROR_SAMPLES = {
    "undeclared.mini": "used before it is declared",
    "redeclared.mini": "already declared",
    "missing_semicolon.mini": "expected ';'",
    "bad_character.mini": "unexpected character",
    "division_by_zero.mini": "division by zero",
    "missing_brace.mini": "expected '}'",
}


def available_runners():
    runners = []
    if CLANG:
        runners.append("clang")
    if LLI:
        runners.append("lli")
    return runners


def execute(ll_path, runner, tmpdir):
    """Run an .ll file with the chosen tool and return (stdout, returncode)."""
    if runner == "lli":
        result = subprocess.run([LLI, ll_path], capture_output=True,
                                text=True, timeout=60)
        return result.stdout, result.returncode
    exe = os.path.join(tmpdir, "prog.exe" if os.name == "nt" else "prog")
    build = subprocess.run([CLANG, ll_path, "-o", exe],
                           capture_output=True, text=True, timeout=120)
    if build.returncode != 0:
        raise AssertionError("clang failed:\n" + build.stderr)
    result = subprocess.run([exe], capture_output=True, text=True, timeout=60)
    return result.stdout, result.returncode


def run_source(source, runner, use_printf=False):
    """Compile MiniLang source text, run it, return the printed ints."""
    with tempfile.TemporaryDirectory() as tmp:
        ll_path = os.path.join(tmp, "test.ll")
        with open(ll_path, "w", newline="\n") as f:
            f.write(compile_source(source, "test.mini", use_printf))
        out, code = execute(ll_path, runner, tmp)
        if code != 0:
            raise AssertionError("program exited with code %d" % code)
        return [int(line) for line in out.split()]


@unittest.skipUnless(available_runners(), "neither clang nor lli is installed")
class SampleProgramTests(unittest.TestCase):
    def test_sample_programs(self):
        for runner in available_runners():
            for use_printf in (False, True):
                for name, expected in SAMPLE_OUTPUT.items():
                    with self.subTest(runner=runner, printf=use_printf, sample=name):
                        with open(os.path.join(EXAMPLES, name)) as f:
                            source = f.read()
                        self.assertEqual(run_source(source, runner, use_printf),
                                         expected)


@unittest.skipUnless(available_runners(), "neither clang nor lli is installed")
class BehaviourTests(unittest.TestCase):
    def check(self, source, expected):
        for runner in available_runners():
            for use_printf in (False, True):
                with self.subTest(runner=runner, printf=use_printf):
                    self.assertEqual(run_source(source, runner, use_printf), expected)

    def test_int_limits_print_correctly(self):
        self.check("int x = 2147483647; print(x); print(-x); print(-x - 1);",
                   [2147483647, -2147483647, -2147483648])

    def test_zero_prints_as_zero(self):
        self.check("print(0); print(-0);", [0, 0])

    def test_integer_division_truncates_toward_zero(self):
        self.check("print(7 / 2); print(-7 / 2);", [3, -3])

    def test_while_loop_that_never_runs(self):
        self.check("int i = 5; while (i < 3) { print(i); } print(99);", [99])

    def test_shadowing(self):
        self.check("int x = 1; { int x = 2; print(x); } print(x);", [2, 1])

    def test_nested_loops(self):
        self.check(
            "int i = 0; int total = 0;"
            "while (i < 3) { int j = 0;"
            "  while (j < 3) { total = total + 1; j = j + 1; }"
            "  i = i + 1; }"
            "print(total);", [9])

    def test_long_loop_with_declaration_in_body(self):
        self.check("int i = 0; while (i < 2000000) { int t = i; i = i + 1; }"
                   "print(i);", [2000000])

    def test_numeric_value_as_condition(self):
        self.check("int a = 3; if (a) { print(1); } else { print(0); }"
                   "int z = 0; if (z) { print(1); } else { print(0); }", [1, 0])

    def test_all_comparisons_as_values(self):
        self.check(
            "int a = 2; int b = 3;"
            "print(a < b); print(a > b); print(a <= b); print(a >= b);"
            "print(a == b); print(a != b);", [1, 0, 1, 0, 0, 1])


@unittest.skipUnless(LLVM_AS, "llvm-as is not installed")
class IRVerifierTests(unittest.TestCase):
    def test_llvm_accepts_every_sample(self):
        for use_printf in (False, True):
            for name in SAMPLE_OUTPUT:
                with self.subTest(sample=name, printf=use_printf):
                    with open(os.path.join(EXAMPLES, name)) as f:
                        ir = compile_source(f.read(), name, use_printf)
                    with tempfile.TemporaryDirectory() as tmp:
                        path = os.path.join(tmp, "x.ll")
                        with open(path, "w", newline="\n") as f:
                            f.write(ir)
                        result = subprocess.run(
                            [LLVM_AS, path, "-o", os.devnull],
                            capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0, result.stderr)


class CommandLineTests(unittest.TestCase):
    def test_writes_ll_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out.ll")
            code = cli_main([os.path.join(EXAMPLES, "arithmetic.mini"), "-o", out])
            self.assertEqual(code, 0)
            with open(out) as f:
                self.assertIn("define i32 @main()", f.read())

    def test_error_samples_fail_with_readable_messages(self):
        main_py = os.path.join(ROOT, "main.py")
        for name, fragment in ERROR_SAMPLES.items():
            with self.subTest(sample=name):
                with tempfile.TemporaryDirectory() as tmp:
                    out = os.path.join(tmp, "out.ll")
                    result = subprocess.run(
                        [sys.executable, main_py,
                         os.path.join(EXAMPLES, "errors", name), "-o", out],
                        capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(fragment, result.stderr)
                    self.assertIn("^", result.stderr)          # caret line shown
                    self.assertFalse(os.path.exists(out))     # no .ll on error

    def test_missing_file(self):
        self.assertEqual(cli_main(["no_such_file.mini"]), 1)

    @unittest.skipUnless(available_runners(), "neither clang nor lli is installed")
    def test_run_flag_executes_program(self):
        main_py = os.path.join(ROOT, "main.py")
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "loops.ll")
            result = subprocess.run(
                [sys.executable, main_py, os.path.join(EXAMPLES, "loops.mini"),
                 "-o", out, "--run"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--- program output ---", result.stdout)
            self.assertIn("55", result.stdout)

    @unittest.skipUnless(CLANG, "clang is not installed")
    def test_build_flag_creates_executable(self):
        main_py = os.path.join(ROOT, "main.py")
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "fib.ll")
            result = subprocess.run(
                [sys.executable, main_py, os.path.join(EXAMPLES, "fibonacci.mini"),
                 "-o", out, "--build", "--run"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            exe = os.path.join(tmp, "fib.exe" if os.name == "nt" else "fib")
            self.assertTrue(os.path.isfile(exe))
            self.assertIn("34", result.stdout)


if __name__ == "__main__":
    unittest.main()
