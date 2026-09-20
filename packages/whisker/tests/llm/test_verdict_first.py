# Copyright 2026 Sean Parsons
# Distributed under the Boost Software License, Version 1.0.

"""Tests for verdict-first UnitCheckClear/UnitCheckDefects bifurcation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from whisker.llm.models import (
    UNIT_CLEAR_CONFIDENCE_FLOOR,
    UNIT_CLEAR_MAX_TOKENS,
    UNIT_DEFECTS_MAX_TOKENS,
    DefectFinding,
    UnitCheck,
    UnitCheckClear,
    UnitCheckDefects,
    to_unit_check,
)


def _defect(**overrides) -> DefectFinding:
    values = {
        "defect_type": "qualifier_omission",
        "source_unit": "page:3",
        "source_quote": "constexpr float ceil(float x);",
        "candidate_location": "Wording declarations",
        "affected_count": 2,
        "severity": "high",
        "reasoning": "The candidate omits constexpr.",
    }
    values.update(overrides)
    return DefectFinding(**values)


def test_unit_check_clear_pass_validates():
    clear = UnitCheckClear(
        unit_id="page:5",
        verdict="pass",
        confidence=0.97,
        reasoning="",
    )
    assert clear.verdict == "pass"
    assert clear.unit_id == "page:5"


def test_unit_check_clear_rejects_non_pass_verdict():
    with pytest.raises(ValidationError):
        UnitCheckClear(
            unit_id="page:5",
            verdict="not-llm-readable",
            confidence=0.97,
        )


def test_unit_check_defects_rejects_pass_with_defects():
    with pytest.raises(ValidationError):
        UnitCheckDefects(
            unit_id="page:5",
            verdict="pass",
            confidence=0.9,
            reasoning="Checked declarations on the flagged page.",
            defects=[_defect()],
        )


def test_unit_check_defects_rejects_fail_without_defects():
    with pytest.raises(ValidationError):
        UnitCheckDefects(
            unit_id="page:5",
            verdict="not-llm-readable",
            confidence=0.9,
            reasoning="Checked declarations on the flagged page.",
            defects=[],
        )


def test_unit_check_defects_valid_fail_with_defects():
    defects_result = UnitCheckDefects(
        unit_id="page:5",
        verdict="not-llm-readable",
        confidence=0.9,
        reasoning="Checked declarations on the flagged page.",
        defects=[_defect()],
    )
    assert defects_result.verdict == "not-llm-readable"
    assert defects_result.defects[0].affected_count == 2


def test_to_unit_check_maps_clear_result():
    clear = UnitCheckClear(
        unit_id="section:Motivation",
        verdict="pass",
        confidence=0.92,
        reasoning="matches source wording",
    )
    check = to_unit_check(clear)

    assert isinstance(check, UnitCheck)
    assert check.unit_id == "section:Motivation"
    assert check.verdict == "pass"
    assert check.confidence == 0.92
    assert check.defects == []
    assert check.reasoning == "matches source wording"


def test_to_unit_check_empty_reasoning_uses_default():
    clear = UnitCheckClear(
        unit_id="page:5",
        verdict="pass",
        confidence=0.9,
        reasoning="",
    )
    check = to_unit_check(clear)

    assert check.reasoning == "unit matches"


def test_verdict_first_constants():
    assert UNIT_CLEAR_MAX_TOKENS == 128
    assert UNIT_DEFECTS_MAX_TOKENS == 768
    assert UNIT_CLEAR_CONFIDENCE_FLOOR == 0.85
