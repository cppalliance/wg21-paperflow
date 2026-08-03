#
# Copyright (c) 2026 Leo Chen (leo.chen0412@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for assay.md prompt authority and pipeline prompt-string guards."""

from __future__ import annotations

import re
from pathlib import Path

from pipeline import PipelinePrompt

_PIPELINE_PY = (
    Path(__file__).resolve().parents[1] / "src" / "assay" / "pipeline.py"
)


def test_verify_step_section_is_non_empty():
    prompt = PipelinePrompt.load("assay", "assay.md")
    assert prompt.step_section("9. Verify").strip()


def test_pipeline_has_no_default_prompt_constants():
    """Enforcement: assay LLM prompts live in assay.md, not Python fallbacks."""
    source = _PIPELINE_PY.read_text(encoding="utf-8")
    assert not re.search(r"_DEFAULT_\w+_PROMPT", source)
