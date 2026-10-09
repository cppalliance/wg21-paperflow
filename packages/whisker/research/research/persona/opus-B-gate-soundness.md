# OPUS META-REVIEWER B - Gate Soundness + Adversarial False-Pass / False-Fail

**Domain:** gate soundness, false-negative (broken-but-pass) and false-positive
(good-but-fail/review) risk on the reference-free hard gate.
**Method:** every claim re-run independently against live code (`score.py`,
`gates.py`, `constants.py`) and the populated data dir. Mutated-markdown claims
were reproduced through the **production metric path**: I monkeypatched
`backend.get_paper_md` so `tomd.check_paper_content` recomputed the real
`ContentCheckResult` (coverage, drift, unigram, regions) for the mutated
markdown against the unmodified source on disk, then fed it to
`whisker.score.score_markdown`. **No repository file was modified, created, or
deleted except this report. `whisker --all` was not run.**

---

## Reproduced claims

| # | Claim (from cluster personas 03/21/23/24) | Reproduced? | Evidence (independent runtime / file:line) |
|---|---|---|---|
| 1 | Hard fail only on a failing gate or `unigram_coverage < 0.85`; shingle `coverage` and shingle `drift` NEVER gate | **YES** | `score.py:152-184` (`_decide` args = unigram, unigram_drift, regions, qa, uncertain, gates, ref only). Synthetic `ContentCheckResult(coverage=0.0, unigram_coverage=1.0)` on clean-gate md -> **`pass`, 0 flags**. |
| 2 | `unigram_coverage` is order-invariant multiset recall; reordering is invisible | **YES** | `check_content.py:621` (`_multiset_coverage`). cov=0.0/uni=1.0 -> pass (claim 1). Total reading-order destruction cannot fail by construction. |
| 3 | `P1040R10` reverse-all-sections + adjacent-row-swap -> **pass** (`cov` 0.9914->0.9759) | **YES (exact)** | runtime: `verdict=pass uni=0.9993 cov=0.9759 regions=0` (persona-03 reported 0.9759 exactly). |
| 4 | Attack generalizes; ~97.4% false-pass across passing table-papers | **YES (96.0% independent)** | My own random sample (seed 7) of 25 passing papers with >=3 `##` sections + a table, attacked with reverse+rowswap: **24 pass, 1 review, 0 fail = 96.0%**. The 1 review (`p3642r5`) had a low baseline `cov=0.952`. |
| 5 | `P3104R5` mutations (swap rows / swap section bodies / strip links / strip emphasis / corrupt code) -> **pass** | **YES (5 of 6)** | runtime: row-swap, section-body-swap, strip-links, strip-emphasis, **corrupt code-block identifiers (template->typedef, constexpr->volatile)** all `pass` (uni>=0.9983). **Deviation:** `merge_paragraphs` -> **review** (6 regions), not pass as persona-23 stated. |
| 6 | Column-mirror table cells survives hard gate, downgrades to `review` (not fail) | **YES** | `P1040R10` mirror-every-row -> `verdict=review uni=0.9993 cov=0.9497 23 regions`. (persona-03 saw 33; same verdict, same mechanism.) |
| 7 | `P4178R0` lives in the pass tier **uncrafted** with `uni=0.952, cov=0.837`, zero flags | **YES** | runtime: `verdict=pass uni=0.9517 cov=0.8366 regions=0` (11.5pp gap, no soft flag). Real reading-order gap already in the pass tier. |
| 8 | `P3941R2/R3/R4` hard-fail SOLELY on `heading_monotone` H2->H4 with `uni~=0.999` | **YES** | runtime: all three `fail`, sole hard flag `gate:heading_monotone:heading level jumps H2 -> H4`, uni 0.9985-0.9994, qa 95. |
| 9 | `lossy_table_count` / `table_parse_errors` stored but absent from `_decide` | **YES** | `score.py:67-68,249-250` (stored), not in `_decide` signature. `P3724R3/R4` -> **pass** with `lossy=1, qa=100`. |
| 10 | Mojibake survives the pass tier | **YES** | `P4211R0` -> **pass** `qa=80 moji=16` (qa 80 > `QA_SCORE_SOFT_EDGE=70`; mojibake_count never enters `_decide`). |
| 11 | The unigram floor genuinely catches missing words (true fails exist, rare) | **YES** | `P3978R0 uni=0.811`, `P4167R0 uni=0.837`, `P4231R0 uni=0.843` all `fail` on `unigram coverage < 0.85 (content missing)`. 3/382 = 0.8%. |
| 12 | Pass band is a knife-edge at 0.95 | **YES** | `P4136R0` -> **pass** `uni=0.9505` (0.0005 above `UNIGRAM_COVERAGE_REVIEW_EDGE`). Synthetic edge sweep: uni<0.85 fail, [0.85,0.95) review, >=0.95 pass (hard cliffs). |
| 13 | `no_empty_table` hard-fails (debatable) | **YES** | `P3290R4 uni=0.982`, `P4012R1 uni=0.909` both `fail` on `no_empty_table:table separator with no data row`. |
| 14 | Heading-monotone false-fail roster: meeting minutes H1->H3 + other depth skips | **YES (full roster)** | `N5035/N5037/N5043` fail H1->H3 (uni 0.947-0.953); `P3161R5`/`P3647R1` H3->H5; `P4160R0` H2->H4; `P3941R2/R3/R4` H2->H4. Exactly the 9 `heading_monotone` fails in baseline §3a. |

**Net: 13 of 14 claim-clusters reproduced exactly; 1 (claim 5) reproduced for 5
of 6 mutations.** The single divergence (`merge_paragraphs` downgrades to review,
not pass) makes whisker look marginally *better* than the persona stated, and
does not affect any verdict below.

---

## False-negative risk (broken-but-pass)

The pass verdict certifies exactly two things and nothing more: **(a) the source
word multiset is >=95% present in the markdown, and (b) the markdown is
structurally well-formed** (front matter present, headings monotone, no empty
code/table fence). Everything a downstream LLM relies on for *meaning* is
ungated:

- **Reading order / section order: categorically ungated.** Shingle `coverage`
  (the only order-sensitive signal) is explicitly "never a verdict flag"
  (`score.py:136-137`). Reproduced: `coverage=0.0, unigram=1.0 -> pass`. A fully
  scrambled document with every word present cannot fail or even review.
- **Table row/cell semantics: ungated.** Adjacent-row swaps preserve verdict
  (`pass`); column mirroring only reaches `review` via difflib region noise, never
  `fail`. `lossy_table_count` is computed and discarded by `_decide`.
- **Code fidelity: ungated.** Corrupting identifiers inside a fenced block
  (`constexpr`->`volatile`) keeps `pass` because those tokens recur elsewhere in
  the multiset. A WG21 normative code example can be wrong and ship green.
- **Up to ~5% token loss passes.** `P4136R0` passes at `uni=0.9505`. A dropped
  rare-vocabulary column, a lost short section, or removed math operators that
  duplicate elsewhere can stay under the 5% bar.
- **Visible encoding damage passes** while `qa_score >= 70` (`P4211R0`, 16
  mojibake, `pass`).

**Quantification.** On my own random sample, **96.0% (24/25)** of passing
table-papers survived an adversarial reorder+row-swap as `pass`. The pass tier is
**42.7% of the corpus** (163/382, baseline §3a). So the *latent* false-negative
surface is the entire pass tier for any defect class other than gross word loss
or structural malformation. This is **by design** (benchmark-aligned content/order
split) and is only a *false negative in practice if tomd actually emits such
corruptions*. The one piece of uncrafted evidence that it can is `P4178R0`
(`cov=0.837` live, `pass`): real reading-order degradation already sits in the
pass tier today. The documented defense (Lane 3 `table`/`order` facts) runs on
**0/382** papers (baseline §4), so nothing operational catches any of this.

**Risk rating: HIGH for order/table/code/semantic corruption, LOW for gross word
loss.** The instrument is sound for the one thing it gates (word presence) and
blind to everything else.

---

## False-positive risk (good-but-fail / cry-wolf review)

- **Confirmed hard false-fails: `heading_monotone`, 9/14 fails (64%).** Every one
  has `uni` 0.947-0.999 and clean content; they fail purely on heading-depth
  skips. `P3941R2/R3/R4` (WG21 wording section numbering `## 4` -> `#### 4.0.1`),
  `N5035/N5037/N5043` (meeting minutes title-as-H1 then H3), `P3161R5/P3647R1`
  (H3->H5), `P4160R0` (H2->H4). These are PDF/convention-faithful, not broken
  conversions. **9/382 = 2.4% of the corpus is hard-failed on typography.**
- **`no_empty_table` 2/14**: `P3290R4`/`P4012R1`. Debatable (could be faithful
  spacer rows or a tomd artifact); without labeled GT I rate these MED, not
  confirmed false-fails.
- **Review tier is a 53.7% majority dominated by a spec-benign signal.** 186
  misaligned-region flags vs 163 passes; `REGION_SOFT_COUNT=1` fires on a single
  region, yet the spec calls furniture-stripping regions "expected on clean
  papers" (`constants.py:43-47`). Persona-24's runtime sweep (70 papers, 18.3% of
  corpus, with *only* a misaligned-region flag) is consistent with the pass-tier
  invariant I confirmed: **every pass has `missing+extra == 0`**, so any single
  benign region forces review. The pass ceiling is structurally capped at 42.7%.

**Quantification.** Confirmed false-fail burden ~= **9/382 (2.4%)** hard +
**~18% review-tier furniture noise** = a cry-wolf rate roughly **20-25% of the
corpus** flagged on benign grounds. The asymmetry is the core defect: the gate is
**pedantically strict on heading depth** (a cosmetic, recoverable property) while
**totally blind to section/table/code reordering** (a semantic, non-recoverable
property).

---

## My independent verdict

**usable-with-conditions.** Confidence: **HIGH** (every material claim reproduced
through the production code path; the gate logic is small, deterministic, and I
exercised both edges).

The hard gate is *sound for its actual contract* and *mislabeled by its name*. As
a **"no gross word loss + well-formed markdown" detector** it works: it correctly
hard-fails the 3 genuinely lossy conversions (uni<0.85) and the structurally
broken ones, with deterministic, explainable flags. As a **"safe to ship /
faithful conversion" gate** (how a `pass` will be read by anyone downstream) it is
**not trustworthy**: 96% of passing table-papers survive adversarial semantic
corruption, and one real paper (`P4178R0`) already passes with badly degraded
reading order. The design choice (order off the content gate) is defensible and
literature-aligned, but it is only safe if (1) consumers treat `pass` as
"words present + well-formed", never "faithful", and (2) the Lane 3 fact layer
that is supposed to catch cell/order errors is actually populated. Neither
condition holds today. Combined with uncalibrated provisional thresholds and a
heading rule that hard-fails clean papers, the gate is usable as a coarse triage
floor but must not be the sole ship/no-ship authority.

Conditions for "usable" (unqualified): demote `heading_monotone` to soft/review
(or make it PDF-depth-aware), populate Lane 3 `table`/`order` facts on
table-heavy papers, and run `calibrate` on >=30 labeled papers to replace the
provisional 0.85/0.95 edges with measured TPR/FPR.

---

## Top-3 issues

1. **[CRITICAL] `pass` is a multiset-presence certificate, not a fidelity
   certificate, and the gap is exploitable at scale (96% reproduced).** Reading
   order, table row/cell assignment, and code-block fidelity are categorically
   ungated; the documented defense (Lane 3 facts) runs on 0/382 papers. A
   `pass` invites downstream consumers to trust a conversion whose section order,
   table semantics, or normative code may be wrong. *Fix:* add at least one
   operational order/table signal to the score path (e.g. a calibrated soft flag
   when `unigram_coverage - coverage` exceeds a fitted gap, or operational Lane 3
   cell-neighbor facts on table papers) and rename/document `pass` as
   "content-present + well-formed", not "faithful".

2. **[HIGH] `heading_monotone` as a HARD fail is a false-positive generator and
   is asymmetric with the reorder blindness.** 9/14 hard fails are clean papers
   (uni 0.947-0.999) failing on PDF-faithful heading-depth skips (WG21 wording
   numbering, meeting-minute conventions), while gross section/table reordering
   passes. The tool rejects cosmetics and accepts semantics. *Fix:* demote to
   review or normalize WG21 heading depth before gating.

3. **[HIGH] Zero calibration + knife-edge thresholds + benign-noise review
   tier.** The 0.85/0.95 edges are self-declared "PROVISIONAL" (`constants.py:11`);
   `P4136R0` passes at 0.9505 (a 0.0005 margin); the 53.7% review majority is
   dominated by the spec's own "expected on clean papers" misaligned-region flag
   firing at `REGION_SOFT_COUNT=1`. No measured TPR/FPR exists for any threshold.
   *Fix:* run `calibrate` on a labeled set; raise `REGION_SOFT_COUNT` above 1 so a
   single furniture region does not force review.
