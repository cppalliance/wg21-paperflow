#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

"""Tests for assay.md classifier binding."""

from __future__ import annotations

import dataclasses

import pytest

from pipeline import PipelinePrompt, StepContext
from pipeline.classifier_backends import NliCrossEncoderBackend

from assay.pipeline import (
    _classifiers_for_routing,
    _parse_classifier_binding,
)


class _MinimalNli(NliCrossEncoderBackend):
    def __init__(self, model_id: str) -> None:
        self.model_id = model_id

    def classify(self, texts, candidate_labels, *, multi_label=True):
        return []


def test_assay_md_declares_at_least_one_classifier_slot():
    # Slot names are opaque to the framework (see markdown.bullet_map /
    # pipeline.resolve_classifiers); assay.md just needs to bind at
    # least one, under whatever key it chooses.
    prompt = PipelinePrompt.load("assay", "assay.md")
    binding = _parse_classifier_binding(prompt)
    assert binding
    assert all(binding.values())


def test_parse_classifier_binding_raises_when_section_missing():
    prompt = PipelinePrompt.load("assay", "assay.md")
    sections = {k: v for k, v in prompt.sections.items() if k != "Classifiers"}
    prompt = dataclasses.replace(prompt, sections=sections)
    with pytest.raises(ValueError, match="assay.md"):
        _parse_classifier_binding(prompt)


def test_classifiers_for_routing_deduplicates_slot_dict_values():
    a = _MinimalNli("a")
    b = _MinimalNli("b")
    ctx = StepContext(classifiers={"routing_nli": a, "routing_tagger": b})
    resolved = _classifiers_for_routing(ctx)
    assert resolved == (a, b)


def test_classifiers_for_routing_deduplicates_shared_backend():
    a = _MinimalNli("a")
    ctx = StepContext(classifiers={"slot1": a, "slot2": a})
    resolved = _classifiers_for_routing(ctx)
    assert resolved == (a,)


def test_classifiers_for_routing_empty():
    assert _classifiers_for_routing(StepContext()) is None
