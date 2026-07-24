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
