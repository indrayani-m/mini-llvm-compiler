# MiniLang --- A Mini Compiler to LLVM IR

MiniLang is a small, integer-based programming language implemented in
Python. It translates `.mini` source files into **LLVM Intermediate
Representation (LLVM IR)** and demonstrates the main stages of compiler
design.

The project also includes a browser-based interface for writing programs
and viewing compilation results.

## Features

-   Integer variables and assignments
-   Arithmetic and comparison operators
-   `if`, `else if`, and `else` statements
-   `while` loops
-   Nested variable scopes and shadowing
-   Lexical, syntax, and semantic error reporting
-   LLVM IR generation
-   Program execution with `lli` or Clang
-   Native executable generation
-   Browser interface for viewing tokens, AST, LLVM IR, output, and
    errors

## How It Works

The compiler processes a MiniLang program in four main stages:

1.  **Lexical Analysis (`lexer.py`)** --- Converts source code into
    tokens.
2.  **Syntax Analysis (`parser.py`)** --- Checks the grammar and builds
    an Abstract Syntax Tree (AST).
3.  **Semantic Analysis (`semantic.py`)** --- Checks declarations,
    variable usage, scopes, and semantic rules.
4.  **Code Generation (`codegen.py`)** --- Converts the checked AST into
    LLVM IR.

`main.py` coordinates these stages and provides the command-line
interface.

## Example

``` c
int a = 10;
int b = 20;
print(a + b);
```

Output:

``` text
30
```

MiniLang supports signed 32-bit integers, arithmetic, comparisons,
conditional statements, `while` loops, and single-line comments using
`//`.

## Technologies

-   Python 3.10+
-   LLVM IR
-   LLVM `lli` (optional)
-   Clang
-   HTML, CSS, and JavaScript for the browser interface
-   Python `unittest` for testing

## Project Structure

``` text
mini-llvm-compiler/
├── main.py
├── lexer.py
├── parser.py
├── ast_nodes.py
├── semantic.py
├── codegen.py
├── errors.py
├── server.py
├── ui.html
├── examples/
└── tests/
```

## Getting Started

Clone the repository:

``` bash
git clone https://github.com/indrayani-m/mini-llvm-compiler.git
cd mini-llvm-compiler
```

Python 3.10 or newer is required. No additional Python packages are
needed.

Install LLVM 15 or newer and Clang if you want to run or build generated
programs. Check your installations:

``` bash
python --version
clang --version
lli --version
```

## Run the Compiler

Generate LLVM IR:

``` bash
python main.py examples/arithmetic.mini
```

Choose an output file:

``` bash
python main.py examples/arithmetic.mini -o output.ll
```

Run the program:

``` bash
python main.py examples/loops.mini --run
```

Build a native executable:

``` bash
python main.py examples/loops.mini --build
```

Inspect compilation stages:

``` bash
python main.py examples/loops.mini --tokens --ast --print-ir
```

Useful options: `--run`, `--build`, `--tokens`, `--ast`, `--print-ir`,
and `--use-printf`.

## Browser Interface

Start the local interface:

``` bash
python server.py
```

Open <http://localhost:5000>.

The interface lets you write MiniLang programs, load examples, inspect
tokens and the AST, view generated LLVM IR, and check output or errors.

## Tests

Run the test suite:

``` bash
python -m unittest discover -s tests -v
```

The original project documentation records 71 passing tests on Linux
with Python 3.13 and LLVM/Clang 18. Tests requiring unavailable LLVM
tools may be skipped.

## Limitations

MiniLang currently supports only signed 32-bit integers. It does not
support strings, floating-point values, arrays, user-defined functions,
`for` loops, or logical operators. It does not perform LLVM
optimizations by default. Runtime division by zero is not checked when
the divisor is a variable.

## Contributors

-   **Indrayani Mude** 
-   **Nimisha Nair** 

------------------------------------------------------------------------

If you find this project interesting, consider giving the repository a
⭐!
