#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""The runtime: control flow over sections.

This ties the primitives together. It starts at ``## Main`` and follows the
model's control-flow tools:

- ``done()`` ends the current flow (and the run, if at the top level).
- ``goto(section)`` clears the context and continues at another section in the
  same store: the program counter moves, the registers are wiped, the store
  persists.
- ``task(section, params)`` runs a section as a subagent with its own isolated
  store, merges that store back on completion, and returns it as JSON so the
  caller can read what came back. The virtual filesystem is shared, as a
  blackboard for inter-subagent handoff.
- lua ``fanout(...)`` runs each listed section as a subagent in turn (serial,
  per determinism) and merges each store back.

Domain tools write to the *current* section's store through a mutable
``ExecContext`` whose ``store`` field the runtime swaps as it descends into and
returns from subagents; execution is synchronous, so there is no interleaving.

Failure handling follows the design's retry contract: a section that raises
:class:`IncompleteError` (no ``done()``) or :class:`PostconditionError` (failed
``check()``) is retried once, with the store rolled back to a pre-attempt
snapshot so the retry starts clean. Preconditions failing is a hard stop.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from promptforge.errors import (
    DepthLimitError,
    IncompleteError,
    PostconditionError,
    PromptForgeError,
    TaskLimitError,
)
from promptforge.execute import SectionResult, ToolResult, run_section
from promptforge.lua import FanoutRequest, configure_section
from promptforge.parser import Document
from promptforge.store import MemStore
from promptforge.tools import ToolRegistry
from promptforge.vfs import MemVFS

logger = logging.getLogger(__name__)

_ENTRY = "## Main"
_MAX_HOPS = 50

# Hand-written schemas for the control tools. Their dispatch is special (they
# change control flow), so they are not generated from Python signatures.
_CONTROL_SCHEMAS: dict[str, dict[str, Any]] = {
    "done": {
        "type": "function",
        "function": {
            "name": "done",
            "description": "Signal that this step's work is complete. Call exactly once, at the end.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    "goto": {
        "type": "function",
        "function": {
            "name": "goto",
            "description": (
                "Clear the context and continue at another section. A one-way "
                "transition, not a call; nothing after it runs in this section."
            ),
            "parameters": {
                "type": "object",
                "properties": {"section": {"type": "string"}},
                "required": ["section"],
            },
        },
    },
    "task": {
        "type": "function",
        "function": {
            "name": "task",
            "description": (
                "Run another section as an isolated subagent and get its result "
                "back. Use to delegate work and then continue here."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {"type": "string"},
                    "params": {"type": "object"},
                },
                "required": ["section"],
            },
        },
    },
}


@dataclass
class ExecContext:
    """Ambient handles for domain tools. ``store`` is swapped per section."""

    store: MemStore
    vfs: MemVFS
    presented: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    """The outcome of a whole pipeline run."""

    ok: bool
    store: MemStore
    vfs: MemVFS
    presented: str = ""


class Runtime:
    """Executes a pipeline document over a store and a virtual filesystem."""

    def __init__(
        self,
        document: Document | str | Path,
        *,
        model: Any = None,
        resolver: Any = None,
        registry: ToolRegistry | None = None,
        store: MemStore | None = None,
        vfs: MemVFS | None = None,
        max_depth: int = 5,
        max_tasks: int = 64,
        max_turns: int = 16,
        retries: int = 1,
        ask_fn: Any = None,
    ) -> None:
        self.document = _as_document(document)
        self._single_model = model
        self._resolver = resolver
        self.registry = registry or ToolRegistry()
        self.store = store or MemStore()
        self.vfs = vfs or MemVFS()
        self.max_depth = max_depth
        self.max_tasks = max_tasks
        self.max_turns = max_turns
        self.retries = retries
        self.ctx = ExecContext(store=self.store, vfs=self.vfs)
        if ask_fn is not None:
            self.ctx.extras["ask"] = ask_fn
        self._task_count = 0
        # Every pipeline gets the generic library tools; scoping still decides
        # which sections actually see them.
        from promptforge.builtins import register_builtins

        register_builtins(self)

    # -- public entry points ------------------------------------------------

    def execute(self, params: dict[str, Any] | None = None) -> RunResult:
        """Run the pipeline from ``## Main`` to completion."""
        self._begin_run()
        self._run_flow(_ENTRY, params or {}, self.store, depth=0)
        return RunResult(
            ok=True,
            store=self.store,
            vfs=self.vfs,
            presented=self.ctx.presented or "",
        )

    def execute_section(
        self, ref: str, params: dict[str, Any] | None = None
    ) -> SectionResult:
        """Run a single section in isolation against the runtime store."""
        self._begin_run()
        return self._run_section_with_retry(ref, params or {}, self.store, depth=0)

    # -- control flow -------------------------------------------------------

    def _begin_run(self) -> None:
        self._task_count = 0
        self.ctx.store = self.store
        self.ctx.presented = None

    def _run_flow(
        self, start: str, params: dict[str, Any], store: MemStore, depth: int
    ) -> SectionResult:
        """Run sections following ``goto`` transitions until one finishes."""
        current = start
        current_params = params
        for _ in range(_MAX_HOPS):
            result = self._run_section_with_retry(current, current_params, store, depth)
            if result.status != "goto":
                return result
            current = result.transition or ""
            current_params = {}
        raise PromptForgeError(f"goto exceeded {_MAX_HOPS} hops (loop?)")

    def _run_section_with_retry(
        self, ref: str, params: dict[str, Any], store: MemStore, depth: int
    ) -> SectionResult:
        section = self.document.section(ref)
        snapshot = store.serialize()
        last_error: PromptForgeError | None = None

        for attempt in range(1, self.retries + 2):
            # Preconditions run here; a failure is a hard stop, never retried.
            config = configure_section(
                section.lua, store=store, params=params, document=self.document
            )
            self.ctx.store = store
            try:
                if config.fanout is not None:
                    self._run_fanout(config.fanout, store, depth)
                    config.run_check()
                    return SectionResult("done", attempts=attempt)

                result = run_section(
                    prose=section.prose,
                    model=self._model_for(config.model_slot),
                    tool_schemas=self._schemas_for(config.tools),
                    dispatch=self._make_dispatch(store, depth),
                    injected=self._inject_params(config.injected, params),
                    run_check=config.run_check,
                    max_turns=self.max_turns,
                )
                result.attempts = attempt
                return result
            except (IncompleteError, PostconditionError) as exc:
                last_error = exc
                logger.warning(
                    "section '%s' attempt %d/%d failed: %s",
                    ref, attempt, self.retries + 1, exc,
                )
                store.reset(snapshot)

        assert last_error is not None
        raise last_error

    def _run_fanout(
        self, request: FanoutRequest, store: MemStore, depth: int
    ) -> None:
        """Run each fan-out task as a subagent, merging each store back."""
        for task in request.tasks:
            if not isinstance(task, dict):
                continue
            section = task.get("section")
            if not section:
                continue
            task_params = dict(request.shared)
            task_params.update(task.get("params") or {})
            self._spawn(section, task_params, store, depth)

    def _spawn(
        self, section: str, params: dict[str, Any], parent_store: MemStore, depth: int
    ) -> MemStore:
        """Run a section as an isolated subagent and merge its store back."""
        if depth + 1 > self.max_depth:
            raise DepthLimitError(
                f"max nesting depth {self.max_depth} exceeded at '{section}'"
            )
        self._task_count += 1
        if self._task_count > self.max_tasks:
            raise TaskLimitError(f"max task count {self.max_tasks} exceeded")

        child_store = MemStore()
        previous_store = self.ctx.store
        try:
            self._run_flow(section, params, child_store, depth + 1)
        finally:
            self.ctx.store = previous_store
        parent_store.merge(child_store)
        return child_store

    def _make_dispatch(self, store: MemStore, depth: int):
        """Build the per-section tool dispatcher (control tools plus registry)."""

        def dispatch(name: str, args: dict[str, Any]) -> ToolResult:
            if name == "done":
                return ToolResult("done", done=True)
            if name == "goto":
                target = str(args.get("section", "")).strip()
                return ToolResult(f"transitioning to {target}", transition=target)
            if name == "task":
                child = self._spawn(
                    str(args.get("section", "")).strip(),
                    args.get("params") if isinstance(args.get("params"), dict) else {},
                    store,
                    depth,
                )
                return ToolResult(json.dumps(child.serialize(), ensure_ascii=False))
            return ToolResult(self.registry.dispatch(name, args))

        return dispatch

    # -- helpers ------------------------------------------------------------

    def _model_for(self, slot: str | None) -> Any:
        if self._resolver is not None:
            return self._resolver.model(slot or "default")
        if self._single_model is not None:
            return self._single_model
        raise PromptForgeError("no model or resolver configured on the runtime")

    def _schemas_for(self, tools: list[str]) -> list[dict[str, Any]]:
        schemas: list[dict[str, Any]] = []
        for name in tools:
            if name in _CONTROL_SCHEMAS:
                schemas.append(_CONTROL_SCHEMAS[name])
            elif self.registry.has(name):
                schemas.append(self.registry.schema(name))
            else:
                logger.warning("scoped tool '%s' has no schema; skipping", name)
        return schemas

    @staticmethod
    def _inject_params(
        injected: list[str], params: dict[str, Any]
    ) -> list[str]:
        """Surface the section's parameters so the model can see them."""
        if not params:
            return injected
        head = "Parameters (JSON):\n" + json.dumps(params, ensure_ascii=False)
        return [head, *injected]


def _as_document(document: Document | str | Path) -> Document:
    if isinstance(document, Document):
        return document
    text = str(document)
    path = Path(document) if not isinstance(document, Path) else document
    # A single-line string that names an existing file is treated as a path;
    # anything with newlines is treated as inline markdown.
    if "\n" not in text and path.exists():
        return Document.from_path(path)
    return Document(text)
