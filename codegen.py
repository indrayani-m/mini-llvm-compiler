"""LLVM IR code generator: AST -> text of a .ll file.

The IR is produced as plain text; no LLVM library is needed.

Design (kept deliberately simple):
  * Every MiniLang variable is a stack slot:  %var.x = alloca i32
    Reads use `load`, writes use `store`.  Because variables live in memory
    we never need SSA phi nodes.
  * All `alloca` instructions are collected and emitted in the function's
    entry block, so a declaration inside a loop does not grow the stack on
    every iteration.
  * Comparisons produce an i1 (icmp).  Where a comparison is used as a
    number (e.g. `int f = a < b;`) it is widened to i32 with `zext`.
  * Control flow uses labelled basic blocks and `br` instructions.

How `print` is implemented:
  * default: a small helper function @print_int is added to the module. It
    prints the number using only `putchar`, which is available on every
    platform. (On Windows `printf` is not a plain exported function of the
    C runtime, so hand-written IR calling it can fail to link or to run
    under lli.)
  * use_printf=True: calls the classic  printf("%d\\n", value)  instead.
"""

from ast_nodes import (Assign, BinaryOp, Block, If, Number, Print, UnaryOp,
                       VarDecl, Variable, While)

ARITH_INSTRUCTIONS = {"+": "add", "-": "sub", "*": "mul", "/": "sdiv"}
COMPARE_PREDICATES = {"<": "slt", ">": "sgt", "<=": "sle", ">=": "sge",
                      "==": "eq", "!=": "ne"}

# Prints a signed 32-bit integer followed by a newline, using only putchar.
# print_digits is recursive: it prints the leading digits first.
PUTCHAR_HELPERS = r"""declare i32 @putchar(i32)

define void @print_digits(i64 %n) {
entry:
  %big = icmp uge i64 %n, 10
  br i1 %big, label %recurse, label %emit
recurse:
  %q = udiv i64 %n, 10
  call void @print_digits(i64 %q)
  br label %emit
emit:
  %r = urem i64 %n, 10
  %d = add i64 %r, 48
  %c = trunc i64 %d to i32
  %ignored = call i32 @putchar(i32 %c)
  ret void
}

define void @print_int(i32 %v) {
entry:
  %w = sext i32 %v to i64
  %neg = icmp slt i64 %w, 0
  br i1 %neg, label %negative, label %positive
negative:
  %minus = call i32 @putchar(i32 45)
  %m = sub i64 0, %w
  call void @print_digits(i64 %m)
  br label %done
positive:
  call void @print_digits(i64 %w)
  br label %done
done:
  %nl = call i32 @putchar(i32 10)
  ret void
}
"""

PRINTF_HELPERS = r"""@.fmt = private unnamed_addr constant [4 x i8] c"%d\0A\00"

declare i32 @printf(ptr, ...)
"""


def llvm_escape(text):
    """Escape a string for use inside an LLVM "..." literal."""
    out = []
    for byte in text.encode("utf-8"):
        if 32 <= byte < 127 and byte not in (34, 92):
            out.append(chr(byte))
        else:
            out.append("\\%02X" % byte)
    return "".join(out)


class CodeGenerator:
    def __init__(self, source_name="program.mini", use_printf=False):
        self.source_name = source_name
        self.use_printf = use_printf
        self.allocas = []     # lines for the entry block
        self.body = []        # lines for everything after the entry block
        self.temp_count = 0
        self.label_count = 0

    # ----- small helpers -----

    def new_temp(self):
        self.temp_count += 1
        return "%%t%d" % self.temp_count

    def new_label_id(self):
        self.label_count += 1
        return self.label_count

    def emit(self, text):
        self.body.append("  " + text)

    def emit_label(self, name):
        self.body.append("")
        self.body.append(name + ":")

    # ----- entry point -----

    def generate(self, program):
        for statement in program.statements:
            self.gen_statement(statement)

        lines = []
        lines.append('source_filename = "%s"' % llvm_escape(self.source_name))
        lines.append("")
        lines.append(PRINTF_HELPERS if self.use_printf else PUTCHAR_HELPERS)
        lines.append("define i32 @main() {")
        lines.append("entry:")
        lines.extend("  " + a for a in self.allocas)
        lines.append("  br label %start")
        lines.append("")
        lines.append("start:")
        lines.extend(self.body)
        lines.append("  ret i32 0")
        lines.append("}")
        return "\n".join(lines) + "\n"

    # ----- statements -----

    def gen_statement(self, node):
        if isinstance(node, VarDecl):
            self.allocas.append("%%%s = alloca i32" % node.ir_name)
            if node.init is not None:
                value = self.gen_int(node.init)
            else:
                value = "0"                      # uninitialised ints start at 0
            self.emit("store i32 %s, ptr %%%s" % (value, node.ir_name))

        elif isinstance(node, Assign):
            value = self.gen_int(node.value)
            self.emit("store i32 %s, ptr %%%s" % (value, node.ir_name))

        elif isinstance(node, Print):
            value = self.gen_int(node.value)
            if self.use_printf:
                temp = self.new_temp()
                self.emit("%s = call i32 (ptr, ...) @printf(ptr @.fmt, i32 %s)"
                          % (temp, value))
            else:
                self.emit("call void @print_int(i32 %s)" % value)

        elif isinstance(node, Block):
            for statement in node.statements:
                self.gen_statement(statement)

        elif isinstance(node, If):
            self.gen_if(node)

        elif isinstance(node, While):
            self.gen_while(node)

        else:
            raise TypeError("cannot generate code for %r" % (node,))

    def gen_if(self, node):
        n = self.new_label_id()
        then_label = "if.then.%d" % n
        else_label = "if.else.%d" % n
        end_label = "if.end.%d" % n
        has_else = node.else_body is not None

        cond = self.gen_condition(node.condition)
        self.emit("br i1 %s, label %%%s, label %%%s"
                  % (cond, then_label, else_label if has_else else end_label))

        self.emit_label(then_label)
        self.gen_statement(node.then_body)
        self.emit("br label %%%s" % end_label)

        if has_else:
            self.emit_label(else_label)
            self.gen_statement(node.else_body)
            self.emit("br label %%%s" % end_label)

        self.emit_label(end_label)

    def gen_while(self, node):
        n = self.new_label_id()
        cond_label = "while.cond.%d" % n
        body_label = "while.body.%d" % n
        end_label = "while.end.%d" % n

        self.emit("br label %%%s" % cond_label)

        self.emit_label(cond_label)
        cond = self.gen_condition(node.condition)
        self.emit("br i1 %s, label %%%s, label %%%s" % (cond, body_label, end_label))

        self.emit_label(body_label)
        self.gen_statement(node.body)
        self.emit("br label %%%s" % cond_label)

        self.emit_label(end_label)

    # ----- expressions -----
    # gen_expr returns (operand, llvm_type) where type is "i32" or "i1".

    def gen_expr(self, node):
        if isinstance(node, Number):
            return str(node.value), "i32"

        if isinstance(node, Variable):
            temp = self.new_temp()
            self.emit("%s = load i32, ptr %%%s" % (temp, node.ir_name))
            return temp, "i32"

        if isinstance(node, UnaryOp):            # only unary minus exists
            operand = self.gen_int(node.operand)
            temp = self.new_temp()
            self.emit("%s = sub i32 0, %s" % (temp, operand))
            return temp, "i32"

        if isinstance(node, BinaryOp):
            left = self.gen_int(node.left)
            right = self.gen_int(node.right)
            temp = self.new_temp()
            if node.op in ARITH_INSTRUCTIONS:
                self.emit("%s = %s i32 %s, %s"
                          % (temp, ARITH_INSTRUCTIONS[node.op], left, right))
                return temp, "i32"
            self.emit("%s = icmp %s i32 %s, %s"
                      % (temp, COMPARE_PREDICATES[node.op], left, right))
            return temp, "i1"

        raise TypeError("cannot generate code for expression %r" % (node,))

    def gen_int(self, node):
        """Evaluate an expression and make sure the result is an i32."""
        operand, ty = self.gen_expr(node)
        if ty == "i1":
            temp = self.new_temp()
            self.emit("%s = zext i1 %s to i32" % (temp, operand))
            return temp
        return operand

    def gen_condition(self, node):
        """Evaluate an expression as a branch condition (an i1)."""
        operand, ty = self.gen_expr(node)
        if ty == "i1":
            return operand
        temp = self.new_temp()
        self.emit("%s = icmp ne i32 %s, 0" % (temp, operand))
        return temp


def generate(program, source_name="program.mini", use_printf=False):
    return CodeGenerator(source_name, use_printf).generate(program)
