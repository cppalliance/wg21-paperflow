VERDICT: KEEP-AS-IS - OmniDocBench parity; levenshtein already paid for and fast.

# BUILD-vs-BUY: full-text edit distance / NID core

Capability: **character-level Levenshtein distance**, normalized as `distance / max(len(a), len(b))`, composed into `text_nid = 1 - NED` after OmniDocBench text-axis normalization.

Constraints applied: deterministic, no LLM, minimalism ladder, permissive license (noted tension), Python >=3.12, library returns data.

---

## 1. Current state

| Symbol | File | Role |
|--------|------|------|
| `normalized_edit_distance` | `packages/whisker/src/whisker/metrics.py:172-185` | Core NED: `Levenshtein.distance(a,b) / max(len(a),len(b))`; both-empty → `0.0`. |
| `text_nid` | `packages/whisker/src/whisker/metrics.py:450-457` | `1 - normalized_edit_distance(_normalize_text(a), _normalize_text(b))`; whitespace collapsed first. |
| `normalized_text` | `packages/whisker/src/whisker/metrics.py:445-447` | OmniDocBench normalizer: `clean_string(textblock2unicode(text))`. |
| `_TedsConfig.normalized_distance` | `packages/whisker/src/whisker/metrics.py:496-497` | TEDS cell relabel: same `Levenshtein.distance / max(len)`. |
| `_mhs_relabel` | `packages/whisker/src/whisker/metrics.py:658-664` | MHS heading-text relabel via `normalized_edit_distance`. |
| `_ned` | `packages/whisker/src/whisker/match.py:100-107` | Block NED matrix cell (duplicate formula). |
| `_sub_gt_fuzzy_matching` | `packages/whisker/src/whisker/match.py:119-132` | Sliding-window substring NED for fuzzy rescue. |
| `match_blocks` | `packages/whisker/src/whisker/match.py:180` | Raw `edit_num=Levenshtein.distance(g,p)` for `edit_whole`. |
| `reading_order_ned` | `packages/whisker/src/whisker/match.py:295` | Concatenated matched-block sequence distance. |

**Dependency:** `levenshtein>=0.25.1` in `packages/whisker/pyproject.toml:10` (import name `Levenshtein`). Pin in workspace resolves to **0.27.3** (June 2026).

**Hot path:** full-document compare in oracle `ref_nid` (`score.py:212` via `text_nid`), block NED matrix in `match.py` (O(gt×pred) cells, capped by `BLOCK_MATRIX_CELL_BUDGET`), TEDS cell tokens, MHS heading labels.

**Reference lineage:** verbatim OmniDocBench / PubTabNet stack (`metrics.py` module docstring, `match.py` module docstring). Published Text Edit axis = `(1 - edit)` on normalized content, not fuzzy ratio or Ratcliff.

---

## 2. Candidate libraries

Spot-checked on Python 3.12 (June 2026) with representative pairs including CJK and 1k-char strings. **Score-identical** means raw Levenshtein integer distance and `distance/max(len)` match whisker's `normalized_edit_distance` on tested inputs.

| Library | PyPI name | License | Last release | Implementation | Deterministic | Score-identical to current |
|---------|-----------|---------|--------------|----------------|---------------|---------------------------|
| **python-Levenshtein successor (current)** | `levenshtein` | **GPL-2.0-or-later** | 0.27.3 (2025) | C extension (bit-parallel) | Yes (single-threaded, no RNG) | **Yes (definition)** |
| **RapidFuzz Levenshtein** | `rapidfuzz` | MIT | 3.14.5 (2025) | C++ / SIMD | Yes | **Yes on spot tests** for `distance()` and `normalized_distance()`; **not** for `Indel` (insert/delete-only; e.g. `Indel('abc','abd')=2` vs Levenshtein `1`) |
| **RapidFuzz ratios** (`fuzz.ratio`, `partial_ratio`) | `rapidfuzz` | MIT | 3.14.5 | C++ | Yes | **No** — 0–100 scale, different normalization; used by MinerU/marker/opendataloader, not OmniDocBench NID |
| **editdistance** | `editdistance` | MIT | 0.8.1 (2022) | C extension | Yes | **Yes** raw distance on spot tests; unmaintained; no bundled NED helper |
| **jellyfish** | `jellyfish` | BSD-2-Clause (project) | 1.2.1 (2024) | C | Yes | **Yes** raw distance on spot tests; extra dep for no gain |
| **stdlib difflib.SequenceMatcher** | (stdlib) | PSF | 3.12 | Pure Python | Yes | **No** — `ratio()` is Ratcliff-Obershelp-like (longest matching blocks / total); e.g. `('hello world','hello there')` → ratio `0.636` vs NID `0.545` |

**Notes**

- `rapidfuzz` and `levenshtein` share maintainer (Max Bachmann) and algorithm lineage; `rapidfuzz.distance.Levenshtein` is the MIT-licensed sibling.
- **License tension:** current dep is GPL-2.0-or-later per PyPI `License-Expression`. Constraint prefers MIT/BSD/Apache/BSL. Already shipped in whisker; swapping to `rapidfuzz` is the documented escape hatch if GPL becomes blocking, after a full corpus golden parity run.
- **Weighted Levenshtein** (Unstructured `(2,1,1)` insert/delete/substitution) is a **different metric** — not comparable to OmniDocBench NID.

---

## 3. Local red-team repos (28) — who uses what

Clones under `packages/whisker/research/repos/<name>/` were **not present** in this workspace (0 files). Usage below is from red-team reports that deep-read those repos (file paths as cited in reports).

| Repo | Library / API | Evidence (red-team report → upstream path) |
|------|---------------|--------------------------------------------|
| **marker** | `rapidfuzz` `fuzz.partial_ratio_alignment` | `research/redteam/marker.md` → `repos/marker/benchmarks/overall/scorers/heuristic.py:271` |
| **MinerU** | `fuzzywuzzy` / `fuzz.ratio` (rapidfuzz lineage) | `research/redteam/MinerU.md` → `test_e2e.py:7-8,164-167` |
| **opendataloader-pdf** | `rapidfuzz` ratios | `research/redteam/opendataloader-pdf.md` → `evaluator_reading_order.py:37-38` |
| **docling** | Python `levenshtein()` (NED `dist/len(gt)`, not `max(len)`) | `research/redteam/docling.md` → `verify_utils.py:110-112,253` |
| **unstructured** | Custom weighted Levenshtein `(2,1,1)` | `research/redteam/unstructured.md` → `text_extraction.py:57-117,109-110` |
| **grobid** | Java Levenshtein + Ratcliff tiers | `research/redteam/grobid.md` → `EndToEndEvaluation.java:1126-1134` |
| **firecrawl** | Levenshtein similarity (one of several signals) | `research/redteam/firecrawl.md` → shadow/AB thresholds (TypeScript) |
| **pymupdf4llm** | `difflib.unified_diff` (failure display only, not scoring) | `research/redteam/pymupdf4llm.md` → `tests/test_370.py:35-42` |
| **Dolphin, nougat, PDF-Extract-Kit, …** | External OmniDocBench leaderboard; no in-repo Python Levenshtein | `research/redteam/Dolphin.md`, `nougat.md` — cite OmniDocBench axes, not a local import |
| **Remaining ~18 repos** (pandoc, html2text, turndown, camelot, pdfplumber, …) | **None** for edit-distance scoring | No matches in red-team grep for this capability |

**Field pattern:** converters that score in-repo often use **rapidfuzz ratios** (block-level, 0–100) or **exact golden diff**; only whisker + OmniDocBench lineage target **NED = Lev/max(len)** on normalized full text.

---

## 4. VERDICT: KEEP-AS-IS

### Why (constraint-tied)

1. **Score parity (binding):** whisker ports OmniDocBench Text Edit verbatim. Leaderboard numbers, guard baselines, and `_FLOORS` assume `Levenshtein.distance / max(len)`. No candidate besides `levenshtein` / `rapidfuzz.distance.Levenshtein` matches that definition; switching without a full golden corpus re-baseline would invalidate every published comparison.
2. **Minimalism ladder:** `levenshtein` is **already** in `pyproject.toml` and wired at six call sites. `rapidfuzz` would be a **swap** (add + remove), not a free win — zero new capability for the NID axis.
3. **Performance:** C-extension bit-parallel Levenshtein already makes full-document compares milliseconds (`metrics.py:176-178`, `CLAUDE.md:116-117`). SIMD batching in rapidfuzz helps O(n×m) matrices marginally; block path is already capped by `BLOCK_MATRIX_CELL_BUDGET`.
4. **Determinism:** All serious candidates are deterministic. No LLM, no parallelism in scoring path. KEEP.
5. **No lib wins on merit:** `editdistance` / `jellyfish` duplicate raw distance with no OmniDocBench pedigree. `difflib` is the wrong metric. `rapidfuzz` ratios are the wrong metric. `rapidfuzz.Indel` is a footgun (different distance).

### Why not BUY rapidfuzz (now)

- Spot tests show **bit-identical** Levenshtein + NED vs current, but production corpus + pinned wheels were not re-goldened in this research pass.
- **API surface:** rapidfuzz exposes many metrics; whisker needs exactly one. Staying on `Levenshtein.distance` minimizes wrong-metric imports.
- **Single-maintainer concentration** applies equally to `levenshtein` (same org: rapidfuzz/Levenshtein on GitHub).

### Why not BUILD-IMPROVE (pure Python)

- Pure-Python Wagner-Fischer is **O(n×m)** on tens of thousands of chars per document → minutes per paper (`metrics.py:176-178`). Violates usable bench/oracle latency. Stdlib `difflib` is wrong metric + slow.

### Micro-improvements (optional, no dep change)

1. **DRY:** `match.py:_ned` duplicates `metrics.normalized_edit_distance` (only whitespace handling differs — match normalizes before call). Route `_ned` through `normalized_edit_distance` after shared normalize to one formula.
2. **Pin discipline:** keep `levenshtein>=0.25.1`; bump only with a parity test job that asserts `normalized_edit_distance` golden vectors unchanged (existing `tests/test_metrics.py:33-35`, `tests/test_invariants.py`).
3. **Future license migration:** if GPL-2.0-or-later on `levenshtein` becomes unacceptable, plan **BUY rapidfuzz** with `from rapidfuzz.distance import Levenshtein as RFLev` and `RFLev.distance` / `RFLev.normalized_distance` only — never `Indel` or `fuzz.ratio`. Require corpus-wide golden diff before dropping `levenshtein`.

### If forced to BUY rapidfuzz later (integration sketch)

```
# pyproject.toml
- "levenshtein>=0.25.1",
+ "rapidfuzz>=3.14.5,<4",

# metrics.py / match.py
- import Levenshtein
+ from rapidfuzz.distance import Levenshtein as _Lev
  ...
- Levenshtein.distance(a, b)
+ _Lev.distance(a, b)
```

Delete: `levenshtein` dependency. Add: `tests/test_edit_distance_parity.py` with property tests + frozen OmniDocBench snippet vectors. Re-run `whisker guard --update` on full baseline after parity proof.

---

## 5. Determinism and score-parity risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Library swap** (levenshtein → rapidfuzz / other) | **HIGH** | Treat as semver-major for whisker scores. Full corpus golden + guard baseline refresh. Spot tests insufficient. |
| **Wrong rapidfuzz API** (`Indel`, `fuzz.ratio`, `partial_ratio`) | **HIGH** | Code review + lint import ban. Only `distance.Levenshtein.distance`. |
| **Normalization drift** (`normalized_text`, `clean_string`, pylatexenc) | **HIGH** | Dominates perceived NID changes; edit-distance core is stable if normalization is pinned. Pin normalizer version in baseline metadata (gap noted in red-team). |
| **Weighted / asymmetric NED** (Docling `dist/len(gt)`, Unstructured weights) | **MEDIUM** | Do not mix formulas across axes. whisker uses `max(len)` everywhere — matches OmniDocBench. |
| **Float boundary** at guard `round(v, 4)` | **LOW** | Independent of distance lib; round both sides before diff. |
| **GPL-2.0-or-later on `levenshtein`** | **MEDIUM (license)** | Pre-existing dep. rapidfuzz MIT is migration path; not a score reason to switch today. |
| **levenshtein pin bump** | **LOW** | Same algorithm family; run invariant tests on upgrade. |
| **Unicode version / Python version** | **LOW** | All C extensions use Python str code points; deterministic across runs on same Python build. |

---

## 6. Evidence log

- Current implementation read: `packages/whisker/src/whisker/metrics.py`, `match.py`, `pyproject.toml`.
- Prior synthesis: `packages/whisker/notes/redteam-synthesis.md`, `gap-matrix.md` (row 16: verbatim TEDS/MHS/NID).
- Runtime parity (June 2026, workspace venv): `Levenshtein.distance` == `rapidfuzz.distance.Levenshtein.distance` == `editdistance.eval` == `jellyfish.levenshtein_distance` on 7 test pairs; NED matches `rapidfuzz.normalized_distance`; `SequenceMatcher.ratio` diverges on fuzzy pairs.
