# 13 - Score Fusion Architect

**Verdict:** usable-with-conditions (+ a conservative det-primary escalation matrix is implementable today from existing sidecars without violating C1/C2, but it must cap LLM influence at `review` when whisker is not already `fail`, and it must not invent a gate-mode numeric composite the deterministic lane never defined.)
**Confidence:** high

## Findings

- [CRITICAL] The 2026-07-06 run shows **123/194 (63%) tapetum adjudications disagree** with the whisker verdict on record (`00-baseline.md:49`), so any fusion rule that treats LLM and deterministic lanes symmetrically (worst-of, naive 3×3 fail cells, confidence-weighted blend) will fight the CI contract daily. Impact: goal 3 must encode **asymmetric** fusion (deterministic primary, LLM modifier), not democratic averaging.
- [CRITICAL] Gate-mode whisker has **no numeric composite score**; `_decide` returns a trichotomy verdict from hard/soft flags only (`score.py:118-184`), and the only true `overall` mean lives in `bench.py` (`00-baseline.md:23-24`). Impact: candidate **(b) confidence-weighted numeric composite** has no honest deterministic operand unless you invent a new scalar (breaking the "verdict = rules, NOT a score" design at `score.py:10-17`).
- [HIGH] Tapetum already implements the fusion grammar we need: **severity-aware worst-axis fold** (`chunking.py:106-123`, only `fail`+`major` forces overall fail) and **never-upgrade demotions** (`adjudicate.py:279-285`, ungrounded or sub-floor confidence stays `review`). Impact: merged logic should reuse these predicates (`has_major_fail(axis_findings)`, `confidence >= CONFIDENCE_DECISION_FLOOR` at `constants.py:45`) rather than re-deriving verdict semantics.
- [HIGH] C2 forces merge code into **`tapetum_llm` (or a sidecar reader beside it), never `score.py`**: core must not import the LLM lane (`00-baseline.md:39`, `CLAUDE.md:408-409`). Impact: recommended home is `packages/whisker/src/whisker/tapetum_llm/fusion.py` with `fuse_sidecars(whisker: dict, tapetum: dict | None) -> FusionResult`; CLI persistence via an extended `whisker-tapetum-llm --fuse` or post-run hook in `cli.py:207-217`, keeping `WhiskerResult.verdict` untouched (`score.py:93`).
- [HIGH] **Absent/errored LLM lane is common**: 6/200 candidates produced no usable tapetum sidecar in the run (`00-baseline.md:51`), and `adjudicate_paper` returns a zero-confidence stub when the pipeline fails (`adjudicate.py:490-501`). Impact: fusion must branch on `tapetum_available: bool`; when false, `combined_verdict == whisker_verdict` and `combined_rule == "whisker_only"` (no synthetic LLM pass).
- [MED] The inspect report already formalizes the display join: **`agree` vs `DIFFERS`** on `(whisker.verdict, tapetum.suggested_verdict)` (`inspect_report.py:55-56`, header counts at `inspect_report.py:125-129`). Impact: candidate **(e) display-only** partially exists; goal 3 adds a third **`combined_verdict`** column derived by rule, not another side-by-side string.
- [MED] Candidate **(c) worst-of** on raw verdicts violates C1 spirit: tapetum `suggested_verdict=fail` on a whisker `pass` would become combined `fail`, effectively letting the LLM gate despite the advisory flag (`models.py:135`, `CLAUDE.md:369-371`). Impact: worst-of is usable only after the same **major-severity fold** as `worst_axis_verdict` and a **fail ceiling** (combined `fail` iff whisker already `fail`).
- [LOW] Persisted tapetum sidecars already carry join keys: `whisker_verdict`, `suggested_verdict`, `confidence`, `axis_findings`, `advisory: true` (`models.py:114-136`, `cli.py:212`). Impact: goal 2 persistence can stay as two files plus a third `<pid>.fusion.json` (or a `fusion` block in `report.json`) without bumping `WHISKER_SCHEMA_VERSION` (`constants.py:166`).

### Fusion candidate evaluation (C1 + 2026-07-06 numbers)

| Candidate | C1 safe? | LLM absent/6 errors | Determinism | Pure sidecar join? |
|---|---|---|---|---|
| **(a) 3×3 verdict matrix** | Yes **if** fail row/column locked to whisker `fail` and LLM-only fail maps to `review` | Falls back to whisker-only row | Fully deterministic given static matrix + sorted inputs | Yes |
| **(b) Confidence-weighted composite** | Risky: a numeric threshold becomes a shadow gate | Degrades to det-only scalar (must pick `ref_overall` or `unigram_coverage`) | Deterministic but **uncalibrated** (123 disagreements) | Yes, but operands are mismatched (verdict vs float) |
| **(c) Worst-of / best-of** | Worst-of **breaks C1** unless capped; best-of creates false passes | Worst-of(det) = det; best-of inflates passes | Deterministic | Yes |
| **(d) Det primary + modifier arrows** | **Native C1 pattern** (`inspect_report.py:56`) | Modifier `no_advisory` | Deterministic | Yes |
| **(e) Display-only merge** | Safest | Trivial | Deterministic | Yes (no merged verdict field) |

### Recommended design: conservative escalation matrix (d + a)

**Rule (one sentence):** `combined_verdict` equals whisker `verdict` unless tapetum is present and strictly more severe, in which case escalate **at most one step to `review`**, never to `fail` unless whisker is already `fail`; apply tapetum's major-severity fold before comparing.

**Concrete fields (`FusionResult.to_dict()`):**

```json
{
  "schema_version": 1,
  "pid": "P4003R0",
  "whisker_verdict": "review",
  "tapetum_verdict": "fail",
  "tapetum_available": true,
  "tapetum_has_major_fail": true,
  "tapetum_confidence": 0.95,
  "advisory_delta": "llm_more_severe",
  "combined_verdict": "review",
  "combined_rule": "llm_escalate_major",
  "advisory": true
}
```

**Decision table (after mapping tapetum `fail`+non-`major` → effective `review` per `chunking.py:117-120`):**

| whisker \ tapetum (effective) | pass | review | fail/major |
|---|---|---|---|
| pass | pass / `agree` | review / `llm_escalate` | review / `llm_escalate_major` |
| review | review / `llm_lenient` | review / `agree` | review / `llm_escalate_major` |
| fail | fail / `whisker_fail_locked` | fail / `whisker_fail_locked` | fail / `whisker_fail_locked` |

**Code placement:** `packages/whisker/src/whisker/tapetum_llm/fusion.py` (pure join + rule engine); `packages/whisker/src/whisker/tapetum_llm/fusion_report.py` (optional markdown/terminal columns mirroring `inspect_report.py`); persist `<pid>.fusion.json` beside `<pid>.whisker.json` and `<pid>.whisker.tapetum.json` from tapetum CLI (`cli.py:207-217`). **Do not** write `combined_verdict` back into `<pid>.whisker.json` (C1/C4). Extend `report.md` with columns `whisker | tapetum | combined | delta` in the tapetum inspect path, not in `whisker --gate` output.

**Numeric display (optional, non-gating):** show whisker `ref_overall` (or `unigram_coverage` when `ref_overall` is null, `score.py:106-109`) and tapetum `confidence` (`models.py:120`) as **separate lanes**; do not multiply them into a merged score (anti-pattern documented at `constants.py:66-67`, `CLAUDE.md:254-255`).

## False-pass hypothesis

Whisker `pass` on a PRIMARY false-pass candidate (e.g. table row/cell swap with high `unigram_coverage`) that was **never sent to tapetum** because it lacks `lossy_table_count`/`table_parse_errors`/gap signals (`adjudicate.py:101-113`, `select_candidates` PRIMARY definition at `adjudicate.py:86-88`): fusion returns `combined_verdict=pass` / `combined_rule=whisker_only` while semantic corruption remains. The 76-paper row-swap attack (74 pass) cited in `tapetum-llm-decision-synthesis.md:29-30` is the concrete case.

## False-fail hypothesis

Whisker `fail` on heading-monotone-only hard flag (`adjudicate.py:128-134`, RESCUE population) with tapetum `suggested_verdict=pass` after severity fold: recommended matrix keeps `combined_verdict=fail` / `whisker_fail_locked`, so the merged lane **cannot** rescue the paper even when the LLM disagrees. Example shape: whisker fail + tapetum pass → combined fail (human must use tapetum inspect, not fusion, for rescue signal).

## What would change my mind

A labeled calibration set (≥30 papers with human gold verdicts) showing that **LLM-major-fail on whisker-pass** cases achieve ≥90% precision for true semantic defects *and* that lifting the fail ceiling (allowing combined `fail` without whisker `fail`) improves F1 without increasing CI false-fail rate—none of which exists today (`constants.py:11-15`, `00-baseline.md:44-45`).
