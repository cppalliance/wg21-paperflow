#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

import pytest
from whisker.det.anchors import (
    AnchorPattern,
    AnchorSpec,
    anchor_spec_from_dict,
    check_anchors,
)

_MD = """---
title: "A Paper"
document: P3100R6
---

## Abstract

This proposes P3100R0 for LEWG review.

## Proposal

Body text here.
"""


def test_must_contain_pass_and_fail():
    spec = AnchorSpec(pid="P1", surface="raw", must_contain=("P3100R0", "LEWG"))
    assert check_anchors(_MD, spec).passed
    bad = AnchorSpec(pid="P1", surface="raw", must_contain=("ABSENT_PHRASE",))
    rep = check_anchors(_MD, bad)
    assert rep.failed
    assert "ABSENT_PHRASE" in rep.failures()[0].detail


def test_must_not_contain():
    spec = AnchorSpec(pid="P1", surface="raw", must_not_contain=("Page 1 of",))
    assert check_anchors(_MD, spec).passed
    bad = AnchorSpec(pid="P1", surface="raw", must_not_contain=("Abstract",))
    assert check_anchors(_MD, bad).failed


def test_ordered_chain_monotonic():
    spec = AnchorSpec(pid="P1", surface="raw", ordered=("## Abstract", "## Proposal"))
    assert check_anchors(_MD, spec).passed
    # reversed order must fail
    rev = AnchorSpec(pid="P1", surface="raw", ordered=("## Proposal", "## Abstract"))
    assert check_anchors(_MD, rev).failed


def test_ordered_missing_anchor_fails():
    spec = AnchorSpec(pid="P1", surface="raw", ordered=("## Abstract", "## Nope"))
    rep = check_anchors(_MD, spec)
    assert rep.failed
    assert any("missing ordered anchor" in c.detail for c in rep.failures())


def test_normalized_surface_strips_markup():
    # On the normalized surface, "##" and punctuation vanish; bare content tokens
    # still match.
    spec = AnchorSpec(pid="P1", surface="normalized", must_contain=("Abstract", "LEWG"))
    assert check_anchors(_MD, spec).passed
    # raw markdown markup is NOT present on the normalized surface.
    spec2 = AnchorSpec(pid="P1", surface="normalized", must_contain=("## Abstract",))
    assert check_anchors(_MD, spec2).failed


def test_pattern_match():
    spec = AnchorSpec(
        pid="P1", surface="raw",
        patterns=(AnchorPattern(id="doc", regex=r"^document:\s*P3100R6\s*$", flags="MULTILINE"),),
    )
    assert check_anchors(_MD, spec).passed
    bad = AnchorSpec(
        pid="P1", surface="raw",
        patterns=(AnchorPattern(id="doc", regex=r"^document:\s*P9999R9\s*$", flags="M"),),
    )
    assert check_anchors(_MD, bad).failed


def test_conjunctive_all_must_pass():
    spec = AnchorSpec(
        pid="P1", surface="raw",
        must_contain=("P3100R0",),
        must_not_contain=("forbidden",),
    )
    rep = check_anchors(_MD, spec)
    assert rep.passed
    assert len(rep.checks) == 2


# -- spec loading / validation -----------------------------------------------


def test_anchor_spec_from_dict_roundtrip():
    data = {
        "kind": "whisker-anchors",
        "surface": "normalized",
        "must_contain": ["LEWG"],
        "ordered": ["Abstract", "Proposal"],
        "patterns": [{"id": "x", "regex": "P3100", "flags": "I"}],
    }
    spec = anchor_spec_from_dict(data, "P3100R6")
    assert spec.pid == "P3100R6"
    assert spec.surface == "normalized"
    assert spec.must_contain == ("LEWG",)
    assert spec.patterns[0].id == "x"


def test_wrong_kind_raises():
    with pytest.raises(ValueError):
        anchor_spec_from_dict({"kind": "something-else"}, "P1")


def test_unknown_key_raises():
    with pytest.raises(ValueError):
        anchor_spec_from_dict({"must_includ": ["typo"]}, "P1")


def test_bad_surface_raises():
    with pytest.raises(ValueError):
        anchor_spec_from_dict({"surface": "binary"}, "P1")


def test_bad_flag_raises():
    with pytest.raises(ValueError):
        anchor_spec_from_dict({"patterns": [{"regex": "x", "flags": "BOGUS"}]}, "P1")


def test_invalid_regex_raises():
    with pytest.raises(ValueError):
        anchor_spec_from_dict({"patterns": [{"regex": "([unclosed"}]}, "P1")


def test_must_contain_must_be_list_of_strings():
    with pytest.raises(ValueError):
        anchor_spec_from_dict({"must_contain": "notalist"}, "P1")
