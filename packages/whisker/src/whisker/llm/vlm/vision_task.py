#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Whisker-local multimodal LLM dispatch for the dormant VLM lane.

The pipeline framework is text-only by design and, per project decision,
stays unmodified by whisker: everything vision-specific lives HERE, inside
the whisker package. This module is the whisker-local counterpart of
``pipeline.run_task`` for image-bearing calls.

Documented D1 exception: D1 routes every LLM call through the pipeline
framework, which cannot carry image parts without being changed. Package
boundary (whisker-only changes) takes precedence, so this module performs
the OpenAI-compatible multimodal call itself while preserving the
framework's discipline: serial dispatch (D11), pinned sampling (D5
equivalent: temperature 0, top_p 1, seed 0), schema-in-prompt structured
output (D6), finite retry budget (D10), full debug logging.

The VLM lane is dormant (no vision endpoint deployed). This module keeps
it functional for the day a vision pod exists, without any footprint in
the pipeline package. No production CLI or service configuration invokes
it, so it must not be reported as production coverage.

Library-pure: returns data, never persists.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, TypeVar

import openai
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

_T = TypeVar("_T", bound=BaseModel)

__all__ = [
    "VisionAgent",
    "VisionTaskError",
    "run_vision_task",
]

_VISION_TASK_CONCURRENCY = 1
"""Serial dispatch (D11): one in-flight vision request at a time,
mirroring ``pipeline.tasks._TASK_CONCURRENCY``."""

_vision_task_semaphore = asyncio.Semaphore(_VISION_TASK_CONCURRENCY)

MAX_VISION_ATTEMPTS = 2
"""Finite retry budget (D10): one retry after a transient API error or
a malformed JSON completion, then fail loudly."""

_TRANSIENT_RETRY_BASE_DELAY_SECONDS = 2
"""Base for the exponential backoff delay after a transient API error."""


class VisionTaskError(Exception):
    """Raised when a vision call cannot produce valid structured output."""


@dataclass
class VisionAgent:
    """Connection settings for a vision-capable vLLM endpoint.

    Whisker-local stand-in for ``pipeline.AgentBackend``: the pipeline
    registry has no vision backend type, so the dormant VLM lane carries
    its own agent configuration.
    """

    base_url: str
    api_key: str
    model: str
    max_tokens: int = 16384
    service_name: str = ""


def _schema_instruction(output_type: type[BaseModel]) -> str:
    """Schema-in-prompt structured output instruction (D6)."""
    schema = json.dumps(output_type.model_json_schema(), indent=2)
    return (
        "Respond with a single JSON object matching this JSON schema. "
        "No prose before or after the JSON.\n\n" + schema
    )


def _extract_json(content: str) -> str:
    """Cut the first top-level JSON object out of a completion."""
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise VisionTaskError(f"No JSON object in completion: {content[:200]!r}")
    return content[start:end + 1]


async def run_vision_task(
    agent: VisionAgent,
    system_prompt: str,
    user_message: str,
    output_type: type[_T],
    *,
    user_media: list[bytes] | None = None,
    label: str = "run_vision_task",
    debug_log: list[str] | None = None,
) -> _T:
    """Run one multimodal call and return validated structured output.

    Images are sent as base64 PNG data URIs in OpenAI content parts.
    Serial by design (module-level semaphore); sampling pinned to
    temperature 0 / top_p 1 / seed 0.

    Raises VisionTaskError on exhausted retries or invalid output.
    """
    client = AsyncOpenAI(base_url=agent.base_url, api_key=agent.api_key)
    full_system = f"{system_prompt}\n\n{_schema_instruction(output_type)}"

    content_parts: list[dict[str, Any]] = []
    for img_bytes in user_media or []:
        b64 = base64.b64encode(img_bytes).decode("ascii")
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        })
    content_parts.append({"type": "text", "text": user_message})

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": full_system},
        {"role": "user", "content": content_parts},
    ]

    if debug_log is not None:
        digests = ", ".join(
            f"sha256={hashlib.sha256(b).hexdigest()[:16]} ({len(b)} bytes)"
            for b in user_media or []
        )
        debug_log.append(
            f"<!-- call: {label} | model={agent.model} | "
            f"max_tokens={agent.max_tokens} | "
            f"images={len(user_media or [])} -->\n"
            f"<!-- system -->\n{full_system.rstrip()}\n"
            + (f"<!-- images: {digests} -->\n" if digests else "")
            + f"<!-- user -->\n{user_message.rstrip()}\n"
        )

    async with _vision_task_semaphore:
        for attempt in range(MAX_VISION_ATTEMPTS):
            try:
                response = await client.chat.completions.create(
                    model=agent.model,
                    messages=messages,
                    temperature=0.0,
                    top_p=1.0,
                    seed=0,
                    max_tokens=agent.max_tokens,
                )
                content = response.choices[0].message.content or ""
            except (openai.NotFoundError, openai.APIConnectionError,
                    openai.InternalServerError, openai.APITimeoutError) as exc:
                if attempt < MAX_VISION_ATTEMPTS - 1:
                    delay = _TRANSIENT_RETRY_BASE_DELAY_SECONDS ** (attempt + 1)
                    logger.warning(
                        "Transient API error (attempt %d/%d), retrying in %ds: %s",
                        attempt + 1, MAX_VISION_ATTEMPTS, delay, exc,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise VisionTaskError(
                    f"{label}: API error after {attempt + 1} attempt(s): {exc}"
                ) from exc

            if debug_log is not None:
                debug_log.append(f"<!-- {label} -->\n<!-- raw-json -->\n{content}\n")

            try:
                result = output_type.model_validate(
                    json.loads(_extract_json(content))
                )
            except (VisionTaskError, json.JSONDecodeError, ValidationError) as exc:
                if attempt < MAX_VISION_ATTEMPTS - 1:
                    logger.warning(
                        "Vision JSON parse failed (attempt %d), retrying: %s",
                        attempt + 1, exc,
                    )
                    continue
                raise VisionTaskError(
                    f"{label}: JSON completion failed after {attempt + 1} "
                    f"attempt(s): {exc}\nContent: {content[:500]!r}"
                ) from exc

            if debug_log is not None:
                debug_log.append(
                    f"<!-- output -->\n"
                    f"{json.dumps(result.model_dump(), indent=2, ensure_ascii=False)}\n"
                )
            return result

    raise AssertionError(
        f"unreachable: loop must return or raise "
        f"(MAX_VISION_ATTEMPTS={MAX_VISION_ATTEMPTS})"
    )
