#
# Copyright (c) 2026 Dmitriy Chukhin (dmitriy@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Round-trip guard: the checker strip rules must match the emitter output.

This is the automated link between the wording-markup *producer* (the
format helper the emitters call) and the *consumer* (the checker strip
regexes). Both are derived from the same constants in ``lib.wording_markup``;
this test asserts they agree, so a future format change that updates one
without the other fails CI instead of silently re-depressing wording-paper
coverage scores.

The fenced-div cases cover a syntax tomd no longer emits: they pin the
recognizer ``lib.check_content`` needs for markdown an older tomd wrote.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tomd.lib.pdf.types import SectionKind
from tomd.lib.wording_markup import (
    LEGACY_FENCE_MARKER,
    LEGACY_WORDING_FENCE_RE,
    WORDING_CLASSES,
    WORDING_TAG_RE,
    WORDING_TAGS,
    wording_tag_open,
)


@pytest.mark.parametrize("div_class", WORDING_CLASSES)
def test_legacy_fence_regex_matches_open(div_class):
    # tomd no longer emits fenced wording divs, but check_content still
    # normalizes markdown an older tomd wrote, so the recognizer must keep
    # matching every opening fence that syntax ever produced.
    fence = f"{LEGACY_FENCE_MARKER}{div_class}"
    assert LEGACY_WORDING_FENCE_RE.match(fence) is not None


def test_legacy_fence_regex_matches_close():
    assert LEGACY_WORDING_FENCE_RE.match(LEGACY_FENCE_MARKER) is not None


@pytest.mark.parametrize("tag", WORDING_TAGS)
def test_tag_regex_matches_emitter_tag(tag):
    emitted = wording_tag_open(tag, "x")
    assert WORDING_TAG_RE.search(emitted) is not None
    # Only the tags are removed; the inner prose is preserved.
    assert WORDING_TAG_RE.sub(" ", emitted).strip() == "x"


def test_wording_classes_match_section_kind():
    # WORDING_CLASSES must equal the SectionKind values the PDF emitter
    # interpolates (emit.py uses sec.kind.value). Keeps the shared vocabulary
    # from drifting away from the enum.
    section_kind_wording = {
        kind.value for kind in SectionKind if kind.value.startswith("wording")
    }
    assert section_kind_wording == set(WORDING_CLASSES)
