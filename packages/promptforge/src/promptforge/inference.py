#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""The inference client.

A ``Model`` takes a message list plus scoped tool schemas and returns one
assistant turn: free-text reasoning and zero or more tool calls. The runtime
owns the loop; the model owns one turn. Calls are non-streaming, because
streaming tool calls are the least reliable path on open-weight models.

Two implementations:

- ``ScriptedModel`` replays a fixed sequence of turns, for deterministic
  offline tests (the whole runtime is testable without a live endpoint).
- ``OpenAIToolModel`` talks to any OpenAI-compatible endpoint (vLLM/SGLang on
  RunPod), pinned to temperature 0 and seed 0 for determinism.

The endpoints themselves come from the shared ``SERVICES.toml`` inventory that
the ``pipeline`` package already defines; see ``services.py``.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


@dataclass
class ToolCall:
    """One tool call requested by the model."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    id: str = ""


@dataclass
class AssistantTurn:
    """One assistant response: reasoning text plus requested tool calls."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class Model(Protocol):
    """A single-turn completion interface."""

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AssistantTurn:
        ...


def tool_call(name: str, id: str = "", **arguments: Any) -> ToolCall:
    """Build a ToolCall, for scripting tests and builtins."""
    return ToolCall(name=name, arguments=dict(arguments), id=id or f"call_{name}")


def turn(*calls: ToolCall, text: str = "") -> AssistantTurn:
    """Build an AssistantTurn from tool calls (and optional text)."""
    return AssistantTurn(text=text, tool_calls=list(calls))


class ScriptedModel:
    """A model that replays a fixed queue of turns."""

    def __init__(self, turns: list[AssistantTurn]) -> None:
        self._turns = list(turns)
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AssistantTurn:
        self.calls.append({"messages": messages, "tools": tools})
        if not self._turns:
            raise RuntimeError("ScriptedModel exhausted: no more turns queued")
        return self._turns.pop(0)


class OpenAIToolModel:
    """A model backed by an OpenAI-compatible chat completions endpoint."""

    def __init__(
        self,
        *,
        model: str,
        base_url: str = "",
        api_key: str = "",
        client: Any = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        timeout: float = 120.0,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        if client is None:
            from openai import OpenAI

            client = OpenAI(
                base_url=base_url or None,
                api_key=api_key or "none",
                timeout=timeout,
            )
        self._client = client

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AssistantTurn:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "top_p": 1.0,
            "seed": 0,
            "max_tokens": self._max_tokens,
            "stream": False,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        response = self._client.chat.completions.create(**kwargs)
        return _parse_response(response)


def _parse_response(response: Any) -> AssistantTurn:
    """Turn an OpenAI-shaped chat completion into an AssistantTurn."""
    message = response.choices[0].message
    text = _THINK_RE.sub("", message.content or "").strip()

    calls: list[ToolCall] = []
    for raw in getattr(message, "tool_calls", None) or []:
        arguments = raw.function.arguments or "{}"
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            logger.warning("tool-call arguments were not valid JSON: %r", arguments)
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        calls.append(ToolCall(
            name=raw.function.name,
            arguments=parsed,
            id=getattr(raw, "id", "") or "",
        ))

    return AssistantTurn(text=text, tool_calls=calls)
