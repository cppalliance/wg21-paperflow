#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

"""Regression gate for assay.harness deterministic reducers (ASSAY-002).

Locks full outputs of collect, cross_examine, and synthesize with hand-built
fixtures. No network, no LLM.
"""

from __future__ import annotations

import pytest

from assay.harness import LENS_ORDER, _dedup_items, collect, cross_examine, synthesize
from assay.models import (
    AskOutput,
    ChunkExtractOutput,
    CollectedItem,
    CollectedItems,
    CompoundOutput,
    CrossExamVerdict,
    DeriveOutput,
    FindingOutput,
    GapOutput,
    ItemOutput,
    KilledFinding,
    ScanOutput,
    SynthesisOutput,
)


def _item(
    item_type: str,
    quote: str,
    *,
    line: int = 1,
    quality_tier: str | None = None,
) -> ItemOutput:
    return ItemOutput(type=item_type, quote=quote, line=line, quality_tier=quality_tier)


def _chunk(chunk_index: int, items: list[ItemOutput]) -> ChunkExtractOutput:
    return ChunkExtractOutput(chunk_index=chunk_index, items=items)


def _gap(
    gap_text: str,
    *,
    primary_lens: str = "Performance",
    secondary_lens: str | None = None,
    chunk_index: int = 0,
) -> GapOutput:
    return GapOutput(
        chunk_index=chunk_index,
        item_quote="item",
        line=10,
        gap=gap_text,
        why_important="important",
        primary_lens=primary_lens,
        secondary_lens=secondary_lens,
        severity="significant",
    )


def _finding(
    finding_id: int,
    title: str,
    *,
    lens: str = "Design",
    severity: str = "significant",
    quote: str = "",
    explanation: str = "",
    damage: str = "",
) -> FindingOutput:
    return FindingOutput(
        id=finding_id,
        title=title,
        lens=lens,
        severity=severity,
        quote=quote,
        line=42,
        explanation=explanation or title,
        damage=damage,
    )


def _derive(central_claim: str) -> DeriveOutput:
    return DeriveOutput(
        central_claim=central_claim,
        problem_statement="legacy executors are slow",
        scope_boundary="networking executors only",
    )


def _empty_gaps_by_lens() -> dict[str, list[GapOutput]]:
    return {lens: [] for lens in LENS_ORDER}


def _assert_collect_result(
    result: tuple,
    *,
    items: CollectedItems,
    gaps_by_lens: dict[str, list[GapOutput]],
    asks: list,
    active_lenses: list[str],
    inactive_lenses: list[str],
    next_id: int,
) -> None:
    got_items, got_gaps, got_asks, got_active, got_inactive, got_next = result
    assert got_items == items
    assert got_gaps == gaps_by_lens
    assert got_asks == asks
    assert got_active == active_lenses
    assert got_inactive == inactive_lenses
    assert got_next == next_id


# -- collect + _dedup_items -------------------------------------------------


def test_collect_dedupes_claims_and_assigns_sequential_ids():
    duplicate_claim = "The proposal improves throughput for senders"
    extractions = [
        _chunk(
            0,
            [
                _item("claim", duplicate_claim, line=5),
                _item("evidence", "benchmark shows throughput", line=6),
                _item("concession", "minor API churn", line=7),
            ],
        ),
        _chunk(
            1,
            [
                _item("claim", duplicate_claim, line=20),
                _item(
                    "evidence", "benchmark shows throughput on large workloads", line=21
                ),
            ],
        ),
    ]
    scans = [
        ScanOutput(chunk_index=0, gaps=[_gap("missing latency data")]),
    ]
    start_id = 10

    result = collect(extractions, scans, start_id=start_id)

    expected_items = CollectedItems(
        claims=[
            CollectedItem(
                type="claim",
                quote=duplicate_claim,
                line=5,
                quality_tier=None,
                id=10,
            ),
        ],
        evidence=[
            CollectedItem(
                type="evidence",
                quote="benchmark shows throughput on large workloads",
                line=21,
                quality_tier=None,
                id=11,
            ),
        ],
        concessions=[
            CollectedItem(
                type="concession",
                quote="minor API churn",
                line=7,
                quality_tier=None,
                id=12,
            ),
        ],
        questions=[],
        dependencies=[],
        scope=[],
    )
    gap_with_id = _gap("missing latency data").model_copy(update={"id": 13})
    expected_gaps = _empty_gaps_by_lens()
    expected_gaps["Performance"] = [gap_with_id]
    expected_active = ["Performance", "Rationale"]
    expected_inactive = ["Design", "Specification", "Usability", "Ecosystem"]

    _assert_collect_result(
        result,
        items=expected_items,
        gaps_by_lens=expected_gaps,
        asks=[],
        active_lenses=expected_active,
        inactive_lenses=expected_inactive,
        next_id=14,
    )


def test_collect_groups_gaps_by_primary_and_secondary_lens():
    dual_lens_gap = _gap(
        "API shape unclear",
        primary_lens="Performance",
        secondary_lens="Design",
    )
    same_lens_gap = _gap(
        "normative wording gap",
        primary_lens="Specification",
        secondary_lens="Specification",
    )
    scans = [ScanOutput(chunk_index=0, gaps=[dual_lens_gap, same_lens_gap])]

    result = collect([], scans, start_id=1)
    _, gaps_by_lens, asks, active_lenses, inactive_lenses, next_id = result

    perf_gap = dual_lens_gap.model_copy(update={"id": 1})
    spec_gap = same_lens_gap.model_copy(update={"id": 2})
    expected_gaps = _empty_gaps_by_lens()
    expected_gaps["Performance"] = [perf_gap]
    expected_gaps["Design"] = [perf_gap]
    expected_gaps["Specification"] = [spec_gap]

    assert gaps_by_lens == expected_gaps
    assert asks == []
    assert active_lenses == ["Performance", "Design", "Specification", "Rationale"]
    assert inactive_lenses == ["Usability", "Ecosystem"]
    assert next_id == 3


def test_collect_builds_asks_from_ask_type_items():
    extractions = [
        _chunk(0, [_item("ask", "We request LEWG direction", line=99)]),
    ]

    result = collect(extractions, [], start_id=5)
    items, gaps_by_lens, asks, active_lenses, inactive_lenses, next_id = result

    assert items == CollectedItems()
    assert gaps_by_lens == _empty_gaps_by_lens()
    assert asks == [
        AskOutput(
            id=5,
            quote="We request LEWG direction",
            line=99,
            target="",
            type="",
        ),
    ]
    assert active_lenses == ["Rationale"]
    assert inactive_lenses == [
        "Performance",
        "Design",
        "Specification",
        "Usability",
        "Ecosystem",
    ]
    assert next_id == 6


def test_collect_dedupes_asks_across_chunks():
    duplicate_ask = "We request LEWG direction"
    extractions = [
        _chunk(0, [_item("ask", duplicate_ask, line=99)]),
        _chunk(1, [_item("ask", duplicate_ask, line=120)]),
    ]

    result = collect(extractions, [], start_id=5)

    _assert_collect_result(
        result,
        items=CollectedItems(),
        gaps_by_lens=_empty_gaps_by_lens(),
        asks=[
            AskOutput(
                id=5,
                quote=duplicate_ask,
                line=99,
                target="",
                type="",
            ),
        ],
        active_lenses=["Rationale"],
        inactive_lenses=[
            "Performance",
            "Design",
            "Specification",
            "Usability",
            "Ecosystem",
        ],
        next_id=6,
    )


def test_collect_does_not_dedup_questions_dependencies_scope():
    shared = "Should this apply to coroutines?"
    extractions = [
        _chunk(
            0,
            [
                _item("question", shared, line=1),
                _item("dependency", "P2300 sender algorithms", line=2),
                _item("scope", "executors only", line=3),
            ],
        ),
        _chunk(
            1,
            [
                _item("question", shared, line=10),
                _item("dependency", "P2300 sender algorithms", line=11),
                _item("scope", "executors only", line=12),
            ],
        ),
    ]

    result = collect(extractions, [], start_id=1)
    items, gaps_by_lens, asks, active_lenses, inactive_lenses, next_id = result

    assert items.questions == [
        _item("question", shared, line=1),
        _item("question", shared, line=10),
    ]
    assert items.dependencies == [
        _item("dependency", "P2300 sender algorithms", line=2),
        _item("dependency", "P2300 sender algorithms", line=11),
    ]
    assert items.scope == [
        _item("scope", "executors only", line=3),
        _item("scope", "executors only", line=12),
    ]
    assert items.claims == []
    assert gaps_by_lens == _empty_gaps_by_lens()
    assert asks == []
    assert active_lenses == ["Rationale"]
    assert inactive_lenses == [
        "Performance",
        "Design",
        "Specification",
        "Usability",
        "Ecosystem",
    ]
    assert next_id == 1


def test_dedup_items_drops_duplicate_and_absorbs_substring():
    items = [
        _item("claim", "alpha beta claim", line=1),
        _item("claim", "alpha beta claim", line=2),
        _item("claim", "short", line=3),
        _item("claim", "short but longer quote", line=4),
        _item("claim", "distinct item", line=5),
    ]

    result = _dedup_items(items)

    assert result == [
        _item("claim", "alpha beta claim", line=1),
        _item("claim", "short but longer quote", line=4),
        _item("claim", "distinct item", line=5),
    ]


# -- cross_examine (Step 14 apply) --------------------------------------------


def test_cross_examine_missing_verdict_raises():
    findings = [_finding(1, "orphan finding")]
    with pytest.raises(ValueError, match="incomplete: no verdict for \\[1\\] orphan finding"):
        cross_examine(findings, [])


def test_cross_examine_partial_batch_raises():
    f1 = _finding(1, "judged")
    f2 = _finding(2, "unjudged")
    verdict = CrossExamVerdict(
        finding_id=1,
        finding_title=f1.title,
        survived=True,
        killed_by=None,
        reasoning="holds up",
    )
    with pytest.raises(ValueError, match="incomplete: no verdict for \\[2\\] unjudged"):
        cross_examine([f1, f2], [verdict])


def test_cross_examine_orphan_verdict_warns(caplog):
    finding = _finding(1, "covered finding")
    verdicts = [
        CrossExamVerdict(
            finding_id=1,
            finding_title=finding.title,
            survived=True,
            killed_by=None,
            reasoning="holds up",
        ),
        CrossExamVerdict(
            finding_id=99,
            finding_title="orphan",
            survived=False,
            killed_by="phantom",
            reasoning="no such finding",
        ),
    ]
    with caplog.at_level("WARNING"):
        surviving, killed = cross_examine([finding], verdicts)
    assert surviving == [finding]
    assert killed == []
    assert "orphan verdict finding_id(s) [99]" in caplog.text


def test_cross_examine_orphan_only_does_not_raise(caplog):
    finding = _finding(1, "covered finding")
    verdict = CrossExamVerdict(
        finding_id=1,
        finding_title=finding.title,
        survived=True,
        killed_by=None,
        reasoning="holds up",
    )
    with caplog.at_level("WARNING"):
        surviving, killed = cross_examine([finding], [verdict])
    assert surviving == [finding]
    assert killed == []
    assert "orphan verdict" not in caplog.text


def test_cross_examine_survived_true_keeps_finding():
    finding = _finding(2, "survives challenge")
    verdict = CrossExamVerdict(
        finding_id=2,
        finding_title=finding.title,
        survived=True,
        killed_by=None,
        reasoning="challenge did not apply",
    )
    surviving, killed = cross_examine([finding], [verdict])
    assert surviving == [finding]
    assert killed == []


def test_cross_examine_killed_records_challenge_and_reasoning():
    finding = _finding(3, "killed by phantom", lens="Specification")
    verdict = CrossExamVerdict(
        finding_id=3,
        finding_title=finding.title,
        survived=False,
        killed_by="phantom",
        reasoning="no supporting passage",
    )
    surviving, killed = cross_examine([finding], [verdict])
    assert surviving == []
    assert killed == [
        KilledFinding(
            3,
            finding_title="killed by phantom",
            lens="Specification",
            challenge="phantom",
            reasoning="no supporting passage",
        ),
    ]


def test_cross_examine_killed_without_killed_by_uses_empty_challenge():
    finding = _finding(4, "killed without label")
    verdict = CrossExamVerdict(
        finding_id=4,
        finding_title=finding.title,
        survived=False,
        killed_by=None,
        reasoning="generic kill",
    )
    surviving, killed = cross_examine([finding], [verdict])
    assert surviving == []
    assert killed == [
        KilledFinding(
            4,
            finding_title="killed without label",
            lens="Design",
            challenge="",
            reasoning="generic kill",
        ),
    ]


def test_cross_examine_preserves_input_order():
    f1 = _finding(10, "first survives")
    f2 = _finding(11, "second killed")
    f3 = _finding(12, "third survives")
    verdicts = [
        CrossExamVerdict(
            finding_id=11,
            finding_title=f2.title,
            survived=False,
            killed_by="substance",
            reasoning="thin evidence",
        ),
        CrossExamVerdict(
            finding_id=10,
            finding_title=f1.title,
            survived=True,
            killed_by=None,
            reasoning="holds up",
        ),
        CrossExamVerdict(
            finding_id=12,
            finding_title=f3.title,
            survived=True,
            killed_by=None,
            reasoning="holds up",
        ),
    ]

    surviving, killed = cross_examine([f1, f2, f3], verdicts)

    assert surviving == [f1, f3]
    assert killed == [
        KilledFinding(
            11,
            finding_title="second killed",
            lens="Design",
            challenge="substance",
            reasoning="thin evidence",
        ),
    ]


# -- synthesize (Step 16) -----------------------------------------------------


def test_synthesize_compound_promotion_reason():
    finding = _finding(1, "allocator propagation gap")
    compound = CompoundOutput(
        name="allocator-state-loss",
        constituents=[1],
        mechanism="A breaks B.",
    )
    derive = _derive("senders deliver three times throughput improvement")

    result = synthesize([finding], [compound], derive)

    assert result == SynthesisOutput(
        verdict_label="Weakened",
        verdict_confidence="Medium",
        verdict_statement=(
            "The dominant structural weakness is allocator-state-loss. "
            "1 significant finding survived challenge."
        ),
        dominant_dynamic="allocator-state-loss",
        thesis_survives=True,
        thesis_statement=derive.central_claim,
        major_findings=[finding],
        regular_findings=[],
        promotion_reasons={1: "compound: allocator-state-loss"},
        critical_count=0,
        significant_count=1,
    )


def test_synthesize_compound_beats_thesis_overlap():
    central = "senders deliver three times throughput improvement"
    finding = _finding(
        2,
        "throughput claim unsupported",
        quote="senders deliver three times throughput",
        explanation="improvement not demonstrated",
    )
    compound = CompoundOutput(
        name="throughput-evidence-gap",
        constituents=[2],
        mechanism="missing benchmarks undermine throughput.",
    )
    derive = _derive(central)

    result = synthesize([finding], [compound], derive)

    assert result.promotion_reasons[2] == "compound: throughput-evidence-gap"
    assert result.promotion_reasons[2].startswith("compound:")
    assert result.major_findings == [finding]
    assert result.regular_findings == []


def test_synthesize_thesis_overlap_promotion_reason():
    central = "senders deliver three times throughput improvement"
    finding = _finding(
        3,
        "benchmark gap",
        quote="senders deliver three times throughput",
        explanation="improvement not demonstrated in paper",
    )
    derive = _derive(central)

    result = synthesize([finding], [], derive)

    assert result.major_findings == [finding]
    assert result.regular_findings == []
    assert result.promotion_reasons[3] == (
        "thesis-overlap: deliver, improvement, senders, three, throughput, times"
    )
    assert result.dominant_dynamic is None
    assert result.verdict_label == "Weakened"
    assert result.verdict_confidence == "Medium"
    assert result.thesis_survives is True
    assert result.thesis_statement == central
    assert result.critical_count == 0
    assert result.significant_count == 1
    assert result.verdict_statement == (
        "benchmark gap. 1 significant finding survived challenge."
    )


def test_synthesize_dominant_dynamic_tie_resolves_to_first():
    f1 = _finding(1, "first")
    f2 = _finding(2, "second")
    compounds = [
        CompoundOutput(name="first-dynamic", constituents=[1], mechanism="a"),
        CompoundOutput(name="second-dynamic", constituents=[2], mechanism="b"),
    ]
    derive = _derive("unrelated thesis statement here")

    result = synthesize([f1, f2], compounds, derive)

    assert result.dominant_dynamic == "first-dynamic"


def test_synthesize_dominant_dynamic_prefers_longer_constituent_chain():
    f1 = _finding(1, "first")
    f2 = _finding(2, "second")
    f3 = _finding(3, "third")
    compounds = [
        CompoundOutput(name="short-chain", constituents=[3], mechanism="c alone"),
        CompoundOutput(name="long-chain", constituents=[1, 2], mechanism="a then b"),
    ]
    derive = _derive("unrelated thesis statement here")

    result = synthesize([f1, f2, f3], compounds, derive)

    assert result.dominant_dynamic == "long-chain"


@pytest.mark.parametrize(
    "surviving, expected_label, expected_confidence, expected_thesis_survives, "
    "expected_critical, expected_significant",
    [
        ([], "Sound", "High", True, 0, 0),
        (
            [
                _finding(
                    1,
                    "thesis contradiction",
                    severity="critical",
                    quote="senders deliver three times throughput",
                    explanation="improvement claim fails",
                ),
            ],
            "Undermined",
            "High",
            False,
            1,
            0,
        ),
        (
            [
                _finding(
                    2,
                    "critical unrelated",
                    severity="critical",
                    quote="unrelated words only",
                )
            ],
            "Weakened",
            "High",
            True,
            1,
            0,
        ),
        (
            [_finding(3, "significant only", severity="significant")],
            "Weakened",
            "Medium",
            True,
            0,
            1,
        ),
        (
            [_finding(4, "minor only", severity="minor")],
            "Sound",
            "High",
            True,
            0,
            0,
        ),
    ],
)
def test_synthesize_verdict_matrix(
    surviving,
    expected_label,
    expected_confidence,
    expected_thesis_survives,
    expected_critical,
    expected_significant,
):
    derive = _derive("senders deliver three times throughput improvement")

    result = synthesize(surviving, [], derive)

    assert result.verdict_label == expected_label
    assert result.verdict_confidence == expected_confidence
    assert result.thesis_survives is expected_thesis_survives
    assert result.critical_count == expected_critical
    assert result.significant_count == expected_significant
    assert result.thesis_statement == derive.central_claim
    if expected_label == "Sound":
        assert result.verdict_statement == "No structural weaknesses found."
    else:
        assert "survived challenge" in result.verdict_statement


def test_synthesize_verdict_statement_uses_emergent_risk():
    finding = _finding(1, "major gap", severity="critical", damage="breaks ABI")
    compound = CompoundOutput(
        name="abi-break-chain",
        constituents=[1],
        mechanism="A then B.",
        emergent_risk="Deployments cannot adopt incrementally",
    )
    derive = _derive("unrelated thesis")

    result = synthesize([finding], [compound], derive)

    assert result.verdict_statement == (
        "Deployments cannot adopt incrementally. "
        "1 critical finding survived challenge."
    )


def test_synthesize_verdict_statement_uses_dominant_name_without_emergent_risk():
    finding = _finding(1, "major gap", severity="significant")
    compound = CompoundOutput(
        name="latency-chain",
        constituents=[1],
        mechanism="A then B.",
        emergent_risk=None,
    )
    derive = _derive("unrelated thesis")

    result = synthesize([finding], [compound], derive)

    assert result.verdict_statement == (
        "The dominant structural weakness is latency-chain. "
        "1 significant finding survived challenge."
    )


def test_synthesize_verdict_statement_uses_major_finding_without_compounds():
    finding = _finding(
        1,
        "Missing error handling",
        severity="significant",
        damage="Users get silent failures",
        quote="senders deliver three times throughput",
        explanation="improvement not demonstrated in paper",
    )
    derive = _derive("senders deliver three times throughput improvement")

    result = synthesize([finding], [], derive)

    assert result == SynthesisOutput(
        verdict_label="Weakened",
        verdict_confidence="Medium",
        verdict_statement=(
            "Missing error handling: Users get silent failures "
            "1 significant finding survived challenge."
        ),
        dominant_dynamic=None,
        thesis_survives=True,
        thesis_statement=derive.central_claim,
        major_findings=[finding],
        regular_findings=[],
        promotion_reasons={
            1: "thesis-overlap: deliver, improvement, senders, three, throughput, times",
        },
        critical_count=0,
        significant_count=1,
    )
