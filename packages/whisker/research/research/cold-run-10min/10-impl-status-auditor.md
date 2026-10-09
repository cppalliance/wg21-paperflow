# 10 - Implementation Status Auditor

**Verdict:** usable-with-conditions — v11 landed most CONSERVATIVE scheduling/cache levers, but the two largest remaining cold-wall multipliers (dual-pod sharding, verdict-first decode shrink) and AGGRESSIVE metadata replacement are still absent at HEAD; ~10 min remains blocked on infra + schema work, not on re-discovering waste.
**Confidence:** high

## Lever audit (settled SYNTHESIS levers vs HEAD)

| # | Lever | Status | Evidence |
|---|-------|--------|----------|
| 1 | Metadata-fail short-circuit | **Implemented** | `pdf_judge.py:742-758` skips page escalations + unit checks when `metadata_check.verdict != "pass"` (exempt: `--all-pages`, `--exhaustive-units`); `adjudicate.py:521-531` HTML lane equivalent. `_LANE_VERSION = 11` documents it (`cli.py:119-122`). **Drift:** skips review tier entirely; SYNTHESIS Tier A+B kept one unit on review (`148-verifier-stacking-arithmetic.md`). |
| 2 | HMAC per-paper guard tag | **Partial (PDF lane)** | `cli.py:467-479` `_paper_guard_tag` (HMAC); passed at `cli.py:1331-1333`. Text lane `adjudicate_paper()` at `cli.py:1403-1412` receives **no** `guard_tag`. Library fallbacks still use `secrets.token_hex`: `unit_judge.py:250,789`, `pdf_judge.py:395,660`. |
| 3 | Prompt reorder [static][document][query-last] | **Partial (PDF unit/page)** | Unit checks: candidate markdown first `unit_judge.py:791-798`. Page escalations: converted markdown first `pdf_judge.py:397-403`. **Not reordered:** monolith still RAW-PDF-then-markdown `pdf_judge.py:662-665`; metadata check source-first `unit_judge.py:252-261`; text triage header/outline before markdown `adjudicate.py:702-708`. |
| 4 | Verdict-first / terse pass schema | **Not implemented** | `UnitCheck` reasoning-first `models.py:301-313`; `MetadataOutlineCheck` reasoning-first `models.py:265-281`; `Adjudication` reasoning-first `models.py:174-177`. `PdfJudgment` alone is verdict-first `pdf_judge.py:256-270`. No conditional pass-path schema or empty pass reasoning. |
| 5 | Dual-pod CLI sharding | **Not implemented** | Single `asyncio.Semaphore(concurrency)` fleet gather `cli.py:1193-1194`; no index split, per-pod cap, or shard fingerprint. `h200x8-deepseek-v4-pro` declared in `SERVICES.toml:47-57` but unused by tapetum CLI. Doc still says one pod (`tapetum_llm.md:306`). |
| 6 | Error tombstone fingerprints + `--retry-errors` | **Implemented** | Flag `cli.py:373-378`; tombstone writer attaches fingerprint `cli.py:810-828`; skip path honors error + `--retry-errors` `cli.py:1269-1293`. |
| 7 | LJF paper ordering | **Implemented** | `_sort_pids_ljf` `cli.py:1030-1038`; applied on full run `cli.py:1063`. |
| 8 | `to_thread` for `screen_pages` | **Implemented** | `pdf_judge.py:658` `await asyncio.to_thread(screen_pages, ...)`. |
| 9 | Monolith `wait_for` timeout | **Implemented** | `MONOLITH_TIMEOUT_SECONDS = 240.0` `constants.py:244-245`; PDF monolith `pdf_judge.py:672-681`; text tier-1 `adjudicate.py:244-246`. Page/unit timeouts also present `constants.py:197,241-242`. |
| 10 | Per-call timing in sidecars | **Not implemented** | Only paper-level `duration_seconds` `cli.py:723-741,1375-1378`. No `call_timings[]`; `judge_task.py:52-74` records nothing; `PdfJudgeResult.to_sidecar_dict()` has no per-call fields (`pdf_judge.py:455-557`). |
| 11 | Escalation dedupe | **Not implemented** | Escalation loop `pdf_judge.py:818-899` then unit checks `pdf_judge.py:923-944` with no overlap guard; research found 18/18 escalations duplicate a unit check (`tapetum-llm-speedup/18-escalation-overlap-auditor.md`). |
| 12 | Deterministic metadata diff (no LLM) | **Not implemented** | Metadata still LLM via `run_metadata_outline_check` `unit_judge.py:231-273`; called from `pdf_judge.py:702` and `adjudicate.py:512`. `source_router.py` / `html_outline.py` supply deterministic outline data but do not replace the metadata call. |

## Findings

- [CRITICAL] **Dual-pod sharding — the largest unimplemented cold-wall multiplier — is still absent.** Evidence: no shard logic in `cli.py` (only `asyncio.Semaphore(concurrency)` at `1193-1194`); second pod entry exists in `SERVICES.toml:47-57` but tapetum never splits the fleet. Impact: SYNTHESIS modeled ~1.9× on post-cut wall (~1500 s savings on remainder); without it, even full v11 CONSERVATIVE+metadata lands ~11–14 min, not ≤600 s.

- [CRITICAL] **Metadata-fail short-circuit is live (v11) and matches the 44.6% call-elimination lever.** Evidence: `pdf_judge.py:747-758` sets `metadata_short_circuited` and skips escalations/units; HTML mirror `adjudicate.py:521-531`. Impact: ~1341 s toward 10 min already capturable at HEAD on cold runs (per SYNTHESIS P145 replay). Drift: review-tier papers get full skip, not “one top unit” (Tier A+B spec).

- [HIGH] **Verdict-first / pass-path schema shrink — ~180–360 s decode savings — not coded.** Evidence: `UnitCheck` and `MetadataOutlineCheck` still emit 40-word `reasoning` before `verdict` (`models.py:265-313`); 70% zero-defect unit checks still decode full schema. Impact: decode-bound pod (~5.91 s decode mean) leaves this as the largest **software-only** gap after metadata short-circuit.

- [HIGH] **HMAC guard tag + prompt reorder landed on PDF serial calls only.** Evidence: `_paper_guard_tag` + CLI wiring `cli.py:467-479,1331-1333`; document-first in `unit_judge.py:791-798`, `pdf_judge.py:397-403`. Text lane (~50% fleet calls, `42-text-lane-accountant`) lacks guard tag and document-first reorder. Impact: prefix-cache savings under-realized on HTML/text papers; PDF in-paper reuse partially enabled.

- [MED] **CONSERVATIVE “free wins” mostly shipped; observability gap remains.** Evidence: tombstone FP + `--retry-errors` `cli.py:373-378,810-828`; LJF `cli.py:1030-1063`; `to_thread` `pdf_judge.py:658`; monolith timeout `constants.py:244-245`. Missing: per-call `call_timings[]` (only `duration_seconds` per paper `cli.py:723-741`). Impact: warm error skip works; fleet A/B for remaining levers lacks per-call-class denominators (P96 playbook blocked).

- [MED] **Escalation dedupe and deterministic metadata remain paper-only.** Evidence: no dedupe between `pdf_judge.py:818-899` and `923-944`; metadata LLM at `unit_judge.py:263-273`. Impact: ~23 s (dedupe) + ~471 s (metadata LLM replacement, AGGRESSIVE) still on the table; dedupe is hygiene, metadata is a quality-gated cut.

- [LOW] **`_LANE_VERSION = 11` confirms prompt/cache semantics bumped; drift from SYNTHESIS HEAD 51cb704 is substantial implementation progress, not regression.** Evidence: `cli.py:119-122`, `tapetum_llm.md:334`. Impact: incremental skip invalidates correctly after v11; cold runs pick up short-circuit + PDF cache layout without operator flags.

## False-pass hypothesis

Metadata short-circuit on a **review**-tier metadata verdict skips all unit checks (`pdf_judge.py:748-752`) while SYNTHESIS allowed one corroborating unit on review papers (`42-text-lane-accountant.md` P4020R0 scenario): merged verdict stays capped at `review`, but `--inspect` loses section-level quotes that would have surfaced localized defects without flipping fleet verdicts.

## False-fail hypothesis

Dual-pod sharding (when implemented) with a mis-split index or unequal per-pod semaphores could leave one pod idle while the other queues, **increasing** wall time vs single-pod baseline despite correct per-paper verdicts — a scheduling false-fail, not a quality false-fail.

## What would change my mind

A fresh 381-paper cold run at HEAD with `/metrics` scrape showing wall ≤700 s **without** dual-pod would flip the “dual-pod required for 10 min” claim; a single counterexample run with timestamps beats the SYNTHESIS arithmetic model.

## Package readiness vs 10 min target (arithmetic)

| Package | SYNTHESIS levers | HEAD status |
|---------|------------------|-------------|
| CONSERVATIVE | tombstones, HMAC+reorder, LJF, to_thread, monolith timeout, dual-pod | **~5/6** (dual-pod missing; HMAC/reorder partial on text) |
| MODERATE | + metadata short-circuit, escalation dedupe, verdict-first | **~1/3** (short-circuit yes; dedupe + verdict-first no) |
| AGGRESSIVE | + deterministic metadata | **0/1** |

**Estimated cold wall at HEAD (no new run):** apply metadata short-circuit (−1341 s) + partial prefix gains (−200–400 s est.) to 3003 s baseline → **~1260–1460 s (~21–24 min)** if nothing else changed; still **above 600 s** until dual-pod (~÷1.9 → ~660–770 s) and/or verdict-first (−180–360 s) land.
