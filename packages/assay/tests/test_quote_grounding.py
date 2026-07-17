#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

"""Offline quote-grounding validator tests (ASSAY-005)."""

from __future__ import annotations

from assay.harness import ground_quotes, normalize_for_grounding, validate_quote
from assay.models import AskOutput, CollectedItem, CollectedItems, ItemOutput


PAPER_MD = "Line A\nThe committee shall  require X.\nLine C\n"


def test_normalize_for_grounding_collapses_whitespace():
    assert normalize_for_grounding("shall  require") == "shall require"


def test_validate_quote_exact_substring_ok():
    result = validate_quote("The committee shall require X.", 2, PAPER_MD)
    assert result.ok
    assert not result.line_mismatch
    assert result.corrected_line == 2


def test_validate_quote_flags_nonsubstring():
    result = validate_quote("The committee shall ban Y.", 2, PAPER_MD)
    assert not result.ok


def test_validate_quote_whitespace_drift_ok():
    result = validate_quote("The committee shall require X.", 2, PAPER_MD)
    assert result.ok


def test_validate_quote_wrong_line_sets_mismatch():
    result = validate_quote("The committee shall require X.", 99, PAPER_MD)
    assert result.ok
    assert result.line_mismatch
    assert result.corrected_line == 2


def test_validate_quote_empty_ok():
    result = validate_quote("", 1, PAPER_MD)
    assert result.ok


def test_ground_quotes_batch():
    entries = [
        ("The committee shall require X.", 2, "claim", 1),
        ("The committee shall ban Y.", 2, "claim", 2),
    ]
    report = ground_quotes(entries, PAPER_MD)
    assert report.checked == 2
    assert report.ungrounded == 1
    assert len(report.failures) == 1
    assert report.failures[0].ref_id == 2


def test_quote_grounding_flags_nonsubstring():
    good = ItemOutput(type="claim", quote="The committee shall require X.", line=2)
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
