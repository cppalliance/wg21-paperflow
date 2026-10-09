# Whisker LLM Extension: Lane 4 Adjudication Plan + Research Synthesis

**Date:** 2026-06-29
**Author context:** SG (QA), driven by the question "extend whisker with an LLM for simple and complex cases, self-hosted or API."
**Status:** PLAN — no code written yet. Awaiting sign-off on the architecture decision (see §7).

This file consolidates the multi-agent research (8 Composer subagents) and the
concrete implementation plan so the knowledge is not lost. Companion files:
`models-vram-deployment-survey.md` (VRAM/deployment survey) and
`comprehension-poc-report.md` (Lane 3 POC).

---

## 1. The core tension (read this first)

Whisker is **deliberately LLM-free**. `src/whisker/CLAUDE.md` and the internal
redteam/persona research treat "no LLM, no network, no randomness" as a
*prerequisite for CI trust*, not an accident. The one-time LLM read-back that
validates Lane 3 facts is explicitly "NEVER in CI (determinism, cost,
model-sovereignty)."

So "add an LLM to whisker" collides with a deliberate decision **if** the LLM
goes into the scoring/gate path. It does **not** collide if the LLM is a
**separate advisory lane** over the review band, leaving the deterministic gate
untouched. That is the design below.

---

## 2. Convergent research finding (8 subagents)

Every external tool and every QA benchmark independently points the same way.

### 2a. Converters: cheap-deterministic first, LLM only for hard cases

| Tool | Pattern | Trigger for LLM |
|------|---------|-----------------|
| **marker** `--use_llm` | full Surya/ML pipeline first, LLM per *block type* | tables, forms, display-math, section headers, cross-page table merges. Plain-text pages = 0 LLM calls. `"no corrections needed"` = cheap discard. Default `gemini-2.0-flash`, T=0 |
| **MinerU** hybrid | auto txt-vs-scan classify + `not_extract_list` | `--effort medium/high` toggles VLM layout depth + image/chart analysis; native text for simple blocks, VLM for tables/images/equations |
| **docling** | standard pipeline + per-page bitmap OCR gating | VLM is a separate operator-chosen pipeline; `force_backend_text` = text from PDF backend, structure from VLM |
| **LangExtract** | 3-tier by complexity | `gemini-3.5-flash` (default) → `gemini-3.1-flash-lite` (volume/cheap) → Gemini Pro (complex reasoning). Knobs: `extraction_passes` (recall vs tokens), `max_char_buffer` (accuracy vs calls), `max_workers` (speed only). Grounding = deterministic span alignment (`char_interval`), NOT an LLM judge |
| **firecrawl / unstructured** | routing at endpoint/partition layer | always a non-LLM escape hatch (regex extractor, `product` format); schema-guided extraction via OpenAI Structured Outputs |

### 2b. QA / evaluation: LLM-as-judge in the scoring loop is REJECTED

- **olmOCR-bench**: deterministic binary unit tests (present/absent/order/table/math).
  Paper: *"avoids reliance on model-based evaluators which can be biased towards
  favoring their own generations"* and *"avoids soft metrics (edit distance,
  ROUGE)."* LLMs are used only to **author** tests, then humans verify. No LLM in
  the scoring loop.
- **Whisker internal redteam/persona**: nothing recommends adding an LLM to the
  gate. Marker's LLM sub-scores are explicitly rejected for whisker. The
  comprehension gap is to be closed with Lane 3 facts + human labels +
  `calibrate`, all deterministic.

### 2c. The one accepted LLM-as-judge shape: the cascade

SOTA 2025-2026 production pattern for document/markdown QA judging:

```
Tier 0: Deterministic gates (whisker Lane 1-3)        <- stays the gate
   v  only ambiguous / review-band cases pass down
Tier 1: Small judge  - pointwise rubric, structured JSON, T=0
   v  escalate only if confidence in the ambiguous band
Tier 2: Large judge  - same rubric, evidence-anchored
   v  still uncertain
Tier 3: Human review (or multi-judge ensemble median)
```

Routing on **calibrated uncertainty** (isotonic regression cheap-model output ->
P(error)), not raw confidence. Cuts cost ~31-50% at matched accuracy. T=0,
schema-constrained output, evidence quotes, version-locked rubric, ~50-example
calibration set rescored on every judge-model change.

**Conclusion:** SG's intent (LLM for simple + complex cases) maps exactly onto
Tier 1/2 of this cascade, over the review band only. This is the intersection of
every source that does it right.

---

## 3. The design: Lane 4 "Adjudication" (advisory, cascade)

```
Lane 1-3 (deterministic) == Tier 0 == the gate. UNTOUCHED.
        |
   verdict == "review"  (~54% of papers; see persona research)   <- only entry point
        v
Lane 4 Tier 1: fast slot judge,  pointwise rubric, JSON, T=0
        v  only if "ambiguous band"
Lane 4 Tier 2: deep slot judge
        v  still uncertain
        -> stays "review" for a human    (Lane 4 NEVER hard-fails)
```

Iron rules:
1. Lane 4 sees only `verdict == "review"`, never `pass`/`fail`.
2. Lane 4 may *suggest* `review -> pass` or `review -> fail`, but it is
   **advisory**: a separate `whisker adjudicate` command, NOT inside
   `whisker --gate` (CI stays deterministic + free + reproducible).
3. Paper markdown is untrusted -> wrap with `ctx.inject_untrusted(text)` before
   it enters any prompt.
4. All LLM calls via the `pipeline` framework (`agent.run` / `run_task` /
   `run_agent`), never raw `chat.completions.create`. T=0, seed=0, structured
   `output_type` (Pydantic, >=5 fields for output stability per MODELS.md).

---

## 4. Model mapping (all on existing RunPod infra; 0 GB local)

These are remote HTTPS vLLM endpoints already in `SERVICES.toml` plus the new
Alliance pod. SG needs no local GPU.

| Lane 4 tier | slot | service | why |
|-------------|------|---------|-----|
| Tier 1 (simple) | `fast` | `h200-qwen3-32b` (Qwen3-32B, 131k) | fast, cheap, enough for clear review triage |
| Tier 2 (complex) | `deep` | `b300-qwen3-235b` (Qwen3-235B-A22B-FP8) or `h200x8-deepseek-v4-pro` (393k ctx) | hard cases, long papers |
| Validation ceiling (DEV only) | - | `anthropic-opus` (claude-opus-4-6) | one-time blind read-back anchor, never production (model-sovereignty) |

### New endpoint shared 2026-06-29 (Alliance self-hosted pod, since 2026-06-30 24/7)

`https://sgjy18glyi4blu-8000.proxy.runpod.net` — same vLLM/RunPod infra,
OpenAI-compatible. Identify the model via `GET /v1/models` then add:

```toml
[services.alliance-pod]
backend = "vllm_thinking"
base_url = "https://sgjy18glyi4blu-8000.proxy.runpod.net/v1"
api_key = "$ALLIANCE_POD_KEY"   # env var ONLY, never commit the key
model = "<from /v1/models>"
max_context_window = 131072
chars_per_token = 4.0
token_multiplier = 1.5
thinking_capable = true
tools_capable = false
```

**Cost discipline:** the pod bills per hour. Test, then stop it on RunPod when
idle. Keep experiments small (few review-band papers) until the design is proven.

> **Update 2026-06-30:** the pod now runs 24/7. The lane may run anytime without
> hourly-cost rationing, so the cost-discipline note above is superseded.

---

## 5. Files (estimate, for sign-off)

New:
- `packages/whisker/src/whisker/adjudicate.py` — Lane 4 cascade logic (returns data only)
- `packages/whisker/src/whisker/models.py` — Pydantic `Adjudication` (verdict, confidence, evidence_spans, reasoning; >=5 fields)
- `packages/whisker/src/whisker/whisker.md` — pipeline authority file with `## Services` slot map (template: `assay.md`)

Changed:
- `packages/whisker/src/whisker/__main__.py` — new `whisker adjudicate [PID]` subcommand (CLI persists; lib returns data)
- `packages/whisker/src/whisker/constants.py` — `AMBIGUOUS_BAND_*` routing thresholds (named constants)
- `packages/whisker/pyproject.toml` — add `pipeline`, `pydantic-ai` deps (breaks "standalone" invariant -> needs explicit sign-off)

Template = **assay** (not dissect): all-`custom` hooks + `agent.run()` +
`ctx.inject_untrusted()`, calls `validate_capabilities()` before `dispatch()`.

### Pipeline framework corrections (from source, override CLAUDE.md naming)
- `wrap_source` does NOT exist. The real API is `ctx.inject_untrusted(text)`
  (`pipeline/tools.py`). CLAUDE.md names it wrong.
- There is no per-step `output_retries` hook. Retries are hardcoded `retries=3`
  on the pydantic-ai `Agent` inside each `ModelBackend`.
- `## Services` lines look like `- **default:** alliance-pod`; `default` is required.

---

## 6. Validation (before trusting Lane 4 in any decision)

Mirror the Lane 3 read-back: take 5-10 review-band papers, run Lane 4, then have
a human adjudicate the same papers blind. Measure agreement (does Lane 4's
suggested review->pass/fail match the human?). Only trust Lane 4 after measured
agreement. Keep a fixed calibration set; rescore it whenever the judge model
changes.

---

## 7. What needs sign-off (SG / Vinnie)

1. **Whisker loses "standalone, no-LLM"** for this new lane. `src/whisker/CLAUDE.md`
   would need an edit -> architecture decision, not a silent change.
2. **Self-hosted primary, Opus dev-only** (chosen by SG) — confirm.
3. **Cost ceiling**: how much hourly RunPod spend is acceptable for the
   experiment phase? *(Resolved 2026-06-30: the pod runs 24/7; no hourly ceiling
   for the experiment phase, the lane may run anytime.)*

---

## 8. Sources (verified 2026-06-29)

- google/langextract README (model tiering, grounding via `char_interval`)
- datalab-to/marker (hybrid `--use_llm`, block-type triggers, `gemini-2.0-flash`)
- opendatalab/MinerU (hybrid-engine, `--effort`, `not_extract_list`)
- docling-project/docling (standard vs vlm pipeline, `force_backend_text`)
- allenai/olmocr + olmOCR-bench (deterministic unit tests, rejects LLM-as-judge)
- LLM-as-judge SOTA 2025-2026 (cascade, calibrated uncertainty, T=0, structured output)
- packages/pipeline (run_agent/run_task/AgentBackend, inject_untrusted, assay template)
- packages/whisker/research/{redteam,persona,notes} (no-LLM invariant; Lane 3 facts as the comprehension fix)
- SERVICES.toml (existing RunPod vLLM endpoints + anthropic-opus)
