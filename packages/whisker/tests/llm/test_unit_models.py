#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for source-aware unit-check structured output models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from whisker.llm.models import (
    DefectFinding,
    IdealDiscrepancy,
    IdealVerification,
    MetadataOutlineCheck,
    TapetumResult,
    UnitCheck,
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


def test_defect_finding_validates_count_gte_1():
    finding = _defect(affected_count=1)
    assert finding.affected_count == 1


def test_defect_finding_rejects_zero_count():
    with pytest.raises(ValidationError):
        _defect(affected_count=0)


def test_metadata_outline_check_valid():
    check = MetadataOutlineCheck(
        reasoning="Compared source metadata and heading levels.",
        title_matches=True,
        document_number_matches=True,
        date_matches=True,
        heading_drift=["h2:Abstract -> ###:Abstract"],
        missing_sections=[],
        verdict="review",
    )
    assert check.heading_drift == ["h2:Abstract -> ###:Abstract"]
    assert check.verdict == "review"


def test_unit_check_valid_with_defects():
    check = UnitCheck(
        reasoning="Checked declarations on the flagged page.",
        unit_id="page:3",
        defects=[_defect()],
        verdict="not-llm-readable",
        confidence=0.95,
    )
    assert check.defects[0].affected_count == 2
    assert check.unit_id == "page:3"


def test_unit_check_empty_defects_is_pass():
    check = UnitCheck(
        reasoning="No fidelity defects found.",
        unit_id="section:Abstract",
        defects=[],
        verdict="pass",
        confidence=0.9,
    )
    assert check.defects == []
    assert check.verdict == "pass"


def test_defect_finding_severity_literal():
    with pytest.raises(ValidationError):
        _defect(severity="major")


def test_defect_finding_table_flattened_type():
    """table_flattened is a valid defect_type value."""
    finding = _defect(defect_type="table_flattened")
    assert finding.defect_type == "table_flattened"


def _tapetum_result(**overrides) -> TapetumResult:
    values = {
        "pid": "P4020R0",
        "whisker_verdict": "review",
        "suggested_verdict": "review",
        "confidence": 0.9,
        "escalated": False,
        "tier1_model": "fast-service",
        "tier2_model": None,
    }
    values.update(overrides)
    return TapetumResult(**values)


def test_old_tapetum_result_without_ideal_data_stays_compatible():
    result = _tapetum_result()

    assert result.ideal_verification is None
    assert "ideal_verification" not in result.to_dict()


def test_tapetum_result_serializes_ideal_only_when_present():
    verification = IdealVerification(
        verdict="review",
        discrepancies=[
            IdealDiscrepancy(
                axis="headings",
                candidate_quote="### Scope",
                ideal_quote="## Scope",
                severity="major",
                explanation="The candidate demotes the section heading.",
            )
        ],
    )

    payload = _tapetum_result(ideal_verification=verification).to_dict()

    assert payload["ideal_verification"] == verification.model_dump()
