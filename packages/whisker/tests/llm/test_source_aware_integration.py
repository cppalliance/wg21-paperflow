#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Integration tests for the source-aware unit check pipeline (v6).

Tests the wired path: pdf_judge -> extract_page_units -> route -> run_unit_checks.
Uses monkeypatching to control the LLM agent without network.
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pipeline import StepContext
from whisker.llm.adjudicate import (
    _custom_adjudicate,
    _custom_triage,
    _PipelineState,
    _run_html_unit_checks,
)
from whisker.llm.constants import MAX_UNIT_CHECKS
from whisker.llm.models import (
    Adjudication,
    AxisFinding,
    DefectFinding,
    MetadataOutlineCheck,
    UnitCheck,
)
from whisker.llm.pdf_judge import (
    PdfJudgment,
    judge_pdf_extraction,
)
from whisker.llm.source_router import RiskSignal, route_pdf_units
from whisker.llm.textlayer import PageUnit
from whisker.llm.unit_judge import (
    FULL_AUDIT_NO_SIGNAL_CONTEXT,
    UNIT_CHECK_SYSTEM_PROMPT,
    _mechanical_count,
    run_unit_checks,
    verify_defect_counts,
    verify_unit_evidence,
)

# -- Helpers --

def _make_page_unit(page: int, text: str, **kwargs) -> PageUnit:
    return PageUnit(
        page=page,
        text=text,
        heading_candidates=kwargs.get("heading_candidates", []),
        has_images=False,
        has_tables=False,
        caption_lines=kwargs.get("caption_lines", []),
        code_token_count=0,
        content_tokens=len(text.split()),
    )


class _StubAgent:
    """Returns a configurable sequence of responses."""

    chars_per_token = 4.0
    token_multiplier = 1.5
    max_context_window = 131072
    service_name = "stub-service"

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self._call_count = 0
        self.last_user_message: str | None = None
        self.last_system_prompt: str | None = None
        self.user_messages: list[str] = []
        self.system_prompts: list[str] = []

    @property
    def call_count(self) -> int:
        return self._call_count

    async def run(self, system_prompt, user_message, output_type, **kwargs):
        self.last_system_prompt = system_prompt
        self.last_user_message = user_message
        self.system_prompts.append(system_prompt)
        self.user_messages.append(user_message)
        self._call_count += 1
        if output_type is MetadataOutlineCheck:
            return MetadataOutlineCheck(
                reasoning="metadata and outline match",
                title_matches=True,
                document_number_matches=True,
                date_matches=True,
                heading_drift=[],
                missing_sections=[],
                verdict="pass",
            )
        if self._responses:
            return self._responses.pop(0)
        return PdfJudgment(
            verdict="pass", missing_content=[], confidence=0.95, reasoning="ok"
        )


def _pass_unit_check(unit_id: str = "page:1") -> UnitCheck:
    return UnitCheck(
        reasoning="content preserved",
        unit_id=unit_id,
        defects=[],
        verdict="pass",
        confidence=0.95,
    )


class _FailOneUnitAgent:
    """Pass every unit check except one unit_id, which raises."""

    service_name = "stub-service"

    def __init__(self, fail_unit_id: str) -> None:
        self.fail_unit_id = fail_unit_id
        self.call_count = 0
        self.checked_unit_ids: list[str] = []

    async def run(self, system_prompt, user_message, output_type, **kwargs):
        self.call_count += 1
        unit_line = next(
            (line for line in user_message.splitlines() if line.startswith("Unit: ")),
            "",
        )
        unit_id = unit_line.removeprefix("Unit: ").strip()
        self.checked_unit_ids.append(unit_id)
        if unit_id == self.fail_unit_id:
            raise RuntimeError(f"stub failure for {unit_id}")
        return _pass_unit_check(unit_id)


class _StubBackend:
    def __init__(self, pdf_path: Path, md: str) -> None:
        self._pdf = pdf_path
        self._md = md

    def get_source_path(self, pid):
        return self._pdf

    def get_paper_md(self, pid):
        return self._md


# -- Mechanical count verification tests --

class TestMechanicalCount:
    def test_keyword_count(self):
        text = "constexpr int x; constexpr float y; int z;"
        assert _mechanical_count("constexpr", text) == 2
        assert _mechanical_count("int", text) == 2
        assert _mechanical_count("float", text) == 1

    def test_case_sensitive(self):
        text = "Constexpr constexpr CONSTEXPR"
        assert _mechanical_count("constexpr", text) == 1


class TestVerifyDefectCounts:
    def test_countable_keyword_verified(self):
        groups = [{
            "defect_type": "qualifier_omission",
            "affected_count": 151,
            "severity": "critical",
            "examples": ["constexpr float logb(float x)"],
        }]
        unit_text_map = {
            "page:1": "constexpr int a; constexpr float b;",
            "page:2": "constexpr double c;",
        }
        candidate = "int a; float b; double c;"
        result = verify_defect_counts(groups, unit_text_map, candidate)
        assert len(result) == 1
        cv = result[0]["count_verification"]
        assert cv["count_status"] == "verified"
        assert cv["source_count"] == 3
        assert cv["candidate_count"] == 0
        assert cv["verified_delta"] == 3
        assert result[0]["verified_count"] == 3

    def test_non_countable_unverified(self):
        groups = [{
            "defect_type": "content_omission",
            "affected_count": 5,
            "severity": "high",
            "examples": ["some missing text"],
        }]
        result = verify_defect_counts(groups, {}, "candidate text")
        assert result[0]["count_verification"]["count_status"] == "unverified"

    def test_refuted_when_delta_is_zero(self):
        groups = [{
            "defect_type": "qualifier_omission",
            "affected_count": 10,
            "severity": "high",
            "examples": ["constexpr int x"],
        }]
        unit_text_map = {"page:1": "constexpr int x;"}
        candidate = "constexpr int x;"
        result = verify_defect_counts(groups, unit_text_map, candidate)
        cv = result[0]["count_verification"]
        assert cv["verified_delta"] == 0


class TestVerifyUnitEvidence:
    def test_source_grounded_candidate_present(self):
        unit_results = [{
            "unit_id": "page:1",
            "verdict": "not-llm-readable",
            "defects": [{
                "defect_type": "content_omission",
                "source_quote": "the quick brown fox jumps over the lazy dog",
                "affected_count": 1,
            }],
        }]
        unit_text_map = {
            "page:1": "the quick brown fox jumps over the lazy dog and more text"
        }
        candidate = "some preamble the quick brown fox jumps over the lazy dog and ending"
        result = verify_unit_evidence(unit_results, unit_text_map, candidate)
        assert len(result[0]["evidence_dispositions"]) == 1
        disp = result[0]["evidence_dispositions"][0]
        assert disp["source_grounded"] is True
        assert disp["candidate_status"] == "present_in_candidate"

    def test_source_ungrounded(self):
        unit_results = [{
            "unit_id": "page:1",
            "verdict": "not-llm-readable",
            "defects": [{
                "defect_type": "content_omission",
                "source_quote": "this quote is not in the source at all",
                "affected_count": 1,
            }],
        }]
        unit_text_map = {"page:1": "completely different text here in the source page"}
        candidate = "candidate markdown"
        result = verify_unit_evidence(unit_results, unit_text_map, candidate)
        disp = result[0]["evidence_dispositions"][0]
        assert disp["source_grounded"] is False
        assert disp["candidate_status"] == "source_ungrounded"


class TestRunUnitChecksContract:
    """Tests that run_unit_checks respects the RiskSignal/unit_text_map contract."""

    def test_no_signals_returns_none(self):
        result = asyncio.run(run_unit_checks(
            "P1R0", "# doc", AsyncMock(),
            risk_signals=[],
            unit_text_map={},
        ))
        assert result is None

    def test_cap_exceeded_returns_review(self):
        signals = [
            RiskSignal(f"page:{i}", "low_recall", "high", f"recall {i}")
            for i in range(MAX_UNIT_CHECKS + 5)
        ]
        agent = _StubAgent([
            _pass_unit_check(f"page:{i}") for i in range(MAX_UNIT_CHECKS)
        ])
        result = asyncio.run(run_unit_checks(
            "P1R0", "# doc", agent,
            risk_signals=signals,
            unit_text_map={f"page:{i}": f"text {i}" for i in range(MAX_UNIT_CHECKS + 5)},
        ))
        assert result is not None
        assert result.verdict == "review"
        assert result.unit_results == []
        assert result.coverage_complete is False
        assert len(result.unchecked_unit_ids) == MAX_UNIT_CHECKS + 5

    def test_missing_unit_text_is_unroutable_not_unchecked(self):
        """A routed unit without a source packet is pre-filtered, not cap-burning."""
        signals = [RiskSignal("page:99", "low_recall", "high", "missing")]
        result = asyncio.run(run_unit_checks(
            "P1R0", "# doc", AsyncMock(),
            risk_signals=signals,
            unit_text_map={},
        ))
        assert result is not None
        assert result.unit_results == []
        assert result.unroutable_unit_ids == ["page:99"]
        assert "page:99" not in result.unchecked_unit_ids
        assert result.coverage_complete is True
        assert result.verdict == "pass"


class TestRequiredUnitChecks:
    """required_unit_ids support for all-pages review mode (step 1)."""

    def test_required_units_with_zero_risk_signals(self):
        required = ["page:3", "page:1", "page:2"]
        agent = _StubAgent([_pass_unit_check(uid) for uid in sorted(required)])
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "# doc",
            agent,
            risk_signals=[],
            unit_text_map={uid: f"text for {uid}" for uid in required},
            required_unit_ids=required,
        ))
        assert result is not None
        assert result.coverage_complete is True
        assert result.checked_unit_ids == ["page:1", "page:2", "page:3"]
        assert agent.call_count == 3
        assert result.required_unit_ids == required

    def test_routed_and_required_overlap_checked_once(self):
        signals = [RiskSignal("page:2", "low_recall", "high", "recall 0.40")]
        agent = _StubAgent([_pass_unit_check("page:2")])
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "# doc",
            agent,
            risk_signals=signals,
            unit_text_map={"page:2": "source text for page 2"},
            required_unit_ids=["page:2"],
        ))
        assert result is not None
        assert agent.call_count == 1
        assert result.checked_unit_ids == ["page:2"]

    def test_required_units_bypass_max_unit_checks_cap(self):
        n = MAX_UNIT_CHECKS + 3
        required = [f"page:{i}" for i in range(n)]
        agent = _StubAgent([_pass_unit_check(uid) for uid in required])
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "# doc",
            agent,
            risk_signals=[],
            unit_text_map={uid: f"text {uid}" for uid in required},
            required_unit_ids=required,
        ))
        assert result is not None
        assert agent.call_count == n
        assert len(result.checked_unit_ids) == n
        assert result.coverage_complete is True

    def test_required_unit_missing_packet_incomplete(self):
        required = ["page:1", "page:2"]
        agent = _StubAgent([_pass_unit_check("page:1")])
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "# doc",
            agent,
            risk_signals=[],
            unit_text_map={"page:1": "present packet"},
            required_unit_ids=required,
        ))
        assert result is not None
        assert "page:2" in result.unchecked_unit_ids
        assert result.coverage_complete is False
        assert result.verdict == "review"

    def test_required_unit_failed_call_incomplete(self, monkeypatch):
        # Isolate from the verdict-first bifurcation (a separate feature):
        # under it, a failing unit is attempted twice (Stage 1 Clear, then
        # Stage 2 Defects), which is that feature's own concern, not this
        # required-unit fail-closed contract's.
        monkeypatch.setenv("TAPETUM_VERDICT_FIRST", "0")
        required = ["page:1", "page:2", "page:3"]
        agent = _FailOneUnitAgent("page:2")
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "# doc",
            agent,
            risk_signals=[],
            unit_text_map={uid: f"text {uid}" for uid in required},
            required_unit_ids=required,
        ))
        assert result is not None
        assert result.failed_unit_ids == ["page:2"]
        assert result.coverage_complete is False
        assert set(result.checked_unit_ids) == {"page:1", "page:3"}
        assert agent.call_count == 3

    def test_fleet_empty_signals_still_returns_none(self):
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "# doc",
            AsyncMock(),
            risk_signals=[],
            unit_text_map={},
            required_unit_ids=None,
        ))
        assert result is None

    def test_fleet_with_signals_selection_unchanged(self):
        signals = [
            RiskSignal(f"page:{i}", "low_recall", "high", f"recall {i}")
            for i in range(MAX_UNIT_CHECKS + 5)
        ]
        unit_text_map = {
            f"page:{i}": f"text {i}" for i in range(MAX_UNIT_CHECKS + 5)
        }
        agent_baseline = _StubAgent(
            [_pass_unit_check(f"page:{i}") for i in range(MAX_UNIT_CHECKS)]
        )
        baseline = asyncio.run(run_unit_checks(
            "P1R0",
            "# doc",
            agent_baseline,
            risk_signals=signals,
            unit_text_map=unit_text_map,
        ))
        agent_explicit = _StubAgent(
            [_pass_unit_check(f"page:{i}") for i in range(MAX_UNIT_CHECKS)]
        )
        explicit_none = asyncio.run(run_unit_checks(
            "P1R0",
            "# doc",
            agent_explicit,
            risk_signals=signals,
            unit_text_map=unit_text_map,
            required_unit_ids=None,
        ))
        assert baseline is not None and explicit_none is not None
        assert baseline.checked_unit_ids == explicit_none.checked_unit_ids
        assert baseline.unchecked_unit_ids == explicit_none.unchecked_unit_ids
        assert baseline.unit_selection == explicit_none.unit_selection
        assert baseline.required_unit_ids == []
        assert explicit_none.required_unit_ids == []

    def test_unit_prompt_inherits_full_contract_and_anywhere_rule(self):
        assert "TOC content that REMAINS" in UNIT_CHECK_SYSTEM_PROMPT
        assert "ANYWHERE in the candidate markdown" in UNIT_CHECK_SYSTEM_PROMPT
        agent = _StubAgent([_pass_unit_check("page:1")])
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "# doc",
            agent,
            risk_signals=[],
            unit_text_map={"page:1": "source packet text"},
            required_unit_ids=["page:1"],
        ))
        assert result is not None
        assert agent.last_system_prompt is not None
        assert "TOC content that REMAINS" in agent.last_system_prompt
        assert "ANYWHERE in the candidate markdown" in agent.last_system_prompt
        assert agent.last_user_message is not None
        assert FULL_AUDIT_NO_SIGNAL_CONTEXT in agent.last_user_message


class TestUnroutableUnits:
    """Routed units without source packets are pre-filtered before quota selection."""

    def test_routed_unit_without_packet_frees_slot(self, monkeypatch):
        # Pins the static MAX_UNIT_CHECKS cap: this test verifies the
        # slot-freeing mechanism itself (a packet-less routed unit is
        # pre-filtered before quota selection, not just capacity-starved),
        # which is orthogonal to whether the cap value is static or the
        # fleet-mode dynamic quota.
        monkeypatch.setenv("TAPETUM_DYNAMIC_QUOTA", "0")
        signals = [
            RiskSignal(f"page:{i}", "low_recall", "high", f"recall {i}")
            for i in range(1, 7)
        ]
        unit_text_map = {
            f"page:{i}": f"text {i}" for i in range(2, 7)
        }
        routable_ids = [f"page:{i}" for i in range(2, 7)]
        agent = _StubAgent(
            [_pass_unit_check(uid) for uid in routable_ids],
        )
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "# doc",
            agent,
            risk_signals=signals,
            unit_text_map=unit_text_map,
        ))
        assert result is not None
        assert result.unroutable_unit_ids == ["page:1"]
        assert "page:1" not in result.unchecked_unit_ids
        assert set(result.checked_unit_ids) == set(routable_ids)
        assert len(result.checked_unit_ids) == MAX_UNIT_CHECKS
        assert result.coverage_complete is True
        assert agent.call_count == MAX_UNIT_CHECKS

    def test_required_unit_without_packet_stays_unchecked(self):
        required = ["page:1", "page:2"]
        agent = _StubAgent([_pass_unit_check("page:1")])
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "# doc",
            agent,
            risk_signals=[],
            unit_text_map={"page:1": "present packet"},
            required_unit_ids=required,
        ))
        assert result is not None
        assert "page:2" in result.unchecked_unit_ids
        assert "page:2" not in result.unroutable_unit_ids
        assert result.coverage_complete is False
        assert result.verdict == "review"

    def test_unroutable_in_unit_selection(self):
        signals = [
            RiskSignal("page:1", "low_recall", "high", "recall 0.50"),
            RiskSignal("page:2", "low_recall", "high", "recall 0.40"),
        ]
        agent = _StubAgent([_pass_unit_check("page:2")])
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "# doc",
            agent,
            risk_signals=signals,
            unit_text_map={"page:2": "source text"},
        ))
        assert result is not None
        unroutable_entries = [
            entry for entry in result.unit_selection
            if entry["status"] == "unroutable"
        ]
        assert len(unroutable_entries) == 1
        assert unroutable_entries[0]["unit_id"] == "page:1"
        assert unroutable_entries[0]["reason"] == "no_source_packet"


class TestLaneIndependence:
    """Verify the LLM lane never reads the deterministic whisker sidecar."""

    def test_route_pdf_units_ignores_det_sidecar(self):
        """The router only reads source units + candidate MD, never det signals."""
        page = _make_page_unit(1, "x " * 200)
        signals = route_pdf_units([page], "x " * 200)
        assert isinstance(signals, list)

    def test_unit_judge_takes_no_sidecar_arg(self):
        """run_unit_checks signature has no whisker/det parameter."""
        import inspect
        sig = inspect.signature(run_unit_checks)
        param_names = set(sig.parameters.keys())
        forbidden = {"whisker_sidecar", "det_result", "sidecar", "whisker_signals"}
        assert not param_names.intersection(forbidden)


class _MetadataVerdictStubAgent(_StubAgent):
    """Same as ``_StubAgent`` but the metadata/outline check returns a
    configurable verdict instead of the hardcoded pass, for HTML
    metadata-short-circuit tests."""

    def __init__(self, responses: list, metadata_verdict: str) -> None:
        super().__init__(responses)
        self._metadata_verdict = metadata_verdict

    async def run(self, system_prompt, user_message, output_type, **kwargs):
        if output_type is MetadataOutlineCheck:
            self.last_system_prompt = system_prompt
            self.last_user_message = user_message
            self.system_prompts.append(system_prompt)
            self.user_messages.append(user_message)
            self._call_count += 1
            is_pass = self._metadata_verdict == "pass"
            return MetadataOutlineCheck(
                reasoning="metadata matches" if is_pass else "metadata mismatch",
                title_matches=is_pass,
                document_number_matches=True,
                date_matches=True,
                heading_drift=[],
                missing_sections=[],
                verdict=self._metadata_verdict,
            )
        return await super().run(system_prompt, user_message, output_type, **kwargs)


class TestHtmlSourceAwareIntegration:
    def test_metadata_outline_runs_when_router_is_clean(self, tmp_path):
        body = " ".join(f"word{i}" for i in range(80))
        source = tmp_path / "p.html"
        source.write_text(
            f"<html><body><h2>Design</h2><p>{body}</p></body></html>",
            encoding="utf-8",
        )
        backend = SimpleNamespace(get_source_path=lambda _pid: source)
        agent = _StubAgent([])
        state = _PipelineState(paper_md=f"## Design\n\n{body}")
        ctx = SimpleNamespace(
            pid="P1R0",
            backend=backend,
            agents={"fast": agent},
            debug_log=[],
        )

        asyncio.run(_run_html_unit_checks(state, ctx))

        assert state.metadata_outline_check is not None
        assert state.metadata_outline_check.verdict == "pass"
        assert state.risk_signals == []
        assert agent.call_count == 1

    def test_html_risky_unit_records_complete_coverage(self, tmp_path):
        body = " ".join(f"word{i}" for i in range(80))
        source = tmp_path / "p.html"
        source.write_text(
            f"<html><body><h2>Design</h2><p>{body}</p></body></html>",
            encoding="utf-8",
        )
        backend = SimpleNamespace(get_source_path=lambda _pid: source)
        unit_check = UnitCheck(
            reasoning="content preserved",
            unit_id="section:0",
            defects=[],
            verdict="pass",
            confidence=0.95,
        )
        agent = _StubAgent([unit_check])
        state = _PipelineState(paper_md=f"### Design\n\n{body}")
        ctx = SimpleNamespace(
            pid="P1R0",
            backend=backend,
            agents={"fast": agent},
            debug_log=[],
        )

        asyncio.run(_run_html_unit_checks(state, ctx))

        assert state.metadata_outline_check is not None
        assert state.unit_result is not None
        assert state.unit_result.coverage_complete is True
        assert state.unit_result.checked_unit_ids == ["section:0"]
        assert agent.call_count == 2

    def test_html_metadata_short_circuit(self, tmp_path):
        """A failing metadata check skips unit checks entirely (not exhaustive)."""
        body = " ".join(f"word{i}" for i in range(80))
        source = tmp_path / "p.html"
        source.write_text(
            f"<html><body><h2>Design</h2><p>{body}</p></body></html>",
            encoding="utf-8",
        )
        backend = SimpleNamespace(get_source_path=lambda _pid: source)
        unit_check = UnitCheck(
            reasoning="content preserved",
            unit_id="section:0",
            defects=[],
            verdict="pass",
            confidence=0.95,
        )
        agent = _MetadataVerdictStubAgent([unit_check], "not-llm-readable")
        state = _PipelineState(paper_md=f"### Design\n\n{body}")
        ctx = SimpleNamespace(
            pid="P1R0",
            backend=backend,
            agents={"fast": agent},
            debug_log=[],
        )

        asyncio.run(_run_html_unit_checks(state, ctx))

        assert state.metadata_outline_check is not None
        assert state.metadata_outline_check.verdict == "not-llm-readable"
        assert state.unit_result is None
        assert agent.call_count == 1  # metadata only; unit check skipped

    def test_html_metadata_short_circuit_bypassed_exhaustive(self, tmp_path):
        """--exhaustive-units keeps unit checks running despite metadata fail."""
        body = " ".join(f"word{i}" for i in range(80))
        source = tmp_path / "p.html"
        source.write_text(
            f"<html><body><h2>Design</h2><p>{body}</p></body></html>",
            encoding="utf-8",
        )
        backend = SimpleNamespace(get_source_path=lambda _pid: source)
        unit_check = UnitCheck(
            reasoning="content preserved",
            unit_id="section:0",
            defects=[],
            verdict="pass",
            confidence=0.95,
        )
        agent = _MetadataVerdictStubAgent([unit_check], "not-llm-readable")
        state = _PipelineState(paper_md=f"### Design\n\n{body}", exhaustive=True)
        ctx = SimpleNamespace(
            pid="P1R0",
            backend=backend,
            agents={"fast": agent},
            debug_log=[],
        )

        asyncio.run(_run_html_unit_checks(state, ctx))

        assert state.metadata_outline_check is not None
        assert state.metadata_outline_check.verdict == "not-llm-readable"
        assert state.unit_result is not None
        assert agent.call_count == 2  # metadata + unit check, bypassed


class TestPdfJudgeIntegration:
    """End-to-end integration: monolith + unit checks through judge_pdf_extraction."""

    @staticmethod
    def _make_pdf(path: Path, page_texts: list[str]) -> None:
        import pymupdf
        doc = pymupdf.open()
        for text in page_texts:
            page = doc.new_page()
            page.insert_textbox(
                pymupdf.Rect(72, 72, 540, 770), text, fontsize=11,
            )
        doc.save(str(path))
        doc.close()

    def test_risk_signals_populated_in_result(self, tmp_path, monkeypatch):
        """When page units produce risk signals, they appear in the result."""
        from whisker.llm.table_compare import TableCompareResult

        monolith_judgment = PdfJudgment(
            verdict="pass", missing_content=[], confidence=0.95, reasoning="clean"
        )

        low_recall_signal = RiskSignal("page:1", "low_recall", "high", "recall 0.50")
        monkeypatch.setattr(
            "whisker.llm.pdf_judge.extract_page_units",
            lambda _path: [_make_page_unit(1, "source text " * 50)],
        )
        monkeypatch.setattr(
            "whisker.llm.pdf_judge.route_pdf_units",
            lambda _units, _md: [low_recall_signal],
        )
        monkeypatch.setattr(
            "whisker.llm.pdf_judge.compare_pdf_tables",
            lambda _src, _md: TableCompareResult(
                total_source_tables=0,
                total_candidate_tables=0,
                matched_tables=0,
            ),
        )

        unit_check_response = UnitCheck(
            reasoning="content present",
            unit_id="page:1",
            defects=[],
            verdict="pass",
            confidence=0.9,
        )
        agent = _StubAgent([monolith_judgment, unit_check_response])

        long_text = "This is a WG21 paper about contracts. " * 20
        pdf = tmp_path / "p.pdf"
        self._make_pdf(pdf, [long_text + " unique-marker-xyz"])
        backend = _StubBackend(pdf, "# Title\n\n" + long_text)

        result = asyncio.run(judge_pdf_extraction("P1R0", backend, agent))
        assert len(result.risk_signals) == 1
        assert result.risk_signals[0]["signal_type"] == "low_recall"

    def test_defect_groups_demote_pass(self, tmp_path, monkeypatch):
        """Verified defects from unit checks demote a monolith pass to review."""
        # Isolate from the verdict-first bifurcation (a separate feature):
        # this stub's order-based response queue has one canned unit-check
        # answer, which the Stage 1 Clear request would consume and reject
        # (verdict="not-llm-readable"), starving the Stage 2 Defects request that
        # actually carries the defect this test asserts on.
        monkeypatch.setenv("TAPETUM_VERDICT_FIRST", "0")
        monolith_judgment = PdfJudgment(
            verdict="pass", missing_content=[], confidence=0.95, reasoning="clean"
        )

        long_text = "This is a WG21 paper about contracts. " * 20
        signal = RiskSignal("page:2", "token_delta", "medium", "constexpr delta")
        monkeypatch.setattr(
            "whisker.llm.pdf_judge.extract_page_units",
            lambda _path: [_make_page_unit(2, "constexpr int a; constexpr float b;")],
        )
        monkeypatch.setattr(
            "whisker.llm.pdf_judge.route_pdf_units",
            lambda _units, _md: [signal],
        )
        monkeypatch.setattr(
            "whisker.llm.pdf_judge.extract_textlayer",
            lambda _path: [long_text],
        )

        defect = DefectFinding(
            defect_type="qualifier_omission",
            source_unit="page:2",
            source_quote="constexpr int a",
            affected_count=2,
            severity="high",
            reasoning="missing constexpr",
        )
        unit_check_response = UnitCheck(
            reasoning="missing keywords",
            unit_id="page:2",
            defects=[defect],
            verdict="not-llm-readable",
            confidence=0.9,
        )
        agent = _StubAgent([monolith_judgment, unit_check_response])

        pdf = tmp_path / "p.pdf"
        self._make_pdf(pdf, [long_text + " unique-marker-xyz"])
        backend = _StubBackend(pdf, "# Title\n\n" + long_text)

        result = asyncio.run(judge_pdf_extraction("P1R0", backend, agent))
        assert result.verdict == "review"
        assert len(result.defect_groups) >= 1


# ---------------------------------------------------------------------------
# Text-lane monolith per-call timeout (Phase 1): _custom_triage /
# _custom_adjudicate must not hold a fleet slot forever if run_agent hangs.
# ---------------------------------------------------------------------------

class TestTextLaneMonolithTimeout:
    _TEST_TIMEOUT_SECONDS = 0.05

    @staticmethod
    async def _hang(*_args, **_kwargs):
        await asyncio.sleep(999)

    def _ctx(self, tmp_path, pid="P1R0") -> StepContext:
        # A missing/unreadable source is a documented best-effort fallback
        # in _build_triage_message (bare except -> no outline block), so a
        # nonexistent path is enough; no real source file needed for this test.
        backend = SimpleNamespace(
            get_source_path=lambda _pid: tmp_path / "missing.html",
        )
        return StepContext(pid=pid, backend=backend)

    def test_single_chunk_triage_timeout_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "whisker.llm.adjudicate.run_agent", self._hang,
        )
        monkeypatch.setattr(
            "whisker.llm.adjudicate.MONOLITH_TIMEOUT_SECONDS",
            self._TEST_TIMEOUT_SECONDS,
        )
        state = _PipelineState(paper_md="short markdown content")
        ctx = self._ctx(tmp_path)

        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(
                asyncio.wait_for(
                    _custom_triage(state, ctx, spec=None),
                    timeout=self._TEST_TIMEOUT_SECONDS * 20,
                ),
            )

    def test_multi_chunk_triage_timeout_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "whisker.llm.adjudicate.run_agent", self._hang,
        )
        monkeypatch.setattr(
            "whisker.llm.adjudicate.MONOLITH_TIMEOUT_SECONDS",
            self._TEST_TIMEOUT_SECONDS,
        )
        # Force a multi-chunk split with a tiny per-chunk budget, so a
        # short fixture paper_md still exercises the chunk-loop call site.
        monkeypatch.setattr("whisker.llm.adjudicate.MAX_PAPER_MD_CHARS", 20)
        paper_md = (
            "## Section A\n\nSome body text longer than twenty characters.\n\n"
            "## Section B\n\nMore body text longer than twenty characters.\n"
        )
        state = _PipelineState(paper_md=paper_md)
        ctx = self._ctx(tmp_path)

        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(
                asyncio.wait_for(
                    _custom_triage(state, ctx, spec=None),
                    timeout=self._TEST_TIMEOUT_SECONDS * 20,
                ),
            )

    def test_adjudicate_tier2_timeout_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "whisker.llm.adjudicate.run_agent", self._hang,
        )
        monkeypatch.setattr(
            "whisker.llm.adjudicate.MONOLITH_TIMEOUT_SECONDS",
            self._TEST_TIMEOUT_SECONDS,
        )
        # confidence=0.5 sits inside the ambiguous band, guaranteeing an
        # escalation signal fires without needing evidence grounding setup.
        tier1 = Adjudication(
            reasoning="tier1 reasoning",
            axis_findings=[
                AxisFinding(
                    axis="wording", verdict="pass", severity="none", note="ok",
                ),
            ],
            worst_axis="wording",
            verdict="pass",
            confidence=0.5,
            evidence_spans=[],
            primary_concern="none",
        )
        state = _PipelineState(paper_md="short markdown content", tier1=tier1)
        ctx = self._ctx(tmp_path)

        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(
                asyncio.wait_for(
                    _custom_adjudicate(state, ctx, spec=None),
                    timeout=self._TEST_TIMEOUT_SECONDS * 20,
                ),
            )
