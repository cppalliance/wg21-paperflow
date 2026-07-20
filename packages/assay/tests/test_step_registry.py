#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

"""Tests for _build_hooks / assay.md sync."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from assay.models import CollectedItem, CollectedItems, PipelineState
from assay.pipeline import (
    _PERSIST_BY_SLUG,
    _build_hooks,
    _persist_concessions,
    _persist_step,
    _step_slug,
)
from paperstore.testing import store  # noqa: F401
from pipeline import PipelinePrompt, build_pipeline


def test_hooks_match_assay_md():
    prompt = PipelinePrompt.load("assay", "assay.md")
    hooks = _build_hooks()

    build_pipeline(prompt, hooks)


def test_persist_slugs_match_assay_md():
    prompt = PipelinePrompt.load("assay", "assay.md")
    md_slugs = {_step_slug(s.name) for s in prompt.steps}

    unknown = set(_PERSIST_BY_SLUG) - md_slugs
    assert not unknown, f"persist slugs not in assay.md: {sorted(unknown)}"

    for slug in _PERSIST_BY_SLUG:
        matches = [s.name for s in prompt.steps if _step_slug(s.name) == slug]
        assert len(matches) == 1, f"slug {slug!r} matches {matches}"


def test_persist_step_dispatches_collect():
    spec = SimpleNamespace(step=SimpleNamespace(name="7. Collect"))
    state = PipelineState(items=CollectedItems())
    ctx = SimpleNamespace(backend=MagicMock(), pid="p0001r0")

    _persist_step(spec, state, ctx)

    ctx.backend.store_assay_claims.assert_called_once()


def test_persist_concessions_uses_collect_ids(store):
    concessions = [
        CollectedItem(
            type="concession",
            id=9,
            line=7,
            quote="minor API churn",
            section="Intro",
        ),
        CollectedItem(
            type="concession",
            id=10,
            line=12,
            quote="edge case",
            section="Design",
        ),
    ]

    _persist_concessions(store, "P1000R0", concessions)

    rows = store.get_assay_concessions("P1000R0")
    assert [r.uid for r in rows] == [9, 10]
    assert [r.loc_line for r in rows] == [7, 12]
    assert [r.quote for r in rows] == ["minor API churn", "edge case"]
