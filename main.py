"""MiniLang compiler - command-line interface.

Usage examples:
    python main.py examples/arithmetic.mini
    python main.py examples/loops.mini --run
    python main.py examples/loops.mini --build --run
    python main.py examples/loops.mini --tokens --ast --print-ir
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

from ast_nodes import dump
from codegen import CodeGenerator
from errors import CompileError, format_error
from lexer import tokenize
from parser import Parser
from semantic import SemanticAnalyzer


# ---------------------------------------------------------------------------
# The compiler pipeline
# ---------------------------------------------------------------------------

def compile_source(source, filename="program.mini", use_printf=False):
    """Compile MiniLang source text and return the LLVM IR as a string.

    Raises CompileError (or a subclass) if the program is invalid.
    """
    tokens = tokenize(source)
    program = Parser(tokens).parse_program()
    SemanticAnalyzer().analyze(program)
    return CodeGenerator(filename, use_printf).generate(program)


# ---------------------------------------------------------------------------
# Finding and running LLVM tools
# ---------------------------------------------------------------------------

def find_tool(name):
    """Look for an LLVM tool on PATH, then in the default Windows install dir."""
    path = shutil.which(name)
    if path:
        return path
    if os.name == "nt":
        for env in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(env)
            if base:
                candidate = os.path.join(base, "LLVM", "bin", name + ".exe")
                if os.path.isfile(candidate):
                    return candidate
    return None


def exe_path_for(ll_path):
    base = os.path.splitext(ll_path)[0]
    return os.path.abspath(base + (".exe" if os.name == "nt" else ""))


def build_with_clang(clang, ll_path, exe_path):
    result = subprocess.run([clang, ll_path, "-o", exe_path],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print("error: clang failed to build the program:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return False
    return True


def run_program(command):
    print("--- program output ---")
    sys.stdout.flush()
    result = subprocess.run(command)
    print("--- exit code %d ---" % result.returncode)
    return result.returncode


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def make_arg_parser():
    p = argparse.ArgumentParser(
        prog="main.py",
        description="MiniLang compiler: translates a .mini file to LLVM IR (.ll).")
    p.add_argument("source", help="path to the .mini source file")
    p.add_argument("-o", "--output",
                   help="path of the .ll file to write (default: next to the source)")
    p.add_argument("--run", action="store_true",
                   help="run the program (uses lli, or clang if lli is missing)")
    p.add_argument("--build", action="store_true",
                   help="build a native executable with clang")
    p.add_argument("--tokens", action="store_true", help="show the token list")
    p.add_argument("--ast", action="store_true", help="show the syntax tree")
    p.add_argument("--print-ir", action="store_true",
                   help="print the generated LLVM IR to the console")
    p.add_argument("--use-printf", action="store_true",
                   help="implement print with C printf instead of the portable "
                        "putchar-based helper")
    return p


def main(argv=None):
    args = make_arg_parser().parse_args(argv)

    # ---- read the source ----
    try:
        with open(args.source, "r", encoding="utf-8-sig") as f:
            source = f.read()
    except OSError as e:
        print("error: cannot read '%s': %s" % (args.source, e.strerror),
              file=sys.stderr)
        return 1
    except UnicodeDecodeError:
        print("error: '%s' is not a valid UTF-8 text file" % args.source,
              file=sys.stderr)
        return 1

    filename = os.path.basename(args.source)

    # ---- compile ----
    try:
        tokens = tokenize(source)
        if args.tokens:
            print("== tokens ==")
            for t in tokens:
                print("%4d:%-3d %-8s %r" % (t.line, t.col, t.type, t.value))

        program = Parser(tokens).parse_program()
        if args.ast:
            print("== syntax tree ==")
            print(dump(program))

        SemanticAnalyzer().analyze(program)
        ir = CodeGenerator(filename, args.use_printf).generate(program)
    except CompileError as err:
        print(format_error(err, source, filename), file=sys.stderr)
        return 1

    # ---- write the .ll file ----
    ll_path = args.output or os.path.splitext(args.source)[0] + ".ll"
    try:
        with open(ll_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(ir)
    except OSError as e:
        print("error: cannot write '%s': %s" % (ll_path, e.strerror),
              file=sys.stderr)
        return 1
    print("Compiled %s -> %s" % (args.source, ll_path))

    if args.print_ir:
        print("== LLVM IR ==")
        print(ir, end="")

    if not (args.run or args.build):
        return 0

    # ---- optionally build / run with LLVM tools ----
    clang = find_tool("clang")
    lli = find_tool("lli")
    built_exe = None

    if args.build:
        if not clang:
            print("error: clang was not found. Install LLVM and make sure "
                  "clang is on PATH (see README.md).", file=sys.stderr)
            return 2
        exe = exe_path_for(ll_path)
        if not build_with_clang(clang, ll_path, exe):
            return 2
        print("Built executable -> %s" % exe)
        built_exe = exe

    if args.run:
        if built_exe:
            return run_program([built_exe])
        if lli:
            return run_program([lli, ll_path])
        if clang:
            print("note: lli not found, building with clang instead.")
            with tempfile.TemporaryDirectory() as tmp:
                exe = os.path.join(tmp, "program.exe" if os.name == "nt" else "program")
                if not build_with_clang(clang, ll_path, exe):
                    return 2
                return run_program([exe])
        print("error: neither lli nor clang was found. The .ll file was still "
              "written; install LLVM to run it (see README.md).", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
