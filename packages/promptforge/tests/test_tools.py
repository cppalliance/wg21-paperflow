#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for tool schema generation and dispatch."""

from __future__ import annotations

from typing import Literal

import pytest

from promptforge.tools import ToolRegistry, build_schema


def sample_set(type: str, count: int, ratio: float, flag: bool) -> str:
    """File a sample record."""
    return f"{type} {count} {ratio} {flag}"


def sample_enum(kind: Literal["library", "language", "both"]) -> str:
    "Classify."
    return kind


def test_build_schema_basic_types() -> None:
    schema = build_schema(sample_set)
    fn = schema["function"]
    assert fn["name"] == "sample_set"
    assert fn["description"] == "File a sample record."
    props = fn["parameters"]["properties"]
    assert props["type"] == {"type": "string"}
    assert props["count"] == {"type": "integer"}
    assert props["ratio"] == {"type": "number"}
    assert props["flag"] == {"type": "boolean"}
    assert set(fn["parameters"]["required"]) == {"type", "count", "ratio", "flag"}


def test_build_schema_literal_enum() -> None:
    props = build_schema(sample_enum)["function"]["parameters"]["properties"]
    assert props["kind"]["type"] == "string"
    assert props["kind"]["enum"] == ["library", "language", "both"]


def test_build_schema_optional_and_default_not_required() -> None:
    def fn(a: str, b: int = 3, c: str | None = None) -> str:
        "x"
        return a

    params = build_schema(fn)["function"]["parameters"]
    assert params["required"] == ["a"]
    assert params["properties"]["c"] == {"type": "string"}


def test_build_schema_list_type() -> None:
    def fn(tags: list[str]) -> str:
        "x"
        return ""

    props = build_schema(fn)["function"]["parameters"]["properties"]
    assert props["tags"] == {"type": "array", "items": {"type": "string"}}


def test_build_schema_unsupported_type_raises() -> None:
    def fn(x: dict) -> str:
        "x"
        return ""

    with pytest.raises(TypeError):
        build_schema(fn)


def test_dispatch_success_and_side_effect() -> None:
    calls: list[dict] = []

    def add_claim(quote: str, line: int) -> str:
        "File a claim."
        calls.append({"quote": quote, "line": line})
        return f"filed at line {line}"

    reg = ToolRegistry()
    reg.register(add_claim)
    out = reg.dispatch("add_claim", {"quote": "hi", "line": 5})
    assert out == "filed at line 5"
    assert calls == [{"quote": "hi", "line": 5}]


def test_dispatch_coerces_model_quirks() -> None:
    def fn(count: int, ratio: float, flag: bool) -> str:
        "x"
        return f"{count!r} {ratio!r} {flag!r}"

    reg = ToolRegistry()
    reg.register(fn)
    # Model sends stringy / floaty values.
    out = reg.dispatch("fn", {"count": "3", "ratio": "0.5", "flag": "true"})
    assert out == "3 0.5 True"


def test_dispatch_missing_required_is_error_string() -> None:
    reg = ToolRegistry()
    reg.register(sample_enum)
    out = reg.dispatch("sample_enum", {})
    assert out.startswith("ERROR:")
    assert "kind" in out


def test_dispatch_bad_enum_is_error_string() -> None:
    reg = ToolRegistry()
    reg.register(sample_enum)
    out = reg.dispatch("sample_enum", {"kind": "nonsense"})
    assert out.startswith("ERROR:")


def test_dispatch_unknown_tool_is_error_string() -> None:
    assert ToolRegistry().dispatch("nope", {}).startswith("ERROR:")


def test_dispatch_drops_unknown_extra_args() -> None:
    def fn(a: str) -> str:
        "x"
        return a

    reg = ToolRegistry()
    reg.register(fn)
    assert reg.dispatch("fn", {"a": "ok", "surprise": 1}) == "ok"


def test_dispatch_tool_exception_is_error_string() -> None:
    def boom(a: str) -> str:
        "x"
        raise RuntimeError("kaboom")

    reg = ToolRegistry()
    reg.register(boom)
    out = reg.dispatch("boom", {"a": "x"})
    assert out.startswith("ERROR:")
    assert "kaboom" in out


def test_schemas_scoping_returns_subset() -> None:
    reg = ToolRegistry()
    reg.register(sample_set)
    reg.register(sample_enum)
    scoped = reg.schemas(["sample_enum"])
    assert len(scoped) == 1
    assert scoped[0]["function"]["name"] == "sample_enum"


def test_register_as_decorator() -> None:
    reg = ToolRegistry()

    @reg.register
    def greet(name: str) -> str:
        "Greet."
        return f"hi {name}"

    assert reg.has("greet")
    assert reg.dispatch("greet", {"name": "x"}) == "hi x"
