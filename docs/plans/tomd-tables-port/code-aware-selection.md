# Code-aware selection: design (2026-11-17)

Status: design, measured offline. Nothing is built.

## Problem

`select.select_tables` picks one reading per region by a fixed source priority:
tags > poll > grid > rules > codepair > tomd > content/records.
About eight pairwise overrides then let one reader displace another under narrow conditions.
For 123 of the 220 failing non-deck tables, a right reading (accuracy ≥ 0.9) existed, but the funnel lost it.

The overrides fail for reasons that have nothing to do with the table itself. Most of these are code:

- "Content refines rules" rejects record keys that start in lowercase, a test meant to catch wrapped
  sentences. Code identifiers start in lowercase (`vertices(g)`, `copyable_vertex_t<...>`):
  p1709r5-t28/t29/t40/t43, p3337r0-t4, p3258r0-t5.
- The same override is single-page only (p3005r0-t11, p4195r0-t6) and needs equal column counts.
- "A records reading of code is never emitted" bars a perfect reading (p3129r2-t4/t10/t11/t12).
- The wrap tests treat long identifiers as wrapped prose (p4148r2-t3).

Code tables are 23% of tables but 41% of the lost points. Their failures come in two opposite kinds:

| kind of code table (truth) | tables | failing | lost pts |
|---|---|---|---|
| listing comparison: 2 rows, one code block per column | 130 | 42 | 2.18 |
| records with code cells: 5+ rows | 61 | 25 | 2.17 |

When a code table fails:
- 17 have a listing split into lines;
- 13 have records merged;
- 27 are missing.

## Design

1. **Rank readings by evidence instead of by source.** Every reading of a region gets one score,
   built from evidence the pipeline already computes:
   - agreement with other readers (exact or partial);
   - conservation of the region's words;
   - extent: its share of the region, and how much falls outside it;
   - rule flags;
   - shape relative to the other readings: row, column and word counts, empty cells, multi-line cells;
   - source, as one input among the others.

   The highest score wins. This replaces the priority order and the pairwise overrides. Each
   override is a special case of "the reading with more evidence wins".
2. **Decide the code kind of a region before ranking.** When the region's text is code (monospace,
   statement punctuation), classify it as a listing comparison or as records with code cells. Then
   rank only the readings whose shape fits that kind: 2 rows for a listing, one row per record for
   records. The same decision replaces the prose-only tests that misfire on code:
   - the lowercase-key test;
   - the wrap-fit test on identifiers;
   - the ban on emitting records readings of code.
3. Gate, escalation and emission stay as they are.

## Measured offline (dev side, 8 sets, decks excluded)

Method:
- scratchpad `trace_all.py` (port venv) records every candidate for all 1038 key tables;
- `sel_eval.py` and `code_class.py` (poc venv) score each selection policy against truth.

Gains are in loss-breakdown points, measured on candidate accuracy against today's primary.
The ranker is a numpy logistic regression with about 30 features. It is trained leave-one-set-out:
each set's tables are scored by a model that never saw that set.

| policy | gain | tables better | tables worse |
|---|---|---|---|
| ceiling: best candidate always chosen | +5.90 | 134 | 0 |
| ceiling among readings that pass the rule checks | +4.51 | 87 | 0 |
| hand-written evidence orders (5 tried) | -2.57 to +0.47 | | |
| learned ranker | +2.44 | 67 | 32 (-1.40) |
| ranker + perfect code-kind decision | +3.68 | 75 | 24 (-0.52) |
| ranker + crude code-kind heuristic (149/215 right) | +3.02 | 74 | 31 (-0.95) |

- The ranker gains in 6 of 8 held-out sets; dev loses 0.30 and fresh5 is flat.
- Without the code-kind decision, the ranker breaks even on code tables (18 better, 18 worse).
- With a perfect code-kind decision, code tables gain +1.23 (26 better, 10 worse).
- The largest ranker wins:
  - rules → content, 23 tables, +1.17;
  - regions that today emit nothing because every reading fails a check, now taking the best
    reading, 24 tables, +0.80.
- The largest ranker losses:
  - p0957r8-t8 (tomd → tags), -0.29;
  - p3144r0-t5/t6/t7 (rules → codepair, code), -0.47 in all.

Reach: about 100 tables change, so this is a broad change by the many-tables rule.
The code-kind classifier is the weak part: the crude version gets half of the code value.

## Limits

- The ceiling is +5.9 pts. Selection cannot reach the 20–30 pt target alone. The rest is in:
  - tables no reader reads right: 59 tables, 6.17 pts;
  - slide decks: 85 tables, 3.31 pts;
  - tables nothing detected: 38 tables, 1.63 pts.
- Offline numbers score candidate rows. The emitted tables score higher on average (0.896 against
  0.855 for the primary candidate), because later steps repair cells. A real run through the
  pipeline is needed, with fresh7–9 as the single check.
- A learned model carries about 30 weights. It replaces a priority list and about eight
  hand-written overrides, but the weights need a fixed training set and a retraining procedure.
  An interpretable alternative (few features, hand-set) did not come close: +0.47 at best.

## Build order (if approved)

1. Code-kind classifier first. It is useful alone (it fixes the override tests) and needed by the
   ranker. Target: well above 149/215 on the truth kinds. Train on dev-side tables only.
2. Ranker inside `select_tables`, behind a switch. Train leave-one-set-out, then compare gate runs
   over the 8 dev-side sets against gd16, then one fresh7–9 check.
3. Remove the pairwise overrides the ranker makes redundant, and the code-blind tests.

## Step 1 result: code-kind classifier (2026-11-17, offline)

Rule, from a reading's body lines:
- the region is code when at least half of its lines are monospace;
- a code region is a **listing** when at least 30% of its monospace lines are complete statements:
  they end in `;`, `{` or `}`, or are a `//`, `/*` or `#` line;
- otherwise it is **records**.

The truth kind comes from the key's body cells: an average of 16+ words means listing, fewer than
8 means records.
- 188 of 194 code tables are classified right, leave-one-set-out. The threshold chosen was the same
  in all 8 folds.
- 12 of 778 non-code tables are called listing.
- A bracket-nesting and indentation signal added nothing, and was dropped.

Data: scratchpad `trace_lines.py` → `trace_lines_gd16.json`, `kind_probe2.py`.

Uses inside today's priority selection, simulated on the trace:

| use | tables changed | gain |
|---|---|---|
| listing: keep only the readings with the most coverage, then the fewest rows | 27 (13 better, 14 worse) | -0.65 |
| listing: among full-coverage readings, avoid row breaks inside a statement or block | 5 (4 better) | +0.45 |
| + prefer block cells over one-line-per-row readings with the same header | 8 (6 better, 2 worse) | +0.47 |
| records: accept identifier keys in "content refines rules"; emit records readings of code (estimated from stage 4) | about 10 | about +0.6 |

Why "fewest rows" fails: it picks readings that lost the header or part of the table (a tags reading
with 3 of 6 rows), and listings can hold several stacked pairs (p2392r3 has 7-8 rows).

Conclusion: the classifier is accurate, but wired into today's priority order it reaches only about
15-20 tables (about +1 pt). Each use is a separate narrow rule. Its value is as an input to the
evidence ranker: with a perfect kind decision, the ranker gains +1.23 on code tables, against a wash
without it.

## Step 2 result: the in-pipeline ranker. Correction: the offline estimate was inflated (2026-11-17)

The offline ranker (+2.44, and +3.0 to +3.7 with the code kind) used two features measured against
the truth region: how much of the key table's region a reading covers, and how much of it lies
outside. The pipeline has neither. Those features leaked the answer; the earlier table above
overstates what selection can gain.

Built `rank.py` and a hook in `select_tables`. Every usable reading of a region competes, with
features computed from pipeline evidence only (agreement, conservation, shape against the other
readings, area against the largest reading, code kind, statement splits, source). Traced all 8
dev-side sets: 971 key tables matched a ranked region, 828 with 2+ readings.

| policy (leave-one-set-out) | gain | tables better / worse |
|---|---|---|
| ceiling: best reading in the ranked region | +3.22 | 69 / 0 |
| pointwise logistic | -0.47 | 32 / 56 |
| softmax within the region | -1.27 to -0.10 | 25-33 / 28-39 |
| softmax, switch only on a large margin | +0.08 to +0.52 | 4-6 / 1-13 |

On honest evidence, ranking does not beat source priority by more than about +0.5 pts over a
handful of tables, which is narrow. The ceiling (+3.22) exists, but the pipeline's evidence does not
identify the right reading. Code tables lose most often.

Not built. `select.py` was restored, `rank.py` was removed, and the patch is kept in the scratchpad
(`ranked_selection.patch`, `rank.py.saved`). The code-kind classifier result (188 of 194) stands.
Its use inside selection is limited by the same lack of evidence.
