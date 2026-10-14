VERDICT: BUILD stdlib - field uses exact substrings; metrics already cover fuzzy drift

# Build vs Buy: Per-Paper Substring/Section-Order Anchors

Research for whisker gap-matrix #9 (June 2026). Scope: author-curated per-paper
assertions that specific text MUST or MUST NOT appear (optionally in order) in
converted Markdown, independent of corpus-wide NID/TEDS/MHS guard baselines.

Constraints: deterministic, no LLM, Python >=3.12, permissive license only,
minimalism ladder (stdlib first), lib returns data, anchors are trusted config.

---

## 1. Confirm absence in whisker

**No anchor/facts layer exists today.**

| Location | Evidence |
|----------|----------|
| `guard.py` | Diffs only `nid/teds/mhs/overall` floats per paper; no substring checks (`packages/whisker/src/whisker/guard.py:65-71`, `172-184`). |
| `__main__.py` | Bench/guard corpus loader pairs `<pid>.gt.md` with staged candidate MD only; no `<pid>.anchors.json` or facts loader (`packages/whisker/src/whisker/__main__.py:248-255`). |
| `tests/` | No `must_include`, `anchor`, or `facts` tests (`grep` over `packages/whisker/tests/`). |
| `gap-matrix.md` | Row #9: **ABSENT** — "Recommended follow-on: per-paper `facts` file (anchors)" (`packages/whisker/notes/gap-matrix.md:19`). |
| `redteam-synthesis.md` | Tier-3 deferred feature: "Substring/section-order anchors" (`packages/whisker/notes/redteam-synthesis.md:37-38`). |

**Closest analog:** full reference files `<pid>.gt.md` for bench scoring. That is a
heavy labeled golden, not a lightweight tripwire. A paper can pass guard slack while
losing a critical phrase (markitdown red-team finding).

---

## 2. Per-repo anchor styles (local grep + prior deep-read)

### 2.1 markitdown — must/must-not + ordered `str.find()`

**Present/absent (exact substring on raw markdown):**

```65:68:packages/whisker/research/repos/markitdown/packages/markitdown/tests/test_module_vectors.py
    for string in test_vector.must_include:
        assert string in result.markdown
    for string in test_vector.must_not_include:
        assert string not in result.markdown
```

**Vector schema (author-curated lists per fixture):**

```11:12:packages/whisker/research/repos/markitdown/packages/markitdown/tests/_test_vectors.py
    must_include: List[str]
    must_not_include: List[str]
```

**PDF helper: normalize backslashes, then `in` / `not in`:**

```14:21:packages/whisker/research/repos/markitdown/packages/markitdown/tests/test_pdf_tables.py
def validate_strings(result, expected_strings, exclude_strings=None):
    """Validate presence or absence of specific strings."""
    text_content = result.text_content.replace("\\", "")
    for string in expected_strings:
        assert string in text_content, f"Expected string not found: {string}"
    if exclude_strings:
        for string in exclude_strings:
            assert string not in text_content, f"Excluded string found: {string}"
```

**Section order: collect `find()` offsets, assert strict increasing chain:**

```225:241:packages/whisker/research/repos/markitdown/packages/markitdown/tests/test_pdf_tables.py
        header_pos = text_content.find("INVENTORY RECONCILIATION REPORT")
        ...
        variance_pos = text_content.find("Variance Analysis:")
        extended_review_pos = text_content.find("Extended Inventory Review:")
        ...
        recommendations_pos = text_content.find("Recommendations:")
```

```256:268:packages/whisker/research/repos/markitdown/packages/markitdown/tests/test_pdf_tables.py
        assert (
            positions["header"] < positions["first_table"]
        ), "Header should come before first table"
        assert (
            positions["first_table"] < positions["variance_analysis"]
        ), "First table should come before Variance Analysis"
        ...
        assert (
            positions["extended_review"] < positions["second_table"]
        ), "Extended Review should come before second table"
```

**Style summary:** exact substring, optional minimal pre-normalize (`replace("\\","")`),
ordered sections via monotonic `find()` positions; optional `re.search` for brittle
table headers (`test_pdf_tables.py:227-237`).

### 2.2 firecrawl — Jest `toContain` / `not.toContain` on markdown

Local checkout is sparse (no `apps/api/src/**/scrapeURL.test.ts` in tree); prior
deep-read of full clone documented ~124 markdown substring anchors. Representative
patterns (from `packages/whisker/research/redteam/firecrawl.md`, paths in upstream repo):

| Pattern | Upstream cite |
|---------|---------------|
| Must contain site title | `scrapeURL.test.ts:55` — `expect(out.document.markdown).toContain("Firecrawl Test Site")` |
| Must not contain stripped nav | `scrapeURL.test.ts:142-143` — `not.toContain("[FAQ](/faq/)")` after `excludeTags` |
| Unicode CJK anchor | `scrape.test.ts:191-193` |
| Go html-to-md service | `handler_test.go:157-162` — `contains(response.Markdown, tc.expectedOutput)` |

**Style summary:** exact substring on converted markdown body; no fuzzy layer; negative
anchors for stripped/excluded content.

### 2.3 olmocr — JSONL present/absent/order facts with normalization

Source tree not cloned locally (empty `research/repos/olmocr/`). Prior deep-read
(`packages/whisker/research/redteam/olmocr.md`) cites upstream `tests.py`:

| Class | Upstream cite | Semantics |
|-------|---------------|-----------|
| `TextPresenceTest` | `tests.py:128-182` | Required substrings; `ABSENT` mode for forbidden text (`177-182`) |
| `TextOrderTest` | `tests.py:186-226` | Before/after ordering pairs |
| `normalize_text()` | `tests.py:47-80,150-154` | NFC, hyphen/quote fold, markdown strip, whitespace collapse before every check |
| Length-relative fuzzy | `tests.py:168-169` | `threshold = 1.0 - (max_diffs / len(reference_query))` — edit budget per fact, not RapidFuzz |

**Style summary:** structured fact file per PDF/page; normalize-then-exact (with optional
bounded edit tolerance on normalized text). Rejects whole-page edit distance as primary
gate (`README.md:10-11` per redteam doc).

### 2.4 MinerU — substring hit-rate + `fuzz.ratio` per block

Source tree not cloned locally. Prior deep-read (`packages/whisker/research/redteam/MinerU.md`)
cites `tests/unittest/test_e2e.py`:

| Pattern | Upstream cite | Semantics |
|---------|---------------|-----------|
| Table cell anchors | `test_e2e.py:181-199` | `target_str_list` literals; pass if hit rate > threshold |
| txt/ocr threshold | `test_e2e.py:198-199` | `correct_count / len(targets) > 0.9` |
| vlm threshold | `test_e2e.py:198-201` | `> 0.7` (lower bar for vision backend) |
| Block text fuzzy | `test_e2e.py:163-168,213-218` | `fuzz.ratio(a,b) > 90` (fuzzywuzzy, GPL lineage) |

**Style summary:** modality-stratified thresholds; aggregate hit-rate over anchor list;
fuzzy ratio on block text (not partial_ratio sliding window).

### 2.5 Field consensus

From `packages/whisker/notes/cross-repo-qa-research.md:62-71`:

- **Exact anchors dominate** for tripwire tests (markitdown, firecrawl, olmocr presence/absence/order).
- **Fuzzy hit-rate** appears where OCR/VLM noise is expected (MinerU, marker per redteam).
- **Normalization before match** is universal in serious implementations (markitdown backslash strip; olmocr full normalize pipeline; whisker already has `normalized_text` for metrics).

---

## 3. Candidate implementation table

| Option | License | New dep? | Determinism | Fuzzy tolerance | Field alignment |
|--------|---------|----------|-------------|-----------------|-----------------|
| **stdlib `in` / `not in`** | PSF | No | Exact, stable | None | markitdown, firecrawl |
| **stdlib `str.find()` order chain** | PSF | No | Exact; `-1` = missing | None | markitdown `test_pdf_tables.py` |
| **stdlib `re.search` / `re.findall`** | PSF | No | Exact on chosen surface | None | markitdown table-header patterns |
| **`normalized_text()` surface** | BSL (in-tree) | No (already in metrics) | Exact on content-normalized text | Collapses format noise olmocr also strips | olmocr normalize-then-check; whisker bench NID axis |
| **`rapidfuzz.partial_ratio`** | MIT | Yes (`rapidfuzz`) | Deterministic for fixed inputs; **long-needle (>64) uses LCS heuristic, may miss optimal alignment** (upstream docs) | Sliding-window partial match; threshold e.g. 90 | MinerU/marker fuzzy tier (different API: full `ratio`, not partial) |
| **`Levenshtein.ratio` (already dep)** | GPL-2.0? **Check:** `levenshtein` PyPI is **GPL-2.0-or-later** | Already installed | Deterministic | Full-string ratio; can scan windows manually | MinerU-like without new dep, but window scan is O(n*m) and duplicates metric-layer edit distance |

**rapidfuzz note:** MIT-licensed, acceptable under whisker license policy. Adds a dep for
capability largely orthogonal to anchor tripwires. Long-string `partial_ratio` is
approximate (documented in RapidFuzz: may not find globally optimal alignment for needles
>64 chars). That is a determinism-vs-semantics tradeoff, not run-to-run variance.

**levenshtein note:** Already required for `text_nid`/TEDS. Reusing it for optional fuzzy
anchors avoids a new dep but blurs the "tripwire vs metric" boundary and GPL is already
accepted in this workspace.

---

## 4. Verdict: BUILD (stdlib + `normalized_text`)

**Do not BUY `rapidfuzz` for v1 anchors.**

### Why BUILD

1. **Field practice matches stdlib.** The three highest-signal repos for WG21-style
   conversion QA (markitdown, firecrawl, olmocr) gate on **exact** normalized substrings
   and **ordered `find()`**, not fuzzy partial match. Fuzzy tiers target OCR/VLM backends
   (MinerU txt vs vlm split), not deterministic pdfminer/toml HTML paths.

2. **Fuzzy drift is already guarded.** NID/TEDS/MHS/unigram coverage catch aggregate
   text loss. Anchors are **localized tripwires** for facts that must survive reflow
   (proposal numbers, normative "shall" phrases, table headers). Authors pick anchor
   strings from known-good output; exact match is the intended contract.

3. **Minimalism ladder.** `in`, `not in`, `find()`, and optional `re` cover present,
   absent, order, and pattern anchors with zero new dependencies.

4. **Normalization reuse.** Apply `whisker.metrics.normalized_text` (or raw MD via
   explicit `"surface": "raw"`) so anchors align with the bench text axis, matching
   olmocr's "normalize before diff" principle without importing olmocr's full pipeline.

5. **Determinism.** Stdlib exact match has no heuristic alignment ambiguity. Avoid
   `partial_ratio` long-needle approximation in a gate that must be auditable.

### Optional hybrid (later, still no rapidfuzz)

If a paper needs tolerance for minor whitespace/unicode noise **after** normalization:

- Phase 2 `"match": "ratio"` anchor using existing `Levenshtein.ratio` on the **anchor
  string only** (short needle, bounded), with explicit `min_ratio` in JSON — mirrors
  olmocr `max_diffs` semantics, not MinerU corpus hit-rate.
- Or olmocr-style: `max_edits` integer on normalized anchor text (stdlib + Levenshtein
  distance on extracted window).

Do not default the corpus to fuzzy; opt-in per anchor.

### Proposed `<pid>.anchors.json` schema

```json
{
  "schema_version": 1,
  "kind": "whisker-anchors",
  "pid": "P3100R6",
  "surface": "normalized",
  "must_contain": [
    "P3100R0",
    "LEWG"
  ],
  "must_not_contain": [
    "Page 1 of"
  ],
  "ordered": [
    "## Abstract",
    "## Revision history",
    "## Proposal"
  ],
  "patterns": [
    {"id": "document-line", "regex": "^document:\\s*P3100R6\\s*$", "flags": "MULTILINE"}
  ]
}
```

| Field | Semantics |
|-------|-----------|
| `surface` | `"normalized"` (default): `normalized_text(md)`; `"raw"`: candidate MD as stored |
| `must_contain` | Every string must appear (`sub in haystack` after surface) |
| `must_not_contain` | Every string must be absent |
| `ordered` | Strictly increasing `haystack.find(s)`; all must be found (`pos != -1`) |
| `patterns` | `re.search` must match at least once; `flags` passed to `re.compile` |

Optional phase-2 extension (not v1):

```json
"fuzzy": [{"needle": "WG21", "min_ratio": 0.92, "match": "levenshtein_ratio"}]
```

### Check function (returns data)

New module e.g. `anchors.py` (sketch only; not implemented in this research pass):

```python
@dataclass(frozen=True)
class AnchorCheck:
    id: str          # e.g. "must_contain[0]" or "ordered[1]"
    passed: bool
    detail: str      # human-readable failure

@dataclass(frozen=True)
class AnchorReport:
    pid: str
    passed: bool
    checks: tuple[AnchorCheck, ...]

def check_anchors(md: str, spec: AnchorSpec) -> AnchorReport:
    haystack = _surface(md, spec.surface)
    checks: list[AnchorCheck] = []
    # must_contain, must_not_contain, ordered find chain, patterns — pure, no I/O
    ...
    return AnchorReport(pid=spec.pid, passed=all(c.passed for c in checks), checks=tuple(checks))
```

Load JSON → `AnchorSpec` dataclass; validate schema/kind; reject unknown fields in strict mode.

### CLI integration (gate sketch)

Extend **`whisker guard`** (same corpus walk as today):

1. `_load_corpus_pairs(corpus)` unchanged.
2. For each `pid`, if `corpus / f"{pid}.anchors.json"` exists, load spec and run
   `check_anchors(candidate_md, spec)`.
3. Merge into `GuardReport`: new per-paper field `anchor_failed: bool`, list of
   `AnchorCheck` failures; new status `STATUS_ANCHOR_FAIL` (or fold into
   `STATUS_REGRESSED` with axis `"anchors"`).
4. Exit code: anchor failure fails guard same as metric regression (deterministic hard fail).
5. **`whisker bench`**: optionally report anchor pass rate in JSON; do not require anchors
   for leaderboard means.

Optional: `whisker guard --anchors-only` for fast tripwire CI without full metric diff.

Anchors are **conjunctive** with metric guard (markitdown pattern: all asserts must pass;
olmocr: every fact is independent pass/fail). Anchor miss fails even when NID slack holds.

---

## 5. Risks

| Risk | Mitigation |
|------|------------|
| **Anchor brittleness** | Authors derive strings from committed good output; prefer `normalized` surface; use short distinctive phrases (proposal id, section titles), not full paragraphs; document refresh ritual alongside `guard --update`. |
| **Normalization mismatch** | Default `surface: "normalized"` ties anchors to the same `normalized_text` used by bench NID; document that YAML front-matter tokens remain in normalized text (negligible for WG21). Offer `raw` for format-specific checks (pipe tables). |
| **Ordering semantics** | `ordered` is **document order**, not reading-order metric; duplicate anchor strings make `find()` pick first occurrence only — forbid duplicates in schema validation or use unique ids with `re.search` for disambiguation. |
| **False confidence** | Anchors catch localized deletion; they do not prove full fidelity. Keep `<pid>.gt.md` bench + guard metrics as primary regression surface. |
| **Fuzzy creep** | Resist default fuzzy anchors; they duplicate NID and introduce threshold tuning. If added later, per-anchor `min_ratio` only, never corpus-wide hit-rate without labeled rationale. |
| **Partial repo clones** | firecrawl/olmocr/MinerU source not fully present under `research/repos/`; citations above mix local grep (markitdown) with prior deep-read line refs. Re-verify upstream before implementing olmocr-style `max_diffs`. |

---

## 6. References

- `packages/whisker/notes/gap-matrix.md` (#9)
- `packages/whisker/notes/cross-repo-qa-research.md` (practice #3)
- `packages/whisker/notes/redteam-synthesis.md` (Tier 3)
- `packages/whisker/research/redteam/markitdown.md`
- `packages/whisker/research/redteam/firecrawl.md`
- `packages/whisker/research/redteam/olmocr.md`
- `packages/whisker/research/redteam/MinerU.md`
- Local grep: `packages/whisker/research/repos/markitdown/packages/markitdown/tests/`
