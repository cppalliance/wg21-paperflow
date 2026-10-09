# opus-E — Adoption Path Synthesis (final filter before synthesis)

**Meta-Reviewer:** E
**Re-verified personas:** 23 (Simplicity-Skeptic), 04 (MinerU-Dolphin), 08 (pandoc-html2text-markdownify), 10 (table-tools), 11 (opendataloader-PDFKit)
**Code read for verification:** `packages/whisker/src/whisker/gates.py` (full), `score.py` (full), `tables.py:36`, `constants.py` (floors)
**Date:** 2026-07-15

---

## 0. Verification of the Simplicity-Skeptic's LOC estimates against real code

The skeptic's effort rank is directionally right but under-counts three items because it ignored two hard constraints that the actual code imposes:

- **`_gate_front_matter(fm_lines)` (`gates.py:60`) has no access to the body.** It is called `_gate_front_matter(fm_lines)` in `run_gates` (`gates.py:156`). A title-vs-first-heading check needs the body, so MC1 forces a signature change to `_gate_front_matter(fm_lines, body)` plus the `run_gates` call site. That plumbing is real LOC the skeptic's "12" omits.
- **`_decide(...)` (`score.py:136`) receives only the `IdealPanel`, never `md_text`/`ideal_md`.** Any diff-line count (MC3 difflib, MC4 sub-resolution) must be computed up in `score_markdown` (`score.py:241`, where the texts exist) and threaded into `_decide` as a new parameter. The skeptic's "3 LOC in `_decide`" cannot see the texts.
- **No-bare-literal invariant.** `constants.py` floors are `NID_FLOOR=0.90`, `TEDS_FLOOR=0.80`, `MHS_FLOOR=0.80`, `CONTENT_RECALL_FLOOR=0.90`. The photocopy check wants `>= 0.99`, which is a **new** named constant (whisker forbids bare numeric literals in the scoring path, per `CLAUDE.md` invariants), not a reuse of an existing floor.

Corrected LOC (verified):

| MC | Skeptic LOC | Verified LOC | Why the delta |
|---|---|---|---|
| MC3 photocopy | ~3 | ~6-8 + 1 const | needs `md_text`/`ideal_md` threaded into `_decide` + new PHOTOCOPY edge constant; and see §4 (it cannot discriminate the failure) |
| MC4 sub-resolution | ~5 | ~8-10 | `import difflib` + `normalize_for_exact_lane` + count computed in `score_markdown` + new `_decide` param + band constant |
| MC2 TOC leak | ~10 | ~12 | fence-aware reuse of `_iter_body_lines` keeps it cheap; estimate holds |
| MC1 front-matter | ~12 | ~18-22 | `_gate_front_matter` signature change (add `body`) + first-H2 scan + normalize + reply-to shape; date sub-check needs `missing_regions` (deferred) |
| MC5 backstop | ~18 | split: ~6 (strip FM from LLM scope) + ~8 (fusion evidence cap, mostly already built) + ~30+ (deterministic outline diff, deferred) | the flat "18" conflates a cheap safe part with a heavy source-dependent part |

**Net:** the skeptic's ordinal ranking (MC3 < MC4 < MC2 < MC1 < MC5 by LOC) is roughly correct **as a byte count**, but LOC is the wrong axis for MC3/MC4 (see §4). The cheapest-to-write items are the least discriminating.

---

## 1. Per-MC final adoption recommendation

### MC1 — Front-Matter Truth
- **Files:** `gates.py` only (`_gate_front_matter`, `run_gates` call site). Date sub-check would also need `score.py` (`missing_regions` plumbing) — **deferred**.
- **Verified LOC:** ~18-22 for title-vs-first-H2 + reply-to shape (the two body/FM-only checks). Date-presence: +~6 and a `score.py` change → separate, Tier 3.
- **Gate type:** **SOFT (review)**, not hard. *This overrides the skeptic, who said hard.* Steelman (25) documents the exact false-flag: a paper whose title genuinely equals its opening section. With no labeled corpus (`CLAUDE.md` "Calibration status": edges provisional), whisker's own doctrine is "review beats a false pass." A wrong title should raise a human review, not hard-fail a shippable paper.
- **Steelman risk:** MED. False-flag on title==first-section papers. Mitigation: fire only when the normalized title EXACTLY equals the normalized first H2 AND that H2 carries a section-number prefix or a stripped trailing page digit (the TOC-leak fingerprint). Reply-to shape (`len>5`, missing `EMAIL_RE`) is near-zero false-positive.
- **New dependency:** none (stdlib `re`).

### MC2 — TOC Leak Detection
- **Files:** `gates.py` (new `_gate_no_toc_leak(body)` + `run_gates` call site). **No new `toc_detect.py` module** — reuse `_iter_body_lines` (`gates.py:78`) for fence-awareness, exactly as `_gate_heading_monotone` filters `if kind != "text"`.
- **Verified LOC:** ~12 for the unambiguous subset.
- **Gate type:** **HARD**, but restricted to two zero-ambiguity signatures: (a) a body line matching `^(?:#{1,6}\s+)?(?:table of contents|contents)\s*$` (case-insensitive), and (b) a heading whose page-digit-stripped normalized text duplicates an earlier heading where the earlier instance carried a trailing `\s+\d{1,4}$`. Both are TOC fingerprints a real WG21 body never produces. General duplicate-heading (no page digit) → soft, deferred.
- **Steelman risk:** LOW for the narrow signatures. Implementation requirement: MUST filter to `kind == "text"` so a `## Contents` inside a code fence never trips it.
- **New dependency:** none.

### MC3 — Photocopy-Golden Blindness
- **Files:** `score.py` (`_decide` + `score_markdown` plumbing) + new constant.
- **Verified LOC:** ~6-8 + 1 constant for the cheap panel-threshold version.
- **Gate type:** **WARNING (info only), NOT soft.** *This overrides persona 15, who said "soft flag."* Whisker has no info-only channel today (only `hard_flags`→fail, `soft_flags`→review, gates). A soft flag drives review, and the photocopy signal **fires identically on a genuinely excellent conversion and on a photocopy ideal** — the panel values `nid/mhs/recall >= 0.99` cannot tell the two apart, and neither can a difflib line count. So as a soft flag it is a false-fail generator on perfect papers. It has value only as a non-verdict annotation ("ideal panel is near-identical to the candidate, so its green proves nothing").
- **Steelman risk:** HIGH if wired as soft (demotes perfect conversions). LOW as info-only.
- **New dependency:** none. **But the honest fix (ideal-vs-SOURCE reconcile) needs a new pipeline (§4) → Tier 3.**

### MC4 — Sub-Resolution Defects
- **Files:** `score.py` (`score_markdown` computes diff, `_decide` new param) + `import difflib` + `normalize_for_exact_lane` from `golden.py`.
- **Verified LOC:** ~8-10 for the naive candidate-vs-ideal diff.
- **Gate type:** **DEFER.** The naive "`ideal_diff_lines > 0` → review" (persona 16) floods the review queue: a curated ideal is *deliberately* edited away from raw tomd output (`is_unedited_seed` blocks byte-identical seeds at bless time), so `diff > 0` is the normal state for every curated-ideal paper → mass false-fail. The useful narrow form (panel ~1.0 AND small nonzero diff) is coupled to MC3: on a photocopy ideal the dropped character is in BOTH sides → `diff == 0` → miss (persona 16's own caveat). The robust fix is an INDEPENDENT second conversion byte-diff (olmOCR source-anchored unit tests; `docx-parse-eval` reconcile) = new infra.
- **Steelman risk:** HIGH (naive form). 
- **New dependency:** none for naive; the robust form is new infra.

### MC5 — LLM Calibration
- **Files:** `tapetum_llm/adjudicate.py` + `tapetum_llm/pdf_judge.py` (strip front-matter from LLM scope); `tapetum_llm/fusion.py` (evidence cap, mostly already present).
- **Verified LOC:** split. (a) strip FM from LLM judgment scope ~6; (b) empty-evidence-pass→review is **already built** per `CLAUDE.md` ("a confident pass whose evidence was emitted but entirely dropped by grounding ALSO demotes to review"), so net-new is ~0-8; (c) deterministic source-vs-markdown outline diff for #282/#295 = ~30+, HTML-only, PDF-unsolved → **deferred**.
- **Gate type:** advisory (tapetum never gates; `CLAUDE.md`).
- **Steelman risk:** MED. Steelman explicitly warns: do NOT narrow `llm_clear_soft_review` — it undoes a proven 72 review→pass queue shrink. So MC5(a) is limited to removing front-matter from the LLM's scope (it only ever sees markdown; MC1-deterministic takes over the FM role), which is safe and pairs with MC1.
- **New dependency:** none for (a)/(b).

---

## 2. Priority-ordered adoption list

### Tier 1 — ship immediately (< 15 LOC, no new deps, low risk)

| # | Item | Files | Verified LOC | Gate type |
|---|---|---|---|---|
| T1.1 | **MC2 TOC-leak gate** (narrow: TOC-label line + duplicate-heading-with-page-digit) | `gates.py` (`_gate_no_toc_leak`, `run_gates`) | ~12 | **hard** |
| T1.2 | **Table-separator fix** (MC-adjacent, persona 19/10): `-{2,}` → `-+`, collapse the duplicated `_TABLE_SEP_RE` into ONE shared constant exported from `tables.py`, import it in `gates.py` | `tables.py:36`, `gates.py:132` | ~4 net | hard (fixes existing `no_empty_table`) |

T1.2 is not one of the 5 MCs, but it is the single highest-confidence lowest-LOC correctness win in the whole swarm (`|-|-|` is valid GFM, persona 19 confirmed against GFM §4.10; the regex is duplicated in two files, a latent drift bug). Ship it with T1.

### Tier 2 — ship after testing (15-30 LOC, needs new fixtures)

| # | Item | Files | Verified LOC | Gate type |
|---|---|---|---|---|
| T2.1 | **MC1 front-matter** (title≠first-H2 + reply-to shape; date sub-check deferred) | `gates.py` (`_gate_front_matter` gains `body` param) | ~18-22 | **soft** (not hard — see §3) |
| T2.2 | **MC5(a) strip front-matter from LLM scope** (+ rely on existing evidence-drop demote) | `tapetum_llm/adjudicate.py`, `pdf_judge.py` | ~6 | advisory |

Both need PR-replay regression fixtures (persona 24): p1122r3 for T2.1 (currently pinned `front_matter_valid: true`), and an adjudicate fixture for T2.2. Pandoc/html2text/markdownify (persona 08) contribute the **test pattern** here (golden AST round-trip, exact micro-corpus), not a runtime check.

### Tier 3 — defer (> 30 LOC, new deps/infra, or un-buildable now)

| # | Item | Why deferred |
|---|---|---|
| T3.1 | **MC3 real fix** (ideal-vs-SOURCE reconcile) | new pipeline, partially duplicates tomd; the cheap panel warning cannot discriminate photocopy from excellent conversion |
| T3.2 | **MC4 robust fix** (independent second-conversion byte-diff) | naive ideal-diff floods review (false-fail); robust form is new infra |
| T3.3 | **MC5(c) deterministic source↔markdown outline diff** (#282/#295) | ~30+ LOC, HTML-only, no reliable PDF outline (persona 18: flat font ladders mis-level) |
| T3.4 | **Platt/VERDI/bias-adjusted LLM calibration** | requires a LABELED holdout corpus that does not exist (persona 17 pt5; `CLAUDE.md` calibration status). Prerequisite-missing, not merely heavy |
| T3.5 | **MC1 date-presence sub-check** | needs `missing_regions` threaded from `score.py` into the gate |

---

## 3. Verification of the skeptic's rejections + where I disagree

### Rejections the skeptic got RIGHT
- **New modules (`toc_detect.py`):** correct. `gates.py` hosts `_gate_no_toc_leak` and reuses `_iter_body_lines`. A new module would be a one-function file with no second consumer — minimalism-ladder violation.
- **Platt / VERDI calibration:** correct rejection, but the reason is stronger than "over-engineering" — it is **un-buildable today**. Every calibration method in web card Q3 (VERDI Platt-scaling, bias-adjusted estimator, linear probes) needs a labeled gold set first. Whisker has none (`CLAUDE.md`: edges are "adopted from external repos, not fitted on our labeled corpus"). You cannot fit a calibrator with zero labels. Defer until a label corpus exists.
- **ideal-vs-source divergence pipeline as a first move:** correct to reject as heavy and tomd-duplicative — **with one honest caveat** (below).

### Where the skeptic is TOO AGGRESSIVE / mis-prioritized
1. **MC3 (#1, "3 LOC") and MC4 (#2, "5 LOC") are ranked as the top cheap wins. They are the cheapest to *type* and the least *discriminating*.** The MC3 panel signal fires identically on a healthy near-perfect conversion and on a photocopy ideal; the MC4 naive diff fires on every curated-ideal paper. A check that produces the same output on healthy and broken inputs is not a signal — it is noise with a threshold. LOC is the wrong ranking axis for these two. They belong in Tier 3, not at the top.
2. **The skeptic's rejection of ideal-vs-source leaves MC3 and MC4 genuinely OPEN.** The skeptic's own ranking implies MC3/MC4 are "done" at 3-5 LOC. They are not: the honest fix for both is exactly the ideal-vs-source / independent-second-conversion reconcile the skeptic rejected. The skeptic should state plainly that MC3 and MC4 are **deferred, not closed** — otherwise the ranking oversells coverage.
3. **MC1 as a hard gate** contradicts Steelman's documented false-flag and whisker's "review beats false pass." It should be soft.
4. **MC5 as a flat "18 LOC"** conflates a safe 6-LOC change (strip FM from LLM scope) with a 30+-LOC deferred one (deterministic outline diff that needs the source and is unsolved for PDF).

### Net verdict on the skeptic
Right on the *architecture* rejections (no new modules, no premature calibration, no heavyweight pipeline as a first move). Wrong on *prioritization and gate hardness*: LOC-minimalism pushed the two non-discriminating checks (MC3/MC4) to the top and hardened a check (MC1) that the calibration reality says must be soft. The minimalism ladder answered "what is shortest," not "what actually discriminates the failure" — the PRISM surprise-check the swarm is supposed to apply.

---

## 4. Tier-1 conflict check: MC1 + MC2 together

**No runtime interaction bug.** Both are pure functions added to `run_gates` returning independent `GateResult`s; there is no shared mutable state (gates are `@dataclass(frozen=True)`).

**Semantic interaction is benign and self-consistent:**
- On a TOC-leaked paper (MC2's target, e.g. p1122r3), MC1's "first body H2" scan may land on a leaked TOC entry like `## 1. Introduction 3`. Because MC1 normalizes away the trailing page digit and section-number prefix, that entry collapses to the same token as the genuine `## 1. Introduction`. So MC1's title-vs-first-H2 outcome is identical whether or not the TOC leaked. The two checks co-fire correctly on p1122r3 (wrong title AND TOC leak) without corrupting each other.
- Because I recommend MC2=hard and MC1=soft, `_decide` (`score.py:217`, `if hard: return VERDICT_FAIL`) short-circuits: on p1122r3 MC2's hard fail wins and MC1's soft flag is moot (correct — a hard-broken paper does not need a review nuance). On a wrong-title paper with NO TOC leak, only MC1(soft) fires → review (correct: a human looks). No double-jeopardy, no masking.
- Both correctly reuse the `kind == "text"` fence guard from `_iter_body_lines`, so neither trips on TOC-like or title-like text inside a code fence.

**Conclusion:** MC1 + MC2 are safe to ship together. They reinforce on the exact PR (#290 / p1122r3) that motivated both, and they do not interact destructively on any other input class.

---

## 5. Re-verification of my 5 assigned personas

- **04 MinerU-Dolphin** — CONFIRMED. Extraction pipelines, not QA judges. Only adoptable pattern is `test_e2e.py` typed-block self-scoring (`fuzz.ratio > 90`, `len(type_set) >= 4`), which whisker already covers via `content_recall`/facts. **Contributes nothing to any of the 5 MCs.**
- **08 pandoc-html2text-markdownify** — CONFIRMED. All three map `hN`→N mechanically; none validate title/YAML, detect TOC leaks, or gate heading levels against source. The one real nugget is the **regression-test pattern** (golden AST round-trip, exact micro-corpus, option-matrix), which feeds the Tier-2 fixture requirement, not a runtime gate.
- **10 table-tools** — CONFIRMED against code. `_TABLE_SEP_RE` with `-{2,}` is present and **duplicated** in `tables.py:36` and `gates.py:132`. `|-|-|` is valid GFM. → T1.2. camelot's reference-free `(accuracy/100)*(1-whitespace/100)` sidecar = defer (new signal, needs calibration).
- **11 opendataloader-PDFKit** — CONFIRMED. Null-eligibility already adopted (`bench.py`, and `ideal.teds/mhs` None-guarded at `score.py:206-215`). The corpus-mean regression backstop is a bench-lane guard, not a per-paper miss-class fix, and corpus means have *less* resolution than per-paper — **so it does not help MC4** and adds nothing new to the 5 MCs.
- **23 Simplicity-Skeptic** — re-verified in §0 and §3.

---

## 6. Model boundary (PRISM)

This adoption path would be revised if: (a) a labeled calibration corpus is authored — then MC3/MC4/MC5(c) and Platt-style calibration move out of Tier 3; or (b) an independent second-conversion oracle already staged per paper turns out to be cheaper than assumed — then the MC4 robust byte-diff becomes Tier 2. Open question I still cannot answer from the code: how many papers currently carry a golden ideal (governs whether MC1/MC4 review volume is a flood or a trickle) — this needs a run of `find_ideals_dir()` against the live fixtures, which I did not execute.
