"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

import re

# An ATX heading opener at column 0: one to six "#" then whitespace or nothing.
# A body block that starts this way is read by every Markdown parser as a
# heading, so a preprocessor directive quoted in prose (P3556R0 quotes the
# [cpp.include] grammar as `# include ... new-line causes the replacement of
# that directive by ...`) silently becomes an H1 (#302).
_LEADING_ATX_RE = re.compile(r"^(#{1,6})(\s|$)")

_ITALIC_INLINE_ESCAPE_RE = re.compile(r"([\\*_`])")
# Leading characters that would otherwise be parsed as a list marker,
# blockquote, ATX heading, or ordered-list start. The synthesised
# sub-caption paragraph (text == "*...*") would be misclassified if any
# of these appears at column 0 inside the italics wrapper.
_LEADING_BLOCK_CHARS = ("-", "*", "+", ">", "#")
_LEADING_ORDERED_RE = re.compile(r"^(\d+)\.")


def escape_leading_atx(text: str) -> str:
    """Backslash-escape a "#" that would turn a body block into a heading.

    The text is unchanged for readers; only Markdown's block parser is
    affected. Text already backslash-escaped upstream (the sub-caption path in
    ``escape_italic_wrapper``) does not match and is left alone. Shared by
    the paragraph and wording-prose renderers, the two emit paths that flatten
    lines into a single body block.
    """
    return _LEADING_ATX_RE.sub(r"\\\1\2", text)


def escape_italic_wrapper(text: str) -> str:
    """Escape characters that would break a ``*...*`` italic wrapper.

    Used by the caption and sub-caption rendering paths (emitted as
    ``*<escaped>*``). Escapes:

    - ``\\`` so a trailing backslash doesn't eat the closing ``*``.
    - ``*``, ``_``, and backticks so they don't terminate the wrapper
      or open a code span.
    - A leading list/quote/heading character so the paragraph doesn't
      render as a list item, blockquote, or heading once the italics
      wrapper is in place.
    """
    escaped = _ITALIC_INLINE_ESCAPE_RE.sub(r"\\\1", text)
    if not escaped:
        return escaped
    if escaped[0] in _LEADING_BLOCK_CHARS:
        # The first character has already been backslash-escaped if it
        # was ``*``; the other leading-block characters need their own
        # leading backslash.
        if escaped[0] != "\\":
            escaped = "\\" + escaped
    else:
        m = _LEADING_ORDERED_RE.match(escaped)
        if m:
            escaped = escaped[: m.end() - 1] + "\\." + escaped[m.end() :]
    return escaped


def escape_pipe_in_cell(text: str) -> str:
    """Escape literal pipe characters inside a GFM pipe-table cell."""
    return text.replace("|", "\\|")


def escape_wording_angle_brackets(text: str) -> str:
    """HTML-escape literal (non-tag, non-backtick) text in a wording line.

    Wording lines render where ``<ins>`` / ``<del>`` are real HTML tags, so
    the surrounding content sits in an HTML context. A literal ``<`` / ``>``
    in the code (the ``<float>`` in ``vec<float>``) is otherwise parsed as a
    stray HTML tag and silently dropped by the renderer. Escaping makes those
    angle brackets render literally. Backtick code spans are left untouched:
    the Markdown renderer already escapes their contents, and escaping them
    here would surface the raw entities. The ``<ins>`` / ``<del>`` tags
    themselves are emitted around the escaped text, never through this helper.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
