#
# Copyright (c) 2026 Dmitriy Chukhin (dmitriy@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Single source of truth for tomd wording-markup syntax.

Proposed standard-text edits are emitted as Pandoc fenced divs
(``:::wording-add`` ... ``:::``) and inline ``<ins>``/``<del>`` tags. The
emitters (``lib.pdf.emit``, ``lib.html.render``), the scoring detector
(``lib.pdf.qa``), and the content checker (``lib.check_content``) all depend
on this exact syntax. Defining it once here, and deriving both the emitter
format helpers and the checker strip rules from the same constants, makes
them unable to drift apart.

New wording emission must go through the helpers here, not a fresh literal:
a hardcoded ``:::``/``<ins>`` at a new call site is the one drift the
round-trip test (``tests/test_wording_markup.py``) cannot see.
"""

from __future__ import annotations

import re

# Fenced-div marker and the wording class names. ``WORDING_CLASSES`` must
# equal the ``SectionKind`` values ``lib.pdf.emit`` interpolates and the HTML
# class names ``lib.html.render`` recognizes; ``test_wording_markup`` asserts
# the enum agreement so the two cannot diverge silently.
FENCE_MARKER = ":::"
WORDING_CLASSES = ("wording", "wording-add", "wording-remove")

# Inline edit tags.
WORDING_TAGS = ("ins", "del")

# Closing fence is the bare marker.
WORDING_FENCE_CLOSE = FENCE_MARKER


def wording_fence_open(div_class: str) -> str:
    """Opening fence for a wording div, e.g. ``:::wording-add``."""
    return f"{FENCE_MARKER}{div_class}"


def wording_tag_open(tag: str, inner: str) -> str:
    """Inline edit tag wrapping ``inner``, e.g. ``<ins>x</ins>``."""
    return f"<{tag}>{inner}</{tag}>"


# -- Checker-side strip rules, derived from the SAME definitions --------------
# A fence line is the marker plus an optional known class name, alone on a
# line. Anchoring + the closed class alternation keep it from matching code
# (``a ::: b``) or scope-resolution tokens. Built from WORDING_CLASSES so a new
# class is covered automatically and a syntax change is caught by the
# round-trip test, not silently missed.
_CLASS_ALT = "|".join(re.escape(c) for c in WORDING_CLASSES)
WORDING_FENCE_RE = re.compile(
    rf"^[ \t]*{re.escape(FENCE_MARKER)}(?:{_CLASS_ALT})?[ \t]*$",
    re.MULTILINE,
)
WORDING_TAG_RE = re.compile(
    rf"</?(?:{'|'.join(re.escape(t) for t in WORDING_TAGS)})\b[^>]*>",
    re.IGNORECASE,
)
