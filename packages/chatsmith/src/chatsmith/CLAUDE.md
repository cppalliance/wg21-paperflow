# chatsmith - Agent Rules

## What this is

A reusable, pack-driven **knowledge-capture voice interviewer**. chatsmith runs a
spoken interview (speech-to-text -> normalize -> LLM -> text-to-speech) behind a
talking avatar, draws out how a person thinks, and stores a durable transcript.
Everything domain-specific (persona, glossary, themes, branding) lives in a
swappable **pack**, so the same code serves WG21, Boost, or any field with no
code change. LLM calls route through wg21-paperflow's `pipeline`; speech is not
an LLM call and lives in the reusable `vox` package.

## Incremental landing (read this first)

chatsmith lands in stages. **This PR contains the foundation + domain-pack layer
only.** Later PRs add the session store, the LLM turn pipeline, the Flask
server + CLI, and finally the browser GUI. Keep the "arriving later" list current
as each layer lands, and grow the `__init__.py` re-exports with it.

Present now:

- `models.py` - the sole schema authority for LLM output: **frozen** Pydantic
  models (`NormalizeOutput`, `TurnReply`). Every future `agent.run` declares
  `output_type=<one of these>`, never `output_type=str` (matches paperflow D6).
- `interview/models.py` - the session data model. `InterviewSession` + `Turn` +
  a light resumable `InterviewState`. Every type round-trips through plain dicts
  (`to_dict`/`from_dict`, `SCHEMA_VERSION`) so any store (JSON, SQLite, a Django
  JSONField) shares the same bytes. `transcript_markdown()` renders pure Q/A and
  deliberately keeps a trailing unanswered question (interviews end on a Q).
- `interview/state_machine.py` - an advisory, tool-free coarse phase model
  (greeting/elicit/walk/close) + close-intent detection. Advisory only.
- `pack/` + `packs/wg21/` - the domain-pack layer. `pack/base.py` defines the
  `DomainPack` Protocol, the `FileSystemPack` loader, and `resolve()`;
  `pack/prompt.py` parses the pack's `prompt.md` into sections + `## Services`.
  `packs/wg21/` is the bundled WG21 (Mentographist / "Nova") pack.
- `identity.py` - `Owner` (opaque principal, or `None` = local single-user) and
  `owner_matches`, the data-layer authorization check.
- `metrics.py` - per-turn latency capture (`Stopwatch`, `turn_record`, `emit`).
- `turnguard.py` - `TurnGuard`: a newer turn supersedes an older one and a stale
  commit is dropped, so barge-in never persists a superseded reply.

Arriving in later PRs: `config.py` (Settings), `store/`, `llm.py`,
`normalize.py`, `interview/engine.py`, `service.py`, `debug_audio.py`,
`server/`, `__main__.py`, and `web/`.

## Later-layer checklist (enforce when each layer lands)

The foundation makes no LLM calls and has no store, so these paperflow rules are
latent today. The PR that introduces each layer MUST satisfy them:

- **LLM routing (`llm.py`, `normalize.py`, `engine.py`), D1:** every call goes
  through `pipeline.run_agent` / `run_task` / `AgentBackend.run`. Never construct
  a `pydantic_ai.Agent` or hit a provider SDK directly.
- **Structured output, D6 + D10:** keep `output_type=NormalizeOutput | TurnReply`
  (already `frozen=True`); pair each with a finite `output_retries` and use
  `ModelRetry` in a validator to self-correct rather than parsing free text.
- **Prompt-injection defense:** wrap every untrusted input (the subject's STT
  utterance and prior transcript) with `pipeline.tools.wrap_source` before it
  enters a prompt. Paper/transcript text is data, never instructions.
- **Determinism, D7:** sort `mishearings`, `corpus`, and `state.interests` (and
  any `set`/`dict`) before they feed a prompt. `pack/base.py`
  `normalize_system_prompt()` and the `interview/models.py` transcript header
  iterate unsorted today; add `sorted(...)` when they first feed an LLM.
- **Services + model sovereignty:** add `[services.chatsmith-conversational]`
  and `[services.chatsmith-fast]` to the root `SERVICES.toml` targeting a
  `vllm_thinking` (open-weight) backend, not only Anthropic. Resolve them with
  `pipeline.resolve_pipeline_models(pack.services(), registry)`, which raises
  `ServiceConfigError` if the names are missing.
- **Parser consolidation:** once chatsmith depends on `pipeline`, drop the local
  `parse_services` in `pack/prompt.py` for `pipeline.parse_pipeline_services`,
  and either adopt fence-aware section splitting or document that pack prompts
  avoid fenced `##` / `---` zones.
- **Schema versioning:** `interview/models.py` `from_dict` must reject or migrate
  a payload whose `version` exceeds `SCHEMA_VERSION` (written but not yet
  checked), matching `paperstore/html_manifest.py`.
- **Serial LLM, D11:** the async engine keeps at most one in-flight LLM request
  per session and must not raise pipeline's global concurrency
  (`_task_semaphore` / `_parallel_semaphore`). Port `TurnGuard`'s
  `threading.Lock` to an asyncio lock or queue. Session-state eviction already
  exists via `TurnGuard.forget`.

## The pack is DATA, not code

A pack is a directory (`packs/<name>/` or an external `CHATSMITH_PACK_DIR`) of:
`pack.toml` (manifest + logical model slots), `prompt.md` (persona + per-step
instructions + `## Services`), `keyterms.txt` (STT glossary),
`corpus_by_category.json`, `mishearings.json`, `themes.json` (GUI branding).
Selecting a different pack repurposes the whole app with no code change. The
on-screen character (Nova for wg21) is set in the pack, decoupled from the
package name. `pack.toml [services]` maps the logical slots `default` (the
conversational reply) and `fast` (the post-STT normalizer) onto service names in
the deployment's root `SERVICES.toml`; the slots are used only when routing
through `pipeline`, and the offline stub ignores them.

## Invariants

- **LLM output is always a frozen Pydantic model.** Add new output schemas to
  `models.py` with `frozen=True`; never parse free-text.
- **Config is injected; the core never reads `os.environ`.** `Settings` (later
  PR) is built once by the glue/CLI layer and passed in.
- **Sessions are owner-scoped.** Stores call `owner_matches` before returning a
  session, so a scoped caller can never read another owner's data. Local dev is
  single-user (`owner=None` sees all).
- **Latency metrics are for maintenance, never shown to end users.** Captured to
  a per-session sink, exportable with the transcript.
- BSL-1.0 header on every `.py`. `__init__.py` is re-exports only. `logging`,
  not `print` (the CLI, later, owns stdout). Tunable thresholds are named
  constants.

## Tests

Offline (stub voice, no LLM, no keys), cross-platform:

```bash
uv run --package chatsmith pytest packages/chatsmith/tests
```
