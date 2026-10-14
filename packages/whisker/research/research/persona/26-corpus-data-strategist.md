# 26 - The Corpus / Data Strategist

**Verdict:** usable-with-conditions — the shared micro-corpus design and `calibrate` CLI are production-ready, but with zero real members (`00` §4–§5) whisker is structurally untrustworthy until a staged label pass (50 adjudications + 25 full corpus papers) is committed; the README describes format, not a sampling plan, and full `<pid>.gt.md` authorship is the cost bottleneck, not facts or labels alone.
**Confidence:** high

## Findings

- [CRITICAL] **The missing labeled corpus is the sole blocker to defensible trust claims.** Evidence: `00-EVIDENCE-BASELINE.md` §4 (corpus holds only `README.md` + `EXAMPLE.facts.jsonl`; `golden`/`bench`/`facts` all error); §5 ("Calibration: NEVER PERFORMED"; no `--labels` JSON; `constants.py:11-15` "PROVISIONAL … not yet a value fitted on a labeled corpus"). Impact: 163 pass / 205 review / 14 fail on 382 papers (`00` §3a) is **unlabeled prevalence**, not TPR/FPR; 353 green tests (`00` §2) validate code, not verdict accuracy.

- [CRITICAL] **Minimum viable trust path is two staged deliverables, not one monolithic corpus.** Evidence: `__main__.py:758-791` (`calibrate --labels` needs only `{pid, label}` JSON with `pass|review|fail`; scores via `score_paper(..., reference_engine=None)` when `unigram_coverage` absent); `corpus/README.md:15-17` (membership = `<pid>.gt.md` for lanes 1–3). Impact: **Phase A (calibration, ~1 week):** 50 human-adjudicated labels, no `gt.md`. **Phase B (regression guard, ~3–4 weeks):** 25 papers with `<pid>.gt.md` + `<pid>.facts.jsonl` (5–8 verified facts each) + blessed `<pid>.expected.md`. Phase A alone fits unigram edges and records TPR/FPR; Phase B alone enables guard/facts hard fails. Either phase without the other leaves a known blind spot (borrowed thresholds vs. no comprehension/table tripwires).

- [HIGH] **Sample 50 calibration labels with explicit stratification on the 382-paper pool; do not random-draw.** Evidence: source mix html **198** / pdf **184** (`00` §3b); ref-free tiers pass **163** / review **205** / fail **14** (`00` §3a); hard-fail drivers `heading_monotone` **9**, unigram `<0.85` **3**, `no_empty_table` **2** (`00` §3a); `calibrate.py:174-178` (needs both classes per fit). **Recommended 50-label matrix:**

  | Stratum | n | Selection rule |
  |---|---:|---|
  | pass / html | 8 | random from ref-free pass, prefer table or math if cheap metadata (`\|` count, `$`) |
  | pass / pdf | 8 | same |
  | review / html | 7 | from whisker review; human re-adjudicate (many are benign `misaligned region(s)` — **186** papers, `00` §3a) |
  | review / pdf | 7 | same |
  | fail / all formats | 10 | all **14** whisker fails + 6 human-found content-loss cases (inject if pool thin) |
  | edge / multi-column | 5 | top `(unigram_coverage − coverage)` gap from sidecars (tomd reflow signal, `CLAUDE.md:307-314`) |
  | table-heavy | 3 | ≥3 pipe tables in staged `.md` |
  | math-heavy | 2 | ≥5 `$…$` or `\(` spans |

  Hold out **10 labels (20%)** for reporting holdout TPR/FPR; fit on 40 only (`calibration-roc.md` §5: small-n overfit risk). Impact: pooled calibration on 50 i.i.d. papers hides subgroup FPR inflation (pdf vs html, table vs prose); without strata, the borrowed 0.85 floor may look calibrated while table-loss FPR stays unknown.

- [HIGH] **Author `facts.jsonl` cheaply from SOURCE; defer full `gt.md` to table/math strata only.** Evidence: `corpus/README.md:33-37` (facts authored from source PDF/HTML, not tomd output; `"checked": "verified"` is a separate bless step); `facts.py:17-23` ("handful of human-verified facts per paper are cheap"); `EXAMPLE.facts.jsonl` (7 lines covering all five types). **Cheap workflow per paper (~20–30 min):** (1) open source PDF/HTML; (2) write 5–8 facts: 2× `present` (abstract term + section title), 1× `absent` (page furniture), 1× `order` (3-item section flow), 0–2× `table`/`math` only if paper has tables/equations; (3) run `whisker facts --strict`, fix drafts; (4) set `"checked": "verified"`. **gt.md shortcut:** for prose-only papers, minimal `gt.md` = human-corrected tomd output (fix headings + one table block), not transcription from scratch; reserve full GT authoring (~2–4 h) for the 8 table/math stratum papers in Phase B. Impact: README's "annotation cost paid once" (`corpus/README.md:3-4`) is realistic for facts + partial GT, **not** for 25 fully hand-transcribed markdown files.

- [HIGH] **`calibrate --labels` contract is ready but misaligned with production verdict fusion.** Evidence: `__main__.py:753-755` (`pass|review|fail`); `827-830` (fail fit: positive = `fail` only; review fit: positive = `fail|review`); `827-838` (both fits use `unigram_coverage` only); `score.py:156-178` (live `_decide` also uses gates, drift, regions, qa, optional `ref_nid`). Labels file shape:

  ```json
  [
    {"pid": "P3100R6", "label": "pass"},
    {"pid": "P3941R2", "label": "fail", "unigram_coverage": 0.999}
  ]
  ```

  or `{"P3100R6": "pass", ...}`. Precompute `unigram_coverage` in labels JSON when adjudicating offline to avoid re-scoring. Impact: fitted edges report TPR/FPR for **coverage sub-rules**, not full `verdict`; promoting constants without noting this overstates review-volume control (205/382 review is **186** misaligned-region driven, `00` §3a, outside calibrate).

- [MED] **Defensible operating points: FPR ≤ 5% for hard fail; do not treat review edge as equally calibrated until region noise is fixed.** Evidence: `calibrate.py:41-44` (`DEFAULT_TARGET_FPR = 0.05`, "at most 1 in 20 good papers wrongly flagged"); `CLAUDE.md:318` ("FPR <= **10%**" — conflicts with code default); `redteam-synthesis.md` Tier 3 (per-axis/stratified calibration deferred). **Targets to commit with evidence:** (1) **fail edge:** max TPR at **FPR ≤ 0.05** on holdout good papers (`calibrate.py:184-187`); aim **TPR ≥ 0.80** on holdout bad (content-loss class, not heading-only fails); (2) **review edge:** secondary; accept **FPR ≤ 0.15–0.20** on good papers OR defer review-edge promotion until `REGION_SOFT_COUNT` is validated (`constants.py:47`, `10-threshold-constants-skeptic.md`); (3) **bench floors** (`NID/TEDS/MHS`, `constants.py:56-67`): fit in Phase B from guard rows, not Phase A. Impact: screening-gate ethics favor low false fail (ship bad) over low false review; 5% FPR on fail is defensible and matches `calibrate.py`; 10% is an upper bound for review-tier exploration only.

- [MED] **Corpus README plan is architecturally realistic but operationally incomplete.** Evidence: `corpus/README.md:1-73` (three-lane layout, provenance discipline, fact schema, run commands — no N, no strata, no holdout, no timeline); `CHANGELOG.md:50-52` ("Shared micro-corpus … amortize annotation cost"). What README gets right: single directory, facts independent of GT, conjunctive guard (`__main__.py:436-444`). What's missing: sample size (CLAUDE.md:318 says **30-50** labels; this persona recommends **50 fit + 10 holdout** and **25** full corpus members), adjudication rubric (heading-only fails like P3941R2 are **not** content-loss), and explicit statement that **labels JSON ≠ corpus membership**. Impact: a team following README alone will build file formats correctly but still lack a defensible sampling protocol.

- [MED] **Annotation cost estimate (one experienced WG21 reader, first pass).**

  | Deliverable | n | Time/paper | Total |
  |---|---:|---|---:|
  | Labels JSON (adjudicate pass/review/fail from source + whisker sidecar) | 50 | 8–12 min | **7–10 h** |
  | Holdout labels (separate adjudicator or delayed pass) | 10 | 8–12 min | **1.5–2 h** |
  | `facts.jsonl` (verified, 5–8 facts from source) | 25 | 20–30 min | **8–12 h** |
  | `gt.md` prose-only (corrected tomd, not full rewrite) | 17 | 45–90 min | **13–25 h** |
  | `gt.md` table/math-heavy (full human clean) | 8 | 2–4 h | **16–32 h** |
  | `expected.md` bless via `whisker golden --update` | 25 | 10 min review | **4 h** |
  | `calibrate` + promote + guard baseline `--update` | — | — | **4 h** |

  **Phase A total: ~12 h.** **Phase A+B total: ~55–90 h (~1.5–2 FTE-weeks).** Bench/guard on 25 papers with block matching may add **minutes per long paper** (`14-performance-scalability.md`: ~11 s for 632-block real paper). Impact: cost is dominated by **8 table/math GT papers**, not by facts or labels; skipping full GT on prose papers is the main cost lever.

- [LOW] **382 converted papers are a sufficient sampling frame; do not wait for more conversions.** Evidence: `00` §3a (382 scored); §3b (html/pdf near-balanced). Use `$WG21_DATA_DIR` sidecars for strata features (`unigram_coverage`, `coverage`, soft flags) when drawing the 50. Impact: delaying labeling until N>500 adds little stratification power compared to fixing review-tier noise and committing the first 25-paper guard corpus.

## False-pass hypothesis

A **table column drop** on a paper in the pass stratum with multiset token recall still ≥ **0.85** (repeated tokens in other columns) passes ref-free hard gate and would receive label **`pass`** if the adjudicator only glances at whisker's green verdict. Evidence: only **3/382** ref-free fails on unigram floor (`00` §3a); Lane 3 `table` facts exist precisely for this (`facts.py:13-15`, `corpus/README.md:60-62`); no deployed facts files (`00` §4). A labeled corpus without table-stratum facts and without human source reading would **encode this false pass into calibration negatives=0**.

## False-fail hypothesis

**P3941R2/R3/R4** (`00` §3c): `uni=0.999`, `drift=0.001`, fail solely on `heading_monotone` (H2→H4). If labeled **`fail`** without rubric distinction, calibration treats them as content-loss positives and **pulls the fail edge upward**, worsening false-pass rate on real content loss. Adjudication rubric must tag **`fail_structural`** vs **`fail_content`** in label notes (even if JSON stays `fail`) or exclude heading-only cases from fail-positive class for unigram calibration (`gates.py:105-109`, `02-calibration-statistician.md`).

## What would change my mind

Committed **`labels.json` (n≥50, documented strata + 20% holdout)** and **`packages/whisker/corpus/` with ≥25 `<pid>.gt.md` + verified facts**, plus one **`whisker calibrate --labels labels-train.json --target-fpr 0.05 --out thresholds.json`** run whose **`thresholds.json` reports holdout fail-edge FPR ≤ 0.05 and content-loss TPR ≥ 0.80**, and a **`whisker guard --corpus … --baseline …`** CI dry-run that fails on at least one injected table-fact regression. That bundle would flip verdict to **usable** for production triage on the labeled strata; until then, treat ref-free pass as **smoke test only**.
