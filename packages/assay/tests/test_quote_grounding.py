#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

"""Offline quote-grounding validator tests (ASSAY-005)."""

from __future__ import annotations

import logging

from assay.harness import ground_quotes, normalize_for_grounding, validate_quote
from assay.models import (
    AskOutput,
    CollectedItem,
    CollectedItems,
    FindingOutput,
    ItemOutput,
    PipelineState,
    QuoteCheckResult,
    QuoteGroundingReport,
)

PAPER_MD_EXACT = "Line A\nThe committee shall require X.\nLine C\n"
PAPER_MD_WHITESPACE_DRIFT = "Line A\nThe committee shall  require X.\nLine C\n"
PAPER_MD = PAPER_MD_WHITESPACE_DRIFT

QUOTE = "The committee shall require X."


def test_normalize_for_grounding_collapses_whitespace():
    assert normalize_for_grounding("shall  require") == "shall require"


def test_validate_quote_exact_substring_ok():
    assert QUOTE in PAPER_MD_EXACT
    result = validate_quote(QUOTE, 2, PAPER_MD_EXACT)
    assert result.ok
    assert not result.line_mismatch
    assert result.corrected_line == 2


def test_validate_quote_flags_nonsubstring():
    result = validate_quote("The committee shall ban Y.", 2, PAPER_MD)
    assert not result.ok


def test_validate_quote_whitespace_drift_ok():
    assert QUOTE not in PAPER_MD_WHITESPACE_DRIFT
    result = validate_quote(QUOTE, 2, PAPER_MD_WHITESPACE_DRIFT)
    assert result.ok


def test_validate_quote_wrong_line_sets_mismatch():
    result = validate_quote(QUOTE, 99, PAPER_MD)
    assert result.ok
    assert result.line_mismatch
    assert result.corrected_line == 2


PAPER_MD_MULTILINE = "Line A\nThe committee shall\nrequire X.\nLine D\n"


def test_validate_quote_multiline_wrong_line_sets_mismatch():
    result = validate_quote("The committee shall require X.", 99, PAPER_MD_MULTILINE)
    assert result.ok
    assert result.corrected_line == 2
    assert result.line_mismatch


def test_validate_quote_empty_ok():
    result = validate_quote("", 1, PAPER_MD)
    assert result.ok


def test_ground_quotes_batch():
    entries = [
        (QUOTE, 2, "claim", 1),
        ("The committee shall ban Y.", 2, "claim", 2),
    ]
    report = ground_quotes(entries, PAPER_MD)
    assert report.checked == 2
    assert report.ungrounded == 1
    assert len(report.failures) == 1
    assert report.failures[0].ref_id == 2


def test_quote_grounding_flags_nonsubstring():
    good = ItemOutput(type="claim", quote=QUOTE, line=2)
    bad = ItemOutput(type="claim", quote="The committee shall ban Y.", line=2)
    assert validate_quote(good.quote, good.line, PAPER_MD).ok
    assert not validate_quote(bad.quote, bad.line, PAPER_MD).ok


def test_collect_entries_skip_companion_source_pid():
    """Companion evidence (non-empty source_pid) is excluded from collect grounding."""
    from assay.pipeline import _collect_quote_grounding_entries

    items = CollectedItems(
        claims=[CollectedItem(type="claim", quote="paper claim", line=1, id=1)],
        evidence=[
            CollectedItem(type="evidence", quote="companion quote", line=5, id=2, source_pid="P1234"),
            CollectedItem(type="evidence", quote="paper evidence", line=2, id=3),
        ],
        concessions=[],
        questions=[],
        dependencies=[],
        scope=[],
    )
    asks = [AskOutput(id=4, quote="do X", line=3, target="LEWG", type="poll")]
    entries = _collect_quote_grounding_entries(items, asks)
    quotes = {e[0] for e in entries}
    assert "paper claim" in quotes
    assert "paper evidence" in quotes
    assert "do X" in quotes
    assert "companion quote" not in quotes


def test_collect_log_reports_collect_failures(caplog):
    """Collect-stage ungrounded quotes are logged under Collect only."""
    from assay.pipeline import _apply_collect_quote_grounding

    state = PipelineState(
        paper_md=PAPER_MD,
        items=CollectedItems(
            claims=[
                CollectedItem(
                    type="claim",
                    quote="fabricated collect quote",
                    line=1,
                    id=1,
                ),
            ],
            evidence=[],
            concessions=[],
            questions=[],
            dependencies=[],
            scope=[],
        ),
        asks=[],
    )
    with caplog.at_level(logging.WARNING, logger="assay.pipeline"):
        _apply_collect_quote_grounding(state)

    collect_logs = [
        r.message for r in caplog.records if "Collect quote grounding" in r.message
    ]
    assert len(collect_logs) == 1
    assert "1 ungrounded / 1 checked" in collect_logs[0]
    assert state.quote_grounding_collect is not None
    assert state.quote_grounding_collect.ungrounded == 1


def test_challenge_log_uses_challenge_only_report(caplog):
    """Collect ungrounded failures must not appear under Challenge WARNING logs."""
    from assay.pipeline import _apply_challenge_quote_grounding

    state = PipelineState(
        paper_md=PAPER_MD,
        quote_grounding_collect=QuoteGroundingReport(
            checked=1,
            ungrounded=1,
            failures=[
                QuoteCheckResult(
                    ok=False,
                    quote="fabricated collect quote",
                    line=1,
                    kind="claim",
                    ref_id=1,
                ),
            ],
        ),
        surviving=[],
        strengths=[],
    )
    with caplog.at_level(logging.WARNING, logger="assay.pipeline"):
        _apply_challenge_quote_grounding(state)

    challenge_logs = [
        r.message for r in caplog.records if "Challenge quote grounding" in r.message
    ]
    assert challenge_logs == []


def test_challenge_log_reports_challenge_failures(caplog):
    """Challenge-stage ungrounded quotes are logged under Challenge only."""
    from assay.pipeline import _apply_challenge_quote_grounding

    state = PipelineState(
        paper_md=PAPER_MD,
        quote_grounding_collect=QuoteGroundingReport(checked=0, ungrounded=0),
        surviving=[
            FindingOutput(
                id=1,
                title="bad finding",
                lens="Design",
                severity="minor",
                quote="fabricated finding quote",
                line=1,
                explanation="because",
            ),
        ],
        strengths=[],
    )
    with caplog.at_level(logging.WARNING, logger="assay.pipeline"):
        _apply_challenge_quote_grounding(state)

    challenge_logs = [
        r.message for r in caplog.records if "Challenge quote grounding" in r.message
    ]
    assert len(challenge_logs) == 1
    assert "1 ungrounded / 1 checked" in challenge_logs[0]
