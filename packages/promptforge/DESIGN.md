# PromptForge development log

Broad-strokes architectural record, appended at milestones. The full
specification is `promptforge.md`; this file captures the decisions that shaped
the implementation and the reasons behind them.

## M1 - Core runtime (parser through control flow)

The runtime is built from small, independently tested leaf modules that map
onto the design's four primitives plus their supporting stores and clients:

- `parser.py` (Parse), `lua.py` (Configure), `execute.py` (Execute), `tools.py`
  (Dispatch), with `store.py`, `vfs.py`, `inference.py`, `services.py`, and
  `runtime.py` (control flow) around them.

Decisions that shaped the whole:

- **Synchronous runtime.** The whole engine is sync, and fan-out runs sections
  serially. This matches the pipeline package's determinism rule D3 (serial,
  `Semaphore(1)` dispatch), removes all asyncio complexity from the loop, and
  makes every path deterministically testable. Parallel fan-out is a future
  optimization, not a correctness requirement.

- **No pydantic.** State is a plain dict behind `MemStore`; everything else is
  dataclasses. Tool JSON schemas are generated from a function's signature and
  type hints via `inspect`/`typing` (`str`/`int`/`float`/`bool`/`Literal`/
  `list`/`Optional`). The reliability win the design wants - flat calls with
  typed, enum-closed arguments - falls straight out of the signature.

- **Own the tool-call loop; borrow the endpoints.** The `pipeline` package
  reaches models through a pydantic structured-output contract that returns a
  validated object, which cannot express a `done()`-terminated tool loop. So
  PromptForge runs its own non-streaming OpenAI-compatible loop and reaches the
  same RunPod models by reading the shared `SERVICES.toml` inventory. This
  keeps "use pipeline for the LLM callouts" (same services, same transport)
  without dragging in pydantic or the wrong loop shape.

- **Control flow lives in the runtime, not the loop.** `execute.run_section` is
  a generic loop that takes an opaque `dispatch(name, args) -> ToolResult`; a
  tool is a control tool precisely because its result sets `done` or
  `transition`. The runtime supplies `done`/`goto`/`task`; `goto` wipes context
  and moves the program counter while the store persists, and `task` runs an
  isolated subagent whose store is merged back (the virtual filesystem is
  shared, as a blackboard).

- **Ambient store swap for subagent isolation.** Domain tools write to the
  current section's store through a mutable `ExecContext` whose `store` field
  the runtime swaps as it descends into and returns from subagents. Because the
  runtime is synchronous, there is no interleaving to corrupt this.

- **Three-layer failure detection with rollback retry.** Missing `done()`
  raises `IncompleteError`; a failed Lua `check()` raises `PostconditionError`;
  both are retried once, with the store rolled back to a pre-attempt snapshot so
  the retry starts clean. Failed preconditions are a hard stop, never retried.

- **Lua sandbox is defense-in-depth for a trusted author.** `register_eval` and
  `register_builtins` are off, an attribute filter blocks underscore access on
  host objects, and the dangerous Lua standard libraries are niled. Adequate
  because the pipeline author is us.

## M2 - Generic library tools and end-to-end runs

The runtime auto-registers a small set of generic tools every pipeline can
scope in: virtual-file I/O (`create_file`/`append_file`/`read_file`/
`delete_file`), `present` (records the operator-facing result on the run), and
`ask_user` (routes to a runtime `ask_fn`, or reports an unattended run). Scoping
still decides which sections see them, so a global registry does not widen any
section's tool set.

With these in place the whole stack runs unmodified against a scripted model.
The design's Example 1 (a two-section classifier connected by `goto`) and
Example 3 (fan-out of one extraction subagent per chunk, each with its own
isolated store merged back) both pass end to end, which validates parse ->
configure -> execute -> dispatch and the goto/task/fanout control flow together,
deterministically and offline.

*2026-07-23 - Claude Opus 4.8 (Cursor agent)*
