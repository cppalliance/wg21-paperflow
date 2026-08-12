# agora

LLM-driven thread planning pipeline (the Mod). Project-wide rules live in the root `CLAUDE.md`; framework rules in `packages/pipeline/src/pipeline/CLAUDE.md`; sampling and concurrency rationale in `MODELS.md`.

## Authority

`agora.md` is the upstream authority for pipeline structure. It defines the step sequence, step metadata (model slot, execution mode, tools, conditions), and all LLM-facing instructions. Python conforms.

## What this pipeline does

Plans, generates, and emits a thread for a WG21 paper. The plan phase (Steps 0-7) researches the paper's public reception, calibrates discussion heat and intellectual interest, and lays out every reply slot with a brief describing what that reply must accomplish. The generation phase (Steps 8-10) casts a roster persona on every slot, writes each comment body in that persona's voice, and runs the reactor pass — every persona's individual `+1`/`-1` votes on every comment and the submission. The emit phase (Step 11) maps the finished thread to the `.agora.json` artifact, runs the advisory generation QA report, validates the producer contract, and writes the artifact to paperstore.

Scores, orderings, time labels, and reveal timing are **not** produced here — the website derives everything display-side from revealed votes. The brief on each `Reply` is a permanent audit trail: "this reply addresses anchor X from the Y domain lens."

`the-mod.md` is the creative reference: heat/interest tiers, Tables A-D, the noise palette, encounter rules, content rules, ad palette, mod roster. It ships as package data and is injected as context into the LLM calls that need it.

One-shot, fully batch. No `AskQuestion`, no human-in-the-loop, no resumable runs.

## Layout

- `agora.md` - prompt document and pipeline authority.
- `the-mod.md` - canonical creative reference, shipped as package data. `mod_reference.py` slices it into per-step excerpts injected into LLM call user messages.
- `mod_reference.py` - loads the-mod.md and exposes the scoped excerpt each step's prepare hook injects (heat check for calibration, Table C + noise palette for the skeleton, etc.). Fails loudly if a cited heading disappears.
- `pipeline.py` - async orchestration: hook registry (`_build_hooks`), step prepare/extract functions, blueprint validation, public `agora_paper()` and `agora_since()` entry points. Step parsing (`StepSpec`, `PipelinePrompt`) and the dispatch loop live in the `pipeline` package. Sub-agent dispatch goes through `pipeline.tasks.run_task`, which serializes via the shared `_task_semaphore`.
- `artifact.py` - the `.agora.json` interface: `thread_to_artifact` maps a fully generated `Thread` to the artifact dict (model names -> artifact vocabulary: `content`->`body`, `character_username`->`persona`, `flair`->`tag`, `submission_flair`->`submission_tag`; embeds the analysis-phase blueprint for audit), `validate_artifact` enforces the producer-side invariants (structure, vote uniqueness/direction, anchor coverage, roster membership when a roster is supplied). Canonical hand-authored fixtures live in `tests/fixtures/`.
- `roster.py` - the fixed persona roster (15 community personas + human mods + AutoModerator), each with a system prompt (the voice) and the reactor floats (`upvote_bias`, `contrarianism`, `snark_affinity`). `roster_usernames()` is the validation set; `dump_roster_json()` is the website-facing export.
- `casting.py` - deterministic persona selection over a planned thread (stable-hash draws; no LLM).
- `generate.py` - Step 8 (Cast) and Step 9 (Voice): copies casting onto the `Thread`, sets the pre-text flags, then writes every comment body via per-persona `run_task` calls in the-mod.md section 9 order. Voice calls ride the pipeline guard floor (`ctx.guard_instruction` + `ctx.inject_untrusted`), and each body is checked (verbatim blockquote when the slot carries a quote; every URL from the verified link inventory) with two corrective rewrites before the step fails.
- `reactor.py` - Step 10: the deterministic per-persona vote pass (pure heuristic, no LLM).
- `qa.py` - the advisory generation QA report Step 11 runs before the write: unknown `u/` handles, personal-attack phrasing, typo-nitpick comments, fourth-wall leaks. Findings are logged and traced, never fatal.
- `render.py` - debug transcript and per-step trace renderers. No HTML.
- `models.py` - Pydantic models. One schema (`Thread`, `Reply`, `EncounterPlan` and friends) matches the eventual database; analysis-phase fields are required, generation-phase fields are `Optional`. Per-step LLM output classes and `PipelineState` live here too. `SourceLoc` imported from `paperstore`.
- `errors.py` - paper-domain errors (`PaperNotFoundError`, `PaperNotConvertedError`) inheriting `pipeline.PipelineError`.

## Pipeline architecture

12 steps (0-11). Pure-Python steps: 0, 7, 8, 10, 11. LLM `default` steps: 1, 3, 4, 5, 6. Step 2 is pure orchestration over 3 parallel sub-agents. Step 9 routes signal/teaser/encounter/mod slots through the `signal` logical model and noise/tangent through `noise`.

Step 6 (Encounter Briefs) has a guard that skips it when calibration produced zero encounters.

Step 11 is the pipeline's only artifact write: it validates via `validate_artifact` (full roster) and persists `{pid}.agora.json` via `backend.write_agora_json`, so a failed run never leaves a partial artifact. Debug transcripts and per-step traces go to `backend.get_debug_md_path(pid)` and `backend.get_trace_md_path(pid)`.

## Invariants

- `agora.md` is the authority. Step metadata drives model slot, execution mode, and tool registration.
- No hardcoded prompt strings for main agent steps. Main-agent LLM-facing instructions come from `agora.md` at runtime. Sub-agent system prompts are short role strings in Python; the substantive instructions still come from `agora.md`.
- No human loop. The pipeline runs end-to-end and emits its best thread.
- Planning never fills generation fields; the generation steps own them (Step 8: identity + dressing flags, Step 9: content, Step 10: votes). `score`, `ordering`, `collapsed`, `removed`, and time labels stay `None`/empty for the website.
- Untrusted text crosses into voice prompts only inside `ctx.inject_untrusted` guard markers, and every voice system prompt starts with `ctx.guard_instruction` — the same boundary the dispatch path enforces.
- Provenance bound at generation time. Every `TechnicalAnchor` carries a `SourceLoc` (from paperstore).
- D6 reminder: every step hook declares `output_type=<PydanticModel>`.
- D7 reminder: validation sets like `addressed`, `lens_used`, `orphan_encounter` in `_validate_blueprint` stay internal (error messages sort them). If you start feeding such collections into a prompt, sort them first.
- Blueprint validation is hard-fail: unaddressed anchors, orphan encounter slots, and domain-lens floor shortfalls raise `ValidationStepError`; an invalid blueprint never serializes. `agora_since` catches per-paper failures and continues the batch.
- Research (Step 2) is toggleable per run via `agora_paper(..., research=False)`; off records an empty research summary, the same shape as the missing-web-tools degradation.
