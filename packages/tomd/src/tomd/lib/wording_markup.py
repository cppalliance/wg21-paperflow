#
# Copyright (c) 2026 Dmitriy Chukhin (dmitriy@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Single source of truth for tomd wording-markup syntax.

Proposed standard-text edits are emitted as inline ``<ins>``/``<del>``
tags and nothing else. The emitters (``lib.pdf.wording_emit``,
``lib.html.render``), the scoring detector (``lib.pdf.qa``), and the
content checker (``lib.check_content``) all depend on this exact syntax.
Defining it once here, and deriving both the emitter format helper and
the checker strip rules from the same constants, makes them unable to
drift apart.

tomd no longer emits Pandoc fenced wording divs (``:::wording-add`` ...
``:::``): they duplicated what the inline tags already say and were pure
noise in the converted Markdown. The fence *recognizer* below survives
only so ``lib.check_content`` can normalize a ``<pid>.md`` produced by an
older tomd; nothing emits that syntax any more.

New wording emission must go through the helper here, not a fresh
literal: a hardcoded ``<ins>`` at a new call site is the one drift the
round-trip test (``tests/test_wording_markup.py``) cannot see.
"""

from __future__ import annotations

import re

# Inline edit tags.
WORDING_TAGS = ("ins", "del")

# Legacy fenced-div syntax, recognized but never emitted. ``WORDING_CLASSES``
# must equal the wording ``SectionKind`` values; ``test_wording_markup``
# asserts the enum agreement so the two cannot diverge silently.
LEGACY_FENCE_MARKER = ":::"
WORDING_CLASSES = ("wording", "wording-add", "wording-remove")


def wording_tag_open(tag: str, inner: str) -> str:
    """Inline edit tag wrapping ``inner``, e.g. ``<ins>x</ins>``."""
    return f"<{tag}>{inner}</{tag}>"


# -- Checker-side strip rules, derived from the SAME definitions --------------
# A legacy fence line is the marker plus an optional known class name, alone
# on a line. Anchoring + the closed class alternation keep it from matching
# code (``a ::: b``) or scope-resolution tokens. Retained for markdown written
# by an older tomd; current output never contains a fence.
_CLASS_ALT = "|".join(re.escape(c) for c in WORDING_CLASSES)
LEGACY_WORDING_FENCE_RE = re.compile(
    rf"^[ \t]*{re.escape(LEGACY_FENCE_MARKER)}(?:{_CLASS_ALT})?[ \t]*$",
    re.MULTILINE,
)
WORDING_TAG_RE = re.compile(
    rf"</?(?:{'|'.join(re.escape(t) for t in WORDING_TAGS)})\b[^>]*>",
    re.IGNORECASE,
)
