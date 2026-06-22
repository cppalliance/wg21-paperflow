#
# Copyright (c) 2026 Luan Fonseca (luan@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Whitespace normalization for code-block lines.

WG21 PDFs encode C++ code with justified spacing that leaks into the
text layer as artifact spaces around punctuation that no human author
writes:

    template <typename From >
    [[ maybe_unused ]] To x = L:: lowest ();
    converting_limits_throws <To, From >()

These artifacts originate in PDF kerning + the dual-extraction word-gap
heuristic; they are not meaningful C++. This module rewrites the most
common patterns on a per-line basis, scoped to ``SectionKind.CODE``.

Conservative-by-default: any line containing a string or character
literal delimiter (``"`` or ``'``) is left untouched, since the rules
would otherwise corrupt literal contents (``"a < b"`` -> ``"a< b"``).
The corpus is template/declaration-heavy and rarely contains literals,
so the skip is a small loss for a large safety margin.

:func:`is_diagram_block` detects text-layer ASCII diagrams (box-drawing
glyphs, Unicode arrows, math symbols, pipe/slash art). When any line
in a CODE block trips a diagram signal, the whole block skips
:func:`normalize_code_line` so spacing is preserved verbatim.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# C++ keywords that legitimately take a space before ``(``. Stripping
# the space here would produce non-idiomatic code (``if(x)``) for
# control-flow constructs that humans always write with the space.
_KEYWORDS_BEFORE_PAREN = frozenset(
    {
        "if",
        "for",
        "while",
        "switch",
        "do",
        "else",
        "catch",
        "return",
        "sizeof",
        "typeid",
        "throw",
        "decltype",
        "noexcept",
        "alignof",
        "alignas",
        "static_assert",
        "constexpr",
        "consteval",
        "new",
        "delete",
        "co_await",
        "co_yield",
        "co_return",
        "requires",
    }
)

# Keywords that introduce a template / constrained construct and so keep
# a space before `<`. ``template <T>`` is the canonical example;
# tightening to ``template<T>`` is jarring even though it parses.
# ``concept`` is its sibling: should the bare keyword ever land before
# `<` in a paper, keeping the space is the faithful rendering. Both are
# reserved words, so a skip here can never suppress tightening of a
# user-named type or concept-id (``vector <T>``, ``convertible_to <T>``),
# which is exactly what we still want to tighten.
_KEYWORDS_BEFORE_ANGLE = frozenset({"template", "concept"})

# `ident <` where ident is a template-class-like name. The lookahead
# rejects `<<` (stream insertion) and whitespace (`a < b` comparison),
# and requires the next char to begin a template-argument list. The
# keyword skip is enforced by the substitution callback.
_IDENT_OPEN_ANGLE_RE = re.compile(r"([A-Za-z_]\w*) <(?=[A-Za-z_:])")

# Space before closing angle bracket when immediately followed by a
# template-closing punctuation token. Whitespace is intentionally NOT
# allowed in the lookahead so `a > b` (comparison), `a > 0` and `a >= b`
# are left alone.
_SPACE_BEFORE_CLOSE_ANGLE_RE = re.compile(r"(\w) >(?=$|[,;)\]}>]|\(|::|\.|->)")

# `ident (` where ident is not a control keyword. Function call/decl
# tightening. Skip-list is consulted at substitution time.
_IDENT_OPEN_PAREN_RE = re.compile(r"([A-Za-z_]\w*) \(")

# Qualified-name separator with stray space: `L:: lowest` -> `L::lowest`.
_DBL_COLON_SPACE_RE = re.compile(r"::\s+([A-Za-z_])")

# Attribute brackets: `[[ name ]]` -> `[[name]]`.
_ATTR_OPEN_RE = re.compile(r"\[\[\s+")
_ATTR_CLOSE_RE = re.compile(r"\s+\]\]")

# Space before comma between template/argument items: `<From , To>`.
_SPACE_BEFORE_COMMA_RE = re.compile(r"(\w) ,")

# Diagram guard: Unicode ranges and symbols that signal ASCII-art blocks.
_BOX_DRAWING_FIRST = "\u2500"
_BOX_DRAWING_LAST = "\u257f"
_UNICODE_ARROW_FIRST = "\u2190"
_UNICODE_ARROW_LAST = "\u21ff"
_EMPTY_SET_CHAR = "\u2205"
_SECTION_SIGN_CHAR = "\u00a7"
_SUPERSCRIPT_FIRST = 0x2070
_SUPERSCRIPT_LAST = 0x209C

# ASCII-art lines may use only these characters (plus space). A line must
# also contain ``\`` or ``|`` so ``//`` and ``// ----`` are not flagged.
_ASCII_ART_CHARS = frozenset(" /\\|_+-.':~")
_ASCII_ART_REQUIRED = frozenset("\\|")


def _has_box_drawing(line: str) -> bool:
    return any(_BOX_DRAWING_FIRST <= ch <= _BOX_DRAWING_LAST for ch in line)


def _has_unicode_arrow(line: str) -> bool:
    return any(_UNICODE_ARROW_FIRST <= ch <= _UNICODE_ARROW_LAST for ch in line)


def _has_diagram_special(line: str) -> bool:
    for ch in line:
        if ch == _EMPTY_SET_CHAR or ch == _SECTION_SIGN_CHAR:
            return True
        code = ord(ch)
        if _SUPERSCRIPT_FIRST <= code <= _SUPERSCRIPT_LAST:
            return True
    return False


def _is_ascii_art_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if not any(ch in _ASCII_ART_REQUIRED for ch in stripped):
        return False
    return all(ch in _ASCII_ART_CHARS for ch in stripped)


def is_diagram_block(lines: Iterable[str]) -> bool:
    """Return True when any line signals a text-layer ASCII diagram.

    Whole-block skip: one diagram line disables normalization for every
    line in the CODE section. Signals are box-drawing glyphs, Unicode
    arrows (ASCII ``->`` is deliberately excluded), math symbols
    (empty set, section sign, sub/superscript), and pipe/slash ASCII
    art whose characters are confined to spacing and diagram punctuation.
    """
    for line in lines:
        if (
            _has_box_drawing(line)
            or _has_unicode_arrow(line)
            or _has_diagram_special(line)
            or _is_ascii_art_line(line)
        ):
            return True
    return False


def maybe_normalize_code_line(line: str, *, preserve_spacing: bool) -> str:
    """Normalize a code line unless the block is a diagram (spacing preserved)."""
    if preserve_spacing:
        return line
    return normalize_code_line(line)


def _has_string_literal(line: str) -> bool:
    """True if the line contains a string or character literal delimiter.

    Conservative: any unescaped quote disables normalization. Catches
    raw string literals (``R"(...)"``) by matching the ``"`` directly.
    Inside fenced code blocks we trust the language is C-family.
    """
    return '"' in line or "'" in line


def _is_preprocessor_directive(line: str) -> bool:
    """True if the line is a C/C++ preprocessor directive.

    Preprocessor directives are left untouched because ``#include <hdr>``
    relies on the space + angle brackets being preserved verbatim by the
    compiler, and the space is canonical style for ``#define FOO``,
    ``#if defined(X)``, etc.
    """
    return line.lstrip().startswith("#")


def _split_at_line_comment(line: str) -> tuple[str, str]:
    """Split a line at the first ``//``, returning (code_part, comment_part).

    The comment part includes the ``//`` so it can be reattached
    verbatim. Returns ``(line, "")`` if no comment is present. Quoted
    sections are excluded by the caller via :func:`_has_string_literal`,
    so a naive search is safe here.

    Block comments (``/* ... */``) are not handled: they may span lines
    and can contain ``//`` inside string literals, so a line-local split
    would be unsafe without a fuller lexer.
    """
    idx = line.find("//")
    if idx < 0:
        return line, ""
    return line[:idx], line[idx:]


def _tighten_ident_open_paren(line: str) -> str:
    """Strip the space in ``ident (`` when ident is not a control keyword."""

    def replace(match: re.Match[str]) -> str:
        ident = match.group(1)
        if ident in _KEYWORDS_BEFORE_PAREN:
            return match.group(0)
        return f"{ident}("

    return _IDENT_OPEN_PAREN_RE.sub(replace, line)


def _tighten_ident_open_angle(line: str) -> str:
    """Strip the space in ``ident <`` for template names (skip ``template``)."""

    def replace(match: re.Match[str]) -> str:
        ident = match.group(1)
        if ident in _KEYWORDS_BEFORE_ANGLE:
            return match.group(0)
        return f"{ident}<"

    return _IDENT_OPEN_ANGLE_RE.sub(replace, line)


def normalize_code_line(line: str) -> str:
    """Tighten PDF-kerning artifact whitespace on a single code line.

    Operates on the line text (indented or not; leading whitespace is
    preserved). Returns the input unchanged for:

    * lines containing string/character literal delimiters (``"`` / ``'``),
    * preprocessor directives (``#include <hdr>`` must keep its space),
    * lines whose *code* portion (everything before the first ``//``)

    The literal check runs on the code portion only, so a quote that
    lives in a trailing comment (``vector <From> result; // don't``)
    no longer disables tightening of the code. This stays safe even
    when a ``//`` sits inside a string literal: the split leaves the
    opening quote in the code portion, so the literal check still trips
    and the line is returned untouched.

    All tightening rules then apply only to the pre-``//`` portion, so
    identifiers in trailing comments (``// also in <proxy>``) are never
    mistaken for template names.
    """
    if _is_preprocessor_directive(line):
        return line
    code, comment = _split_at_line_comment(line)
    if _has_string_literal(code):
        return line
    out = code
    out = _tighten_ident_open_angle(out)
    out = _SPACE_BEFORE_CLOSE_ANGLE_RE.sub(r"\1>", out)
    out = _DBL_COLON_SPACE_RE.sub(r"::\1", out)
    out = _ATTR_OPEN_RE.sub("[[", out)
    out = _ATTR_CLOSE_RE.sub("]]", out)
    out = _SPACE_BEFORE_COMMA_RE.sub(r"\1,", out)
    out = _tighten_ident_open_paren(out)
    return out + comment
