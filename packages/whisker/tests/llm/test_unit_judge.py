#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the source-aware unit judge orchestration layer."""

import asyncio

import pytest
from whisker.llm.models import (
    DefectFinding,
    MetadataOutlineCheck,
    UnitCheck,
)
from whisker.llm.source_router import RiskSignal
from whisker.llm.unit_judge import (
    _TABLE_SIGNAL_TYPES,
    CONVERSION_CONTRACT,
    METADATA_CHECK_SYSTEM_PROMPT,
    UNIT_CHECK_SYSTEM_PROMPT,
    UnitJudgeResult,
    _aggregate_defects,
    _check_one_unit,
    _signal_to_dict,
    run_metadata_outline_check,
    run_unit_checks,
    verify_defect_counts,
)


class TestSignalToDict:
    def test_dict_passthrough(self):
        signal = {"unit_id": "page:3", "signal_type": "low_recall", "severity": "high", "detail": "x"}
        assert _signal_to_dict(signal) == signal

    def test_risksignal_conversion(self):
        from whisker.llm.source_router import RiskSignal

        sig = RiskSignal("page:5", "token_delta", "medium", "constexpr delta")
        result = _signal_to_dict(sig)
        assert result == {
            "unit_id": "page:5",
            "signal_type": "token_delta",
            "severity": "medium",
            "detail": "constexpr delta",
        }


class TestAggregateDefects:
    def test_empty(self):
        assert _aggregate_defects([]) == []

    def test_single_defect(self):
        defects = [{
            "defect_type": "qualifier_omission",
            "affected_count": 10,
            "severity": "critical",
            "source_unit": "pages:1-5",
            "source_quote": "constexpr float logb(float x)",
        }]
        groups = _aggregate_defects(defects)
        assert len(groups) == 1
        assert groups[0]["defect_type"] == "qualifier_omission"
        assert groups[0]["affected_count"] == 10
        assert groups[0]["severity"] == "critical"

    def test_merges_same_type(self):
        defects = [
            {"defect_type": "content_omission", "affected_count": 3, "severity": "high", "source_quote": "a"},
            {"defect_type": "content_omission", "affected_count": 2, "severity": "medium", "source_quote": "b"},
        ]
        groups = _aggregate_defects(defects)
        assert len(groups) == 1
        assert groups[0]["affected_count"] == 5
        assert groups[0]["severity"] == "high"

    def test_different_types_separate(self):
        defects = [
            {"defect_type": "qualifier_omission", "affected_count": 151, "severity": "critical", "source_quote": "x"},
            {"defect_type": "toc_leak", "affected_count": 1, "severity": "high", "source_quote": "y"},
        ]
        groups = _aggregate_defects(defects)
        assert len(groups) == 2
        assert groups[0]["defect_type"] == "qualifier_omission"
        assert groups[1]["defect_type"] == "toc_leak"

    def test_sorted_by_severity_then_count(self):
        defects = [
            {"defect_type": "punctuation_loss", "affected_count": 50, "severity": "low", "source_quote": "a"},
            {"defect_type": "code_loss", "affected_count": 3, "severity": "critical", "source_quote": "b"},
            {"defect_type": "heading_drift", "affected_count": 5, "severity": "high", "source_quote": "c"},
        ]
        groups = _aggregate_defects(defects)
        assert groups[0]["defect_type"] == "code_loss"
        assert groups[1]["defect_type"] == "heading_drift"
        assert groups[2]["defect_type"] == "punctuation_loss"

    def test_examples_capped_at_3(self):
        defects = [
            {"defect_type": "x", "affected_count": 1, "severity": "low", "source_quote": f"q{i}"}
            for i in range(10)
        ]
        groups = _aggregate_defects(defects)
        assert len(groups[0]["examples"]) == 3


class TestUnitJudgeResult:
    def test_has_verified_defects_true(self):
        result = UnitJudgeResult(
            risk_signals=[],
            unit_results=[],
            defect_groups=[{"defect_type": "x", "affected_count": 1}],
            verdict="review",
        )
        assert result.has_verified_defects()

    def test_has_verified_defects_false(self):
        result = UnitJudgeResult(
            risk_signals=[],
            unit_results=[],
            defect_groups=[],
            verdict="pass",
        )
        assert not result.has_verified_defects()


class _UnitAgent:
    service_name = "stub"

    def __init__(self, result: UnitCheck | Exception) -> None:
        self.result = result
        self.calls = 0
        self.last_system_prompt = ""
        self.last_user_message = ""

    async def run(self, system_prompt, user_message, output_type, **kwargs):
        self.calls += 1
        self.last_system_prompt = system_prompt
        self.last_user_message = user_message
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class TestRunUnitChecksFailClosed:
    def test_missing_unit_text_is_unroutable(self):
        """A routed unit without source text is unroutable, not unchecked.

        With Fix 1 (v10), packet-less routed units are pre-filtered before
        quota selection.  They no longer burn cap slots or force
        coverage_complete=false.
        """
        signal = RiskSignal("page:9", "low_recall", "high", "missing packet")
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "# Candidate",
            _UnitAgent(RuntimeError("must not run")),
            risk_signals=[signal],
            unit_text_map={},
        ))
        assert result is not None
        assert result.verdict == "pass"
        assert result.coverage_complete is True
        assert result.unchecked_unit_ids == []
        assert result.unroutable_unit_ids == ["page:9"]

    def test_failed_unit_call_forces_review(self):
        signal = RiskSignal("page:2", "low_recall", "high", "missing prose")
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "# Candidate",
            _UnitAgent(RuntimeError("pod unavailable")),
            risk_signals=[signal],
            unit_text_map={"page:2": "source prose that should be checked"},
        ))
        assert result is not None
        assert result.verdict == "review"
        assert result.coverage_complete is False
        assert result.failed_unit_ids == ["page:2"]

    def test_refuted_defect_does_not_demote_pass(self):
        quote = "constexpr int preserved_value"
        check = UnitCheck(
            reasoning="claimed omission",
            unit_id="page:1",
            defects=[
                DefectFinding(
                    defect_type="qualifier_omission",
                    source_unit="page:1",
                    source_quote=quote,
                    affected_count=1,
                    severity="high",
                    reasoning="keyword allegedly absent",
                )
            ],
            verdict="not-llm-readable",
            confidence=0.99,
        )
        result = asyncio.run(run_unit_checks(
            "P1R0",
            quote,
            _UnitAgent(check),
            risk_signals=[
                RiskSignal("page:1", "token_delta", "high", "constexpr delta")
            ],
            unit_text_map={"page:1": quote},
        ))
        assert result is not None
        assert result.verdict == "pass"
        assert result.defect_groups == []
        assert result.evidence_summary["present_in_candidate"] == 1

    def test_source_ungrounded_defect_forces_review_without_group(self):
        check = UnitCheck(
            reasoning="claimed omission",
            unit_id="page:1",
            defects=[
                DefectFinding(
                    defect_type="content_omission",
                    source_unit="page:1",
                    source_quote="this quote is absent from the source packet",
                    affected_count=1,
                    severity="high",
                    reasoning="prose allegedly absent",
                )
            ],
            verdict="not-llm-readable",
            confidence=0.99,
        )
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "# Candidate",
            _UnitAgent(check),
            risk_signals=[
                RiskSignal("page:1", "low_recall", "high", "missing prose")
            ],
            unit_text_map={"page:1": "different source prose"},
        ))
        assert result is not None
        assert result.verdict == "review"
        assert result.defect_groups == []
        assert result.evidence_summary["source_ungrounded"] == 1

    def test_candidate_ambiguous_defect_forces_review_without_group(self):
        quote = "value <= limit"
        check = UnitCheck(
            reasoning="claimed operator loss",
            unit_id="page:1",
            defects=[
                DefectFinding(
                    defect_type="punctuation_loss",
                    source_unit="page:1",
                    source_quote=quote,
                    affected_count=1,
                    severity="high",
                    reasoning="operator allegedly changed",
                )
            ],
            verdict="not-llm-readable",
            confidence=0.99,
        )
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "value >= limit",
            _UnitAgent(check),
            risk_signals=[
                RiskSignal("page:1", "token_delta", "high", "operator drift")
            ],
            unit_text_map={"page:1": quote},
        ))
        assert result is not None
        assert result.verdict == "review"
        assert result.defect_groups == []
        assert result.evidence_summary["ambiguous"] == 1

    @pytest.mark.parametrize(
        ("quote", "candidate"),
        [
            ('value = "x"', "value = x"),
            (r'value = "\x"', 'value = "x"'),
            ("x ≤ y", "x ≥ y"),
        ],
    )
    def test_syntax_bearing_candidate_drift_is_ambiguous(
        self,
        quote,
        candidate,
    ):
        check = UnitCheck(
            reasoning="claimed syntax loss",
            unit_id="page:1",
            defects=[
                DefectFinding(
                    defect_type="punctuation_loss",
                    source_unit="page:1",
                    source_quote=quote,
                    affected_count=1,
                    severity="high",
                    reasoning="syntax allegedly changed",
                )
            ],
            verdict="not-llm-readable",
            confidence=0.99,
        )
        result = asyncio.run(run_unit_checks(
            "P1R0",
            candidate,
            _UnitAgent(check),
            risk_signals=[
                RiskSignal("page:1", "token_delta", "high", "syntax drift")
            ],
            unit_text_map={"page:1": quote},
        ))
        assert result is not None
        assert result.verdict == "review"
        assert result.defect_groups == []
        assert result.evidence_summary["ambiguous"] == 1

    def test_fuzzy_source_grounding_forces_review_without_group(self):
        quote = "The implementation stratexy for contracts is described below"
        check = UnitCheck(
            reasoning="claimed omission",
            unit_id="page:1",
            defects=[
                DefectFinding(
                    defect_type="content_omission",
                    source_unit="page:1",
                    source_quote=quote,
                    affected_count=1,
                    severity="high",
                    reasoning="prose allegedly absent",
                )
            ],
            verdict="not-llm-readable",
            confidence=0.99,
        )
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "# Candidate",
            _UnitAgent(check),
            risk_signals=[
                RiskSignal("page:1", "low_recall", "high", "missing prose")
            ],
            unit_text_map={
                "page:1": (
                    "The implementation strategy for contracts is described below"
                )
            },
        ))
        assert result is not None
        disposition = result.unit_results[0]["evidence_dispositions"][0]
        assert disposition["source_status"] == "fuzzy"
        assert disposition["candidate_status"] == "candidate_not_found"
        assert result.verdict == "review"
        assert result.defect_groups == []

    def test_source_operator_mismatch_is_not_mechanically_exact(self):
        quote = "value <= limit"
        check = UnitCheck(
            reasoning="claimed omission",
            unit_id="page:1",
            defects=[
                DefectFinding(
                    defect_type="punctuation_loss",
                    source_unit="page:1",
                    source_quote=quote,
                    affected_count=1,
                    severity="high",
                    reasoning="operator allegedly omitted",
                )
            ],
            verdict="not-llm-readable",
            confidence=0.99,
        )
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "# Candidate",
            _UnitAgent(check),
            risk_signals=[
                RiskSignal("page:1", "token_delta", "high", "operator drift")
            ],
            unit_text_map={"page:1": "value >= limit"},
        ))
        assert result is not None
        disposition = result.unit_results[0]["evidence_dispositions"][0]
        assert disposition["source_status"] == "fuzzy"
        assert result.verdict == "review"
        assert result.defect_groups == []

    def test_multiple_signals_for_one_unit_make_one_call_and_one_count(
        self, monkeypatch,
    ):
        # Isolate from the verdict-first bifurcation (a separate feature):
        # under it, a genuine fail always costs a Stage 1 Clear attempt
        # before falling through to Stage 2 Defects, which is that
        # feature's own concern, not this signal-grouping dedup contract's.
        monkeypatch.setenv("TAPETUM_VERDICT_FIRST", "0")
        quote = "void f() noexcept"
        check = UnitCheck(
            reasoning="missing qualifier",
            unit_id="page:1",
            defects=[
                DefectFinding(
                    defect_type="qualifier_omission",
                    source_unit="page:1",
                    source_quote=quote,
                    affected_count=1,
                    severity="high",
                    reasoning="noexcept is absent",
                )
            ],
            verdict="not-llm-readable",
            confidence=0.99,
        )
        agent = _UnitAgent(check)
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "void f()",
            agent,
            risk_signals=[
                RiskSignal("page:1", "token_delta", "high", "noexcept delta"),
                RiskSignal("page:1", "low_recall", "medium", "declaration drift"),
            ],
            unit_text_map={"page:1": quote},
        ))
        assert result is not None
        assert agent.calls == 1
        assert len(result.defect_groups) == 1
        assert result.defect_groups[0]["verified_count"] == 1


class TestMetadataOutlineCheck:
    def test_always_compares_source_and_candidate_packets(self):
        check = MetadataOutlineCheck(
            reasoning="metadata and headings match",
            title_matches=True,
            document_number_matches=True,
            date_matches=True,
            heading_drift=[],
            missing_sections=[],
            verdict="pass",
        )
        agent = _UnitAgent(check)
        result = asyncio.run(run_metadata_outline_check(
            "P1R0",
            "Title: Example\nDocument: P1R0\nDate: 2026-01-01",
            ["h2: Abstract", "h2: References"],
            "---\ntitle: Example\ndocument: P1R0\ndate: 2026-01-01\n---\n\n"
            "## Abstract\n\nText\n\n## References",
            agent,
        ))
        assert result.verdict == "pass"
        assert agent.calls == 1
        assert "SOURCE METADATA" in agent.last_user_message
        assert "SOURCE OUTLINE" in agent.last_user_message
        assert "CANDIDATE FRONT MATTER" in agent.last_user_message
        assert "CANDIDATE HEADINGS" in agent.last_user_message

    def test_contract_ignores_sanctioned_source_toc_chrome(self):
        check = MetadataOutlineCheck(
            reasoning="metadata and headings match",
            title_matches=True,
            document_number_matches=True,
            date_matches=True,
            heading_drift=[],
            missing_sections=[],
            verdict="pass",
        )
        agent = _UnitAgent(check)
        asyncio.run(run_metadata_outline_check(
            "P1R0",
            "Title: Example",
            ["Contents", "1. Introduction 3", "1. Introduction"],
            "---\ntitle: Example\n---\n\n## 1. Introduction",
            agent,
        ))
        assert METADATA_CHECK_SYSTEM_PROMPT in agent.last_system_prompt
        assert "source table-of-contents entries" in agent.last_system_prompt
        assert "sanctioned source chrome" in agent.last_system_prompt


class TestCheckOneUnitCandidateMdFirst:
    def test_user_message_leads_with_candidate_markdown(self):
        """The shared CANDIDATE MARKDOWN must be the FIRST thing in the
        prompt so its prefix is byte-identical across every unit check for
        a paper (vLLM automatic-prefix-cache reuse)."""
        check = UnitCheck(
            reasoning="unit matches",
            unit_id="page:1",
            defects=[],
            verdict="pass",
            confidence=0.95,
        )
        agent = _UnitAgent(check)
        asyncio.run(_check_one_unit(
            "P1R0", "page:1", "source text", "candidate markdown body",
            "risk detail", agent,
            guard_tag="SRCFEEDFACE",
        ))
        assert agent.last_user_message.startswith("CANDIDATE MARKDOWN:")


class TestVerifiedCounts:
    def test_constexpr_document_delta_is_exact(self):
        groups = [{
            "defect_type": "qualifier_omission",
            "affected_count": 5,
            "severity": "critical",
            "source_unit": "page:1",
            "source_quote": "constexpr float logb(float x)",
            "examples": ["constexpr float logb(float x)"],
        }]
        source = {"page:1": " ".join(["constexpr"] * 231)}
        candidate = " ".join(["constexpr"] * 80)
        verified = verify_defect_counts(groups, source, candidate)
        assert verified[0]["verified_count"] == 151
        assert verified[0]["count_verification"] == {
            "keyword": "constexpr",
            "source_count": 231,
            "candidate_count": 80,
            "verified_delta": 151,
            "count_status": "verified",
        }

    def test_unverified_group_has_no_verified_count(self):
        groups = [{
            "defect_type": "content_omission",
            "affected_count": 7,
            "severity": "high",
            "source_unit": "page:1",
            "source_quote": "missing prose",
            "examples": ["missing prose"],
        }]
        verified = verify_defect_counts(groups, {"page:1": "missing prose"}, "")
        assert verified[0]["verified_count"] is None
        assert verified[0]["count_verification"]["count_status"] == "unverified"

    def test_different_qualifier_keywords_form_separate_groups(self):
        defects = [
            {
                "defect_type": "qualifier_omission",
                "affected_count": 1,
                "severity": "high",
                "source_unit": "page:1",
                "source_quote": "constexpr int source_only",
            },
            {
                "defect_type": "qualifier_omission",
                "affected_count": 1,
                "severity": "high",
                "source_unit": "page:1",
                "source_quote": "void f() noexcept",
            },
        ]
        groups = _aggregate_defects(defects)
        verified = verify_defect_counts(
            groups,
            {"page:1": "constexpr int source_only; void f() noexcept;"},
            "constexpr int replacement; void f();",
        )
        by_keyword = {
            group["count_verification"].get("keyword"): group
            for group in verified
        }
        assert set(by_keyword) == {"constexpr", "noexcept"}
        assert by_keyword["constexpr"]["verified_count"] == 0
        assert by_keyword["noexcept"]["verified_count"] == 1

    def test_zero_delta_for_one_keyword_does_not_erase_another(self):
        check = UnitCheck(
            reasoning="two qualifier claims",
            unit_id="page:1",
            defects=[
                DefectFinding(
                    defect_type="qualifier_omission",
                    source_unit="page:1",
                    source_quote="constexpr int source_only",
                    affected_count=1,
                    severity="high",
                    reasoning="constexpr allegedly omitted",
                ),
                DefectFinding(
                    defect_type="qualifier_omission",
                    source_unit="page:1",
                    source_quote="void f() noexcept",
                    affected_count=1,
                    severity="high",
                    reasoning="noexcept omitted",
                ),
            ],
            verdict="not-llm-readable",
            confidence=0.99,
        )
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "constexpr int replacement; void f();",
            _UnitAgent(check),
            risk_signals=[
                RiskSignal("page:1", "token_delta", "high", "qualifier deltas")
            ],
            unit_text_map={
                "page:1": "constexpr int source_only; void f() noexcept;"
            },
        ))
        assert result is not None
        assert len(result.defect_groups) == 2
        by_keyword = {
            group["count_verification"]["keyword"]: group
            for group in result.defect_groups
        }
        assert by_keyword["constexpr"]["verified_count"] is None
        assert (
            by_keyword["constexpr"]["count_verification"]["location_conflict"]
            is True
        )
        assert by_keyword["noexcept"]["verified_count"] == 1

    def test_single_quote_splits_and_retains_each_whole_word_keyword(self):
        quote = "inline constexpr int source_only"
        check = UnitCheck(
            reasoning="two qualifiers in one quote",
            unit_id="page:1",
            defects=[
                DefectFinding(
                    defect_type="qualifier_omission",
                    source_unit="page:1",
                    source_quote=quote,
                    affected_count=1,
                    severity="high",
                    reasoning="qualifiers allegedly omitted",
                )
            ],
            verdict="not-llm-readable",
            confidence=0.99,
        )
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "constexpr int replacement",
            _UnitAgent(check),
            risk_signals=[
                RiskSignal("page:1", "token_delta", "high", "qualifier deltas")
            ],
            unit_text_map={"page:1": quote},
        ))
        assert result is not None
        assert len(result.defect_groups) == 2
        by_keyword = {
            group["count_verification"]["keyword"]: group
            for group in result.defect_groups
        }
        assert by_keyword["constexpr"]["verified_count"] is None
        assert (
            by_keyword["constexpr"]["count_verification"]["location_conflict"]
            is True
        )
        inline_count = by_keyword["inline"]["count_verification"]
        assert inline_count["source_count"] == 1
        assert inline_count["candidate_count"] == 0
        assert by_keyword["inline"]["verified_count"] == 1

    def test_equal_count_duplicate_elsewhere_preserves_exact_location_defect(self):
        quote = "constexpr int b"
        check = UnitCheck(
            reasoning="specific declaration lost its qualifier",
            unit_id="page:1",
            defects=[
                DefectFinding(
                    defect_type="qualifier_omission",
                    source_unit="page:1",
                    source_quote=quote,
                    affected_count=1,
                    severity="high",
                    reasoning="constexpr is absent at this declaration",
                )
            ],
            verdict="not-llm-readable",
            confidence=0.99,
        )
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "constexpr constexpr int a; int b;",
            _UnitAgent(check),
            risk_signals=[
                RiskSignal("page:1", "token_delta", "high", "constexpr location")
            ],
            unit_text_map={
                "page:1": "constexpr int a; constexpr int b;"
            },
        ))
        assert result is not None
        assert result.verdict == "review"
        assert len(result.defect_groups) == 1
        group = result.defect_groups[0]
        assert group["verified_count"] is None
        assert group["count_verification"] == {
            "keyword": "constexpr",
            "source_count": 2,
            "candidate_count": 2,
            "verified_delta": 0,
            "count_status": "unverified",
            "location_conflict": True,
        }

    def test_equal_count_candidate_present_location_remains_refuted(self):
        quote = "constexpr int a"
        check = UnitCheck(
            reasoning="claimed qualifier omission",
            unit_id="page:1",
            defects=[
                DefectFinding(
                    defect_type="qualifier_omission",
                    source_unit="page:1",
                    source_quote=quote,
                    affected_count=1,
                    severity="high",
                    reasoning="constexpr allegedly absent",
                )
            ],
            verdict="not-llm-readable",
            confidence=0.99,
        )
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "constexpr constexpr int a; int b;",
            _UnitAgent(check),
            risk_signals=[
                RiskSignal("page:1", "token_delta", "high", "constexpr location")
            ],
            unit_text_map={
                "page:1": "constexpr int a; constexpr int b;"
            },
        ))
        assert result is not None
        assert result.verdict == "pass"
        assert result.defect_groups == []
        assert result.evidence_summary["present_in_candidate"] == 1

    def test_exact_location_with_positive_delta_stays_verified(self):
        quote = "constexpr int b"
        check = UnitCheck(
            reasoning="specific declaration lost its qualifier",
            unit_id="page:1",
            defects=[
                DefectFinding(
                    defect_type="qualifier_omission",
                    source_unit="page:1",
                    source_quote=quote,
                    affected_count=1,
                    severity="high",
                    reasoning="constexpr is absent at this declaration",
                )
            ],
            verdict="not-llm-readable",
            confidence=0.99,
        )
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "constexpr int a; int b;",
            _UnitAgent(check),
            risk_signals=[
                RiskSignal("page:1", "token_delta", "high", "constexpr delta")
            ],
            unit_text_map={
                "page:1": "constexpr int a; constexpr int b;"
            },
        ))
        assert result is not None
        assert len(result.defect_groups) == 1
        group = result.defect_groups[0]
        assert group["verified_count"] == 1
        assert group["count_verification"]["count_status"] == "verified"


class TestTableSignalTypes:
    """_TABLE_SIGNAL_TYPES contains only gated table signals (no table_presence)."""

    def test_contains_expected(self):
        assert "table_corruption" in _TABLE_SIGNAL_TYPES
        assert "table_orphan" in _TABLE_SIGNAL_TYPES

    def test_table_presence_excluded(self):
        assert "table_presence" not in _TABLE_SIGNAL_TYPES

    def test_non_table_excluded(self):
        assert "low_recall" not in _TABLE_SIGNAL_TYPES
        assert "token_delta" not in _TABLE_SIGNAL_TYPES


def test_row_loss_signature_in_llm_md():
    """Signature 7 names row_loss and requires not-llm-readable."""
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[2]
        / "src" / "whisker" / "llm" / "llm.md"
    ).read_text(encoding="utf-8")
    assert "7. **row_loss**" in text
    assert "Verdict `not-llm-readable`" in text
    assert "two source rows merged into one pipe row" in text


def test_row_loss_rubric_is_not_llm_readable():
    """The unit rubric counts row_loss toward not-llm-readable."""
    assert "row_loss" in CONVERSION_CONTRACT
    assert "Verdict not-llm-readable, not review." in CONVERSION_CONTRACT
    assert "row_loss" in UNIT_CHECK_SYSTEM_PROMPT
    assert "verdict not-llm-readable" in UNIT_CHECK_SYSTEM_PROMPT


def test_row_loss_verdict_is_not_capped():
    """A row_loss fail is kept when the lost row text is still in the markdown."""
    from whisker.llm.pdf_judge import PdfJudgment, _fold_monolith_verdict

    kept = PdfJudgment(
        verdict="not-llm-readable",
        missing_content=[],
        confidence=0.9,
        reasoning="row_loss: 2026.2 through 2028.2 became headings",
    )
    other = PdfJudgment(
        verdict="not-llm-readable",
        missing_content=[],
        confidence=0.9,
        reasoning="extensive structural reordering",
    )
    assert _fold_monolith_verdict(kept, [], 0) == "not-llm-readable"
    assert _fold_monolith_verdict(other, [], 0) == "review"


class TestUnitCheckPromptContainsFlattenedType:
    """UNIT_CHECK_SYSTEM_PROMPT lists table_flattened as a known defect type."""

    def test_table_flattened_in_prompt(self):
        assert "table_flattened" in UNIT_CHECK_SYSTEM_PROMPT

    def test_table_corruption_still_in_prompt(self):
        assert "table_corruption" in UNIT_CHECK_SYSTEM_PROMPT


class TestTablePageVeto:
    """Page-unit pass is capped to review when table_corruption/orphan signals exist."""

    def test_table_orphan_caps_pass_to_review(self):
        check = UnitCheck(
            unit_id="page:55",
            reasoning="Keywords present",
            defects=[],
            verdict="pass",
            confidence=0.98,
        )
        result = asyncio.run(run_unit_checks(
            "P3400R3",
            "# Candidate with keywords in prose",
            _UnitAgent(check),
            risk_signals=[
                RiskSignal(
                    "page:55", "table_orphan", "critical",
                    "5-col source table has no candidate table on this page",
                ),
            ],
            unit_text_map={"page:55": "keyword1 keyword2 keyword3"},
        ))
        assert result is not None
        vetoed = [
            u for u in result.unit_results
            if u.get("unit_id") == "page:55"
        ]
        assert len(vetoed) == 1
        assert vetoed[0]["verdict"] == "review"
        assert "table-veto" in vetoed[0]["reasoning"]

    def test_table_corruption_caps_pass_to_review(self):
        check = UnitCheck(
            unit_id="page:3",
            reasoning="Content faithfully preserved",
            defects=[],
            verdict="pass",
            confidence=0.95,
        )
        result = asyncio.run(run_unit_checks(
            "PTEST",
            "# Candidate",
            _UnitAgent(check),
            risk_signals=[
                RiskSignal(
                    "page:3", "table_corruption", "critical",
                    "cell (0,2): source 'X' vs candidate ''",
                ),
            ],
            unit_text_map={"page:3": "source with table data"},
        ))
        assert result is not None
        vetoed = [
            u for u in result.unit_results if u.get("unit_id") == "page:3"
        ]
        assert len(vetoed) == 1
        assert vetoed[0]["verdict"] == "review"

    def test_non_table_signal_pass_not_vetoed(self):
        check = UnitCheck(
            unit_id="page:10",
            reasoning="All present",
            defects=[],
            verdict="pass",
            confidence=0.99,
        )
        result = asyncio.run(run_unit_checks(
            "PTEST",
            "# Candidate",
            _UnitAgent(check),
            risk_signals=[
                RiskSignal("page:10", "low_recall", "high", "recall 0.87"),
            ],
            unit_text_map={"page:10": "source prose"},
        ))
        assert result is not None
        unit = [
            u for u in result.unit_results if u.get("unit_id") == "page:10"
        ]
        assert len(unit) == 1
        assert unit[0]["verdict"] == "pass"

    def test_review_unit_not_double_capped(self):
        check = UnitCheck(
            unit_id="page:89",
            reasoning="Bibliography mashed",
            defects=[
                DefectFinding(
                    defect_type="table_corruption",
                    source_unit="page:89",
                    source_quote="[P0001]",
                    affected_count=1,
                    severity="high",
                    reasoning="HTML table merges entries",
                )
            ],
            verdict="review",
            confidence=0.90,
        )
        result = asyncio.run(run_unit_checks(
            "PTEST",
            "# Candidate",
            _UnitAgent(check),
            risk_signals=[
                RiskSignal(
                    "page:89", "table_corruption", "critical",
                    "cell (0,0): source mismatch",
                ),
            ],
            unit_text_map={"page:89": "[P0001] Author, Title"},
        ))
        assert result is not None
        unit = [
            u for u in result.unit_results if u.get("unit_id") == "page:89"
        ]
        assert len(unit) == 1
        assert unit[0]["verdict"] == "review"
        assert "table-veto" not in unit[0].get("reasoning", "")
