#
# Copyright (c) 2026 Luan Fonseca (luan@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Redundant-tag cleanup for a rendered wording section.

When a section is overwhelmingly one role, its inline ``<ins>`` /
``<del>`` tags say nothing the section's own role does not, and they
bury the prose in markup. :func:`strip_redundant_tags` removes them
while preserving contrarian tags (a ``<del>`` inside an otherwise
inserted block marks an intra-block edit and must survive).

Both the PDF emitter (``lib/pdf/wording_emit.py``) and the HTML renderer
(``lib/html/render.py``) call this on the text they have just rendered,
passing the section's wording class. It used to run instead as a pass
over the assembled Markdown, keyed on the ``:::wording-add`` fences the
emitters wrapped each section in; those fences are no longer emitted, so
the role is handed in directly rather than parsed back out. The
character-ratio policy is unchanged.

Code-shaped sections are unaffected, exactly as before. A uniform-role
fenced block carries no inline role tags and trips the "no role chars"
early return; a mixed fenced diff is rendered as a neutral ``wording``
section and trips the ``implicit is None`` early return, so its
``<ins>`` / ``<del>`` markers stay literal inside the fence.
"""

from __future__ import annotations

import re

from .wording_policy import UNIFORM_ROLE_THRESHOLD, implicit_role_for

# Non-greedy across lines so multi-line tag spans match correctly,
# while not accidentally swallowing an unrelated downstream tag of the
# same kind.
_INS_RE = re.compile(r"<ins>(.*?)</ins>", re.DOTALL)
_DEL_RE = re.compile(r"<del>(.*?)</del>", re.DOTALL)
_ANY_ROLE_TAG_RE = re.compile(r"</?(?:ins|del)>")
_WHITESPACE_RE = re.compile(r"\s")


def strip_redundant_tags(div_class: str, text: str) -> str:
    """Strip inline role tags that a uniform-role wording section repeats.

    ``div_class`` is the section's wording class (``wording-add``,
    ``wording-remove``, or the neutral ``wording``); ``text`` is the
    already-rendered Markdown for that one section.

    Idempotent: running this on already-clean output is a no-op. Neutral
    sections are never modified (they exist exactly to carry mixed
    ``<ins>`` / ``<del>`` diffs).
    """
    implicit = implicit_role_for(div_class)
    if implicit is None:
        return text

    matching_re = _INS_RE if implicit == "ins" else _DEL_RE

    # Numerator: visible non-whitespace chars inside the matching role
    # tag. Denominator: visible non-whitespace chars after stripping
    # both kinds of role wrappers (what the reader actually sees).
    tag_chars = sum(
        len(_WHITESPACE_RE.sub("", m.group(1)))
        for m in matching_re.finditer(text)
    )
    visible = _ANY_ROLE_TAG_RE.sub("", text)
    total_chars = len(_WHITESPACE_RE.sub("", visible))

    if total_chars == 0:
        return text
    if tag_chars / total_chars < UNIFORM_ROLE_THRESHOLD:
        return text

    return matching_re.sub(lambda m: m.group(1), text)
