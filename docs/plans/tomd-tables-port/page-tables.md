# Page tables: a model reads the page, tomd keeps the words (2026-11-20)

Status: built behind `--page-tables off|cache|live` (default off). The dev-side trial reproduces exactly through the
pipeline. fresh7–9 sample check (2026-11-21): about +9.5 pts estimated, no table worse.

## Problem

The ceiling study (2026-11-19) rebuilt every key table from the PDF's own words with perfect structure:

| pool | now | ceiling |
|---|---|---|
| dev side | 81.96% | 99.88% |
| fresh7–9 | 81.16% | 99.83% |

The text layer is not the limit. Of the 18 lost points, 11–12.5 sit in tables tomd emits nothing for: slide tables, ruled
status tables, unruled chronologies, and the pages of skipped papers. Better selection among tomd's own readings cannot
reach them, because no reader produces them.

## Design

The pattern is the reading judge's: tomd makes no model calls; requests go out and answers come back in.

- `lib/pdf/page_tables.py`:
  - `page_table_requests(doc)` makes one request per page. The id hashes the prompt version and the page PNG.
  - The page is rendered at 150 dpi, long edge at most 1568 px.
  - `INSTRUCTIONS` and `SCHEMA` give the trial prompt. The table definition is TRUTH_PROTOCOL's, and the output is rows of
    cells plus two continuation flags.
- `model_tables(...)` turns answers into UNCERTAIN table sections (source `page-model`):
  - **Verbatim words.** A model token is kept only when the page has it, as a word (each page word used once) or inside
    the page text. Every other token is dropped. The model proposes structure, never words.
  - **Continuation.** Pieces marked as continuing are joined across consecutive pages when their column counts agree. A
    repeated header row is dropped.
  - **Add, never replace.** A model table is used only where no table tomd selected overlaps it.
  - **Placement.** Model tables are added after the region scan, then their regions are removed from the prose like
    any table's.
- **Skipped papers.** A paper tomd would skip (slide deck, or a long paper taken for a standards draft) emits only its
  model tables, in page order, under a comment saying so.
- **Resolver** (`cli/page_tables.py`):
  - The cache is the paper's `pagetables` intermediate, holding `"<model>/<id>": {"tables": [...]}`.
  - `live` asks claude-opus-5-5 at effort medium, streamed, on a cache miss.
  - Answers are resolved before converting, so one conversion pass is enough.

## Evidence (trial and reproduction)

Trial: `work/paperflow/tools/mstruct_*.py` in the poc, $10.70.
- Sample: 24 dev-side papers in four strata:
  - 3 pilot papers;
  - 12 drawn in proportion to lost points;
  - 8 random;
  - the deck p4277r0 (181 of 233 pages asked).
- 294 key tables. fresh7–9 untouched.

| variant | sample | pool estimate | outside the deck |
|---|---|---|---|
| tomd today | 65.72% | | |
| add (built) | 81.39% | +9.3 pts | +2.8 ± 1.1 pts; 12 tables better, 0 worse |
| replace | 83.43% | +1.8 pts | −4.8 pts; 57 better, 54 worse |

- The deck accounts for +6.56 of the estimate, extrapolated from the 4.29 points seen.
- Through the pipeline (`pt_analyze.py` + `pt_compare.py`, trial answers re-keyed to request ids):
  - 81.39% on all 294 tables, the same score per table as the trial's add;
  - 85 tables better than today, 0 worse.

## fresh7–9 sample check (2026-11-21)

- Sample, $8.83, 623 pages:
  - 20 papers drawn in proportion to lost points. They hold 13.9 of fresh7–9's 18.84 lost points.
  - 10 random papers with no loss today, to catch damage.
- Run through the pipeline with the committed code (judge answers from the fresh7–9 cache), and compared per table with
  jt1 (81.16%).
- Tools: `pt_analyze.py`, `pt_estimate.py` in the poc.

| | |
|---|---|
| sample, 166 key tables | 58.22% → 71.50%; 38 tables better, 0 worse |
| pool estimate | **+9.5 ± 1.9 pts** (81.16% → about 90.7%) |
| lost points recovered, lossy papers | 51% on average |
| false or formatting tables in the sample | 24 → 33 |

- The gain is broad: 11 of the 20 lossy papers recover 79–100% of their lost points. 8 recover nothing: their losses are
  in tables tomd emits wrongly, which add-only does not touch.
- Unlike the dev side, no single deck carries the result. fresh7–9 has no skipped deck with key tables.
- This is a sample estimate, not a full run. The ±1.9 is the sampling error of the proportional stratum.

## Cost

- About $0.017 per page (Opus 5.5, about 3,250 input and 200 output tokens per page).
- The dev side has 4,957 pages, so a full dev run is about $85.
- Reruns with a full cache cost nothing.

## Open issues

- Dev side: the pool estimate rests on one deck (6.6 of 9.3 points). fresh7–9, with no such deck, estimates +9.5.
- Tables tomd emits wrongly are not touched (replace lost on the dev side). They hold most of what is left.
- Add creates false tables: 73 in the deck, 1–6 in most other papers. They cost no accuracy points, but they are noise in
  the output. No check filters them yet (e.g. TRUTH_PROTOCOL's not-a-table kinds, or `table_use`).
- Tokens matched only inside the page text (part of a word) are kept without a box; the cell uses the table's box.
- Rotated pages are skipped. Skipped papers emit tables only, with no prose.
- Live mode makes one call per page, so a 2,000-page draft costs about $34. It is opt-in only.

## Judged groups (2026-11-21)

- **Overlapping tables become judge requests.** Where model tables overlap tomd's, the overlapping tables form groups
  (`combine`). Each group whose readings differ becomes a reading-judge request.
  - A reading may hold several tables, separated by a `=== next table ===` row, so splits and joins are judged.
  - The prompt gains the table definition TRUTH_PROTOCOL uses (`judge._GROUP_NOTE`).
  - Only a high- or medium-confidence answer for the model's reading swaps the group.
- **Word placement.** Each token now takes the page word nearest the table's area, anchored on words that occur once on
  the page. Before, it took the first occurrence, so a common word could come from the header and stretch the table's box
  over the page. A swap then dropped tomd's front-matter table, and the oversized table was lost later. That was the
  cause of two −1.0 losses on fresh7–9.
- **Measured with cached page answers** ($3.2 of judge calls over three runs), scored per table against jt1 / ceiling:

| sample | today | add-only | judged groups | better / worse |
|---|---|---|---|---|
| dev, 294 tables | 65.72% | 83.92% | 85.20% | 127 / 16 |
| fresh7–9, 166 tables | 58.22% | 74.16% | 82.83% | 58 / 4 (worst −0.24) |

- The fresh7–9 pool estimate is **+12.4 ± 1.6 pts** over jt1 (81.16% → about 93.5%), with nothing lost on papers with no
  loss today.
- Open:
  - The dev side's p3128r3 loses about 0.3 per table on 10 tables when its group is swapped.
  - The table definition was added after the fresh7–9 losses were seen. The placement fix was the actual cause; the
    definition stays as the general alignment with the key's convention.
