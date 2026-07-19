#
# Copyright (c) 2026 Greg Kaleka (greg@gregkaleka.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

"""Per-chunk steps must not let the model author ``chunk_index``.

Extract, Decide, and Analyze hand the model a slim ``*Items`` schema with no
``chunk_index`` (a leading bare integer destabilizes JSON generation on thinking
backends - see ``ClassifyGap``). The orchestrator assigns the authoritative
``chunk.index`` from the per-chunk call context. These tests lock both the schema
shape and the injection, including under out-of-order completion.
"""

from __future__ import annotations

import asyncio

from pipeline import StepContext

from assay.models import (
    ChunkAnalyzeItems,
    ChunkDecideItems,
    ChunkDecideOutput,
    ChunkEntry,
    ChunkExtractItems,
    ChunkExtractOutput,
    ClaimDecision,
    FindingOutput,
    ItemOutput,
    PipelineState,
)
from assay.pipeline import _custom_analyze, _custom_decide, _custom_extract


# -- Schema shape ------------------------------------------------------------


def test_slim_types_omit_chunk_index():
    for slim in (ChunkExtractItems, ChunkDecideItems, ChunkAnalyzeItems):
        assert "chunk_index" not in slim.model_fields, slim.__name__


def test_internal_wrappers_keep_chunk_index():
    assert "chunk_index" in ChunkExtractOutput.model_fields
    assert "chunk_index" in ChunkDecideOutput.model_fields


# -- Injection under out-of-order completion ---------------------------------


class _Step:
    def __init__(self, name: str) -> None:
        self.name = name  # hooks read spec.step.name to look up the prompt
        self.model = "fast"
        self.max_output_tokens = 16384
        self.thinking_budget = 4096
        self.concurrency = 8


class _Spec:
    def __init__(self, name: str) -> None:
        self.step = _Step(name)


def _ctx(agent) -> StepContext:
    return StepContext(agents={"fast": agent}, default_concurrency=8)


def _two_chunk_state() -> PipelineState:
    """Chunks in insertion order 0 then 2 (a non-contiguous index on purpose)."""
    state = PipelineState()
    state.paper_id = "P9999R0"
    state.paper_md = "\n".join(f"line {i}" for i in range(40))
    state.chunk_map = [
        ChunkEntry(index=0, heading="Intro", start_line=1, end_line=10, char_count=50),
        ChunkEntry(index=2, heading="Body", start_line=20, end_line=30, char_count=50),
    ]
    return state


class _ExtractAgent:
    """Returns one claim per chunk; lower chunk index completes last."""

    def __init__(self) -> None:
        self.max_tokens = 8192

    async def run(self, *, output_type, label, **kw):
        assert output_type is ChunkExtractItems
        ci = int(label.rsplit("-", 1)[1])
        await asyncio.sleep((10 - ci) / 1000)
        return ChunkExtractItems(items=[
            ItemOutput(type="claim", quote=f"claim in chunk {ci}", line=ci),
        ])


def test_extract_injects_authoritative_chunk_index():
    state = _two_chunk_state()
    asyncio.run(_custom_extract(state, _ctx(_ExtractAgent()), _Spec("4. Extract")))

    # raw_extractions follow chunk_map order, each pinned to its chunk's index.
    assert [e.chunk_index for e in state.raw_extractions] == [0, 2]
    assert [e.items[0].quote for e in state.raw_extractions] == [
        "claim in chunk 0", "claim in chunk 2",
    ]


class _DecideAgent:
    """Returns a supported decision per chunk (keeps cross-chunk pass a no-op)."""

    def __init__(self) -> None:
        self.max_tokens = 8192

    async def run(self, *, output_type, label, **kw):
        assert output_type is ChunkDecideItems
        ci = int(label.rsplit("-", 1)[1])
        await asyncio.sleep((10 - ci) / 1000)
        return ChunkDecideItems(decisions=[
            ClaimDecision(claim_id=0, supported=True, reason="ok"),
        ])


def test_decide_injects_authoritative_chunk_index():
    state = _two_chunk_state()
    # Decide reads claims from raw_extractions; give each chunk one claim.
    state.raw_extractions = [
        ChunkExtractOutput(chunk_index=0, items=[
            ItemOutput(type="claim", quote="intro claim", line=3),
        ]),
        ChunkExtractOutput(chunk_index=2, items=[
            ItemOutput(type="claim", quote="body claim", line=22),
        ]),
    ]
    asyncio.run(_custom_decide(state, _ctx(_DecideAgent()), _Spec("5. Decide")))

    assert [d.chunk_index for d in state.raw_decisions] == [0, 2]


class _AnalyzeAgent:
    """Returns one finding per chunk via the slim Analyze schema."""

    def __init__(self) -> None:
        self.max_tokens = 8192

    async def run(self, *, output_type, label, **kw):
        assert output_type is ChunkAnalyzeItems
        ci = int(label.rsplit("-", 1)[1])
        return ChunkAnalyzeItems(findings=[
            FindingOutput(
                title=f"finding {ci}", lens="Design", severity="minor",
                quote=f"q{ci}", line=ci, explanation="because",
            ),
        ], strengths=[])


def test_analyze_runs_with_slim_schema():
    state = _two_chunk_state()
    asyncio.run(_custom_analyze(state, _ctx(_AnalyzeAgent()), _Spec("12. Analyze")))

    # One finding per chunk, each assigned a unique pipeline id.
    assert len(state.findings) == 2
    assert sorted(f.title for f in state.findings) == ["finding 0", "finding 2"]
    assert len({f.id for f in state.findings}) == 2
