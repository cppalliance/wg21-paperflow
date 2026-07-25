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

Three implementations:

- ``ScriptedModel`` replays a fixed sequence of turns, for deterministic
  offline tests (the whole runtime is testable without a live endpoint).
- ``OpenAIToolModel`` talks to any OpenAI-compatible endpoint (vLLM/SGLang on
  RunPod), pinned to temperature 0 and seed 0 for determinism. Non-streaming,
  because streaming tool calls are the least reliable path for pipeline work.
- ``StreamingOpenAIToolModel`` streams the assistant text to an ``on_text``
  callback (for a voice front-end to speak sentence by sentence) while still
  accumulating tool-call deltas into a complete ``AssistantTurn`` for dispatch.
  ``<think>`` spans are suppressed from the streamed text so reasoning is never
  spoken.

The endpoints themselves come from the shared ``SERVICES.toml`` inventory that
the ``pipeline`` package already defines; see ``services.py``.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

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


def tool_call(name: str, call_id: str = "", **arguments: Any) -> ToolCall:
    """Build a ToolCall, for scripting tests and builtins.

    The call identifier is ``call_id`` (not ``id``) so a tool argument literally
    named ``id`` is passed through as an argument rather than shadowed.
    """
    return ToolCall(name=name, arguments=dict(arguments), id=call_id or f"call_{name}")


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
        *,
        on_text: Callable[[str], None] | None = None,
    ) -> AssistantTurn:
        self.calls.append({"messages": messages, "tools": tools})
        if not self._turns:
            raise RuntimeError("ScriptedModel exhausted: no more turns queued")
        result = self._turns.pop(0)
        # Simulate a single-chunk stream so streaming callers are testable offline.
        if on_text is not None and result.text:
            on_text(result.text)
        return result


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
        top_p: float | None = 1.0,
        seed: int | None = 0,
        timeout: float = 120.0,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        # top_p and seed pin determinism on vLLM, but some OpenAI-compatible
        # servers reject them (Anthropic's compat layer forbids top_p alongside
        # temperature). Pass None to omit either for such an endpoint.
        self._top_p = top_p
        self._seed = seed
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
            "max_tokens": self._max_tokens,
            "stream": False,
        }
        if self._top_p is not None:
            kwargs["top_p"] = self._top_p
        if self._seed is not None:
            kwargs["seed"] = self._seed
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


class _ThinkStreamFilter:
    """Suppress ``<think>...</think>`` spans from a streamed text feed.

    Holds back a short tail that could be the start of a delimiter, so a tag
    split across chunk boundaries is still caught before any of it is emitted.
    """

    _OPEN = "<think>"
    _CLOSE = "</think>"

    def __init__(self) -> None:
        self._buf = ""
        self._in_think = False

    def feed(self, chunk: str) -> str:
        """Add a chunk; return the text safe to emit now (outside think spans)."""
        self._buf += chunk
        out: list[str] = []
        while True:
            if self._in_think:
                end = self._buf.find(self._CLOSE)
                if end < 0:
                    self._buf = self._holdback_tail(self._buf, self._CLOSE)
                    break
                self._buf = self._buf[end + len(self._CLOSE):]
                self._in_think = False
                continue
            start = self._buf.find(self._OPEN)
            if start < 0:
                keep = self._holdback_tail(self._buf, self._OPEN)
                if keep:
                    out.append(self._buf[: len(self._buf) - len(keep)])
                    self._buf = keep
                else:
                    out.append(self._buf)
                    self._buf = ""
                break
            out.append(self._buf[:start])
            self._buf = self._buf[start + len(self._OPEN):]
            self._in_think = True
        return "".join(out)

    def flush(self) -> str:
        """Emit any trailing text (nothing if still inside a think span)."""
        if self._in_think:
            self._buf = ""
            return ""
        out, self._buf = self._buf, ""
        return out

    @staticmethod
    def _holdback_tail(s: str, tag: str) -> str:
        """Return the longest suffix of ``s`` that is a proper prefix of ``tag``."""
        for k in range(min(len(s), len(tag) - 1), 0, -1):
            if tag.startswith(s[-k:]):
                return s[-k:]
        return ""


class StreamingOpenAIToolModel:
    """Streaming variant of :class:`OpenAIToolModel`.

    ``complete`` streams the assistant's visible text to the optional
    ``on_text`` callback as it arrives, while accumulating tool-call deltas, and
    returns the complete :class:`AssistantTurn` when the stream ends so the
    caller dispatches tool calls exactly as with the non-streaming model.
    """

    def __init__(
        self,
        *,
        model: str,
        base_url: str = "",
        api_key: str = "",
        client: Any = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        top_p: float | None = 1.0,
        seed: int | None = 0,
        timeout: float = 120.0,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._top_p = top_p
        self._seed = seed
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
        *,
        on_text: Callable[[str], None] | None = None,
    ) -> AssistantTurn:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "stream": True,
        }
        if self._top_p is not None:
            kwargs["top_p"] = self._top_p
        if self._seed is not None:
            kwargs["seed"] = self._seed
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        stream = self._client.chat.completions.create(**kwargs)
        think = _ThinkStreamFilter()
        text_parts: list[str] = []
        # Accumulate tool-call deltas by their stream index.
        slots: dict[int, dict[str, str]] = {}

        for chunk in stream:
            choices = getattr(chunk, "choices", None)
            if not choices:
                continue
            delta = choices[0].delta
            if delta is None:
                continue
            content = getattr(delta, "content", None)
            if content:
                visible = think.feed(content)
                if visible:
                    text_parts.append(visible)
                    if on_text is not None:
                        on_text(visible)
            for call in getattr(delta, "tool_calls", None) or []:
                slot = slots.setdefault(call.index, {"id": "", "name": "", "args": ""})
                if getattr(call, "id", None):
                    slot["id"] = call.id
                fn = getattr(call, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        slot["name"] = fn.name
                    if getattr(fn, "arguments", None):
                        slot["args"] += fn.arguments

        tail = think.flush()
        if tail:
            text_parts.append(tail)
            if on_text is not None:
                on_text(tail)

        calls: list[ToolCall] = []
        for index in sorted(slots):
            slot = slots[index]
            if not slot["name"]:
                continue
            try:
                parsed = json.loads(slot["args"] or "{}")
            except json.JSONDecodeError:
                logger.warning("streamed tool-call arguments not valid JSON: %r", slot["args"])
                parsed = {}
            if not isinstance(parsed, dict):
                parsed = {}
            calls.append(ToolCall(name=slot["name"], arguments=parsed, id=slot["id"]))

        return AssistantTurn(text="".join(text_parts).strip(), tool_calls=calls)
