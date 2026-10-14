# Opus-C - Meta-Review: Architecture & Economics Cluster
## (11-product-decision-skeptic, 13-steelman-det-first, 15-gating-cartographer, 21-cost-latency-accountant, 22-sovereignty-guardian, 25-evidence-historian)

**Role:** Meta-Reviewer C, stage 2. Re-verify this cluster's load-bearing claims against live
clones (`--no-ignore`), primary rerun evidence, and arithmetic; answer the operator's course
question. **Method note:** used `Get-ChildItem`/`Read`/direct file reads for the gitignored
`packages/whisker/research/repos/` tree per the `00-baseline.md §6` root-cause. One tooling
wrinkle found and worth flagging to meta-review D: PowerShell `Get-ChildItem -Recurse` silently
returned **empty** for `opendataloader-bench-tmp` (a nested `.git` clone) even with
`Test-Path` = True; `cmd /c dir /b` and direct `Read` both worked. Anyone re-verifying that
specific clone should not trust a `-Recurse` empty result as "file absent."

---

## Verdict on cluster

**Usable-with-conditions, high confidence.** All six persona reports converge without internal
contradiction: the central claim (0/31 repos mechanically gate accept/reject on an LLM quality
signal) survives sharpening (P15's taxonomy), survives a second evidence pass (P25's anchor
audit), survives PR-replay re-verification (P11/P13's 4/9→8/9), survives cost arithmetic (P21),
and is *tightened* rather than loosened by the sovereignty constraint (P22). I independently
re-verified 4 of P15/P25's spot-checks directly in the live clones and the primary PR-replay
transcript behind P11/P13's numbers — all held. The one place this cluster is not settled is
**P11's ROI framing**: it does not contradict the architecture verdict, but it is the strongest
version of "wrong path" available from this evidence, and the course-question answer below
engages it head-on rather than dismissing it.

---

## Findings table

| Claim | Verdict | Evidence |
|---|---|---|
| Central claim: 0/31 repos use an LLM judge signal to mechanically gate accept/reject/CI-block | **CONFIRMED** | `00-baseline.md:43-55`; P15's G9 row "NOT FOUND" (`15-gating-cartographer.md:39`) restates it with a testable definition (signal→effect→blast-radius); no counter-example surfaced by any of the 6 personas or by my own spot-checks. |
| P15 spot-check: marker `verify_scores.py:12-22` — CI raises only on deterministic heuristic mean < 90 / table TEDS mean < 0.7 | **CONFIRMED** | My own read of the live clone: `verify_scores.py` lines 5-13 (`verify_scores`, raises `ValueError` on `marker_score < 90`) and 16-22 (`verify_table_scores`, raises on `avg < 0.7`). Exact line match to P15's citation. |
| P15 spot-check: baseline's olmOCR anchor `tests.py:114-125` is stale; real gate logic is `tests.py:150-176` | **CONFIRMED** | My own read: lines 114-125 are `BasePDFTest.run`'s docstring + `raise NotImplementedError` (abstract method). `TextPresenceTest.run` (the actual `fuzz.partial_ratio`/threshold gate logic) starts at line 150 and runs to 182. Baseline (`00-baseline.md:27`) must be corrected to `tests.py:150-176`. |
| P25 anchor correction: firecrawl "124x `toContain` anchors" is drifted; live count is 348 | **CONFIRMED** | My own `rg --no-ignore --no-ignore-vcs -o` count over `firecrawl/apps/api/src/__tests__/**`: **348** matches of `.toContain(` across 36 files. Matches P25 exactly; baseline's "124x" (`00-baseline.md:35`) is stale and must be corrected. |
| P25 anchor correction: `opendataloader-pdf/run.py` does not exist; regression-gate logic lives in the companion bench clone | **CONFIRMED** | My own check: `Test-Path packages/whisker/research/repos/opendataloader-pdf/run.py` = **False**. `opendataloader-bench-tmp/src/run.py` exists; I read `check_regression` (lines 53-117): purely deterministic NID/TEDS/MHS/table-F1/speed/triage threshold comparisons, `return False` on any failure (line 114), no LLM call anywhere in the function. Baseline's `run.py:69-86` under `opendataloader-pdf` (`00-baseline.md:38`) must be corrected to `opendataloader-bench-tmp/src/run.py:53-117`. |
| P11/P13: fresh PR-replay rerun, human agreement went 4/9 → 8/9 after `no_toc_leak` + TOC prompt rule | **CONFIRMED** | Primary source located and read directly: agent transcript `8cc736cd-...` (parent), message at JSONL line 398, contains the actual 3-run comparison table for PRs #282–#295 and states verbatim: *"Abgleich mit dem Menschen: Run 1 traf das Human-Verdict bei 4/9 PRs, Run 2 bei 5/9, Run 3 bei 8/9."* Baseline's "4/9 → 8/9" (`00-baseline.md:61-63`) is accurate for Run1→Run3 but silently drops the Run 2 intermediate step (5/9) — not wrong, but the synthesis should say "4/9 → 5/9 → 8/9" for precision. |
| P11/P13: every one of the 4 new hard fails in the rerun came from the deterministic gate, not the LLM | **CONFIRMED** | Same transcript table: PRs #284, #285, #290, #293 all show combined `**fail**, whisker_fail_locked (**fail** / review 0.85-0.95)` in Run 3 — i.e., in all 4 cases the deterministic verdict is `fail` and the LLM verdict is the *weaker* `review`, never an independent `fail`. The LLM never led on any of the 4; it corroborated and localized only. |
| P11: "0/4 unique LLM catches" on this replay cohort | **CONFIRMED as fair characterization** | Direct consequence of the row above: in 0 of the 4 new hard fails did the LLM alone produce a fail-equivalent verdict. This is consistent with, not contradicted by, the separate constexpr claim below (different PR-axis, different run). |
| P11/P13: PR #293's 31 dropped `constexpr` is a genuine unique LLM catch (code axis, conf 0.95) | **CONFIRMED-as-documented, not raw-artifact-verified** | Cited consistently and without contradiction across 3 independent documents: `golden-qa-gap/00-baseline.md:66`, `golden-qa-gap/SYNTHESIS.md:182`, `golden-qa-gap/opus-C-mc5-llm.md:185-187`. No raw sidecar JSON for p0533r9/PR#293 exists inside the repo to inspect directly (the paper corpus and `.tapetum.json` sidecars live in the external `WG21_DATA_DIR`, not committed) — I flag this as the one claim in the cluster resting on narrative cross-corroboration rather than a byte-level artifact I could open myself. Cross-source consistency across three independently-authored documents is meaningful evidence but is not the same evidentiary tier as the spot-checks above. Note this does **not** conflict with the "0/4" finding above: the constexpr catch is a different PR-axis (code-fidelity) found in Run 1/2, unrelated to the TOC-leak dimension that later made PR #293 a Run-3 det-fail. |
| P21: wall-clock ratios and derived multipliers (0.071 s/paper det sweep; 4.6x det-vs-advisory single-run slowdown; 25-177x corpus-sweep slowdown; 6x judge-mitigation multiplier; 11-14 min per 9-paper PR gate; 1.8-12.2h full-corpus LLM-gate; 10.8 s/paper effective batch rate) | **CONFIRMED (arithmetic)** | Independently recomputed every ratio from P21's own stated inputs: 41.516s/582=0.0713 s/paper ✓; 12.6/2.7=4.67x ✓; 1057.6s/41.5s=25.5x and 7333s/41.5s=176.7x (rounds to "25-177x") ✓; 2×3=6x ✓; 113.5×6=681s=11.35min, ×1.2=817s=13.6min (rounds to "11-14 min") ✓; 692.3/381×582=1057.6s=17.6min, ×6=105.8min=1.76h (rounds to "1.8h"); 582×12.6=7333.2s=122.2min, ×6=733.3min=12.2h ✓; 2159.8/200=10.799 s/paper ✓. Every figure checks out to rounding; no arithmetic error found. |
| P21: `SERVICES.toml` documents hourly billing, not per-token, and no $/hour rate is recorded anywhere | **CONFIRMED** | My own read of `SERVICES.toml:60-63`: "Runs 24/7; billed per hour of uptime, NOT per token, so run size is not a cost question." No dollar figure appears in the surrounding block or file. |
| P22: no reference repo mechanically gates on LLM QA even where LLM lanes exist; sovereignty tightens rather than loosens the case for det-first | **CONFIRMED (consistent with rows above)**; not independently re-derived beyond cluster's own citations | Restates the central claim from the sovereignty angle; no counter-evidence found by this cluster or by my spot-checks. The novel claim (self-hosted judge-grade quality parity with cloud judges is unproven, `22-sovereignty-guardian.md` Finding 3) is a negative/absence claim (no parity study exists) and is, by its nature, not falsifiable by a spot-check — it is correctly logged by P22 as the "what would change my mind" bar rather than a settled fact. |

---

## Corrected baseline anchors (for the synthesis to apply to `00-baseline.md`)

1. **Row "olmOCR", column "(c) LLM-judge bench"**: replace `bench/tests.py:114-125` with
   `bench/tests.py:150-176` (`TextPresenceTest.run`, the actual `fuzz.partial_ratio`/threshold
   gate). Lines 114-125 are the abstract `BasePDFTest.run` docstring and `NotImplementedError`.
2. **Row "olmOCR"**: replace `review_app.py:26-34` (cited for "verified flag") with
   `review_app.py:54-57` for the verified-count logic. Additionally soften the prose: "`checked
   is None` filtering" (`:26-34`) is the *unchecked-queue* view for human triage, not a
   verified-only gate; `load_tests`/`benchmark.py:227-230` evaluate the **full** loaded test set
   regardless of `checked` status. "Bench gates only on verified facts" overstates this as an
   automated runtime filter — it is a human-curation-workflow flag, not a pytest-time gate
   predicate.
3. **Row "firecrawl"**: replace "124x `toContain` anchors" with **348** (live count, 36 files,
   `apps/api/src/__tests__/**/*.ts`, verified 2026-07-16). Also replace the "clean via GPT"
   citation `llmExtract.ts:128-140` (which is `normalizeSchema` recursion) with the correct
   chain: LLM-path gate `:959-972`, no-op passthrough `:1127`, clean-content opt-in gate
   `:1134-1136`, LLM call `:811`, clean prompt starting `:1193`.
4. **Row "opendataloader-pdf(+bench)"**: replace `run.py:69-86` (cited under `opendataloader-pdf`,
   which does not contain this file) with `opendataloader-bench-tmp/src/run.py:53-117`
   (`check_regression`; threshold comparisons at `:69-96`, failure return at `:110-114`). Also
   note the wiring path: `opendataloader-pdf/scripts/bench.sh:83` invokes this file from the
   cloned bench repo — the two repos are companions, not one clone.
5. **Row "docling"**: `layout_postprocessor.py:175-193` (thresholds) is correct but incomplete;
   add the drop site `layout_postprocessor.py:264-268` where clusters below
   `CONFIDENCE_THRESHOLDS[c.label]` are actually removed.
6. **Row "MinerU"**: `test_e2e.py:163-220` has a 1-line drift (`:220` is `len(type_set) >= 4`,
   not part of the `fuzz.ratio` block) — low materiality, cosmetic fix only.
7. **§2 prose**: change "4/9 → 8/9" to "**4/9 → 5/9 → 8/9**" (Run 1 → Run 2 → Run 3) to preserve
   the intermediate calibration step (F1 false-pass fix on p0957r8) that the two-hop framing
   drops.

None of these corrections change the direction of any conclusion in `00-baseline.md` or in this
cluster's six reports; all are citation-precision fixes on claims whose substance already holds.

---

## The course question answered

**Operator's question:** *"Have we taken a wrong path by letting deterministic gates decide and
keeping the LLM lane advisory-only?"*

### Strongest counter-argument first (steelmanned)

The most defensible version of "yes, wrong path" that survives this cluster's own evidence is
**not** "LLM should gate instead of advise" — that door is closed by 31/31 reference repos, five
converging categories of web literature (`05-web.md` Q1-Q5), our own fresh PR-replay evidence,
and a hard sovereignty constraint (P22). The real doubt this cluster's evidence supports is a
**resource-allocation** argument, built entirely from this cluster's own numbers:

- ~4,751 LOC of advisory LLM stack (21 files under `tapetum_llm/`) has exactly **one** traceable,
  cross-corroborated unique catch (PR #293's 31 dropped `constexpr`), and on the freshest
  available replay cohort (the 4-PR TOC-leak rerun) contributed **zero** unique catches — in
  every one of those 4 cases the LLM verdict (`review`) was strictly weaker than the deterministic
  verdict (`fail`) that actually decided the outcome.
- The one miss-class that *did* get closed this cycle (MC2, TOC leak, human agreement 4/9→8/9)
  was closed by **~40 LOC of fence-aware regex**, not by the LLM lane — after the LLM had already
  had two prompt-generation attempts at the same paper and silently missed it both times
  (`13-steelman-det-first.md` Finding 2).
- Running the current advisory lane at all is 25-177x slower than the deterministic sweep it sits
  beside (P21), and any credible attempt to make it judge-quality (position-swap debiasing,
  multi-sample averaging — the literature's own recommended mitigations) multiplies that by 6x
  again, without a labeled holdout to confirm the multiplier buys back any catch-rate.
- If the lane's marginal return is this thin, the honest "wrong path" is not "gates vs LLM," it
  is **"we may have overbuilt 4,751 LOC of narrative-generating advisory tooling when the same
  engineering hours, spent extending deterministic facts and gates (the pattern that actually
  closed MC2, and the olmOCR pattern of LLM-mines/human-verifies/gate-on-verified-facts), would
  have produced more defensible catches per hour of work."**

This is a real argument and this cluster does not have the labeled data to refute it outright —
P11, P13, and P21 each independently name a labeled-holdout experiment as "what would change my
mind," and none of those experiments has been run.

### The answer

**No, the direction was not wrong — but the steelmanned doubt above identifies a real, still-open
calibration question about scope, and this cluster's evidence says the operator should act on
that question rather than dismiss it.**

Ranked by the strength of evidence behind each part:

1. **Gate-vs-advise direction: settled, not revisitable without new labeled data.** 0/31
   reference repos gate on an LLM judge signal (re-verified, not merely repeated); the failure
   mode of promoting LLM to gate is independently documented in the 2026 literature (flaky CI,
   ~50% per-item disagreement at default temp, judges systematically overconfident); and
   model-sovereignty makes det-first **necessary**, not merely prudent, because the cloud
   endpoints the reference repos use for their LLM lanes are the endpoints we are contractually
   forbidden from depending on for defensible output, and our self-hosted judge-grade quality
   parity with those cloud endpoints is unproven (P22). Reversing this would require the
   holdout P22 names: self-hosted judge matching cloud-judge human-agreement within 5pp AND
   ≤5% run-to-run flip rate. Nothing in this research cycle produced that evidence, for or
   against.
2. **The advisory lane's current size/ROI is a legitimate open question, and the cluster's own
   numbers are the strongest evidence for it.** This is not a refutation of the architecture —
   it is a claim that the *emphasis* inside the architecture (how much of the 4,751 LOC's
   surface area is "generate narrative explanations" vs "mine reusable deterministic facts")
   may be miscalibrated. The evidence for this (single-digit unique-catch inventory, 0/4 on the
   freshest cohort, MC2 closed by regex not by the LLM) is concrete and this-cycle, not
   speculative.
3. **The two are not in tension.** "Det decides, LLM advises" can be the right architecture while
   the advisory lane is still the wrong *shape* — too much prose generation, too little
   fact-mining that would let `gates.py`/`score.py` absorb what the LLM finds once and check it
   forever after (the exact mechanism that turned this session's TOC-leak finding into a
   permanent ~40 LOC gate). The operator's doubt is best answered as: **keep the direction,
   redirect the next unit of effort from advisory narrative toward deterministic fact-mining in
   the olmOCR mold**, and treat the labeled-holdout experiment as the actual decision gate for
   whether to invest further in tapetum's current form.

---

## Recommended actions, ranked by cost

1. **(near-zero cost, do first)** Apply the 7 anchor corrections above to `00-baseline.md`
   before the synthesis is finalized; none change any conclusion, all improve citation
   precision for anyone who re-derives this later.
2. **(near-zero cost)** Change "4/9 → 8/9" to "4/9 → 5/9 → 8/9" wherever the synthesis restates
   the PR-replay headline, to keep the F1 false-pass intermediate fix visible.
3. **(cheap, instrumentation only)** Start logging, per paper, whether the LLM verdict diverges
   from the deterministic verdict **and** whether that divergence was later confirmed correct by
   a human. This turns "single-digit unique-catch inventory" from an occasional retrospective
   claim into a running, cheap-to-compute KPI, using batches that are already executing.
4. **(cheap-medium, redirect not add)** For the next prompt/pipeline iteration on tapetum, bias
   new work toward **fact-mining that graduates into a deterministic gate** (the MC2/olmOCR
   pattern: LLM proposes a candidate mechanical check → human verifies a sample → check becomes
   a permanent `gates.py`/`score.py` rule) over new narrative/explanation features. This is a
   reallocation of already-planned engineering time, not new spend.
5. **(medium)** Close or explicitly re-document the selection gap named by P11/P13: clean-pass
   papers with token-preserving corruption never reach tapetum under `--review-all`. Either fix
   the selection filter or state the limitation in `whisker/CLAUDE.md` so operators do not assume
   full-corpus advisory coverage exists today.
6. **(medium-high, the actual decision gate)** Commission the ≥30-paper labeled holdout named
   independently by P11 (does the advisory lane uniquely catch >15% of defects det+facts miss,
   without raising false-pass?), P13/P21 (would an LLM-gate stack hit ≥90% precision with ≤5%
   flip rate at acceptable wall-clock?), and P22 (does self-hosted judge quality match cloud
   within 5pp?). This is the only experiment in this cluster capable of overturning either the
   "keep advisory" or the "redirect toward fact-mining" recommendation above; until it runs,
   both are the best-supported positions and neither requires touching the gate/advise split.
7. **(high cost, not recommended)** Promoting any LLM signal, self-hosted or cloud, to a
   mechanical accept/reject gate. 0/31 reference repos do this, the reviewed 2026 literature
   documents why (flakiness, overconfidence, position bias), model sovereignty forbids the cloud
   version outright, and this cluster's own fresh PR-replay evidence shows the LLM was strictly
   more conservative than the deterministic gate in the one cohort where both ran side by side
   this cycle.
