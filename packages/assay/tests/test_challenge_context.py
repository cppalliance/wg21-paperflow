#
# Copyright (c) 2026 Leo Chen (leo.chen0412@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from __future__ import annotations

from pipeline import StepContext

from assay.chunker import chunk_paper
from assay.locs import format_numbered_lines
from assay.models import ChunkEntry, FindingOutput, PipelineState
from assay.pipeline import CHALLENGE_CHUNK_CHAR_CAP, _build_cross_exam_user_message

P4160R0_REGRESSION_MARKER = "P4160R0_REGRESSION_MARKER_XYZZY"
CHALLENGE_MAX_BATCH = 15
RUNPOD_BODY_LIMIT_CHARS = 1_000_000


def _make_paper(line_count: int) -> str:
    return "\n".join(f"Content for line {i}" for i in range(1, line_count + 1))


def _legacy_cross_exam_user_message(
    findings_batch: list[FindingOutput],
    state: PipelineState,
    ctx: StepContext,
) -> str:
    """Pre-fix Challenge assembly: embed the full chunk once per finding."""
    paper_lines = state.paper_md.splitlines()
    chunk_by_line: dict[int, ChunkEntry] = {}
    for ch in state.chunk_map or []:
        for ln in range(ch.start_line, ch.end_line + 1):
            chunk_by_line[ln] = ch

    parts = ["## Findings to cross-examine\n\n"]
    for f in findings_batch:
        parts.append(f"### [{f.id}] {f.title}\n\n")
        ch = chunk_by_line.get(f.line) if f.line > 0 else None
        if ch is not None:
            context = format_numbered_lines(paper_lines, ch.start_line, ch.end_line)
            parts.append(
                f"**Containing chunk: {ch.heading} (lines {ch.start_line}-{ch.end_line}):**\n\n"
                f"{ctx.inject_untrusted(context)}\n\n"
            )
    return "".join(parts)


class TestChallengeContext:
    def test_deduplicates_shared_chunk_within_batch(self):
        paper_md = _make_paper(20)
        shared_chunk = ChunkEntry(
            index=0,
            heading="Shared section",
            start_line=1,
            end_line=20,
            char_count=200,
        )
        state = PipelineState(
            paper_id="P9999R0",
            paper_md=paper_md,
            chunk_map=[shared_chunk],
        )
        findings = [
            FindingOutput(
                id=1,
                title="Finding one",
                lens="Design",
                severity="minor",
                quote="q1",
                line=5,
                explanation="explanation one",
            ),
            FindingOutput(
                id=2,
                title="Finding two",
                lens="Design",
                severity="minor",
                quote="q2",
                line=10,
                explanation="explanation two",
            ),
            FindingOutput(
                id=3,
                title="Finding three",
                lens="Design",
                severity="minor",
                quote="q3",
                line=15,
                explanation="explanation three",
            ),
        ]
        ctx = StepContext()

        message = _build_cross_exam_user_message(findings, state, ctx)

        assert "## Source chunks" in message
        assert message.count("### Shared section (lines 1-20)") == 1
        assert message.count("Content for line 10") == 1
        assert message.count("see Source chunks above") == len(findings)

    def test_oversized_chunk_uses_line_window(self):
        paper_md = _make_paper(200)
        oversized_chunk = ChunkEntry(
            index=0,
            heading="Huge section",
            start_line=1,
            end_line=200,
            char_count=CHALLENGE_CHUNK_CHAR_CAP + 1,
        )
        state = PipelineState(
            paper_id="P9999R0",
            paper_md=paper_md,
            chunk_map=[oversized_chunk],
        )
        finding = FindingOutput(
            id=1,
            title="Finding one",
            lens="Design",
            severity="minor",
            quote="q1",
            line=100,
            explanation="explanation one",
        )
        ctx = StepContext()

        message = _build_cross_exam_user_message([finding], state, ctx)

        assert "## Source chunks" not in message
        assert f"exceeds {CHALLENGE_CHUNK_CHAR_CAP} chars" in message
        assert "Content for line 100" in message
        assert "Content for line 1\n" not in message


class TestP4160R0ChallengeRegression:
    """Regression tests for P4160R0: old Challenge duplicated chunk text per finding."""

    def test_legacy_batch_duplicates_under_cap_chunk_per_finding(self):
        paper_lines = [f"Content for line {i}" for i in range(1, 201)]
        paper_lines[99] = P4160R0_REGRESSION_MARKER
        paper_md = "\n".join(paper_lines)
        shared_chunk = ChunkEntry(
            index=0,
            heading="Shared section",
            start_line=1,
            end_line=200,
            char_count=len(paper_md),
        )
        state = PipelineState(
            paper_id="P4160R0",
            paper_md=paper_md,
            chunk_map=[shared_chunk],
        )
        findings = [
            FindingOutput(
                id=i,
                title=f"Finding {i}",
                lens="Design",
                severity="minor",
                quote="q",
                line=100,
                explanation="x" * 200,
            )
            for i in range(1, CHALLENGE_MAX_BATCH + 1)
        ]
        ctx = StepContext()

        legacy_message = _legacy_cross_exam_user_message(findings, state, ctx)
        fixed_message = _build_cross_exam_user_message(findings, state, ctx)

        assert shared_chunk.char_count <= CHALLENGE_CHUNK_CHAR_CAP
        assert legacy_message.count(P4160R0_REGRESSION_MARKER) == CHALLENGE_MAX_BATCH
        assert fixed_message.count(P4160R0_REGRESSION_MARKER) == 1

    def test_legacy_monolithic_batch_exceeds_runpod_limit(self):
        paper_md = "x" * 113_781
        giant_chunk = ChunkEntry(
            index=0,
            heading="Whole paper",
            start_line=1,
            end_line=1,
            char_count=len(paper_md),
        )
        state = PipelineState(
            paper_id="P4160R0",
            paper_md=paper_md,
            chunk_map=[giant_chunk],
        )
        findings = [
            FindingOutput(
                id=i,
                title=f"Finding {i}",
                lens="Design",
                severity="minor",
                quote="q",
                line=1,
                explanation="x" * 200,
            )
            for i in range(1, CHALLENGE_MAX_BATCH + 1)
        ]
        ctx = StepContext()

        legacy_message = _legacy_cross_exam_user_message(findings, state, ctx)

        assert len(legacy_message) > RUNPOD_BODY_LIMIT_CHARS

    def test_chunked_paper_batch_stays_under_runpod_limit(
        self, large_issue_list_paper, survey_max_chars,
    ):
        sections = chunk_paper(large_issue_list_paper, max_chars=survey_max_chars)
        chunk_map = [
            ChunkEntry(
                index=i,
                heading=s.heading,
                start_line=s.start_line,
                end_line=s.end_line,
                char_count=s.char_count,
            )
            for i, s in enumerate(sections)
        ]
        state = PipelineState(
            paper_id="P4160R0",
            paper_md=large_issue_list_paper,
            chunk_map=chunk_map,
        )
        largest = max(chunk_map, key=lambda c: c.char_count)
        findings = [
            FindingOutput(
                id=i,
                title=f"Finding {i}",
                lens="Design",
                severity="minor",
                quote="q",
                line=largest.start_line + 1,
                explanation="x" * 200,
            )
            for i in range(1, CHALLENGE_MAX_BATCH + 1)
        ]
        ctx = StepContext()

        message = _build_cross_exam_user_message(findings, state, ctx)

        assert len(sections) > 1
        assert len(message) < RUNPOD_BODY_LIMIT_CHARS

    def test_old_style_per_finding_chunk_embed_absent(self):
        paper_md = _make_paper(100)
        chunk = ChunkEntry(
            index=0,
            heading="Section",
            start_line=1,
            end_line=100,
            char_count=500,
        )
        state = PipelineState(
            paper_id="P4160R0",
            paper_md=paper_md,
            chunk_map=[chunk],
        )
        findings = [
            FindingOutput(
                id=i,
                title=f"Finding {i}",
                lens="Design",
                severity="minor",
                quote="q",
                line=10 * i,
                explanation="explanation",
            )
            for i in range(1, 4)
        ]
        ctx = StepContext()

        message = _build_cross_exam_user_message(findings, state, ctx)

        assert "**Containing chunk: Section (lines 1-100):**" not in message
        assert "see Source chunks above" in message
        assert message.count("Content for line 50") == 1
