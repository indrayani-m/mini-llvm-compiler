"""MiniLang web UI server.

Run with:
    python server.py

Then open http://localhost:5000 in your browser.
No extra packages needed - uses only Python's built-in http.server.
"""

import io
import json
import os
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer

# Make sure imports find the compiler modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ast_nodes import dump
from codegen import CodeGenerator
from errors import CompileError, format_error
from lexer import tokenize
from main import find_tool, build_with_clang, exe_path_for
from parser import Parser
from semantic import SemanticAnalyzer

EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples")

# ---------------------------------------------------------------------------
# Compiler pipeline — returns a dict the frontend can consume
# ---------------------------------------------------------------------------

def run_pipeline(source, filename="program.mini", use_printf=False):
    """Run all compiler stages and return a result dict."""
    result = {
        "filename": filename,
        "tokens": None,
        "ast": None,
        "ir": None,
        "output": None,
        "error": None,
    }

    try:
        # Lexer
        toks = tokenize(source)
        result["tokens"] = [
            {"line": t.line, "col": t.col, "type": t.type, "value": repr(t.value)}
            for t in toks
        ]

        # Parser
        program = Parser(toks).parse_program()
        result["ast"] = dump(program)

        # Semantic
        SemanticAnalyzer().analyze(program)

        # Codegen
        ir = CodeGenerator(filename, use_printf).generate(program)
        result["ir"] = ir

        # Run the program
        clang = find_tool("clang")
        lli = find_tool("lli")

        if lli or clang:
            with tempfile.TemporaryDirectory() as tmp:
                ll_path = os.path.join(tmp, "prog.ll")
                with open(ll_path, "w", newline="\n") as f:
                    f.write(ir)

                if lli:
                    r = subprocess.run([lli, ll_path], capture_output=True,
                                       text=True, timeout=10)
                    if r.returncode == 0:
                        result["output"] = r.stdout
                    else:
                        result["output"] = "(lli error: %s)" % r.stderr.strip()
                elif clang:
                    exe = os.path.join(tmp, "prog.exe" if os.name == "nt" else "prog")
                    br = subprocess.run([clang, ll_path, "-o", exe],
                                        capture_output=True, text=True, timeout=30)
                    if br.returncode != 0:
                        result["output"] = "(clang build error: %s)" % br.stderr.strip()
                    else:
                        r = subprocess.run([exe], capture_output=True, text=True,
                                           timeout=10)
                        result["output"] = r.stdout
        else:
            result["output"] = "(no LLVM tool found — IR generated but not run)"

    except CompileError as err:
        result["error"] = format_error(err, source, filename)

    return result


def list_examples():
    """Return the names and sources of built-in example programs."""
    examples = []
    order = ["arithmetic.mini", "variables.mini", "conditionals.mini",
             "loops.mini", "fibonacci.mini", "primes.mini"]
    for name in order:
        path = os.path.join(EXAMPLES_DIR, name)
        try:
            with open(path, encoding="utf-8") as f:
                examples.append({"name": name, "source": f.read()})
        except OSError:
            pass
    return examples


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui.html")

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Suppress the default per-request log noise
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(HTML_PATH, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/examples":
            self.send_json(list_examples())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/compile":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self.send_json({"error": "bad request"}, 400)
                return
            source = data.get("source", "")
            filename = data.get("filename", "program.mini")
            use_printf = bool(data.get("use_printf", False))
            result = run_pipeline(source, filename, use_printf)
            self.send_json(result)
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    port = 5000
    server = HTTPServer(("localhost", port), Handler)
    url = "http://localhost:%d" % port
    print("MiniLang UI running at %s" % url)
    print("Press Ctrl+C to stop.")

    # Try to open the browser automatically
    import webbrowser
    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
