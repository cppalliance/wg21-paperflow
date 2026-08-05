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

import pytest

from pipeline import PipelinePrompt

_ASSAY_SRC = Path(__file__).resolve().parents[1] / "src" / "assay"

# Scans all of src/assay/. assay.md is the authority for LLM-facing step text;
# this guard blocks reintroducing Python fallback prompt constants (the old
# _DEFAULT_*_PROMPT naming pattern). It does not enforce the wider "no prompt
# strings in Python" rule from assay CLAUDE.md across arbitrary literals.
# The regex matches any occurrence of that name shape, including comments.
_DEFAULT_PROMPT_CONSTANT_RE = re.compile(r"_DEFAULT_\w+_PROMPT")

_ASSAY_STEP_NAMES = tuple(
    s.name for s in PipelinePrompt.load("assay", "assay.md").steps
)


@pytest.mark.parametrize("step_name", _ASSAY_STEP_NAMES)
def test_step_section_is_non_empty(step_name: str):
    prompt = PipelinePrompt.load("assay", "assay.md")
    assert prompt.step_section(step_name).strip(), f"empty step body for {step_name}"


def test_assay_src_has_no_default_prompt_constants():
    for path in sorted(_ASSAY_SRC.rglob("*.py")):
        if path.name.startswith("._"):
            continue
        source = path.read_text(encoding="utf-8")
        match = _DEFAULT_PROMPT_CONSTANT_RE.search(source)
        assert match is None, (
            f"{path.relative_to(_ASSAY_SRC.parent)}: found {match.group(0)}"
        )
