VERDICT: BUY apted - zero-cost dep, delete ~100 lines, scores identical

# BUILD-vs-BUY: ordered tree-edit distance for MHS

Capability: **ordered tree edit distance** with custom insert/delete/relabel costs, used by whisker's **Markdown Heading Similarity (MHS)** metric.

Constraints checked: deterministic (no randomness/parallelism), no LLM, permissive license only, Python >=3.12, minimalism ladder (prefer existing deps over new code/deps).

---

## 1. Current state

| Symbol | File | Lines | Role |
|--------|------|-------|------|
| `TreeNode` | `packages/whisker/src/whisker/metrics.py` | 60–69 | Ordered labeled tree node (`label`, `children`) |
| `_annotate` | `metrics.py` | 72–101 | Postorder + keyroot indexing for Zhang-Shasha DP |
| `tree_edit_distance` | `metrics.py` | 104–156 | Hand-rolled Zhang-Shasha; custom `relabel_cost` / `remove_cost` / `insert_cost` callables |
| `_node_count` | `metrics.py` | 159–166 | Denominator for MHS normalization |
| `_parse_headings` | `metrics.py` | 628–641 | Extract `(level, text)` from markdown (fence-aware) |
| `_build_heading_tree` | `metrics.py` | 644–655 | Nest headings under synthetic root `{"level": 0, "text": "\x00root"}` |
| `_mhs_relabel` | `metrics.py` | 658–666 | Relabel cost = `normalized_edit_distance(text_a, text_b)`; structure-only → 0.0 |
| `mhs` | `metrics.py` | 669–684 | `1 - dist / max(n_a, n_b)`; only consumer of `tree_edit_distance` |
| `_TableTree`, `_TedsConfig`, `_TEDS` | `metrics.py` | 470–584 | **TEDS already uses `apted.APTED`** with custom `Config.rename` (Levenshtein on cell tokens) |
| `tree_edit_distance` tests | `packages/whisker/tests/test_metrics.py` | 44–55 | Generic tree tests (identity, relabel, insert) |
| `mhs` tests | `test_metrics.py`, `test_invariants.py` | 104–116, 96–114 | Identity, level change, no-headings, symmetry |

**Call graph:** `mhs` → `_build_heading_tree` → `tree_edit_distance` (+ `_mhs_relabel`, `_node_count`). Also called from `bench.py:160`, `score.py:214` via `mhs()` only (not `tree_edit_distance` directly).

**Public exports:** `TreeNode`, `tree_edit_distance` are in `metrics.__all__` (lines 43–53). No other package imports them (grep scope: `packages/whisker/`).

**Doc mismatch:** Module docstring (line 8) says "no external deps"; file already imports `apted`, `Levenshtein`, `lxml`, `pylatexenc`.

---

## 2. Candidate libraries

| Library | License | In whisker? | Maintenance | Ordered trees | Custom insert/delete/rename | Determinism | MHS fit |
|---------|---------|-------------|-------------|---------------|----------------------------|-------------|---------|
| **apted** | MIT | **Yes** (`apted>=1.0.3`) | Stable; last PyPI **1.0.3 (2017-11-08)**; used in production for TEDS | Yes (APTED = optimal **ordered** tree edit distance) | Yes: subclass `Config`; override `delete(node)`, `insert(node)`, `rename(node1, node2)`, optional `children(node)` | Pure Python, single-threaded; no RNG | **Best** — already imported; TEDS precedent |
| **zss** | BSD-style (v1.1+; permissive) | No | **Stale**: last PyPI **1.2.0 (2018-03-12)**; ~215k downloads/mo | Yes (Zhang-Shasha, ordered) | Yes: `zss.distance(A, B, get_children, insert_cost, remove_cost, update_cost)` | Pure Python; deterministic | Redundant new dep; same algorithm family as hand-roll |
| **edist** | **GPL-3** | No | Active (1.2.x); Cython core | Yes (`edist.ted.ted` + custom `delta`) | Yes: `delta(x, y)`, `delta(x, None)`, `delta(None, y)` | Deterministic | **Disqualified** — GPL incompatible with whisker BSL / permissive-only rule |

### apted custom-cost API (verified in `.venv/Lib/site-packages/apted/config.py`)

- Default `Config.delete` / `insert` → unit cost 1 (int or float).
- Default `Config.rename` → compares `node.name` (not used for MHS).
- `PerEditOperationConfig(del, ins, ren)` for uniform operation weights.
- TEDS pattern in whisker: `_TedsConfig.rename` returns float Levenshtein ratio; `APTED(...).compute_edit_distance()` accepts float costs.

### Score parity (empirical)

Ran Zhang-Shasha (`tree_edit_distance`) vs `APTED` + `_MhsConfig` on:

- All `test_metrics.py` / `test_invariants.py` MHS fixtures
- 36 heading-markdown pairs × `{structure_only: false, true}` = **72 comparisons**

**Result: 0 mismatches** (distances identical to float equality).

Both algorithms solve the **same optimization problem** (minimum-cost ordered tree edit mapping under the given cost model). Zhang-Shasha and APTED differ in **time complexity**, not optimal distance, when costs are additive and trees are ordered.

---

## 3. Local redteam repos: who uses which lib?

**Grep target:** `packages/whisker/research/repos/<name>/` for `apted`, `zss`, `edist`, `tree edit`, `Zhang-Shasha`.

**Finding:** 30 repo directory names exist under `research/repos/`, but **clones are empty** (0 source files; `Get-ChildItem -Recurse -File` returns nothing). Grep over that tree: **no matches**.

**Prior redteam synthesis** (from `notes/cross-repo-qa-research.md`, `notes/redteam-synthesis.md`, individual `.md` reports — not re-cloned):

| Repo / benchmark | Tree-edit library | Notes |
|------------------|-------------------|-------|
| PubTabNet / OmniDocBench TEDS | **apted** | Verbatim port in whisker `metrics.py:460–619`; `_bench_src/OmniDocBench/src/metrics/table_metric.py` |
| whisker MHS | **Hand-rolled Zhang-Shasha** | `metrics.py:57–156`; only whisker in this workspace |
| opendataloader-pdf | **Custom** (`evaluator_heading_level.py`) | Redteam cites heading/MHS axes; no apted/zss/edist import reported |
| markitdown, MinerU, surya, Dolphin, PDF-Extract-Kit, … | **None in-repo** | External benchmark citations only (`cross-repo-qa-research.md:118`) |
| mdream | **Exact count/level match** (Jest) | Fuzzy tree edit only in whisker (`mdream.md:233`) |
| csim (external, not in 28) | apted **or** zss | Documented as interchangeable TED backends (MIT) |

**Conclusion:** Among the 28 redteam targets, **only the OmniDocBench/TEDS lineage uses apted**. No redteam repo uses `zss` or `edist` for heading metrics. MHS is whisker-internal.

---

## 4. VERDICT: BUY apted

### Why BUY (not BUILD / KEEP / zss)

1. **Zero marginal dependency cost** — `apted>=1.0.3` is already in `pyproject.toml` and used for leaderboard-comparable TEDS.
2. **Delete ~100 lines** — Remove `TreeNode`, `_annotate`, `tree_edit_distance` (~57–156); keep heading parse/build + normalization.
3. **Consistency** — One tree-edit backend (`apted.Config`) for both TEDS and MHS; same import surface as PubTabNet reference.
4. **Scores unchanged** — Empirical parity on 72 cases; MHS is not a published external leaderboard, but identical distances mean **no baseline/guard drift** on migration.
5. **zss rejected** — Adds a stale third-party dep for the same Zhang-Shasha semantics whisker already gets from apted.
6. **KEEP-AS-IS rejected** — Hand-roll duplicates apted's cost model, diverges from TEDS, and maintains dead code (`TreeNode` exported but only MHS uses it).
7. **BUILD-IMPROVE rejected** — No bug or perf gap: heading trees are tiny (≤ tens of nodes per paper); apted is fast enough.

### Integration sketch

```python
# New (mirror _TableTree / _TedsConfig)
class _HeadingTree(Tree):
    def __init__(self, label, *children):
        self.label = label  # {"level": int, "text": str}
        self.children = list(children)

class _MhsConfig(Config):
    def __init__(self, structure_only: bool = False):
        self.structure_only = structure_only

    def delete(self, node):
        return 1.0

    def insert(self, node):
        return 1.0

    def rename(self, node1, node2):
        if self.structure_only:
            return 0.0
        a = node1.label if isinstance(node1.label, dict) else {}
        b = node2.label if isinstance(node2.label, dict) else {}
        return normalized_edit_distance(a.get("text", ""), b.get("text", ""))

    def children(self, node):
        return node.children


def _build_heading_tree(md_text: str) -> _HeadingTree:
    # same stack logic; return _HeadingTree nodes instead of TreeNode
    ...


def mhs(md_a: str, md_b: str, *, structure_only: bool = False) -> float:
    tree_a = _build_heading_tree(md_a)
    tree_b = _build_heading_tree(md_b)
    n_a = _node_count(tree_a)  # or apted iterator tree_size
    n_b = _node_count(tree_b)
    denom = max(n_a, n_b)
    if denom <= 1:
        return 1.0
    dist = APTED(tree_a, tree_b, _MhsConfig(structure_only)).compute_edit_distance()
    return max(0.0, 1.0 - dist / denom)
```

### Lines to delete / change

| Action | Lines (approx) | Content |
|--------|----------------|---------|
| **Delete** | 57–156 | `TreeNode`, `_annotate`, `tree_edit_distance` |
| **Remove from `__all__`** | 43, 53 | `TreeNode`, `tree_edit_distance` |
| **Replace return type** | 644–655 | `_build_heading_tree` → `_HeadingTree` |
| **Replace distance call** | 683 | `APTED(..., _MhsConfig(...)).compute_edit_distance()` |
| **Keep** | 159–166, 628–666 | `_node_count`, `_parse_headings`, `_mhs_relabel` logic (inline into `_MhsConfig.rename`) |
| **Update tests** | `test_metrics.py:44–55` | Drop generic `tree_edit_distance` tests; keep `mhs` tests (should pass unchanged) |
| **Update docstrings** | 8, 21–22, CLAUDE.md | "Zhang-Shasha pure Python" → "apted (same as TEDS)" |

### Score change expectation

**None** under current cost model (unit insert/delete, fractional relabel via Levenshtein). Re-baseline not required if migration includes parity tests asserting `mhs(a,b)` unchanged on frozen fixtures.

---

## 5. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Score drift** if apted bug or non-equivalent cost wiring | Low | 72/72 parity checks; add regression test `mhs` golden vectors before/after swap |
| **apted maintenance** (no release since 2017) | Medium | Already accepted for TEDS leaderboard parity; same risk profile for MHS |
| **Public API break** (`TreeNode`, `tree_edit_distance` exported) | Low | Grep shows no external callers; semver bump or deprecation note if published |
| **Float rename + structure_only=0.0** | Low | Verified; apted `Config.forest_dist` sums float `rename` costs |
| **Tie-breaking in edit mapping** | N/A for MHS | whisker uses distance only, not mapping; tie order irrelevant |
| **Very deep heading trees** | Low | WG21 papers: typically <20 headings; APTED O(n²) or better is fine |
| **Accidental unordered-tree metric** | N/A | APTED is ordered; matches MHS spec (sibling order matters) |

---

## 6. Alternatives considered

| Option | Verdict |
|--------|---------|
| **BUY apted** | **Selected** |
| BUY zss | Rejected: new dep, stale, duplicates Zhang-Shasha hand-roll |
| BUY edist | Rejected: GPL-3 |
| BUILD-IMPROVE hand-roll | Rejected: no perf/correctness win |
| KEEP-AS-IS | Rejected: violates minimalism (duplicate TED stack) |

---

## 7. Evidence log

- Source read: `packages/whisker/src/whisker/metrics.py` (full file)
- Dependency: `packages/whisker/pyproject.toml`
- apted API: `.venv/Lib/site-packages/apted/config.py`
- Parity script: 72 pairwise comparisons, 0 mismatches (2026-06-25, workspace venv)
- Repo grep: `packages/whisker/research/repos/**` — empty clones, 0 library hits
- Prior notes: `notes/cross-repo-qa-research.md:118`, `notes/redteam-synthesis.md`, `research/redteam/opendataloader-pdf.md`, `research/redteam/mdream.md`
