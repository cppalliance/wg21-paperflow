#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the tapetum_llm advisory lane.

Covers:
- Hook table matches llm.md step headers.
- Grounding: verbatim, normalized, fuzzy-floor edge, hallucinated.
- Candidate selection logic.
- Adjudication cascade with mocked LLM.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from whisker.llm.models import (
    Adjudication,
    AxisFinding,
    EvidenceSpan,
    IdealVerification,
    TapetumResult,
)

# -- test_hooks_match_tapetum_md -----------------------------------------------


def test_hooks_match_tapetum_md():
    """Assert _build_hooks() keys match the step headers in llm.md."""
    from pipeline import PipelinePrompt, build_pipeline
    from whisker.llm.adjudicate import _build_hooks

    prompt = PipelinePrompt.load("whisker", "llm/llm.md")
    hooks = _build_hooks()

    # build_pipeline raises if hooks don't match steps
    build_pipeline(prompt, hooks)


# -- Grounding tests -----------------------------------------------------------


class TestGrounding:
    def test_verbatim_match(self):
        from whisker.llm.grounding import ground_spans

        md = "The quick brown fox jumps over the lazy dog."
        spans = [EvidenceSpan(axis="wording", quote="brown fox", reason="test")]
        grounded, dropped = ground_spans(spans, md)
        assert len(grounded) == 1
        assert dropped == 0

    def test_whitespace_normalized_match(self):
        from whisker.llm.grounding import ground_spans

        md = "Hello   world   test  content  here"
        spans = [EvidenceSpan(axis="code", quote="Hello world test", reason="spaces")]
        grounded, dropped = ground_spans(spans, md)
        # normalized_text strips all whitespace and non-alnum, so both normalize
        # to the same alnum string
        assert len(grounded) == 1
        assert dropped == 0

    def test_hallucinated_quote_dropped(self):
        from whisker.llm.grounding import ground_spans

        md = "This is a completely different document about cats."
        spans = [
            EvidenceSpan(
                axis="tables",
                quote="The quantum entanglement of parallel universes dictates",
                reason="hallucinated",
            )
        ]
        grounded, dropped = ground_spans(spans, md)
        assert len(grounded) == 0
        assert dropped == 1

    def test_fuzzy_floor_edge(self):
        from whisker.llm.grounding import ground_spans

        md = "abcdefghijklmnopqrstuvwxyz" * 4
        # A very similar quote (one char off) with high partial_ratio
        spans = [
            EvidenceSpan(
                axis="math",
                quote="abcdefghijklmnopqrstuvwxyz" * 3 + "abcdefghijklmnopqrstuvwxy",
                reason="near match",
            )
        ]
        grounded, dropped = ground_spans(spans, md)
        # The partial ratio should be very high (>= 0.90)
        assert len(grounded) == 1
        assert dropped == 0

    def test_empty_spans(self):
        from whisker.llm.grounding import ground_spans

        grounded, dropped = ground_spans([], "some markdown")
        assert grounded == []
        assert dropped == 0

    def test_empty_quote_dropped(self):
        from whisker.llm.grounding import ground_spans

        spans = [EvidenceSpan(axis="wording", quote="", reason="empty")]
        grounded, dropped = ground_spans(spans, "some content")
        assert len(grounded) == 0
        assert dropped == 1


class TestCandidateEvidenceClassification:
    """Candidate-side checks refute missing claims conservatively."""

    @staticmethod
    def _source_grounded(span):
        from whisker.llm.grounding import GROUND_EXACT, GroundedSpan

        return [GroundedSpan(span, GROUND_EXACT, 0, len(span.quote))]

    def _classify(self, quote, candidate, *, axis="wording"):
        from whisker.llm.grounding import classify_candidate_evidence

        span = EvidenceSpan(axis=axis, quote=quote, reason="missing")
        return classify_candidate_evidence(
            self._source_grounded(span),
            candidate,
        )[0]

    def test_exact_candidate_refutes_missing_claim(self):
        from whisker.llm.grounding import CANDIDATE_PRESENT

        result = self._classify(
            "The committee reviewed the wording",
            "## Wording\n\nThe committee reviewed the wording carefully.\n",
        )
        assert result.candidate_status == CANDIDATE_PRESENT
        assert result.candidate_start is not None

    @pytest.mark.parametrize(
        ("quote", "candidate"),
        [
            (
                "Implementations must not throw on empty input.",
                "Implementations must throw on empty input.",
            ),
            (
                "This paper is document P2583R3 dated January.",
                "This paper is document P2583R4 dated January.",
            ),
        ],
    )
    def test_fuzzy_candidate_abstains(self, quote, candidate):
        from whisker.llm.grounding import CANDIDATE_AMBIGUOUS

        result = self._classify(quote, candidate)
        assert result.candidate_status == CANDIDATE_AMBIGUOUS

    def test_operator_mismatch_abstains_despite_token_exact_match(self):
        from whisker.llm.grounding import CANDIDATE_AMBIGUOUS

        result = self._classify(
            "The constraint requires x >= y for all T.",
            "The constraint requires x <= y for all T.",
            axis="code",
        )
        assert result.candidate_status == CANDIDATE_AMBIGUOUS

    @pytest.mark.parametrize(
        ("axis", "quote", "candidate"),
        [
            ("code", 'value = "x"', "value = x"),
            ("code", r'value = "\x"', 'value = "x"'),
            ("math", "x ≤ y", "x ≥ y"),
        ],
    )
    def test_unicode_syntax_parity_mismatch_abstains(
        self,
        axis,
        quote,
        candidate,
    ):
        from whisker.llm.grounding import CANDIDATE_AMBIGUOUS

        result = self._classify(quote, candidate, axis=axis)
        assert result.candidate_status == CANDIDATE_AMBIGUOUS

    @pytest.mark.parametrize(
        ("quote", "candidate"),
        [
            ("CaseSensitiveName", "casesensitivename"),
            ("declaration.", "declaration;"),
            ("first; second", "first, second"),
            ("value, therefore", "value. therefore"),
            ("#define VALUE", "define VALUE"),
            ("array[index]", "array index"),
            ("f(x)", "f{x}"),
            ("condition ? yes : no", "condition ! yes : no"),
            ("value * factor", "value factor"),
            ("value++;", "value--;"),
        ],
    )
    def test_case_and_semantic_punctuation_mismatch_abstains(
        self,
        quote,
        candidate,
    ):
        from whisker.llm.grounding import CANDIDATE_AMBIGUOUS

        result = self._classify(quote, candidate, axis="structure")
        assert result.candidate_status == CANDIDATE_AMBIGUOUS

    def test_exact_syntax_bearing_punctuation_refutes_missing(self):
        from whisker.llm.grounding import CANDIDATE_PRESENT

        result = self._classify("f(x)", "f(x)", axis="structure")
        assert result.candidate_status == CANDIDATE_PRESENT

    def test_canonical_front_matter_intent_is_case_insensitive(self):
        from whisker.llm.grounding import CANDIDATE_PRESENT

        result = self._classify(
            "Inform",
            "---\ntitle: Paper\nintent: inform\n---\n\n## Abstract\n",
            axis="structure",
        )
        assert result.candidate_status == CANDIDATE_PRESENT

    def test_stable_name_does_not_use_metadata_case_exception(self):
        from whisker.llm.grounding import CANDIDATE_AMBIGUOUS

        result = self._classify(
            "Inform",
            "---\ntitle: Paper\nintent: inform\n---\n",
            axis="stable_names",
        )
        assert result.candidate_status == CANDIDATE_AMBIGUOUS

    def test_exact_quote_keeps_trailing_operators_in_interval(self):
        from whisker.llm.grounding import CANDIDATE_PRESENT

        quote = "constexpr int value++;"
        result = self._classify(quote, quote, axis="code")
        assert result.candidate_status == CANDIDATE_PRESENT
        assert result.candidate_end == len(quote)

    @pytest.mark.parametrize(
        ("quote", "candidate"),
        [("x + y", "x - y"), ("x < y", "x > y")],
    )
    def test_single_operator_mismatch_abstains_for_pdf_structure_axis(
        self,
        quote,
        candidate,
    ):
        from whisker.llm.grounding import CANDIDATE_AMBIGUOUS

        result = self._classify(quote, candidate, axis="structure")
        assert result.candidate_status == CANDIDATE_AMBIGUOUS

    def test_unlocated_candidate_is_not_claimed_verified_absent(self):
        from whisker.llm.grounding import CANDIDATE_NOT_FOUND

        result = self._classify(
            "constexpr float logb(float x);",
            "## Wording\n\nNo declaration is present here.\n",
            axis="code",
        )
        assert result.candidate_status == CANDIDATE_NOT_FOUND

    @pytest.mark.parametrize(
        ("quote", "candidate"),
        [
            (
                "See P1234R5 for wording.",
                "See [P1234R5](P1234R5.html) for wording.",
            ),
            (
                "This important word is preserved.",
                "This _important_ word is preserved.",
            ),
        ],
    )
    def test_markdown_markup_equivalence_refutes_missing(self, quote, candidate):
        from whisker.llm.grounding import CANDIDATE_PRESENT

        result = self._classify(quote, candidate)
        assert result.candidate_status == CANDIDATE_PRESENT

    def test_front_matter_migration_abstains(self):
        from whisker.llm.grounding import CANDIDATE_AMBIGUOUS

        result = self._classify(
            "Date: February 22, 2026",
            '---\ntitle: "Paper"\ndocument: P1234R0\ndate: 2026-02-22\n---\n',
        )
        assert result.candidate_status == CANDIDATE_AMBIGUOUS

    def test_html_table_reformat_refutes_missing(self):
        from whisker.llm.grounding import CANDIDATE_PRESENT

        result = self._classify(
            "Processor architecture Compiler family Version",
            (
                "<table><tr><td>Processor architecture</td>"
                "<td>Compiler family</td><td>Version</td></tr></table>"
            ),
            axis="tables",
        )
        assert result.candidate_status == CANDIDATE_PRESENT

    def test_pipe_table_cell_reorder_abstains(self):
        from whisker.llm.grounding import CANDIDATE_AMBIGUOUS

        result = self._classify(
            "A 1 B 2",
            "| A | B |\n| --- | --- |\n| 1 | 2 |\n",
            axis="tables",
        )
        assert result.candidate_status == CANDIDATE_AMBIGUOUS

    def test_math_surface_with_same_operators_refutes_missing(self):
        from whisker.llm.grounding import CANDIDATE_PRESENT

        result = self._classify(
            "E = mc^2",
            "The relation is $E = mc^{2}$.\n",
            axis="math",
        )
        assert result.candidate_status == CANDIDATE_PRESENT

    @pytest.mark.parametrize("quote", ["Table of Contents", "P1234R0 7", "Page 7"])
    def test_sanctioned_toc_and_page_furniture_abstain(self, quote):
        from whisker.llm.grounding import CANDIDATE_AMBIGUOUS

        result = self._classify(quote, "## Introduction\n\nBody text.\n")
        assert result.candidate_status == CANDIDATE_AMBIGUOUS

    @pytest.mark.parametrize(
        ("quote", "candidate"),
        [
            ("1 Introduction 3", "## 1 Introduction\n\nBody.\n"),
            ("P1234R0 2026-02-22 Smith", "## Introduction\n\nBody.\n"),
        ],
    )
    def test_toc_entry_and_running_header_abstain(self, quote, candidate):
        from whisker.llm.grounding import CANDIDATE_AMBIGUOUS

        result = self._classify(quote, candidate)
        assert result.candidate_status == CANDIDATE_AMBIGUOUS

    def test_code_fence_reformat_refutes_missing(self):
        from whisker.llm.grounding import CANDIDATE_PRESENT

        result = self._classify(
            "constexpr int answer = 42;",
            "```cpp\nconstexpr int answer = 42;\n```\n",
            axis="code",
        )
        assert result.candidate_status == CANDIDATE_PRESENT

    def test_unicode_math_reformat_abstains(self):
        from whisker.llm.grounding import CANDIDATE_AMBIGUOUS

        result = self._classify(
            "x^2",
            "The result is x².\n",
            axis="math",
        )
        assert result.candidate_status == CANDIDATE_AMBIGUOUS

    def test_repeated_quotes_map_deterministically(self):
        from whisker.llm.grounding import (
            CANDIDATE_PRESENT,
            GROUND_EXACT,
            GroundedSpan,
            classify_candidate_evidence,
        )

        span1 = EvidenceSpan(axis="wording", quote="same quote", reason="first")
        span2 = EvidenceSpan(axis="wording", quote="same quote", reason="second")
        results = classify_candidate_evidence(
            [
                GroundedSpan(span1, GROUND_EXACT, 0, 10),
                GroundedSpan(span2, GROUND_EXACT, 20, 30),
            ],
            "same quote then same quote",
        )
        assert [result.candidate_status for result in results] == [
            CANDIDATE_PRESENT,
            CANDIDATE_PRESENT,
        ]
        assert results[0].candidate_start < results[1].candidate_start

    @pytest.mark.parametrize("candidate", ["same quote", "same _quote_"])
    def test_duplicate_claims_do_not_reuse_one_candidate_occurrence(
        self,
        candidate,
    ):
        from whisker.llm.grounding import (
            CANDIDATE_AMBIGUOUS,
            CANDIDATE_PRESENT,
            GROUND_EXACT,
            GroundedSpan,
            classify_candidate_evidence,
        )

        first = EvidenceSpan(axis="wording", quote="same quote", reason="first")
        second = EvidenceSpan(axis="wording", quote="same quote", reason="second")
        results = classify_candidate_evidence(
            [
                GroundedSpan(first, GROUND_EXACT, 0, 10),
                GroundedSpan(second, GROUND_EXACT, 20, 30),
            ],
            candidate,
        )
        assert [result.candidate_status for result in results] == [
            CANDIDATE_PRESENT,
            CANDIDATE_AMBIGUOUS,
        ]

    def test_distinct_nested_claims_may_share_candidate_occurrence(self):
        from whisker.llm.grounding import (
            CANDIDATE_PRESENT,
            GROUND_EXACT,
            GroundedSpan,
            classify_candidate_evidence,
        )

        outer = EvidenceSpan(
            axis="code",
            quote="assert(mul + z == sum(mul, z));",
            reason="code anchor",
        )
        inner = EvidenceSpan(
            axis="math",
            quote="mul + z == sum(mul, z)",
            reason="math anchor",
        )
        results = classify_candidate_evidence(
            [
                GroundedSpan(outer, GROUND_EXACT),
                GroundedSpan(inner, GROUND_EXACT),
            ],
            "assert(mul + z == sum(mul, z));",
        )
        assert [result.candidate_status for result in results] == [
            CANDIDATE_PRESENT,
            CANDIDATE_PRESENT,
        ]


# -- Candidate selection tests -------------------------------------------------


class TestCandidateSelection:
    def test_pass_with_lossy_tables(self):
        from whisker.llm.adjudicate import select_candidates

        results = [
            {"pid": "P1234R0", "verdict": "pass", "lossy_table_count": 1,
             "table_parse_errors": 0, "mojibake_count": 0,
             "unigram_coverage": 0.98, "coverage": 0.95}
        ]
        assert select_candidates(results) == ["P1234R0"]

    def test_pass_with_cov_gap(self):
        from whisker.llm.adjudicate import select_candidates

        results = [
            {"pid": "P5678R1", "verdict": "pass", "lossy_table_count": 0,
             "table_parse_errors": 0, "mojibake_count": 0,
             "unigram_coverage": 0.97, "coverage": 0.80}
        ]
        # gap = 0.17 > 0.15 trigger
        assert select_candidates(results) == ["P5678R1"]

    def test_pass_clean_not_selected(self):
        from whisker.llm.adjudicate import select_candidates

        results = [
            {"pid": "P0001R0", "verdict": "pass", "lossy_table_count": 0,
             "table_parse_errors": 0, "mojibake_count": 0,
             "unigram_coverage": 0.98, "coverage": 0.96}
        ]
        assert select_candidates(results) == []

    def test_review_non_benign_selected(self):
        from whisker.llm.adjudicate import select_candidates

        results = [
            {"pid": "P2000R0", "verdict": "review",
             "soft_flags": ["coverage low"], "unigram_coverage": 0.90,
             "coverage": 0.85, "lossy_table_count": 0,
             "table_parse_errors": 0, "mojibake_count": 0}
        ]
        assert select_candidates(results) == ["P2000R0"]

    def test_review_benign_region_skipped(self):
        from whisker.llm.adjudicate import select_candidates

        results = [
            {"pid": "P3000R0", "verdict": "review",
             "soft_flags": ["misaligned region(s)"],
             "unigram_coverage": 0.96, "coverage": 0.93,
             "lossy_table_count": 0, "table_parse_errors": 0,
             "mojibake_count": 0}
        ]
        assert select_candidates(results) == []

    def test_fail_heading_only_rescued(self):
        from whisker.llm.adjudicate import select_candidates

        results = [
            {"pid": "P4000R0", "verdict": "not-llm-readable",
             "hard_flags": ["gate:heading_monotone:heading level jumps H2 -> H4"],
             "soft_flags": [], "unigram_coverage": 0.99, "coverage": 0.97,
             "lossy_table_count": 0, "table_parse_errors": 0,
             "mojibake_count": 0}
        ]
        assert select_candidates(results) == ["P4000R0"]

    def test_fail_non_heading_not_rescued(self):
        from whisker.llm.adjudicate import select_candidates

        results = [
            {"pid": "P5000R0", "verdict": "not-llm-readable",
             "hard_flags": ["coverage below floor"],
             "soft_flags": [], "unigram_coverage": 0.70, "coverage": 0.65,
             "lossy_table_count": 0, "table_parse_errors": 0,
             "mojibake_count": 0}
        ]
        assert select_candidates(results) == []


# -- Adjudication cascade tests (mocked LLM) ----------------------------------


class TestAdjudicateCascade:
    """Test the cascade logic with mocked agent.run calls."""

    @pytest.fixture
    def mock_backend(self):
        backend = MagicMock()
        backend.get_paper_md.return_value = "# Test Paper\n\nSome content here.\n"
        # sidecar_path needs get_paper_md_path
        md_path = MagicMock()
        md_path.stem = "P9999R0"
        backend.get_paper_md_path.return_value = md_path
        # whisker_output_dir needs workspace_dir
        backend.workspace_dir = MagicMock()
        backend.workspace_dir.__truediv__ = lambda self, x: MagicMock(
            exists=lambda: False
        )
        return backend

    def _make_adjudication(self, verdict="pass", confidence=0.9):
        return Adjudication(
            reasoning="Test reasoning",
            axis_findings=[
                AxisFinding(axis="wording", verdict=verdict, severity="none", note="ok"),
            ],
            worst_axis="wording",
            verdict=verdict,
            confidence=confidence,
            evidence_spans=[
                EvidenceSpan(axis="wording", quote="Some content here", reason="present"),
            ],
            primary_concern="none",
        )

    def test_confident_tier1_no_escalation(self, mock_backend):
        """A confident tier1 (outside ambiguous band) should not escalate."""
        from whisker.llm.adjudicate import (
            _custom_adjudicate,
            _custom_triage,
            _PipelineState,
        )

        state = _PipelineState(
            paper_md="# Test Paper\n\nSome content here.\n",
            whisker_signals={"verdict": "review", "soft_flags": ["coverage low"]},
        )

        adj = self._make_adjudication(verdict="pass", confidence=0.85)

        mock_spec = MagicMock()
        mock_spec.step.model = "fast"
        mock_spec.step.name = "1. Triage"
        mock_spec.hooks.agent = None
        mock_spec.hooks.output_type = Adjudication
        mock_spec.step.tools = None
        mock_spec.step.max_output_tokens = 2048
        mock_spec.step.thinking_budget = 1024

        mock_ctx = MagicMock()
        mock_ctx.pid = "P9999R0"
        mock_ctx.inject_untrusted.return_value = "<wrapped>content</wrapped>"
        mock_ctx.prompt.services = {"fast": "b200x2-gemma4", "deep": "h200x8-deepseek-v4-pro", "default": "b200x2-gemma4"}

        with patch("whisker.llm.adjudicate.run_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = adj

            asyncio.run(_custom_triage(state, mock_ctx, mock_spec))
            assert state.tier1 is not None
            assert state.tier1.confidence == 0.85

            mock_run.reset_mock()
            asyncio.run(_custom_adjudicate(state, mock_ctx, mock_spec))
            mock_run.assert_not_called()
            assert state.tier2 is None

    def test_ambiguous_tier1_escalates(self, mock_backend):
        """A tier1 in the ambiguous band should escalate to tier2."""
        from whisker.llm.adjudicate import (
            _custom_adjudicate,
            _custom_triage,
            _PipelineState,
        )

        state = _PipelineState(
            paper_md="# Test Paper\n\nSome content here.\n",
            whisker_signals={"verdict": "review", "soft_flags": []},
        )

        ambiguous_adj = self._make_adjudication(verdict="review", confidence=0.50)
        deep_adj = self._make_adjudication(verdict="pass", confidence=0.80)

        mock_spec = MagicMock()
        mock_spec.step.model = "fast"
        mock_ctx = MagicMock()
        mock_ctx.pid = "P9999R0"
        mock_ctx.inject_untrusted.return_value = "<wrapped>"
        mock_ctx.prompt.services = {"fast": "svc", "deep": "svc2", "default": "svc"}

        with patch("whisker.llm.adjudicate.run_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ambiguous_adj
            asyncio.run(_custom_triage(state, mock_ctx, mock_spec))
            assert state.tier1.confidence == 0.50

            mock_run.return_value = deep_adj
            asyncio.run(_custom_adjudicate(state, mock_ctx, mock_spec))
            assert state.tier2 is not None
            assert state.tier2.confidence == 0.80

    def test_decide_grounds_and_builds_result(self):
        """Decide step grounds evidence and produces TapetumResult."""
        from whisker.llm.adjudicate import _custom_decide, _PipelineState

        paper_md = "# Paper\n\nSome content here with important data.\n"
        state = _PipelineState(
            paper_md=paper_md,
            whisker_signals={"verdict": "review"},
        )
        state.tier1 = Adjudication(
            reasoning="Found issues",
            axis_findings=[
                AxisFinding(axis="tables", verdict="review", severity="minor", note="ok"),
            ],
            worst_axis="tables",
            verdict="review",
            confidence=0.70,
            evidence_spans=[
                EvidenceSpan(axis="tables", quote="important data", reason="present in md"),
                EvidenceSpan(axis="code", quote="totally hallucinated text xyz", reason="fake"),
            ],
            primary_concern="table concern",
        )

        mock_spec = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.pid = "P1111R0"
        mock_ctx.prompt.services = {"fast": "svc-fast", "deep": "svc-deep", "default": "svc-fast"}

        asyncio.run(_custom_decide(state, mock_ctx, mock_spec))

        result = state._result
        assert isinstance(result, TapetumResult)
        assert result.pid == "P1111R0"
        kept_quotes = [e["quote"] for e in result.grounded_evidence]
        assert "important data" in kept_quotes
        # The verbatim quote grounds exactly with a char interval.
        kept = next(e for e in result.grounded_evidence if e["quote"] == "important data")
        assert kept["status"] == "exact"
        assert paper_md[kept["start"]:kept["end"]] == "important data"
        assert result.ungrounded_dropped >= 1

    def test_decide_runs_readability_probes_off_the_event_loop(self, monkeypatch):
        """Sync httpx probes must not block the loop serving other papers."""
        import threading

        from whisker.llm import adjudicate
        from whisker.llm.adjudicate import _custom_decide, _PipelineState

        state = _PipelineState(paper_md="# Paper\n\nBody.\n")
        state.tier1 = Adjudication(
            reasoning="ok",
            axis_findings=[],
            worst_axis="wording",
            verdict="pass",
            confidence=0.9,
            evidence_spans=[],
            primary_concern="",
        )
        seen: dict[str, object] = {}

        def _fake_block(*_args, **_kwargs) -> dict:
            seen["thread"] = threading.current_thread()
            return {}

        monkeypatch.setattr(adjudicate, "build_llm_readability_block", _fake_block)
        mock_ctx = MagicMock()
        mock_ctx.pid = "P1111R0"

        asyncio.run(_custom_decide(state, mock_ctx, MagicMock()))

        assert state._result.llm_readability == {}
        assert seen["thread"] is not threading.main_thread()
        assert "readability" in state.phase_durations

    def test_decide_demotes_on_low_confidence(self):
        """A verdict with confidence below DECISION_FLOOR is demoted to review."""
        from whisker.llm.adjudicate import _custom_decide, _PipelineState

        paper_md = "# Paper\n\nContent for testing.\n"
        state = _PipelineState(
            paper_md=paper_md,
            whisker_signals={"verdict": "review"},
        )
        state.tier1 = Adjudication(
            reasoning="Uncertain",
            axis_findings=[
                AxisFinding(axis="wording", verdict="pass", severity="none", note="ok"),
            ],
            worst_axis="wording",
            verdict="pass",
            confidence=0.0,  # zero confidence (mechanical anomaly) still demotes
            evidence_spans=[],
            primary_concern="none",
        )

        mock_spec = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.pid = "P2222R0"
        mock_ctx.prompt.services = {"fast": "svc", "deep": "svc2", "default": "svc"}

        asyncio.run(_custom_decide(state, mock_ctx, mock_spec))

        result = state._result
        assert result.suggested_verdict == "review"

    def test_decide_demotes_pass_with_all_evidence_dropped(self):
        """#277 cond 1: a confident pass whose evidence was all dropped -> review."""
        from whisker.llm.adjudicate import _custom_decide, _PipelineState

        paper_md = "# Paper\n\nThis document discusses real content.\n"
        state = _PipelineState(
            paper_md=paper_md,
            whisker_signals={"verdict": "pass"},
        )
        state.tier1 = Adjudication(
            reasoning="Looks fine",
            axis_findings=[
                AxisFinding(axis="wording", verdict="pass", severity="none", note="ok"),
            ],
            worst_axis="wording",
            verdict="pass",
            confidence=0.95,
            evidence_spans=[
                EvidenceSpan(
                    axis="wording",
                    quote="completely fabricated text not in the document at all",
                    reason="hallucinated",
                ),
            ],
            primary_concern="none",
        )

        mock_spec = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.pid = "P2770R1"
        mock_ctx.prompt.services = {"fast": "svc", "deep": "svc2", "default": "svc"}

        asyncio.run(_custom_decide(state, mock_ctx, mock_spec))

        result = state._result
        assert result.suggested_verdict == "review", (
            "a pass with all evidence dropped must demote to review"
        )
        assert result.ungrounded_dropped >= 1

    def test_decide_keeps_pass_with_no_evidence(self):
        """Sanctioned empty-evidence pass is NOT demoted (no evidence_spans)."""
        from whisker.llm.adjudicate import _custom_decide, _PipelineState

        paper_md = "# Paper\n\nClean content here.\n"
        state = _PipelineState(
            paper_md=paper_md,
            whisker_signals={"verdict": "pass"},
        )
        state.tier1 = Adjudication(
            reasoning="All good",
            axis_findings=[
                AxisFinding(axis="wording", verdict="pass", severity="none", note="ok"),
            ],
            worst_axis="wording",
            verdict="pass",
            confidence=0.90,
            evidence_spans=[],
            primary_concern="none",
        )

        mock_spec = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.pid = "P2771R0"
        mock_ctx.prompt.services = {"fast": "svc", "deep": "svc2", "default": "svc"}

        asyncio.run(_custom_decide(state, mock_ctx, mock_spec))

        result = state._result
        assert result.suggested_verdict == "pass", (
            "a pass with no evidence_spans must not be demoted"
        )

    def test_decide_demotes_pass_with_fuzzy_only_evidence(self):
        """A pass whose surviving evidence is all fuzzy -> review.

        The paper contains "realcontent" as one token, the quote splits it
        as "real content" (two tokens).  The exact DP fails (token mismatch)
        but the normalized substring check passes ("realcontent" in
        "...realcontent...") -> GROUND_FUZZY.
        """
        from whisker.llm.adjudicate import _custom_decide, _PipelineState

        paper_md = "# Paper\n\nThis document discusses realcontent here.\n"
        state = _PipelineState(
            paper_md=paper_md,
            whisker_signals={"verdict": "pass"},
        )
        state.tier1 = Adjudication(
            reasoning="Looks fine",
            axis_findings=[
                AxisFinding(axis="wording", verdict="pass", severity="none", note="ok"),
            ],
            worst_axis="wording",
            verdict="pass",
            confidence=0.95,
            evidence_spans=[
                EvidenceSpan(
                    axis="wording",
                    quote="real content",
                    reason="present",
                ),
            ],
            primary_concern="none",
        )

        mock_spec = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.pid = "PFUZZY1"
        mock_ctx.prompt.services = {"fast": "svc", "deep": "svc2", "default": "svc"}

        asyncio.run(_custom_decide(state, mock_ctx, mock_spec))

        result = state._result
        assert result.suggested_verdict == "review", (
            "a pass with fuzzy-only evidence must demote to review"
        )

    def test_decide_keeps_pass_with_exact_evidence(self):
        """A pass with at least one exact-grounded span stays pass."""
        from whisker.llm.adjudicate import _custom_decide, _PipelineState

        paper_md = "# Paper\n\nThis document discusses real content.\n"
        state = _PipelineState(
            paper_md=paper_md,
            whisker_signals={"verdict": "pass"},
        )
        state.tier1 = Adjudication(
            reasoning="Looks fine",
            axis_findings=[
                AxisFinding(axis="wording", verdict="pass", severity="none", note="ok"),
            ],
            worst_axis="wording",
            verdict="pass",
            confidence=0.95,
            evidence_spans=[
                EvidenceSpan(
                    axis="wording",
                    quote="This document discusses real content.",
                    reason="verbatim",
                ),
            ],
            primary_concern="none",
        )

        mock_spec = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.pid = "PEXACT1"
        mock_ctx.prompt.services = {"fast": "svc", "deep": "svc2", "default": "svc"}

        asyncio.run(_custom_decide(state, mock_ctx, mock_spec))

        result = state._result
        assert result.suggested_verdict == "pass", (
            "a pass with exact evidence must not be demoted"
        )

    def test_tapetum_result_to_dict_deterministic(self):
        """TapetumResult.to_dict produces sorted, rounded output."""
        r1 = TapetumResult(
            pid="P0001R0",
            whisker_verdict="review",
            suggested_verdict="pass",
            confidence=0.87654321,
            escalated=True,
            tier1_model="gemma4",
            tier2_model="deepseek",
            axis_findings=[
                {"axis": "tables", "verdict": "pass", "severity": "none", "note": "ok"},
                {"axis": "code", "verdict": "pass", "severity": "none", "note": "ok"},
            ],
            grounded_evidence=[
                {"quote": "quote b", "status": "fuzzy", "start": None, "end": None},
                {"quote": "quote a", "status": "exact", "start": 10, "end": 17},
            ],
            ungrounded_dropped=1,
            primary_concern="none",
            reasoning="all good",
        )
        d = r1.to_dict()
        assert d["confidence"] == 0.8765
        assert [e["quote"] for e in d["grounded_evidence"]] == ["quote a", "quote b"]
        assert d["axis_findings"][0]["axis"] == "code"  # sorted by axis
        assert d["axis_findings"][1]["axis"] == "tables"
        assert d["escalation_signals"] == []
        assert d["advisory"] is True


# -- Inspection report tests ---------------------------------------------------


class TestInspectReport:
    def _whisker(self, **kw):
        base = {
            "pid": "P1234R0",
            "verdict": "review",
            "unigram_coverage": 0.95,
            "coverage": 0.80,
            "lossy_table_count": 0,
            "table_parse_errors": 0,
            "mojibake_count": 0,
            "soft_flags": ["coverage low"],
            "hard_flags": [],
        }
        base.update(kw)
        return base

    def _tapetum(self, **kw):
        base = {
            "pid": "P1234R0",
            "whisker_verdict": "review",
            "suggested_verdict": "pass",
            "confidence": 0.82,
            "escalated": False,
            "tier1_model": "gemma4",
            "tier2_model": None,
            "axis_findings": [
                {"axis": "tables", "verdict": "pass", "severity": "none",
                 "note": "ok | fine"},
            ],
            "grounded_evidence": [
                {"quote": "important data", "status": "exact", "start": 42, "end": 56},
            ],
            "ungrounded_dropped": 1,
            "primary_concern": "none",
            "reasoning": "looks clean",
            "advisory": True,
        }
        base.update(kw)
        return base

    def test_section_contains_both_verdicts(self):
        from whisker.llm.inspect_report import format_paper_section

        out = format_paper_section(self._whisker(), self._tapetum())
        assert "## P1234R0" in out
        assert "`review`" in out  # whisker
        assert "`pass`" in out  # tapetum
        assert "DIFFERS" in out

    def test_section_pipe_escaped_in_note(self):
        from whisker.llm.inspect_report import format_paper_section

        out = format_paper_section(self._whisker(), self._tapetum())
        # the note "ok | fine" must not break the markdown table
        assert "ok \\| fine" in out

    def test_section_no_advisory(self):
        from whisker.llm.inspect_report import format_paper_section

        out = format_paper_section(self._whisker(), None)
        assert "no advisory result" in out

    def test_pdf_evidence_dispositions_are_explicit_and_honest(self):
        from whisker.llm.inspect_report import format_paper_section

        tapetum = self._tapetum(
            evidence_dispositions=[
                {
                    "quote": "already preserved",
                    "source_status": "exact",
                    "candidate_status": "present_in_candidate",
                    "page": None,
                },
                {
                    "quote": "possible omission",
                    "source_status": "fuzzy",
                    "candidate_status": "ambiguous",
                    "page": 3,
                },
                {
                    "quote": "not located",
                    "source_status": "exact",
                    "candidate_status": "candidate_not_found",
                    "page": 4,
                },
            ],
            evidence_summary={
                "present_in_candidate": 1,
                "candidate_not_found": 1,
                "ambiguous": 1,
                "source_ungrounded": 0,
            },
        )
        out = format_paper_section(self._whisker(), tapetum)
        assert "Candidate evidence verification" in out
        assert "refuted: present in candidate" in out
        assert "abstained: ambiguous" in out
        assert "candidate text not located (not proof of absence)" in out
        assert "absent from markdown" not in out

    def test_report_counts_and_determinism(self):
        from whisker.llm.inspect_report import format_report

        pairs = [
            (self._whisker(pid="P2"),
             self._tapetum(pid="P2", suggested_verdict="review")),
            (self._whisker(pid="P1"),
             self._tapetum(pid="P1", suggested_verdict="pass")),
        ]
        out1 = format_report(pairs)
        out2 = format_report(pairs)
        assert out1 == out2  # deterministic
        assert "papers: 2" in out1
        assert "adjudicated: 2" in out1
        # P1 differs (pass vs review), P2 agrees (review vs review)
        assert "advisory differs from whisker: 1" in out1

    def _all_pages_tapetum(self, **kw):
        """Schema-v8-style PDF sidecar with all-pages coverage fields."""
        base = self._tapetum(
            all_pages_requested=True,
            page_count=3,
            page_screen=[
                {
                    "page": 1,
                    "recall": 0.95,
                    "tokens": 120,
                    "flagged": False,
                    "skipped": False,
                },
                {
                    "page": 2,
                    "recall": 0.88,
                    "tokens": 90,
                    "flagged": True,
                    "skipped": False,
                },
                {
                    "page": 3,
                    "recall": 0.99,
                    "tokens": 40,
                    "flagged": False,
                    "skipped": False,
                },
            ],
            unit_coverage={
                "mode": "all_pages",
                "coverage_complete": True,
                "checked_unit_ids": ["page:1", "page:2", "page:3"],
                "unchecked_unit_ids": [],
                "failed_unit_ids": [],
            },
            unit_selection={
                "required": ["page:1", "page:2", "page:3"],
                "checked": ["page:1", "page:2", "page:3"],
                "unchecked": [],
                "failed": [],
            },
            defect_groups=[],
        )
        base.update(kw)
        return base

    def test_all_pages_renders_kn_headline_and_per_page_table(self):
        from whisker.llm.inspect_report import format_paper_section

        out = format_paper_section(self._whisker(), self._all_pages_tapetum())
        assert "Pages checked: 3/3 (mode: all_pages)" in out
        assert "| page | tokens | recall | screen flagged | unit check | findings |" in out
        assert "| 1 | 120 | 0.95 | no | checked | 0 |" in out
        assert "| 2 | 90 | 0.88 | yes | checked | 0 |" in out
        assert "| 3 | 40 | 0.99 | no | checked | 0 |" in out

    def test_unchecked_page_produces_warning_list(self):
        from whisker.llm.inspect_report import format_paper_section

        tapetum = self._all_pages_tapetum(
            unit_coverage={
                "mode": "all_pages",
                "coverage_complete": False,
                "checked_unit_ids": ["page:1", "page:3"],
                "unchecked_unit_ids": ["page:2"],
                "failed_unit_ids": [],
            },
            unit_selection={
                "required": ["page:1", "page:2", "page:3"],
                "checked": ["page:1", "page:3"],
                "unchecked": ["page:2"],
                "failed": [],
            },
        )
        out = format_paper_section(self._whisker(), tapetum)
        assert "Pages checked: 2/3 (mode: all_pages)" in out
        assert "warning" in out.lower()
        assert "page:2" in out
        assert "| 2 |" in out and "unchecked" in out

    def test_clean_all_pages_advisory_phrase_never_verified_correct(self):
        from whisker.llm.inspect_report import format_paper_section

        out = format_paper_section(self._whisker(), self._all_pages_tapetum())
        assert (
            "all pages checked, no additional findings (advisory)" in out
        )
        assert "verified correct" not in out

    def test_old_sidecar_omits_page_coverage_section(self):
        from whisker.llm.inspect_report import format_paper_section

        # Old-style: no page_count, all_pages_requested, unit_selection,
        # or unit_coverage.mode. Must render without error and without
        # the new Page coverage section.
        out = format_paper_section(self._whisker(), self._tapetum())
        assert "Pages checked:" not in out
        assert "Page coverage" not in out

    def test_page_coverage_headline_uses_top_level_page_count(self):
        from whisker.llm.inspect_report import format_paper_section

        tapetum = self._all_pages_tapetum(page_count=5)
        out = format_paper_section(self._whisker(), tapetum)
        assert "Pages checked: 3/5 (mode: all_pages)" in out

    def test_page_coverage_falls_back_to_required_when_page_count_missing(self):
        from whisker.llm.inspect_report import format_paper_section

        # Live v8 sidecars shipped without top-level page_count; N must
        # come from unit_selection.required, never render K/0.
        tapetum = self._all_pages_tapetum()
        del tapetum["page_count"]
        tapetum["unit_selection"] = {
            "required": ["page:1", "page:2", "page:3"],
            "checked": ["page:1", "page:3"],
            "unchecked": ["page:2"],
            "failed": [],
        }
        tapetum["unit_coverage"] = {
            "mode": "all_pages",
            "coverage_complete": False,
            "checked_unit_ids": ["page:1", "page:3"],
            "unchecked_unit_ids": ["page:2"],
            "failed_unit_ids": [],
        }
        out = format_paper_section(self._whisker(), tapetum)
        assert "Pages checked: 2/3 (mode: all_pages)" in out
        assert "Pages checked: 2/0" not in out

    def test_unit_dumps_render_as_evidence(self):
        from whisker.llm.inspect_report import format_paper_section

        tapetum = self._tapetum(
            llm_readability={
                "kind": "whisker-table-readability",
                "verdict": "not-llm-readable",
                "model_certified": False,
                "methods_executed": ["deterministic"],
                "rules": [
                    {
                        "id": "R1",
                        "status": "not-llm-readable",
                        "strength": "HARD",
                        "method": "deterministic",
                    },
                ],
                "unit_dumps": {
                    "kind": "whisker-table-unit-dumps",
                    "pid": "N5040",
                    "model": "deepseek-v4-pro",
                    "pass_count": 1,
                    "fail_count": 0,
                    "skip_count": 0,
                    "units": [
                        {
                            "unit_index": 2,
                            "classification": "label_shift",
                            "dump": None,
                            "probe": {
                                "probe_id": "shift-t2",
                                "question": "count",
                                "expected": "shift",
                                "answer": "HEADER: [1]=EMPTY",
                                "passed": True,
                                "latency_ms": 10,
                                "error": False,
                                "skipped": False,
                                "skip_reason": "",
                            },
                        },
                    ],
                },
                "code_readability": {
                    "contract_id": "wg21-codeblock-readability-deepseek-v4",
                    "contract_version": "1.0.0",
                    "verdict": "incomplete",
                    "model_certified": False,
                    "rules": [
                        {
                            "id": "C2",
                            "status": "pass",
                            "strength": "HARD",
                            "method": "deterministic",
                        },
                    ],
                },
                "code_probes": {
                    "kind": "whisker-codeblock-identifier-probes",
                    "model": "deepseek-v4-pro",
                    "pass_count": 1,
                    "fail_count": 0,
                    "skip_count": 0,
                    "units": [
                        {
                            "unit_index": 0,
                            "identifier": "widget_factory",
                            "line": 1,
                            "passed": True,
                        },
                    ],
                },
            },
        )
        out = format_paper_section(self._whisker(), tapetum)
        assert "| rule | status | strength | method |" in out
        assert "| R1 | not-llm-readable | HARD | deterministic |" in out
        assert "Table unit dumps (evidence, not certification)" in out
        assert "| T2 | label\\_shift | PASS |" in out
        assert "certified: `no`" in out
        assert "**Codeblock readability:**" in out
        assert "| C2 | pass | HARD | deterministic |" in out
        assert "Code identifier probes (evidence, not certification)" in out
        assert "| C0 | widget\\_factory | 1 | PASS |" in out


class TestTableReadabilityBlock:
    """Count-dump hook: honest methods, sibling evidence, no live pod."""

    _MD = (
        "| A | B |\n"
        "|---|---|\n"
        "| 1 | 2 |\n"
    )

    def test_no_credentials_skips_dumps_and_does_not_stamp_llm(self):
        from whisker.llm.unit_judge import build_llm_readability_block

        payload = build_llm_readability_block(self._MD, pid="P0000R0")
        assert "unit_dumps" not in payload
        assert "code_probes" not in payload
        assert "llm" not in payload.get("methods_executed", [])
        assert payload.get("kind") == "whisker-table-readability"
        assert "code_readability" in payload
        assert payload["code_readability"]["vacuous"] is True

    def test_mocked_dump_is_sibling_evidence(self, monkeypatch):
        from whisker.llm import unit_judge
        from whisker.llm.table_probes import (
            UNIT_DUMPS_KIND,
            AllUnitDumpsResult,
            ProbeResult,
            UnitDumpResult,
        )

        fake = AllUnitDumpsResult(
            pid="P0000R0",
            model="deepseek-v4-pro",
            units=[
                UnitDumpResult(
                    unit_index=0,
                    classification="aligned",
                    probe=ProbeResult(
                        probe_id="aligned-t0",
                        question="count",
                        expected="aligned",
                        answer="HEADER: [1]=A [2]=B",
                        passed=True,
                    ),
                ),
            ],
        )

        def _fake_run(*_args, **_kwargs):
            return fake

        monkeypatch.setattr(unit_judge, "run_unit_dumps", _fake_run)
        payload = unit_judge.build_llm_readability_block(
            self._MD,
            pid="P0000R0",
            base_url="http://example.invalid/v1",
            api_key="test-key",
            model="deepseek-v4-pro",
        )
        dumps = payload["unit_dumps"]
        assert dumps["kind"] == UNIT_DUMPS_KIND
        assert dumps["pid"] == "P0000R0"
        assert dumps["units"][0]["classification"] == "aligned"
        assert dumps["units"][0]["probe"]["passed"] is True
        assert "llm" not in payload.get("methods_executed", [])
        assert "certified" in payload
        assert "certified" not in dumps
        assert "verdict" not in dumps
        assert "methods_executed" not in dumps

    def test_mocked_code_probes_are_sibling_evidence(self, monkeypatch):
        from whisker.llm import unit_judge
        from whisker.llm.code_probes import (
            CODE_PROBES_KIND,
            CodeFenceProbeResult,
            CodeProbesResult,
        )
        from whisker.llm.table_probes import AllUnitDumpsResult

        md = "```cpp\nint widget_factory();\n```\n"
        fake_probes = CodeProbesResult(
            pid="P0000R0",
            model="deepseek-v4-pro",
            units=[
                CodeFenceProbeResult(
                    unit_index=0,
                    identifier="widget_factory",
                    line=1,
                    first_line="int widget_factory();",
                    clean_question="q",
                    clean_answer="widget_factory",
                    clean_passed=True,
                    corrupt_answer="NOT FOUND",
                    corrupt_inverted=True,
                    passed=True,
                ),
            ],
        )

        monkeypatch.setattr(
            unit_judge, "run_unit_dumps",
            lambda *_a, **_k: AllUnitDumpsResult(pid="P0000R0", model="m"),
        )
        monkeypatch.setattr(
            unit_judge, "run_code_probes", lambda *_a, **_k: fake_probes
        )
        payload = unit_judge.build_llm_readability_block(
            md,
            pid="P0000R0",
            base_url="http://example.invalid/v1",
            api_key="test-key",
            model="deepseek-v4-pro",
        )
        code_block = payload["code_readability"]
        assert any(rule["id"].startswith("C") for rule in code_block["rules"])
        probes = payload["code_probes"]
        assert probes["kind"] == CODE_PROBES_KIND
        assert probes["units"][0]["passed"] is True
        assert "certified" not in probes
        assert "llm" not in payload.get("methods_executed", [])


# -- Prompt/schema consistency -------------------------------------------------


def _tapetum_md_text() -> str:
    import importlib.resources

    return (
        importlib.resources.files("whisker")
        .joinpath("llm/llm.md")
        .read_text(encoding="utf-8")
    )


def test_prompt_covers_all_axes():
    """Every FidelityAxis literal must appear in the system prompt."""
    from typing import get_args

    from whisker.llm.models import FidelityAxis

    text = _tapetum_md_text()
    for axis in get_args(FidelityAxis):
        assert axis in text, f"axis {axis} missing from llm.md prompt"


def test_prompt_declares_sanctioned_markers():
    """The sanctioned tomd markers must be named so the LLM won't flag them."""
    text = _tapetum_md_text()
    assert "tomd:uncertain" in text
    assert "tomd:glyph-placeholders" in text
    assert "tomd:vector-extraction-uncertain" in text


def test_prompt_couples_severity_and_verdict():
    """The prompt must forbid a fail below major severity (the P3941R4 fix)."""
    text = _tapetum_md_text()
    assert "Severity and verdict are coupled" in text
    assert "Never emit `fail` with `minor`" in text


def test_prompt_has_heading_jump_and_chunk_note():
    """The prompt must call a heading jump cosmetic and explain chunked input."""
    text = _tapetum_md_text()
    assert "heading-level jump" in text
    assert "chunk i of N" in text


# -- Severity-aware worst-axis fold (P3941R4 rescue) --------------------------


def _af(axis, verdict, severity):
    return AxisFinding(axis=axis, verdict=verdict, severity=severity, note="n")


class TestWorstAxisVerdict:
    def test_major_fail_is_hard_fail(self):
        from whisker.llm.chunking import worst_axis_verdict

        assert worst_axis_verdict([_af("tables", "not-llm-readable", "major")]) == "not-llm-readable"

    def test_minor_fail_folds_to_review(self):
        from whisker.llm.chunking import worst_axis_verdict

        assert worst_axis_verdict([_af("structure", "not-llm-readable", "minor")]) == "review"

    def test_review_stays_review(self):
        from whisker.llm.chunking import worst_axis_verdict

        assert worst_axis_verdict([_af("wording", "review", "minor")]) == "review"

    def test_all_pass(self):
        from whisker.llm.chunking import worst_axis_verdict

        assert worst_axis_verdict([_af("code", "pass", "none")]) == "pass"

    def test_major_beats_minor(self):
        from whisker.llm.chunking import worst_axis_verdict

        findings = [_af("xrefs", "not-llm-readable", "minor"), _af("structure", "not-llm-readable", "major")]
        assert worst_axis_verdict(findings) == "not-llm-readable"

    def test_empty(self):
        from whisker.llm.chunking import worst_axis_verdict

        assert worst_axis_verdict([]) == "pass"


class TestDecideSeverity:
    def _run_decide(self, paper_md, finding, *, quote, confidence):
        from whisker.llm.adjudicate import _custom_decide, _PipelineState

        state = _PipelineState(paper_md=paper_md, whisker_signals={"verdict": "review"})
        state.tier1 = Adjudication(
            reasoning="r",
            axis_findings=[finding],
            worst_axis=finding.axis,
            verdict="not-llm-readable",  # model self-reports fail; decide re-derives
            confidence=confidence,
            evidence_spans=[EvidenceSpan(axis=finding.axis, quote=quote, reason="x")],
            primary_concern="c",
        )
        mock_ctx = MagicMock()
        mock_ctx.pid = "P3941R4"
        mock_ctx.prompt.services = {"fast": "svc", "deep": "svc2", "default": "svc"}
        asyncio.run(_custom_decide(state, mock_ctx, MagicMock()))
        return state._result

    def test_major_fail_without_corroboration_demoted_to_review(self):
        """v21: a fail stays only with a second corroborating signal
        (verified unit defect, metadata fail, or TOC clamp). Without
        corroboration, the single-model fail folds to review."""
        paper_md = "# Paper\n\nThe table values are scrambled here.\n"
        result = self._run_decide(
            paper_md,
            _af("tables", "not-llm-readable", "major"),
            quote="table values are scrambled",
            confidence=0.90,
        )
        assert result.suggested_verdict == "review"

    def test_minor_fail_is_rescued_to_review(self):
        # A cosmetic structure fail/minor must NOT become an overall fail even
        # though the model self-reported verdict == "not-llm-readable".
        paper_md = "# Paper\n\nA jumped heading after the section.\n"
        result = self._run_decide(
            paper_md,
            _af("structure", "not-llm-readable", "minor"),
            quote="jumped heading",
            confidence=0.95,
        )
        assert result.suggested_verdict == "review"


# -- Chunking (oversize 413 fix) ----------------------------------------------


class TestChunkMarkdown:
    def test_fits_returns_single_chunk(self):
        from whisker.llm.chunking import chunk_markdown

        chunks, partial = chunk_markdown("small body", 100)
        assert chunks == ["small body"]
        assert partial is False

    def test_h2_split_lossless_and_bounded(self):
        from whisker.llm.chunking import chunk_markdown

        md = "# Title\n\npreamble\n\n" + "".join(
            f"## Section {i}\n\n{'x' * 40}\n\n" for i in range(10)
        )
        chunks, partial = chunk_markdown(md, 120)
        assert partial is False
        assert "".join(chunks) == md
        assert all(len(c) <= 120 for c in chunks)
        assert len(chunks) > 1

    def test_oversized_pipe_table_is_never_bisected(self):
        from whisker.det.llm_readability.contract import load_core_contract
        from whisker.det.llm_readability.models import STATUS_NOT_EVALUATED
        from whisker.det.llm_readability.validate import CheckContext, document_facts
        from whisker.llm.chunking import chunk_markdown, make_table_atomic_check

        header = "| " + " | ".join(f"C{i}" for i in range(40)) + " |\n"
        sep = "| " + " | ".join("---" for _ in range(40)) + " |\n"
        body = "| " + " | ".join("x" * 20 for _ in range(40)) + " |\n"
        table = header + sep + body * 5
        md = "## Big\n\n" + table
        chunks, partial = chunk_markdown(md, 80)
        assert partial is True
        assert "".join(chunks) == md
        assert any(table.strip() in chunk for chunk in chunks)
        for chunk in chunks:
            if "|" in chunk and "C0" in chunk:
                assert table.strip() in chunk.replace("\r\n", "\n")
        check = make_table_atomic_check(chunks, max_chars=80)
        rule = load_core_contract().rule("R12")
        units = ()
        outcome = check(
            CheckContext(
                rule=rule,
                units=units,
                facts=document_facts(units, chunking_evaluated=True),
                thresholds=load_core_contract().thresholds,
            )
        )
        assert outcome.status == STATUS_NOT_EVALUATED
        assert outcome.reason == "oversized_atomic_table"

    def test_oversized_html_table_is_never_bisected(self):
        from whisker.llm.chunking import chunk_markdown

        cell = "<td>" + ("n" * 200) + "</td>"
        table = "<table><tr>" + cell * 8 + "</tr></table>\n"
        md = "## Wide\n\n" + table
        chunks, partial = chunk_markdown(md, 60)
        assert partial is True
        assert "".join(chunks) == md
        holders = [c for c in chunks if "<table" in c.lower()]
        assert len(holders) == 1
        assert table.strip() in holders[0]

    def test_oversize_section_hard_split_sets_partial(self):
        from whisker.llm.chunking import chunk_markdown

        big = "## Big\n\n" + ("y" * 500) + "\n"
        chunks, partial = chunk_markdown(big, 100)
        assert partial is True
        assert all(len(c) <= 100 for c in chunks)
        assert "".join(chunks) == big

    def test_deterministic(self):
        from whisker.llm.chunking import chunk_markdown

        md = "# T\n\n" + "".join(f"## S{i}\n\nbody {i}\n\n" for i in range(8))
        assert chunk_markdown(md, 50) == chunk_markdown(md, 50)

    def test_fence_aware_split(self):
        from whisker.llm.chunking import _split_sections

        secs = _split_sections("## A\n\n```\n## fenced not a heading\n```\n\n## B\n\nbody\n")
        assert len(secs) == 2
        assert "## fenced not a heading" in secs[0]


# -- Aggregation ---------------------------------------------------------------


def _adj(verdict, severity, *, axis="tables", conf=0.8, quote="q"):
    return Adjudication(
        reasoning="r",
        axis_findings=[AxisFinding(axis=axis, verdict=verdict, severity=severity, note="n")],
        worst_axis=axis,
        verdict=verdict,
        confidence=conf,
        evidence_spans=[EvidenceSpan(axis=axis, quote=quote, reason="x")],
        primary_concern="c",
    )


class TestAggregate:
    def test_major_fail_wins_min_conf_union(self):
        from whisker.llm.chunking import aggregate_adjudications

        parts = [
            _adj("pass", "none", conf=0.9, quote="qa"),
            _adj("not-llm-readable", "major", conf=0.6, quote="qb"),
        ]
        agg = aggregate_adjudications(parts, 2)
        assert agg.verdict == "not-llm-readable"
        assert agg.confidence == 0.6
        assert len(agg.evidence_spans) == 2
        assert "chunked into 2 parts" in agg.primary_concern

    def test_minor_fail_folds_to_review(self):
        from whisker.llm.chunking import aggregate_adjudications

        agg = aggregate_adjudications([_adj("not-llm-readable", "minor", axis="structure", conf=0.7)], 1)
        assert agg.verdict == "review"

    def test_empty_parts(self):
        from whisker.llm.chunking import aggregate_adjudications

        agg = aggregate_adjudications([], 0)
        assert agg.verdict == "review"


class TestTriageOversize:
    def _adjudication(self):
        return Adjudication(
            reasoning="chunk ok",
            axis_findings=[AxisFinding(axis="tables", verdict="pass", severity="none", note="ok")],
            worst_axis="tables",
            verdict="pass",
            confidence=0.6,
            evidence_spans=[],
            primary_concern="none",
        )

    def test_oversize_chunks_serially_and_skips_tier2(self):
        from whisker.llm.adjudicate import (
            _custom_adjudicate,
            _custom_triage,
            _PipelineState,
        )

        md = "# T\n\n" + "".join(f"## S{i}\n\n{'x' * 40}\n\n" for i in range(6))
        state = _PipelineState(
            paper_md=md,
            whisker_signals={"verdict": "review", "soft_flags": [], "hard_flags": []},
        )

        mock_ctx = MagicMock()
        mock_ctx.pid = "P2728R12"
        mock_ctx.inject_untrusted = lambda s: s

        with (
            patch("whisker.llm.adjudicate.MAX_PAPER_MD_CHARS", 80),
            patch(
                "whisker.llm.adjudicate.run_agent", new_callable=AsyncMock
            ) as mock_run,
        ):
            mock_run.return_value = self._adjudication()
            asyncio.run(_custom_triage(state, mock_ctx, MagicMock()))

            assert state.chunked is True
            assert mock_run.call_count > 1
            assert state.tier1 is not None

            mock_run.reset_mock()
            asyncio.run(_custom_adjudicate(state, mock_ctx, MagicMock()))
            mock_run.assert_not_called()
            assert state.tier2 is None


# -- Work Item A: Prompt-consistency tests ------------------------------------


class TestPromptConversionContract:
    """Lock the WG21 extraction rules into the prompt text."""

    def test_front_matter_key_order_declared(self):
        text = _tapetum_md_text()
        assert "in this exact key order" in text

    @pytest.mark.parametrize("key", [
        "`title`", "`document`", "`date`", "`intent`", "`audience`", "`reply-to`",
    ])
    def test_front_matter_keys_present(self, key):
        assert key in _tapetum_md_text()

    def test_body_starts_at_h2(self):
        assert "the body starts at H2" in _tapetum_md_text()

    def test_headings_atx(self):
        assert "Headings are ATX" in _tapetum_md_text()

    def test_nest_by_at_most_one_level(self):
        assert "nest by at most one level" in _tapetum_md_text()

    @pytest.mark.parametrize("section", [
        "`Abstract`", "`References`", "`Wording`", "`Motivation`", "`Acknowledgements`",
    ])
    def test_known_sections_present(self, section):
        assert section in _tapetum_md_text()

    def test_paragraph_unwrapped(self):
        assert "each paragraph is one unwrapped line" in _tapetum_md_text()

    def test_blank_line_between_blocks(self):
        assert "one blank line between blocks" in _tapetum_md_text()

    def test_dehyphenated(self):
        assert "dehyphenated across line breaks" in _tapetum_md_text()

    def test_link_schemes(self):
        assert "http/https/mailto" in _tapetum_md_text()

    def test_insertions_deletions(self):
        assert "insertions/deletions (ins/del)" in _tapetum_md_text()

    def test_image_syntax(self):
        assert "`![alt](path)`" in _tapetum_md_text()


class TestPromptCodeReadable:
    """Code rules come from the TOML contract, not a second markdown prompt."""

    def test_authority_file_keeps_the_sentinel(self):
        text = _tapetum_md_text()
        assert "<!-- whisker:codeblock-readability-contract -->" in text
        assert "with a language tag" in text
        assert "no empty fences" in text

    def test_hydrated_prompt_contains_rendered_code_contract(self):
        from pipeline import PipelinePrompt
        from whisker.det.llm_readability.contract import (
            CONSTRUCT_CODEBLOCKS,
            load_core_contract,
        )
        from whisker.llm.unit_judge import (
            CODE_CONTRACT_SENTINEL,
            hydrate_pipeline_prompt,
            resolve_runtime_code_contract,
            resolve_runtime_table_contract,
        )

        prompt = PipelinePrompt.load("whisker", "llm/llm.md")
        hydrated = hydrate_pipeline_prompt(
            prompt,
            resolve_runtime_table_contract(),
            code_resolved=resolve_runtime_code_contract(),
        )
        core = load_core_contract(CONSTRUCT_CODEBLOCKS)
        assert core.id in hydrated.system_prompt
        assert core.hash in hydrated.system_prompt
        assert "C2" in hydrated.system_prompt
        assert "C10" in hydrated.system_prompt
        assert CODE_CONTRACT_SENTINEL not in hydrated.system_prompt
        assert CODE_CONTRACT_SENTINEL not in hydrated.sections.get("System Prompt", "")


class TestPromptTableModes:
    """Table rules come from the TOML contract, not a second markdown prompt."""

    def test_authority_file_keeps_the_sentinel_not_the_old_prose(self):
        text = _tapetum_md_text()
        assert "<!-- whisker:table-readability-contract -->" in text
        assert "Merged cells lost" not in text

    def test_hydrated_prompt_contains_rendered_contract(self):
        from pipeline import PipelinePrompt
        from whisker.det.llm_readability.contract import load_core_contract
        from whisker.llm.unit_judge import (
            TABLE_CONTRACT_SENTINEL,
            hydrate_pipeline_prompt,
            resolve_runtime_table_contract,
        )

        prompt = PipelinePrompt.load("whisker", "llm/llm.md")
        hydrated = hydrate_pipeline_prompt(prompt, resolve_runtime_table_contract())
        core = load_core_contract()
        assert core.id in hydrated.system_prompt
        assert core.hash in hydrated.system_prompt
        assert "sha256:" in hydrated.system_prompt
        assert "R6" in hydrated.system_prompt
        assert "R12" in hydrated.system_prompt
        assert TABLE_CONTRACT_SENTINEL not in hydrated.system_prompt
        assert TABLE_CONTRACT_SENTINEL not in hydrated.sections.get("System Prompt", "")


class TestPromptAxisSpecifics:
    """Per-axis specifics locked into the prompt."""

    def test_stable_names_example(self):
        assert "`[rand.req.urng]`" in _tapetum_md_text()

    def test_xrefs_wrong_revision(self):
        assert "Wrong revision letter" in _tapetum_md_text()

    def test_math_frac(self):
        assert r"`\frac{a}{b}`" in _tapetum_md_text()

    def test_structure_reordered(self):
        assert "reordered, dropped, or duplicated" in _tapetum_md_text()


def test_prompt_front_matter_keys_match_tomd_contract():
    """Anti-drift guard: canonical 6-key order mirrors tomd Front Matter Strict Order.

    Source of truth: packages/tomd/src/tomd/CLAUDE.md (not imported cross-package).
    """
    canonical_keys = ["title", "document", "date", "intent", "audience", "reply-to"]
    text = _tapetum_md_text()
    for key in canonical_keys:
        assert f"`{key}`" in text, f"front-matter key {key!r} missing from prompt"


# -- Work Item B: Extended deterministic offline fixtures ----------------------


class TestChunkMarkdownExtended:
    """Additional deterministic chunking coverage."""

    def test_tilde_fence_not_split(self):
        """A fenced block delimited by ~~~ must not be split mid-fence."""
        from whisker.llm.chunking import chunk_markdown

        fence_body = "line\n" * 8
        md = "## Sec\n\n~~~\n" + fence_body + "~~~\n"
        max_chars = len(md) - 5
        chunks, partial = chunk_markdown(md, max_chars)
        # The section is oversized so it hard-splits, but each fence opener
        # and closer should stay together with surrounding content (lossless).
        rejoined = "".join(chunks)
        assert rejoined == md
        # The fence opener and closer survive in the output
        assert "~~~\n" in rejoined

    def test_yaml_front_matter_before_h2_lossless(self):
        """Front-matter-only preamble before first ## chunks losslessly."""
        from whisker.llm.chunking import chunk_markdown

        md = "---\ntitle: Test\n---\n\n## Section 1\n\nbody one\n\n## Section 2\n\nbody two\n"
        chunks, _ = chunk_markdown(md, 40)
        assert "".join(chunks) == md

    def test_oversized_section_with_h3_sets_partial(self):
        """A single H2 section with nested H3s larger than max_chars -> partial."""
        from whisker.llm.chunking import chunk_markdown

        inner = "### Sub1\n\ntext\n\n### Sub2\n\ntext\n\n### Sub3\n\ntext\n"
        md = "## BigSection\n\n" + inner
        max_chars = len(md) // 2
        chunks, partial = chunk_markdown(md, max_chars)
        assert partial is True
        assert "".join(chunks) == md

    def test_roundtrip_mixed_doc(self):
        """Lossless roundtrip on a mixed doc forced into multiple chunks."""
        from whisker.llm.chunking import chunk_markdown

        md = (
            "---\ntitle: Mixed\ndocument: P9999R0\n---\n\n"
            "## Intro\n\nHello world.\n\n"
            "## Code\n\n```cpp\nint main() {}\n```\n\n"
            "## Tables\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n"
            "## End\n\nDone.\n"
        )
        max_chars = 60
        chunks, _ = chunk_markdown(md, max_chars)
        assert len(chunks) > 1
        assert "".join(chunks) == md


class TestGroundingExtended:
    """Additional grounding edge cases."""

    def test_nbsp_normalized_match(self):
        """A quote with NBSP matches after normalization (alnum-only compare)."""
        from whisker.llm.grounding import ground_spans

        md = "The value is 42 percent of the total."
        # Quote uses NBSP (\u00a0) instead of regular space
        spans = [EvidenceSpan(axis="wording", quote="value\u00a0is\u00a042", reason="nbsp")]
        grounded, dropped = ground_spans(spans, md)
        assert len(grounded) == 1
        assert dropped == 0

    def test_multiple_spaces_normalized(self):
        """Multiple spaces in the quote still ground via normalization."""
        from whisker.llm.grounding import ground_spans

        md = "function returns true when valid"
        spans = [EvidenceSpan(axis="code", quote="function   returns   true", reason="spaces")]
        grounded, dropped = ground_spans(spans, md)
        assert len(grounded) == 1
        assert dropped == 0


class TestAggregateExtended:
    """Additional aggregation coverage."""

    def test_different_worst_axes_fold_correctly(self):
        """Parts with different worst axes: per-axis worst finding survives."""
        from whisker.llm.chunking import aggregate_adjudications

        part1 = Adjudication(
            reasoning="chunk1",
            axis_findings=[
                AxisFinding(axis="tables", verdict="not-llm-readable", severity="major", note="broken"),
                AxisFinding(axis="code", verdict="pass", severity="none", note="ok"),
            ],
            worst_axis="tables",
            verdict="not-llm-readable",
            confidence=0.7,
            evidence_spans=[],
            primary_concern="tables broken",
        )
        part2 = Adjudication(
            reasoning="chunk2",
            axis_findings=[
                AxisFinding(axis="tables", verdict="pass", severity="none", note="ok"),
                AxisFinding(axis="code", verdict="not-llm-readable", severity="major", note="garbled"),
            ],
            worst_axis="code",
            verdict="not-llm-readable",
            confidence=0.8,
            evidence_spans=[],
            primary_concern="code garbled",
        )
        agg = aggregate_adjudications([part1, part2], 2)
        findings_by_axis = {af.axis: af for af in agg.axis_findings}
        assert findings_by_axis["tables"].verdict == "not-llm-readable"
        assert findings_by_axis["tables"].severity == "major"
        assert findings_by_axis["code"].verdict == "not-llm-readable"
        assert findings_by_axis["code"].severity == "major"
        assert agg.verdict == "not-llm-readable"

    def test_order_invariance(self):
        """Aggregating a shuffled copy yields same axis findings and verdict."""
        from whisker.llm.chunking import aggregate_adjudications

        parts = [
            _adj("pass", "none", axis="wording", conf=0.9, quote="a"),
            _adj("review", "minor", axis="tables", conf=0.7, quote="b"),
            _adj("not-llm-readable", "major", axis="code", conf=0.6, quote="c"),
        ]
        agg_original = aggregate_adjudications(parts, 3)
        agg_reversed = aggregate_adjudications(list(reversed(parts)), 3)

        assert agg_original.verdict == agg_reversed.verdict
        orig_axes = {af.axis: (af.verdict, af.severity) for af in agg_original.axis_findings}
        rev_axes = {af.axis: (af.verdict, af.severity) for af in agg_reversed.axis_findings}
        assert orig_axes == rev_axes

    def test_severity_tie_deterministic(self):
        """A tie in severity resolves deterministically (sorted axis name)."""
        from whisker.llm.chunking import aggregate_adjudications

        parts = [
            _adj("not-llm-readable", "major", axis="xrefs", conf=0.5, quote="x"),
            _adj("not-llm-readable", "major", axis="math", conf=0.5, quote="y"),
        ]
        agg = aggregate_adjudications(parts, 2)
        # worst_axis should be deterministic: sorted alphabetically among tied
        assert agg.worst_axis == "math"
        # Run again to confirm
        agg2 = aggregate_adjudications(parts, 2)
        assert agg2.worst_axis == agg.worst_axis


# -- Binary-payload stripping (pre-LLM) ------------------------------------------


class TestStripBinaryPayloads:
    """Data-URI images and bare base64 lines are replaced by sanctioned markers."""

    def test_data_uri_image_stripped_alt_kept(self):
        from whisker.llm.chunking import strip_binary_payloads

        payload = "iVBORw0KGgoAAAANSUhEUg" * 100
        md = f"Intro text.\n\n![Figure 1: flow](data:image/png;base64,{payload})\n\nOutro.\n"
        out, count = strip_binary_payloads(md)
        assert count == 1
        assert payload not in out
        assert "![Figure 1: flow](<!-- tapetum:data-uri-stripped image/png" in out
        assert "Intro text." in out and "Outro." in out

    def test_multiple_images_all_stripped(self):
        from whisker.llm.chunking import strip_binary_payloads

        md = (
            "![](data:image/png;base64,AAAA)\n"
            "prose between\n"
            "![x](data:image/jpeg;base64,BBBB)\n"
        )
        out, count = strip_binary_payloads(md)
        assert count == 2
        assert "AAAA" not in out and "BBBB" not in out
        assert "prose between" in out

    def test_normal_images_and_prose_untouched(self):
        from whisker.llm.chunking import strip_binary_payloads

        md = (
            "![fig](p1234r0-fig1-1.png)\n\n"
            "Normal prose with base64 mentioned in text.\n\n"
            "```cpp\nauto x = decode_base64(s);\n```\n"
        )
        out, count = strip_binary_payloads(md)
        assert count == 0
        assert out == md

    def test_bare_base64_line_stripped(self):
        from whisker.llm.chunking import strip_binary_payloads

        blob = "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVphYmNkZWZnaGlqa2xt" * 40  # > 1024
        md = f"# T\n\nBefore.\n{blob}\nAfter.\n"
        out, count = strip_binary_payloads(md)
        assert count == 1
        assert blob not in out
        assert "tapetum:base64-line-stripped" in out
        assert "Before." in out and "After." in out

    def test_long_prose_line_kept(self):
        from whisker.llm.chunking import strip_binary_payloads

        # Longer than the min-chars gate but plainly prose: spaces and
        # punctuation keep it well under the alphabet floor.
        prose = ("The committee reviewed the proposal, carefully; noting "
                 "wording, tables, and cross-references. ") * 20
        assert len(prose) > 1024
        out, count = strip_binary_payloads(prose)
        assert count == 0
        assert out == prose

    def test_p2728_shape_shrinks_below_chunk_budget(self):
        from whisker.llm.chunking import chunk_markdown, strip_binary_payloads

        # Corpus shape: ~150 KB prose + megabyte data-URI lines.
        prose = ("## Section\n\n" + "word " * 2000 + "\n\n") * 10
        blob = "![](data:image/png;base64," + "A" * 1_100_000 + ")\n"
        md = prose + blob + prose
        assert len(md) > 500_000
        out, count = strip_binary_payloads(md)
        assert count == 1
        chunks, partial = chunk_markdown(out, 500_000)
        assert len(chunks) == 1
        assert partial is False


# -- Grounding DP (langextract port) --------------------------------------------


class TestGroundingDP:
    """Monotonic exact-occurrence DP: intervals, repeated-mention mapping."""

    def test_exact_match_carries_char_interval(self):
        from whisker.llm.grounding import GROUND_EXACT, ground_spans

        md = "# Paper\n\nThe committee reviewed the wording carefully.\n"
        spans = [EvidenceSpan(axis="wording", quote="reviewed the wording", reason="r")]
        grounded, dropped = ground_spans(spans, md)
        assert dropped == 0
        g = grounded[0]
        assert g.status == GROUND_EXACT
        assert md[g.start:g.end] == "reviewed the wording"

    def test_repeated_quote_maps_to_successive_occurrences(self):
        from whisker.llm.grounding import GROUND_EXACT, ground_spans

        md = "The proposal is sound. Later text. The proposal is sound. End."
        spans = [
            EvidenceSpan(axis="wording", quote="The proposal is sound", reason="a"),
            EvidenceSpan(axis="wording", quote="The proposal is sound", reason="b"),
        ]
        grounded, dropped = ground_spans(spans, md)
        assert dropped == 0
        assert [g.status for g in grounded] == [GROUND_EXACT, GROUND_EXACT]
        first, second = grounded
        # Occurrence-blind grounding would collapse both to position 0.
        assert first.start == 0
        assert second.start > first.end
        assert md[second.start:second.end] == "The proposal is sound"

    def test_single_quote_prefers_earliest_occurrence(self):
        from whisker.llm.grounding import ground_spans

        md = "alpha beta gamma. filler. alpha beta gamma."
        spans = [EvidenceSpan(axis="wording", quote="alpha beta gamma", reason="r")]
        grounded, _ = ground_spans(spans, md)
        assert grounded[0].start == 0

    def test_short_quote_cannot_ground_via_fuzzy_ratio(self):
        from whisker.llm.grounding import ground_spans

        # "alphabeta" (9 normalized chars, below EVIDENCE_MIN_FUZZY_CHARS)
        # would clear partial_ratio against "alphaxbeta"; the length gate
        # forces short quotes to ground exactly or by substring.
        md = "alpha x beta and much more document text follows here"
        spans = [EvidenceSpan(axis="wording", quote="alpha beta", reason="r")]
        grounded, dropped = ground_spans(spans, md)
        assert grounded == []
        assert dropped == 1

    def test_punctuation_differences_downgrade_source_grounding(self):
        from whisker.llm.grounding import GROUND_FUZZY, ground_spans

        md = "The value, therefore, is 42 percent."
        spans = [EvidenceSpan(axis="wording", quote="value therefore is 42", reason="r")]
        grounded, dropped = ground_spans(spans, md)
        assert dropped == 0
        assert grounded[0].status == GROUND_FUZZY
        assert grounded[0].start is None
        assert grounded[0].end is None

    @pytest.mark.parametrize(
        ("axis", "quote", "source"),
        [
            ("structure", "value <= limit", "value >= limit"),
            ("code", 'value = "x"', "value = x"),
            ("code", r'value = "\x"', 'value = "x"'),
            ("math", "x ≤ y", "x ≥ y"),
        ],
    )
    def test_semantic_syntax_mismatch_downgrades_source_grounding(
        self,
        axis,
        quote,
        source,
    ):
        from whisker.llm.grounding import GROUND_FUZZY, ground_spans

        spans = [
            EvidenceSpan(
                axis=axis,
                quote=quote,
                reason="source claim",
            )
        ]
        grounded, dropped = ground_spans(spans, source)
        assert dropped == 0
        assert len(grounded) == 1
        assert grounded[0].status == GROUND_FUZZY
        assert grounded[0].start is None
        assert grounded[0].end is None


# -- Escalation signals ----------------------------------------------------------


class TestEscalationSignals:
    """Derived uncertainty signals replace the dead scalar-band-only gate."""

    def _tier1(self, findings, *, confidence=0.95, spans=()):
        return Adjudication(
            reasoning="r",
            axis_findings=findings,
            worst_axis=findings[0].axis if findings else "wording",
            verdict="review",
            confidence=confidence,
            evidence_spans=list(spans),
            primary_concern="c",
        )

    def test_axis_conflict_fires(self):
        from whisker.llm.adjudicate import _escalation_signals
        from whisker.llm.constants import SIGNAL_AXIS_CONFLICT

        tier1 = self._tier1([
            _af("wording", "pass", "none"),
            _af("tables", "not-llm-readable", "major"),
        ])
        assert _escalation_signals(tier1, "some markdown") == [SIGNAL_AXIS_CONFLICT]

    def test_ungrounded_evidence_fires(self):
        from whisker.llm.adjudicate import _escalation_signals
        from whisker.llm.constants import SIGNAL_UNGROUNDED_EVIDENCE

        tier1 = self._tier1(
            [_af("wording", "review", "minor")],
            spans=[EvidenceSpan(axis="wording", quote="not in the document at all xyz", reason="x")],
        )
        assert _escalation_signals(tier1, "completely different text") == [
            SIGNAL_UNGROUNDED_EVIDENCE
        ]

    def test_ambiguous_confidence_fires(self):
        from whisker.llm.adjudicate import _escalation_signals
        from whisker.llm.constants import SIGNAL_CONFIDENCE_AMBIGUOUS

        tier1 = self._tier1([_af("wording", "review", "minor")], confidence=0.50)
        assert _escalation_signals(tier1, "md") == [SIGNAL_CONFIDENCE_AMBIGUOUS]

    def test_clean_consistent_tier1_no_signal(self):
        from whisker.llm.adjudicate import _escalation_signals

        md = "The wording is intact and faithful."
        tier1 = self._tier1(
            [_af("wording", "pass", "none"), _af("tables", "review", "minor")],
            confidence=0.95,
            spans=[EvidenceSpan(axis="wording", quote="wording is intact and faithful", reason="x")],
        )
        assert _escalation_signals(tier1, md) == []

    def test_signals_recorded_in_result(self):
        """An escalated run records which signals fired in the sidecar."""
        from whisker.llm.adjudicate import (
            _custom_adjudicate,
            _custom_decide,
            _PipelineState,
        )
        from whisker.llm.constants import SIGNAL_AXIS_CONFLICT

        state = _PipelineState(
            paper_md="Paper text here.",
            whisker_signals={"verdict": "review", "soft_flags": [], "hard_flags": []},
        )
        state.tier1 = self._tier1([
            _af("wording", "pass", "none"),
            _af("tables", "not-llm-readable", "major"),
        ])

        mock_ctx = MagicMock()
        mock_ctx.pid = "P0042R0"
        mock_ctx.inject_untrusted = lambda s: s
        mock_ctx.prompt.services = {"fast": "svc", "deep": "svc", "default": "svc"}

        deep = self._tier1([_af("tables", "review", "minor")], confidence=0.9)
        with patch(
            "whisker.llm.adjudicate.run_agent", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = deep
            asyncio.run(_custom_adjudicate(state, mock_ctx, MagicMock()))
            assert state.tier2 is not None
            assert state.escalation_signals == [SIGNAL_AXIS_CONFLICT]

        asyncio.run(_custom_decide(state, mock_ctx, MagicMock()))
        result = state._result
        assert result.escalated is True
        assert result.escalation_signals == [SIGNAL_AXIS_CONFLICT]
        assert result.to_dict()["escalation_signals"] == [SIGNAL_AXIS_CONFLICT]


# -- CLI --concurrency tests ----------------------------------------------------


class TestCliConcurrency:
    """--concurrency N: bounded parallel adjudication with per-paper firewall."""

    @staticmethod
    def _result(pid: str) -> TapetumResult:
        return TapetumResult(
            pid=pid,
            whisker_verdict="pass",
            suggested_verdict="pass",
            confidence=0.9,
            escalated=False,
            tier1_model="mock",
            tier2_model=None,
            primary_concern="",
            reasoning="",
        )

    def _tracking_adjudicate(self, fail_pids: frozenset[str] = frozenset()):
        """AsyncMock stand-in that records start order and max in-flight count."""
        state = {"inflight": 0, "max_inflight": 0, "order": []}

        async def fake(pid, backend, **kwargs):
            state["order"].append(pid)
            state["inflight"] += 1
            state["max_inflight"] = max(state["max_inflight"], state["inflight"])
            await asyncio.sleep(0.01)
            state["inflight"] -= 1
            if pid in fail_pids:
                raise RuntimeError("boom")
            return self._result(pid)

        return fake, state

    def _run_cli(self, argv: list[str], adjudicate_fake):
        """Run cli._run with all I/O boundaries mocked; return persist mock."""
        import logging as _logging
        from pathlib import Path

        from whisker.llm import cli

        args = cli._parse_args(argv)
        root = _logging.getLogger()
        saved_handlers = list(root.handlers)
        try:
            with (
                patch.object(cli, "adjudicate_paper", adjudicate_fake),
                patch.object(cli, "open_backend", return_value=MagicMock()),
                patch.object(cli, "load_services", return_value=MagicMock()),
                patch.object(cli, "_probe_llm_endpoint", new=AsyncMock()),
                patch.object(
                    cli, "_persist_result", return_value=Path("out.json")
                ) as persist,
                patch.object(cli, "render_progress", return_value=0),
            ):
                asyncio.run(cli._run(args))
        finally:
            # Batch mode swaps root handlers for the bar-aware handler;
            # restore pytest's logging handlers.
            root.handlers = saved_handlers
        return persist

    def test_serial_opt_in_runs_in_input_order(self):
        fake, state = self._tracking_adjudicate()
        persist = self._run_cli(
            ["p1", "p2", "p3", "p4", "--concurrency", "1"], fake
        )
        assert state["max_inflight"] == 1
        assert state["order"] == ["P1", "P2", "P3", "P4"]
        assert persist.call_count == 4

    def test_default_concurrency_is_parallel_and_bounded(self):
        from whisker.llm import cli

        fake, state = self._tracking_adjudicate()
        pids = [f"p{i}" for i in range(1, 25)]
        persist = self._run_cli(pids, fake)
        # Default 16 matches the pod's --max-num-seqs 16 so queue wait
        # lives in the client semaphore (issue 401).
        assert cli._DEFAULT_CONCURRENCY == 16
        assert state["max_inflight"] <= 16
        assert state["max_inflight"] >= 2
        assert persist.call_count == 24

    def test_concurrency_bounds_inflight(self):
        fake, state = self._tracking_adjudicate()
        persist = self._run_cli(
            ["p1", "p2", "p3", "p4", "p5", "p6", "--concurrency", "3"], fake
        )
        assert state["max_inflight"] <= 3
        assert state["max_inflight"] >= 2
        assert persist.call_count == 6

    def test_firewall_isolates_failing_paper(self):
        from whisker.llm import cli

        fake, state = self._tracking_adjudicate(fail_pids=frozenset({"P2"}))
        persist = self._run_cli(["p1", "p2", "p3", "--concurrency", "2"], fake)
        # The failing paper is not persisted; the run still completes.
        # This-run errors are retried (_ERROR_RETRY_ROUNDS extra attempts).
        assert persist.call_count == 2
        assert set(state["order"]) == {"P1", "P2", "P3"}
        assert state["order"].count("P2") == 1 + cli._ERROR_RETRY_ROUNDS

    def test_nonpositive_concurrency_clamps_to_serial(self):
        fake, state = self._tracking_adjudicate()
        persist = self._run_cli(["p1", "p2", "--concurrency", "0"], fake)
        assert state["max_inflight"] == 1
        assert persist.call_count == 2

    def test_paper_timeout_counts_as_error_not_crash(self):
        """A paper exceeding the per-paper budget is firewalled, not fatal."""
        from whisker.llm import cli

        async def slow(pid, backend, **kwargs):
            if pid == "P2":
                await asyncio.sleep(0.5)
            return self._result(pid)

        with patch.object(
            cli, "_text_lane_timeout_seconds", return_value=0.05
        ):
            persist = self._run_cli(
                ["p1", "p2", "p3", "--concurrency", "2"], slow
            )
        # The timed-out paper is not persisted; the others complete.
        assert persist.call_count == 2


class TestPdfTimeoutEnvelope:
    """v18: _pdf_judge_timeout_seconds includes a CB term when code_boundary=True."""

    def test_cb_term_absent_when_disabled(self):
        from whisker.llm.cli import _pdf_judge_timeout_seconds

        base = _pdf_judge_timeout_seconds(code_boundary=False)
        with_cb = _pdf_judge_timeout_seconds(code_boundary=True)
        assert with_cb > base, "CB term must increase the envelope"

    def test_cb_term_matches_formula(self):
        from whisker.llm.cli import _pdf_judge_timeout_seconds
        from whisker.llm.constants import PAGE_ESCALATION_TIMEOUT_SECONDS
        from whisker.llm.pdf_judge import CODE_BOUNDARY_FENCE_CAP

        base = _pdf_judge_timeout_seconds(code_boundary=False)
        with_cb = _pdf_judge_timeout_seconds(code_boundary=True)
        expected_delta = CODE_BOUNDARY_FENCE_CAP * PAGE_ESCALATION_TIMEOUT_SECONDS
        assert with_cb - base == expected_delta


class TestErrorRetryWave:
    """This-run errors are retried in-process; prior tombstones stay skipped."""

    @staticmethod
    def _result(pid: str) -> TapetumResult:
        return TapetumResult(
            pid=pid,
            whisker_verdict="pass",
            suggested_verdict="pass",
            confidence=0.9,
            escalated=False,
            tier1_model="mock",
            tier2_model=None,
            primary_concern="",
            reasoning="",
        )

    def _run_cli(self, argv: list[str], adjudicate_fake) -> tuple[int, object]:
        import logging as _logging

        from whisker.llm import cli

        args = cli._parse_args(argv)
        root = _logging.getLogger()
        saved_handlers = list(root.handlers)
        try:
            with (
                patch.object(cli, "adjudicate_paper", adjudicate_fake),
                patch.object(cli, "open_backend", return_value=MagicMock()),
                patch.object(cli, "load_services", return_value=MagicMock()),
                patch.object(cli, "_probe_llm_endpoint", new=AsyncMock()),
                patch.object(
                    cli, "_persist_result", return_value=Path("out.json")
                ) as persist,
                patch.object(cli, "render_progress", return_value=0),
                patch.object(cli, "_write_error_tombstone"),
            ):
                rc = asyncio.run(cli._run(args))
        finally:
            root.handlers = saved_handlers
        return rc, persist

    def test_fail_once_then_succeed_exits_zero(self):
        attempts: dict[str, int] = {}

        async def fake(pid, backend, **kwargs):
            n = attempts.get(pid, 0)
            attempts[pid] = n + 1
            if pid == "P2" and n == 0:
                raise RuntimeError("transient")
            return self._result(pid)

        rc, persist = self._run_cli(
            ["p1", "p2", "p3", "--concurrency", "2"], fake
        )
        assert rc == 0
        assert persist.call_count == 3
        assert attempts["P2"] == 2
        assert attempts["P1"] == 1
        assert attempts["P3"] == 1

    def test_always_fail_exits_one_after_rounds(self):
        from whisker.llm import cli

        attempts: dict[str, int] = {}

        async def fake(pid, backend, **kwargs):
            attempts[pid] = attempts.get(pid, 0) + 1
            if pid == "P2":
                raise RuntimeError("boom")
            return self._result(pid)

        rc, persist = self._run_cli(
            ["p1", "p2", "p3", "--concurrency", "1"], fake
        )
        assert rc == 1
        assert persist.call_count == 2
        assert attempts["P2"] == 1 + cli._ERROR_RETRY_ROUNDS

    def test_skipped_tombstone_is_not_retried(self):
        from whisker.llm import cli

        attempts: dict[str, int] = {}

        async def fake(pid, backend, **kwargs):
            attempts[pid] = attempts.get(pid, 0) + 1
            return self._result(pid)

        def skip_decision(pid, backend, fp, retry_errors=False):
            if pid == "P2":
                return True, "tombstone", None
            return False, None, None

        with (
            patch.object(cli, "_compute_fingerprint", return_value={"x": 1}),
            patch.object(
                cli, "_fingerprint_skip_decision", side_effect=skip_decision
            ),
            patch.object(cli, "_refresh_fusion_on_skip"),
        ):
            rc, persist = self._run_cli(
                ["p1", "p2", "p3", "--incremental", "--concurrency", "1"],
                fake,
            )
        assert rc == 0
        assert persist.call_count == 2
        assert "P2" not in attempts

    def test_retry_wave_caps_inflight(self):
        from whisker.llm import cli

        state = {"inflight": 0, "max_retry_inflight": 0}
        attempts: dict[str, int] = {}
        original_retry_c = cli._ERROR_RETRY_CONCURRENCY
        original_rounds = cli._ERROR_RETRY_ROUNDS
        cli._ERROR_RETRY_CONCURRENCY = 2
        cli._ERROR_RETRY_ROUNDS = 1
        try:
            async def fake(pid, backend, **kwargs):
                n = attempts.get(pid, 0)
                attempts[pid] = n + 1
                state["inflight"] += 1
                try:
                    if n >= 1:
                        state["max_retry_inflight"] = max(
                            state["max_retry_inflight"], state["inflight"]
                        )
                        return self._result(pid)
                    raise RuntimeError("transient")
                finally:
                    state["inflight"] -= 1

            rc, persist = self._run_cli(
                ["p1", "p2", "p3", "p4", "--concurrency", "4"], fake
            )
        finally:
            cli._ERROR_RETRY_CONCURRENCY = original_retry_c
            cli._ERROR_RETRY_ROUNDS = original_rounds

        assert rc == 0
        assert persist.call_count == 4
        assert state["max_retry_inflight"] <= 2


class TestFullRunDefault:
    """Default full-run mode: no PIDs, no --review-all -> all converted papers."""

    @staticmethod
    def _result(pid: str) -> TapetumResult:
        return TapetumResult(
            pid=pid,
            whisker_verdict="pass",
            suggested_verdict="pass",
            confidence=0.9,
            escalated=False,
            tier1_model="mock",
            tier2_model=None,
            primary_concern="",
            reasoning="",
        )

    def _make_backend(self, paper_ids: list[str]):
        """Build a mock backend whose list_all_paper_ids and get_paper_md_path work."""
        backend = MagicMock()
        backend.list_all_paper_ids.return_value = paper_ids
        md_mock = MagicMock()
        md_mock.exists.return_value = True
        backend.get_paper_md_path.return_value = md_mock
        return backend

    def _run_cli_full(self, argv: list[str], paper_ids: list[str]):
        """Run cli._run in full-run default mode with mocked boundaries."""
        import logging as _logging
        from pathlib import Path

        from whisker.llm import cli

        fake_adj, state = self._tracking_adjudicate()
        args = cli._parse_args(argv)
        backend = self._make_backend(paper_ids)
        root = _logging.getLogger()
        saved_handlers = list(root.handlers)
        try:
            with (
                patch.object(cli, "adjudicate_paper", fake_adj),
                patch.object(cli, "open_backend", return_value=backend),
                patch.object(cli, "load_services", return_value=MagicMock()),
                patch.object(cli, "_probe_llm_endpoint", new=AsyncMock()),
                patch.object(
                    cli, "_persist_result", return_value=Path("out.json")
                ) as persist,
                patch.object(cli, "render_progress", return_value=0),
            ):
                asyncio.run(cli._run(args))
        finally:
            root.handlers = saved_handlers
        return persist, state

    def _tracking_adjudicate(self):
        state = {"order": [], "inflight": 0, "max_inflight": 0}

        async def fake(pid, backend, **kwargs):
            state["order"].append(pid)
            state["inflight"] += 1
            state["max_inflight"] = max(state["max_inflight"], state["inflight"])
            await asyncio.sleep(0.01)
            state["inflight"] -= 1
            return self._result(pid)

        return fake, state

    def test_no_args_enumerates_all_converted(self):
        """Bare invocation (no PIDs, no --review-all) adjudicates all papers."""
        persist, state = self._run_cli_full(
            ["--concurrency", "1"], ["P1R0", "P2R0", "P3R0"]
        )
        assert sorted(state["order"]) == ["P1R0", "P2R0", "P3R0"]
        assert persist.call_count == 3

    def test_full_run_incremental_is_default(self):
        """Full-run mode enables incremental (fingerprint skip) by default."""
        from whisker.llm import cli

        args = cli._parse_args([])
        assert not args.pids
        assert not args.review_all

    def test_force_disables_incremental_in_full_run(self):
        """--force in full-run mode disables the automatic incremental skip."""
        from whisker.llm import cli

        args = cli._parse_args(["--force"])
        assert args.force is True

    def test_explicit_pids_no_implicit_skip(self):
        """Explicit PIDs should NOT auto-enable incremental (backward compat)."""
        from whisker.llm import cli

        args = cli._parse_args(["P1R0", "P2R0"])
        assert not getattr(args, "incremental", False)


class _IdealCliBackend:
    def __init__(self, tmp_path: Path, suffix: str) -> None:
        self.md_path = tmp_path / "paperstore" / "p4020r0.md"
        self.md_path.parent.mkdir(exist_ok=True)
        self.md_path.write_text("# Candidate\n\nCandidate body.", encoding="utf-8")
        self.source_path = tmp_path / "paperstore" / f"p4020r0{suffix}"
        self.source_path.write_text("source", encoding="utf-8")

    def get_paper_md_path(self, pid: str) -> Path:
        return self.md_path

    def get_paper_md(self, pid: str) -> str:
        return self.md_path.read_text(encoding="utf-8")

    def get_source_path(self, pid: str) -> Path:
        return self.source_path


class TestCliIdealVerification:
    @staticmethod
    def _text_result() -> TapetumResult:
        return TapetumResult(
            pid="P4020R0",
            whisker_verdict="review",
            suggested_verdict="review",
            confidence=0.9,
            escalated=False,
            tier1_model="fast-service",
            tier2_model=None,
        )

    @staticmethod
    def _pdf_result():
        from whisker.llm.pdf_judge import PdfJudgeResult

        return PdfJudgeResult(
            pid="P4020R0",
            verdict="review",
            confidence=0.9,
            reasoning="source-aware result",
            judge_model="deep-service",
        )

    def _run(
        self,
        tmp_path: Path,
        *,
        suffix: str,
        ideal_text: str | None,
        ideal_bytes: bytes | None = None,
        verification_side_effect=None,
        verification_delay: float = 0.0,
        ideals_name: str = "ideals",
        incremental_state: dict | None = None,
    ):
        from whisker.llm import cli

        backend = _IdealCliBackend(tmp_path, suffix)
        ideals_dir = tmp_path / ideals_name
        ideals_dir.mkdir()
        assert ideal_text is None or ideal_bytes is None
        if ideal_text is not None:
            (ideals_dir / "p4020r0.md").write_text(
                ideal_text,
                encoding="utf-8",
                newline="",
            )
        elif ideal_bytes is not None:
            (ideals_dir / "p4020r0.md").write_bytes(ideal_bytes)
        model_backend = MagicMock()
        registry = SimpleNamespace(
            services={"deep-service": model_backend},
            api_key_envs={},
        )
        prompt = SimpleNamespace(
            system_prompt="base prompt",
            services={
                "fast": "deep-service",
                "deep": "deep-service",
                "default": "deep-service",
            },
            steps=(),
        )
        services_config = {
            "services": {
                "deep-service": {
                    "backend": "vllm_thinking",
                    "model": "deepseek-v4-pro",
                    "base_url": "https://models.example/v1",
                }
            }
        }
        events: list[str] = []
        ideal_reads = 0
        original_read_bytes = Path.read_bytes

        def read_bytes(path):
            nonlocal ideal_reads
            if path.parent == ideals_dir:
                ideal_reads += 1
            return original_read_bytes(path)

        async def adjudicate(*_args, **_kwargs):
            events.append("text-judge")
            return self._text_result()

        async def judge_pdf(*_args, **_kwargs):
            events.append("pdf-judge")
            return self._pdf_result()

        async def verify(*_args, **_kwargs):
            events.append("ideal")
            if verification_delay:
                await asyncio.sleep(verification_delay)
            if verification_side_effect is not None:
                raise verification_side_effect
            return IdealVerification(verdict="agree", discrepancies=[])

        def persist(result, *_args, **kwargs):
            events.append("persist")
            if incremental_state is not None:
                incremental_state["fingerprint"] = kwargs["fingerprint"]
            return Path("out.json")

        argv = ["P4020R0", "--concurrency", "1"]
        if incremental_state is not None:
            argv.append("--incremental")
        args = cli._parse_args(argv)
        with (
            patch.object(cli, "open_backend", return_value=backend),
            patch.object(cli, "_load_services_config", return_value=services_config),
            patch.object(cli, "load_services", return_value=registry),
            patch.object(cli, "_probe_llm_endpoint", new=AsyncMock()),
            patch.object(cli, "_PAPER_TIMEOUT_SECONDS", 0.01),
            patch.object(cli.PipelinePrompt, "load", return_value=prompt),
            patch.object(cli, "find_ideals_dir", return_value=ideals_dir),
            patch.object(Path, "read_bytes", read_bytes),
            patch.object(
                cli,
                "_read_existing_fingerprint",
                side_effect=lambda *_args: (
                    incremental_state.get("fingerprint")
                    if incremental_state is not None
                    else None
                ),
            ),
            patch.object(cli, "adjudicate_paper", side_effect=adjudicate),
            patch.object(cli, "judge_pdf_extraction", side_effect=judge_pdf),
            patch.object(cli, "verify_against_ideal", side_effect=verify) as verifier,
            patch.object(cli, "_persist_result", side_effect=persist) as persist_text,
            patch.object(
                cli,
                "_persist_lane_result",
                side_effect=persist,
            ) as persist_pdf,
            patch.object(cli, "_write_error_tombstone") as tombstone,
        ):
            asyncio.run(cli._run(args))

        return SimpleNamespace(
            events=events,
            verifier=verifier,
            persist_text=persist_text,
            persist_pdf=persist_pdf,
            tombstone=tombstone,
            ideal_reads=ideal_reads,
        )

    def test_no_ideal_makes_no_call_and_preserves_text_result(self, tmp_path):
        run = self._run(tmp_path, suffix=".html", ideal_text=None)

        run.verifier.assert_not_awaited()
        result = run.persist_text.call_args.args[0]
        assert result.ideal_verification is None
        assert "ideal_verification" not in result.to_dict()
        assert run.events == ["text-judge", "persist"]

    def test_text_ideal_runs_once_after_judge_and_attaches_before_persist(
        self,
        tmp_path,
    ):
        run = self._run(
            tmp_path,
            suffix=".html",
            ideal_text="# Ideal\n\nIdeal body.",
        )

        run.verifier.assert_awaited_once()
        result = run.persist_text.call_args.args[0]
        assert result.ideal_verification.verdict == "agree"
        assert run.events == ["text-judge", "ideal", "persist"]
        assert run.verifier.await_args.args[1] == "# Candidate\n\nCandidate body."
        assert run.verifier.await_args.args[2] == "# Ideal\n\nIdeal body."
        assert run.verifier.await_args.args[0].service_name == "deep-service"
        assert run.ideal_reads == 1
        fingerprint = run.persist_text.call_args.kwargs["fingerprint"]
        assert fingerprint["ideal_sha256"] == hashlib.sha256(
            run.verifier.await_args.args[2].encode("utf-8")
        ).hexdigest()

    def test_pdf_ideal_runs_once_after_judge_and_attaches_before_persist(
        self,
        tmp_path,
    ):
        run = self._run(
            tmp_path,
            suffix=".pdf",
            ideal_text="# Ideal\n\nIdeal body.",
        )

        run.verifier.assert_awaited_once()
        result = run.persist_pdf.call_args.args[0]
        assert result.ideal_verification.verdict == "agree"
        assert run.events == ["pdf-judge", "ideal", "persist"]

    def test_pdf_no_ideal_makes_no_call_and_preserves_result(self, tmp_path):
        run = self._run(tmp_path, suffix=".pdf", ideal_text=None)

        run.verifier.assert_not_awaited()
        result = run.persist_pdf.call_args.args[0]
        assert result.ideal_verification is None
        assert run.events == ["pdf-judge", "persist"]

    def test_ideal_failure_persists_judge_with_ideal_pending(
        self,
        tmp_path,
    ):
        error = RuntimeError("ideal verifier failed")
        run = self._run(
            tmp_path,
            suffix=".html",
            ideal_text="# Ideal",
            verification_side_effect=error,
        )

        run.persist_text.assert_called_once()
        result = run.persist_text.call_args.args[0]
        assert result.ideal_verification is None
        assert result.ideal_pending is True
        run.tombstone.assert_not_called()

    def test_ideal_timeout_persists_judge_with_ideal_pending(self, tmp_path):
        run = self._run(
            tmp_path,
            suffix=".html",
            ideal_text="# Ideal",
            verification_delay=0.05,
        )

        run.persist_text.assert_called_once()
        result = run.persist_text.call_args.args[0]
        assert result.ideal_pending is True
        run.tombstone.assert_not_called()

    def test_pdf_ideal_failure_persists_judge_with_ideal_pending(self, tmp_path):
        error = RuntimeError("pdf ideal verifier failed")
        run = self._run(
            tmp_path,
            suffix=".pdf",
            ideal_text="# Ideal",
            verification_side_effect=error,
        )

        run.persist_pdf.assert_called_once()
        result = run.persist_pdf.call_args.args[0]
        assert result.ideal_pending is True
        run.tombstone.assert_not_called()

    def test_pdf_ideal_timeout_persists_judge_with_ideal_pending(self, tmp_path):
        run = self._run(
            tmp_path,
            suffix=".pdf",
            ideal_text="# Ideal",
            verification_delay=0.05,
        )

        run.persist_pdf.assert_called_once()
        result = run.persist_pdf.call_args.args[0]
        assert result.ideal_pending is True
        run.tombstone.assert_not_called()

    @pytest.mark.parametrize(
        ("suffix", "judge_event"),
        [
            (".html", "text-judge"),
            (".pdf", "pdf-judge"),
        ],
    )
    def test_invalid_utf8_ideal_runs_source_judge_before_failing(
        self,
        tmp_path,
        suffix,
        judge_event,
    ):
        state: dict = {}
        self._run(
            tmp_path,
            suffix=suffix,
            ideal_text=None,
            ideals_name=f"absent-{judge_event}",
            incremental_state=state,
        )

        run = self._run(
            tmp_path,
            suffix=suffix,
            ideal_text=None,
            ideal_bytes=b"\xff\xfe invalid UTF-8",
            ideals_name=f"invalid-{judge_event}",
            incremental_state=state,
        )

        persist = (
            run.persist_text if suffix == ".html" else run.persist_pdf
        )
        persist.assert_called_once()
        result = persist.call_args.args[0]
        assert result.ideal_pending is True
        assert run.ideal_reads == 1
        run.verifier.assert_not_awaited()
        run.tombstone.assert_not_called()
        assert judge_event in run.events

    def test_incremental_reruns_once_for_ideal_add_change_remove(
        self,
        tmp_path,
    ):
        state: dict = {}

        absent = self._run(
            tmp_path,
            suffix=".html",
            ideal_text=None,
            ideals_name="absent-a",
            incremental_state=state,
        )
        absent_unchanged = self._run(
            tmp_path,
            suffix=".html",
            ideal_text=None,
            ideals_name="absent-b",
            incremental_state=state,
        )
        added = self._run(
            tmp_path,
            suffix=".html",
            ideal_text="# Ideal v1",
            ideals_name="added-a",
            incremental_state=state,
        )
        added_unchanged = self._run(
            tmp_path,
            suffix=".html",
            ideal_text="# Ideal v1",
            ideals_name="added-b",
            incremental_state=state,
        )
        changed = self._run(
            tmp_path,
            suffix=".html",
            ideal_text="# Ideal v2",
            ideals_name="changed-a",
            incremental_state=state,
        )
        changed_unchanged = self._run(
            tmp_path,
            suffix=".html",
            ideal_text="# Ideal v2",
            ideals_name="changed-b",
            incremental_state=state,
        )
        removed = self._run(
            tmp_path,
            suffix=".html",
            ideal_text=None,
            ideals_name="removed-a",
            incremental_state=state,
        )
        removed_unchanged = self._run(
            tmp_path,
            suffix=".html",
            ideal_text=None,
            ideals_name="removed-b",
            incremental_state=state,
        )

        assert absent.events == ["text-judge", "persist"]
        assert absent_unchanged.events == []
        assert added.events == ["text-judge", "ideal", "persist"]
        assert added_unchanged.events == []
        assert changed.events == ["text-judge", "ideal", "persist"]
        assert changed_unchanged.events == []
        assert removed.events == ["text-judge", "persist"]
        assert removed_unchanged.events == []


# -- Exit contract tests -------------------------------------------------------


class TestExitContract:
    """Tapetum advisory verdicts stay exit-0; operational errors yield exit-1."""

    @staticmethod
    def _result(pid: str, *, verdict: str = "pass", status: str = "ok") -> TapetumResult:
        return TapetumResult(
            pid=pid,
            whisker_verdict=verdict,
            suggested_verdict=verdict,
            confidence=0.9,
            escalated=False,
            tier1_model="mock",
            tier2_model=None,
            primary_concern="",
            reasoning="",
            status=status,
        )

    def _run_cli(self, argv: list[str], adjudicate_fake) -> int:
        """Run cli._run with mocked I/O; return the int exit code."""
        import logging as _logging
        from pathlib import Path as _Path

        from whisker.llm import cli

        args = cli._parse_args(argv)
        root = _logging.getLogger()
        saved_handlers = list(root.handlers)
        try:
            with (
                patch.object(cli, "adjudicate_paper", adjudicate_fake),
                patch.object(cli, "open_backend", return_value=MagicMock()),
                patch.object(cli, "load_services", return_value=MagicMock()),
                patch.object(cli, "_probe_llm_endpoint", new=AsyncMock()),
                patch.object(cli, "_persist_result", return_value=_Path("out.json")),
                patch.object(cli, "render_progress", return_value=0),
            ):
                rc = asyncio.run(cli._run(args))
        finally:
            root.handlers = saved_handlers
        return rc

    # -- Advisory verdicts stay exit 0 ----------------------------------------

    def test_advisory_pass_exits_zero(self):
        async def fake(pid, backend, **kw):
            return self._result(pid, verdict="pass")
        assert self._run_cli(["p1"], fake) == 0

    def test_advisory_review_exits_zero(self):
        async def fake(pid, backend, **kw):
            return self._result(pid, verdict="review")
        assert self._run_cli(["p1"], fake) == 0

    def test_advisory_fail_exits_zero(self):
        async def fake(pid, backend, **kw):
            return self._result(pid, verdict="not-llm-readable")
        assert self._run_cli(["p1"], fake) == 0

    # -- Operational errors yield exit 1 --------------------------------------

    def test_exception_yields_exit_one(self):
        async def fake(pid, backend, **kw):
            raise RuntimeError("boom")
        assert self._run_cli(["p1"], fake) == 1

    def test_mixed_batch_persists_success_exits_one(self):
        async def fake(pid, backend, **kw):
            if pid == "P2":
                raise RuntimeError("boom")
            return self._result(pid)
        assert self._run_cli(["p1", "p2", "p3", "--concurrency", "1"], fake) == 1

    def test_all_errors_exits_one(self):
        async def fake(pid, backend, **kw):
            raise RuntimeError("boom")
        assert self._run_cli(["p1", "p2", "--concurrency", "1"], fake) == 1

    def test_timeout_exits_one(self):
        from whisker.llm import cli

        async def slow(pid, backend, **kw):
            if pid == "P1":
                await asyncio.sleep(0.5)
            return self._result(pid)

        with patch.object(cli, "_text_lane_timeout_seconds", return_value=0.05):
            rc = self._run_cli(["p1", "p2", "--concurrency", "1"], slow)
        assert rc == 1

    def test_status_error_exits_one(self):
        """TapetumResult(status='error') is an operational failure, not advisory."""
        async def fake(pid, backend, **kw):
            return self._result(pid, verdict="review", status="error")
        assert self._run_cli(["p1"], fake) == 1

    def test_no_papers_exits_zero(self):
        """No papers selected -> informative exit 0."""
        from whisker.llm import cli
        args = cli._parse_args(["NONEXISTENT"])
        import logging as _logging
        root = _logging.getLogger()
        saved_handlers = list(root.handlers)
        try:
            with (
                patch.object(cli, "adjudicate_paper", AsyncMock()),
                patch.object(cli, "open_backend", return_value=MagicMock()),
                patch.object(cli, "load_services", return_value=MagicMock()),
                patch.object(cli, "_probe_llm_endpoint", new=AsyncMock()),
                patch.object(cli, "_persist_result", return_value=Path("out.json")),
                patch.object(cli, "render_progress", return_value=0),
            ):
                rc = asyncio.run(cli._run(args))
        finally:
            root.handlers = saved_handlers
        assert rc == 0

    def test_main_propagates_exit_code(self):
        """main() forwards _run()'s return code through SystemExit."""
        from whisker.llm import cli

        async def fake_run(args):
            return 1

        with (
            patch.object(cli, "_run", new=fake_run),
            patch.object(cli, "load_dotenv"),
            patch.object(cli, "find_dotenv", return_value=""),
            pytest.raises(SystemExit, match="1"),
        ):
            cli.main(["p1"])


# -- --all-pages CLI wiring ----------------------------------------------------


class TestAllPagesCli:
    """CLI flag, PDF kwarg forwarding, HTML loud-fail, timeout tombstone."""

    def test_all_pages_parses_and_appears_in_help(self):
        import contextlib
        import io

        from whisker.llm import cli

        args = cli._parse_args(["--all-pages"])
        assert args.all_pages is True
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), pytest.raises(SystemExit):
            cli._parse_args(["--help"])
        text = " ".join(buf.getvalue().split())
        assert "--all-pages" in text
        assert "EVERY physical PDF page" in text

    @staticmethod
    def _pdf_result(pid: str = "P1R0"):
        from whisker.llm.pdf_judge import PdfJudgeResult

        return PdfJudgeResult(
            pid=pid,
            verdict="review",
            confidence=0.9,
            reasoning="ok",
            judge_model="deep-service",
        )

    def _run_pdf_cli(
        self,
        tmp_path: Path,
        argv: list[str],
        *,
        judge_side_effect=None,
        sources: dict[str, str] | None = None,
    ):
        """Run cli._run for staged papers; return captured judge kwargs + rc."""
        import logging as _logging

        from whisker.llm import cli

        sources = sources or {"P1R0": ".pdf"}
        paperstore = tmp_path / "paperstore"
        paperstore.mkdir(parents=True, exist_ok=True)

        class _Backend:
            workspace_dir = tmp_path

            def get_paper_md_path(self, pid: str) -> Path:
                return paperstore / f"{pid.lower()}.md"

            def get_paper_md(self, pid: str) -> str:
                return self.get_paper_md_path(pid).read_text(encoding="utf-8")

            def get_source_path(self, pid: str) -> Path:
                return paperstore / f"{pid.lower()}{sources[pid.upper()]}"

            def get_trace_md_path(self, pid: str, tool: str = "") -> Path:
                suffix = f".{tool}" if tool else ""
                return paperstore / f"{pid.lower()}.trace{suffix}.md"

            def get_debug_md_path(self, pid: str, tool: str = "") -> Path:
                suffix = f".{tool}" if tool else ""
                return paperstore / f"{pid.lower()}.debug{suffix}.md"

            def list_all_paper_ids(self):
                return sorted(sources)

        backend = _Backend()
        for pid, suffix in sources.items():
            (paperstore / f"{pid.lower()}.md").write_text(
                f"# {pid}\n", encoding="utf-8"
            )
            (paperstore / f"{pid.lower()}{suffix}").write_bytes(
                b"%PDF-1.4 fake" if suffix == ".pdf" else b"<html></html>"
            )

        captured: list[dict] = []

        async def capture_judge(pid, _backend, agent, **kwargs):
            captured.append({"pid": pid, **kwargs})
            if judge_side_effect is not None:
                return await judge_side_effect(pid, _backend, agent, **kwargs)
            return self._pdf_result(pid)

        async def text_ok(pid, _backend, **kwargs):
            return TapetumResult(
                pid=pid,
                whisker_verdict="pass",
                suggested_verdict="pass",
                confidence=0.9,
                escalated=False,
                tier1_model="mock",
                tier2_model=None,
            )

        model_backend = MagicMock()
        registry = SimpleNamespace(
            services={"deep-service": model_backend},
            api_key_envs={},
        )
        prompt = SimpleNamespace(
            system_prompt="base",
            services={
                "fast": "deep-service",
                "deep": "deep-service",
                "default": "deep-service",
            },
            steps=(),
        )
        services_config = {
            "services": {
                "deep-service": {
                    "backend": "vllm_thinking",
                    "model": "m",
                    "base_url": "https://example/v1",
                }
            }
        }
        args = cli._parse_args(argv)
        root = _logging.getLogger()
        saved = list(root.handlers)
        try:
            with (
                patch.object(cli, "open_backend", return_value=backend),
                patch.object(
                    cli, "_load_services_config", return_value=services_config
                ),
                patch.object(cli, "load_services", return_value=registry),
                patch.object(cli, "_probe_llm_endpoint", new=AsyncMock()),
                patch.object(cli.PipelinePrompt, "load", return_value=prompt),
                patch.object(cli, "find_ideals_dir", return_value=None),
                patch.object(cli, "judge_pdf_extraction", side_effect=capture_judge),
                patch.object(cli, "adjudicate_paper", side_effect=text_ok),
                patch.object(
                    cli, "_persist_lane_result", return_value=Path("out.json")
                ),
                patch.object(
                    cli, "_persist_result", return_value=Path("out.json")
                ),
                patch.object(cli, "_pdf_page_count", return_value=5),
                patch.object(cli, "render_progress", return_value=0),
            ):
                rc = asyncio.run(cli._run(args))
        finally:
            root.handlers = saved
        return SimpleNamespace(captured=captured, rc=rc, backend=backend)

    @pytest.mark.parametrize(
        "extra_flags,expected_exhaustive",
        [
            ([], False),
            (["--exhaustive-units"], True),
            (["--inspect"], True),
            (["--exhaustive-units", "--inspect"], True),
        ],
    )
    def test_pdf_branch_forwards_all_pages_and_exhaustive(
        self, tmp_path, extra_flags, expected_exhaustive
    ):
        run = self._run_pdf_cli(
            tmp_path,
            ["P1R0", "--all-pages", "--concurrency", "1", *extra_flags],
        )
        assert len(run.captured) == 1
        kwargs = run.captured[0]
        assert kwargs["all_pages"] is True
        assert kwargs["exhaustive_units"] is expected_exhaustive
        assert isinstance(kwargs.get("progress"), dict)

    def test_inspect_alone_sets_exhaustive_units_on_pdf_lane(self, tmp_path):
        """Regression: --inspect must wire exhaustive_units on the PDF lane."""
        run = self._run_pdf_cli(
            tmp_path,
            ["P1R0", "--inspect", "--concurrency", "1"],
        )
        assert len(run.captured) == 1
        assert run.captured[0]["all_pages"] is False
        assert run.captured[0]["exhaustive_units"] is True

    def test_html_all_pages_errors_loudly_other_papers_continue(self, tmp_path):
        import json
        import logging as _logging

        from whisker.llm import cli

        sources = {"PHTML": ".html", "PPDF": ".pdf"}
        paperstore = tmp_path / "paperstore"
        paperstore.mkdir(parents=True, exist_ok=True)

        class _Backend:
            def get_paper_md_path(self, pid: str) -> Path:
                return paperstore / f"{pid.lower()}.md"

            def get_paper_md(self, pid: str) -> str:
                return self.get_paper_md_path(pid).read_text(encoding="utf-8")

            def get_source_path(self, pid: str) -> Path:
                return paperstore / f"{pid.lower()}{sources[pid.upper()]}"

        for pid, suffix in sources.items():
            (paperstore / f"{pid.lower()}.md").write_text(
                f"# {pid}\n", encoding="utf-8"
            )
            (paperstore / f"{pid.lower()}{suffix}").write_bytes(
                b"%PDF-1.4 fake" if suffix == ".pdf" else b"<html></html>"
            )

        judged: list[str] = []
        errors: list[Exception] = []

        async def capture_judge(pid, _backend, agent, **kwargs):
            judged.append(pid)
            return self._pdf_result(pid)

        async def text_must_not_run(pid, _backend, **kwargs):
            raise AssertionError(f"adjudicate_paper must not run for {pid}")

        model_backend = MagicMock()
        registry = SimpleNamespace(
            services={"deep-service": model_backend},
            api_key_envs={},
        )
        prompt = SimpleNamespace(
            system_prompt="base",
            services={
                "fast": "deep-service",
                "deep": "deep-service",
                "default": "deep-service",
            },
            steps=(),
        )
        services_config = {
            "services": {
                "deep-service": {
                    "backend": "vllm_thinking",
                    "model": "m",
                    "base_url": "https://example/v1",
                }
            }
        }
        real_tombstone = cli._write_error_tombstone

        def tracking_tombstone(pid, backend, exc, **kwargs):
            errors.append(exc)
            return real_tombstone(pid, backend, exc, **kwargs)

        args = cli._parse_args(
            ["PHTML", "PPDF", "--all-pages", "--concurrency", "1"]
        )
        root = _logging.getLogger()
        saved = list(root.handlers)
        try:
            with (
                patch.object(cli, "open_backend", return_value=_Backend()),
                patch.object(
                    cli, "_load_services_config", return_value=services_config
                ),
                patch.object(cli, "load_services", return_value=registry),
                patch.object(cli, "_probe_llm_endpoint", new=AsyncMock()),
                patch.object(cli.PipelinePrompt, "load", return_value=prompt),
                patch.object(cli, "find_ideals_dir", return_value=None),
                patch.object(
                    cli, "judge_pdf_extraction", side_effect=capture_judge
                ),
                patch.object(
                    cli, "adjudicate_paper", side_effect=text_must_not_run
                ),
                patch.object(
                    cli, "_persist_lane_result", return_value=Path("out.json")
                ),
                patch.object(cli, "_pdf_page_count", return_value=5),
                patch.object(cli, "render_progress", return_value=0),
                patch.object(
                    cli, "_write_error_tombstone", side_effect=tracking_tombstone
                ),
            ):
                rc = asyncio.run(cli._run(args))
        finally:
            root.handlers = saved

        assert rc == 1
        assert judged == ["PPDF"]
        assert len(errors) == 1 + cli._ERROR_RETRY_ROUNDS
        assert "--all-pages is PDF-only" in str(errors[0])
        tomb = tmp_path / "whisker" / "llm" / "phtml.whisker.tapetum.json"
        assert tomb.exists()
        payload = json.loads(tomb.read_text(encoding="utf-8"))
        assert payload["status"] == "error"
        assert payload["error"] == "RuntimeError"

    def test_timeout_tombstone_includes_partial_progress(self, tmp_path):
        async def timeout_after_progress(pid, backend, agent, **kwargs):
            progress = kwargs.get("progress")
            assert progress is not None
            progress.update(
                {
                    "phase": "unit_checks",
                    "checked_unit_ids": ["page:1", "page:2"],
                    "required_unit_ids": ["page:1", "page:2", "page:3"],
                    "page_count": 3,
                }
            )
            raise asyncio.TimeoutError()

        run = self._run_pdf_cli(
            tmp_path,
            ["P1R0", "--all-pages", "--concurrency", "1"],
            judge_side_effect=timeout_after_progress,
        )
        assert run.rc == 1
        tomb = tmp_path / "whisker" / "llm" / "p1r0.whisker.tapetum.json"
        assert tomb.exists()
        payload = __import__("json").loads(tomb.read_text(encoding="utf-8"))
        assert payload["status"] == "error"
        assert payload["error"] == "TimeoutError"
        assert payload["partial_progress"]["phase"] == "unit_checks"
        assert payload["partial_progress"]["checked_unit_ids"] == [
            "page:1",
            "page:2",
        ]
        assert payload["partial_progress"]["page_count"] == 3

    def test_pdf_branch_writes_trace_when_trace_flag_set(self, tmp_path):
        run = self._run_pdf_cli(
            tmp_path,
            ["P1R0", "--trace", "--concurrency", "1"],
        )
        assert run.rc == 0
        trace = tmp_path / "paperstore" / "p1r0.trace.tapetum_llm.md"
        assert trace.exists()
        text = trace.read_text(encoding="utf-8")
        assert text.startswith("# Tapetum_Llm P1R0 ")
        assert "## Result" in text

    def test_pdf_branch_writes_error_trace_on_pdf_lane_error(self, tmp_path):
        from whisker.llm.pdf_judge import PdfLaneError

        async def boom(pid, backend, agent, **kwargs):
            raise PdfLaneError(f"{pid}: judge call failed: boom")

        run = self._run_pdf_cli(
            tmp_path,
            ["P1R0", "--trace", "--concurrency", "1"],
            judge_side_effect=boom,
        )
        assert run.rc == 1
        trace = tmp_path / "paperstore" / "p1r0.trace.tapetum_llm.md"
        assert trace.exists()
        text = trace.read_text(encoding="utf-8")
        assert text.startswith("# Tapetum_Llm P1R0 ")
        assert "## Error" in text
        assert "PdfLaneError" in text


# -- LJF (longest job first) ordering -----------------------------------------


class TestLjfOrdering:
    def test_ljf_ordering(self, tmp_path):
        """Descending source size, ascending PID as tiebreak."""
        from whisker.llm.cli import _sort_pids_ljf

        sizes = {"PBIG": 3000, "PMED": 2000, "PSMALLB": 500, "PSMALLA": 500}
        paths: dict[str, Path] = {}
        for pid, size in sizes.items():
            p = tmp_path / f"{pid}.pdf"
            p.write_bytes(b"x" * size)
            paths[pid] = p

        class _Backend:
            def get_source_path(self, pid: str) -> Path:
                return paths[pid]

        pids = ["PMED", "PSMALLB", "PBIG", "PSMALLA"]
        ordered = _sort_pids_ljf(pids, _Backend())
        # PBIG (3000) > PMED (2000) > PSMALLA == PSMALLB (500, tied -> PID asc)
        assert ordered == ["PBIG", "PMED", "PSMALLA", "PSMALLB"]

    def test_ljf_missing_source_sorts_last(self, tmp_path):
        """A paper whose source cannot be stat'd sorts last (size=0)."""
        from whisker.llm.cli import _sort_pids_ljf

        present = tmp_path / "PGOOD.pdf"
        present.write_bytes(b"x" * 100)

        class _Backend:
            def get_source_path(self, pid: str) -> Path:
                if pid == "PGOOD":
                    return present
                raise FileNotFoundError(pid)

        ordered = _sort_pids_ljf(["PMISSING", "PGOOD"], _Backend())
        assert ordered == ["PGOOD", "PMISSING"]


# -- per-paper duration in sidecars -------------------------------------------


class _DurationBackend:
    """Minimal backend stub: only get_paper_md_path is needed by the
    persist helpers (sidecar_path / whisker_output_dir derive everything
    from it; no whisker sidecar exists so _read_whisker_sidecar stubs)."""

    def __init__(self, tmp_path: Path, pid: str) -> None:
        self.md_path = tmp_path / "paperstore" / f"{pid.lower()}.md"
        self.md_path.parent.mkdir(parents=True, exist_ok=True)
        self.md_path.write_text("# doc", encoding="utf-8")

    def get_paper_md_path(self, pid: str) -> Path:
        return self.md_path


class _FakeLaneResult:
    """Stands in for PdfJudgeResult/VlmDiffResult for _persist_lane_result."""

    def __init__(self, pid: str) -> None:
        self.pid = pid

    def to_sidecar_dict(self) -> dict:
        return {"pid": self.pid, "verdict": "pass"}


class TestDurationInSidecar:
    def test_duration_in_sidecar(self, tmp_path):
        """duration_seconds is persisted, rounded to 2 decimal places."""
        import json

        from whisker.llm.cli import _persist_lane_result

        backend = _DurationBackend(tmp_path, "P1R0")
        out_path = _persist_lane_result(
            _FakeLaneResult("P1R0"), backend, duration_seconds=12.3456,
        )
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert payload["duration_seconds"] == round(12.3456, 2)

    def test_duration_in_sidecar_text_lane(self, tmp_path):
        """Same contract for _persist_result (the markdown text lane)."""
        import json

        from whisker.llm.cli import _persist_result

        backend = _DurationBackend(tmp_path, "P2R0")
        result = TapetumResult(
            pid="P2R0",
            whisker_verdict="pass",
            suggested_verdict="pass",
            confidence=0.9,
            escalated=False,
            tier1_model="mock",
            tier2_model=None,
        )
        out_path = _persist_result(result, backend, duration_seconds=7.891)
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert payload["duration_seconds"] == round(7.891, 2)

    def test_duration_absent_when_none(self, tmp_path):
        """No duration_seconds key is written when duration_seconds=None."""
        import json

        from whisker.llm.cli import _persist_lane_result

        backend = _DurationBackend(tmp_path, "P3R0")
        out_path = _persist_lane_result(
            _FakeLaneResult("P3R0"), backend, duration_seconds=None,
        )
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert "duration_seconds" not in payload


class TestEvaluatedAtWarmMarker:
    """B2: evaluated_at is stamped on every actual evaluation (both lanes),
    never touched on a fingerprint skip (that path never calls persist)."""

    def test_persist_lane_result_stamps_evaluated_at(self, tmp_path):
        import json

        from whisker.llm.cli import _persist_lane_result

        backend = _DurationBackend(tmp_path, "P4R0")
        out_path = _persist_lane_result(_FakeLaneResult("P4R0"), backend)
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert isinstance(payload["evaluated_at"], str)
        assert payload["evaluated_at"]

    def test_persist_result_stamps_evaluated_at(self, tmp_path):
        import json

        from whisker.llm.cli import _persist_result

        backend = _DurationBackend(tmp_path, "P5R0")
        result = TapetumResult(
            pid="P5R0",
            whisker_verdict="pass",
            suggested_verdict="pass",
            confidence=0.9,
            escalated=False,
            tier1_model="mock",
            tier2_model=None,
        )
        out_path = _persist_result(result, backend)
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert isinstance(payload["evaluated_at"], str)
        assert payload["evaluated_at"]


class TestRefreshFusionOnSkip:
    """B3: a fingerprint skip must recompute fusion against the CURRENT
    det sidecar, not silently keep whatever fusion block was written the
    last time this paper was actually evaluated."""

    def test_stale_fusion_is_recomputed_against_current_det_sidecar(
        self, tmp_path,
    ):
        import json

        from whisker.det.score import VERDICT_FAIL, VERDICT_PASS
        from whisker.llm.cli import _refresh_fusion_on_skip

        det_dir = tmp_path / "whisker" / "det"
        det_dir.mkdir(parents=True)
        llm_dir = tmp_path / "whisker" / "llm"
        llm_dir.mkdir(parents=True)

        det_path = det_dir / "p6r0.whisker.json"
        det_path.write_text(
            json.dumps({"pid": "P6R0", "verdict": VERDICT_FAIL,
                        "hard_flags": ["gate:non_empty"], "soft_flags": []}),
            encoding="utf-8",
        )
        tap_path = llm_dir / "p6r0.whisker.tapetum.json"
        tap_path.write_text(
            json.dumps({
                "pid": "P6R0",
                "status": "ok",
                "suggested_verdict": VERDICT_PASS,
                "confidence": 0.95,
                "axis_findings": [],
                "evaluated_at": "2020-01-01T00:00:00+00:00",
                # Stale: written back when det was still "pass".
                "fusion": {"combined_verdict": VERDICT_PASS, "combined_rule": "agree"},
            }),
            encoding="utf-8",
        )

        backend = _DurationBackend(tmp_path, "P6R0")
        backend.workspace_dir = tmp_path

        _refresh_fusion_on_skip("P6R0", backend)

        refreshed = json.loads(tap_path.read_text(encoding="utf-8"))
        # Deterministic fail is a hard gate: fusion must reflect it now,
        # not the stale pass-agree rule from the old det sidecar.
        assert refreshed["fusion"]["combined_verdict"] == VERDICT_FAIL
        # evaluated_at (the warm marker) is untouched by a fusion refresh.
        assert refreshed["evaluated_at"] == "2020-01-01T00:00:00+00:00"
        assert refreshed["suggested_verdict"] == VERDICT_PASS

    def test_missing_tapetum_sidecar_is_a_noop(self, tmp_path):
        """No tapetum sidecar to refresh: must not raise or create one."""
        from whisker.llm.cli import _refresh_fusion_on_skip

        backend = _DurationBackend(tmp_path, "P7R0")
        backend.workspace_dir = tmp_path

        _refresh_fusion_on_skip("P7R0", backend)  # no exception
