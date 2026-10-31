# MiniLang - a mini compiler to LLVM IR (Python)

MiniLang is a tiny integer-only programming language. This project compiles
`.mini` source files into LLVM IR text (`.ll` files) using plain Python.
No LLVM Python bindings are used: the compiler writes the IR as text, and the
LLVM tools (`clang`, optionally `lli`) are only needed if you want to *run* the result.

```
 .mini source
     |  lexer.py      characters -> tokens
     v
   tokens
     |  parser.py     tokens -> AST (recursive descent)      [ast_nodes.py]
     v
    AST
     |  semantic.py   scope + error checks, names variables
     v
 checked AST
     |  codegen.py    AST -> LLVM IR text
     v
 .ll file  --->  lli file.ll          (interpret it)
           --->  clang file.ll -o exe (native executable)
```

## The language

```c
// comments start with //
int x = 10;            // declaration with a value
int y;                 // declaration without one: starts at 0
y = x * 2 + 1;         // assignment
print(y);              // prints an integer and a newline

if (x < y) {           // comparisons: <  >  <=  >=  ==  !=
    print(1);
} else if (x == y) {
    print(2);
} else {
    print(3);
}

while (x > 0) {
    x = x - 3;
}
```

* One type: 32-bit signed `int`.
* Operators: `+ - * /` (integer division, truncates toward zero), unary `-`,
  parentheses, and the comparisons above. Precedence (high to low): unary `-`,
  `* /`, `+ -`, comparisons.
* A comparison produces `1` (true) or `0` (false), so `int f = a < b;` works.
  Any number can be used as a condition: `0` is false, anything else is true.
* `if` / `while` bodies **must** use braces. `else if` chains are supported.
* Every `{ ... }` is a scope. A name can be reused in a different scope, and an
  inner block may shadow an outer variable. Declaring the same name twice in
  one scope is an error.
* `print(expr);` prints one integer per line.

Full grammar: see the docstring at the top of `parser.py`.

## Requirements and installation (Windows 11)

You need **Python 3.10 or newer**. To *run* compiled programs you also need LLVM.
Generating `.ll` files needs only Python.

1. **Python** - install from <https://www.python.org/downloads/> (tick
   "Add python.exe to PATH"), or in PowerShell:
   ```powershell
   winget install Python.Python.3.12
   ```
   Check: `python --version` (if `python` is not found, try `py --version` and use
   `py` instead of `python` in all commands below).

2. **LLVM / clang** (needed for `--run` and `--build`; LLVM 15 or newer, because the
   generated IR uses the modern `ptr` type):
   ```powershell
   winget install LLVM.LLVM
   ```
   Open a **new** terminal afterwards and check: `clang --version`.
   If `clang` is not found, add `C:\Program Files\LLVM\bin` to PATH (the compiler
   also looks there automatically).

3. **A linker for clang (only for `--build`)** - on Windows, clang links with
   Microsoft's tools, so install *Visual Studio Build Tools* with the
   "Desktop development with C++" workload:
   <https://visualstudio.microsoft.com/downloads/> (scroll to "Tools for Visual Studio").
   Without it, `clang` can't produce `.exe` files.

4. **`lli`** (optional) interprets `.ll` files directly without a linker. Check with
   `lli --version`. Some Windows LLVM installers do not include it - if it is missing,
   `--run` automatically falls back to clang.

   An alternative that bundles clang, lli and a linker without Visual Studio is
   MSYS2 (<https://www.msys2.org/>): `pacman -S mingw-w64-ucrt-x86_64-clang`.

On Linux/macOS the same commands work; use `python3` and `/` in paths.

## Usage

Run these from the project folder (the one containing `main.py`).

| Goal | Command |
|------|---------|
| Compile to `examples\arithmetic.ll` | `python main.py examples\arithmetic.mini` |
| Choose the output file | `python main.py examples\arithmetic.mini -o out.ll` |
| Compile and run (lli, or clang if lli is missing) | `python main.py examples\loops.mini --run` |
| Build a native `.exe` with clang | `python main.py examples\loops.mini --build` |
| Build the `.exe` and run it | `python main.py examples\loops.mini --build --run` |
| Show the generated IR | `python main.py examples\loops.mini --print-ir` |
| Show tokens / syntax tree | `python main.py examples\loops.mini --tokens --ast` |
| Use C `printf` for `print` | `python main.py examples\loops.mini --run --use-printf` |

You can also run the `.ll` file yourself:

```powershell
lli examples\loops.ll
clang examples\loops.ll -o loops.exe
.\loops.exe
```

Run every sample in PowerShell:

```powershell
Get-ChildItem examples\*.mini | ForEach-Object { python main.py $_.FullName --run }
```

Exit codes of `main.py`: `0` success, `1` compile error / unreadable file,
`2` an LLVM tool is missing or failed.

### Error messages

Errors show the position, the offending line and a caret:

```
Syntax error: missing_semicolon.mini:1:10: expected ';' after variable declaration but found 'print'
    int x = 5
             ^
```

Kinds of errors: *Lexical* (unknown character, `12abc`), *Syntax* (missing `;`,
`)`, `}`, ...), *Semantic* (undeclared variable, redeclaration in the same scope,
division by the literal `0`, number larger than 2147483647). Try the files in
`examples\errors\`.

## Sample programs (`examples\`)

| File | Shows | Output |
|------|-------|--------|
| `arithmetic.mini` | operators, precedence, unary minus | 13 7 30 3 14 20 -5 5 2 |
| `variables.mini` | declarations, defaults, assignment, scopes | 0 10 15 -5 2 1 |
| `conditionals.mini` | if / else if / else, nesting, comparisons as values | 1 100 2 555 1 0 |
| `loops.mini` | while: sum, factorial, countdown | 55 120 3 2 1 |
| `fibonacci.mini` | first 10 Fibonacci numbers | 0 1 1 2 3 5 8 13 21 34 |
| `primes.mini` | nested loops: primes below 30 | 2 3 5 7 11 13 17 19 23 29 |

## Project structure

```
MiniLang/
  main.py          command-line interface and the compile pipeline
  lexer.py         source text -> tokens
  parser.py        tokens -> AST (recursive descent, grammar in docstring)
  ast_nodes.py     AST node classes + a tree printer (--ast)
  semantic.py      checks the AST, resolves variables to unique stack slots
  codegen.py       AST -> LLVM IR text
  errors.py        error classes + pretty error formatting
  examples/        sample programs; examples/errors/ has programs that fail on purpose
  tests/           unit and end-to-end tests
```

## How the generated IR works

* Each variable is a stack slot (`%var.x = alloca i32`), read with `load` and written
  with `store`. Keeping variables in memory means no SSA `phi` nodes are needed.
* All `alloca` instructions are placed in the entry block, so declaring a variable
  inside a loop does not grow the stack on every iteration.
* Arithmetic uses `add`, `sub`, `mul`, `sdiv`. Comparisons use `icmp` (giving an `i1`);
  a comparison used as a number is widened with `zext`.
* `if` and `while` become labelled blocks joined by `br` (conditional and
  unconditional): `if.then.N / if.else.N / if.end.N` and
  `while.cond.N / while.body.N / while.end.N`.
* **How `print` works.** By default the module contains a small helper,
  `@print_int`, written in IR on top of `putchar`. This is deliberate: on Windows,
  `printf` is not a plain function exported by the C runtime (it is provided through
  headers/legacy libraries), so hand-written IR that calls it can fail to link or to
  run under `lli`. `putchar` is a normal function everywhere. If you prefer the
  textbook version, `--use-printf` emits `call i32 (ptr, ...) @printf(...)` instead.

## Tests

```powershell
python -m unittest discover -s tests -v
```

* `test_frontend.py` - lexer, parser (precedence, else-if, syntax errors), semantic checks.
* `test_codegen.py` - checks the IR text (alloca/load/store, arithmetic, `icmp`, branches, labels).
* `test_end_to_end.py` - compiles every sample, runs it with clang and/or lli (both print
  styles), compares the output with the expected values, validates IR with `llvm-as`,
  and tests the command-line behaviour. Tests that need an LLVM tool are skipped
  automatically if it is not installed.

### Verification status

The project was developed and tested on **Linux with Python 3.13 and LLVM/clang 18**
(`clang`, `lli`, `llvm-as`): all 71 tests passed. It has **not** been run on Windows 11;
the Windows commands above follow standard Windows behaviour of Python and LLVM, but
the installation steps (especially linking with clang) depend on your machine.

## Limitations

* Only `int` (32-bit signed). No strings, floats, booleans, arrays or functions.
* No `%`, `&&`, `||`, `!`, `break`, `continue`, or `for` loops.
* Overflow wraps around (e.g. `2147483647 + 1` is `-2147483648`).
* Division by zero is only detected when the divisor is the literal `0`; a runtime
  zero (`x / y` with `y == 0`) is undefined behaviour in LLVM and may crash.
* The largest literal is 2147483647 (write `-2147483647 - 1` for the minimum).
* `if` and `while` bodies must be `{ }` blocks. Source files must be UTF-8 (plain ASCII
  outside comments).
* No optimisation: the IR is intentionally simple and unoptimised (try
  `opt -O2 -S file.ll` if you want to see LLVM optimise it).
* Generated IR uses opaque pointers (`ptr`), so LLVM 15+ is required to consume it.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `clang was not found` | Install LLVM, open a new terminal, check `clang --version`. |
| `neither lli nor clang was found` | The `.ll` file was still written; install LLVM to run it. |
| clang error about `link.exe` / `kernel32.lib` / `msvcrt.lib` | Install Visual Studio Build Tools (C++ workload), or use `lli` / MSYS2. |
| `'python' is not recognized` | Reinstall Python with "Add to PATH", or use `py`. |
| `error: ... expected ';'` | Check the line shown above the caret - the `;` goes at the end of that statement. |
