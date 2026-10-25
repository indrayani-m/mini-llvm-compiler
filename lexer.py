"""Lexer: turns MiniLang source text into a list of tokens.

Token types:
  * "NUMBER"  - an integer literal (value is a Python int)
  * "IDENT"   - a variable name
  * "EOF"     - end of input
  * keywords and symbols use their own text as the type,
    e.g. "int", "print", "if", "+", "==", "{"
"""

from errors import LexError

KEYWORDS = {"int", "print", "if", "else", "while"}

TWO_CHAR_OPS = {"==", "!=", "<=", ">="}
ONE_CHAR_OPS = set("+-*/<>=(){};")

DIGITS = "0123456789"


class Token:
    def __init__(self, type, value, line, col, length=0):
        self.type = type
        self.value = value
        self.line = line
        self.col = col
        self.length = length   # characters in the source text

    def __repr__(self):
        return "Token(%r, %r, %d:%d)" % (self.type, self.value, self.line, self.col)


def _is_letter(ch):
    return ch.isascii() and (ch.isalpha() or ch == "_")


def tokenize(source):
    tokens = []
    i = 0
    line = 1
    col = 1
    n = len(source)

    while i < n:
        ch = source[i]

        # --- whitespace and newlines ---
        if ch == "\n":
            i += 1
            line += 1
            col = 1
            continue
        if ch in " \t\r":
            i += 1
            col += 1
            continue

        # --- comments: // until end of line ---
        if source.startswith("//", i):
            while i < n and source[i] != "\n":
                i += 1
            continue

        # --- numbers ---
        if ch in DIGITS:
            start = i
            while i < n and source[i] in DIGITS:
                i += 1
            if i < n and _is_letter(source[i]):
                raise LexError(
                    "invalid token '%s%s...': a number cannot be followed by letters"
                    % (source[start:i], source[i]),
                    line, col)
            text = source[start:i]
            tokens.append(Token("NUMBER", int(text), line, col, len(text)))
            col += len(text)
            continue

        # --- identifiers and keywords ---
        if _is_letter(ch):
            start = i
            while i < n and (_is_letter(source[i]) or source[i] in DIGITS):
                i += 1
            text = source[start:i]
            if text in KEYWORDS:
                tokens.append(Token(text, text, line, col, len(text)))
            else:
                tokens.append(Token("IDENT", text, line, col, len(text)))
            col += len(text)
            continue

        # --- operators and punctuation ---
        two = source[i:i + 2]
        if two in TWO_CHAR_OPS:
            tokens.append(Token(two, two, line, col, 2))
            i += 2
            col += 2
            continue
        if ch in ONE_CHAR_OPS:
            tokens.append(Token(ch, ch, line, col, 1))
            i += 1
            col += 1
            continue

        if ch == "!":
            raise LexError("unexpected character '!' (did you mean '!=')", line, col)
        raise LexError("unexpected character %r" % ch, line, col)

    tokens.append(Token("EOF", "", line, col, 0))
    return tokens
