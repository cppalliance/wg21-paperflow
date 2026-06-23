#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from types import SimpleNamespace

from tomd.lib.check_content import MisalignedRegion

from whisker.constants import REGION_DETAIL_CAP
from whisker.score import (
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_REVIEW,
    score_markdown,
)

_CLEAN_MD = """---
title: "A Paper"
document: P1234R0
---

## Introduction

This is a faithful paragraph of prose that the source also contains.

## Design

More prose describing the design in plain words.
"""


def _make_regions(count, side, *, page=7):
    """Build synthetic MisalignedRegion objects for testing."""
    return tuple(
        MisalignedRegion(
            side=side, token_start=i * 100, token_end=i * 100 + 50,
            sample=f"sample text at {i}", page=page,
        )
        for i in range(count)
    )


def _content(
    coverage, *, unigram=None, drift=0.0, unigram_drift=None,
    missing=0, extra=0, fmt="pdf",
    missing_regions=None, extra_regions=None,
):
    # unigram_coverage is the content gate; it defaults to the shingle coverage
    # but can be set independently to model reflow (low shingle, high unigram).
    # Likewise unigram_drift (order-invariant, the soft signal) defaults to the
    # shingle drift but can be set apart to model a faithful reflow whose only
    # divergence is order (high shingle drift, zero unigram drift).
    if missing_regions is None:
        missing_regions = _make_regions(missing, "source")
    if extra_regions is None:
        extra_regions = _make_regions(extra, "markdown")
    return SimpleNamespace(
        source_format=fmt,
        coverage=coverage,
        drift=drift,
        unigram_coverage=coverage if unigram is None else unigram,
        unigram_drift=drift if unigram_drift is None else unigram_drift,
        missing_regions=missing_regions,
        extra_regions=extra_regions,
    )


def test_clean_high_coverage_passes():
    r = score_markdown("P1234R0", _CLEAN_MD, content=_content(0.98))
    assert r.verdict == VERDICT_PASS
    assert not r.hard_flags and not r.soft_flags


def test_mid_coverage_is_review():
    r = score_markdown("P1234R0", _CLEAN_MD, content=_content(0.90))
    assert r.verdict == VERDICT_REVIEW
    assert any("coverage" in f for f in r.soft_flags)


def test_low_coverage_is_fail():
    r = score_markdown("P1234R0", _CLEAN_MD, content=_content(0.50))
    assert r.verdict == VERDICT_FAIL
    assert any("coverage" in f for f in r.hard_flags)


def test_reflow_high_unigram_low_shingle_not_fail():
    # The P4047R0 case: tomd correctly reflowed multi-column text, so the
    # order-sensitive shingle coverage is low (0.66) but the words are present
    # (unigram 0.95). Reading order must not gate content: this is a clean pass,
    # and no flag may mention the shingle coverage.
    r = score_markdown("P1234R0", _CLEAN_MD, content=_content(0.66, unigram=0.95))
    assert r.verdict == VERDICT_PASS
    assert not r.hard_flags and not r.soft_flags


def test_low_unigram_is_hard_fail():
    # Genuinely missing words (low unigram) hard-fails even if the shingle
    # coverage is identical to the reflow case above.
    r = score_markdown("P1234R0", _CLEAN_MD, content=_content(0.66, unigram=0.70))
    assert r.verdict == VERDICT_FAIL
    assert any("unigram coverage" in f for f in r.hard_flags)


def test_mid_unigram_is_soft_review():
    # Some words missing (unigram in the 0.85-0.95 band) is a review, not a fail.
    r = score_markdown("P1234R0", _CLEAN_MD, content=_content(0.66, unigram=0.90))
    assert r.verdict == VERDICT_REVIEW
    assert any("unigram coverage" in f for f in r.soft_flags)
    assert not r.hard_flags


def test_many_regions_is_soft_review_not_fail():
    r = score_markdown("P1234R0", _CLEAN_MD, content=_content(0.98, missing=2, extra=2))
    assert r.verdict == VERDICT_REVIEW
    assert any("region" in f for f in r.soft_flags)
    assert not r.hard_flags


def test_unigram_drift_is_soft_review():
    # Order-invariant drift (injected/extra tokens) above the edge is a review.
    r = score_markdown(
        "P1234R0", _CLEAN_MD, content=_content(0.98, drift=0.0, unigram_drift=0.25)
    )
    assert r.verdict == VERDICT_REVIEW
    assert any("unigram drift" in f for f in r.soft_flags)


def test_shingle_drift_alone_is_not_review():
    # A faithful reflow: the order-sensitive shingle drift is high (0.25) but the
    # order-invariant unigram drift is zero. Reading order must not gate content,
    # so this is a clean pass and no flag may mention drift.
    r = score_markdown(
        "P1234R0", _CLEAN_MD, content=_content(0.98, drift=0.25, unigram_drift=0.0)
    )
    assert r.verdict == VERDICT_PASS
    assert not r.hard_flags and not r.soft_flags


def test_broken_structure_forces_fail_despite_coverage():
    broken = "no front matter at all\n\n## A\n\n#### skip\n"
    r = score_markdown("P1234R0", broken, content=_content(0.99))
    assert r.verdict == VERDICT_FAIL
    assert any(f.startswith("gate:") for f in r.hard_flags)


def test_to_dict_is_serializable_and_sorted():
    r = score_markdown("P1234R0", _CLEAN_MD, content=_content(0.90, drift=0.25))
    d = r.to_dict()
    assert d["soft_flags"] == sorted(d["soft_flags"])
    assert d["verdict"] == VERDICT_REVIEW
    assert d["schema_version"] == 1


# -- reference-oracle agreement (ADVISORY overlay) --------------------------
#
# The reference signal NEVER hard-fails. The trustworthy reference-free path
# (structural gates + coverage floor) is the only gate; low cross-converter text
# agreement is layered on as an advisory review flag, and teds/mhs never flag.

# nid ~0.22 after clean_string: text shares almost nothing -> well below 0.85.
_DIVERGENT_REF = "## Totally\n\nDifferent alien words sharing nothing alike zzz qqq.\n" * 3


def test_reference_identical_adds_no_advisory_flag():
    # Identical reference -> nid 1.0 -> no advisory flag. With good coverage the
    # paper passes clean: the reference rode along without changing the verdict.
    r = score_markdown(
        "P1234R0", _CLEAN_MD, content=_content(0.98),
        reference_md=_CLEAN_MD, ref_engine="markitdown",
    )
    assert r.verdict == VERDICT_PASS
    assert r.ref_nid == 1.0
    assert r.ref_engine == "markitdown"
    assert not r.hard_flags and not r.soft_flags


def test_reference_low_text_agreement_is_advisory_review_never_fail():
    # Very divergent reference (nid well below the advisory edge) with otherwise
    # healthy content: the verdict is REVIEW, driven by an advisory soft flag.
    # It must NEVER hard-fail on the reference signal.
    r = score_markdown(
        "P1234R0", _CLEAN_MD, content=_content(0.98),
        reference_md=_DIVERGENT_REF, ref_engine="markitdown",
    )
    assert r.verdict == VERDICT_REVIEW
    assert r.ref_nid < 0.85
    assert any("reference text agreement" in f and "advisory" in f for f in r.soft_flags)
    assert not r.hard_flags


def test_reference_weak_table_heading_axes_never_flag():
    # The reference adds a table the candidate lacks: teds collapses. teds/mhs
    # are report-only, so no flag may mention them; only the text axis (nid) may
    # raise the advisory flag.
    ref = _CLEAN_MD + "\n| a | b |\n| --- | --- |\n| 1 | 2 |\n"
    r = score_markdown(
        "P1234R0", _CLEAN_MD, content=_content(0.98),
        reference_md=ref, ref_engine="markitdown",
    )
    assert r.ref_teds < 0.8  # the table axis genuinely dipped...
    flags = r.hard_flags + r.soft_flags
    assert not any("teds" in f or "mhs" in f for f in flags)  # ...but never flagged


def test_coverage_still_hard_fails_with_reference_on():
    # Reference present and agreeing (identical -> nid 1.0) does NOT rescue a
    # paper with genuinely missing content: coverage below the floor is the
    # trustworthy hard gate regardless of the oracle.
    r = score_markdown(
        "P1234R0", _CLEAN_MD, content=_content(0.50),
        reference_md=_CLEAN_MD, ref_engine="markitdown",
    )
    assert r.verdict == VERDICT_FAIL
    assert any("coverage" in f for f in r.hard_flags)


def test_reference_does_not_mask_structural_gate():
    # A broken candidate still hard-fails on the gate even if the reference
    # (here equally broken) agrees: structural gates stay hard under reference.
    broken = "no front matter at all\n\n## A\n\n#### skip\n"
    r = score_markdown(
        "P1234R0", broken, content=_content(0.99),
        reference_md=broken, ref_engine="markitdown",
    )
    assert r.verdict == VERDICT_FAIL
    assert any(f.startswith("gate:") for f in r.hard_flags)


def test_reference_formatting_only_difference_scores_high_nid():
    # clean_string normalization: the candidate carries front-matter + markdown
    # headings; the reference is the same body words as plain text. The body
    # dominates, so content agreement lands comfortably above the advisory edge
    # (only the small front-matter delta survives), giving a clean pass.
    plain_ref = (
        "A Paper\n"
        "P1234R0\n\n"
        "Introduction\n\n"
        "This is a faithful paragraph of prose that the source also contains.\n\n"
        "Design\n\n"
        "More prose describing the design in plain words.\n"
    )
    r = score_markdown(
        "P1234R0", _CLEAN_MD, content=_content(0.98),
        reference_md=plain_ref, ref_engine="markitdown",
    )
    assert r.ref_nid >= 0.85
    assert r.verdict == VERDICT_PASS
    assert not r.hard_flags and not r.soft_flags


def test_no_reference_leaves_ref_fields_none():
    r = score_markdown("P1234R0", _CLEAN_MD, content=_content(0.98))
    assert r.ref_overall is None and r.ref_engine is None
    d = r.to_dict()
    assert d["ref_overall"] is None and d["ref_nid"] is None and d["ref_engine"] is None


# -- region detail (content-level WHERE) ------------------------------------

def test_to_dict_carries_region_detail_with_expected_keys():
    r = score_markdown("P1234R0", _CLEAN_MD, content=_content(0.98, missing=2, extra=1))
    d = r.to_dict()
    assert len(d["missing_regions"]) == 2
    assert len(d["extra_regions"]) == 1
    for reg in d["missing_regions"] + d["extra_regions"]:
        assert set(reg.keys()) == {"page", "token_start", "token_end", "sample"}
        assert "side" not in reg


def test_region_detail_cap_is_enforced():
    many = _make_regions(REGION_DETAIL_CAP + 3, "source")
    r = score_markdown(
        "P1234R0", _CLEAN_MD,
        content=_content(0.98, missing_regions=many),
    )
    assert len(r.missing_regions) == REGION_DETAIL_CAP


def test_region_detail_sorted_by_token_start():
    unsorted = (
        MisalignedRegion(side="source", token_start=300, token_end=350, sample="c", page=3),
        MisalignedRegion(side="source", token_start=100, token_end=150, sample="a", page=1),
        MisalignedRegion(side="source", token_start=200, token_end=250, sample="b", page=2),
    )
    r = score_markdown(
        "P1234R0", _CLEAN_MD,
        content=_content(0.98, missing_regions=unsorted),
    )
    starts = [reg["token_start"] for reg in r.missing_regions]
    assert starts == sorted(starts)


def test_region_detail_empty_when_no_regions():
    r = score_markdown("P1234R0", _CLEAN_MD, content=_content(0.98))
    assert r.missing_regions == []
    assert r.extra_regions == []
    d = r.to_dict()
    assert d["missing_regions"] == [] and d["extra_regions"] == []
