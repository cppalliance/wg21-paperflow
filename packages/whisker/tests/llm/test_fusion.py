#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for deterministic + LLM fusion (llm/fusion.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from whisker.det.score import VERDICT_FAIL, VERDICT_PASS, VERDICT_REVIEW
from whisker.llm.chunking import aggregate_adjudications
from whisker.llm.constants import (
    FUSION_RULE_AGREE,
    FUSION_RULE_CLEAR_BLOCKED_IDEAL_FLAG,
    FUSION_RULE_CLEAR_BLOCKED_MISSING_REGION,
    FUSION_RULE_IDEAL_REVIEW_CAP,
    FUSION_RULE_LLM_CLEAR_SOFT_REVIEW,
    FUSION_RULE_LLM_ESCALATE_MAJOR,
    FUSION_RULE_LLM_RESCUE_HEADING,
    FUSION_RULE_LLM_REVIEW_CAP,
    FUSION_RULE_SOURCE_AWARE_REVIEW_CAP,
    FUSION_RULE_WHISKER_FAIL_LOCKED,
    FUSION_RULE_WHISKER_ONLY,
    MAX_IDEAL_DISCREPANCIES,
)
from whisker.llm.fusion import fuse_verdicts
from whisker.llm.fusion_report import (
    build_merged_json,
    render_merged_report_md,
    render_terminal_fusion_footer,
    render_terminal_fusion_line,
)
from whisker.llm.inspect_report import format_report
from whisker.llm.models import Adjudication, AxisFinding

_INVALID_PID_VALUES = (None, [], 7)
_INVALID_CONFIDENCE_VALUES = ("bad", float("nan"), float("inf"), [])
_INVALID_FINGERPRINT_VALUES = (None, [], "bad", 7)


def _whisker(
    verdict: str,
    *,
    soft: list[str] | None = None,
    hard: list[str] | None = None,
    ref_nid: float | None = 0.5,
    pid: str = "P0000",
    missing_region_count: int | None = None,
) -> dict:
    d: dict = {
        "pid": pid,
        "verdict": verdict,
        "soft_flags": soft or [],
        "hard_flags": hard or [],
    }
    if ref_nid is not None:
        d["ref_nid"] = ref_nid
    if missing_region_count is not None:
        d["missing_region_count"] = missing_region_count
    return d


def _tapetum(
    verdict: str,
    *,
    conf: float = 0.95,
    axis_findings: list[dict] | None = None,
    status: str = "ok",
    ideal_verification: dict | None = None,
) -> dict:
    result = {
        "pid": "P0000",
        "status": status,
        "suggested_verdict": verdict,
        "confidence": conf,
        "axis_findings": axis_findings or [],
    }
    if ideal_verification is not None:
        result["ideal_verification"] = ideal_verification
    return result


class TestFusionMatrix:
    """3x3 base cells plus asymmetric rescue/escalate/clear rules."""

    def test_absent_tapetum_whisker_only(self):
        r = fuse_verdicts(_whisker(VERDICT_REVIEW, soft=["x"]), None)
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_WHISKER_ONLY
        assert r.tapetum_available is False

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            *(("pid", value) for value in _INVALID_PID_VALUES),
            ("suggested_verdict", []),
            *(("confidence", value) for value in _INVALID_CONFIDENCE_VALUES),
        ],
    )
    def test_direct_fusion_treats_invalid_tapetum_as_unavailable(
        self, field, value
    ):
        tapetum = _tapetum(VERDICT_PASS)
        tapetum[field] = value

        result = fuse_verdicts(_whisker(VERDICT_PASS), tapetum)

        assert result.combined_verdict == VERDICT_PASS
        assert result.combined_rule == FUSION_RULE_WHISKER_ONLY
        assert result.tapetum_available is False
        assert result.tapetum_confidence == 0.0

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            *(("pid", value) for value in _INVALID_PID_VALUES),
            ("verdict", []),
        ],
    )
    def test_direct_fusion_uses_stub_for_invalid_whisker(self, field, value):
        whisker = _whisker(VERDICT_PASS)
        whisker[field] = value

        result = fuse_verdicts(whisker, _tapetum(VERDICT_PASS))

        assert result.whisker_verdict == "?"
        assert result.combined_verdict == "?"

    @pytest.mark.parametrize("fingerprint", _INVALID_FINGERPRINT_VALUES)
    def test_direct_fusion_ignores_malformed_tapetum_fingerprint(
        self, fingerprint
    ):
        tapetum = _tapetum(VERDICT_PASS)
        tapetum["fingerprint"] = fingerprint

        result = fuse_verdicts(_whisker(VERDICT_PASS), tapetum)

        assert result.tapetum_available is True
        assert result.combined_verdict == VERDICT_PASS

    def test_direct_fusion_accepts_finite_numeric_confidence_string(self):
        tapetum = _tapetum(VERDICT_PASS)
        tapetum["confidence"] = "0.9"

        result = fuse_verdicts(_whisker(VERDICT_PASS), tapetum)

        assert result.tapetum_available is True
        assert result.tapetum_confidence == 0.9

    def test_error_stub_whisker_only(self):
        r = fuse_verdicts(
            _whisker(VERDICT_PASS),
            _tapetum(VERDICT_REVIEW, status="error", conf=0.0),
        )
        assert r.combined_verdict == VERDICT_PASS
        assert r.combined_rule == FUSION_RULE_WHISKER_ONLY
        assert r.tapetum_available is False

    def test_confidence_zero_stub_whisker_only(self):
        r = fuse_verdicts(
            _whisker(VERDICT_REVIEW),
            {"suggested_verdict": VERDICT_REVIEW, "confidence": 0.0},
        )
        assert r.combined_rule == FUSION_RULE_WHISKER_ONLY
        assert r.tapetum_available is False

    def test_fail_locked_non_heading(self):
        r = fuse_verdicts(
            _whisker(VERDICT_FAIL, hard=["gate:non_empty"]),
            _tapetum(VERDICT_PASS),
        )
        assert r.combined_verdict == VERDICT_FAIL
        assert r.combined_rule == FUSION_RULE_WHISKER_FAIL_LOCKED

    def test_rescue_heading_only_fail(self):
        r = fuse_verdicts(
            _whisker(
                VERDICT_FAIL,
                hard=["gate:heading_monotone:heading level jumps H1 -> H3"],
                pid="N5035",
            ),
            _tapetum(VERDICT_REVIEW),
        )
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_LLM_RESCUE_HEADING
        assert r.combined_verdict != VERDICT_PASS

    def test_rescue_never_upgrades_to_pass(self):
        r = fuse_verdicts(
            _whisker(VERDICT_FAIL, hard=["gate:heading_monotone:H2 -> H4"]),
            _tapetum(VERDICT_PASS),
        )
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_LLM_RESCUE_HEADING

    def test_toc_leak_fail_is_not_rescued(self):
        # PR #290 replay: the no_toc_leak detail contains the word "heading";
        # a substring match would wrongly qualify this fail for the rescue
        # path. It must stay locked.
        r = fuse_verdicts(
            _whisker(
                VERDICT_FAIL,
                hard=[
                    "gate:no_toc_leak:duplicate heading '1. introduction' "
                    "previously seen as '1. introduction 3' (TOC leak)"
                ],
            ),
            _tapetum(VERDICT_REVIEW),
        )
        assert r.combined_verdict == VERDICT_FAIL
        assert r.combined_rule == FUSION_RULE_WHISKER_FAIL_LOCKED

    def test_clear_soft_review(self):
        r = fuse_verdicts(
            _whisker(VERDICT_REVIEW, soft=["9 misaligned region(s)"], ref_nid=0.92),
            _tapetum(VERDICT_PASS),
        )
        assert r.combined_verdict == VERDICT_PASS
        assert r.combined_rule == FUSION_RULE_LLM_CLEAR_SOFT_REVIEW

    def test_clear_guardrail_ref_nid(self):
        r = fuse_verdicts(
            _whisker(VERDICT_REVIEW, soft=["misaligned"], ref_nid=0.05),
            _tapetum(VERDICT_PASS),
        )
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule != FUSION_RULE_LLM_CLEAR_SOFT_REVIEW

    def test_clear_blocked_with_axis_fail(self):
        """Clear is blocked when the LLM has any axis fail, regardless of confidence."""
        r = fuse_verdicts(
            _whisker(VERDICT_REVIEW, soft=["misaligned"], ref_nid=0.92),
            _tapetum(
                VERDICT_PASS,
                conf=0.95,
                axis_findings=[
                    {
                        "axis": "tables",
                        "verdict": VERDICT_FAIL,
                        "severity": "minor",
                        "note": "cell off",
                    }
                ],
            ),
        )
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule != FUSION_RULE_LLM_CLEAR_SOFT_REVIEW

    def test_escalate_major_on_pass(self):
        r = fuse_verdicts(
            _whisker(VERDICT_PASS),
            _tapetum(
                VERDICT_FAIL,
                axis_findings=[
                    {
                        "axis": "tables",
                        "verdict": VERDICT_FAIL,
                        "severity": "major",
                        "note": "garbled",
                    }
                ],
            ),
        )
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_LLM_ESCALATE_MAJOR

    def test_escalate_ignores_non_major_fail_but_review_cap_still_fires(self):
        """A non-major axis fail does not trigger llm_escalate_major, but the
        primary tapetum verdict is still fail, so llm_review_cap (M2) caps the
        merge at review instead of silently keeping the deterministic pass."""
        r = fuse_verdicts(
            _whisker(VERDICT_PASS),
            _tapetum(
                VERDICT_FAIL,
                axis_findings=[
                    {
                        "axis": "structure",
                        "verdict": VERDICT_FAIL,
                        "severity": "minor",
                        "note": "heading",
                    }
                ],
            ),
        )
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_LLM_REVIEW_CAP

    def test_review_cap_on_pass_when_llm_review(self):
        """M2 (E19/E32): det=pass + llm=review must cap at review, never read
        combined_verdict=pass next to tapetum_verdict=review with no rule."""
        r = fuse_verdicts(
            _whisker(VERDICT_PASS),
            _tapetum(VERDICT_REVIEW),
        )
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_LLM_REVIEW_CAP
        assert r.tapetum_verdict == VERDICT_REVIEW

    def test_review_cap_on_pass_when_llm_fail_without_major_axis(self):
        """M2: det=pass + llm=fail with no major-severity axis finding (and no
        axis findings at all) still caps at review, not just when a non-major
        axis finding happens to exist."""
        r = fuse_verdicts(
            _whisker(VERDICT_PASS),
            _tapetum(VERDICT_FAIL, axis_findings=[]),
        )
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_LLM_REVIEW_CAP
        assert r.tapetum_verdict == VERDICT_FAIL

    def test_review_cap_does_not_fire_when_det_pass_llm_pass(self):
        """The lane must not become trigger-happy: a clean det=pass agreeing
        with llm=pass still fuses to pass via the ordinary agree rule."""
        r = fuse_verdicts(
            _whisker(VERDICT_PASS),
            _tapetum(VERDICT_PASS),
        )
        assert r.combined_verdict == VERDICT_PASS
        assert r.combined_rule == FUSION_RULE_AGREE

    def test_escalate_major_wins_over_review_cap(self):
        """The more specific llm_escalate_major rule fires (and reports its
        own reason) instead of being shadowed by the generic review cap."""
        r = fuse_verdicts(
            _whisker(VERDICT_PASS),
            _tapetum(
                VERDICT_FAIL,
                axis_findings=[
                    {
                        "axis": "tables",
                        "verdict": VERDICT_FAIL,
                        "severity": "major",
                        "note": "garbled",
                    }
                ],
            ),
        )
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_LLM_ESCALATE_MAJOR

    def test_toc_leak_clamp_det_review_llm_review_major_stays_review(self):
        """TOC-leak clamp: det=review + LLM=review with structure=major
        fuses to review, never fail. The advisory lane cannot unilaterally
        fail a paper even with major severity."""
        r = fuse_verdicts(
            _whisker(VERDICT_REVIEW, soft=["no_toc_leak"]),
            _tapetum(
                VERDICT_REVIEW,
                axis_findings=[
                    {
                        "axis": "structure",
                        "verdict": VERDICT_REVIEW,
                        "severity": "major",
                        "note": "toc_leak_unpaired: '## 5 lexical conventions [lex] 10'",
                    }
                ],
            ),
        )
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_AGREE

    def test_toc_leak_clamp_det_pass_llm_review_major_caps_review(self):
        """TOC-leak clamp: det=pass + LLM=review with structure=major
        must cap at review (llm_review_cap or llm_escalate_major), never fail."""
        r = fuse_verdicts(
            _whisker(VERDICT_PASS),
            _tapetum(
                VERDICT_REVIEW,
                axis_findings=[
                    {
                        "axis": "structure",
                        "verdict": VERDICT_REVIEW,
                        "severity": "major",
                        "note": "toc_leak_unpaired: '## 5 lexical conventions [lex] 10'",
                    }
                ],
            ),
        )
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_verdict != VERDICT_FAIL

    def test_review_cap_never_promotes_deterministic_fail(self):
        """Gate G1 regression: an adversarial all-clear advisory verdict
        (llm=pass, high confidence, no axis fails) must never lift a
        deterministic fail. The demote-only ratchet is untouched by M2."""
        r = fuse_verdicts(
            _whisker(VERDICT_FAIL, hard=["gate:non_empty"]),
            _tapetum(VERDICT_PASS, conf=1.0, axis_findings=[]),
        )
        assert r.combined_verdict == VERDICT_FAIL
        assert r.combined_rule == FUSION_RULE_WHISKER_FAIL_LOCKED

    def test_agree_when_same(self):
        r = fuse_verdicts(_whisker(VERDICT_REVIEW, soft=["x"]), _tapetum(VERDICT_REVIEW))
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_AGREE

    def test_hard_flags_block_clear(self):
        r = fuse_verdicts(
            _whisker(VERDICT_REVIEW, soft=["x"], hard=["gate:heading_monotone"]),
            _tapetum(VERDICT_PASS),
        )
        assert r.combined_rule != FUSION_RULE_LLM_CLEAR_SOFT_REVIEW

    def test_clear_blocked_when_missing_regions(self):
        r = fuse_verdicts(
            _whisker(
                VERDICT_REVIEW,
                soft=["2 misaligned region(s)"],
                ref_nid=0.92,
                missing_region_count=2,
            ),
            _tapetum(VERDICT_PASS, conf=0.95),
        )
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_CLEAR_BLOCKED_MISSING_REGION

    def test_clear_allowed_when_zero_missing_regions(self):
        r = fuse_verdicts(
            _whisker(
                VERDICT_REVIEW,
                soft=["2 misaligned region(s)"],
                ref_nid=0.92,
                missing_region_count=0,
            ),
            _tapetum(VERDICT_PASS, conf=0.95),
        )
        assert r.combined_verdict == VERDICT_PASS
        assert r.combined_rule == FUSION_RULE_LLM_CLEAR_SOFT_REVIEW

    def test_clear_allowed_when_missing_region_count_absent(self):
        r = fuse_verdicts(
            _whisker(
                VERDICT_REVIEW,
                soft=["2 misaligned region(s)"],
                ref_nid=0.92,
            ),
            _tapetum(VERDICT_PASS, conf=0.95),
        )
        assert r.combined_verdict == VERDICT_PASS
        assert r.combined_rule == FUSION_RULE_LLM_CLEAR_SOFT_REVIEW

    def test_ideal_review_caps_llm_pass_at_review(self):
        r = fuse_verdicts(
            _whisker(VERDICT_PASS),
            _tapetum(
                VERDICT_PASS,
                ideal_verification={
                    "verdict": "review",
                    "discrepancies": [{
                        "axis": "headings",
                        "candidate_quote": "### Candidate heading",
                        "ideal_quote": "## Ideal heading",
                        "severity": "major",
                        "explanation": "The candidate heading level differs.",
                    }],
                },
            ),
        )

        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_IDEAL_REVIEW_CAP
        assert r.ideal_verdict == "review"
        assert r.ideal_discrepancy_count == 1

    def test_ideal_pending_caps_llm_pass_at_review(self):
        tap = _tapetum(VERDICT_PASS)
        tap["ideal_pending"] = True
        r = fuse_verdicts(_whisker(VERDICT_PASS), tap)
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_IDEAL_REVIEW_CAP

    def test_ideal_agree_never_promotes_deterministic_review(self):
        r = fuse_verdicts(
            _whisker(VERDICT_REVIEW, soft=["ordinary review"]),
            _tapetum(
                VERDICT_REVIEW,
                ideal_verification={"verdict": "agree", "discrepancies": []},
            ),
        )

        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_AGREE
        assert r.ideal_verdict == "agree"
        assert r.ideal_discrepancy_count == 0

    def test_ideal_soft_flag_blocks_llm_soft_review_clear(self):
        r = fuse_verdicts(
            _whisker(
                VERDICT_REVIEW,
                soft=["ideal nid 0.700 < 0.850 (advisory)"],
                ref_nid=0.92,
            ),
            _tapetum(VERDICT_PASS),
        )

        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_CLEAR_BLOCKED_IDEAL_FLAG

    def test_ideal_verifier_does_not_change_locked_deterministic_fail(self):
        r = fuse_verdicts(
            _whisker(VERDICT_FAIL, hard=["gate:non_empty"]),
            _tapetum(
                VERDICT_PASS,
                ideal_verification={
                    "verdict": "review",
                    "discrepancies": [{
                        "axis": "structure",
                        "candidate_quote": "candidate",
                        "ideal_quote": "ideal",
                        "severity": "major",
                        "explanation": "different",
                    }],
                },
            ),
        )

        assert r.combined_verdict == VERDICT_FAIL
        assert r.combined_rule == FUSION_RULE_WHISKER_FAIL_LOCKED

    def test_old_sidecar_without_ideal_data_preserves_existing_clear(self):
        r = fuse_verdicts(
            _whisker(VERDICT_REVIEW, soft=["misaligned"], ref_nid=0.92),
            _tapetum(VERDICT_PASS),
        )

        assert r.combined_verdict == VERDICT_PASS
        assert r.combined_rule == FUSION_RULE_LLM_CLEAR_SOFT_REVIEW
        assert r.ideal_verdict is None
        assert r.ideal_discrepancy_count == 0
        assert r.to_dict()["ideal_verdict"] is None
        assert r.to_dict()["ideal_discrepancy_count"] == 0

    @pytest.mark.parametrize(
        "malformed",
        [
            {"verdict": "review", "discrepancies": None},
            {"verdict": "review", "discrepancies": "not-a-list"},
            {"verdict": "review", "discrepancies": [None]},
            {
                "verdict": "review",
                "discrepancies": [
                    {
                        "axis": "headings",
                        "candidate_quote": "candidate",
                        "ideal_quote": "ideal",
                        "severity": "major",
                        "explanation": "different",
                    }
                ] * (MAX_IDEAL_DISCREPANCIES + 1),
            },
        ],
    )
    def test_malformed_ideal_payload_is_neutral(self, malformed):
        r = fuse_verdicts(
            _whisker(VERDICT_PASS),
            _tapetum(VERDICT_PASS, ideal_verification=malformed),
        )

        assert r.combined_verdict == VERDICT_PASS
        assert r.combined_rule == FUSION_RULE_AGREE
        assert r.ideal_verdict is None
        assert r.ideal_discrepancy_count == 0


class TestSourceAwareFusion:
    """Schema-v6 source-aware evidence caps fusion independently of confidence."""

    def test_html_metadata_fail_or_review_caps_pass_at_review(self):
        for metadata_verdict in (VERDICT_FAIL, VERDICT_REVIEW):
            tapetum = {
                **_tapetum(VERDICT_PASS, conf=0.0),
                "schema_version": 6,
                "metadata_outline_check": {"verdict": metadata_verdict},
                "unit_coverage": {"coverage_complete": True},
            }
            r = fuse_verdicts(_whisker(VERDICT_PASS), tapetum)
            assert r.combined_verdict == VERDICT_REVIEW
            assert r.combined_rule == FUSION_RULE_SOURCE_AWARE_REVIEW_CAP
            assert r.tapetum_verdict == VERDICT_PASS

    def test_pdf_verified_critical_group_caps_pass_at_review(self):
        tapetum = {
            **_tapetum(VERDICT_PASS, conf=0.0),
            "schema_version": 6,
            "source_kind": "pdf",
            "metadata_outline_check": {"verdict": VERDICT_PASS},
            "unit_coverage": {"coverage_complete": True},
            "defect_groups": [{
                "defect_type": "content_omission",
                "severity": "critical",
                "verified_count": 3,
                "count_verification": {
                    "count_status": "verified",
                    "verified_delta": 3,
                },
            }],
        }
        r = fuse_verdicts(_whisker(VERDICT_PASS), tapetum)
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_SOURCE_AWARE_REVIEW_CAP
        assert r.tapetum_verdict == VERDICT_PASS

    def test_exact_candidate_not_found_high_or_critical_group_caps_review(self):
        for source_kind, severity in (
            ("html", "high"),
            ("pdf", "critical"),
        ):
            quote = f"{source_kind} source text omitted from candidate"
            tapetum = {
                **_tapetum(VERDICT_PASS, conf=0.0),
                "schema_version": 6,
                "source_kind": source_kind,
                "metadata_outline_check": {"verdict": VERDICT_PASS},
                "unit_coverage": {"coverage_complete": True},
                "defect_groups": [{
                    "defect_type": "content_omission",
                    "severity": severity,
                    "source_quote": quote,
                    "examples": [quote],
                    "verified_count": None,
                    "count_verification": {"count_status": "unverified"},
                }],
                "unit_checks": [{
                    "unit_id": (
                        "section:Motivation" if source_kind == "html" else "page:2"
                    ),
                    "defects": [{
                        "defect_type": "content_omission",
                        "severity": severity,
                        "source_quote": quote,
                        "evidence_disposition": {
                            "quote": quote,
                            "source_grounded": True,
                            "source_status": "exact",
                            "candidate_status": "candidate_not_found",
                        },
                    }],
                }],
            }
            r = fuse_verdicts(_whisker(VERDICT_PASS), tapetum)
            assert r.combined_verdict == VERDICT_REVIEW
            assert r.combined_rule == FUSION_RULE_SOURCE_AWARE_REVIEW_CAP

    def test_unaccepted_high_or_critical_claims_do_not_demote(self):
        controls = (
            ("present_in_candidate", "exact", True),
            ("ambiguous", "exact", True),
            ("candidate_not_found", "fuzzy", True),
            ("source_ungrounded", None, False),
        )
        for candidate_status, source_status, source_grounded in controls:
            quote = f"claim with {candidate_status}"
            evidence_summary = {
                "present_in_candidate": int(
                    candidate_status == "present_in_candidate"
                ),
                "candidate_not_found": int(
                    candidate_status == "candidate_not_found"
                ),
                "ambiguous": int(candidate_status == "ambiguous"),
                "source_ungrounded": int(
                    candidate_status == "source_ungrounded"
                ),
            }
            disposition = {
                "quote": quote,
                "source_grounded": source_grounded,
                "candidate_status": candidate_status,
            }
            if source_status is not None:
                disposition["source_status"] = source_status
            tapetum = {
                **_tapetum(VERDICT_PASS, conf=0.0),
                "schema_version": 6,
                "metadata_outline_check": {"verdict": VERDICT_PASS},
                "unit_coverage": {
                    "coverage_complete": True,
                    "evidence_summary": evidence_summary,
                },
                "defect_groups": [{
                    "defect_type": "content_omission",
                    "severity": "critical",
                    "source_quote": quote,
                    "examples": [quote],
                    "verified_count": None,
                    "count_verification": {"count_status": "unverified"},
                }],
                "unit_checks": [{
                    "unit_id": "page:2",
                    "defects": [{
                        "defect_type": "content_omission",
                        "severity": "critical",
                        "source_quote": quote,
                        "evidence_disposition": disposition,
                    }],
                }],
            }
            r = fuse_verdicts(_whisker(VERDICT_PASS), tapetum)
            assert r.combined_verdict == VERDICT_PASS

    def test_flattened_pdf_unit_acceptance_caps_review(self):
        quote = "accepted PDF unit omission"
        tapetum = {
            **_tapetum(VERDICT_PASS, conf=0.0),
            "schema_version": 6,
            "source_kind": "pdf",
            "metadata_outline_check": {"verdict": VERDICT_PASS},
            "unit_coverage": {"coverage_complete": True},
            "defect_groups": [{
                "defect_type": "content_omission",
                "severity": "high",
                "source_quote": quote,
                "examples": [quote],
                "verified_count": None,
                "count_verification": {"count_status": "unverified"},
            }],
            "evidence_dispositions": [{
                "unit_id": "page:4",
                "quote": quote,
                "source_status": "exact",
                "candidate_status": "candidate_not_found",
            }],
        }
        r = fuse_verdicts(_whisker(VERDICT_PASS), tapetum)
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_SOURCE_AWARE_REVIEW_CAP

    def test_raw_high_group_without_accepted_evidence_does_not_demote(self):
        tapetum = {
            **_tapetum(VERDICT_PASS, conf=0.0),
            "schema_version": 6,
            "metadata_outline_check": {"verdict": VERDICT_PASS},
            "unit_coverage": {"coverage_complete": True},
            "defect_groups": [{
                "defect_type": "content_omission",
                "severity": "high",
                "source_quote": "raw model claim",
                "examples": ["raw model claim"],
                "verified_count": None,
                "count_verification": {"count_status": "unverified"},
            }],
            "evidence_dispositions": [{
                "quote": "raw model claim",
                "source_status": "exact",
                "candidate_status": "candidate_not_found",
            }],
        }
        r = fuse_verdicts(_whisker(VERDICT_PASS), tapetum)
        assert r.combined_verdict == VERDICT_PASS

    def test_incomplete_coverage_caps_pass_at_review(self):
        for unit_coverage in (
            {
                "coverage_complete": False,
                "unchecked_unit_ids": ["section:Motivation"],
                "failed_unit_ids": [],
            },
            {
                "coverage_complete": True,
                "unchecked_unit_ids": [],
                "failed_unit_ids": ["page:3"],
            },
        ):
            tapetum = {
                **_tapetum(VERDICT_PASS, conf=0.0),
                "schema_version": 6,
                "metadata_outline_check": {"verdict": VERDICT_PASS},
                "unit_coverage": unit_coverage,
            }
            r = fuse_verdicts(_whisker(VERDICT_PASS), tapetum)
            assert r.combined_verdict == VERDICT_REVIEW
            assert r.combined_rule == FUSION_RULE_SOURCE_AWARE_REVIEW_CAP

    def test_clean_source_aware_pass_preserves_pass(self):
        tapetum = {
            **_tapetum(VERDICT_PASS, conf=0.0),
            "schema_version": 6,
            "metadata_outline_check": {"verdict": VERDICT_PASS},
            "unit_coverage": {
                "coverage_complete": True,
                "evidence_summary": {
                    "ambiguous": 0,
                    "source_ungrounded": 0,
                },
            },
            "defect_groups": [],
        }
        r = fuse_verdicts(_whisker(VERDICT_PASS), tapetum)
        assert r.combined_verdict == VERDICT_PASS
        assert r.tapetum_verdict == VERDICT_PASS

    def test_refuted_only_evidence_does_not_demote_pass(self):
        tapetum = {
            **_tapetum(VERDICT_PASS, conf=0.0),
            "schema_version": 6,
            "metadata_outline_check": {"verdict": VERDICT_PASS},
            "unit_coverage": {
                "coverage_complete": True,
                "evidence_summary": {
                    "present_in_candidate": 2,
                    "candidate_not_found": 0,
                    "ambiguous": 0,
                    "source_ungrounded": 0,
                },
            },
            "defect_groups": [],
            "evidence_dispositions": [{
                "quote": "already present",
                "source_status": "exact",
                "candidate_status": "present_in_candidate",
            }],
        }
        r = fuse_verdicts(_whisker(VERDICT_PASS), tapetum)
        assert r.combined_verdict == VERDICT_PASS
        assert r.tapetum_verdict == VERDICT_PASS

    def test_all_pages_complete_selection_does_not_force_review(self):
        tapetum = {
            **_tapetum(VERDICT_PASS, conf=0.0),
            "schema_version": 8,
            "metadata_outline_check": {"verdict": VERDICT_PASS},
            "unit_coverage": {
                "coverage_complete": True,
                "unchecked_unit_ids": [],
                "failed_unit_ids": [],
                "mode": "all_pages",
            },
            "all_pages_requested": True,
            "unit_selection": {
                "required": ["page:1", "page:2"],
                "checked": ["page:1", "page:2"],
                "unchecked": [],
                "failed": [],
            },
            "defect_groups": [],
        }
        r = fuse_verdicts(_whisker(VERDICT_PASS), tapetum)
        assert r.combined_verdict == VERDICT_PASS

    def test_all_pages_unchecked_forces_review(self):
        tapetum = {
            **_tapetum(VERDICT_PASS, conf=0.0),
            "schema_version": 8,
            "metadata_outline_check": {"verdict": VERDICT_PASS},
            "unit_coverage": {
                "coverage_complete": True,
                "unchecked_unit_ids": [],
                "failed_unit_ids": [],
                "mode": "all_pages",
            },
            "all_pages_requested": True,
            "unit_selection": {
                "required": ["page:1", "page:2"],
                "checked": ["page:1"],
                "unchecked": ["page:2"],
                "failed": [],
            },
            "defect_groups": [],
        }
        r = fuse_verdicts(_whisker(VERDICT_PASS), tapetum)
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_SOURCE_AWARE_REVIEW_CAP

    def test_old_sidecar_without_all_pages_fields_unchanged(self):
        tapetum = {
            **_tapetum(VERDICT_PASS, conf=0.0),
            "schema_version": 6,
            "metadata_outline_check": {"verdict": VERDICT_PASS},
            "unit_coverage": {
                "coverage_complete": True,
                "evidence_summary": {
                    "ambiguous": 0,
                    "source_ungrounded": 0,
                },
            },
            "defect_groups": [],
        }
        r = fuse_verdicts(_whisker(VERDICT_PASS), tapetum)
        assert r.combined_verdict == VERDICT_PASS


class TestFusionDeterminism:
    def test_same_input_same_dict(self):
        w = _whisker(VERDICT_REVIEW, soft=["misaligned"], ref_nid=0.9, pid="N5034")
        t = _tapetum(VERDICT_PASS)
        a = fuse_verdicts(w, t).to_dict()
        b = fuse_verdicts(w, t).to_dict()
        assert a == b
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)

    def test_fingerprint_stable(self):
        w = _whisker(VERDICT_PASS, pid="P4003R0")
        fp1 = fuse_verdicts(w, None).whisker_fingerprint
        fp2 = fuse_verdicts(w, None).whisker_fingerprint
        assert fp1 == fp2
        assert len(fp1) == 16

    def test_evidence_cleanup_does_not_change_lane_or_fusion_verdicts(self):
        whisker = _whisker(
            VERDICT_REVIEW,
            soft=["misaligned"],
            ref_nid=0.92,
            pid="P2840",
        )
        llm = {
            **_tapetum(
                VERDICT_FAIL,
                axis_findings=[{
                    "axis": "structure",
                    "verdict": VERDICT_FAIL,
                    "severity": "major",
                    "note": "independent section-order defect",
                }],
            ),
            "whisker_verdict": VERDICT_REVIEW,
        }
        before = {
            **llm,
            "grounded_evidence": [{
                "quote": "false missing",
                "reason": "legacy absence claim",
            }],
        }
        after = {
            **llm,
            "grounded_evidence": [],
            "evidence_dispositions": [{
                "quote": "false missing",
                "source_status": "exact",
                "candidate_status": "present_in_candidate",
            }],
        }
        before_fusion = fuse_verdicts(whisker, before)
        after_fusion = fuse_verdicts(whisker, after)

        assert whisker["verdict"] == VERDICT_REVIEW
        assert after["whisker_verdict"] == VERDICT_REVIEW
        assert after["suggested_verdict"] == VERDICT_FAIL
        assert after_fusion.combined_verdict == before_fusion.combined_verdict
        assert after_fusion.combined_rule == before_fusion.combined_rule

    def test_det_llm_and_merged_are_three_distinct_outputs(self):
        whisker = _whisker(VERDICT_PASS, pid="P2930")
        llm = _tapetum(
            VERDICT_FAIL,
            axis_findings=[{
                "axis": "structure",
                "verdict": VERDICT_FAIL,
                "severity": "major",
                "note": "missing declarations",
            }],
        )
        fusion = fuse_verdicts(whisker, llm)
        assert whisker["verdict"] == VERDICT_PASS
        assert llm["suggested_verdict"] == VERDICT_FAIL
        assert fusion.combined_verdict == VERDICT_REVIEW


class TestRealSidecarFixtures:
    """Shape-validated fixtures from the 2026-07-06 sidecar run."""

    N5035_WHISKER = {
        "pid": "N5035",
        "verdict": "not-llm-readable",
        "hard_flags": ["gate:heading_monotone:heading level jumps H1 -> H3"],
        "soft_flags": ["9 misaligned region(s)", "reference text agreement 0.662 low (advisory)"],
        "ref_nid": 0.6623,
        "unigram_coverage": 0.9526,
    }
    N5035_TAPETUM = {
        "pid": "N5035",
        "status": "ok",
        "suggested_verdict": "review",
        "confidence": 0.95,
        "axis_findings": [
            {
                "axis": "structure",
                "verdict": "review",
                "severity": "minor",
                "note": "Cosmetic heading-level jump (H1 -> H3)",
            }
        ],
    }

    P4003_WHISKER = {
        "pid": "P4003R0",
        "verdict": "review",
        "soft_flags": ["62 misaligned region(s)", "1 uncertain marker(s)"],
        "hard_flags": [],
        "ref_nid": 0.824,
        "unigram_coverage": 0.974,
    }
    P4003_TAPETUM = {
        "pid": "P4003R0",
        "suggested_verdict": "not-llm-readable",
        "confidence": 0.95,
        "axis_findings": [
            {"axis": "tables", "verdict": "not-llm-readable", "severity": "major", "note": "garbled"},
        ],
    }

    N5034_WHISKER = {
        "pid": "N5034",
        "verdict": "review",
        "soft_flags": ["misaligned region(s)"],
        "hard_flags": [],
        "ref_nid": 0.9227,
        "unigram_coverage": 0.95,
    }
    N5034_TAPETUM = {
        "pid": "N5034",
        "suggested_verdict": "pass",
        "confidence": 0.95,
        "axis_findings": [],
    }

    def test_n5035_rescue(self):
        r = fuse_verdicts(self.N5035_WHISKER, self.N5035_TAPETUM)
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_LLM_RESCUE_HEADING

    def test_p4003_no_escalate_when_det_review(self):
        """det=review + llm fail stays review (escalate only on det=pass)."""
        r = fuse_verdicts(self.P4003_WHISKER, self.P4003_TAPETUM)
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_WHISKER_ONLY

    def test_p4003_escalate_when_det_pass(self):
        whisker = {**self.P4003_WHISKER, "verdict": VERDICT_PASS, "soft_flags": []}
        r = fuse_verdicts(whisker, self.P4003_TAPETUM)
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_LLM_ESCALATE_MAJOR

    def test_n5034_clear(self):
        r = fuse_verdicts(self.N5034_WHISKER, self.N5034_TAPETUM)
        assert r.combined_verdict == VERDICT_PASS
        assert r.combined_rule == FUSION_RULE_LLM_CLEAR_SOFT_REVIEW

    P0957_WHISKER = {
        "pid": "P0957R8",
        "verdict": "review",
        "soft_flags": ["2 misaligned region(s)"],
        "hard_flags": [],
        "ref_nid": None,
        "missing_region_count": 2,
        "missing_regions": [
            {"page": 1, "token_start": 0, "token_end": 29, "sample": "1 proxy a polymorphic..."},
            {
                "page": 13,
                "token_start": 3545,
                "token_end": 3730,
                "sample": "13 figure 1 expected memory layout...",
            },
        ],
        "coverage": 0.9166,
        "unigram_coverage": 0.97,
    }
    P0957_TAPETUM = {
        "pid": "P0957R8",
        "status": "ok",
        "suggested_verdict": "pass",
        "confidence": 0.98,
        "axis_findings": [{"axis": "structure", "verdict": "pass", "severity": "none", "note": "..."}],
    }

    def test_p0957_missing_region_blocks_clear(self):
        """Verified false-pass: LLM cannot see the source, so it cannot verify
        the absence of the 2 regions whisker flagged as missing."""
        r = fuse_verdicts(self.P0957_WHISKER, self.P0957_TAPETUM)
        assert r.combined_verdict == VERDICT_REVIEW
        assert r.combined_rule == FUSION_RULE_CLEAR_BLOCKED_MISSING_REGION


class TestFusionReport:
    def _rows(self):
        w1 = _whisker(VERDICT_REVIEW, soft=["x"], ref_nid=0.9, pid="N5034")
        t1 = _tapetum(VERDICT_PASS)
        f1 = fuse_verdicts(w1, t1).to_dict()
        t1_full = {**t1, "fusion": f1}
        w2 = _whisker(VERDICT_PASS, pid="P4003R0")
        return build_merged_json([w1, w2], {"N5034": t1_full})

    def test_build_merged_json_sorted_worst_first(self):
        rows = self._rows()
        assert rows[0]["pid"] == "N5034"
        assert rows[0]["merged"] == VERDICT_PASS

    def test_render_merged_report_md_deterministic(self):
        rows = self._rows()
        assert render_merged_report_md(rows) == render_merged_report_md(rows)

    def test_render_merged_report_md_has_table(self):
        md = render_merged_report_md(self._rows())
        assert "| PID | det | llm | merged |" in md
        assert "| class |" in md
        assert "N5034" in md

    def test_terminal_line_and_footer(self):
        line = render_terminal_fusion_line("N5034", "review", "pass", "pass", 0.95, "llm_clear")
        assert "merged:PASS" in line
        footer = render_terminal_fusion_footer(self._rows())
        assert "LLM coverage" in footer

    def test_merged_report_shows_compact_ideal_status_without_quotes(self):
        w = _whisker(VERDICT_PASS, pid="IDEAL1")
        t = _tapetum(
            VERDICT_PASS,
            ideal_verification={
                "verdict": "review",
                "discrepancies": [{
                    "axis": "headings",
                    "candidate_quote": "PRIVATE CANDIDATE QUOTE",
                    "ideal_quote": "PRIVATE IDEAL QUOTE",
                    "severity": "major",
                    "explanation": "heading level differs",
                }],
            },
        )
        t["fusion"] = fuse_verdicts(w, t).to_dict()

        rows = build_merged_json([w], {"IDEAL1": t})
        md = render_merged_report_md(rows)

        assert rows[0]["ideal_verdict"] == "review"
        assert rows[0]["ideal_discrepancy_count"] == 1
        assert "| review | 1 |" in md
        assert "PRIVATE CANDIDATE QUOTE" not in md
        assert "PRIVATE IDEAL QUOTE" not in md

    def test_merged_report_marks_absent_ideal_neutrally(self):
        rows = self._rows()
        md = render_merged_report_md(rows)

        assert all(r["ideal_verdict"] is None for r in rows)
        assert all(r["ideal_discrepancy_count"] == 0 for r in rows)
        assert "| - | 0 |" in md

    @pytest.mark.parametrize(
        "malformed",
        [
            {"verdict": "review", "discrepancies": None},
            {"verdict": "review", "discrepancies": "not-a-list"},
            {"verdict": "review", "discrepancies": [None]},
            {
                "verdict": "review",
                "discrepancies": [
                    {
                        "axis": "headings",
                        "candidate_quote": "candidate",
                        "ideal_quote": "ideal",
                        "severity": "major",
                        "explanation": "different",
                    }
                ] * (MAX_IDEAL_DISCREPANCIES + 1),
            },
        ],
    )
    def test_merged_report_treats_malformed_ideal_as_absent(self, malformed):
        w = _whisker(VERDICT_PASS, pid="MALFORMED")
        t = _tapetum(VERDICT_PASS, ideal_verification=malformed)

        rows = build_merged_json([w], {"MALFORMED": t})
        md = render_merged_report_md(rows)

        assert rows[0]["ideal_verdict"] is None
        assert rows[0]["ideal_discrepancy_count"] == 0
        assert "| - | 0 |" in md

    def test_merged_report_is_total_over_wrong_sidecar_types(self):
        rows = build_merged_json(
            [{
                "pid": "BROKEN",
                "verdict": "pass",
                "unigram_coverage": None,
                "ref_overall": "not-a-number",
                "ideal_overall": [],
                "hard_flags": None,
                "soft_flags": "not-a-list",
            }],
            {
                "BROKEN": {
                    "suggested_verdict": None,
                    "confidence": "not-a-number",
                    "axis_findings": [None],
                    "fusion": {
                        "combined_verdict": [],
                        "combined_rule": [],
                    },
                    "ideal_verification": {"verdict": "review", "discrepancies": [None]},
                }
            },
        )

        assert rows[0]["ideal_verdict"] is None
        assert rows[0]["ideal_discrepancy_count"] == 0
        assert render_merged_report_md(rows)


class TestReplayedMarker:
    """B2: the merged report marks a tapetum result as ``replayed`` when it
    was carried over from a previous run rather than evaluated in this one.
    """

    def test_no_run_started_at_marks_present_tapetum_as_replayed(self):
        """--fuse-only (no run_started_at): every tapetum result present is
        definitionally a replay, since no evaluation happened this call."""
        w = _whisker(VERDICT_PASS, pid="R1")
        t = _tapetum(VERDICT_PASS)
        t["fusion"] = fuse_verdicts(w, t).to_dict()
        rows = build_merged_json([w], {"R1": t})
        assert rows[0]["replayed"] is True

    def test_evaluated_at_before_run_started_is_replayed(self):
        w = _whisker(VERDICT_PASS, pid="R2")
        t = {**_tapetum(VERDICT_PASS), "evaluated_at": "2020-01-01T00:00:00+00:00"}
        t["fusion"] = fuse_verdicts(w, t).to_dict()
        rows = build_merged_json(
            [w], {"R2": t}, run_started_at="2030-01-01T00:00:00+00:00",
        )
        assert rows[0]["replayed"] is True

    def test_evaluated_at_after_run_started_is_not_replayed(self):
        w = _whisker(VERDICT_PASS, pid="R3")
        t = {**_tapetum(VERDICT_PASS), "evaluated_at": "2030-06-01T00:00:00+00:00"}
        t["fusion"] = fuse_verdicts(w, t).to_dict()
        rows = build_merged_json(
            [w], {"R3": t}, run_started_at="2030-01-01T00:00:00+00:00",
        )
        assert rows[0]["replayed"] is False

    def test_missing_evaluated_at_with_run_started_at_is_replayed(self):
        """A sidecar with no evaluated_at at all (pre-B2 sidecar, or an
        error tombstone) is treated as a replay, never as freshly evaluated."""
        w = _whisker(VERDICT_PASS, pid="R4")
        t = _tapetum(VERDICT_PASS)
        t["fusion"] = fuse_verdicts(w, t).to_dict()
        rows = build_merged_json(
            [w], {"R4": t}, run_started_at="2030-01-01T00:00:00+00:00",
        )
        assert rows[0]["replayed"] is True

    def test_no_tapetum_data_is_not_applicable(self):
        w = _whisker(VERDICT_PASS, pid="R5")
        rows = build_merged_json([w], {}, run_started_at="2030-01-01T00:00:00+00:00")
        assert rows[0]["replayed"] is None

    def test_replay_count_in_summary_and_replay_column_in_table(self):
        w = _whisker(VERDICT_PASS, pid="R6")
        t = {**_tapetum(VERDICT_PASS), "evaluated_at": "2020-01-01T00:00:00+00:00"}
        t["fusion"] = fuse_verdicts(w, t).to_dict()
        rows = build_merged_json(
            [w], {"R6": t}, run_started_at="2030-01-01T00:00:00+00:00",
        )
        md = render_merged_report_md(rows)
        assert "warm replay (fingerprint-skip carryover): 1/1" in md
        assert "| replay |" in md
        assert "| warm |" in md


class TestCosmeticTier:
    def test_structure_only_minor_is_cosmetic(self):
        w = _whisker(VERDICT_REVIEW, soft=["x"], ref_nid=0.9, pid="TEST1")
        t = _tapetum(
            VERDICT_REVIEW,
            axis_findings=[
                {"axis": "structure", "verdict": "review", "severity": "minor", "note": "heading"},
                {"axis": "wording", "verdict": "pass", "severity": "none", "note": "ok"},
            ],
        )
        fusion = fuse_verdicts(w, t).to_dict()
        t_full = {**t, "fusion": fusion}
        rows = build_merged_json([w], {"TEST1": t_full})
        assert rows[0]["class"] == "cosmetic"

    def test_non_structure_axis_not_cosmetic(self):
        w = _whisker(VERDICT_REVIEW, soft=["x"], ref_nid=0.9, pid="TEST2")
        t = _tapetum(
            VERDICT_REVIEW,
            axis_findings=[
                {"axis": "tables", "verdict": "review", "severity": "minor", "note": "lossy"},
            ],
        )
        fusion = fuse_verdicts(w, t).to_dict()
        t_full = {**t, "fusion": fusion}
        rows = build_merged_json([w], {"TEST2": t_full})
        assert rows[0]["class"] == ""

    def test_major_severity_not_cosmetic(self):
        w = _whisker(VERDICT_REVIEW, soft=["x"], ref_nid=0.9, pid="TEST3")
        t = _tapetum(
            VERDICT_REVIEW,
            axis_findings=[
                {"axis": "structure", "verdict": "not-llm-readable", "severity": "major", "note": "broken"},
            ],
        )
        fusion = fuse_verdicts(w, t).to_dict()
        t_full = {**t, "fusion": fusion}
        rows = build_merged_json([w], {"TEST3": t_full})
        assert rows[0]["class"] == ""

    def test_cosmetic_in_md_and_footer(self):
        w = _whisker(VERDICT_REVIEW, soft=["x"], ref_nid=0.9, pid="COS1")
        t = _tapetum(
            VERDICT_REVIEW,
            axis_findings=[
                {"axis": "structure", "verdict": "review", "severity": "minor", "note": "h"},
            ],
        )
        fusion = fuse_verdicts(w, t).to_dict()
        t_full = {**t, "fusion": fusion}
        rows = build_merged_json([w], {"COS1": t_full})
        md = render_merged_report_md(rows)
        assert "cosmetic" in md
        footer = render_terminal_fusion_footer(rows)
        assert "cosmetic" in footer


class TestInspectMergedRollup:
    def test_header_includes_merged_rollup(self):
        w = _whisker(VERDICT_REVIEW, soft=["x"], ref_nid=0.9, pid="N5034")
        t = _tapetum(VERDICT_PASS)
        fusion = fuse_verdicts(w, t).to_dict()
        report = format_report([(w, {**t, "fusion": fusion})])
        assert "merged rollup" in report
        assert "1 pass" in report

    def test_inspect_renders_full_ideal_discrepancies_and_authority(self):
        w = _whisker(VERDICT_PASS, pid="IDEAL1")
        t = _tapetum(
            VERDICT_PASS,
            ideal_verification={
                "verdict": "review",
                "discrepancies": [{
                    "axis": "headings",
                    "candidate_quote": "### Candidate heading",
                    "ideal_quote": "## Ideal heading",
                    "severity": "major",
                    "explanation": "The heading level differs.",
                }],
            },
        )

        report = format_report([(w, t)])

        assert "source remains the factual authority" in report
        assert "**Ideal verification:** `review` (1 discrepancy)" in report
        assert "| headings | major |" in report
        assert "### Candidate heading" in report
        assert "## Ideal heading" in report
        assert "The heading level differs." in report

    def test_inspect_marks_no_ideal_neutrally(self):
        report = format_report([
            (_whisker(VERDICT_PASS, pid="NOIDEAL"), _tapetum(VERDICT_PASS))
        ])

        assert "**Ideal verification:** not available" in report

    @pytest.mark.parametrize(
        "malformed",
        [
            {"verdict": "review", "discrepancies": None},
            {"verdict": "review", "discrepancies": "not-a-list"},
            {"verdict": "review", "discrepancies": [None]},
            {
                "verdict": "review",
                "discrepancies": [
                    {
                        "axis": "headings",
                        "candidate_quote": "candidate",
                        "ideal_quote": "ideal",
                        "severity": "major",
                        "explanation": "different",
                    }
                ] * (MAX_IDEAL_DISCREPANCIES + 1),
            },
        ],
    )
    def test_inspect_treats_malformed_ideal_as_absent(self, malformed):
        report = format_report([
            (
                _whisker(VERDICT_PASS, pid="MALFORMED"),
                _tapetum(VERDICT_PASS, ideal_verification=malformed),
            )
        ])

        assert "**Ideal verification:** not available" in report
        assert "source remains the factual authority" not in report

    def test_inspect_escapes_markdown_and_html_active_ideal_text(self):
        t = _tapetum(
            VERDICT_PASS,
            ideal_verification={
                "verdict": "review",
                "discrepancies": [{
                    "axis": "wording",
                    "candidate_quote": "<script>alert(1)</script> | *candidate*",
                    "ideal_quote": "<b>ideal</b> | value",
                    "severity": "minor",
                    "explanation": "<em>difference</em> | explained",
                }],
            },
        )

        report = format_report([(_whisker(VERDICT_PASS, pid="ESCAPE"), t)])

        assert "<script>" not in report
        assert "<b>" not in report
        assert "<em>" not in report
        assert "&lt;script&gt;" in report
        assert "\\| \\*candidate\\*" in report

    def test_inspect_is_total_over_wrong_sidecar_types(self):
        report = format_report([
            (
                {"pid": "BROKEN", "verdict": "review", "soft_flags": None},
                {
                    "suggested_verdict": None,
                    "confidence": None,
                    "axis_findings": [None],
                    "metadata_outline_check": [],
                    "unit_coverage": "broken",
                    "defect_groups": [{
                        "count_verification": None,
                        "source_quote": None,
                    }],
                    "risk_signals": [{"detail": None}],
                    "evidence_dispositions": [{"candidate_status": []}],
                    "evidence_summary": [],
                    "grounded_evidence": [{"quote": None}],
                    "fusion": {"combined_verdict": []},
                    "ideal_verification": {"verdict": "review", "discrepancies": [None]},
                },
            )
        ])

        assert "## BROKEN" in report
        assert "**Ideal verification:** not available" in report


class TestChunkFoldBypassFix:
    def test_empty_aggregated_findings_uses_per_part_severity_fold(self):
        """Cosmetic fail in one chunk must not become overall fail via raw verdict."""
        part = Adjudication(
            reasoning="r",
            axis_findings=[
                AxisFinding(
                    axis="structure",
                    verdict=VERDICT_FAIL,
                    severity="minor",
                    note="heading",
                )
            ],
            worst_axis="structure",
            verdict=VERDICT_FAIL,
            confidence=0.9,
            evidence_spans=[],
            primary_concern="cosmetic",
        )
        empty = Adjudication(
            reasoning="ok",
            axis_findings=[],
            worst_axis="structure",
            verdict=VERDICT_PASS,
            confidence=0.95,
            evidence_spans=[],
            primary_concern="",
        )
        agg = aggregate_adjudications([part, empty], 2)
        assert agg.verdict == VERDICT_REVIEW

    def test_empty_findings_all_parts_raw_fail_still_fail(self):
        """Without axis findings, raw part fail verdicts still propagate fail."""
        fail_part = Adjudication(
            reasoning="r",
            axis_findings=[],
            worst_axis="tables",
            verdict=VERDICT_FAIL,
            confidence=0.9,
            evidence_spans=[],
            primary_concern="broken",
        )
        agg = aggregate_adjudications([fail_part], 1)
        assert agg.verdict == VERDICT_FAIL


# ---------------------------------------------------------------------------
# _build_merged_report: disk-level integration tests
# ---------------------------------------------------------------------------


class _MergedReportBackend:
    """Minimal duck-typed backend for _build_merged_report tests."""

    def __init__(self, root: Path, pids: list[str]) -> None:
        self._root = root
        self._pids = pids
        (root / "paperstore").mkdir(parents=True, exist_ok=True)

    def get_paper_md_path(self, pid: str) -> Path:
        return self._root / "paperstore" / f"{pid.lower()}.md"

    def list_all_paper_ids(self) -> list[str]:
        return list(self._pids)


def _seed_sidecars(
    root: Path,
    pids: list[str],
    *,
    whisker_verdicts: dict[str, str] | None = None,
    tapetum_verdicts: dict[str, str] | None = None,
) -> None:
    """Write minimal whisker + tapetum sidecar files into the on-disk layout."""
    wv = whisker_verdicts or {}
    tv = tapetum_verdicts or {}

    det_dir = root / "whisker" / "det"
    det_dir.mkdir(parents=True, exist_ok=True)
    llm_dir = root / "whisker" / "llm"
    llm_dir.mkdir(parents=True, exist_ok=True)

    for pid in pids:
        w = _whisker(wv.get(pid, VERDICT_PASS), pid=pid)
        (det_dir / f"{pid.lower()}.whisker.json").write_text(
            json.dumps(w), encoding="utf-8",
        )

        if pid in tv:
            t = _tapetum(tv[pid])
            t["pid"] = pid
            fusion = fuse_verdicts(w, t).to_dict()
            t["fusion"] = fusion
            (llm_dir / f"{pid.lower()}.whisker.tapetum.json").write_text(
                json.dumps(t), encoding="utf-8",
            )


class TestBuildMergedReport:
    """Verify _build_merged_report writes report-merged files from sidecars."""

    @pytest.mark.parametrize("root", [[], None, "not-an-object", 7])
    def test_full_report_treats_non_object_tapetum_as_unavailable(
        self, tmp_path, root
    ):
        from whisker.llm.cli import _build_merged_report

        pid = "P0001"
        _seed_sidecars(
            tmp_path,
            [pid],
            whisker_verdicts={pid: VERDICT_PASS},
            tapetum_verdicts={pid: VERDICT_PASS},
        )
        tap_path = (
            tmp_path / "whisker" / "llm" / "p0001.whisker.tapetum.json"
        )
        tap_path.write_text(json.dumps(root), encoding="utf-8")

        _build_merged_report(_MergedReportBackend(tmp_path, [pid]))

        report_path = tmp_path / "whisker" / "llm" / "report-merged.json"
        rows = json.loads(report_path.read_text(encoding="utf-8"))
        assert len(rows) == 1
        assert rows[0]["pid"] == pid
        assert rows[0]["llm"] == "-"
        assert rows[0]["merged"] == VERDICT_PASS

    @pytest.mark.parametrize("root", [[], None, "not-an-object", 7])
    def test_full_report_uses_stub_for_non_object_whisker(self, tmp_path, root):
        from whisker.llm.cli import _build_merged_report

        pid = "P0001"
        _seed_sidecars(
            tmp_path,
            [pid],
            whisker_verdicts={pid: VERDICT_PASS},
            tapetum_verdicts={pid: VERDICT_PASS},
        )
        whisker_path = tmp_path / "whisker" / "det" / "p0001.whisker.json"
        whisker_path.write_text(json.dumps(root), encoding="utf-8")

        _build_merged_report(_MergedReportBackend(tmp_path, [pid]))

        report_path = tmp_path / "whisker" / "llm" / "report-merged.json"
        rows = json.loads(report_path.read_text(encoding="utf-8"))
        assert rows[0]["pid"] == pid
        assert rows[0]["det"] == "?"

    @pytest.mark.parametrize("root", [[], None, "not-an-object", 7])
    def test_fuse_only_skips_non_object_tapetum(self, tmp_path, root):
        from whisker.llm.cli import _fuse_only

        pid = "P0001"
        _seed_sidecars(
            tmp_path,
            [pid],
            whisker_verdicts={pid: VERDICT_PASS},
            tapetum_verdicts={pid: VERDICT_PASS},
        )
        tap_path = (
            tmp_path / "whisker" / "llm" / "p0001.whisker.tapetum.json"
        )
        original = json.dumps(root)
        tap_path.write_text(original, encoding="utf-8")

        _fuse_only(_MergedReportBackend(tmp_path, [pid]), inspect=False)

        assert tap_path.read_text(encoding="utf-8") == original

    @pytest.mark.parametrize("root", [[], None, "not-an-object", 7])
    def test_fuse_only_uses_stub_for_non_object_whisker(self, tmp_path, root):
        from whisker.llm.cli import _fuse_only

        pid = "P0001"
        _seed_sidecars(
            tmp_path,
            [pid],
            whisker_verdicts={pid: VERDICT_PASS},
            tapetum_verdicts={pid: VERDICT_PASS},
        )
        whisker_path = tmp_path / "whisker" / "det" / "p0001.whisker.json"
        whisker_path.write_text(json.dumps(root), encoding="utf-8")

        _fuse_only(_MergedReportBackend(tmp_path, [pid]), inspect=False)

        tap_path = (
            tmp_path / "whisker" / "llm" / "p0001.whisker.tapetum.json"
        )
        tap = json.loads(tap_path.read_text(encoding="utf-8"))
        assert tap["fusion"]["whisker_verdict"] == "?"

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            *(("pid", value) for value in _INVALID_PID_VALUES),
            ("suggested_verdict", []),
            *(("confidence", value) for value in _INVALID_CONFIDENCE_VALUES),
        ],
    )
    def test_full_report_treats_invalid_tapetum_object_as_unavailable(
        self, tmp_path, field, value
    ):
        from whisker.llm.cli import _build_merged_report

        pid = "P0001"
        _seed_sidecars(
            tmp_path,
            [pid],
            whisker_verdicts={pid: VERDICT_PASS},
            tapetum_verdicts={pid: VERDICT_PASS},
        )
        tap_path = (
            tmp_path / "whisker" / "llm" / "p0001.whisker.tapetum.json"
        )
        tapetum = json.loads(tap_path.read_text(encoding="utf-8"))
        tapetum[field] = value
        tap_path.write_text(json.dumps(tapetum), encoding="utf-8")

        _build_merged_report(_MergedReportBackend(tmp_path, [pid]))

        report_path = tmp_path / "whisker" / "llm" / "report-merged.json"
        rows = json.loads(report_path.read_text(encoding="utf-8"))
        assert rows[0]["pid"] == pid
        assert rows[0]["llm"] == "-"
        assert rows[0]["merged"] == VERDICT_PASS
        assert rows[0]["rule"] == ""

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            *(("pid", value) for value in _INVALID_PID_VALUES),
            ("verdict", []),
        ],
    )
    def test_full_report_uses_stub_for_invalid_whisker_object(
        self, tmp_path, field, value
    ):
        from whisker.llm.cli import _build_merged_report

        pid = "P0001"
        _seed_sidecars(
            tmp_path,
            [pid],
            whisker_verdicts={pid: VERDICT_PASS},
            tapetum_verdicts={pid: VERDICT_PASS},
        )
        whisker_path = tmp_path / "whisker" / "det" / "p0001.whisker.json"
        whisker = json.loads(whisker_path.read_text(encoding="utf-8"))
        whisker[field] = value
        whisker_path.write_text(json.dumps(whisker), encoding="utf-8")

        _build_merged_report(_MergedReportBackend(tmp_path, [pid]))

        report_path = tmp_path / "whisker" / "llm" / "report-merged.json"
        rows = json.loads(report_path.read_text(encoding="utf-8"))
        assert rows[0]["pid"] == pid
        assert rows[0]["det"] == "?"

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            *(("pid", value) for value in _INVALID_PID_VALUES),
            ("suggested_verdict", []),
            *(("confidence", value) for value in _INVALID_CONFIDENCE_VALUES),
        ],
    )
    def test_fuse_only_skips_invalid_tapetum_object(
        self, tmp_path, field, value
    ):
        from whisker.llm.cli import _fuse_only

        pid = "P0001"
        _seed_sidecars(
            tmp_path,
            [pid],
            whisker_verdicts={pid: VERDICT_PASS},
            tapetum_verdicts={pid: VERDICT_PASS},
        )
        tap_path = (
            tmp_path / "whisker" / "llm" / "p0001.whisker.tapetum.json"
        )
        tapetum = json.loads(tap_path.read_text(encoding="utf-8"))
        tapetum[field] = value
        original = json.dumps(tapetum)
        tap_path.write_text(original, encoding="utf-8")

        _fuse_only(_MergedReportBackend(tmp_path, [pid]), inspect=False)

        assert tap_path.read_text(encoding="utf-8") == original

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            *(("pid", value) for value in _INVALID_PID_VALUES),
            ("verdict", []),
        ],
    )
    def test_fuse_only_uses_stub_for_invalid_whisker_object(
        self, tmp_path, field, value
    ):
        from whisker.llm.cli import _fuse_only

        pid = "P0001"
        _seed_sidecars(
            tmp_path,
            [pid],
            whisker_verdicts={pid: VERDICT_PASS},
            tapetum_verdicts={pid: VERDICT_PASS},
        )
        whisker_path = tmp_path / "whisker" / "det" / "p0001.whisker.json"
        whisker = json.loads(whisker_path.read_text(encoding="utf-8"))
        whisker[field] = value
        whisker_path.write_text(json.dumps(whisker), encoding="utf-8")

        _fuse_only(_MergedReportBackend(tmp_path, [pid]), inspect=False)

        tap_path = (
            tmp_path / "whisker" / "llm" / "p0001.whisker.tapetum.json"
        )
        tapetum = json.loads(tap_path.read_text(encoding="utf-8"))
        assert tapetum["fusion"]["whisker_verdict"] == "?"

    @pytest.mark.parametrize("fingerprint", _INVALID_FINGERPRINT_VALUES)
    def test_full_report_ignores_malformed_fingerprint(
        self, tmp_path, fingerprint
    ):
        from whisker.llm.cli import _build_merged_report

        pid = "P0001"
        _seed_sidecars(
            tmp_path,
            [pid],
            whisker_verdicts={pid: VERDICT_PASS},
            tapetum_verdicts={pid: VERDICT_PASS},
        )
        tap_path = (
            tmp_path / "whisker" / "llm" / "p0001.whisker.tapetum.json"
        )
        tapetum = json.loads(tap_path.read_text(encoding="utf-8"))
        tapetum["fingerprint"] = fingerprint
        tap_path.write_text(json.dumps(tapetum), encoding="utf-8")

        _build_merged_report(_MergedReportBackend(tmp_path, [pid]))

        report_path = tmp_path / "whisker" / "llm" / "report-merged.json"
        rows = json.loads(report_path.read_text(encoding="utf-8"))
        assert rows[0]["llm"] == VERDICT_PASS

    @pytest.mark.parametrize("fingerprint", _INVALID_FINGERPRINT_VALUES)
    def test_fuse_only_removes_malformed_fingerprint(
        self, tmp_path, fingerprint
    ):
        from whisker.llm.cli import _fuse_only

        pid = "P0001"
        _seed_sidecars(
            tmp_path,
            [pid],
            whisker_verdicts={pid: VERDICT_PASS},
            tapetum_verdicts={pid: VERDICT_PASS},
        )
        tap_path = (
            tmp_path / "whisker" / "llm" / "p0001.whisker.tapetum.json"
        )
        tapetum = json.loads(tap_path.read_text(encoding="utf-8"))
        tapetum["fingerprint"] = fingerprint
        tap_path.write_text(json.dumps(tapetum), encoding="utf-8")

        _fuse_only(_MergedReportBackend(tmp_path, [pid]), inspect=False)

        rewritten = json.loads(tap_path.read_text(encoding="utf-8"))
        assert "fingerprint" not in rewritten
        assert rewritten["fusion"]["combined_verdict"] == VERDICT_PASS

    def test_full_run_produces_merged_report(self, tmp_path):
        from whisker.llm.cli import _build_merged_report

        pids = ["P0001", "P0002"]
        _seed_sidecars(
            tmp_path, pids,
            whisker_verdicts={"P0001": VERDICT_PASS, "P0002": VERDICT_REVIEW},
            tapetum_verdicts={"P0001": VERDICT_PASS, "P0002": VERDICT_REVIEW},
        )
        backend = _MergedReportBackend(tmp_path, pids)
        _build_merged_report(backend)

        md = tmp_path / "whisker" / "llm" / "report-merged.md"
        js = tmp_path / "whisker" / "llm" / "report-merged.json"
        assert md.exists(), "report-merged.md not written"
        assert js.exists(), "report-merged.json not written"

        rows = json.loads(js.read_text(encoding="utf-8"))
        assert len(rows) == 2
        row_pids = {r["pid"] for r in rows}
        assert row_pids == {"P0001", "P0002"}

    def test_no_tapetum_sidecars_skips_gracefully(self, tmp_path):
        from whisker.llm.cli import _build_merged_report

        pids = ["P0001"]
        _seed_sidecars(tmp_path, pids, whisker_verdicts={"P0001": VERDICT_PASS})
        backend = _MergedReportBackend(tmp_path, pids)
        _build_merged_report(backend)

        md = tmp_path / "whisker" / "llm" / "report-merged.md"
        assert not md.exists(), "should not write merged report without tapetum sidecars"

    def test_error_tombstone_falls_back_to_deterministic(self, tmp_path):
        from whisker.llm.cli import _build_merged_report

        pids = ["P0001", "P0002"]
        _seed_sidecars(
            tmp_path, pids,
            whisker_verdicts={"P0001": VERDICT_PASS, "P0002": VERDICT_FAIL},
            tapetum_verdicts={"P0001": VERDICT_PASS},
        )
        # P0002 has whisker sidecar but no tapetum -> falls back to det verdict
        llm_dir = tmp_path / "whisker" / "llm"
        error_stub = {"pid": "P0002", "status": "error", "suggested_verdict": "review", "confidence": 0.0}
        (llm_dir / "p0002.whisker.tapetum.json").write_text(
            json.dumps(error_stub), encoding="utf-8",
        )
        backend = _MergedReportBackend(tmp_path, pids)
        _build_merged_report(backend)

        js = tmp_path / "whisker" / "llm" / "report-merged.json"
        assert js.exists()
        rows = json.loads(js.read_text(encoding="utf-8"))
        p2_row = [r for r in rows if r["pid"] == "P0002"][0]
        assert p2_row["merged"] == VERDICT_FAIL

    def test_fuse_only_and_full_run_produce_same_aggregate(self, tmp_path):
        """Verify _build_merged_report output matches _fuse_only aggregate."""
        from whisker.llm.cli import _build_merged_report

        pids = ["P0001", "P0002"]
        _seed_sidecars(
            tmp_path, pids,
            whisker_verdicts={"P0001": VERDICT_PASS, "P0002": VERDICT_REVIEW},
            tapetum_verdicts={"P0001": VERDICT_PASS, "P0002": VERDICT_REVIEW},
        )
        backend = _MergedReportBackend(tmp_path, pids)
        _build_merged_report(backend)

        js = tmp_path / "whisker" / "llm" / "report-merged.json"
        rows_full = json.loads(js.read_text(encoding="utf-8"))

        # Running _build_merged_report again must produce identical output
        _build_merged_report(backend)
        rows_again = json.loads(js.read_text(encoding="utf-8"))
        assert rows_full == rows_again

    def test_uncovered_whisker_papers_included(self, tmp_path):
        """Papers with whisker sidecar but no tapetum sidecar appear in aggregate."""
        from whisker.llm.cli import _build_merged_report

        pids = ["P0001", "P0002"]
        _seed_sidecars(
            tmp_path, pids,
            whisker_verdicts={"P0001": VERDICT_PASS, "P0002": VERDICT_REVIEW},
            tapetum_verdicts={"P0001": VERDICT_PASS},
        )
        backend = _MergedReportBackend(tmp_path, pids)
        _build_merged_report(backend)

        js = tmp_path / "whisker" / "llm" / "report-merged.json"
        rows = json.loads(js.read_text(encoding="utf-8"))
        row_pids = {r["pid"] for r in rows}
        assert "P0002" in row_pids
        p2_row = [r for r in rows if r["pid"] == "P0002"][0]
        assert p2_row["llm"] == "-"
        assert p2_row["merged"] == VERDICT_REVIEW


class TestInspectWithFusion:
    """Verify that inspect pairs carry fusion data during normal runs."""

    def test_inspect_pair_has_fusion(self):
        """Simulate what _adjudicate_one now does: add fusion to inspect pairs."""
        w = _whisker(VERDICT_REVIEW, soft=["x"], ref_nid=0.9, pid="TEST1")
        t = _tapetum(VERDICT_PASS)
        t["pid"] = "TEST1"
        fusion = fuse_verdicts(w, t).to_dict()
        t["fusion"] = fusion

        report = format_report([(w, t)])
        assert "merged rollup" in report
        assert "1 pass" in report

    def test_inspect_without_fusion_omits_rollup(self):
        """Pair without fusion block must not produce a merged rollup."""
        w = _whisker(VERDICT_REVIEW, soft=["x"], ref_nid=0.9, pid="TEST2")
        t = _tapetum(VERDICT_PASS)
        t["pid"] = "TEST2"

        report = format_report([(w, t)])
        assert "merged rollup" not in report
