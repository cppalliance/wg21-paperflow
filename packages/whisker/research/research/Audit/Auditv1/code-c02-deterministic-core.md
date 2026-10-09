# C02 Deterministic Core Architect — Audit Report

**Persona:** C02 — Deterministic Core Architect
**Scope:** `packages/whisker/src/whisker/` (deterministic scoring path)
**Date:** 2026-07-19
**Verdict:** **PASS** (all four invariants hold)

---

## 1. Scoring Path Trace

```
score_paper(pid, backend)
  ├─ backend.get_paper_md(pid)           # read-only I/O
  ├─ check_paper_content(pid, backend)   # tomd lib, deterministic
  ├─ reference_markdown(pid, backend)    # markitdown (CPU, no LLM, no net)
  ├─ find_ideals_dir() → ideal_path()   # FS read, or None
  └─ score_markdown(pid, md_text, content=, reference_md=, ideal_md=)
       ├─ compute_metrics(md_text)       # tomd QA, pure
       ├─ run_gates(md_text)             # gates.py, pure
       ├─ text_nid(normalized_text(a), normalized_text(b))  # metrics.py, pure
       ├─ table_score(md_text, reference_md)                # bench.py, pure
       ├─ mhs(md_text, reference_md)                        # metrics.py, pure
       ├─ score_against_ideal(md_text, ideal_md)            # golden_ideals.py, pure
       └─ _decide(unigram_coverage, drift, missing, extra, qa, uncertain, gates, ref, ideal)
            └─ → (verdict, hard_flags, soft_flags)          # pure logic
```

Every function in the chain after I/O read is a pure function of its inputs.

---

## 2. Findings

### F01 — Metric purity: no randomness, no network, no LLM

- **Severity:** INFO
- **Claim:** All metric computations in `metrics.py`, `match.py`, `bench.py`, `gates.py`, `facts.py`, `golden.py`, `golden_ideals.py` are deterministic pure functions with no random state, no network calls, and no LLM invocations.
- **Evidence:**
  - `metrics.py` imports: `logging`, `re`, `Counter`, `deque`, `contextmanager`, `mistune`, `apted`, `lxml`, `pylatexenc`, `rapidfuzz` — all deterministic CPU libraries.
  - `match.py` imports: `re`, `numpy`, `rapidfuzz`, `scipy.optimize.linear_sum_assignment` — deterministic linear algebra.
  - `bench.py` imports: `grits`, `whisker.constants`, `whisker.match`, `whisker.metrics`, `whisker.tables` — all local pure modules.
  - `gates.py` imports: `re`, `dataclasses` — stdlib only.
  - `facts.py` imports: `json`, `re`, `rapidfuzz` — deterministic.
  - `golden.py` imports: `difflib`, `dataclasses`, `whisker.constants` — stdlib only.
  - `reference.py`: `MarkItDown(enable_plugins=False)` explicitly disables all plugins, network, and LLM.
  - Grep for `random|asyncio|aiohttp|httpx|requests\.` across all 7 core modules: **zero matches**.
- **Affected gate/dimension:** D1-D11 (determinism invariant)
- **Confidence:** HIGH
- **False-pass hypothesis:** A transitive dependency (e.g. `grits`, `scipy`) internally seeds a PRNG. Mitigated: `grits` uses numpy/pylcs (no RNG), `scipy.optimize.linear_sum_assignment` is the Jonker-Volgenant algorithm (deterministic).
- **False-fail hypothesis:** None identified.

---

### F02 — sorted() calls on unordered collections

- **Severity:** INFO
- **Claim:** All outputs derived from unordered collections (`hard_flags`, `soft_flags`, bench rows, `below_floor`) are sorted before serialization/return.
- **Evidence:**
  - `score.py:129-130`: `"hard_flags": sorted(self.hard_flags), "soft_flags": sorted(self.soft_flags)` in `WhiskerResult.to_dict()`.
  - `score.py:283`: `ordered = sorted(regions, key=lambda r: r.token_start)` for region detail.
  - `bench.py:211`: `return sorted(rows, key=lambda r: r.pid)` in `run_bench`.
  - `bench.py:247`: `below = sorted(r.pid for r in rows ...)` in `aggregate`.
  - `golden.py:151`: `"findings": [f.to_dict() for f in sorted(self.findings, key=lambda x: x.pid)]` in `GoldenReport.to_dict()`.
  - `golden.py:190`: `findings = [_evaluate(item) for item in sorted(items, key=lambda x: x.pid)]`.
  - `facts.py:595`: `neighbors.sort(key=lambda dv: _TABLE_DIRECTIONS.index(dv[0]))` — direction order is fixed.
- **Affected gate/dimension:** D7 (sort unordered collections before they feed a prompt or output)
- **Confidence:** HIGH
- **False-pass hypothesis:** A `set` used internally in `gates.py` (`keys`, `seen_plain`) is never serialized; it is only membership-tested (`k not in keys`), so iteration order is irrelevant. Same for `match.py` (`matched_gt`, `matched_pred`).
- **False-fail hypothesis:** None identified.

---

### F03 — Lane isolation: no cross-imports between lanes

- **Severity:** INFO
- **Claim:** Lane 1 (`golden.py`), Lane 2 (`metrics.py` / `match.py` / `bench.py` / `score.py`), and Lane 3 (`facts.py`) do not import each other. They share only `constants.py` (thresholds) and `tables.py` (grid parsing utility).
- **Evidence:**
  - `golden.py` imports: `difflib`, `dataclasses`, `whisker.constants`. No imports from `score`, `facts`, `metrics`, `bench`, `match`.
  - `facts.py` imports: `json`, `re`, `rapidfuzz`, `whisker.constants`, `whisker.metrics` (for `normalized_text`, `textblock2unicode` — the shared text normalizer), `whisker.tables`. No imports from `score`, `golden`, `bench`, `match`.
  - `score.py` does NOT import `golden.py` or `facts.py`. It imports `golden_ideals.py` (an advisory panel scorer, not Lane 1 stability logic).
  - Lane 1's `golden.py` is only called from `__main__.py` (`_golden_main`).
  - Lane 3's `facts.py` is only called from `__main__.py` (`_facts_main`, `_guard_main`, `_check_facts_main`).
  - Lane 2's `score.py` is called from `__main__.py` (`_score_main`, `_score_file_main`).
- **Affected gate/dimension:** Architectural invariant (lane independence)
- **Confidence:** HIGH
- **False-pass hypothesis:** `facts.py` imports `whisker.metrics.normalized_text` — is that a cross-lane coupling? No: `normalized_text` is a shared utility (text normalizer ported from OmniDocBench), not a Lane-2 scoring function. It is used by Lane 3 for its own surface mode.
- **False-fail hypothesis:** None identified.

---

### F04 — tapetum_llm isolation from core modules

- **Severity:** LOW (one edge case noted)
- **Claim:** No core module (`score.py`, `gates.py`, `metrics.py`, `match.py`, `bench.py`, `golden.py`, `facts.py`, `constants.py`, `golden_ideals.py`, `reference.py`) imports from `whisker.tapetum_llm`.
- **Evidence:**
  - Grep `import tapetum_llm|from whisker\.tapetum_llm` across all of `packages/whisker/src/whisker/`: matches are ONLY in `tapetum_llm/` subpackage files and `menu.py`.
  - `menu.py` uses a lazy import inside a function body (`from whisker.tapetum_llm.cli import main as tapetum_main`) gated behind interactive menu selection. `menu.py` is not a scoring module; it is a UI convenience invoked when `__main__.py` sees no CLI args on a tty.
- **Affected gate/dimension:** D1 (no LLM in the deterministic gate)
- **Confidence:** HIGH
- **False-pass hypothesis:** `menu.py`'s lazy import could be considered a violation. However: (a) `menu.py` is not in the scoring path (it is the interactive menu, never invoked during batch scoring), and (b) the import is guarded by user selection of the "tapetum" menu item. This is architecturally correct per the one-way isolation invariant documented in CLAUDE.md.
- **False-fail hypothesis:** None identified.

---

### F05 — Library returns data; only __main__.py writes files

- **Severity:** INFO
- **Claim:** All library modules (`score.py`, `gates.py`, `metrics.py`, `match.py`, `bench.py`, `golden.py`, `facts.py`, `golden_ideals.py`, `reference.py`) return data structures and never perform file writes. All `write_text`/`write`/`open` calls are in `__main__.py`.
- **Evidence:**
  - Grep for `write_text|\.write\(|open\(` across all 8 library modules: **zero matches** in `score.py`, `gates.py`, `metrics.py`, `match.py`, `bench.py`, `golden.py`, `facts.py`, `golden_ideals.py`.
  - `reference.py` reads the source file via `backend.get_source_path(pid)` and passes it to markitdown — it reads, never writes.
  - All `write_text` calls (11 occurrences) are in `__main__.py`: sidecar JSON, report.json, report.md, baseline, golden snapshots, facts report, calibration output.
- **Affected gate/dimension:** Invariant (library-returns-data; CLI owns persistence)
- **Confidence:** HIGH
- **False-pass hypothesis:** `reference.py` calls `_markitdown().convert(str(source_path))` which reads a file. This is a read (acceptable for a library function that processes inputs), not a write.
- **False-fail hypothesis:** None identified.

---

### F06 — Every threshold uses a named constant from constants.py

- **Severity:** INFO
- **Claim:** All scoring/gating thresholds in the deterministic path reference named constants from `whisker.constants`, with no bare numeric literals used as thresholds.
- **Evidence:**
  - `score.py:181`: `C.UNIGRAM_COVERAGE_FAIL_EDGE` (0.85)
  - `score.py:186`: `C.UNIGRAM_COVERAGE_REVIEW_EDGE` (0.95)
  - `score.py:190`: `C.REGION_SOFT_COUNT` (1)
  - `score.py:193`: `C.DRIFT_SOFT_EDGE` (0.10)
  - `score.py:195`: `C.QA_SCORE_SOFT_EDGE` (70)
  - `score.py:202`: `C.REF_NID_ADVISORY_EDGE` (0.85)
  - `score.py:209-213`: `C.NID_FLOOR`, `C.TEDS_FLOOR`, `C.MHS_FLOOR`, `C.CONTENT_RECALL_FLOOR`
  - `score.py:239`: `C.REGION_BENIGN_UNIGRAM_FLOOR` (0.95)
  - `score.py:287`: `C.REGION_DETAIL_CAP` (5)
  - `match.py:173`: `C.BLOCK_ACCEPT_NED` (0.70)
  - `match.py:195`: `C.BLOCK_FUZZY_MAX_PRED_LEN` (2000)
  - `match.py:198`: `C.BLOCK_FUZZY_RESCUE_NED` (0.40)
  - `match.py:253`: `C.BLOCK_MATRIX_CELL_BUDGET` (400_000)
  - `bench.py:250-253`: `C.NID_FLOOR`, `C.TEDS_FLOOR`, `C.MHS_FLOOR`, `C.CONTENT_RECALL_FLOOR`
  - Bare `0.0`/`1.0` in `match.py` and `bench.py` are identity/null accumulator values (perfect/zero similarity), NOT tunable thresholds.
  - Grep for `\b0\.\d+\b` in `score.py`: only a comment (line 221: `>= 0.95` explaining the fold). All actual comparisons use `C.*` constants.
- **Affected gate/dimension:** Invariant (thresholds are named constants)
- **Confidence:** HIGH
- **False-pass hypothesis:** The `3.0` divisor in `score.py:275` (`ref_overall = (ref_nid + ref_teds + ref_mhs) / 3.0`) is a structural count, not a tunable threshold.
- **False-fail hypothesis:** None identified.

---

### F07 — Gate results are deterministic and complete

- **Severity:** INFO
- **Claim:** `run_gates(md_text)` returns a fixed-order list of 6 gate results, each computed from text-only regex/string operations. No gate depends on external state.
- **Evidence:**
  - `gates.py:211-219`: `run_gates` returns a hardcoded list of 6 calls: `_gate_non_empty`, `_gate_front_matter`, `_gate_heading_monotone`, `_gate_no_empty_code`, `_gate_no_empty_table`, `_gate_no_toc_leak`.
  - Each gate is a pure function of `body` or `fm_lines` (derived by splitting the markdown text once).
  - `_iter_body_lines` tracks fence state with a boolean; its iteration is sequential over `body.splitlines()` (deterministic line order).
  - No file I/O, no imports beyond `re` and `dataclasses`.
- **Affected gate/dimension:** G1-G6 (all structural gates)
- **Confidence:** HIGH
- **False-pass hypothesis:** A markdown document with platform-specific line endings could produce different gate results. Mitigated: the only platform-sensitive part (CRLF) is handled upstream by `normalize_for_exact_lane` in golden and by `splitlines()` (which handles `\r\n`, `\r`, `\n` uniformly in Python).
- **False-fail hypothesis:** None identified.

---

### F08 — _decide() is a pure verdict function

- **Severity:** INFO
- **Claim:** The verdict function `_decide()` in `score.py` is a pure function of its numeric/list inputs. No side effects, no I/O, no mutation of external state.
- **Evidence:**
  - `score.py:136-231`: `_decide` accepts scalars and a list of `GateResult`, builds two local lists (`hard`, `soft`), applies threshold comparisons using named constants, and returns a tuple `(verdict, hard, soft)`.
  - No imports, no `self`, no global mutation, no logging.
  - The "benign-region fold" (`_is_benign_region_only`) is also pure: a string suffix check + float comparison against `C.REGION_BENIGN_UNIGRAM_FLOOR`.
- **Affected gate/dimension:** All (this is the verdict nexus)
- **Confidence:** HIGH
- **False-pass hypothesis:** If `gates` list were somehow order-dependent (it is not: `hard.append` iterates in list order, which is fixed by `run_gates`).
- **False-fail hypothesis:** None identified.

---

### F09 — menu.py tapetum_llm import boundary

- **Severity:** LOW
- **Claim:** `menu.py` performs a lazy conditional import of `whisker.tapetum_llm.cli` inside a function body, but this module is NOT on the scoring path and is only invoked interactively.
- **Evidence:** `menu.py:182,195`: `from whisker.tapetum_llm.cli import main as tapetum_main` inside `_run_tapetum()`. Called only when the user selects "tapetum" from the interactive Rich menu. Never loaded during `whisker --all`, `whisker bench`, `whisker guard`, `whisker golden`, `whisker facts`.
- **Affected gate/dimension:** D1 (no LLM in the deterministic path)
- **Confidence:** HIGH
- **False-pass hypothesis:** An accidental auto-import of `menu.py` at package init time. Verified: `whisker/__init__.py` does NOT import `menu`.
- **False-fail hypothesis:** Overly strict reading of "no tapetum_llm anywhere" ignoring architectural layering.

---

### F10 — `match.py` sets are membership-only (not iterated for output)

- **Severity:** INFO
- **Claim:** The `set[int]` variables in `match.py` (`matched_gt`, `matched_pred`) are used only for `in` membership checks, never iterated for output order. The fuzzy-rescue loop iterates `range()` (deterministic index order) and checks membership.
- **Evidence:**
  - `match.py:169-170`: `matched_gt: set[int] = set()`, `matched_pred: set[int] = set()`.
  - `match.py:183-184`: `matched_gt.add(r)`, `matched_pred.add(c)`.
  - `match.py:189-190`: `if r in matched_gt: continue` / `if c in matched_pred: continue` — pure membership; the iteration is over `range(len(gt_text))` and `range(len(pr_text))`, which is index-ordered.
  - Comment at line 188: "Scan in index order for determinism; first qualifying pred wins."
- **Affected gate/dimension:** D7 (unordered collections)
- **Confidence:** HIGH
- **False-pass hypothesis:** None; sets here encode "already matched" status, not ordering.
- **False-fail hypothesis:** None identified.

---

### F11 — `gates.py` sets are membership-only

- **Severity:** INFO
- **Claim:** The `set` in `_gate_front_matter` (`keys`) and `_gate_no_toc_leak` (`seen_plain`) are used only for `in`/`not in` membership checks, never serialized or iterated for output.
- **Evidence:**
  - `gates.py:63`: `keys = set()` — tested at line 70: `if k not in keys`.
  - `gates.py:156`: `seen_plain: set[str] = set()` — tested at line 171: `if stem in seen_plain`.
  - Neither set is returned or serialized. The gate returns a single `GateResult` (pass/fail + detail string).
- **Affected gate/dimension:** D7
- **Confidence:** HIGH
- **False-pass hypothesis:** None.
- **False-fail hypothesis:** None.

---

## 3. Summary Verdicts

| Invariant | Status | Evidence Strength |
|-----------|--------|-------------------|
| **Deterministic purity** | PASS | Zero RNG/network/LLM imports in all 8 core modules. All metrics are pure functions of text inputs. |
| **Lane isolation** | PASS | Lane 1 (`golden.py`), Lane 2 (`score.py`/`bench.py`/`metrics.py`/`match.py`), Lane 3 (`facts.py`) have no cross-imports. Shared utilities (`constants.py`, `tables.py`, `metrics.normalized_text`) are compute-only, never lane-specific logic. |
| **Library-returns-data** | PASS | All 8 library modules have zero `write`/`write_text`/`open` calls. All 11 write operations live in `__main__.py`. |
| **Named constants** | PASS | Every scoring threshold references a named constant from `constants.py`. Bare `0.0`/`1.0` in code are identity values, not tunables. |

---

## 4. Risks and Residuals

| Risk | Severity | Mitigation |
|------|----------|------------|
| `menu.py` has a lazy `tapetum_llm` import | LOW | Only reachable via interactive menu (no args + tty); never on the scoring path. Not imported at package init. |
| `reference.py` uses `@cache` on `_markitdown()` | LOW | Caches a single MarkItDown instance process-wide. Deterministic (same object, same behavior). No mutable cached state that could drift. |
| `match.py` `_ned_matrix` is O(n*m) | LOW | Capped by `BLOCK_MATRIX_CELL_BUDGET = 400_000` with documented fallback. |
| `pylatexenc` can theoretically hang on pathological input | LOW | Guarded by OmniDocBench's 3-layer ladder (`_likely_bad_latex`, `_looks_like_weak_latex_input`, `_looks_like_plaintext_formula_noise`) + `_MAX_LATEX_INPUT_LEN = 8000`. Documented shortcut comment in `metrics.py`. |

---

## 5. Methodology Notes

- All modules read in full via Read tool.
- Grep patterns verified across the entire `packages/whisker/src/whisker/` tree.
- Import graphs traced manually from the source.
- No tests were executed (this is a static code audit).
- Confidence calibration: HIGH = direct textual evidence, MEDIUM = inference from structure, LOW = assumption-dependent.
