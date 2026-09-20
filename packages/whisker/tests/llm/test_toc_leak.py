#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the unpaired TOC-leak detector and shared clamp."""

import asyncio
from unittest.mock import MagicMock

from whisker.llm.adjudicate import _custom_decide, _PipelineState
from whisker.llm.models import Adjudication, AxisFinding, EvidenceSpan
from whisker.llm.toc_leak import (
    MIN_CLUSTER_RUN,
    clamp_toc_leak,
    detect_unpaired_toc_leak,
)


def test_wg21_shape_p3596r0():
    hits = detect_unpaired_toc_leak(
        "## 5 Lexical conventions [lex] 10\n\n"
        "## 5.11 Identifiers [lex.name] 12\n\n"
        "orphaned\n"
    )
    assert {h.heading for h in hits if h.kind == "wg21_shape"} == {
        "5 lexical conventions [lex] 10",
        "5.11 identifiers [lex.name] 12",
    }


def test_cluster_distinct_stems():
    hits = detect_unpaired_toc_leak(
        "## 1. Introduction 3\n\n## 2. Scope 5\n\n## 3. Definitions 7\n\nbody\n"
    )
    cluster = [h for h in hits if h.kind == "cluster"]
    assert len(cluster) >= MIN_CLUSTER_RUN
    assert MIN_CLUSTER_RUN == 3


def test_cluster_allows_short_body_gap():
    """1-2 nonblank lines between distinct-stem TOC entries still cluster."""
    hits = detect_unpaired_toc_leak(
        "## 1. Introduction 3\n\n"
        "see page.\n"
        "## 2. Scope 5\n\n"
        "see page.\n"
        "more.\n"
        "## 3. Definitions 7\n\n"
        "body\n"
    )
    cluster = [h for h in hits if h.kind == "cluster"]
    assert len(cluster) >= MIN_CLUSTER_RUN
    assert {h.heading for h in cluster} == {
        "1. introduction 3",
        "2. scope 5",
        "3. definitions 7",
    }


def test_negatives():
    cases = (
        "## Step 1\n\na\n\n## Step 2\n\nb\n\n## Step 3\n\nc\n",
        "## C++ 11\n\na\n\n## C++ 14\n\nb\n\n## C++ 17\n\nc\n",
        "## Contents of the proposal\n\ntext\n",
        "## Example\n\na\n\n## Example\n\nb\n",
        "## A\n\n```md\n## 5 Lexical conventions [lex] 10\n"
        "## 6 Basics [basic] 15\n## 7 Expressions [expr] 20\n```\n",
    )
    for body in cases:
        assert detect_unpaired_toc_leak(body) == []


def test_clamp_toc_leak_policy():
    hits = ["5 lexical conventions [lex] 10"]
    assert clamp_toc_leak("pass", hits, "none") == ("review", "major")
    assert clamp_toc_leak("review", hits, "minor") == ("review", "major")
    assert clamp_toc_leak("not-llm-readable", hits, "major") == ("not-llm-readable", "major")
    assert clamp_toc_leak("pass", [], "none") == ("pass", "none")
    assert clamp_toc_leak("review", [], "minor") == ("review", "minor")


def _decide(paper_md: str, findings: list[AxisFinding], *, verdict: str):
    state = _PipelineState(paper_md=paper_md, whisker_signals={"verdict": "pass"})
    state.tier1 = Adjudication(
        reasoning="ok",
        axis_findings=findings,
        worst_axis=findings[0].axis if findings else "structure",
        verdict=verdict,
        confidence=0.9,
        evidence_spans=[
            EvidenceSpan(axis="wording", quote="body text", reason="present"),
        ],
        primary_concern="none",
    )
    ctx = MagicMock()
    ctx.pid = "P1R0"
    ctx.prompt.services = {"fast": "svc", "deep": "svc2", "default": "svc"}
    asyncio.run(_custom_decide(state, ctx, MagicMock()))
    return state._result


_LEAK_MD = "## 5 Lexical conventions [lex] 10\n\nbody text\n"


def test_text_clamp_pass_creates_structure_review_major():
    result = _decide(
        _LEAK_MD,
        [AxisFinding(axis="wording", verdict="pass", severity="none", note="ok")],
        verdict="pass",
    )
    assert result.suggested_verdict == "review"
    structure = next(f for f in result.axis_findings if f["axis"] == "structure")
    assert structure["verdict"] == "review"
    assert structure["severity"] == "major"


def test_text_clamp_review_stays_review_major():
    result = _decide(
        _LEAK_MD,
        [AxisFinding(
            axis="structure", verdict="review", severity="minor", note="jump",
        )],
        verdict="review",
    )
    assert result.suggested_verdict == "review"
    structure = next(f for f in result.axis_findings if f["axis"] == "structure")
    assert structure["verdict"] == "review"
    assert structure["severity"] == "major"


def test_text_clamp_does_not_escalate_fail():
    result = _decide(
        _LEAK_MD,
        [AxisFinding(
            axis="wording", verdict="not-llm-readable", severity="major", note="garbled",
        )],
        verdict="not-llm-readable",
    )
    assert result.suggested_verdict == "not-llm-readable"
    structure = next(f for f in result.axis_findings if f["axis"] == "structure")
    assert structure["verdict"] == "review"
    assert structure["severity"] == "major"
