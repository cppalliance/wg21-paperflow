#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""The Lua configuration layer.

One mechanism replaces a metadata DSL: each section carries at most one Lua
fence, and that code selects the model, scopes the tools, checks preconditions,
injects context, and defines the postcondition. Deterministic logic lives here
rather than in the prompt, so it is offloaded from the model.

Five host objects are exposed to the sandbox:

- ``state``  - a read-only snapshot of accumulated state (a Lua table).
- ``store``  - a live count/exists/get view of the store.
- ``tools``  - the scoped tool-set builder (add/remove).
- ``params`` - the section's arguments (a Lua table).
- ``context``- injects assembled text into the model's initial prompt.

Plus ``model(slot)``, ``sections`` (block/children), and ``fanout(...)``.

Sandbox posture (defense-in-depth, per the design; the pipeline author is
trusted): ``register_eval=False`` and ``register_builtins=False`` keep Python
out of Lua, an ``attribute_filter`` blocks access to underscore attributes on
host objects (so ``obj.__class__`` escapes are closed), and the dangerous Lua
standard libraries (``os``, ``io``, ``package``, ``debug``, loaders) are niled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import lupa
from lupa import LuaError, LuaRuntime

from promptforge.errors import PostconditionError, PreconditionError

# Close the Lua-native file/exec/loader surface. Attribute access is separately
# guarded by the filter; this removes the standard-library entry points.
_SANDBOX_PRELUDE = (
    "os=nil; io=nil; dofile=nil; loadfile=nil; load=nil; loadstring=nil; "
    "require=nil; package=nil; debug=nil; collectgarbage=nil"
)


@dataclass
class FanoutRequest:
    """A recorded lua-driven fan-out, executed later by the runtime."""

    tasks: list[Any]
    shared: dict[str, Any] = field(default_factory=dict)
    opts: dict[str, Any] = field(default_factory=dict)


class LuaConfig:
    """The result of running a section's Lua block."""

    def __init__(
        self,
        runtime: LuaRuntime | None,
        model_slot: str | None,
        tools: list[str],
        injected: list[str],
        fanout: FanoutRequest | None,
    ) -> None:
        self._runtime = runtime
        self.model_slot = model_slot
        self.tools = tools
        self.injected = injected
        self.fanout = fanout

    def run_check(self) -> None:
        """Run the section's ``check()`` postcondition, if it defined one."""
        if self._runtime is None:
            return
        check = self._runtime.globals().check
        if check is None:
            return
        try:
            check()
        except LuaError as exc:
            raise PostconditionError(_clean_lua_message(exc)) from exc


def configure_section(
    lua_code: str | None,
    *,
    store: Any,
    params: dict[str, Any],
    document: Any = None,
) -> LuaConfig:
    """Run a section's Lua block and return its resolved configuration.

    Preconditions (top-level ``assert`` calls) run during execution; a failure
    raises :class:`PreconditionError`. The ``check()`` function, if defined, is
    kept for the runtime to invoke after ``done()``.
    """
    if not lua_code or not lua_code.strip():
        return LuaConfig(None, None, [], [], None)

    scope = _ToolScope()
    context = _ContextBuilder()
    recorder = _Recorder()
    runtime = _make_runtime()

    def to_lua(value: Any) -> Any:
        return _to_lua(runtime, value)

    globals_ = runtime.globals()
    globals_.state = runtime.table_from(store.serialize(), recursive=True)
    globals_.params = runtime.table_from(dict(params), recursive=True)
    globals_.store = _StoreView(store, to_lua)
    globals_.tools = scope
    globals_.context = context
    globals_.sections = _SectionsView(document, to_lua)
    globals_.model = recorder.set_model
    globals_.fanout = recorder.set_fanout

    try:
        runtime.execute(lua_code)
    except LuaError as exc:
        raise PreconditionError(_clean_lua_message(exc)) from exc

    return LuaConfig(runtime, recorder.model_slot, scope.names, context.parts, recorder.fanout)


def _make_runtime() -> LuaRuntime:
    runtime = LuaRuntime(
        register_eval=False,
        register_builtins=False,
        attribute_filter=_attribute_filter,
    )
    runtime.execute(_SANDBOX_PRELUDE)
    return runtime


def _attribute_filter(obj: Any, name: str, is_setting: bool) -> str:
    """Block access to underscore attributes on host objects from Lua."""
    if isinstance(name, str) and name.startswith("_"):
        raise AttributeError(f"access to '{name}' is not allowed")
    return name


class _ToolScope:
    """Records the scoped tool set. Order-preserving, deduplicated."""

    def __init__(self) -> None:
        self.names: list[str] = []

    def add(self, *names: str) -> None:
        for name in names:
            if name not in self.names:
                self.names.append(name)

    def remove(self, *names: str) -> None:
        for name in names:
            if name in self.names:
                self.names.remove(name)


class _ContextBuilder:
    """Collects text to inject into the model's initial prompt."""

    def __init__(self) -> None:
        self.parts: list[str] = []

    def inject(self, text: Any) -> None:
        self.parts.append(str(text))


class _Recorder:
    """Captures ``model(slot)`` and ``fanout(...)`` calls."""

    def __init__(self) -> None:
        self.model_slot: str | None = None
        self.fanout: FanoutRequest | None = None

    def set_model(self, slot: Any) -> None:
        self.model_slot = str(slot)

    def set_fanout(self, tasks: Any, shared: Any = None, opts: Any = None) -> None:
        self.fanout = FanoutRequest(
            tasks=_from_lua(tasks),
            shared=_from_lua(shared) or {},
            opts=_from_lua(opts) or {},
        )


class _StoreView:
    """A live, read-oriented view of the store for Lua predicates."""

    def __init__(self, store: Any, to_lua: Callable[[Any], Any]) -> None:
        self._store = store
        self._to_lua = to_lua

    def count(self, collection: str, where: Any = None) -> int:
        return self._store.count(collection, _from_lua(where))

    def get(self, key: str, default: Any = None) -> Any:
        return self._to_lua(self._store.get(key, default))

    def exists(self, key: str) -> bool:
        return self._store.exists(key)


class _SectionsView:
    """Exposes verbatim blocks and H3 children to Lua."""

    def __init__(self, document: Any, to_lua: Callable[[Any], Any]) -> None:
        self._document = document
        self._to_lua = to_lua

    def block(self, tag: str) -> str:
        if self._document is None:
            raise LuaError("sections.block called but no document is bound")
        return self._document.block(tag)

    def children(self, ref: str) -> Any:
        if self._document is None:
            raise LuaError("sections.children called but no document is bound")
        return self._to_lua([child.name for child in self._document.children(ref)])


def _to_lua(runtime: LuaRuntime, value: Any) -> Any:
    """Convert a Python container to a Lua table so Lua can index/iterate it."""
    if isinstance(value, (dict, list)):
        return runtime.table_from(value, recursive=True)
    return value


def _from_lua(value: Any) -> Any:
    """Convert a Lua table to a Python list or dict, recursively."""
    if lupa.lua_type(value) != "table":
        return value
    items = list(value.items())
    keys = [k for k, _ in items]
    is_sequence = bool(keys) and all(isinstance(k, int) for k in keys) and sorted(keys) == list(
        range(1, len(keys) + 1)
    )
    if is_sequence:
        return [_from_lua(v) for _, v in sorted(items, key=lambda kv: kv[0])]
    return {k: _from_lua(v) for k, v in items}


def _clean_lua_message(exc: LuaError) -> str:
    """Strip Lua's ``[string "<python>"]:N:`` prefix from an error message."""
    message = str(exc)
    marker = ']:'
    if message.startswith('[string') and marker in message:
        tail = message.split(marker, 1)[1]
        # Drop the leading line number and colon (e.g. "1: ").
        return tail.split(":", 1)[1].strip() if ":" in tail else tail.strip()
    return message
