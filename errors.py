"""Error types shared by every stage of the MiniLang compiler."""


class CompileError(Exception):
    """Base class for all compile-time errors. Carries a source position."""

    kind = "Error"

    def __init__(self, message, line=None, col=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col


class LexError(CompileError):
    kind = "Lexical error"


class ParseError(CompileError):
    kind = "Syntax error"


class SemanticError(CompileError):
    kind = "Semantic error"


def format_error(err, source, filename):
    """Build a friendly multi-line message with the offending line and a caret."""
    location = filename
    if err.line is not None:
        location += ":%d:%d" % (err.line, err.col)
    text = "%s: %s: %s" % (err.kind, location, err.message)

    if err.line is not None:
        lines = source.splitlines()
        if 1 <= err.line <= len(lines):
            shown = lines[err.line - 1].replace("\t", " ")
            text += "\n    " + shown
            text += "\n    " + " " * (err.col - 1) + "^"
    return text
