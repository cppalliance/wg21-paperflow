# 00 - Evidence Baseline (shared fact sheet)

Captured by Opus 4.8 on 2026-06-25 against the live repo + the populated data dir
(`$WG21_DATA_DIR = C:\Users\sabog\Desktop\cppalliance\cppalliance\data`).

**Every persona and every opus subagent MUST argue against these numbers, not against
guesses.** Cite a file:line or one of these runtime facts in every finding. Do not
re-file bugs already closed in `notes/redteam-synthesis.md` (re-verify them instead).

---

## 0. What whisker is (one paragraph)

Deterministic, no-LLM QA for tomd's PDF/HTML -> Markdown conversions. Three
independent lanes: **Lane 1 Stability** (`golden`, exact difflib vs `<pid>.expected.md`),
**Lane 2 Fidelity** (`bench`/`guard`, nid/teds/mhs/content_recall vs `<pid>.gt.md`),
**Lane 3 Comprehension** (`facts`, human-verified assertions). The default `whisker`
verb is a reference-free hard gate (structural gates + `unigram_coverage` floor) plus an
optional markitdown "oracle" advisory overlay. Verdict trichotomy: pass / review / fail.
Spec: `src/whisker/CLAUDE.md`.

## 1. Code size (src ~4145 LOC, tests ~1714 LOC)

| module | LOC | module | LOC |
|---|---|---|---|
| metrics.py | 573 | golden.py | 155 |
| __main__.py | 794 | gates.py | 134 |
| facts.py | 405 | constants.py | 146 |
| guard.py | 376 | __init__.py | 104 |
| bench.py | 273 | reference.py | 49 |
| score.py | 273 | anchors.py | 197 |
| match.py | 248 | calibrate.py | 161 |
| report.py | 257 | | |

Tests: 14 files. `test_score.py` 241, `test_guard.py` 225, `test_facts.py` 219,
`test_metrics.py` 179, `test_report.py` 154, `test_bench.py` 131, `test_anchors.py` 105,
`test_calibrate.py` 86, `test_invariants.py` 83, `test_match.py` 76, `test_gates.py` 67,
`test_golden.py` 61, `test_edit_distance_parity.py` 57, `test_reference.py` 30.

## 2. Test suite: GREEN

```
uv run --package whisker pytest packages/whisker/tests -q
=> 353 passed in 1.62s
```

All tests pass. Note for auditors: 353 passing tests is a quality signal for the CODE,
not for the VERDICT's real-world accuracy (no labeled corpus, see section 5).

## 3. Verdict distribution on 382 real converted papers

### 3a. Fresh schema-3 reference-free run (the trustworthy hard gate, no oracle)

```
uv run --package whisker whisker --all --no-reference --no-write --stats
=> 14 failed, 205 review, 163 passed (382 scored) in 86.1s   [exit 5]
```

- **pass 163 (42.7%)  review 205 (53.7%)  fail 14 (3.7%)**
- Flag rollup:
  - hard: `heading_monotone` 9, `unigram coverage < floor` 3, `no_empty_table` 2
  - soft: **misaligned regions 186**, unigram drift > 88, unigram coverage in review band 54,
    uncertain markers 30, qa_score < 6

### 3b. Stale schema-1 report.json on disk (older run, WITH oracle)

```
data/whisker/report.json : schema_version = 1  (code is now schema 3 -> STALE artifact)
counts: pass 126 (33%)  review 236 (62%)  fail 20 (5%)
source formats: html 198, pdf 184
hard flags: unigram coverage<floor 12, heading_monotone 6, no_empty_table 2
soft flags: 184 misaligned region(s), 147 reference text agreement low (advisory),
            75 drift, 64 unigram in review band, 30 uncertain
ref_nid: n=382 mean=0.836, below 0.85 advisory edge = 147 papers
unigram_coverage: mean=0.966, below 0.85 = 12, in 0.85-0.95 band = 64
```

### 3c. Observations worth pressure-testing (NOT yet conclusions)

- **Review tier is the majority** (54% ref-free, 62% with oracle). A QA tool that sends
  most outputs to a human provides weak triage unless those flags are precise.
- **The dominant review driver (186 "misaligned region(s)") is declared BENIGN by the
  spec** (tomd strips furniture; `REGION_SOFT_COUNT = 1` fires on a single region).
  CLAUDE.md "Soft signals": misaligned regions are "expected on clean papers".
- **The fail tier is mostly heading pedantry, not content loss.** 9 of 14 fails are
  `heading_monotone` (H2->H4 jumps). Examples `P3941R2/R3/R4` fail with
  `uni=0.999, drift=0.001` SOLELY on an H2->H4 jump. Only 3 of 14 fails are genuine
  content-missing (`unigram_coverage < 0.85`).
- With the oracle on, 147/382 papers trip the advisory `ref_nid < 0.85` flag; mean
  ref_nid is 0.836 (i.e. below the advisory edge on average), suggesting the edge may be
  mis-set for the markitdown oracle on this corpus.

## 4. Corpus lanes: NON-OPERATIONAL on real data

`packages/whisker/corpus/` contains only `README.md` + `EXAMPLE.facts.jsonl` (a template).
Zero real labeled members.

```
whisker golden --corpus packages/whisker/corpus
  => ERROR: no <pid>.gt.md papers found            (Lane 1 cannot run)
whisker facts  --corpus packages/whisker/corpus
  => ERROR: no <pid>.facts.jsonl with a staged candidate  (Lane 3 cannot run; EXAMPLE skipped)
whisker bench  --corpus packages/whisker/corpus
  => ERROR: no (candidate, reference) pairs found   (Lane 2 cannot run)
```

So **only the reference-free / oracle SCORE path (the hard gate) actually runs on real
data.** Lanes 1, 2, 3 are built and unit-tested but have no in-repo ground truth.

## 5. Calibration: NEVER PERFORMED

```
whisker calibrate --labels LABELS [--target-fpr 0.05] ...
```

`calibrate` requires a hand-labeled `--labels` JSON ({pid,label}). No such file exists in
the repo. `constants.py` header states plainly: the band edges are
**"PROVISIONAL ... not yet a value fitted on a labeled corpus."** Borrowed edges:
`UNIGRAM_COVERAGE_FAIL_EDGE=0.85`, `REVIEW_EDGE=0.95`, `REF_NID_ADVISORY_EDGE=0.85`
(edgeparse), `TEDS/MHS/NID/CONTENT_RECALL` floors 0.80/0.80/0.90/0.90 (OmniDocBench/
DP-Bench norms). **No measured TPR / FPR / precision exists for any threshold.**

## 6. Prior swarm (do not re-file these; verify they hold)

`notes/redteam-synthesis.md`: a 28-agent composer-2.5-fast swarm (June 2026) red-teamed
`guard.py` + `calibrate.py`. It FIXED 7 Tier-1 bugs: (1) baseline floors/slack now read,
(2) NaN/inf hard-fail `STATUS_INVALID`, (3) inverted-band guard in calibrate, (4) baseline
kind/schema validation, (5) duplicate-pid ValueError, (6) target_fpr range check,
(7) symmetric 4dp rounding. Tier-3 deferred items: exact golden lane, anchors, null-axis
eligibility (some since built in schema 3), set-F1/content_recall (built), per-axis
calibration, version-keyed baselines.

## 7. Dependencies / licensing facts

`pyproject.toml`: apted, grits-metric (MIT), lxml, markitdown[pdf], mistune~=3.2,
numpy, paperstore, pylatexenc, **rapidfuzz>=3.14.5,<4** (MIT, replaced GPL Levenshtein),
scipy, tomd. CHANGELOG 0.5.0 documents the GPL->MIT swap with frozen parity vectors in
`test_edit_distance_parity.py` (GPL import lint-banned there).

---

## Required report template (every persona writes exactly this shape)

```
# NN - <Persona name>

**Verdict:** usable | usable-with-conditions | garbage   (+ 1 sentence why)
**Confidence:** high | medium | low

## Findings
- [CRITICAL|HIGH|MED|LOW] <claim>. Evidence: <file:line OR runtime number from 00>.
  Impact: <why it makes the QA more/less trustworthy>.
  (repeat; 3-8 findings, ranked)

## False-pass hypothesis
<one concrete broken conversion that whisker would wrongly PASS, or "none found">

## False-fail hypothesis
<one concrete good conversion that whisker would wrongly FAIL/REVIEW, or "none found">

## What would change my mind
<the single piece of evidence that would flip my verdict>
```
