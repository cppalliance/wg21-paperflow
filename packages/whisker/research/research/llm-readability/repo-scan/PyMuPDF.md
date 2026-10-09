# Repo scan: PyMuPDF

**Does it verify LLM-readability?** **no** (regression gates **committed output artifacts** — exact text, pickle table structs, pipe markdown, pixmap RMS — with version-keyed goldens; no fact assertions, no LLM eval, no downstream consumability proof for markdown destined for LLM pipelines)

Scanned: local shallow clone at `packages/whisker/research/repos/PyMuPDF` (read-only). pymupdf4llm builds on this library; this scan covers parent extraction/table QA only.

## Findings

### No LLM-readability or comprehension layer

Full-tree search finds no fact-assertion corpus, no LLM-as-judge harness, no RAG accuracy benchmark in `tests/`. Docs include a manual RAG chatbot sample (`docs/samples/national-capitals.py`, mirrored in pymupdf4llm examples) with no automated scoring.

### Version-keyed parallel goldens

Runtime selects expected artifact by `mupdf_version_tuple`:

| Test | Evidence |
|------|----------|
| Text extraction | `tests/test_font.py:72-77` branches `_expected`, `_1.26`, `_1.28` |
| OCR text | `tests/test_tesseract.py:82-85,107` |
| Annot pixmap | `tests/test_annots.py:241-244` (cited in redteam) |
| Warning text | `tests/test_2548.py:29-36` |

Prevents dependency bumps from passing against wrong-era snapshots.

### Table extraction QA (structural, not LLM comprehension)

**Pickle snapshot regression** — cell text exact, geometry approximate:

```15:37:packages/whisker/research/repos/PyMuPDF/tests/test_tables.py
def test_table1():
    ...
    assert old_data["extracts"] == extracts  # same cell contents
    ...
    assert abs(c1 - c0) < 0.2  # difference must be small
```

**Pipe markdown golden** — `tab.to_markdown()` exact string (`tests/test_tables.py:302-319`):

- Expected pipe table with `<br>` cell breaks (`tests/test_tables.py:308-315`).
- `assert md == md_expected` (`tests/test_tables.py:318-319`).

**Table finder counts/dimensions** — `test_3179`, `test_battery_file`, `test_dotted_grid`, `test_boxes_param` assert table count, row/col dimensions, extract grids (`tests/test_tables.py:280-374`).

These verify **extraction fidelity**, not whether an LLM can answer questions from the markdown (Q3 baseline distinction).

### Reading-order proxy: `gentle_compare`

`gentle_compare(w0, w1)` requires equal word count, **identical word strings in order**, rects within `1e-3` norm (`tests/gentle_compare.py:6-27`). Used in:

- `tests/test_mupdf_regressions.py:16,33,94`
- `tests/test_remove-rotation.py:30`

Word-order equality is a **geometric reading-order check** on raw extraction, not markdown-level order facts or LLM comprehension.

### Exact text goldens with CRLF normalize

`test_2608` compares block text to version-selected golden; strips `\r` before assert (`tests/test_font.py:78-85`).

`test_3842` OCR partial-page text exact match, version-keyed expected file (`tests/test_tesseract.py:82-107`).

### Heterogeneous per-property tolerances

Not one global slack:

| Property | Threshold | Evidence |
|----------|-----------|----------|
| Word rects | norm `<= 1e-3` | `gentle_compare.py:13-25` |
| Table cell geometry | `abs(c1-c0) < 0.2` | `tests/test_tables.py:37` |
| Pixmap RMS | `< 0.1` | `tests/test_annots.py:268` (redteam cite) |

Exact strings for text/cell content; approximate for layout.

### Markdown *input* support tests (not PDF→LLM-md output QA)

`tests/test_markdown_support.py`: MD→PDF round-trip (archive links, CSS, bad-unicode table/list extraction). Version-branch expected bytes for table recognition (`tests/test_markdown_support.py:106-163`). Tests **MuPDF as markdown renderer**, not PDF-to-markdown for LLM ingestion.

### Global test hygiene (meta-gate)

`conftest.py` wrap asserts empty `mupdf_warnings()`, unchanged `pymupdf._globals`, stable `JM_annot_id_stem`, optional fd-leak dump (`tests/conftest.py:142-159`). Determinism/side-effect guard, not readability.

### CI multi-version matrix

`test_quick.yml` / `test_multiple.yml` matrix MuPDF branches × OS (redteam 1.9); integration regression, not comprehension.

## Portable to whisker (ranked)

1. **Version-keyed parallel baselines** selected by toolchain tuple (`tests/test_font.py:72-77`) — map to `baseline["rows_by_toolchain"]` or sibling JSON files; never overwrite old toolchain row on `--update`.
2. **Per-axis / per-property tolerance** — exact for text/content, slack for geometry (`tests/test_tables.py:26-37`, `gentle_compare.py:13-25`); adopt per-axis guard slack (TEDS looser than NID).
3. **CRLF normalize before text golden compare** (`tests/test_font.py:80-82`).
4. **Structured table snapshot pattern** — exact cell content + neighbor geometry budget mirrors whisker Lane 3 `table` facts (`facts.py` neighbor checks); PyMuPDF pickle test validates the **extraction layer** whisker should treat as upstream, not duplicate in guard floats-only mode.
5. **Pipe-table markdown golden** for table-heavy corpus members (`tests/test_tables.py:302-319`) — candidate for whisker `table` fact seeds or golden sidecar hashes.
6. **Word-order gentle_compare** — inspiration for `order` facts on raw block/word sequences when validating reading-order axis beyond NID score.
7. **conftest-style determinism replay** — score same PID twice, assert metric identity (whisker meta-test).
8. **Do not adopt pixmap RMS or full byte goldens as whisker primary gate** — wrong cost model for ~200-paper corpus; structural counts/fingerprints suffice (redteam 1.2).

## Cross-check vs redteam report

Reference: `packages/whisker/research/redteam/PyMuPDF.md`.

| Redteam claim | Scan verdict |
|---------------|--------------|
| Version-keyed parallel goldens by `mupdf_version_tuple` | **Confirms** (`tests/test_font.py:72-77`, `tests/test_tesseract.py:82-85`). |
| Regression on committed outputs not metric snapshots | **Confirms** (text, pickle, markdown, pixmaps). |
| Heterogeneous tolerance per property type | **Confirms** (`gentle_compare.py:13`, `tests/test_tables.py:37`, `tests/test_annots.py:268`). |
| Pickle table cells + geometry split | **Confirms** (`tests/test_tables.py:15-37`). |
| `test_markdown` exact pipe markdown | **Confirms** (`tests/test_tables.py:302-319`); redteam cited `test_md_styles` — actual function name is `test_markdown`. |
| CRLF strip before exact compare | **Confirms** (`tests/test_font.py:80-82`). |
| conftest global-state hygiene | **Confirms** (`tests/conftest.py:142-159`). |
| No ROC/calibration module | **Confirms**. |
| gentle_compare / reading order | **Confirms** usage in `test_mupdf_regressions.py`, `test_remove-rotation.py`; not a dedicated markdown reading-order suite. |
| No LLM comprehension verification | **Confirms** — scan adds: markdown support tests are MD→PDF direction; no downstream LLM consumability benchmark. |

No material contradictions. Minor naming fix: `test_md_styles` → `test_markdown` in `test_tables.py`.
