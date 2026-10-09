# Meta-review B: contradictions, overclaims, consensus

Reviewer: meta-reviewer B. Date: 2026-07-22.
Scope: `00-baseline.md` + 17 archaeology reports (a01-a17) + 24 persona reports (c01-c22, incl. duplicate-numbered c17/c19/c20/c21 pairs) + 15 repo reports (r01-r15) + 5 web reports (w1-w5).
Method: every Verdict line, all CRITICAL/HIGH findings, all false-pass/false-fail sections read. Five headline numbers spot-checked against primary sources inside the repo (not just against the reports quoting them).

---

## 1. Disagreements (resolved)

Nine material disagreements found. Ordered by consequence.

### D1. Would the VLM channel have caught the PR #286 SF defect? (most consequential)

- **Optimistic**: `personas/c21-vlm-channel.md` verdict calls the dormant rasterize-transcribe-diff stack "the right independent channel for PDF geometry-lossy defects," conditional on table-page scoping and per-page diff.
- **Pessimistic**: `personas/c20-architecture-skeptic.md` scores shape (b) readback/transcribe as MISS/MISS on both incidents, citing corrupt-control failures (8/8 pass on corrupted P4182R0 readback).
- **Agnostic**: `archaeology/a06-vlm-pdf-qa.md` states flatly that no runtime experiment exists ("VLM never ran on PR #286"), that the as-built whole-document `text_nid` diff would likely false-pass six corrupted header tokens drowned in ~13k tokens, and that the readback artifacts in Auditv1 are text-mode, not VLM evidence.
- **Resolution: evidence favors a06.** Both extremes overclaim. c20's MISS verdict leans on readback corrupt-controls, which both a06 and c21-vlm themselves warn are not VLM transcription evidence (different input modality, different model path). c21-vlm's "right channel" claim has zero measured TPR behind it; the P0876R23 readback artifact where the pod misread `SF` as `F` even from markdown actively cuts against transcription confidence. Correct statement: VLM catch capability on PR #286 is **unproven in either direction**, and the as-built diff granularity (whole-doc similarity) would not surface it even if transcription were perfect. Any synthesis sentence of the form "VLM would have caught this" is unsupported.

### D2. Is `MAX_UNIT_CHECKS=5` a cost cap, and does cost justify it?

- `archaeology/a16-git-history.md` calls budget starvation "an intentional cost cap from day one of v6" (constants comment about not "spending 1+N calls"); `archaeology/a05-per-page-judging.md` warns that raising the cap "repeats the same tradeoff the corpus already rejected."
- `personas/c21-cost-realist.md` and `personas/c02-budget-scheduler.md` counter that marginal dollar cost is zero on an hourly-billed pod (SERVICES.toml), that the cap is a latency guard pattern-copied from `MAX_PAGE_ESCALATIONS`, and that checking all 9 routed units on PR #286 costs roughly +2 minutes wall clock.
- **Resolution: both true at different denominators; c21-cost/c02 win for the golden-PR case.** "Cost" in a16/a05 means wall-clock and false-review noise at fleet scale (c21-cost itself concedes ~23h serial for mailing-scale exhaustive checking). For golden PRs, which are rare and high-stakes, the arithmetic decisively favors exhausting the routed queue. The unresolved design question is that a single global constant serves both denominators; no report defends that.

### D3. What was the deterministic-lane verdict on PR #295: pass or review?

- `personas/c17-deterministic-lane-gap.md` (findings) says "PR #295 deterministic **pass** with four secno headings retained."
- `personas/c19-downstream-consumer.md` cites PR286-LLM-FALSE-CLEAR.md:168-169: deterministic lane verdict **review**, driven by advisory `ref_nid` 0.8081, not by the secno defect. `personas/c22-steelman.md` agrees ("det review, tapetum review conf 1.0").
- **Resolution: evidence favors c19/c22** (specific artifact line and value). c17-det-gap's "pass" is loose: gates were green but the tier verdict was review via an unrelated advisory oracle. Note the baseline itself never states the PR #295 deterministic verdict, which is how the drift crept in. Materially, c17-det-gap's core claim survives (nothing deterministic fired **on the secno defect**), but its verdict line as written is wrong.

### D4. When did `screen_pages` / per-page screening land?

- `archaeology/a05-per-page-judging.md` and `archaeology/a12-incident-timeline.md` date the screen+escalation implementation to commit 58a978c (2026-07-09), "validated live 2026-07-15."
- `archaeology/a16-git-history.md` explicitly corrects both: `git show 58a978c` contains no `screen_pages`; it landed in c59139c (2026-07-17) together with `MAX_UNIT_CHECKS` and the lexical sort.
- **Resolution: a16 wins, it ran the git commands.** Consequence: the budget-starvation mechanism and the screening architecture are the *same commit*, so "screening was validated before the cap was added" narratives in a05/a12 are chronologically impossible as stated (a live sim on 07-15 could only have run uncommitted code).

### D5. Which answer class is the primary cause of the PR #286 miss?

- `archaeology/a13-model-stack.md` frames class 3 as primary: even if pages 8/9 reached the model, DeepSeek's table understanding (CompTab EM ~25%, anti-calibrated confidence) would likely miss the wrapped cell.
- `personas/c01-router-recall.md`, `personas/c02-budget-scheduler.md`: class 2 primary; recall was lost before any model saw the pages, so model capability never entered the causal chain.
- `personas/c04-pdf-textlayer.md`: even under a raised cap, the flat `get_text("text")` packet destroys row geometry, so the model test a13 predicts failure on was never a fair test; class 1/5, making class 3 "untestable."
- **Resolution: layered, and `personas/c11-model-capability.md` adjudicates it correctly**: classes 1 and 2 explain where recall *was* lost on the actual incidents; class 3 bounds what recall is *attainable* after 1 and 2 are fixed. a13's "would have missed anyway" is a counterfactual with real supporting evidence (page-13 false clear at conf 1.0) but it is not the recorded cause. Reports that promote class 3 to primary cause of the incidents overclaim.

### D6. Did the LLM lane actually "fail" on the two PRs?

- `personas/c22-steelman.md`: no false-clear occurred; fusion capped both PRs at review via `source_aware_review_cap`, which is the advisory lane's designed contract, so "on triage, both runs succeeded."
- `personas/c02`, `personas/c08-fusion-semantics.md`, `personas/c19-operator-ux.md`, `archaeology/a12` (signature 4): the review verdict is a coverage artifact "masquerading as detection"; the operator report contains zero pointers to either defect, so operationally it is an "effective false-clear on the blocker."
- **Resolution: same facts, different framing; the operational evidence favors the majority.** c22 is factually right that no `clear` was emitted, and this matters for severity accounting. But c19-downstream's actionability audit (inspect report omits routed-unchecked unit IDs; review reason not surfaced) shows an operator cannot distinguish "capped for coverage" from "checked and suspicious," so the lane failed *as a verification instrument* even while honoring its *triage* contract. Both statements should survive into synthesis; neither alone.

### D7. Dormant VLM stack size: ~460 vs 788 vs 793 LOC

- `00-baseline.md`: "~460 LOC"; `archaeology/a02-llm-qa-integration.md`: 788 LOC (citing whisker CLAUDE.md); `archaeology/a06` and `personas/c21-vlm-channel.md`: ~793 LOC.
- **Resolution: unresolved scope discrepancy, almost certainly different file sets** (vision.py/vision_task.py/vlm_*.py/transcribe.py vs including readback.py etc.). Immaterial to any conclusion, but the baseline number and the archaeology numbers differ by 70%, so nobody should quote a LOC figure without naming the file list.

### D8. Required corpus size to certify recall >= 0.95

- `personas/c17-corpus-strategy.md`: Clopper-Pearson with zero misses gives **n ~ 59** labeled positives per defect class (math checks out: ln 0.05 / ln 0.95 = 58.4).
- `personas/c12-calibration.md`: "Wilson lower bound >= 0.95 requires **~2000** labeled defect instances (n=1500 -> 0.948, n=2000 -> 0.955)."
- **Resolution: c17-corpus is right; c12's figure is wrong by ~30x.** Standard Wilson lower bound with zero misses is n/(n+z^2): n=73 suffices at z=1.96; n=1500 gives 0.997, not 0.948. c12's 0.451 (13/13) and 0.313 (7/7) lower bounds also do not reproduce under Wilson or exact Clopper-Pearson (which give ~0.75-0.77 and ~0.59-0.65). c12's *qualitative* point (dev-replay n is far too small for "100% verification" claims) stands; its arithmetic must not be quoted.

### D9. Would fixing the lexical sort alone have saved PR #286?

- `archaeology/a12` "what would change my mind" implies numeric page ordering (with table-signal reservation) is the fix; casual readers of the baseline ("`page:13` < `page:2`") may infer the sort bug is sufficient.
- `personas/c02` and `repos/r15-routing-budget-survey.md` both compute that under numeric sort the top five severity-tied units are pages 1-5, still displacing 8/9; a fix needs cap >= routed count, class quotas, or signal-precision improvements.
- **Resolution: c02/r15, with arithmetic.** Lexical-sort repair is necessary hygiene but demonstrably insufficient alone. (Side note: c02's stated mechanism for the lexical bug, "char '3' < '2' after shared `page:1` prefix," garbles the comparison; the deciding characters are '1' vs '2' at index 5. Conclusion unaffected.)

Minor non-disagreements checked and dismissed: routed/unchecked page sets across baseline/c14/c15 (consistent once 2026-07-21 historical vs 2026-07-22 current runs are separated, per a12); "prior research predicted PR #286" (a01 says no, a04/a07/a09/a13 say yes: reconcilable, the defect *class* was predicted repeatedly, the *mechanism* - lexical displacement of a wrapped-cell page - never); c14's own prose ("eleven router + two budget") vs its table (twelve router + one budget), see spot-check #2.

---

## 2. Unverified single-source claims

Flagged because exactly one report asserts them, with derivation rather than measurement, or with unstated methodology:

1. **c12-calibration sample-size arithmetic** (n~2000; Wilson bounds 0.451/0.313). Single source, demonstrably wrong (see D8). Do not propagate.
2. **c21-cost-realist token/latency model** (54k tokens, ~3.5 min for +4 unit checks; 23h fleet-scale figure). Derived from other corpora's mean call latencies, never measured on the PR #286 run. Direction is safe, magnitudes are estimates.
3. **c20-coverage-contract object counts** ("399 enumerable objects on P1068R11"; "10/15 pages has_tables=True"). Persona counted them itself; methodology one line. Plausible, uncorroborated.
4. **a13's claim that DeepSeek would miss wrapped SF even when pages reach it** (CompTab EM ~25% transfer). External benchmark analogy, no in-repo run of the model on pages 8/9 exists. Testable in ~1 minute; currently speculation.
5. **c20-architecture-skeptic's MISS/MISS scores for the readback/VLM shape** on both incidents. Scored from corrupt-control artifacts of a *different* channel (text readback); no VLM run exists (see D1).
6. **c15-false-positive-hunter's projected FP signals** (YAML title spoof, script pollution, prose-heading routing producing false reviews). Static code reading, zero runtime confirmation on any paper.
7. **c19-operator-ux "operator would need N minutes to localize"**-style ergonomic quantities. No operator study; rhetorical.
8. **a11's claim that Auditv2 was "equally blind by design"** to golden-PR recall (all live-LLM scenarios blocked). Single report's reading of audit scope docs; no cross-report confirmed the blocking rationale.

Not flagged despite single-source: a16's git dating corrections (single source but backed by reproducible git commands) and a17's rule table (single source but load-bearing entries independently re-verified, see spot-check #1).

---

## 3. Consensus core (ranked by independent convergence)

1. **(~20 reports) PR #286 mechanism: pages 8/9 were router-visible and routed, then displaced by `MAX_UNIT_CHECKS=5` under severity-then-lexical ordering; no unit containing a poll table was ever checked.** Confirmed from git history (a16), scheduler code (c02), textlayer geometry (c04), runtime artifacts (baseline, c14, c15), ecosystem absence of any analogous cap (r15, w5), and fusion accounting (c08). Strongest-attested fact in the swarm.
2. **(~15) PR #295 mechanism: `html_outline.py` collects all heading descendant text including `span.secno`, so source outline == candidate outline and `heading_drift` is structurally silent; no prompt or contract rule encodes secno stripping.** Converges from code (c03, c09), prompt inventory (c05), contract mapping (a17), history (a01, a12), and seven external HTML converters showing the same flatten-by-default behavior (r09).
3. **(~15) No table-cell content comparison exists anywhere in either lane, and `PageUnit.has_tables` is computed but never read by the router.** Code-verified this review (see spot-check notes): router emits only `token_delta`, `low_recall`, `missing_captions`, `heading_drift`, `missing_code`. Converges from c01, c04, c10, c14, a06, a09, and the repo sweep showing cell-grid oracles exist off the shelf (r10, r11, r13).
4. **(~12) The LLM lane is architecturally subtract-only: evidence verification filters generated claims and cannot create recall; zero generated claims short-circuits the entire verification machinery into a vacuous pass.** c06 (grounding), c07 (validators), a03 (two-sided filter scoped to precision), a14 (langextract), r06/r12 and w5 (ecosystem: same generate-then-align asymmetry everywhere).
5. **(~10) No surveyed external system, 0/31 repos and 0/7 eval frameworks, gates document-conversion quality on LLM verdicts; deterministic anchors own recall everywhere.** r01-r15 (esp. r13, r14), w3, w5, a02.
6. **(~10) Both incident defects are deterministically decidable, and the highest-leverage fix is deterministic encoding (cell-grid compare, secno-aware heading check), not LLM improvement.** c17-det-gap, c18, c10, c20-arch, c21-cost, a17, r02/r07/r10/r11. Confidence on implementation difficulty diverges (c17-det-gap says P0 closes 2/2; c10 and r11 document borderless-table and in-cell-newline edge cases), but the direction is unanimous.
7. **(~8) Self-reported confidence carries zero (or negative) discriminative signal: 96/96 clear firings at >= 0.95, false clear at 1.00, escalation band dead (0/198).** baseline, a02, a13, c11, c12, c18, w4 (VERDI anti-calibration AUROC 0.32-0.49 as external replication of the pattern).
8. **(~8) Single-run verdicts are bounded by >= 25% rerun instability on the current serving config, and the fix is server-side (batch-invariant kernels), not prompt or sampling pins.** a08, a13, c11, c13, c18, w1, w4.
9. **(~5) The `review` verdict on both PRs was a coverage cap, not detection, and operator-facing reports contain no pointer to either defect.** c08, c19-downstream, c19-operator, c22 (agreeing on facts while disputing framing, see D6), a12.
10. **(4) Dev-replay labels actively encode both misses as non-defects (PR #295 labeled clean; PR #286 table defect absent), so the existing corpus cannot even measure the failure.** a15, c16, c17-corpus, c18.

---

## 4. Answer-class tally

Method: every CRITICAL and HIGH finding across a01-a17, c01-c22 (24 files), r01-r15 was assigned to its first-listed (primary) answer class. Hand count; treat as accurate to roughly +/- 10%. Web reports carry no findings-format entries and are excluded.

| Answer class | CRITICAL | HIGH | Total |
|---|---|---|---|
| 1. Contract-encoding gap | 32 | 60 | **92** |
| 2. Routing/budget starvation | 27 | 45 | **72** |
| 3. Model capability ceiling | 9 | 17 | 26 |
| 4. Verification asymmetry | 18 | 20 | 38 |
| 5. Goal mis-specification | 31 | 25 | **56** |

Reading:

- **The two actual incidents are owned by classes 1 and 2.** PR #295 is nearly pure class 1 (rule exists only in human docs; outline check structurally blind). PR #286 is class 2 (displacement) sitting on class 1 (no table signal emitter, no cell-content contract). Every report that traced the recorded causal chain ends in 1 or 2; class 3 never entered the chain because no model ever saw the defective content (c01, c11, c14 all converge here).
- **Hypothetical future misses are owned by classes 3 and 4.** Once routing and encoding are fixed, the residual risk inventory is: anti-calibrated false clears at full confidence (c11's page-13 case), >= 25% verdict flips (c13), and grounding attrition silently deleting true positives (c06, c12). These dominate the false-pass hypothesis sections of a13, c11, c12, c13, c06.
- **Class 5 is not a cause but the verdict frame**: its high count reflects near-every report concluding that "100% LLM verification" is ill-posed for an advisory, subtract-only lane (c18's metrology argument, c17-det-gap's reframe, the whole repos/web sweep). Class 5 findings answer the research question; class 1/2 findings explain the incidents.
- Class 3's low count is not exoneration: it is unmeasured (no run ever reached the model with the defect visible), which several reports correctly mark as untested rather than passed.

---

## 5. Number spot-checks

Checked against primary sources in the repo this review, not just against the reports quoting them.

1. **"38% of golden-contract rules unreachable" - SOFT, quote with range.** Source a17: 13/34 atomic rules reach neither deterministic code nor LLM prompts. The strict count in a17's own text is 10/34 (29%); 13 requires counting boundary rules (#13, #17, plus one PDF/HTML-asymmetric entry) as unreachable. Load-bearing entries re-verified directly: no `secno` handling anywhere in `tapetum_llm` (rg over the module returns nothing; `html_outline.py` joins raw descendant text at lines 73/112/155), and no table-cell or wrapped-cell rule in any prompt (`unit_judge.py`'s only "wrapped" reference is prose-unwrapping normalization, line 74). Verdict: direction solid, headline number is the generous end of 29-38%; c18 repeats 38% without noting the boundary.
2. **"13/14 scenarios die pre-model" - SUPPORTED, with an internal inconsistency.** c14's own scenario table shows 12 Router kills + 1 Budget kill + 1 Model kill; its verdict prose says "eleven router, two budget, one model." Either split gives 13/14 dying before any LLM call. Router signal inventory re-verified: `source_router.py` emits exactly `token_delta`, `low_recall`, `missing_captions`, `heading_drift`, `missing_code` (PDF path lines 181-233) - no table, math, cell, or footnote signal, consistent with the scenario kills. The 13/14 figure is fine; c14's prose/table mismatch should be fixed before external quotation.
3. **"0/31 repos LLM-gate" - SUPPORTED.** `packages/whisker/research/repos/` contains exactly 31 clone directories (counted this review); r14's per-repo table covers all 31 with zero gating mechanically on LLM signals, one advisory-only user (marker, offline benchmark triage). r13's companion figure (6/31 implement cell-grid-vs-GT comparison, all offline) is consistent.
4. **">= 25% verdict flip rate" - SUPPORTED as stated, but config-scoped.** Primary source `packages/whisker/research/llm-batching/20-sweep-results.md:32-33`: two identical c=32 reruns on 20 PIDs gave 15 pass / 5 review vs 10 pass / 10 review = 5/20 = 25% floor; `whisker/CLAUDE.md:554` records ">= 25% verdict-flip rate." Caveats the synthesis must carry: n=20, one rerun pair, measured at concurrency 32 on a MoE model without batch-invariant kernels. It is a property of the serving configuration, not an intrinsic model constant (w4's vLLM batch-invariance data shows the mechanism); quoting it as an immutable ceiling overclaims.
5. **"96/96 clear firings at >= 0.95 confidence" - SUPPORTED.** `whisker/CLAUDE.md:557`: "96/96 clear firings at >= 0.95 confidence," including the false clear at 1.00; c12 corroborates from the opus-B calibration sweep (0/381 sidecars below 0.50, escalation band 0/198). Sample is one 20-paper corpus plus incident artifacts; "anti-calibrated" is the right word, "always wrong at high confidence" would not be (most high-confidence clears were correct; the signal is *non-discriminative*, not inverted).

---

## Bottom line for the synthesizer

Nine material disagreements, all resolvable from evidence already inside the swarm. The consensus core (sections 3.1-3.4) is safe to build on. Three things must not survive into synthesis: any claim that the VLM would have caught PR #286 (D1), c12's sample-size arithmetic (D8), and the bare "38%" without its 29-38% boundary (spot-check 1). The two incidents are class 1+2 events; classes 3+4 are the residual-risk story after the deterministic fixes land.
