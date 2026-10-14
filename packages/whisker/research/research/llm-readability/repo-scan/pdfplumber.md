# Repo scan: pdfplumber

**Does it verify LLM-readability?** **no**

pdfplumber is a PDF text/table **extraction** library (plain text, CSV, JSON). It does not emit markdown and has zero comprehension, downstream QA, LLM-judge, or fact-recovery gates on converted output. Its test suite validates **extractor fidelity** (exact cell strings, geometry counts, domain invariants), which is structurally analogous to olmOCR-bench's table/presence classes at the **pre-markdown** layer, not Lane 3 "can an LLM recover facts from our markdown."

---

## Findings

1. **[HIGH] Exact per-cell table assertions on real PDF fixtures** — issue-140 pins last row and column slices byte-for-byte; NICS pins corner cells. Evidence: `tests/test_table.py:64-100`, `tests/test_nics_report.py:112-115`. Impact: strongest portable pattern for whisker `table` facts in `facts.py`; tests that a named cell exists with expected neighbors, not just TEDS.

2. **[HIGH] Reference-free domain accounting invariant on parsed tables** — after `extract_table`, every numeric column must satisfy `colsum == (total * 2)` (month + YTD rows in NICS layout). Evidence: `tests/test_nics_report.py:81-85`. Impact: template for optional `invariants` block in whisker baseline/corpus beyond fuzzy metrics; catches wrong cell assignment when aggregate scores look fine.

3. **[HIGH] Committed byte-exact text goldens (library + CLI parity)** — SCOTUS transcript compared to `tests/comparisons/scotus-transcript-p1.txt` via `page.extract_text(layout=True)` and CLI `--format text`. Evidence: `tests/test_utils.py:382-398`, `tests/test_convert.py:299-314`. Impact: proves exact-output regression gates catch drift fuzzy scores miss; for whisker use normalized anchors/hashes, not byte-exact markdown (redteam agrees).

4. **[MED] Cardinality and shape invariants** — hard counts on tables, edges, intersections. Evidence: `tests/test_table.py:183-186` (`len(tables)==3`, row counts), `tests/test_ca_warn_report.py:81` (`len(p0.edges)==364`), `tests/test_ca_warn_report.py:141` (`len(ixs.keys())==304`), `tests/test_nics_report.py:55-56` (700 vertical / 508 horizontal edges). Impact: cheap whisker baseline fields (`table_count`, `heading_count`) that guard cannot express today.

5. **[MED] Pre-assert normalization before compare** — `fix_row_spaces` strips intra-cell spaces; layout golden strips trailing `\n`. Evidence: `tests/test_ca_warn_report.py:14-15`, `54-55`; `tests/test_utils.py:384-386`. Impact: whisker fact checks already normalize pipe tables; same discipline for `present`/`table` cell matching.

6. **[MED] Issue-numbered permanent regression fixtures** — one PDF per bug with dedicated test (e.g. issue-336 table order/counts, issue-140 strict lines). Evidence: `tests/test_table.py:176-186`, `tests/pdfs/issue-*.pdf` pattern via `tests/test_issues.py`. Impact: process model for whisker corpus members tied to named regressions.

7. **[MED] Multi-strategy extraction equivalence** — alternate horizontal strategies must yield identical `extract()` output. Evidence: `tests/test_nics_report.py:137-160`. Impact: orthogonal sanity check if tomd exposes alternate extract paths; not LLM-related.

8. **[LOW] Structure-tree exact snapshot** — full inline `SCOTUS` dict compared to `pdf.structure_tree`. Evidence: `tests/test_structure.py:1032-1036`. Impact: heading-hierarchy hash in whisker baseline; fuzzy MHS alone can miss tree drift.

9. **[LOW] Tolerance-sensitivity sweeps** — edge-merge tests assert count transitions across `snap_x_tolerance` / `join_y_tolerance`. Evidence: `tests/test_ca_warn_report.py:79-128`. Impact: calibration sensitivity reporting, not comprehension.

10. **[CONFIRMED ABSENT] LLM, markdown, comprehension, benchmark, downstream QA** — repo-wide grep over `*.py`/`*.md` finds no matches; README describes text/table extraction only (`README.md:1-7`, `21-22`). No olmOCR-style fact JSONL, no LLM judge, no reading-order comprehension beyond table-count ordering tests.

---

## Portable to whisker (ranked)

1. **Per-cell + neighbor table facts from real PDFs** — adopt olmOCR/pdfplumber pattern directly into `corpus/*.facts.jsonl` `table` type (`cell`, `up`/`down`/`left`/`right`/`heading`, `max_diffs`). Source: `tests/test_table.py:76-100`, `tests/test_nics_report.py:112-115`. Highest ROI for corpus authoring; already matches whisker Lane 3 schema.

2. **Domain accounting invariants** — optional baseline `invariants: [{"type": "col_sum", ...}]` for papers with known totals rows. Source: `tests/test_nics_report.py:81-85`. Reference-free; complements guard slack.

3. **Cardinality axes in guard baseline** — `table_count`, `edge-equivalent block counts` from bench. Source: `tests/test_table.py:183-186`. Actionable now per redteam.

4. **Normalization layer shared by facts and golden** — strip/normalize before assert (pdfplumber `fix_row_spaces`). Source: `tests/test_ca_warn_report.py:14-15`. Align with `facts.py` pipe-table parser.

5. **Anchor substring / line-hash snapshots** — not byte-exact markdown; subset of pdfplumber golden pattern. Source: `tests/test_utils.py:352-372` (goal line list), `383-398` (committed file).

6. **Issue-PID regression mapping** — one corpus member per fixed bug. Source: `tests/test_table.py:176-186`.

7. **Low priority:** structure-tree hash (`test_structure.py:1032-1036`), tolerance sweeps for calibrate sensitivity (`test_ca_warn_report.py:79-128`).

**Not portable as LLM-readability proof:** pdfplumber validates **extracted text/cells**, not markdown consumability by an LLM. Whisker must still run Lane 3 on **tomd output**, not raw pdfplumber cells.

---

## Cross-check vs redteam report (`packages/whisker/research/redteam/pdfplumber.md`)

| Redteam claim | Verdict | Evidence |
|---------------|---------|----------|
| NICS `colsum == (total * 2)` invariant | **CONFIRMED** | `tests/test_nics_report.py:81-85` |
| Committed exact-output goldens (`comparisons/*.txt`) | **CONFIRMED** | `tests/test_utils.py:383-398`, `tests/test_convert.py:312-314` |
| Inline `SCOTUS` structure tree snapshot | **CONFIRMED** | `tests/test_structure.py:1032-1036` |
| Exact per-cell / per-row assertions | **CONFIRMED** | `tests/test_ca_warn_report.py:59-77`, `tests/test_table.py:64-100` |
| Cardinality invariants (`len(tables)`, `len(edges)`) | **CONFIRMED** | `tests/test_table.py:183-186`, `tests/test_ca_warn_report.py:81`, `test_nics_report.py:55-56` |
| `fix_row_spaces` pre-assert normalization | **CONFIRMED** | `tests/test_ca_warn_report.py:14-15`, `54-55` |
| Embedded per-operation tolerances + sensitivity tests | **CONFIRMED** | `tests/test_nics_report.py:65` (`intersection_tolerance: 5`), `tests/test_ca_warn_report.py:79-128` |
| Multi-strategy equivalence | **CONFIRMED** | `tests/test_nics_report.py:137-160` |
| No ROC calibration (whisker ahead) | **CONFIRMED** | no calibrate module; thresholds are test-local constants |
| Table tests portable for whisker corpus authoring | **CONFIRMED with scope limit** | cell-level asserts are portable as **human-verified facts**; they test extraction correctness, not LLM comprehension of markdown |

**No contradictions found.** Redteam correctly frames pdfplumber as extractor-level exact gates, not LLM-readability. This scan adds: pdfplumber is **not a converter** (no markdown path), so the LLM-readability question is **out of scope** for the repo itself; only the **fact-assertion authoring pattern** transfers to whisker.
