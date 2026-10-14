#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Whisker-local dispatch for PDF-judge LLM calls.

``pipeline.run_task`` holds a global ``asyncio.Semaphore(1)`` that
serializes every call across the whole process. That gate exists for
dissect (D11: at most one in-flight request). For the advisory
tapetum-llm lane it is the wrong bound: a 118-paper PDF-judge batch
measured 678 s wall time because every judge call queued behind that
single slot while the CLI's ``--concurrency 16`` sat idle.

This module is the per-package concurrency mechanism that D11 sanctions
("per-context or per-call concurrency parameter; never a global flip"),
implemented on the whisker side so the pipeline package stays untouched.
It matches the text lane's dispatch model: ``adjudicate_paper`` calls
``run_agent`` directly with no global gate, and the CLI's paper-level
semaphore is the actual in-flight bound. The judge lane gets the same
contract via ``run_judge_task``.

Documented D1 deviation: the call goes through ``AgentBackend.run``
(never a raw ``pydantic_ai.Agent``, never ``chat.completions.create``),
so every model-level discipline is preserved: sampling pins (D2),
structured output (D6), retry budgets (D10), BPE cleanup, truncation
retry. Only the dispatch gate differs from ``run_task``. The variance
budget for concurrent in-flight requests is documented in
``llm.md`` (advisory lane, never gates).

Library-pure: returns data, never persists.
"""

from __future__ import annotations

import logging
from typing import TypeVar

from pipeline import AgentBackend
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

__all__ = ["run_judge_task"]


async def run_judge_task(
    agent: AgentBackend,
    system_prompt: str,
    user_message: str,
    output_type: type[T],
    *,
    label: str = "run_judge_task",
    debug_log: list[str] | None = None,
    max_tokens: int | None = None,
) -> T:
    """Run one judge call and return validated structured output.

    No global semaphore: the caller bounds in-flight requests (the
    tapetum-llm CLI's paper-level ``--concurrency`` semaphore). Each
    paper issues at most one judge call, so paper-level bounding is
    call-level bounding.

    ``max_tokens``, when given, overrides the agent's default output
    token budget for this call (verdict-first bifurcation: a pass-path
    micro-schema needs far fewer decode tokens than the full defect
    schema). ``None`` keeps the agent's construction-time default.
    """
    return await agent.run(
        system_prompt,
        user_message,
        output_type,
        max_tokens=max_tokens,
        label=label,
        debug_log=debug_log,
    )
