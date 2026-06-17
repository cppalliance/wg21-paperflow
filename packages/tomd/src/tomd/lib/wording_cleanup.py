#
# Copyright (c) 2026 Luan Fonseca (luan@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Post-render cleanup for Pandoc fenced wording divs.

This module runs against the **assembled Markdown**, not against any
PDF- or HTML-internal representation. Both the PDF emitter (``lib/pdf/
emit.py``) and the HTML renderer (``lib/html/render.py``) produce the
same Pandoc shape:

    :::wording-add

    <ins>added clause</ins> existing context <ins>more added</ins>

    :::

When the section is overwhelmingly its declared role, the inline
``<ins>`` / ``<del>`` tags duplicate the div-level signal and become
noise. This pass strips the redundant tags while preserving contrarian
tags (a ``<del>`` inside a ``:::wording-add`` block marks an intra-
block edit and must survive).

Code promotion (turning a multi-line monospace-dominant wording
section into a fenced ``cpp`` block inside the div) lives in the PDF
emitter because it needs span-level structure that the rendered
Markdown has already collapsed. This module never touches code-
promoted divs: they contain no inline role tags and trip the
"no role chars" early return.
"""

from __future__ import annotations

import re

from .wording_policy import UNIFORM_ROLE_THRESHOLD, implicit_role_for

_WORDING_OPEN_RE = re.compile(
    r":::(wording(?:-add|-remove)?)[ \t]*$",
)
_WORDING_CLOSE = ":::"

# Non-greedy across lines so multi-line tag spans match correctly,
# while not accidentally swallowing an unrelated downstream tag of the
# same kind.
_INS_RE = re.compile(r"<ins>(.*?)</ins>", re.DOTALL)
_DEL_RE = re.compile(r"<del>(.*?)</del>", re.DOTALL)
_ANY_ROLE_TAG_RE = re.compile(r"</?(?:ins|del)>")
_WHITESPACE_RE = re.compile(r"\s")


def clean_wording_blocks(md: str) -> str:
    """Strip redundant inline role tags inside uniform-role wording divs.

    Idempotent: running this on already-clean output is a no-op.
    Neutral ``:::wording`` divs are never modified (they exist exactly
    to carry mixed ``<ins>`` / ``<del>`` diffs).
    """
    out: list[str] = []
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        m = _WORDING_OPEN_RE.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        close = _find_close(lines, i + 1)
        if close is None:
            # Unclosed div; leave the rest of the document untouched.
            out.extend(lines[i:])
            break
        div_class = m.group(1)
        inner = lines[i + 1:close]
        cleaned = _strip_redundant_tags(div_class, inner)
        out.append(lines[i])
        out.extend(cleaned)
        out.append(lines[close])
        i = close + 1
    return "\n".join(out)


def _find_close(lines: list[str], start: int) -> int | None:
    """Return the index of the next bare ``:::`` line, or ``None``.

    Skips over any nested fenced code blocks so a ``:::`` line buried
    inside a ``` block (theoretically possible, currently never emitted
    by tomd) is not mistaken for the div terminator.
    """
    in_code_fence = False
    for j in range(start, len(lines)):
        stripped = lines[j].strip()
        if stripped.startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if not in_code_fence and stripped == _WORDING_CLOSE:
            return j
    return None


def _strip_redundant_tags(div_class: str, inner_lines: list[str]) -> list[str]:
    implicit = implicit_role_for(div_class)
    if implicit is None:
        return inner_lines

    inner = "\n".join(inner_lines)
    matching_re = _INS_RE if implicit == "ins" else _DEL_RE

    # Numerator: visible non-whitespace chars inside the matching role
    # tag. Denominator: visible non-whitespace chars after stripping
    # both kinds of role wrappers (what the reader actually sees).
    tag_chars = sum(
        len(_WHITESPACE_RE.sub("", m.group(1)))
        for m in matching_re.finditer(inner)
    )
    visible = _ANY_ROLE_TAG_RE.sub("", inner)
    total_chars = len(_WHITESPACE_RE.sub("", visible))

    if total_chars == 0:
        return inner_lines
    if tag_chars / total_chars < UNIFORM_ROLE_THRESHOLD:
        return inner_lines

    stripped = matching_re.sub(lambda m: m.group(1), inner)
    return stripped.split("\n")
