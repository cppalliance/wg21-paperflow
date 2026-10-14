#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for CodeBoundaryJudgment schema and persist-on-ideal-error behavior.

Hermetic: no LLM calls, no pod, no paperstore. Validates schema constraints
and quote-grounding invariants from archived snippet patterns.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from whisker.llm.models import (
    CodeBoundaryFinding,
    CodeBoundaryJudgment,
)


def _finding(**overrides) -> dict:
    values = {
        "kind": "heading_in_fence",
        "verdict": "not-llm-readable",
        "candidate_quote": '## F. Modifications to "Header <cmath> synopsis"',
        "source_quote": "",
        "rule_id": "C1",
        "reasoning": "Heading sits inside cpp fence.",
    }
    values.update(overrides)
    return values


def _judgment(**overrides) -> dict:
    values = {
        "reasoning": "Checked three fences on page 7.",
        "page": "page:7",
        "findings": [_finding()],
        "verdict": "not-llm-readable",
        "confidence": 0.92,
    }
    values.update(overrides)
    return values


# -- Schema validation: at least one finding required --------------------------

def test_empty_findings_rejected():
    with pytest.raises(ValidationError, match="at least one finding"):
        CodeBoundaryJudgment(**_judgment(findings=[]))


def test_single_clean_finding_passes():
    judgment = CodeBoundaryJudgment(
        **_judgment(
            findings=[_finding(kind="clean", verdict="pass", rule_id="none")],
            verdict="pass",
        )
    )
    assert judgment.verdict == "pass"
    assert judgment.findings[0].kind == "clean"


def test_pass_with_defect_finding_rejected():
    """A pass verdict with a non-clean finding is rejected."""
    with pytest.raises(ValidationError, match="pass verdict requires only clean"):
        CodeBoundaryJudgment(
            **_judgment(
                findings=[_finding(kind="heading_in_fence", verdict="not-llm-readable")],
                verdict="pass",
            )
        )


def test_non_pass_with_only_clean_rejected():
    """A non-pass verdict with only clean findings is rejected."""
    with pytest.raises(ValidationError, match="non-pass verdict requires"):
        CodeBoundaryJudgment(
            **_judgment(
                findings=[_finding(kind="clean", verdict="pass", rule_id="none")],
                verdict="not-llm-readable",
            )
        )


# -- S1 heading-in-fence pattern (P0533R9 BASE, cmath synopsis) ---------------

def test_heading_in_fence_finding():
    """The LLM must be able to report a heading inside a cpp fence."""
    finding = CodeBoundaryFinding(
        kind="heading_in_fence",
        verdict="not-llm-readable",
        candidate_quote='## F. Modifications to "Header <cmath> synopsis"',
        rule_id="C1",
        reasoning="Heading inside cpp fence.",
    )
    assert finding.kind == "heading_in_fence"
    assert finding.rule_id == "C1"


def test_heading_in_fence_judgment():
    """A complete judgment for the cmath heading-in-fence case."""
    judgment = CodeBoundaryJudgment(**_judgment())
    assert judgment.verdict == "not-llm-readable"
    assert len(judgment.findings) == 1
    assert judgment.findings[0].kind == "heading_in_fence"


# -- S1 listing-split pattern (P0533R9 HEAD, split fences) ---------------------

def test_listing_split_finding():
    """Split-fence pattern: ellipsis fence + lone constexpr fence."""
    findings = [
        CodeBoundaryFinding(
            kind="listing_split",
            verdict="review",
            candidate_quote="```\n...\n```",
            rule_id="C1",
            reasoning="Ellipsis in its own fence.",
        ),
        CodeBoundaryFinding(
            kind="listing_split",
            verdict="review",
            candidate_quote="```cpp\nconstexpr\n```",
            rule_id="C1",
            reasoning="Lone constexpr fence.",
        ),
    ]
    judgment = CodeBoundaryJudgment(
        reasoning="Three fences for one listing.",
        page="page:7",
        findings=findings,
        verdict="review",
        confidence=0.85,
    )
    assert len(judgment.findings) == 2
    assert all(f.kind == "listing_split" for f in judgment.findings)


# -- S2 false wording on comment (P2040R0 BASE, <ins>// ko</ins>) -------------

def test_false_wording_on_comment_finding():
    """The LLM must report false <ins>/<del> on comment markers."""
    finding = CodeBoundaryFinding(
        kind="false_wording_on_comment",
        verdict="review",
        candidate_quote="<ins>// ko</ins>",
        rule_id="C6",
        reasoning="Wording tag on comment text.",
    )
    assert finding.kind == "false_wording_on_comment"
    assert "<ins>" in finding.candidate_quote


# -- Quote grounding (candidate_quote must be non-empty) ----------------------

def test_candidate_quote_min_length():
    """An empty candidate_quote must be rejected (grounding requirement)."""
    with pytest.raises(ValidationError):
        CodeBoundaryFinding(
            kind="clean",
            verdict="pass",
            candidate_quote="",
            rule_id="none",
            reasoning="Clean page.",
        )


# -- Five-field floor (MODELS.md stability floor) -----------------------------

def test_schema_has_five_plus_fields():
    """CodeBoundaryJudgment must have >= 5 fields for constrained-decoding
    stability (MODELS.md floor)."""
    schema = CodeBoundaryJudgment.model_json_schema()
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    assert len(properties) >= 5, (
        f"CodeBoundaryJudgment has {len(properties)} properties, need >= 5"
    )


def test_finding_schema_has_five_plus_fields():
    """CodeBoundaryFinding must have >= 5 fields."""
    schema = CodeBoundaryFinding.model_json_schema()
    properties = schema.get("properties", {})
    assert len(properties) >= 5, (
        f"CodeBoundaryFinding has {len(properties)} properties, need >= 5"
    )


# -- TapetumResult and PdfJudgeResult carry code_boundary field ----------------

def test_tapetum_result_code_boundary_in_to_dict():
    """TapetumResult.to_dict() includes code_boundary when non-empty."""
    from whisker.llm.models import TapetumResult

    result = TapetumResult(
        pid="P0533R9",
        whisker_verdict="review",
        suggested_verdict="review",
        confidence=0.85,
        escalated=False,
        tier1_model="deepseek",
        tier2_model=None,
        code_boundary=[{"page": "page:7", "verdict": "not-llm-readable", "findings": []}],
    )
    d = result.to_dict()
    assert "code_boundary" in d
    assert len(d["code_boundary"]) == 1


def test_tapetum_result_no_code_boundary_when_empty():
    """TapetumResult.to_dict() omits code_boundary when empty."""
    from whisker.llm.models import TapetumResult

    result = TapetumResult(
        pid="P0533R9",
        whisker_verdict="pass",
        suggested_verdict="pass",
        confidence=0.95,
        escalated=False,
        tier1_model="deepseek",
        tier2_model=None,
    )
    d = result.to_dict()
    assert "code_boundary" not in d


# -- Skip-clear on code pages (unit_judge heuristic) --------------------------

def test_code_page_indicators_match_cpp():
    """The _CODE_PAGE_INDICATORS regex fires on C++ code patterns."""
    from whisker.llm.unit_judge import _CODE_PAGE_INDICATORS

    code_text = (
        "constexpr float ceil(float x);\n"
        "template<class T>\n"
        "namespace std {\n"
    )
    assert _CODE_PAGE_INDICATORS.search(code_text) is not None


def test_code_page_indicators_skip_prose():
    """The heuristic should not fire on plain English prose."""
    from whisker.llm.unit_judge import _CODE_PAGE_INDICATORS

    prose = (
        "This paper proposes changes to the wording of the standard. "
        "The committee reviewed the proposal at the last meeting."
    )
    assert _CODE_PAGE_INDICATORS.search(prose) is None


# -- Inspect report rendering -------------------------------------------------

def test_inspect_report_renders_code_boundary():
    """The inspect report renders code_boundary findings."""
    from whisker.llm.inspect_report import format_paper_section

    whisker = {"pid": "P0533R9", "verdict": "review"}
    tapetum = {
        "pid": "P0533R9",
        "suggested_verdict": "review",
        "confidence": 0.85,
        "escalated": False,
        "tier1_model": "deepseek",
        "tier2_model": None,
        "axis_findings": [],
        "code_boundary": [
            {
                "page": "page:7",
                "verdict": "not-llm-readable",
                "reasoning": "Heading in fence.",
                "confidence": 0.9,
                "findings": [
                    {
                        "kind": "heading_in_fence",
                        "verdict": "not-llm-readable",
                        "candidate_quote": "## F. Modifications",
                        "source_quote": "",
                        "rule_id": "C1",
                        "reasoning": "H2 inside cpp fence.",
                    }
                ],
            }
        ],
    }
    section = format_paper_section(whisker, tapetum)
    assert "Code boundary" in section
    # _cell() escapes underscores for markdown tables
    assert "heading" in section and "fence" in section
    assert "C1" in section
