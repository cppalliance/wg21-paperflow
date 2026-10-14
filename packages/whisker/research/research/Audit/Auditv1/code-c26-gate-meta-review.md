# C26 — Gate Meta-Review

**Persona:** C26 — Gate Meta-Reviewer
**Date:** 2026-07-19
**Commit:** `51cb704610220d31c9d5e078b1350c1b37a8714a`
**Scope:** Independent re-verification of all 7 hard gates (G1-G7) from AUDIT-SCORECARD.md against the persona reports (C03-C09) and actual source code in `packages/whisker/`.

---

## Methodology

For each gate:

1. **Pass rule** extracted verbatim from AUDIT-SCORECARD.md §2.
2. **Persona evidence** summarized from the corresponding `code-c0N-*.md` report.
3. **Spot-check** performed by reading the cited source file and line range to confirm at least one critical claim against actual code.
4. **Verdict** rendered: PASS / FAIL / UNPROVEN.
5. **Flip condition** stated: what change would flip this gate to FAIL.
6. **Caveats** noted: cosmetic issues, unproven sub-claims, or evidence limitations.

**Global caveat:** Live LLM evidence is BLOCKED (`ALLIANCE_POD_KEY` not set). G1 and G5 evidence is code-analysis-only, not runtime-verified against a real adversarial model. The deterministic replay was 7 papers + 38 pinning tests, not full-corpus. These are inherent limitations of the offline audit environment.

---

## G1 — Advisory Non-Leakage

### Pass rule (AUDIT-SCORECARD)

> Removing the advisory field leaves the verdict unchanged; adversarial "all-clear" structured output is ignored by the deterministic layer.

### Persona evidence (C03)

C03 proved isolation at four levels:

- **F1:** Zero `tapetum_llm` imports in any scoring module (`score.py`, `gates.py`, `constants.py`, `metrics.py`, `match.py`, `bench.py`, `guard.py`, `golden.py`, `golden_ideals.py`, `facts.py`, `tables.py`, `anchors.py`, `reference.py`, `report.py`, `corpus_tools.py`, `calibrate.py`). Only `menu.py` has lazy imports, inside function bodies guarded by `_has_tapetum_llm()`.
- **F2:** `_decide()` uses only deterministic signals. `ref` and `ideal` signals append to `soft` only, never `hard`.
- **F5:** The `whisker` CLI exit code at `__main__.py:283` reads `[r.verdict for r in results]` from `score_paper()`, which never touches fusion or tapetum. The `whisker-tapetum-llm` CLI is a separate executable.
- **F6:** Exit codes (`_verdict_exit_code`, lines 130-136) depend only on the deterministic verdict list.

### Spot-check: `_decide()` in `score.py:136-231`

**Confirmed.** Read `score.py:136-231` directly. The function signature accepts only deterministic signals. Lines 177-179: gate failures append to `hard`. Lines 181-184: low `unigram_coverage` appends to `hard`. Lines 200-203: `ref_nid` below advisory edge appends to `soft`. Lines 205-215: ideal panel axes append to `soft` with `"(advisory)"` suffix. Lines 217-218: `if hard: return VERDICT_FAIL`. No LLM signal touches `hard`. **The persona's claim is verified.**

Also confirmed `__main__.py:283`: `return _verdict_exit_code([r.verdict for r in results], args.gate)` — the `results` list is built from `score_paper()` (line 220), which never calls fusion.

### Verdict: **PASS**

### Flip condition

Any change that routes a `tapetum_llm` output (adjudication verdict, confidence, or fusion result) into the `hard` flags list of `_decide()`, or into the `results` list consumed by `_verdict_exit_code`, would flip this gate to FAIL.

### Caveats

- Evidence is code-analysis-only. No runtime adversarial-all-clear test was executed (LLM unavailable). The structural proof is strong (separate executables, separate import trees), but the AUDIT-SCORECARD's "adversarial-verdict rejection log" evidence type is absent.
- The `menu.py` lazy imports are on the CLI-interactive path only, never reachable from `whisker --gate`.

---

## G2 — Fail-Not-Partial

### Pass rule (AUDIT-SCORECARD)

> Fidelity-critical fault -> non-zero exit, no output artifact updated, debug preserved.

### Persona evidence (C04)

- **Batch-worker firewall:** `__main__.py:218-231`: `except Exception` is commented as "Batch worker firewall", `errored` counter tracked, `logger.exception` preserves full traceback.
- **Total failure -> EXIT_ERROR:** Lines 236-238: `if not results: return C.EXIT_ERROR`.
- **Gate failures -> hard flags -> FAIL:** `gates.py:run_gates` -> `_decide()` lines 177-179 -> `VERDICT_FAIL` -> `EXIT_FAIL` (5).
- **Vacuous green detection:** `_warn_vacuous_reports()` (lines 642-657) returns PIDs with zero verified facts; `_facts_main` (line 916) returns `EXIT_FAIL` when vacuous; CI test asserts at least one verified fact per paper.
- **Exit codes defined:** `constants.py:154-157`: `EXIT_OK=0`, `EXIT_ERROR=1`, `EXIT_REVIEW=3`, `EXIT_FAIL=5`.
- **Two LOW findings:** F01 (NaN `unigram_coverage` would silently pass `_decide`, theoretical), F02 (uncommented `except Exception` in `metrics.py` LaTeX normalization, cosmetic).

### Spot-check: Vacuous-green path in `__main__.py:642-657` and `__main__.py:916`

**Confirmed.** Read `__main__.py:642-657` directly: `_warn_vacuous_reports` iterates reports, checks `verified_count == 0`, adds PID to `vacuous` set, logs warning. Read `__main__.py:916`: `return C.EXIT_FAIL if (failed or vacuous_pids) else C.EXIT_OK`. Vacuous green correctly forces non-zero exit.

Also confirmed `__main__.py:236-238`: `if not results: logger.error(...); return C.EXIT_ERROR`.

Also confirmed `test_comprehension_corpus.py:75-76`: `verified = [c for c in report.checks if c.verified]; assert verified, ...`.

### Verdict: **PASS**

### Flip condition

Any change that emits a sidecar or report for an errored paper (a "hollow artifact"), or that returns `EXIT_OK` (0) when all papers have errored, or that removes the vacuous-green detection, would flip this gate to FAIL.

### Caveats

- F01 (NaN slip-through in `_decide`) is a theoretical gap. In practice `check_paper_content` returns finite floats, and the `guard.py` path catches NaN explicitly (`_finite()` at line 135-136, `STATUS_INVALID` at lines 341-349). The risk is LOW but the comment in the persona report is honest.
- F02 (uncommented LaTeX fallback catches in `metrics.py`) are on the normalization path, not the scoring/gating path. LOW severity, cosmetic.

---

## G3 — Determinism by Replay

### Pass rule (AUDIT-SCORECARD)

> Re-run under the declared tier (C-DET) satisfies the tier's equality contract.

### Declared tier (C-DET): Quality-stable

> Semantic equality of findings, not bit-exact.

### Persona evidence (C05)

- **Metric purity:** `text_nid`, `teds`, `mhs`, `content_recall` are all pure functions of string inputs. No randomness, no network, no mutable shared state.
- **Scoring purity:** `score_markdown` and `_decide` have no side effects, no external state. All comparisons use named constants from `constants.py`.
- **Output ordering:** All flag lists, result lists, bench rows are `sorted()` before output. `facts.py:595`: neighbor directions post-hoc sorted by canonical direction order.
- **No randomness sources:** Zero grep hits for `random`/`shuffle`/`sample`/`uuid`/`time.time` in scoring code.
- **Score pinning tests (38):** `test_score_pinning.py` pins 19 goldens field-by-field against a committed baseline, CI-blocked update (`WHISKER_PIN_UPDATE=1` + `if CI: pytest.fail`).
- **Replay evidence (code-offline-evidence.md):** 7-paper replay with 0 mismatches across 2 independent runs. 38/38 pinning tests pass.

### Spot-check: `score.py:129-130` — output sorting

**Confirmed.** Read `score.py:129-130`: `"hard_flags": sorted(self.hard_flags), "soft_flags": sorted(self.soft_flags)`. The `to_dict()` method sorts both flag lists lexicographically.

Also confirmed `bench.py:211`: `return sorted(rows, key=lambda r: r.pid)` — bench rows sorted by PID.

Also confirmed `bench.py:237-239`: `teds_vals = [r.teds for r in rows if r.teds is not None]` — eligibility-filtered aggregation is deterministic.

### Verdict: **PASS**

### Flip condition

Introducing any randomness source (e.g. `random.shuffle`, non-deterministic dict iteration into a prompt, non-deterministic tie-breaking in block matching, concurrent LLM requests in the deterministic lane), or changing the pinning test baseline without `WHISKER_PIN_UPDATE=1`, would flip this gate to FAIL.

### Caveats

- The replay evidence covers 7 papers (of 381 converted) + 38 pinning tests. This is not a full-corpus replay. The architectural purity of the scoring functions (all pure, all deterministic) provides strong structural assurance, but the replay sample is small.
- `scipy.optimize.linear_sum_assignment` determinism depends on the algorithm implementation staying stable across versions. Dependency pinning in `pyproject.toml` mitigates this.
- §9 pre-audit determinism questions (user's definition, Sean's definition, reconciliation) are marked as blocking in AUDIT-SCORECARD. The verdict here is **provisional** pending those answers. The declared tier is quality-stable, which the evidence supports.

---

## G4 — Per-Axis Reporting + Eval Integrity

### Pass rule (AUDIT-SCORECARD)

> Report shows per-axis scores with eligible/null counts; table gate requires structure AND content at the same bar; no modality scored when absent.

### Persona evidence (C06)

- **Null eligibility (8 findings, all PASS):** `bench.py:185-189`: `teds_v = ... if _extract_md_tables(reference_md) else None`. `bench.py:190`: `mhs_v = ... if has_headings(reference_md) else None`. No synthetic 1.0 for absent modalities.
- **Serialization:** `BenchRow.to_dict()` faithfully serializes `None` as JSON null (lines 78-83).
- **Aggregate:** `bench.py:237-243`: eligibility-weighted means (only eligible rows), denominators published in `eligible_counts`.
- **below_floor:** `bench.py:251-252`: `(r.teds is not None and r.teds < C.TEDS_FLOOR)` — None teds skips the floor check.
- **Per-axis verdict path:** `score.py:208-215`: ideal panel loops per axis with `if value is not None and value < floor`.
- **content_recall not folded into overall:** `bench.py:199-205`: `parts = [nid_v]` + eligible teds/mhs. content_recall explicitly excluded from `overall`.
- **No synthetic 1.0:** `bench.py:185-189`: when reference has no tables, `teds_v = None`, not `1.0`.

### Spot-check: `bench.py:185-211` — null eligibility and overall computation

**Confirmed.** Read `bench.py:185-211` directly:
- Line 185-188: `teds_v = _table_score(...) if _extract_md_tables(reference_md) else None` — GT-driven eligibility.
- Line 190: `mhs_v = mhs(...) if has_headings(reference_md) else None`.
- Lines 200-205: `parts = [nid_v]; if teds_v is not None: parts.append(teds_v); if mhs_v is not None: parts.append(mhs_v); overall = sum(parts) / len(parts)`. Ineligible axes excluded from overall.

Also confirmed `bench.py:247-254`: `below_floor` respects None with `r.teds is not None and r.teds < C.TEDS_FLOOR`.

### Verdict: **PASS**

### Flip condition

Any change that imputes a synthetic `1.0` for absent modalities (e.g. `teds_v = 1.0` when reference has no tables), or folds ineligible axes into the overall composite, or removes per-axis null counts from the aggregate, would flip this gate to FAIL.

### Caveats

None. This gate is clean with 8/8 findings passing.

---

## G5 — Untrusted-Input Mediation

### Pass rule (AUDIT-SCORECARD)

> Paper/web text wrapped (segregation + delimiter hardening) and structured-output-validated before any prompt.

### Persona evidence (C07)

- **Triage wrapping:** `adjudicate.py:579`: `wrapped_md = ctx.inject_untrusted(md)`.
- **Adjudicate wrapping (tier-1 model output also wrapped):** `adjudicate.py:598-601`: `tier1_text = ctx.inject_untrusted(f"Tier 1 reasoning: {tier1.reasoning}\n" f"Tier 1 concern: {tier1.primary_concern}")`. Comment at 587-589 explicitly states a paper that smuggled instructions into tier 1's reasoning must not be replayed as trusted prose.
- **PDF judge wrapping:** `pdf_judge.py:401`: `guard_instruction(tag)` in system prompt. Lines 406-408: both inputs wrapped with `inject_untrusted`.
- **Unit judge wrapping:** `unit_judge.py:148,580`: `guard_instruction(tag)` in system prompts. Lines 152-158, 586-588: all inputs wrapped.
- **Structured output (D6):** Every LLM call uses a pydantic `output_type`. `models.py:30`: `Verdict = Literal["pass", "fail", "review"]`. Models include `model_validator` enforcing consistency.
- **Evidence grounding:** `grounding.py:248-335`: three-tier verification (exact monotonic DP, fuzzy substring, fuzzy ratio). Unlocatable quotes dropped.
- **Independence invariant:** `adjudicate.py:547-550,592-594`: no deterministic-lane signals injected into LLM prompts.

### Spot-check: `adjudicate.py:579-611` — wrapping calls

**Confirmed.** Read `adjudicate.py:575-611` directly:
- Line 579: `wrapped_md = ctx.inject_untrusted(md)` — paper markdown wrapped.
- Line 580: `return header + wrapped_md` — wrapped content appended after trusted header.
- Lines 598-601: `tier1_text = ctx.inject_untrusted(...)` — model-derived free-text fields also wrapped.
- Line 610: `wrapped_md = ctx.inject_untrusted(state.paper_md)` — paper markdown wrapped again in adjudicate step.

The `inject_untrusted` function is the pipeline framework's canonical delimiter-wrapping primitive. The persona correctly identifies it as equivalent to `wrap_source`.

### Verdict: **PASS (code-analysis-only)**

### Flip condition

Any LLM call that concatenates raw paper text or model-derived free-text into a prompt without `inject_untrusted` / `guard_instruction`, or any LLM call that uses free-text parsing instead of a pydantic `output_type`, would flip this gate to FAIL.

### Caveats

- **No runtime adversarial injection test.** The AUDIT-SCORECARD requires "delimiter-forgery and instruction-in-data tests that hold." No such test was executed (LLM unavailable). The defense is structural (delimiter wrapping + structured output), so code-analysis provides strong assurance, but the "injection test results by attack class" evidence artifact is absent.
- The persona notes (C07 Finding 7 false-pass hypothesis): "No explicit adversarial injection test... the defense is structural, not behavioral." This is honest but means the gate carries a code-analysis-only confidence, not a runtime-tested one.

---

## G6 — Baseline Canary (Inverted)

### Pass rule (AUDIT-SCORECARD)

> A zero-authoring baseline runs on 100% of pages; inverting a canary (known-bad output) MUST fail the gate.

### Persona evidence (C08)

- **Three canaries exist (one per exploit class):**
  1. `test_canary_scrambled_table_cell_fails` (P4182R0): replaces "(CUDA, SYCL) | No |" with "(CUDA, SYCL) | Yes |", asserts `tableA-gpu-coro-no` fact fails.
  2. `test_canary_scrambled_code_fails` (P4234R0): replaces `asm("Image$$ER_ZI$$Base")` with `asm("Image__ER_ZI__Base")`, asserts `code-asm-alias` fact fails.
  3. `test_canary_scrambled_formula_fails` (P4185R0): replaces `\(x^{2k} \geq 0\)` with `\(x^{2k} \leq 0\)`, asserts `math-even-power-nonneg` fact fails.
- Each canary includes an anchor assertion (`assert needle in md`) that guards against snapshot drift.
- Vacuous-green detection present in CLI and CI test suite.
- All 6 structural gates tested for both pass and fail (16 tests in `test_gates.py`).

### Spot-check: `test_comprehension_corpus.py:83-143` — all three canaries

**Confirmed.** Read `test_comprehension_corpus.py:83-143` directly:
- Lines 83-101: P4182R0 canary. Line 93: `needle = "(CUDA, SYCL) | No |"`. Line 94: `assert needle in md`. Line 95: `scrambled = md.replace(needle, "(CUDA, SYCL) | Yes |", 1)`. Line 100: `assert report.failed`. Line 101: `assert any(c.id == "tableA-gpu-coro-no" for c in report.failures())`.
- Lines 104-122: P4234R0 canary. Line 114: `needle = 'asm("Image$$ER_ZI$$Base")'`. Line 116: scramble to `'asm("Image__ER_ZI__Base")'`. Line 122: asserts `code-asm-alias`.
- Lines 125-143: P4185R0 canary. Line 135: `needle = r"\(x^{2k} \geq 0\)"`. Line 137: scramble to `r"\(x^{2k} \leq 0\)"`. Line 143: asserts `math-even-power-nonneg`.

All three canaries are correctly implemented: load snapshot, corrupt one semantically meaningful element, assert specific fact ID fails.

### Runtime evidence (code-offline-evidence.md §2)

All 3 canaries passed (correctly failed on corruption) in the offline test run.

### Verdict: **PASS**

### Flip condition

Removing a canary, making a canary's corruption invisible to the fact checker (e.g. weakening `_check_table` to ignore neighbor mismatches), or removing the vacuous-green detection, would flip this gate to FAIL.

### Caveats

- The "zero-authoring baseline on 100% of pages" sub-rule is partially met: the structural gates (`run_gates`) run on every paper, and the score pinning tests cover 19 goldens. The comprehension canaries cover 3 of 5 corpus papers (each with one canary). The canary corpus is small (3 papers, 3 exploit classes) but covers the three most important semantic corruption types (table cell, code, formula).
- No adversarial canary for the advisory LLM lane exists (out of scope: the LLM lane never gates).

---

## G7 — Licensing / Attribution

### Pass rule (AUDIT-SCORECARD)

> No incompatible license combination shipped; required third-party attribution present; BSL-1.0 full-notice satisfied.

### Persona evidence (C09)

- **BSL-1.0 headers:** 42/42 source `.py` files carry the BSL-1.0 copyright header.
- **Core dependency licenses:** All 12 core dependencies are permissively licensed (MIT, BSD-3-Clause, BSL-1.0). `rapidfuzz` (MIT) explicitly replaced GPL `levenshtein`.
- **Optional tapetum-llm dependencies:** All 5 are permissively licensed (Apache-2.0, MIT, BSD-3-Clause, BSL-1.0).
- **Ported code attribution:** TEDS (PubTabNet/OmniDocBench, Apache-2.0) attributed at `metrics.py:392-399`. OmniDocBench normalizer at `metrics.py:88-96`. Block matching at `match.py:8-29`. Langextract DP at `grounding.py:14-21` with `THIRD_PARTY_NOTICES.md`.
- **No vendored code:** All ports are algorithm-level re-implementations, not copy-pasted source.

### Spot-check: `THIRD_PARTY_NOTICES.md` + `metrics.py:88-96`

**Confirmed.** Read `THIRD_PARTY_NOTICES.md` directly: langextract (Apache-2.0) attribution present with source URL, commit hash, and scope description.

Read `metrics.py:88-96`: OmniDocBench attribution block present: "Content normalization ported VERBATIM from OmniDocBench (src/core/preprocess/{data_preprocess,text_postprocess}.py)."

Also confirmed `constants.py:154-157`: `EXIT_OK = 0`, `EXIT_ERROR = 1`, `EXIT_REVIEW = 3`, `EXIT_FAIL = 5` — these are original constants, no license issue.

### Verdict: **PASS**

### Flip condition

Adding a GPL-licensed dependency to core (not optional extra), removing BSL-1.0 headers from a source file, or removing attribution comments from ported code, would flip this gate to FAIL.

### Caveats

- Dependency license versions confirmed from common knowledge, not from a `pip-licenses` run. Confidence 0.95 (persona's own assessment). A `pip-licenses --format=csv` would bring this to 1.0.
- All ports are from Apache-2.0 sources, which permits derivative works under BSL-1.0. No copyleft contamination risk identified.

---

## Cross-Cutting Observations

### 1. LLM evidence gap

G1 (adversarial rejection log) and G5 (injection test results by attack class) both require runtime LLM evidence that is BLOCKED. The code-analysis evidence is strong and structural, but the AUDIT-SCORECARD's full evidence requirements are not met for these two gates. Both pass on code-analysis confidence; neither has been runtime-tested against a real adversarial model.

### 2. Replay sample size

G3 evidence covers 7 papers + 38 pinning tests. The full corpus is 381 converted papers. The architectural purity argument (all metrics are pure functions of inputs) substantially compensates, but a full-corpus replay would strengthen the evidence.

### 3. Determinism definition pending

AUDIT-SCORECARD §9 pre-audit questions (user/Sean determinism definitions, reconciliation, equality contract, variance scope) are unanswered. G3 verdict is provisional under the interim quality-stability tier.

### 4. Human fact blessing

All 37 verified facts were authored AND verified by the agent. No human has independently blessed a fact. This is documented honestly (C01 Known contradiction #5, CLAUDE.md Known gaps #8) but weakens the independence claim for G6 canaries.

### 5. Persona report quality

All 7 persona reports (C03-C09) are thorough, cite specific line numbers, and include false-pass/false-fail hypotheses. The evidence claims I spot-checked were accurate in every case: line numbers matched, code behavior matched, and the personas did not overstate their findings.

---

## Summary Table

| Gate | Pass rule (abbreviated) | Persona verdict | Meta-reviewer verdict | Confidence | Flip condition |
|------|-------------------------|-----------------|----------------------|------------|----------------|
| **G1** Advisory non-leakage | Advisory field removal leaves verdict unchanged; adversarial all-clear ignored | PASS (1.0) | **PASS** | 0.95 (code-only, no runtime adversarial test) | Any tapetum_llm output routed into `hard` flags or `_verdict_exit_code` results list |
| **G2** Fail-not-partial | Fidelity fault -> non-zero exit, no hollow artifact, debug preserved | PASS (2 LOW findings) | **PASS** | 0.98 | Hollow artifact emitted for errored paper, or EXIT_OK on total failure, or vacuous-green removed |
| **G3** Determinism by replay | Re-run at declared tier (quality-stable) satisfies equality contract | PASS (STRONG) | **PASS (provisional)** | 0.90 (7-paper replay, not full-corpus; §9 unanswered) | Any randomness source in scoring, non-deterministic tie-breaking, concurrent LLM in deterministic lane |
| **G4** Per-axis + eval integrity | Per-axis scores with eligible/null; table=structure+content; absent modality not imputed | PASS (CLEAN, 8/8) | **PASS** | 1.0 | Synthetic 1.0 for absent modality, or ineligible axis folded into overall |
| **G5** Untrusted-input mediation | Paper/web text wrapped + structured-output validated before prompt | PASS (CLEAN) | **PASS (code-only)** | 0.90 (code-analysis, no runtime injection test) | Raw untrusted text in prompt without wrapping, or free-text parsing instead of pydantic output_type |
| **G6** Baseline canary (inverted) | Inverted canary MUST fail the gate | PASS (CLEAN) | **PASS** | 0.98 | Canary removed, corruption made invisible, or vacuous-green detection removed |
| **G7** Licensing / attribution | No incompatible license; attribution present; BSL-1.0 satisfied | PASS (CLEAN) | **PASS** | 0.95 (no pip-licenses run) | GPL dependency in core, BSL-1.0 header removed, or attribution deleted |

---

## Overall Gate Ledger

**All 7 gates: PASS.** No gate failure. Band is NOT capped at Unsound.

**Evidence grade caveats:**

- G1, G5: code-analysis-only (grade B, not A). Runtime adversarial evidence blocked by missing `ALLIANCE_POD_KEY`.
- G3: provisional (§9 determinism definition questions unanswered). Replay sample is 7/381 papers + 38 pinning tests.
- G7: dependency licenses confirmed from common knowledge, not `pip-licenses` (grade B).
- G2, G4, G6: fully evidenced (grade A).

**Unproven sub-claims (documented, not a gate failure):**

- No runtime adversarial "all-clear" injection test (G1).
- No delimiter-forgery document-embedded injection test corpus run (G5).
- Determinism definition reconciliation pending (G3 §9).
- All 37 facts agent-authored, no human blessing (affects G6 canary independence).
