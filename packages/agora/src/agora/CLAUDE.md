# agora

LLM-driven thread planning pipeline (the Mod). Project-wide rules live in the root `CLAUDE.md`; framework rules in `packages/pipeline/src/pipeline/CLAUDE.md`; sampling and concurrency rationale in `MODELS.md`.

## Authority

`agora.md` is the upstream authority for pipeline structure. It defines the step sequence, step metadata (model slot, execution mode, tools, conditions), and all LLM-facing instructions. Python conforms.

## What this pipeline does

Plans and generates a thread for a WG21 paper. The plan phase (Steps 0-7) researches the paper's public reception, calibrates discussion heat and intellectual interest, and lays out every reply slot with a brief describing what that reply must accomplish. The generation phase (Steps 8-9) casts a roster persona on every slot and writes each comment body in that persona's voice.

Votes, scores, orderings, time labels, and furniture stay `None`/empty: the reactor pass and the full-artifact emit arrive with the integration work. After Step 9 every non-deleted reply has `content` and a cast `character_username`; the brief on each `Reply` is a permanent audit trail: "this reply addresses anchor X from the Y domain lens."

`the-mod.md` is the creative reference: heat/interest tiers, Tables A-D, the noise palette, encounter rules, content rules, ad palette, mod roster. It ships as package data and is injected as context into the LLM calls that need it.

One-shot, fully batch. No `AskQuestion`, no human-in-the-loop, no resumable runs.

## Layout

- `agora.md` - prompt document and pipeline authority.
- `the-mod.md` - canonical creative reference, shipped as package data. `mod_reference.py` slices it into per-step excerpts injected into LLM call user messages.
- `mod_reference.py` - loads the-mod.md and exposes the scoped excerpt each step's prepare hook injects (heat check for calibration, Table C + noise palette for the skeleton, etc.). Fails loudly if a cited heading disappears.
- `pipeline.py` - async orchestration: hook registry (`_build_hooks`), step prepare/extract functions, blueprint validation, public `agora_paper()` and `agora_since()` entry points. Step parsing (`StepSpec`, `PipelinePrompt`) and the dispatch loop live in the `pipeline` package. Sub-agent dispatch goes through `pipeline.tasks.run_task`, which serializes via the shared `_task_semaphore`.
- `artifact.py` - the `.agora.json` interface: `thread_to_artifact` maps a fully generated `Thread` to the artifact dict (model names -> artifact vocabulary: `content`->`body`, `character_username`->`persona`, `flair`->`tag`, `submission_flair`->`submission_tag`; embeds the analysis-phase blueprint for audit), `validate_artifact` enforces the producer-side invariants (structure, vote uniqueness/direction, anchor coverage, roster membership when a roster is supplied). Canonical hand-authored fixtures live in `tests/fixtures/`.
- `roster.py` - the fixed persona roster (15 community personas + human mods + AutoModerator), each with a system prompt (the voice). `roster_usernames()` is the validation set; `dump_roster_json()` is the website-facing export.
- `casting.py` - deterministic persona selection over a planned thread (stable-hash draws; no LLM).
- `generate.py` - Step 8 (Cast) and Step 9 (Voice): copies casting onto the `Thread`, sets the pre-text flags, then writes every comment body via per-persona `run_task` calls in the-mod.md section 9 order. Voice calls ride the pipeline guard floor (`ctx.guard_instruction` + `ctx.inject_untrusted`), and each body is checked (verbatim blockquote when the slot carries a quote; every URL from the verified link inventory) with two corrective rewrites before the step fails.
- `render.py` - debug transcript and per-step trace renderers. No HTML.
- `models.py` - Pydantic models. One schema (`Thread`, `Reply`, `EncounterPlan` and friends) matches the eventual database; analysis-phase fields are required, generation-phase fields are `Optional`. Per-step LLM output classes and `PipelineState` live here too. `SourceLoc` imported from `paperstore`.
- `errors.py` - paper-domain errors (`PaperNotFoundError`, `PaperNotConvertedError`) inheriting `pipeline.PipelineError`.

## Pipeline architecture

10 steps (0-9). Pure-Python steps: 0, 7, 8. LLM `default` steps: 1, 3, 4, 5, 6. Step 2 is pure orchestration over 3 parallel sub-agents. Step 9 is a per-slot `run_task` fan-out routed through the `signal`/`noise` logical models.

Step 6 (Encounter Briefs) has a guard that skips it when calibration produced zero encounters.

Step 7 writes the blueprint `Thread` as `{pid}.agora.json` via `backend.write_agora_json`; Steps 8-9 mutate the in-memory `Thread` and never touch the backend. Debug transcripts and per-step traces go to `backend.get_debug_md_path(pid)` and `backend.get_trace_md_path(pid)`.

## Invariants

- `agora.md` is the authority. Step metadata drives model slot, execution mode, and tool registration.
- No hardcoded prompt strings for main agent steps. Main-agent LLM-facing instructions come from `agora.md` at runtime. Sub-agent system prompts are short role strings in Python; the substantive instructions still come from `agora.md`.
- No human loop. The pipeline runs end-to-end and emits its best plan.
- Steps 8-9 fill `content`, `character_username`, `is_mod`/`is_op`, and the pre-text dressing flags (`edited`, `controversial`, `deleted`). Votes, scores, orderings, and time labels stay `None`/empty for the reactor pass.
- Untrusted text crosses into voice prompts only inside `ctx.inject_untrusted` guard markers, and every voice system prompt starts with `ctx.guard_instruction` — the same boundary the dispatch path enforces.
- Provenance bound at generation time. Every `TechnicalAnchor` carries a `SourceLoc` (from paperstore).
- D6 reminder: every step hook declares `output_type=<PydanticModel>`.
- D7 reminder: validation sets like `addressed`, `lens_used`, `orphan_encounter` in `_validate_blueprint` stay internal (error messages sort them). If you start feeding such collections into a prompt, sort them first.
- Blueprint validation is hard-fail: unaddressed anchors, orphan encounter slots, and domain-lens floor shortfalls raise `ValidationStepError`; an invalid blueprint never serializes. `agora_since` catches per-paper failures and continues the batch.
- Research (Step 2) is toggleable per run via `agora_paper(..., research=False)`; off records an empty research summary, the same shape as the missing-web-tools degradation.
