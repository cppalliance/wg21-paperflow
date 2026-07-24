#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the inference client (scripted and OpenAI-compatible)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from promptforge.inference import (
    AssistantTurn,
    OpenAIToolModel,
    ScriptedModel,
    StreamingOpenAIToolModel,
    tool_call,
    turn,
)


def test_scripted_model_returns_turns_in_order() -> None:
    model = ScriptedModel([
        turn(tool_call("read_input", path="p.md")),
        turn(tool_call("done")),
    ])
    first = model.complete([{"role": "user", "content": "go"}])
    assert first.tool_calls[0].name == "read_input"
    assert first.tool_calls[0].arguments == {"path": "p.md"}
    second = model.complete([])
    assert second.tool_calls[0].name == "done"


def test_scripted_model_records_calls() -> None:
    model = ScriptedModel([turn(text="hi")])
    model.complete([{"role": "user", "content": "x"}], tools=[{"a": 1}])
    assert model.calls[0]["tools"] == [{"a": 1}]


def test_scripted_model_raises_when_exhausted() -> None:
    model = ScriptedModel([turn(tool_call("done"))])
    model.complete([])
    with pytest.raises(RuntimeError):
        model.complete([])


def _make_response(content, tool_calls):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])


def _raw_tool_call(name, arguments, id="call_1"):
    return SimpleNamespace(id=id, function=SimpleNamespace(name=name, arguments=arguments))


class _FakeCompletions:
    def __init__(self, response):
        self._response = response
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response


class _FakeClient:
    def __init__(self, response):
        self.chat = SimpleNamespace(completions=_FakeCompletions(response))


def test_openai_model_builds_request_and_parses_tool_calls() -> None:
    response = _make_response(
        "<think>reasoning</think>ok",
        [_raw_tool_call("set_metadata", '{"document": "P1", "tier": "large"}')],
    )
    client = _FakeClient(response)
    model = OpenAIToolModel(model="deepseek-v4-pro", client=client, max_tokens=2048)

    result = model.complete(
        [{"role": "user", "content": "go"}],
        tools=[{"type": "function", "function": {"name": "set_metadata"}}],
    )

    sent = client.chat.completions.last_kwargs
    assert sent["model"] == "deepseek-v4-pro"
    assert sent["stream"] is False
    assert sent["temperature"] == 0.0
    assert sent["seed"] == 0
    assert sent["max_tokens"] == 2048
    assert sent["tool_choice"] == "auto"

    # <think> stripped from text; tool-call arguments parsed to a dict.
    assert result.text == "ok"
    assert result.tool_calls[0].name == "set_metadata"
    assert result.tool_calls[0].arguments == {"document": "P1", "tier": "large"}
    assert result.tool_calls[0].id == "call_1"


def test_openai_model_omits_top_p_and_seed_when_none() -> None:
    # Some compat endpoints reject top_p/seed; None must omit them.
    client = _FakeClient(_make_response("hi", None))
    model = OpenAIToolModel(model="m", client=client, top_p=None, seed=None)
    model.complete([{"role": "user", "content": "x"}])
    sent = client.chat.completions.last_kwargs
    assert "top_p" not in sent
    assert "seed" not in sent


def test_openai_model_omits_tools_when_none() -> None:
    client = _FakeClient(_make_response("hi", None))
    model = OpenAIToolModel(model="m", client=client)
    result = model.complete([{"role": "user", "content": "x"}])
    assert "tools" not in client.chat.completions.last_kwargs
    assert "tool_choice" not in client.chat.completions.last_kwargs
    assert result.text == "hi"
    assert result.tool_calls == []


def test_openai_model_tolerates_malformed_tool_args() -> None:
    response = _make_response("", [_raw_tool_call("f", "{not json")])
    model = OpenAIToolModel(model="m", client=_FakeClient(response))
    result = model.complete([])
    # Malformed arguments degrade to an empty dict rather than crashing.
    assert result.tool_calls[0].arguments == {}


def test_tool_call_passes_id_argument_through() -> None:
    # An argument literally named "id" must not be shadowed by the call id.
    call = tool_call("file_verdict", id=7)
    assert call.arguments == {"id": 7}
    assert call.id == "call_file_verdict"
    call2 = tool_call("f", call_id="abc", value=1)
    assert call2.id == "abc"
    assert call2.arguments == {"value": 1}


def test_assistant_turn_defaults() -> None:
    t = AssistantTurn()
    assert t.text == ""
    assert t.tool_calls == []


# -- streaming model --------------------------------------------------------

def _stream_chunk(content=None, tool_calls=None):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def _tc_delta(index, id=None, name=None, args=None):
    return SimpleNamespace(index=index, id=id, function=SimpleNamespace(name=name, arguments=args))


class _FakeStreamCompletions:
    def __init__(self, chunks):
        self._chunks = chunks
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return iter(self._chunks)


class _FakeStreamClient:
    def __init__(self, chunks):
        self.chat = SimpleNamespace(completions=_FakeStreamCompletions(chunks))


def test_streaming_text_streams_to_callback() -> None:
    chunks = [_stream_chunk(content="Hello "), _stream_chunk(content="there.")]
    client = _FakeStreamClient(chunks)
    model = StreamingOpenAIToolModel(model="m", client=client)
    received: list[str] = []
    result = model.complete([{"role": "user", "content": "hi"}], on_text=received.append)
    assert "".join(received) == "Hello there."
    assert result.text == "Hello there."
    assert client.chat.completions.last_kwargs["stream"] is True


def test_streaming_suppresses_think_from_callback() -> None:
    # The think span is split across chunk boundaries.
    chunks = [
        _stream_chunk(content="<thi"),
        _stream_chunk(content="nk>planning</think>Real "),
        _stream_chunk(content="answer."),
    ]
    model = StreamingOpenAIToolModel(model="m", client=_FakeStreamClient(chunks))
    received: list[str] = []
    result = model.complete([], on_text=received.append)
    spoken = "".join(received)
    assert spoken == "Real answer."
    assert "planning" not in spoken
    assert result.text == "Real answer."


def test_streaming_accumulates_tool_calls() -> None:
    chunks = [
        _stream_chunk(content="ok"),
        _stream_chunk(tool_calls=[_tc_delta(0, id="call_1", name="rate_answer", args='{"qual')]),
        _stream_chunk(tool_calls=[_tc_delta(0, args='ity": "rich"}')]),
    ]
    client = _FakeStreamClient(chunks)
    model = StreamingOpenAIToolModel(model="m", client=client)
    result = model.complete([], tools=[{"type": "function", "function": {"name": "rate_answer"}}])
    assert result.text == "ok"
    assert result.tool_calls[0].name == "rate_answer"
    assert result.tool_calls[0].arguments == {"quality": "rich"}
    assert result.tool_calls[0].id == "call_1"
    assert client.chat.completions.last_kwargs["tool_choice"] == "auto"


def test_streaming_tolerates_malformed_tool_args() -> None:
    chunks = [_stream_chunk(tool_calls=[_tc_delta(0, name="f", args="{bad")])]
    model = StreamingOpenAIToolModel(model="m", client=_FakeStreamClient(chunks))
    result = model.complete([])
    assert result.tool_calls[0].arguments == {}
