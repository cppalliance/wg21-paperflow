VERDICT: BUY mistune - already transitive via tomd; matches tomd QA AST pattern

# BUILD-vs-BUY: Markdown structure parsing for whisker MHS

Research date: 2026-06-25. Scope: heading hierarchy + future section/block tree for `whisker` (`packages/whisker/`). Hard constraints: deterministic, no LLM scoring, permissive license only, Python >=3.12, lib returns data, minimalism ladder.

---

## 1. Current regex approach

### Primary symbols (MHS path)

| Location | Symbol | Role |
|----------|--------|------|
| `packages/whisker/src/whisker/metrics.py` | `_HEADING_RE` | ATX-only: `^(#{1,6})\s+(.*?)\s*#*\s*$` |
| `packages/whisker/src/whisker/metrics.py` | `_FENCE_RE` | Toggle fenced-code skip: `^\s*(```\|~~~)` |
| `packages/whisker/src/whisker/metrics.py` | `_parse_headings()` | Line scan → `list[tuple[int, str]]` (level, text) |
| `packages/whisker/src/whisker/metrics.py` | `_build_heading_tree()` | Stack-nest levels → `TreeNode` for Zhang-Shasha MHS |
| `packages/whisker/src/whisker/metrics.py` | `mhs()` | Tree edit distance over heading trees |

Related regex-only heading scans (not MHS, same blind spots):

| Location | Symbol | Role |
|----------|--------|------|
| `packages/whisker/src/whisker/gates.py` | `_HEADING_RE` | Monotone gate: `^(#{1,6})\s+\S` (body only, after FM split) |
| `packages/whisker/src/whisker/bench.py` | `_FENCE_RE` | Block split for bench NID |
| `packages/whisker/src/whisker/match.py` | `_FENCE_RE` | Block split for Hungarian match |

### What it gets right

- ATX headings `#`..`######` on their own line (outside fences).
- Closing-hash ATX (`## Title ##`) via trailing `#*` strip.
- Fenced code blocks: naive open/close toggle on `` ``` `` / `~~~` (same pattern as gates/bench/match).
- Deterministic: pure line scan, no parser state beyond `in_fence`.
- Fast and zero extra dependencies.

### Blind spots

| Gap | Example | MHS impact |
|-----|---------|------------|
| **Setext headings** | `Title\n-----` | Missed entirely; hierarchy collapses or scores 1.0 incorrectly vs GT |
| **No front-matter strip in MHS** | `metrics.py` scans full string including YAML | FM lines not counted (good), but inconsistent with `gates.py` body split |
| **Raw inline markup in heading text** | `## **Bold** [x](u)` | Text axis is `"**Bold** [x](u)"`, not normalized prose |
| **HTML block headings** | `<h2>Section</h2>` | Missed (tomd rarely emits these; GT/other tools may) |
| **Headings inside blockquotes/lists** | `> ## Quote`, `- ## Item` | Regex may false-positive on `> ##` / `- ##` lines as ATX; parser nests them (see below) |
| **Indented ATX** | `  ## Indented` | Missed (CommonMark: not a heading) |
| **Lazy continuation / block structure** | Paragraph wrapping, list continuations | Line model ignores block boundaries except fences |
| **No section/block tree** | Only flat heading list → stack tree | Future section-order/anchor checks need block spans |
| **Fence edge cases** | Unclosed fence, nested fences, info-string lines | Toggle can desync; both regex and simple toggles share this class of bug |
| **Thematic break vs setext** | `---` alone | Not a heading (correct for regex); setext underline `---` under text is missed |

Verified with runtime probe (2026-06-25): mistune on `## **Bold** [link](u)` yields plain text `Bold link`; regex keeps `**Bold** [link](u)`.

---

## 2. Candidate parser table

| Candidate | License | Maintenance (2026) | AST / headings | Determinism | Already transitive for whisker? |
|-----------|---------|-------------------|----------------|-------------|--------------------------------|
| **mistune 3.2.x** | BSD-3-Clause | Active (3.2.0 Dec 2025, 3.2.1 May 2026; 3k+ GitHub stars) | `renderer="ast"`, `plugins=["table"]`; `type=="heading"`, `attrs.level`, `style` atx/setext, inline `children` | Pure Python, fixed plugin set, stable token order for fixed input+version | **YES** — `whisker → tomd → mistune~=3.2.0` (`uv tree --package whisker`) |
| **markdown-it-py 4.x** | MIT | Active (CommonMark reference implementation family) | Token stream via `MarkdownIt("commonmark")`; rich inline tokenization | Deterministic for pinned version | **NO** — workspace dev/test only (`pyproject.toml` root `[dependency-groups] dev`; `tomd/tests/test_html_render.py`) |
| **marko 2.2.x** | MIT | Active (2.2.3 May 2026; CommonMark 0.31.2) | Native AST / `ASTRenderer` dicts; GFM via `marko.ext.gfm` | Deterministic for pinned version | **NO** — not in whisker/tomd/markitdown lockfile |
| **stdlib** | PSF | N/A | None | N/A | N/A |

### markitdown / tomd transitive check

```
uv tree --package whisker
├── markitdown[pdf] → markdownify, pdfplumber, …   (HTML→MD conversion; no MD parser)
└── tomd → mistune v3.2.0                           (MD AST for QA + content check)
```

`markitdown` does **not** pull a Markdown parser for parsing MD structure. `markdownify` converts HTML to Markdown strings only.

---

## 3. Per-repo evidence (grep)

`packages/whisker/research/repos/<name>/` is **not present** in this workspace (redteam notes only). Evidence below is from workspace source + redteam synthesis.

| Repo / package | MD parser | Evidence | Used for |
|----------------|-----------|----------|----------|
| **tomd** | **mistune 3.2** | `packages/tomd/pyproject.toml`; `lib/pdf/qa.py:_AST_RENDERER`; `lib/check_content.py:_AST_RENDERER` | QA metrics (`heading_count`, `heading_level_skips`), content-coverage token stream |
| **tomd (tests)** | **markdown-it-py** | `packages/tomd/tests/test_html_render.py`: `MarkdownIt("commonmark")` | Assert list/heading **rendering** in tests only; not runtime |
| **whisker** | **regex** | `metrics.py:_parse_headings`, `gates.py:_HEADING_RE` | MHS metric; heading monotone gate |
| **markitdown** | none (MD parse) | `uv.lock` deps: beautifulsoup4, markdownify, … | Reference oracle conversion, not structure parse |
| **html-to-markdown-py** (redteam) | CommonMark vectors | `research/redteam/html-to-markdown-py.md`: `commonmark_spec.json` | External converter QA, not whisker |
| **html-to-markdown-go** (redteam) | commonmark plugin | `research/redteam/html-to-markdown-go.md`: `plugin/commonmark/` goldens | External converter QA |
| **opendataloader-pdf** (redteam) | external MHS | `research/redteam/opendataloader-pdf.md`: `evaluator_heading_level.py` | Published MHS benchmark axis; parser not in repo |
| **Other redteam converters** (markitdown, nougat, marker, …) | mostly none in-repo | `notes/cross-repo-qa-research.md`: "Most repos … no in-repo metrics" | Cite external benchmarks only |

**Pattern:** The only in-workspace Markdown **structure** parser is **mistune** in tomd. Whisker MHS is the outlier still on regex.

---

## 4. VERDICT: BUY mistune

### Why not KEEP-AS-IS

Regex is intentionally minimal but **wrong on setext**, **raw-markup heading text**, and **block structure**. MHS is a structural metric; line regex is not a structural parse. Acceptable for a bootstrap; not for a benchmark axis that must align with how tomd (and CommonMark) define headings.

### Why not BUILD-IMPROVE (regex)

Adding setext + FM strip + HTML `<hN>` patterns is a partial CommonMark reimplementation. Every fix duplicates parser rules mistune already ships. Violates minimalism ladder rung 4 ("already-installed dependency") and rung 6 (minimum that works). Does not deliver a block tree for future section/anchor work without a second pass.

### Why not markdown-it-py or marko

- **markdown-it-py**: excellent CommonMark fidelity and already used in tomd **tests**, but **not** a whisker runtime transitive dep. Adding it duplicates mistune's job and adds a second parser surface to pin.
- **marko**: MIT, solid AST, but **new dependency** when mistune is free and already canonical in tomd.

### Why mistune

1. **Free**: already installed via `whisker → tomd → mistune~=3.2.0` (no new `pyproject.toml` line required; optional explicit pin for clarity only).
2. **Precedent**: tomd `qa.py` and `check_content.py` use the same `_AST_RENDERER = mistune.create_markdown(renderer="ast", plugins=["table"])`.
3. **Correctness**: setext + ATX + fenced-code suppression verified; closed ATX handled.
4. **Determinism**: pure Python, version-pinned with tomd; no LLM, no network.
5. **License**: BSD-3-Clause (permissive).
6. **Future tree**: top-level token stream extends to block types (`paragraph`, `list`, `table`, `block_code`) for section spans and anchor checks.

### Implementation sketch (metrics.py only; not implemented here)

```python
import mistune

_AST = mistune.create_markdown(renderer="ast", plugins=["table"])

def _strip_front_matter(md_text: str) -> str:
    # Reuse gates._split_front_matter logic: return body after closing ---

def _inline_text(node: dict) -> str:
    # Walk heading children (text, emphasis, link, …); join raw text fields

def _parse_headings(md_text: str) -> list[tuple[int, str]]:
    tokens = _AST(_strip_front_matter(md_text))
    out = []
    for t in tokens:
        if t.get("type") != "heading":
            continue
        level = t.get("attrs", {}).get("level", 0)
        text = _normalize_text(_inline_text(t))
        if level and text:
            out.append((level, text))
    return out

# _build_heading_tree / mhs unchanged
```

**Front matter:** Required. Probe shows mistune parses `---\ntitle: x\n---` as `thematic_break` + setext heading `title: x` unless body is pre-stripped (same approach as `gates.py`).

**Top-level-only headings:** Match tomd QA documented limitation (`qa.py:_heading_level_skips`: headings inside blockquotes/lists not in top-level token list). Acceptable for WG21 papers; document in whisker CLAUDE.md if adopted.

**Optional shared module:** If gates/bench/match also switch later, extract `_AST` + FM strip to a small `md_structure.py`; not required for MHS-only first step.

### MHS score impact

| Corpus | Expected change |
|--------|-------------------|
| **tomd ATX output vs ATX GT** | **Small** — levels unchanged; heading text may drop inline markup (`**`, links) → relabel cost uses plain text (usually improves semantic match) |
| **GT with setext headings** | **Meaningful** — headings previously invisible now count (correctness fix; scores may drop vs old false-high) |
| **No-heading docs** | **None** — still 1.0 (`denom <= 1`) |
| **Guard baselines** | Re-bench after switch; expect minor MHS drift on papers with rich inline heading markup |

User constraint accepted: small score change OK when fixing correctness.

---

## 5. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **mistune version drift** via tomd pin | Medium | Couple whisker heading tests to same mistune major as tomd; bump together |
| **Front matter false headings** if strip omitted | High | Always strip FM before parse (gates pattern) |
| **Top-level-only headings** miss nested `> ##` | Low | WG21 papers don't nest headings; document; optional recursive walk later |
| **Heading text normalization change** (strip markup) | Medium | Document in CHANGELOG; re-run bench baselines |
| **YAML `---` inside body** | Low | Rare in papers; same ambiguity as any CM parser |
| **Parser ≠ author intent** on edge CommonMark cases | Low | Pin mistune; add invariant tests mirroring `test_metrics.py` + setext fixtures |
| **Duplicated parser config** (whisker vs tomd) | Low | Import shared constant from tomd only if willing to couple packages; else duplicate one-liner `_AST` (acceptable) |
| **Performance** | Low | mistune parse on full paper MD is ms-scale vs regex; negligible vs TEDS/lxml |
| **Future block tree scope creep** | Medium | Ship heading extraction first; block tree as separate BUILD step using same `_AST` tokens |

---

## References

- `packages/whisker/src/whisker/metrics.py` — current MHS regex
- `packages/tomd/src/tomd/lib/pdf/qa.py` — mistune AST QA (heading_count, heading_level_skips)
- `packages/tomd/src/tomd/lib/check_content.py` — mistune AST text extraction
- `packages/whisker/pyproject.toml` — whisker deps (tomd, markitdown)
- `uv.lock` / `uv tree --package whisker` — transitive mistune
- `pyproject.toml` (root) — markdown-it-py test-only comment
- `packages/whisker/notes/cross-repo-qa-research.md`, `gap-matrix.md`, `research/redteam/*.md` — prior QA research
