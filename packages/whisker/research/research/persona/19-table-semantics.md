# 19 - THE TABLE-SEMANTICS EXPERT

**Verdict:** usable-with-conditions — table cell semantics are almost entirely ungated on the path that actually runs (382 papers); TEDS and grits_con exist only on the dormant bench lane, and grits_con is explicitly advisory.
**Confidence:** high

## Findings

- [CRITICAL] **The default `whisker` verdict has zero cell-level table gates.** Evidence: `_decide` hard-fails only structural gates + `unigram_coverage < 0.85` (`score.py:152-160`); `ref_teds`/`ref_mhs` are computed but **never flag** (`score.py:145-147`, `constants.py:80-83`). `table_parse_errors` and `lossy_table_count` are stored on `WhiskerResult` (`score.py:67-68,249-250`) but never read in `_decide`. Impact: **382/382 scored papers** can pass with scrambled table cells; the only table-related hard flag in the ref-free corpus run is `no_empty_table` (**2/382**, `00` §3a).

- [CRITICAL] **Lane 2 table metrics (TEDS + grits_con) do not run on real data.** Evidence: `packages/whisker/corpus/` has only `README.md` + `EXAMPLE.facts.jsonl` (`00` §4); **0** `<pid>.gt.md` anywhere in repo (glob); `whisker bench --corpus packages/whisker/corpus` => ERROR no pairs (`00` §4). Impact: `TEDS_FLOOR=0.80` (`constants.py:56-58`) and `_grits_con_score` (`bench.py:180-205`) are unit-tested but **never exercised** on the 382-paper production corpus; table fidelity is a dead lane.

- [HIGH] **grits_con is computed but explicitly never gated — the cell-F1 complement is decorative.** Evidence: `BenchRow.grits_con` docstring: "ADVISORY only … never gated until it has its own calibration" (`bench.py:68-71`); `GUARD_REGRESSION_AXES` lists `nid/teds/mhs/content_recall/overall` only — **grits_con omitted** (`constants.py:109`); `aggregate().below_floor` checks nid/teds/mhs/content_recall only (`bench.py:285-292`); `test_grits_con_is_not_gated` proves a cell swap drops grits_con but not `below_floor` (`test_bench.py:118-125`). Impact: even if bench were populated tomorrow, **localized cell corruption that GriTS catches would still not fail a paper** without a new floor + guard axis.

- [HIGH] **TEDS smooths over errors that matter at the 0.80 floor; GriTS is lower but also ungated.** Evidence: runtime on repo code — a single 2×2 cell swap (`| 1 | 2 |` → `| 1 | 9 |`) yields **teds=0.8333** (≥ `TEDS_FLOOR`) and **grits_con=0.75**; a 10×10 table with one wrong cell yields **teds=0.9917**, grits_con=0.9909 (denominator dilution via xpath-descendant norm, `metrics.py:503-514`). TEDS rename cost is normalized Levenshtein on char-token cell content (`metrics.py:431-442`), not per-cell F1. Impact: bench could **pass TEDS while a human reading row 3 col 2 gets the wrong value**; on large WG21 tables (~3.75 tables/paper mean, see quantification below) one wrong cell is nearly invisible to both metrics.

- [HIGH] **The only cell-level gate (`facts` `table` type) has zero production coverage.** Evidence: `facts.py:309-335` implements neighbor-graph checks (up/down/left/right/heading); `check_facts` gates only `checked == "verified"` (`facts.py:25-28,129-130`); corpus template includes one table fact (`corpus/EXAMPLE.facts.jsonl:5`); **0** `*.facts.jsonl` under `$WG21_DATA_DIR` (runtime scan); `whisker facts --corpus` fails on real data (`00` §4). Impact: the **direct "row 3, column 2" test** described in `CLAUDE.md:37-44` is implemented but **undeployed**; 167 table-bearing papers have no comprehension tripwire.

- [MED] **Reference-oracle table agreement is deliberately disabled as a signal.** Evidence: markitdown "structures tables differently" so `ref_teds`/`ref_mhs` are "report-only" (`CLAUDE.md:250-253`); `_decide` adds a review flag only for `ref_nid < 0.85`, never for ref_teds (`score.py:175-178`). Impact: the default oracle path (163 pass + 205 review on 382 papers, `00` §3a) **cannot steer reviewers toward table disagreements** even when markitdown and tomd differ on pipe tables.

- [MED] **Structural table gate `no_empty_table` catches syntax, not semantics.** Evidence: `_gate_no_empty_table` fails only when a GFM separator has no following data row (`gates.py:135-150`); 2 hard fails in ref-free `--stats` run (`00` §3a). `lossy_table_count > 0` on **10/382** papers in stale `report.json` (runtime) but is not a verdict input. Impact: **165+ table papers** with well-formed pipe syntax pass structural gates regardless of cell content.

- [LOW] **TEDS and grits_con share order-matched pairing, not Hungarian multi-table alignment.** Evidence: `_table_score` and `_grits_con_score` pair tables by index `k in range(max(len(cand), len(ref)))` (`bench.py:156-163,195-205`); buildvsbuy doc flags this as a known pairing mismatch vs GriTS TE mode (`teds-tables.md:126`). Impact: table **count/order** errors can depress both axes, but **within-table** swap/merge errors are where TEDS smoothing vs GriTS sensitivity diverges — the blind spot this persona targets.

### Quantification (table blind spot)

| Layer | Runs on 382 papers? | Cell-level gate? | Coverage |
|-------|---------------------|------------------|----------|
| Default `whisker` (gates + unigram) | Yes | No | 0/382 cell checks |
| `no_empty_table` (syntax) | Yes | No (structure only) | 2/382 hard fails |
| Oracle `ref_teds` | Yes (default) | No (advisory absent) | 0 flags (`score.py:175-178`) |
| `lossy_table_count` / `table_parse_errors` | Reported | No | 10 lossy / 0 parse errors (sidecar only) |
| Lane 2 `teds` + guard floor | **No** (no gt.md) | Would gate teds only | 0 papers |
| Lane 2 `grits_con` | **No** | **Never** (by design) | 0 papers |
| Lane 3 `table` facts | **No** (no facts.jsonl) | Would gate if verified | 0 papers |
| Papers with ≥1 pipe table (candidate `.md`) | 167/382 (**43.7%**) | — | mean 3.75 tables/paper |

**Bottom line:** On the only operational path, **~44% of the corpus carries tables that can fail semantically while every table metric is either absent, advisory, or non-operational.** Cell-level detection coverage is **0/167 table papers (0%)**.

## False-pass hypothesis

A WG21 paper with a 6×4 feature-comparison table: tomd swaps two body rows (same tokens, wrong row/column assignment) but keeps all cell text in the document. **Default whisker passes:** `unigram_coverage` stays ~1.0 (no words dropped, `metrics.py:372-389`), structural gates green, no table facts. If bench were run against a blessed `<pid>.gt.md`, **TEDS could still pass** (runtime row-swap on 3×2 grid: teds=0.5556 — below floor; but a **single swapped pair in a large table** scores teds≈0.99 while grits_con≈0.99, both ungated). A `table` fact pinning one cell's `right`/`down` neighbors would fail (`facts.py:327-334`) — but none exist in production.

## False-fail hypothesis

A paper with a valid GFM table whose header row uses `---` underline styling that tomd emits as an H2→H4 heading jump elsewhere: **review/fail on `heading_monotone`**, not on table content (`00` §3c: P3941R2/R3/R4 fail with uni=0.999 solely on H2→H4). Table semantics are innocent; heading pedantry dominates the fail tier (9/14 ref-free fails).

## What would change my mind

A labeled micro-corpus (≥30 table-heavy `<pid>.gt.md` + verified `table` facts) with measured **TPR/FPR** showing that gating `grits_con` (or TEDS) at a calibrated floor catches real cell errors without exceeding 10% false-fail on clean papers — plus evidence that at least one production table corruption in the 167 table papers is caught by that gate and would otherwise pass today.
