# 11 - Output-Token-Decode-Auditor

**Verdict:** usable-with-conditions — per-call output decode grew ~1.5x on aggregate tokens, not ~2x per monolith call; the 4.2x wall regression is driven primarily by ~7x call multiplication with repeated prefill, while schema growth on new call types adds modest decode (+11 s/paper) and larger guided-JSON prefill overhead.
**Confidence:** medium

## Findings

- [CRITICAL] **Monolith schemas did not grow; the "quiet doubling" failure class does not apply to the primary judge call.** Evidence: `git show 58a978c:packages/whisker/src/whisker/tapetum_llm/models.py` has `Adjudication` (7 fields) identical to HEAD `models.py:166-188`; `PdfJudgment` at `58a978c` and HEAD `pdf_judge.py:252-269` both have 4 fields (`verdict`, `missing_content`, `confidence`, `reasoning`). Schema JSON: HEAD `PdfJudgment` 826 chars (~206 tok), `Adjudication` 2657 chars (~664 tok) — unchanged class set at 07-09. Impact: blaming decode regression on monolith schema inflation is wrong; synthesis must not chase a phantom 2x decode on tier-1/pdf-judge.

- [CRITICAL] **Tonight's per-paper decoded output is P50 ~936 tok across ~7 calls, vs ~635 tok in one call at 07-09 — only 1.47x token growth.** Evidence: reconstructed from 377 successful `data/whisker/llm/*.whisker.tapetum.json` sidecars (2026-07-23 run, `00-baseline.md:24-28`): monolith proxy P50 283 tok, metadata P50 112 tok, unit checks aggregate P50 524 tok (5 checks × P50 77 tok each, n=1510 single-check samples). Baseline 635 tok from `17-latency-decomposer.md:14` (204 sidecars, `Adjudication`-shaped). At 28 tok/s decode (`17-latency-decomposer.md:29`): old 22.7 s decode, new 33.4 s decode (+10.8 s). Back-solved serial budget (`692.3×32/381` vs `2883×32/381`, `00-baseline.md:41-42`): delta 183.9 s/paper; decode-token growth explains **5.8%** of that delta. Impact: output-decode shrink levers (schema field caps, max_tokens cuts) cannot recover 48 min; they save single-digit seconds per paper.

- [CRITICAL] **Call multiplication (~7×) dominates; per-call output shrank.** Evidence: sidecar-derived `n_calls` P50 = 7 (1 monolith + 1 metadata + P50 5 unit checks; `unit_judge.py` did not exist at `58a978c`, `00-baseline.md:66-68`). Per-call output P50 = 936/7 ≈ **134 tok** vs 635 tok monolith-only. `00-baseline.md:104-108` envelope 4-9× call-volume matches observed ~7×. Impact: the regression price is mostly "more calls," not "fatter JSON per call."

- [HIGH] **New call types add decode budget by count, not by catastrophic schema bloat.** Evidence: worst-case synthetic JSON (`UnitCheck` with 5 `DefectFinding` groups: 2216 chars ≈ 554 tok; `MetadataOutlineCheck`: 471 chars ≈ 118 tok) vs monolith worst-case `PdfJudgment` 887 chars ≈ 222 tok. Observed P50 unit-check single: 311 chars ≈ 77 tok; P90 1580 chars ≈ 395 tok when defects present (n=1510). `DefectFinding` adds 7 fields including `affected_count` and 25-word `source_quote` (`models.py:231-259`), but empty-defect passes dominate. Decode per call type @28 tok/s (P50): monolith 10.1 s, metadata 4.0 s, units (5×) 18.7 s. Impact: unit-check decode is real (~19 s/paper aggregate) but is **new work**, not doubled monolith decode.

- [HIGH] **`max_tokens` and `thinking_budget` did not change in ways that inflate decode.** Evidence: `git show 58a978c:adjudicate.py` already had `_SLOT_MAX_TOKENS fast=1024/deep=2048`; HEAD `adjudicate.py:88-92` identical. PDF judge `max_tokens=1536` unchanged (`git show 58a978c:cli.py` vs HEAD `cli.py:1007-1012`). `thinking_budget` omitted everywhere; pod default off (`tapetum_llm.md:305`, `17-latency-decomposer.md:16`). `git diff 58a978c HEAD -- packages/pipeline/src/pipeline/model_backends.py` empty — no guided-JSON strategy change. Impact: 07-22 `_LANE_VERSION` bump and prompt growth are not paired with output-ceiling or thinking enablement; decode inflation is not a config knob accident.

- [MED] **Guided-JSON schema prefill grew on new call types (prefill term, not decode), especially `UnitCheck`.** Evidence: HEAD schema-in-prompt sizes via `model_backends._schema_instruction`: `PdfJudgment` ~301 tok, `MetadataOutlineCheck` ~372 tok, `UnitCheck` ~793 tok (2.6× monolith schema). `UNIT_CHECK_SYSTEM_PROMPT` ~924 tok includes full `CONVERSION_CONTRACT` ~524 tok (`unit_judge.py:70-106`, 07-22 all-pages side effect per `00-baseline.md:74-77`). Each of ~5 unit calls repeats ~1717 tok system+schema (`unit_judge.py` + schema). At 4000 tok/s prefill (`17-latency-decomposer.md:12`): ~0.43 s/call × 5 ≈ 2.2 s/paper prefill from unit schema alone — small vs decode but multiplied by call count. Impact: input-side schema growth belongs in the Prompt-Token persona's ledger; it is not the decode-doubling hypothesis.

- [MED] **Sidecar persistence grew 75× but that is stored verdict surface, not generation budget.** Evidence: schema v0 error stubs P50 202 bytes (n=4); schema v8 P50 12638 bytes (n=377). `TapetumResult.to_dict` now carries `unit_checks`, `defect_groups`, `metadata_outline_check`, `evidence_dispositions` (`models.py:363-411`). LLM never decodes sidecars; only structured `output_type` JSON is generated. Impact: do not use sidecar byte size as decode proxy — use reconstructed per-call model output only.

- [LOW] **Page escalation and ideal verification are negligible decode terms tonight.** Evidence: `00-baseline.md:32-33` log: 16 escalation mentions, 181 pdf-judge lines; `PageJudgment` schema 1399 chars (~350 tok), output shape similar to `PdfJudgment`. `ideal_verification` present in 1/381 sidecars (2847 chars). Impact: tier-2/`Adjudication` escalation (23 papers, `00-baseline.md:27`) adds occasional ~635 tok calls; not fleet-scale.

## Decode budget table (P50 paper, @28 tok/s)

| Call type | 07-09 | Now (P50) | Output tok | Decode s | Share of new 33.4 s decode |
|-----------|-------|-----------|------------|----------|----------------------------|
| Monolith (`PdfJudgment` / `Adjudication`) | 635 tok, 1 call | 283 tok, 1 call | 283 | 10.1 | 30% |
| Metadata/outline | — | 112 tok, 1 call | 112 | 4.0 | 12% |
| Unit checks (×5) | — | 524 tok, 5 calls | 524 | 18.7 | 56% |
| Page escalation | — | ~0.04 call/paper | ~80 est. | ~3 est. | <2% |
| **Total decode** | **22.7 s** | **33.4 s** | **936** | **33.4** | **100%** |

**Share of 4.2× wall regression attributable to output-token decode:** ~6% of the 183.9 s/paper serial delta (10.8 s / 183.9 s). Remaining ~94% is call-count multiplication, repeated prefill, and per-call fixed latency under c=32 continuous batching (not output length on any single schema).

## False-pass hypothesis

Shrinking `DefectFinding` field caps or dropping `affected_count`/`source_quote` would cut P90 unit-check output (~395 tok) toward P50 (~77 tok) and look like a decode win on dashboards, but would strip the scale signal the 07-17 lane needs for keyword-delta defect groups — faster calls that systematically under-report omission counts.

## False-fail hypothesis

Setting `max_tokens` to 2048 on unit checks (matching authority doc) could trigger `finish_reason=length` retries on papers with 5 populated `DefectFinding` groups (`model_backends.py:377-387` doubles budget), turning one 18.7 s unit tranche into two decode passes and masquerading as a schema-size regression.

## What would change my mind

A `--debug` sample of 20 papers logging raw model output char length per call type alongside wall time: if unit-check median raw JSON exceeds 1200 chars (300 tok) while sidecar reconstruction shows 77 tok, hidden thinking or non-JSON prefix is adding decode outside the measured schemas; if medians match reconstruction, call-count multiplication is confirmed as the sole lever above ~6% decode share.
