#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tool registry, schema generation, and dispatch.

A tool is a flat-signature Python function. Its JSON schema is generated from
its signature and type hints (no pydantic): the reliability win on mid-size
models comes from flat calls with typed, enum-closed arguments, which this
produces directly from ``str``/``int``/``float``/``bool``/``Literal``/``list``.

``dispatch`` is total: it returns the tool's string result, or an ``ERROR: ...``
string on any failure (unknown tool, missing argument, bad enum, coercion
failure, or an exception in the tool). That string goes straight back to the
model, which can then self-correct on the next turn - the flat-call analog of a
structured-output validation failure, but re-asked in isolation.

Control tools (``done``/``goto``/``task``/``fanout``) are not registered here;
they change control flow and are owned by the execute and runtime layers.
"""

from __future__ import annotations

import inspect
import logging
import types
import typing
from typing import Any, Callable, Literal, get_args, get_origin, get_type_hints

logger = logging.getLogger(__name__)

_JSON_PRIMITIVES: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def build_schema(
    fn: Callable[..., Any],
    name: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Build an OpenAI-style function tool schema from a callable."""
    name = name or fn.__name__
    description = description if description is not None else (inspect.getdoc(fn) or "").strip()
    hints = get_type_hints(fn)
    properties: dict[str, Any] = {}
    required: list[str] = []

    for pname, param in inspect.signature(fn).parameters.items():
        if pname == "self":
            continue
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        annotation = hints.get(pname, str)
        prop, optional = _type_to_schema(annotation)
        properties[pname] = prop
        if param.default is inspect.Parameter.empty and not optional:
            required.append(pname)

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


def _type_to_schema(annotation: Any) -> tuple[dict[str, Any], bool]:
    """Map a type annotation to ``(json_schema, is_optional)``."""
    origin = get_origin(annotation)

    if origin is typing.Union or origin is types.UnionType:
        args = get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        has_none = len(non_none) != len(args)
        # Model the first non-None arm; unions of distinct real types are
        # discouraged by the tool-parameter design, so this stays simple.
        sub, _ = _type_to_schema(non_none[0])
        return sub, has_none

    if origin is Literal:
        values = list(get_args(annotation))
        return {"type": _enum_json_type(values), "enum": values}, False

    if origin in (list, typing.List):  # noqa: UP006 - typing.List for older hints
        item_args = get_args(annotation)
        item_schema, _ = _type_to_schema(item_args[0] if item_args else str)
        return {"type": "array", "items": item_schema}, False

    if annotation in _JSON_PRIMITIVES:
        return {"type": _JSON_PRIMITIVES[annotation]}, False

    raise TypeError(
        f"unsupported tool parameter type {annotation!r}; use str/int/float/"
        f"bool/Literal/list or Optional of those"
    )


def _enum_json_type(values: list[Any]) -> str:
    """Infer the JSON type of a Literal from its members (bool before int)."""
    if all(isinstance(v, bool) for v in values):
        return "boolean"
    if all(isinstance(v, int) for v in values):
        return "integer"
    if all(isinstance(v, str) for v in values):
        return "string"
    return "string"


class ToolRegistry:
    """A name-to-callable registry that also owns each tool's schema."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}
        self._schemas: dict[str, dict[str, Any]] = {}

    def register(
        self,
        fn: Callable[..., Any] | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Callable[..., Any]:
        """Register a tool. Usable directly or as a decorator."""

        def _register(f: Callable[..., Any]) -> Callable[..., Any]:
            key = name or f.__name__
            self._tools[key] = f
            self._schemas[key] = build_schema(f, key, description)
            return f

        return _register(fn) if fn is not None else _register

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        return list(self._tools)

    def schema(self, name: str) -> dict[str, Any]:
        return self._schemas[name]

    def schemas(self, names: list[str]) -> list[dict[str, Any]]:
        """Return schemas for a scoped subset, preserving the requested order."""
        return [self._schemas[n] for n in names if n in self._schemas]

    def dispatch(self, name: str, args: dict[str, Any] | None) -> str:
        """Validate arguments, call the tool, and return a result string."""
        if name not in self._tools:
            return f"ERROR: unknown tool '{name}'"
        params = self._schemas[name]["function"]["parameters"]
        try:
            kwargs = _validate(params, args or {})
        except ValueError as exc:
            return f"ERROR: {exc}"
        try:
            result = self._tools[name](**kwargs)
        except Exception as exc:  # returned to the model, which retries
            logger.exception("tool '%s' raised", name)
            return f"ERROR: {name} raised: {exc}"
        return result if isinstance(result, str) else str(result)


def _validate(params: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    """Check required args and coerce each to its declared type."""
    properties = params["properties"]
    missing = [r for r in params.get("required", []) if r not in args]
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(missing)}")
    coerced: dict[str, Any] = {}
    for key, value in args.items():
        if key not in properties:  # drop unknown extras; models add them
            continue
        coerced[key] = _coerce(value, properties[key], key)
    return coerced


def _coerce(value: Any, schema: dict[str, Any], key: str) -> Any:
    """Coerce a model-supplied value to the schema type, tolerantly."""
    if "enum" in schema:
        if value in schema["enum"]:
            return value
        if schema.get("type") == "string" and str(value) in schema["enum"]:
            return str(value)
        raise ValueError(f"'{key}'={value!r} is not one of {schema['enum']}")

    kind = schema.get("type")
    if kind == "string":
        return value if isinstance(value, str) else str(value)
    if kind == "integer":
        return _to_int(value, key)
    if kind == "number":
        return _to_float(value, key)
    if kind == "boolean":
        return _to_bool(value, key)
    if kind == "array":
        if not isinstance(value, list):
            raise ValueError(f"'{key}' expected a list, got {type(value).__name__}")
        item_schema = schema.get("items", {"type": "string"})
        return [_coerce(v, item_schema, key) for v in value]
    return value


def _to_int(value: Any, key: str) -> int:
    # bool is an int subclass; reject it so True does not silently become 1.
    if isinstance(value, bool):
        raise ValueError(f"'{key}' expected an integer, got a boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            pass
    raise ValueError(f"'{key}' expected an integer, got {value!r}")


def _to_float(value: Any, key: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"'{key}' expected a number, got a boolean")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            pass
    raise ValueError(f"'{key}' expected a number, got {value!r}")


def _to_bool(value: Any, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    raise ValueError(f"'{key}' expected a boolean, got {value!r}")
