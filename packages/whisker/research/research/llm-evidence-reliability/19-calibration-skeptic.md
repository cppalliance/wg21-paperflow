# 19 - LLM-Judge Calibration Skeptic

**Verdict:** usable-with-conditions — prompt tweaks, confidence, self-consistency, NLI, and reruns cannot fix the 40% quote-evidence precision crisis; only a deterministic candidate-side check (olmOCR-style) can, and every other "calibration" upgrade is feature creep until that ships.
**Confidence:** high

## Findings

- [CRITICAL] **The evidence failure is a verification gap, not a calibration gap.** Nine-PR replay: 20 PDF-judge "missing-content" quotes, **8/20 genuinely absent (40% precision)**; PR #285 and #290 were 0/5 false absences (`llm-evidence-reliability/00-baseline.md:11-24`). Code proves source presence only: `ground_spans(spans, pdf_text)` at `pdf_judge.py:513-520`, then sidecar labels every quote `"present in PDF text layer, absent from markdown"` (`pdf_judge.py:401-404`) without ever calling `ground_spans` on candidate markdown. Impact: no amount of prompt engineering, confidence tuning, or rerun consensus repairs a label that overstates what was mechanically verified; the fix is Tier-2 candidate locate, not Tier-3 judge psychology.

- [CRITICAL] **Absence detection is structurally weak in LLMs; the ecosystem routes around it.** AbsenceBench (arxiv:2506.11440) reports strong models fail surface-form absence even with both documents in context (`llm-evidence-reliability/05-web.md / Q1 / AbsenceBench`). olmOCR-Bench uses deterministic `TextPresenceTest` for both `PRESENT` and `ABSENT` (`05-web.md / Q1 / olmOCR-Bench`). LitRAG and Ragas locate quotes deterministically before any LLM support judgment (`05-web.md / Q2`). Impact: treating the judge's absence claim as evidence without candidate-side falsification repeats a known failure mode; calibration layers on top of an unverified absence claim compound false precision.

- [HIGH] **Prompt changes improve verdict triage, not quote precision.** PR rerun human agreement rose 4/9 → 7/9 after det `no_toc_leak` + TOC prompt rule; **four new hard fails were all deterministic** (`llm-qa-integration/00-baseline.md:61-66`). PR #282 still false-cleared at confidence 1.00 with HTML outline injected (`opus-B-llm-calibration.md:45`, `golden-qa-gap/00-baseline.md:63`). Marker rubric + image grounding (P20) targets blind spots the text layer cannot see (`20-llm-judge-scholar.md:8-12`), not the "quote already in markdown" class that drove 12/20 false absences. Impact: prompt budget is worth spending on axis rubrics and vision for advisory verdict recall; it is **not** a substitute for candidate `ground_spans(tomd_md)` on missing-content quotes.

- [HIGH] **Confidence is anti-calibrated and inert for evidence policy.** Production: min 0.85–0.90, median 0.95, 0/381 below `CONFIDENCE_DECISION_FLOOR` (0.50), 0/381 in ambiguous band `[0.35, 0.65]` (`17-calibration-statistician.md:8-16`, `opus-B-llm-calibration.md:41-43`). `llm_clear_soft_review` fired 96/381 times, **all at confidence ≥ 0.95** (`opus-B-llm-calibration.md:42`). Escalation already moved to derived signals (`SIGNAL_AXIS_CONFLICT`, `SIGNAL_UNGROUNDED_EVIDENCE`; `adjudicate.py:232-253`) because the scalar band never fired. Impact: refitting confidence, TH-Score, or ECE (`05-web.md / Q2 / Overconfidence in LLM-as-a-Judge`) changes sidecar cosmetics, not whether a quote is present in markdown; **300+ labeled decisions** needed for publishable calibration (`17-calibration-statistician.md:49`) with zero expected lift on candidate-absence precision.

- [HIGH] **Self-consistency and multi-run reruns are the wrong tool and the wrong cost.** D5 forbids per-call temperature override; repo targets quality-stability, not vote aggregation (`CLAUDE.md` Determinism; `20-llm-judge-scholar.md:16-17`). Empirical: identical 20-PID reruns shifted pass/review histogram **5/20 (25% lower bound on flips)** under same concurrency (`opus-B-llm-calibration.md:46`, `llm-batching/20-sweep-results.md:31-40`). `05-web.md / Q2 / Necessary but Not Sufficient`: temp=0 reduces but does not eliminate grader disagreement; multi-sample averaging raises human correlation at the cost of variance and determinism. Impact: k-run self-consistency would cost **k× serial judge calls per paper** (D11), increase flake without verifying candidate absence, and cannot fix quotes that are **already present** under normalized substring match.

- [MED] **NLI is a deferred resolver for `ambiguous`, not a first-fix.** Web synthesis ranks NLI (RefChecker, verifiable-rag) as resolver for semantic equivalence only after deterministic locate (`llm-evidence-reliability/05-web.md / Q3 / RefChecker`, `:180-194`). Whisker already has stdlib+fuzzy tiers (`grounding.py:171-241`); adding NLI introduces a **second model dependency**, sovereignty surface, and non-determinism on the evidence path. Impact: NLI might help dehyphenation/reformat cases routed to `ambiguous`; it does **nothing** for the dominant replay failure mode (verbatim prose present in markdown, falsely quoted as missing).

- [MED] **Feature creep inventory vs minimal fix (cost table).**

  | Upgrade | Marginal LLM cost | Expected evidence-precision lift | Falsifier (drop if…) |
  | --- | --- | --- | --- |
  | **Candidate-side `ground_spans` + honest labels** | **0×** (reuse existing tiers on `tomd_md`) | 40% → **≥85%** on 20-quote replay (12 FP removed) | Holdout precision **<80%** after fuzzy/markdown-normalize tier |
  | Prompt/rubric/TOC/vision | 1× (+ optional image per escalated page) | Verdict recall; **~0** on quote FP class | A/B replay: false-absent count unchanged |
  | Confidence calibration fit | 0 LLM; **30–50+ human labels** (~300 for ECE) | **0** on quote precision | Bins still flat after fit |
  | Self-consistency (k=3) | **3×** judge calls | Unknown; breaks D5 contract | k-run majority absent ⊆ single-run absent on labeled quotes |
  | NLI on ambiguous quotes | **+1 call/quote** (or batch) | Small on reformatted-only subset | NLI FP rate **>** det fuzzy alone on holdout |
  | Rerun-until-agree | **2–20×** | Reduces verdict flake, not quote truth | Duplicate run still emits same false absent with source-only grounding |

  Impact: any roadmap item above the first row is **scope creep** until candidate-side verification ships and evidence precision is re-measured.

- [LOW] **Inspect already partially debiases confidence theater.** `inspect_report.py:67` labels confidence "self-reported, uncalibrated" (opus-B action #1). Impact: further UX honesty (drop decimal, per-quote `source: exact|fuzzy`, `candidate: present|absent|ambiguous`) costs near zero and prevents operators from trusting 0.95 on a false-absent quote.

## False-pass hypothesis

PR #285 replay: judge emits five "missing" date lines, all already present in markdown (some twice) (`00-baseline.md:17-18`). Source-only grounding keeps all five as `"present in PDF text layer, absent from markdown"` (`pdf_judge.py:401-404`). Prompt edits, confidence demotion, or a third rerun do not re-read markdown; only a candidate locate that returns `present` would demote or drop them. Self-consistency makes it worse if 2/3 runs agree on the same hallucinated absence.

## False-fail hypothesis

PR #293: five `constexpr` quotes genuinely absent; candidate-side check correctly retains `absent` (`00-baseline.md:19`). Aggressive normalized-only candidate matching (the only matcher without a guard) could false-fail if declarations survive as HTML/code-fence reformats. Mitigation: exact → normalized → fuzzy tier ladder with explicit `ambiguous` abstention (`05-web.md / Q5 / CRAG`), not NLI as gate zero.

## What would change my mind

A labeled quote holdout (≥50 quotes, human `{absent, present, reformatted}` on source+candidate pairs) where **prompt-only + confidence floor + 3-run self-consistency** beats **single-run LLM + two-sided deterministic verify** on evidence precision at equal or lower total LLM cost. No published result in the llm-qa-integration or llm-evidence-reliability baselines suggests that outcome; AbsenceBench and olmOCR precedent predict the opposite.

### Anti-creep policy (ranked)

1. **Ship candidate-side verify first** (~reuse `ground_spans` / `ground_page_quotes` on markdown; olmOCR `TextPresenceTest` parity). Re-run 20-quote replay; target **≥85% precision**, report evidence F1 separate from verdict agreement (ALCE pattern, `05-web.md / Q2 / ALCE`).
2. **Defer** formal confidence calibration (P17), NLI resolver (P21), and self-consistency until post-fix precision is measured; none address the dominant FP class.
3. **Allow** prompt/rubric/vision upgrades only under advisory verdict recall, with explicit non-goal: "does not replace candidate verify."
4. **Reject** binding evidence acceptance, CI gates, or fusion weighting on LLM-reported confidence or rerun consensus (`11-product-decision-skeptic.md:20`, `opus-B-llm-calibration.md:85-91`).
