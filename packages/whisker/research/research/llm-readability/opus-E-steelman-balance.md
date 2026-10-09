# Opus Meta-Reviewer E - Steelman + Balancing Decision

**Run question:** "Are our markdowns provably fully LLM-readable, theoretically and practically?"
**Scope:** whisker Lane 3 comprehension + comprehension corpus + tapetum_llm advisory lane + tomd output conventions (self-target, SHA `e66116a0`).
**Inputs weighed:** `00-baseline.md`, `05-web.md`, `17-steelman.md`, `22-blind-readback-methodologist.md`, and all 24 other persona reports (01-25). Swarm distribution: 24x usable-with-conditions, 1x garbage (persona 22, scoped to the read-back anchor).

**Recommended overall verdict band:** **usable-with-conditions.**
**Confidence:** high.

The design is right and externally validated; the proof is real but narrow. Neither the pile-on ("garbage, unproven") nor the steelman ("aligned, honest, done") is the fair reading. The honest one-line answer to the run question: **provably readable for the 2 corpus papers' authored facts; not yet proven for the ~200-paper fleet.**

---

## 1. Weighing the steelman against the harshest findings

The steelman (17) and the harshest reports (10, 16, 21, 22) are **not in contradiction** once you separate *architecture* from *coverage*. They are describing the same object from two ends.

### What survives as genuine strength (the steelman is correct)

1. **The architecture is the only externally validated pattern.** olmOCR-bench, ParseBench (169K deterministic rules, explicitly rejects LLM-as-judge and TEDS gating), and RealDocBench (field-level typed gold, decoupled from formatting) all converge on **deterministic, LLM-free comprehension assertions** (`05-web.md` Q1/Q3). Lane 3 implements the same five substantive olmOCR assertion classes (`facts.py:59-64`) with no LLM in the scoring loop. This is not an ad-hoc local invention; it tracks where the 2026 field is actually moving, and it is ahead of the structural-only benchmarks (OmniDocBench, opendataloader-bench) that still gate on edit distance. This is a real, load-bearing strength and no persona rebuts it.

2. **The layering respects every root invariant.** Deterministic CI gate (reproducible, no LLM) + one-time out-of-band empirical anchor + opt-in advisory LLM lane that *never gates*, with one-way import isolation. This is the correct decomposition for the CLAUDE.md determinism/model-sovereignty/fidelity invariants, not a compromise (17 finding 3; `03` confirms the deterministic lanes are pure and ordering-stable).

3. **The gate has teeth on what it covers.** The scrambled-table and scrambled-formula canaries genuinely flip (`test_comprehension_corpus.py:77-116`; `19` LOW confirms the ≥/≤ canary works at runtime), the anti-vacuous suite guard exists, and only `checked=="verified"` facts gate. Within the 2-paper corpus the comprehension assertions are real and would catch the cell/formula corruptions Lane 2 fidelity metrics wave through.

4. **Documented honesty is real and must not be re-billed as a defect.** The team's own CLAUDE.md admits provisional thresholds, 2-paper scale, and `ovr` being a misleading display composite. That is epistemic hygiene.

### What the strength does NOT cover (the harsh reports are also correct)

The steelman's own "Where the steelman ends" section concedes the decisive point, and it is right to: **the architecture being correct does not make the fleet claim true.** 198 of ~200 converted papers have zero verified facts; for them Lane 3 passes vacuously (`facts.py:128-130`), and the only remaining protection is the order-blind `unigram_coverage >= 0.85` multiset gate plus structural gates plus a never-gating advisory lane. So:

- The **design** is usable.
- The **2-paper proof** is usable-with-conditions.
- The **fleet claim** is unproven.

The steelman and the skeptics are weighing the same evidence at different scopes. Neither is wrong. The fair verdict is the one that names the scope explicitly rather than averaging them into mush.

---

## 2. Adjudicating persona 22's "garbage" verdict on the read-back

Persona 22 is the lone "garbage" verdict, and its label is a **scoping error, not a content error.** Its findings are largely valid; its verdict judges the artifact against a claim the artifact never made.

**As evidence for a fleet-wide "practically confirmed LLM-readable" claim: persona 22 is right, and this framing IS garbage.** You cannot extrapolate 17/17 question-answers on 2 hand-picked near-100% converts to ~200 papers. The specific confounds are real and correctly identified:
- Contamination is uncontrolled (public WG21 papers, front matter names the PID, 2026 frontier models can recall the source: `P4182R0.expected.md:3`).
- Questions embed answer lexemes that appear verbatim in both the fact strings and the markdown (`P4182R0.validation.md:35-38` vs `P4182R0.facts.jsonl:4,7-8`), so a pass can be substring retrieval rather than table-coordinate comprehension (TabVerse cell-lookup baseline ~9.9%, `05-web.md` Q2).
- No adversarial control: a corrupted `expected.md` was never shown to a reader model, so the "facts track what LLMs recover" inference is untested in the failure direction.
- n=17 on 2 papers cannot support a population claim.

Any language anywhere in the stack that reads the read-back as fleet confirmation should be struck. Persona 22 earns its keep here.

**As a documented one-time anchor for 2 papers: persona 22 over-reaches, and the artifact is sound.** The `validation.md` files explicitly scope the read-back as a one-time out-of-band anchor, *not* a CI gate and *not* fleet evidence (`00-baseline.md:61-64` records it as "NOT in CI"). Its purpose is narrow and legitimate: sanity-check that the deterministic facts correspond to something a downstream LLM actually recovers, so the CI gate can stand in for the LLM without putting an LLM in the loop. For that purpose:
- Run 3 on P4182R0 was byte-exact on the committed substrate and passed 8/8 (`P4182R0.validation.md:45-47`) — that is the anchor that matters; the runs-1-2 excerpt critique dents replication rigor but not the byte-exact anchor.
- The methodology (question-answering, not resemblance round-trip) is the *correct* choice per the field (RealDocBench uses exactly a fixed-extraction-LLM QA design).
- The contamination confound weakens the anchor but does not void it: the anchor's job is "are these facts answerable from this artifact," not "prove the model has no priors."

**Balanced framing to adopt:** Persona 22's *content* is a high-value HIGH-severity critique of over-claiming and should be folded into the conditions (holdout papers, archived prompts/bytes, adversarial control, questions authored independently of fact strings). Its *verdict label* ("garbage") is mis-applied: the read-back is **garbage as fleet evidence, sound as a scoped POC anchor.** In the swarm tally it should be read as a usable-with-conditions critique wearing a garbage label, not as a refutation of the stack. The one legitimate refutation it delivers is narrow: **delete any "fleet practically confirmed" language.**

---

## 3. Finding taxonomy: DESIGN flaw vs COVERAGE gap vs DOCUMENTED limitation

Fairness requires not counting the same thing three times and not billing documented honesty as a new defect.

### A. Already-known-and-documented (do NOT count as new defects)

| Finding | Reported by | Where documented |
|---|---|---|
| Provisional/unfitted thresholds (`0.85` etc.) | 10, 12, 20, 05 | `CLAUDE.md` Calibration status; `00-baseline.md:86-88`; `constants.py:11-15` |
| Corpus = 2 papers / POC scale | 16, 21, 12, 10, 18, 19 | `00-baseline.md:53-57,77-79` |
| tapetum never gates / advisory-only | 25, 12, 01 | `CLAUDE.md:361-371` |
| `ovr` is a misleading display composite | 11 | `CLAUDE.md:356-359` |
| Read-back is a one-time out-of-band anchor, not CI, not fleet | 22, 16 | `validation.md`; `00-baseline.md:61-64` |
| #277 conditions 1-3 open | 01, 03, 04, 07, 08, 25 | `00-baseline.md:71-76,84-85`; prior #277 synthesis |

These are transparency, not surprises. A reviewer who re-files them as fresh CRITICALs is inflating. They belong in the conditions list (work remaining), not the defect ledger.

### B. Genuine DESIGN weaknesses (architecture-level fixes needed)

| Finding | Reported by | Fair severity for run question |
|---|---|---|
| `present`/`absent`/`order` run on `normalized_text` (strips non-alnum): `!=`≡`==`, `C++`→`C` | 23, 10, 05 | **HIGH** (schema cannot express operators; real for WG21 payload) |
| No `code`/`xref`/`image-ref` fact type | 23, 16, 15, 12 | **HIGH** (whole risk classes un-assertable) |
| Table cell location is first-match-wins → decoy-table false-pass defeats the canary class | 10, 18, 07, 03, 11, 12 | **HIGH** (real; note threat model is lossy conversion, not adversarial markdown) |
| `_parse_pipe_tables` is the sole table input; emitted HTML tables (Tony/spec/NB-ballot) are invisible | 18 | **HIGH** (whole emission class unseen) |
| Math fold erases brace scope / case / root index (`x^{2k}`≡`x^2k`) | 19, 23 | **HIGH** (bounded; a documented deliberate trade vs KaTeX geometry) |
| Reference-free hard gate is order-blind token-multiset (reorder survives at `uni=1.0`) | 12, 20, 10 | **MED** (deliberate; shingle `coverage` sidecar exists but never gates; documented) |
| `_hard_split` not fence/table-aware | 24 | **MED** (advisory-only, ~6 oversized papers, `partial=True` already demotes pass) |
| `whisker --all` drops errored papers from machine-readable output | 09 | **MED** (audit-coverage gap, not a readability proof gap) |

### C. COVERAGE gaps (right architecture, under-populated — the dominant, fair theme)

- 2/~200 papers; 6 WG21 classes with zero coverage (multi-column, merged/nested tables, display math, code-heavy, footnote-dense, image-bearing) — `21`, `16`, `12`.
- Fact density ~0.007 facts/line, ~1 fact/page vs olmOCR's ~5 facts/page; 17 facts vs 7,010 — `21`, `10`, `18`, `20`.
- CI gates frozen `expected.md` snapshots, not live `paperstore` converter output — `16`, `04`, `21`, `14`.

These are the honest core. They are the #254 fleet claim being open, not a broken design.

---

## 4. Severity re-grading: which CRITICALs are actually MED/HIGH

Severity must be relative to the run question ("provably fully LLM-readable"). Applying that lens:

- **tapetum #277 grounding gap (confident `pass` with all evidence dropped, `adjudicate.py:237`).** Rated CRITICAL by **six** personas (01, 03-as-HIGH, 04, 07, 08, 25). It is a real, one-line-fixable, still-open, already-tracked gap. **But tapetum is advisory-only and is not in the readability proof path at all.** A confident-but-ungrounded advisory `pass` cannot make a markdown less readable; it can only mislead a human about whether to *look*. For the tapetum lane's own trustworthiness it is HIGH. **For the run question it is MED.** This is the single most over-weighted item across the swarm, and it is exactly the case the task flags ("CRITICALs actually MED given the advisory-only nature of tapetum"). **This is the severity I corrected most.**

- **tapetum non-determinism across MoE reruns (`03` CRITICAL).** Real, but explicitly out of the gate (`test_tapetum_llm_eval.py:12`: "NOT a CI gate"). Advisory-only → **MED** for the run question.

- **`check_facts` O(facts×doc) re-normalization (`06` CRITICAL).** At the current 17-facts/2-paper scale this is a non-issue; it only bites at olmOCR-scale, and the fix is trivial memoization of `normalized_text(md)`/`_math_surface(md)`/`_parse_pipe_tables(md)` once per call. **MED** (a scaling precondition for growing the corpus, not a present defect).

- **`_hard_split` seam corruption (`24` CRITICAL).** Advisory-only, ~6 oversized papers, `partial=True` already blocks a clean pass. **MED.**

- **What stays CRITICAL:** the **fleet vacuous-pass cluster** (`12`, `16`, `21`, `04`, `09`) — 198 papers with zero facts, Lane 3 vacuously green, order-blind hard gate as the only backstop. This is the finding that decides the fleet verdict and is not inflated. It is primarily a COVERAGE gap with one documented DESIGN sub-issue (order-blind gate). It should read as **CRITICAL-for-the-fleet-question, and the reason the fleet band is not "usable."**

Net effect: the swarm's CRITICAL count is dominated by tapetum-lane and scaling items that are MED for the actual question. Strip those and the load-bearing CRITICAL is singular and honest: **the fleet is not covered.**

---

## 5. Fairest verdict bands, split by scope

### (a) The 2 corpus papers (P4182R0, P4185R0): **usable-with-conditions (leaning usable)**

The deterministic gate provably establishes that the **authored, human-verified facts are recoverable** from the blessed markdown, backed by canaries and a byte-exact blind read-back. This is the strongest comprehension evidence any of the 28 surveyed converters produces. It is **not** "fully" readable in the literal sense of the run question, for two honest reasons: (i) 17 facts cover a small fraction of each document (`10`: ~1.8% by char on P4182R0), so unasserted spans are unproven; (ii) the read-back anchor has the methodological weaknesses persona 22 correctly lists. Verdict: the authored facts are provably readable and empirically anchored; drop the word "fully."

### (b) The ~200-paper fleet: **usable-with-conditions, honest answer = NOT YET PROVEN**

For the strict run question, the fleet answer is **no**: 198 papers carry zero comprehension coverage, Lane 3 is vacuously green for them, and the remaining backstop (order-blind `uni>=0.85` + structural gates + never-gating advisory lane) provably misses token-preserving semantic corruption (cell swaps, xref drift, code/operator garbling, reorder). The stack is **correctly positioned** to close this — the pattern is right and the tooling exists — but positioning is not proof. "Provably readable" is false for the fleet today; "on the only credible path to provable" is true.

**Overall run band: usable-with-conditions.** Design usable, POC proof usable-with-conditions, fleet claim open.

---

## 6. Top-5 conditions, ranked by leverage

Leverage = how much closing the condition moves the fleet answer from "not proven" toward "usable." This is where nearly every persona's "what would change my mind" converges.

1. **Grow a stratified comprehension corpus: 30-50 fleet papers (NOT near-100% converts), >=300 verified facts, >=5 papers per zero-coverage class, with a blind holdout read-back at >=90% fact recovery on the production self-hosted model stack.** Highest leverage: directly closes the dominant CRITICAL (2/~200 coverage) and is the single change that could flip the fleet band. Sourced from 21, 16, 12, 10, 20, 22 convergent asks.

2. **Extend the fact schema to the un-assertable risk classes: add `code`, `xref`, `image-ref` types and a raw/operator-sensitive surface mode for `present`/`absent` (so `!=` vs `==`, `C++` vs `C`, `[P1234R5]` revisions become assertable).** Without this, even a large corpus cannot gate WG21's highest-value payload; `normalized_text` collapse is a real DESIGN gap. Sourced from 23, 16, 15, 12, 10.

3. **Gate live converter output, not frozen snapshots, and fail on vacuous coverage.** Run facts against live `paperstore` markdown (or continuously rebase snapshots) so `tomd` regressions trip Lane 3, and fail `whisker guard`/`whisker facts` when a processed `.facts.jsonl` has `verified_count == 0` (mirror `test_comprehension_corpus.py:67-70` into the CLI). Cheap, high value; closes the CI-substrate mismatch and the vacuous-green contract footgun. Sourced from 16, 04, 21, 09, 14.

4. **Harden the deterministic gate's defeatable primitives: heading-anchored (not first-match) table identity, an HTML-aware grid builder for emitted `html_table`s, and a brace/scope-preserving math surface; add a CI canary per exploit class.** These are the genuine DESIGN fixes that make each added fact trustworthy against the decoy-table, HTML-table-blindness, and brace-scope classes; without them, more facts still miss the same holes. Sourced from 10, 18, 19, 07, 11.

5. **Land #277 blocking condition 1 (one-line `adjudicate.py:237` demotion of a `pass` whose evidence was all dropped + regression test) and ground-truth-audit the 72 review->pass clears; align the CLAUDE.md grounding docs to the code.** Lowest leverage for the *readability* question because tapetum is advisory-only (this is the severity I downgraded), but it is nearly free, already tracked, restores the advisory lane's honesty, and closes a documented doc-vs-code contradiction (08). Ranked last precisely because it does not touch the deterministic proof. Sourced from 25, 01, 08, 04, 07, 03.

---

## Bottom line

The stack is aligned with the best 2026 external practice, layered, canaried, and honest about its own gaps — the steelman is right about all of that. It is also a methodology demonstration on 1% of the fleet — the skeptics are right about that. Persona 22's critique is valid and should be adopted as conditions, but its "garbage" label mis-scopes a sound POC anchor against a fleet claim it never made. The fair verdict is **usable-with-conditions**, with the answer to the run question stated at its true resolution: **proven for the 2 corpus papers' authored facts, not yet proven for the fleet, and on the only credible path to becoming so.**
