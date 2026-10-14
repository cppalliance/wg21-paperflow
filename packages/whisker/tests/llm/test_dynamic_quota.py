#
# Copyright (c) 2026 Sean Parsons
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for dynamic MAX_UNIT_CHECKS and combo_safe router tightening."""

from __future__ import annotations

import asyncio

from whisker.llm.constants import (
    FLEET_UNIT_CHECK_BASE,
    FLEET_UNIT_CHECK_CEILING,
    MAX_UNIT_CHECKS,
)
from whisker.llm.html_outline import SectionUnit
from whisker.llm.models import UnitCheck
from whisker.llm.source_router import RiskSignal, route_html_units
from whisker.llm.unit_judge import fleet_max_unit_checks, run_unit_checks


class TestFleetMaxUnitChecks:
    def test_no_signals_returns_base(self):
        assert fleet_max_unit_checks([], {}) == FLEET_UNIT_CHECK_BASE

    def test_high_severity_signal_bumps_by_one(self):
        signals_by_unit = {
            "page:1": [RiskSignal("page:1", "low_recall", "high", "x")],
        }
        assert (
            fleet_max_unit_checks(["page:1"], signals_by_unit)
            == FLEET_UNIT_CHECK_BASE + 1
        )

    def test_table_presence_signal_bumps_by_one(self):
        signals_by_unit = {
            "page:1": [RiskSignal("page:1", "table_presence", "medium", "x")],
        }
        assert (
            fleet_max_unit_checks(["page:1"], signals_by_unit)
            == FLEET_UNIT_CHECK_BASE + 1
        )

    def test_table_and_high_severity_bumps_by_two(self):
        signals_by_unit = {
            "page:1": [RiskSignal("page:1", "low_recall", "high", "x")],
            "page:2": [RiskSignal("page:2", "table_presence", "medium", "y")],
        }
        assert (
            fleet_max_unit_checks(["page:1", "page:2"], signals_by_unit)
            == FLEET_UNIT_CHECK_BASE + 2
        )

    def test_all_bumps_stay_under_ceiling(self):
        routable_risky_ids = [f"page:{i}" for i in range(9)]
        signals_by_unit = {
            "page:0": [RiskSignal("page:0", "low_recall", "high", "x")],
            "page:1": [RiskSignal("page:1", "table_presence", "medium", "y")],
        }
        result = fleet_max_unit_checks(routable_risky_ids, signals_by_unit)
        assert result == FLEET_UNIT_CHECK_BASE + 3
        assert result <= FLEET_UNIT_CHECK_CEILING

    def test_respects_custom_ceiling(self):
        routable_risky_ids = [f"page:{i}" for i in range(9)]
        signals_by_unit = {
            "page:0": [RiskSignal("page:0", "low_recall", "high", "x")],
            "page:1": [RiskSignal("page:1", "table_presence", "medium", "y")],
        }
        result = fleet_max_unit_checks(
            routable_risky_ids, signals_by_unit, ceiling=4,
        )
        assert result == 4


class TestConstants:
    def test_fleet_base_is_three(self):
        assert FLEET_UNIT_CHECK_BASE == 3

    def test_fleet_ceiling_is_seven(self):
        assert FLEET_UNIT_CHECK_CEILING == 7

    def test_static_max_unit_checks_unchanged(self):
        assert MAX_UNIT_CHECKS == 5


class TestComboSafeHeadingDrift:
    def test_skips_heading_drift_for_empty_source_section(self):
        """An outline entry whose section carries no source text (no source
        packet) must not raise heading_drift, even when the candidate is
        missing (or level-mismatched for) that heading."""
        units = [
            SectionUnit(
                section_id=0,
                tag="h2",
                title="Design",
                text="",
                content_tokens=0,
                code_blocks=0,
                has_tables=False,
                has_images=False,
            ),
        ]
        source_outline = [("h2", "Design")]
        candidate_md = "# Something else\n\nUnrelated body text."

        signals = route_html_units(units, candidate_md, source_outline)

        assert not any(s.signal_type == "heading_drift" for s in signals)

    def test_still_emits_heading_drift_for_nonempty_section(self):
        """Control: the same mismatch WITH source content still flags."""
        units = [
            SectionUnit(
                section_id=0,
                tag="h2",
                title="Design",
                text="Real source content describing the design.",
                content_tokens=6,
                code_blocks=0,
                has_tables=False,
                has_images=False,
            ),
        ]
        source_outline = [("h2", "Design")]
        candidate_md = "# Something else\n\nUnrelated body text."

        signals = route_html_units(units, candidate_md, source_outline)

        assert any(s.signal_type == "heading_drift" for s in signals)


class _StubAgent:
    service_name = "stub"

    async def run(self, system_prompt, user_message, output_type, **kwargs):
        return UnitCheck(
            reasoning="clean",
            unit_id="page:0",
            defects=[],
            verdict="pass",
            confidence=0.95,
        )


class TestDynamicQuotaWiring:
    """Integration: run_unit_checks honors the dynamic quota by default."""

    def _many_low_severity_signals(self, count: int) -> tuple[list[RiskSignal], dict[str, str]]:
        signals = [
            RiskSignal(f"page:{i}", "low_recall", "medium", "detail")
            for i in range(count)
        ]
        unit_text_map = {f"page:{i}": f"source text for page {i}" for i in range(count)}
        return signals, unit_text_map

    def test_fleet_mode_caps_at_dynamic_base_by_default(self, monkeypatch):
        monkeypatch.delenv("TAPETUM_DYNAMIC_QUOTA", raising=False)
        signals, unit_text_map = self._many_low_severity_signals(6)
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "# Candidate",
            _StubAgent(),
            risk_signals=signals,
            unit_text_map=unit_text_map,
        ))
        assert result is not None
        assert result.checked_unit_ids == []
        assert result.coverage_complete is False
        assert result.verdict == "review"

    def test_fleet_mode_runs_units_when_quota_fits(self, monkeypatch):
        monkeypatch.delenv("TAPETUM_DYNAMIC_QUOTA", raising=False)
        signals, unit_text_map = self._many_low_severity_signals(
            FLEET_UNIT_CHECK_BASE,
        )
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "# Candidate",
            _StubAgent(),
            risk_signals=signals,
            unit_text_map=unit_text_map,
        ))
        assert result is not None
        assert len(result.checked_unit_ids) == FLEET_UNIT_CHECK_BASE

    def test_static_env_toggle_falls_back_to_max_unit_checks(self, monkeypatch):
        monkeypatch.setenv("TAPETUM_DYNAMIC_QUOTA", "0")
        signals, unit_text_map = self._many_low_severity_signals(MAX_UNIT_CHECKS)
        result = asyncio.run(run_unit_checks(
            "P1R0",
            "# Candidate",
            _StubAgent(),
            risk_signals=signals,
            unit_text_map=unit_text_map,
        ))
        assert result is not None
        assert len(result.checked_unit_ids) == MAX_UNIT_CHECKS
