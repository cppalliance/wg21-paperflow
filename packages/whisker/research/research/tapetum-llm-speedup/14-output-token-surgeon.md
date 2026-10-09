# 14 - Output-Token-Surgeon

**Verdict:** usable-with-conditions — pass-path reasoning and redundant prose dominate decode (~303k fleet output tokens); conditional verdict-first schemas can shave ~3–6 min off the 3003 s cold run, but output shrink alone cannot reach the 5–10 min target without call elimination.
**Confidence:** medium

## Findings

- [CRITICAL] **Fleet output is ~303k tokens across 2284 calls; pass-path reasoning is the largest shrinkable block.** Evidence: call census `00-baseline.md:22-23` (381 monolith + 377 metadata + 1510 unit + ~16 page); sidecar P50 per call type from `research/tapetum-llm-throughput/11-output-token-decode-auditor.md:10-14` (monolith 283 tok, metadata 112 tok, unit single-check 77 tok, paper aggregate 936 tok). Reconstructed total: 381×283 + 377×112 + 1510×77 + 16×150 ≈ **303,447 output tokens**. On pass unit checks (1057/1510 = 70%, `00-baseline.md:29`), P50 JSON is ~77 tok with `defects:[]` — field audit (`models.py:298-320`) shows ~55 tok is the 40-word `reasoning` alone; nothing downstream reads unit reasoning on pass (`unit_judge.py:792` persists it but fusion/grounding skip it). Impact: empty or 10-word pass reasoning across 1057 calls saves ~47k tok (~22 min serial @ 70 tok/s, ~2.8 min wall @ 16 slots / 70 tok/s, ~8.4 min @ 28 tok/s effective).

- [HIGH] **`DefectFinding` quotes are non-negotiable on non-pass; `affected_count` is mechanically consumed.** Evidence: seven fields per group (`models.py:231-259`): `defect_type` (~3 tok), `source_unit` (~5), `source_quote` (25 words ≈ 35 tok, prompt `unit_judge.py:157-158`), `candidate_location` (~0–10), `affected_count` (~2, verified in `verify_defect_counts` at `unit_judge.py:448`), `severity` (~1), `reasoning` (20 words ≈ 27). Worst-case 5 groups ≈ 554 tok synthetic (`11-output-token-decode-auditor.md:14`); P90 observed unit check ≈ 395 tok. Grounding rejects quotes `<5` chars (`unit_judge.py:703`) and drops ungrounded claims. Impact: shrinking or deferring `source_quote` on fail paths would save decode but breaks two-sided verification (`unit_judge.py:686-691`) — quality risk is false-pass on hallucinated defects, not faster JSON.

- [HIGH] **`PdfJudgment` / `PageJudgment` already use evidence-on-demand for quotes; monolith P50 283 tok implies verbose reasoning, not quote bloat.** Evidence: `PdfJudgment` four fields (`pdf_judge.py:252-269`): `verdict` (1), `confidence` (3), `reasoning` (60 words ≈ 80 tok, `pdf_judge.py:267-268`), `missing_content` (max 5 × 20 words, empty on pass — `pdf_judge.py:354-355`). `PageJudgment` adds `content_missing` bool with validator tying quotes to flag (`models.py:208-227`). Pass-shaped monolith (~124 tok: reasoning + keys) vs P50 283 tok implies models emit long reasoning or occasional quotes on review-tier passes. Impact: cap `reasoning` 60→20 words (LLMTrace uses ~60-token *total* output, `05-web.md:105-106`) saves ~40 tok × 381 monolith ≈ 15k tok (~3.6 min wall @ 28 tok/s / 16 slots); cannot drop `missing_content` on non-pass without breaking `_fold_monolith_verdict` (`pdf_judge.py:343-367`).

- [HIGH] **`MetadataOutlineCheck` is cheap and already conditional on mismatches.** Evidence: six fields (`models.py:262-281`): `reasoning` (40 words ≈ 55 tok), three bools (~6 tok), `heading_drift` / `missing_sections` (lists max 5, empty on pass), `verdict` (1). P50 112 tok (`11-output-token-decode-auditor.md:14`). Validator forbids pass with mismatches (`models.py:283-295`). Impact: shrinking `reasoning` 40→15 words saves ~25 tok × 377 ≈ 9.4k tok (~1.4 min wall @ 28 tok/s / 16); lists are already empty on clean papers — no further conditionalization win.

- [MED] **`Adjudication` (HTML text lane) is the heaviest schema per call but rare in tonight's PDF fleet.** Evidence: seven fields (`models.py:166-188`, stability floor `models.py:15-16`): `reasoning` (60 words ≈ 80), `axis_findings` (7 × `AxisFinding` ≈ 140–175 tok even on pass — `models.py:155-163` 12-word notes), `worst_axis` (2), `verdict` (1), `confidence` (3), `evidence_spans` (max 3 × ~49 tok, grounded in `adjudicate.py:309`), `primary_concern` (15 words). Tier-1 escalation 23/381 papers (`11-output-token-decode-auditor.md:22`). `max_tokens` 1024 fast / 2048 deep unchanged (`adjudicate.py:88-92`). Impact: compressing axis_findings on pass could save ~100 tok × ~46 Adjudication calls — negligible fleet wall; high verdict-drift risk on HTML lane.

- [MED] **50% mean output-token reduction saves ~2–6 min wall on the 3003 s run, not 40+ min.** Evidence: total output ~303k tok; 50% cut = ~152k tok saved. Decode @ 70 tok/s per request (`00-baseline.md:26-27`, `pdf_judge.py:27-28`): serial decode savings 152k/70 ≈ 2170 s → **~136 s wall** with 16 server slots (2170/16). Effective loaded decode @ 28 tok/s (`11-output-token-decode-auditor.md:29`): **~339 s (~5.7 min)** wall. Per-call latency ~20 s (`00-baseline.md:24-25`) is mostly prefill + fixed slot time; output decode is ~6–23% of fleet wall per `11-output-token-decode-auditor.md:34`. Impact: output shrink is a necessary but insufficient lever; pairing with call elimination (`00-baseline.md:90-91`) is required for 5–10 min.

- [MED] **SLMJury / LLMTrace support shorter verdicts; general-task penalty applies to our rubric.** Evidence: Phi-4 at 10 output tokens = 89.55% oracle agreement on math; loses up to 23% on general tasks (`05-web.md:88-90`). LLMTrace ADR uses ~60-token strict JSON (`05-web.md:105-106`). Our prompts already bind terseness (`pdf_judge.py:203-212`, `unit_judge.py:156-158`) but schema field order forces reasoning-first CoT (`models.py:14-15`). Impact: verdict-first reorder + pass-path reasoning omission could approach SLMJury token budgets on the 1057 zero-defect unit checks with medium drift risk; must re-measure on 48-paper holdout (`whisker/CLAUDE.md` dev-replay vs holdout).

- [LOW] **`PdfJudgment` has 4 schema fields — below the 5-field stability floor.** Evidence: `models.py:15-16` cites `MODELS.md:35-49` (≥5 fields for constrained-decoding stability); `PdfJudgment` at `pdf_judge.py:252-269` has 4. `UnitCheck`/`Adjudication`/`MetadataOutlineCheck` meet the floor (5–7 fields). Impact: adding a discard padding field (cf. `MODELS.md:51` `unused1`/`unused2` pattern) costs ~4 tok output but may reduce verdict flip rate; net wall effect negligible.

## Per-call output token budget (field-level, P50 / P90)

| Schema | Call count (381-paper fleet) | Pass P50 | Non-pass P90 | Dominant fields | Safe conditional? |
|--------|------------------------------|----------|--------------|-----------------|-------------------|
| `PdfJudgment` | 381 | ~124 (empty quotes) / obs 283 | ~350 (3 quotes + reasoning) | `reasoning` 80, `missing_content` 0–130 | Quotes already conditional; shrink reasoning |
| `MetadataOutlineCheck` | 377 | ~112 | ~180 (drift strings) | `reasoning` 55, bools 6 | Lists already empty on pass |
| `UnitCheck` | 1510 | ~77 (`defects:[]`) | ~395 (2–3 groups) | pass: `reasoning` 55; fail: `source_quote`+`affected_count` | Pass: omit/shrink reasoning; fail: keep quotes |
| `PageJudgment` | ~16 | ~90 | ~250 | same as PdfJudgment + `content_missing` | Quotes conditional on flag (`models.py:220-227`) |
| `Adjudication` | ~46 (HTML + tier-2) | ~220 | ~400 | `axis_findings` 140+, `evidence_spans` 0–147 | Do not drop axes without holdout proof |

## False-pass hypothesis

Verdict-first `UnitCheck` with literal `"ok"` reasoning on pass (SLMJury-style ~10 tok) on the 1057 zero-defect calls would cut decode ~45 tok each, but removes the auditable CoT the schema deliberately front-loads (`models.py:14-15`). A model that silently skips comparing `constexpr` counts would return `pass` with no prose trace; downstream has no defect quotes to ground — the documented selection-gap false-pass (`00-baseline.md:29-30`, only 16/381 verdicts changed by LLM) would widen.

## False-fail hypothesis

Shrinking `DefectFinding.source_quote` below verbatim grounding (e.g., 25→8 words) or dropping `affected_count` to speed JSON would cause `source_ungrounded` dispositions (`unit_judge.py:703-708`) and cap papers at `review` via fail-closed coverage — manufacturing review noise on papers that are actually clean, the opposite of the RESCUE population intent.

## What would change my mind

Holdout re-run (48-paper manifest, `whisker/CLAUDE.md`) comparing current schemas vs pass-path `reasoning=""` + 20-word caps on monolith/metadata, measuring both wall time **and** verdict delta + grounding drop rate: if ≥95% verdict stability and zero increase in `source_ungrounded`/`candidate_not_found` rates, promote conditional pass schemas; if verdict flips exceed the measured ≥25% rerun instability baseline (`whisker/CLAUDE.md` advisory lane), abandon output shrink except `max_tokens` ceiling tuning.
