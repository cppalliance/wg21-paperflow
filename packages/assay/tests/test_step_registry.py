#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

"""Tests for _build_hooks / assay.md sync."""

from assay.pipeline import _PERSIST_BY_SLUG, _build_hooks, _step_slug
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
