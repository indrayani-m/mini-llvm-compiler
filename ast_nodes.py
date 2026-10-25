"""AST node definitions for MiniLang, plus a tiny pretty-printer (dump).

Every node remembers the line/column where it started so later stages
(the semantic analyzer) can report useful error positions.

`ir_name` is filled in by the semantic analyzer: it is the unique LLVM
name of the stack slot that a variable refers to.
"""

from dataclasses import dataclass, fields, is_dataclass
from typing import Any, List, Optional


# ---------- expressions ----------

@dataclass
class Number:
    value: int
    line: int = 0
    col: int = 0


@dataclass
class Variable:
    name: str
    line: int = 0
    col: int = 0
    ir_name: Optional[str] = None


@dataclass
class UnaryOp:
    op: str            # only "-"
    operand: Any
    line: int = 0
    col: int = 0


@dataclass
class BinaryOp:
    op: str            # + - * /  <  >  <=  >=  ==  !=
    left: Any
    right: Any
    line: int = 0
    col: int = 0


# ---------- statements ----------

@dataclass
class VarDecl:
    name: str
    init: Optional[Any]    # expression or None (defaults to 0)
    line: int = 0
    col: int = 0
    ir_name: Optional[str] = None


@dataclass
class Assign:
    name: str
    value: Any
    line: int = 0
    col: int = 0
    ir_name: Optional[str] = None


@dataclass
class Print:
    value: Any
    line: int = 0
    col: int = 0


@dataclass
class Block:
    statements: List[Any]
    line: int = 0
    col: int = 0


@dataclass
class If:
    condition: Any
    then_body: Block
    else_body: Optional[Any]   # Block, another If (for "else if"), or None
    line: int = 0
    col: int = 0


@dataclass
class While:
    condition: Any
    body: Block
    line: int = 0
    col: int = 0


@dataclass
class Program:
    statements: List[Any]


# ---------- pretty printer ----------

_HIDDEN_FIELDS = ("line", "col", "ir_name")


def _dump_lines(node, indent):
    pad = "  " * indent
    if isinstance(node, list):
        if not node:
            return [pad + "(empty)"]
        lines = []
        for item in node:
            lines.extend(_dump_lines(item, indent))
        return lines

    scalars = []
    children = []
    for f in fields(node):
        if f.name in _HIDDEN_FIELDS:
            continue
        value = getattr(node, f.name)
        if value is None:
            continue
        if isinstance(value, list) or is_dataclass(value):
            children.append((f.name, value))
        else:
            scalars.append("%s=%r" % (f.name, value))

    head = pad + type(node).__name__
    if scalars:
        head += "(" + ", ".join(scalars) + ")"
    lines = [head]
    for label, child in children:
        lines.append(pad + "  " + label + ":")
        lines.extend(_dump_lines(child, indent + 2))
    return lines


def dump(node):
    """Return an indented, human-readable text tree of an AST."""
    return "\n".join(_dump_lines(node, 0))
