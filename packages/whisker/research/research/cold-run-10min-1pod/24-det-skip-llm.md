# 24 - Det-Skip-LLM (strong deterministic signals)

**Verdict:** usable-with-conditions — **no shipped mode skips LLM entirely** on strong det; partial skips exist (metadata short-circuit, router-empty, incremental fingerprint); a **new `--det-skip` tier** is architecturally safe for the advisory lane but trades speed for the documented selection-gap blind spot.
**Confidence:** high

## Executive answer

| Question | Answer |
|----------|--------|
| **Mode exists today?** | **No** — nothing skips all in-paper LLM calls based on whisker det strength. |
| **Closest shipped behavior** | v11 **metadata short-circuit** (2 calls min), **E-PDF-4** no router signals (2 calls), **C2** fingerprint skip (warm only), **`--fuse-only`** (zero LLM, prior sidecars). |
| **Viable for advisory lane?** | **Yes, with conditions** — fusion already handles absent tapetum as `whisker_only`; lane never gates. **Not** viable as default cold path if advisory value matters (selection gap, 16/381 merged flips). |
| **Cold after `_LANE_VERSION` bump?** | Fingerprint skip is **0 s** on cold; det-skip would cut **N** on first run — complementary to v11 metadata short-circuit, not a replacement. |

---

## Findings

- [CRITICAL] **No CLI flag or code path skips adjudication when det is strong/pass.** Evidence: default full run adjudicates every converted paper (`cli.py:1058-1065`); `--review-all` narrows *to* risk candidates but still runs LLM on each selected PID (`cli.py:1052-1055`, `adjudicate.select_candidates`); `--fuse-only` skips LLM entirely but requires existing sidecars (`cli.py:1044-1046`, `343-347`). Impact: operator asking for "strong det → no LLM" must implement a new selection gate; nothing in HEAD matches.

- [CRITICAL] **Partial LLM skip is shipped; full skip is not.** Evidence: v11 metadata short-circuit skips page escalations + unit checks when `metadata_outline_check.verdict != pass` and not audit mode (`pdf_judge.py:742-759`, `798`; HTML mirror `adjudicate.py:521-531`) — **minimum 2 LLM calls remain** (PDF: monolith + metadata; HTML text: tier-1 + metadata). When router emits no `risk_signals`, unit loop never runs (`pdf_judge.py:934-945`, `unit_judge.py:317-354`). Text lane skips tier-2 when escalation signals empty (`adjudicate.py:301-303`). Impact: best-case fleet paper is **1–2 LLM calls**, not zero; ~44.6% of v10 unit calls eliminated (`24-fusion-dead-reverify.md`), not 100% of calls on any paper.

- [HIGH] **`--review-all` is the inverse of det-skip, not an instance of it.** Evidence: `select_candidates` (`adjudicate.py:101-129`) selects PRIMARY (pass + risk signals), SECONDARY (non-benign review), RESCUE (heading-only fail). Clean **pass-tier papers without risk signals are excluded** — the documented selection gap (`whisker/CLAUDE.md` tapetum section). Impact: `--review-all` saves wall by *skipping clean passes* (no LLM), but that is candidate filtering, not "strong det → skip"; it **widens** the false-pass blind spot full run was designed to close.

- [HIGH] **Strong-det skip would fuse as `whisker_only` — safe for gate, weak for advisory.** Evidence: `fuse_verdicts` when tapetum absent/unusable → `combined_rule: whisker_only`, `combined_verdict = det` (`fusion.py:346-357`, `_tapetum_is_usable` `154-164`). Root contract: tapetum never gates (`whisker/CLAUDE.md`). Impact: det-skip does not change CI exit codes or deterministic verdicts; it only removes second-opinion and merged-report rows for skipped PIDs.

- [HIGH] **Cold after lane bump: fingerprint useless; det-skip would help N.** Evidence: incremental skip requires matching sidecar fingerprint (`cli.py:1257-1301`); `_LANE_VERSION` bump invalidates all prior sidecars (`cli.py:119-123`). v11 metadata short-circuit is already in the call path on cold default fleet (~−1059 s modeled, `cold-run-10min-1pod/00-baseline.md:26-28`). Impact: post-bump cold must pay full LLM on every paper unless a **new** skip rule runs; det-skip is one such N-cut, orthogonal to fingerprint.

- [MED] **Proposed but unimplemented: unit-only deterministic skip, not whole-paper skip.** Evidence: zero-defect predictor (`35-zero-defect-predictor.md`) — best volume rule skips ~45% of **unit** checks at 98.6% verified-defect precision (below SAJA 99.6% bar); requires `predicted_clean_unit_ids` + fusion `coverage_complete` extension. Docling-style `--profile fast` (`56-docling-quality-speed.md`) — monolith + metadata only unless hard router signals; **not in CLI**. Deterministic metadata diff (`10-impl-status-auditor.md`, `131-surya-model-sizing.md`) — replaces 377 metadata **LLM** calls, not whole paper. Impact: engineering effort on det-skip-LLM competes with higher-yield partial cuts already partially shipped.

- [MED] **Wall arithmetic if clean-pass papers skipped entirely (modeled, not replayed).** Baseline: 381 papers, ~2284 calls, 3003 s cold (`00-baseline.md`). Det pass cohort ~163/381 (~42.7%, `vlm-pdf-qa/18-product-decision-skeptic.md`). PRIMARY pass+risk is a subset; **roughly 100–140 clean-pass papers** (no lossy tables, no parse errors, no mojibake, no cov-uni gap) might qualify — **needs sidecar replay to pin**. At **2 calls/paper** (post-v11 metadata pass + monolith or tier-1 only): **200–280 calls** → **250–350 s** @ S=16 (`N×20/16`). Not additive with metadata-fail short-circuit (disjoint cohorts). Still **~500+ s short** of 600 s target alone (`00-baseline.md:27-28`).

- [LOW] **Benign region-only review fold (no LLM at all) is a separate, smaller lever.** Evidence: `hybrid-llm-scoring/SYNTHESIS.md:40` — ~44 never-adjudicated region-only reviews could clear with det-side fold, zero LLM. Distinct from clean-pass skip; SECONDARY population already mostly gets LLM under `--review-all`.

---

## What exists today (skip spectrum)

| Mechanism | LLM calls left | Cold after lane bump? | Trigger |
|-----------|---------------:|----------------------|---------|
| Default full fleet | ~2–12 / paper | Pays full N | — |
| v11 metadata short-circuit | **2** min (PDF/HTML) | **Yes** | metadata ≠ pass |
| No router signals (E-PDF-4) | **2** | Yes | empty `risk_signals` |
| No tier-2 escalation (E-TXT-3) | **1** (small HTML) | Yes | confident tier-1 |
| `--review-all` | 0 on clean pass | Yes | candidate filter |
| Incremental fingerprint (C2) | 0 on match | **No** | unchanged inputs |
| `--fuse-only` | **0** | **No** | prior sidecars |
| **Hypothetical `--det-skip`** | **0** | **Yes** | det pass + no risk + gates green |

---

## False-pass hypothesis

**Clean-pass det-skip** skips LLM on papers with `verdict=pass`, high `unigram_coverage`, all gates green, and no whisker risk signals — exactly the cohort where **token-preserving semantic corruption** (table cell swap, math collapse) survives order-blind det (`whisker/CLAUDE.md`, `hybrid-llm-scoring/SYNTHESIS.md:22`). Merged verdict stays `pass` (`whisker_only`); operator sees no advisory row. **0 fleet hits** if corruption always trips a risk signal; **structurally exposed** if it does not.

## False-fail hypothesis

None on deterministic gate. Skipped papers omit tapetum sidecar → fusion `whisker_only` → merged equals det. No inflation of fail/review from absent LLM.

## Advisory lane viability

| Criterion | Assessment |
|-----------|------------|
| Gate / CI safety | **Pass** — lane never gates; det verdict unchanged |
| Fusion correctness | **Pass** — absent tapetum is first-class (`whisker_only`) |
| Advisory value | **Conditional fail** — loses 16/381-class merged flips and selection-gap coverage on skipped cohort |
| Cold 1-pod 600 s goal | **Insufficient alone** — ~250–350 s modeled; stacks with v11, deterministic metadata, unit predictor |
| Operator contract | **OK as opt-in tier** (`--det-skip` or `--profile nightly`); **not OK as default** replacing full run |

**Recommendation:** Viable for an **advisory speed tier** (nightly rollup where human triage is det-primary), not for the **default advisory lane** that justifies full-corpus LLM. After lane bump, prefer: (1) v11 metadata short-circuit (shipped), (2) deterministic metadata diff (AGGRESSIVE), (3) unit zero-defect predictor, (4) optional `--det-skip` on clean-pass only with explicit `coverage_mode: det_skip` in sidecar for audit.

---

## What would change my mind

1. Sidecar replay pinning **clean-pass count** and showing **0/48 holdout** verified-defect papers in that cohort would upgrade det-skip to **usable** for nightly cold.
2. Any holdout case where **only** full LLM (not det signals) caught a defect on a paper meeting proposed det-skip criteria would **kill** default use.
3. Combined cold run ≤600 s on one pod **without** det-skip would demote this lever to LATER.

---

## Sources

- `packages/whisker/src/whisker/tapetum_llm/cli.py` — run modes, fuse-only, incremental
- `packages/whisker/src/whisker/tapetum_llm/adjudicate.py` — `select_candidates`, HTML short-circuit
- `packages/whisker/src/whisker/tapetum_llm/pdf_judge.py` — metadata short-circuit, E-PDF-4
- `packages/whisker/src/whisker/tapetum_llm/fusion.py` — `whisker_only`
- `research/cold-run-10min/68-cascade-early-exit-map.md` — early-exit catalog
- `research/cold-run-10min/24-fusion-dead-reverify.md` — v11 partial skip verified
- `research/tapetum-llm-speedup/35-zero-defect-predictor.md` — unit skip only
- `research/hybrid-llm-scoring/SYNTHESIS.md` — selection gap, fusion matrix
