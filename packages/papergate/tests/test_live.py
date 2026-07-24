#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Live end-to-end PaperGate run against a real model.

Marked ``network`` so it is deselected by default (the repo runs
``-m 'not network'``). It prefers a reachable tools-capable RunPod endpoint
from SERVICES.toml; if none is up it falls back to the Anthropic
OpenAI-compatible endpoint (the same code path a vLLM endpoint exercises), and
skips if neither is available.
"""

from __future__ import annotations

import os

import httpx
import pytest
from promptforge.inference import OpenAIToolModel
from promptforge.services import load_services

from papergate.run import build_runtime

_PAPER = """Document: P9999R0
Title: std::ring_buffer, a fixed-capacity circular buffer
Author: A. Committee Member

## 1 Motivation
Circular buffers are ubiquitous in audio, networking, and embedded systems.
Every large codebase reimplements one. We propose std::ring_buffer, a
fixed-capacity FIFO with O(1) push and pop and contiguous storage.

## 2 Why standardize
Boost.CircularBuffer has existed since 2007 and is widely used. folly has one.
A standard vocabulary type lets independent libraries exchange buffers without
conversion. Three audio libraries each define incompatible ring types; bridging
them copies element by element.

## 3 Design
template<class T, size_t N> class ring_buffer. push_back overwrites the oldest
element when full.

## 4 Implementation
A reference implementation exists with tests and benchmarks showing parity with
Boost.CircularBuffer.
"""


def _reachable(base_url: str, api_key: str) -> bool:
    try:
        response = httpx.get(
            base_url.rstrip("/") + "/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=8.0,
        )
        return response.status_code < 400
    except httpx.HTTPError:
        return False


def _live_model() -> OpenAIToolModel | None:
    for service in load_services().values():
        if service.tools_capable and service.base_url and _reachable(service.base_url, service.api_key):
            return OpenAIToolModel(
                model=service.model, base_url=service.base_url,
                api_key=service.api_key, max_tokens=8000,
            )
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return OpenAIToolModel(
            model="claude-opus-4-6", base_url="https://api.anthropic.com/v1/",
            api_key=key, max_tokens=8000, top_p=None, seed=None, timeout=120.0,
        )
    return None


@pytest.mark.network
def test_papergate_gates_a_real_paper(tmp_path) -> None:
    model = _live_model()
    if model is None:
        pytest.skip("no reachable tools-capable endpoint and no ANTHROPIC_API_KEY")

    paper = tmp_path / "p9999r0.md"
    paper.write_text(_PAPER, encoding="utf-8")

    runtime = build_runtime(model=model)
    result = runtime.execute(params={"paper": str(paper), "output_path": "p9999r0-papergate.md"})

    assert result.ok
    report = result.vfs.read("p9999r0-papergate.md")
    assert "## Missing From The Paper" in report
    assert result.store.get("metadata")["classification"] in {"library", "language", "both"}
    # PaperGate reports whether the case is made; it never decides belonging.
    assert "hire" not in result.presented.lower()
