# Opus D - Meta-review: adoptable-patterns cluster (14, 16, 18, 24)

**Scope:** re-verify feasibility of the ADOPTABLE upgrades proposed by
14-maintainability-complexity, 16-retry-loop-architect, 18-grounding-engineer,
24-fallback-cascade-designer against live code (`--no-ignore` reads into
`packages/whisker/research/repos/`, direct reads of `packages/tomd`,
`packages/whisker`).

## Verdict on cluster

All four personas independently converge on the same conclusion the baseline
states: deterministic-gates-decide + advisory-LLM is the right architecture,
and the ecosystem's real lesson is bounded mechanical retry/fallback around
**conversion**, never LLM-signal gating of accept/reject. That framing holds
up under re-verification. But two of the four proposals turn out to be built
on weaker plumbing than the persona reports imply once you read the actual
parameter surface and call graph:

- **P18** (fuzzy-only demotion) is real, cheap, and almost exactly as
  described — the smallest, highest-confidence adopt in the cluster.
- **P24** (page-failed marker + gate) is real and buildable, with one
  under-scoped edge case (genuinely blank/unreadable pages are invisible to
  today's per-page model, not just "uncertain" - see table).
- **P14** (dead-code inventory) is factually accurate on the qualitative
  claims (VLM lane is a fully wired-off island; cascade escalation is
  measured dead across 6+ independently-dated research runs) but overstates
  one number (VLM LOC) and leaves one open question (has the cascade
  actually stayed dead *after* the derived-signal fix, or is 0/198 a
  pre-fix number being re-cited).
- **P16** (retry loop) is **not vapor** - tomd genuinely has three parameter
  axes that can change conversion output (`ml_tables`, `extract_vector`,
  `whiteout_text`) - but P16's own trigger map is half-wrong: the one
  concrete example it gives for text-coverage recovery (`extract_vector=True`)
  is mapped to the wrong failure mode and, per tomd's own documented
  behavior, can plausibly make the target metric *worse*. The only
  survivably-correct trigger (`ml_tables=True` on table-shaped gate fails)
  depends on an optional dependency (`docling`) that is not declared
  anywhere in tomd and not forwarded through the public API today.

## Feasibility table

| Proposal | Status | Evidence | Honest cost |
|---|---|---|---|
| **P16-1**: gate fail -> bounded tomd re-convert with named parameter variants -> re-gate | **FEASIBLE-WITH-CHANGES** | `run_pipeline` (`packages/tomd/src/tomd/lib/pdf/pipeline.py:1380-1387`) exposes `ml_tables`, `visualize`, `extract_vector`, `whiteout_text` — tomd is genuinely multi-strategy, not single-strategy. But: (a) `api.py`'s `convert_paper_full`/`_convert_with_tomd_full` (`api.py:298-325,375-413`) forward only `extract_vector`/`whiteout_text`, **not** `ml_tables` — the one table-shaped trigger needs new plumbing; (b) `ml_tables` is gated on `_docling_available()` (`pipeline.py:1708`, `docling_backend.py`) and **`docling` is absent from `packages/tomd/pyproject.toml` entirely** (no dependency, no extra) — unverified whether it's installed anywhere the pipeline actually runs, and when absent the "retry" silently no-ops (same output, wasted attempt, not a false pass, just dead work); (c) `extract_vector=True` is mapped by P16 to `unigram_coverage`/repeat-ngram fixes, but tomd's own architecture doc (`tomd/CLAUDE.md`, "Body-text cleanup around extracted vectors") states turning it on can **drop** body paragraphs that overlap a detected vector cluster, replacing them with an opaque image ref — the opposite of recovering missing text. | Expose `ml_tables` through `api.py` (~10 LOC) + declare `docling` as an optional extra + verify it runs where conversion actually runs (infra unknown) + **delete or redesign** the `extract_vector` trigger + build the ~100-150 LOC `convert_attempts[]` orchestration wrapper P16 itself scopes. Roughly half the proposal is solid; half needs rework before it is buildable. |
| **P24**: `tomd:page-failed` marker + new whisker hard gate | **FEASIBLE-AS-DESCRIBED** (core case), scope gap on one edge case | Confirmed: no `tomd:page-failed` (or nougat `[MISSING_PAGE_*]`) equivalent exists in tomd today — only `tomd:uncertain` (soft, dual-path disagreement, `structure.py:331-339`) and `SkipReason` (document-level typed skip). Nougat's markers verified live in the clone at the exact cited anchor: `predict.py:178-202` (`[MISSING_PAGE_POST]`, `[MISSING_PAGE_EMPTY:n]`, `[MISSING_PAGE_FAIL:n]`, all present, byte-for-byte). The hook point is real: `structure.py`'s `compare_extractions` — after pairwise-neighbor promotion (`:346-358`) and document-wide bulk promotion (`:378-407`) both fail to rescue a page, and it survives the `MIN_UNCERTAIN_WORDS` triviality filter (`:411-419`), that state IS "exhausted recovery." The whisker-side gate (~40 LOC) is a direct copy of the existing `_gate_no_empty_table` pattern (`gates.py:191-206`). **Gap P24 under-scoped:** `all_pages` in `compare_extractions` (`:299`) is built from `set(mupdf_by_page) \| set(spatial_by_page)` — a page where BOTH paths return zero blocks (genuinely blank scan, or a page where extraction crashed outright) never enters the comparison and is never marked anything, not even `uncertain`. That is the actual nougat-`[MISSING_PAGE_EMPTY]` analog and needs iterating the full page-count range independent of block presence, which P24's 60-100 LOC tomd-side estimate does not obviously cover. | ~40 LOC whisker gate (cheap, low risk, mirrors existing pattern) + ~100-150 LOC tomd-side realistic (the "disagreement exhausted" case is close to P24's estimate; the "both-paths-empty" case is additional, unscoped work) + a policy decision on what counts as unrecoverable vs. honestly-disagreeing + new test fixtures with injected page defects. |
| **P18**: use `GroundedSpan.status` in demotion — demote `pass` -> `review` when all surviving evidence is `GROUND_FUZZY` | **FEASIBLE-AS-DESCRIBED** | Read `adjudicate.py:296-310` in full: current demotion checks only `not grounded` (list emptiness), line 299 and 305-310 — it never inspects `.status`. `ground_spans` (`grounding.py:190-239`) already returns each span's status (`GROUND_EXACT` / `GROUND_FUZZY`, `grounding.py:46-47`) and this is already surfaced to the sidecar (`adjudicate.py:329-331`, per P18's own citation). The proposed change is additive: one new conditional, `if grounded and all(g.status == GROUND_FUZZY for g in grounded): suggested_verdict = VERDICT_REVIEW`, using data already computed. Langextract citations spot-checked directly in the clone (previously misdiagnosed as empty by earlier scouts — it is not, 6348 files) at `packages/whisker/research/repos/langextract/langextract/resolver.py`: Tier-3 thresholds exact at `56-58`; `accept_match_lesser: bool = True` real, found at line 335 (P18 cited 328-330, off by ~5-7 lines, same method/same default); `_accept_lcs_match` coverage/density logic real, found at `1377-1391` (P18 cited 1360-1387, off by ~15 lines, same function); plural-stem `_normalize_token` real, found at `1276-1281` (P18 cited 1263-1268, off by ~13 lines) with an **exact** logic match ("`len(token) > 3 and token.endswith('s') and not token.endswith('ss')`"), consumed on the LCS path at line 745 exactly as cited. `MATCH_LESSER`/`MATCH_EXACT`/`MATCH_FUZZY` enum confirmed in `core/data.py:43-47`. | ~5-10 LOC in `adjudicate.py` + a couple of new unit tests (fuzzy-only pass demotes; exact-anchored pass does not). No new data plumbing. Line-number drift on langextract citations (5-15 lines throughout) is version skew between what P18 read and the pinned clone commit, not a fabrication or an empty-clone misread — the algorithm descriptions are all substantively correct. |
| **P14**: dead-code inventory (0/198 cascade, ~637 LOC dormant VLM lane) | **FEASIBLE-AS-DESCRIBED**, with two corrections | Cascade 0/198: cross-verified in 6+ independently-dated research docs spanning 2026-07-06 to 2026-07-16 (`llm-stack/opus-A-metric-validity.md:20,32,35`; `llm-stack/opus-B-gates-logic.md:7`; `llm-batching/17-latency-decomposer.md:8`; `deepseek-v4-pro/SYNTHESIS.md:14`; `tapetum-golden-review-findings-2026-07-14.md:86-89`) all agreeing on 0 escalations out of 197-204 sidecars. `constants.py:22-28`'s current comment ("The band alone proved dead in production (0/198 escalations)... escalation now also fires on DERIVED uncertainty signals") confirms the team already reacted to this exact number by adding two new triggers (`axis_conflict`, `ungrounded_evidence`) alongside the confidence band — this IS live in the code I read (`adjudicate.py:230-253`). VLM lane dormancy fully confirmed: `vlm_adjudicate_paper` (`vlm_pipeline.py:36`) has zero callers outside its own module and `tests/test_vlm_lane.py`; `pyproject.toml`'s three script entry points (`whisker`, `whisker-tapetum-llm`, `whisker-readback`) never import it; `cli.py` only calls `judge_pdf_extraction`/`adjudicate_paper` (`cli.py:36,54,790,832`). **Correction 1:** measured LOC across the five VLM files is **788**, not ~637 (vlm_pipeline.py 97 + vision_task.py 210 + transcribe.py 140 + vlm_diff.py 218 + vision.py 123) — a 24% undercount; the qualitative "fully dormant" claim is exact. **Correction 2 (open question, not a refutation):** whether escalation is *still* 0/N after the derived-signal fix landed, or whether the cited 0/198 predates that fix and simply has not been re-measured, is not resolvable from the docs available — P14's "still dead despite a July refactor" framing should be treated as needing one fresh corpus run to confirm, not as already double-confirmed post-fix. | Zero code-writing cost to validate the finding (already true). Cost is the *cleanup* P14 recommends: deleting/quarantining ~788 LOC (VLM lane) is low-risk (unreachable in production); collapsing the dual PDF/text prompt authorities is a materially larger, higher-risk refactor because it touches the actively-used production PDF-judge path (`pdf_judge.py`) — should be split into its own task, not bundled with the VLM deletion. |

## Ranked adoption list (value/cost, highest first)

1. **P18 - fuzzy-only demotion in `adjudicate.py`.** Best ratio in the
   cluster: ~5-10 LOC, zero new data plumbing (status is already computed
   and already persisted to the sidecar), closes a real precision gap in
   exactly the false-pass population the lane exists to catch (a `pass`
   backed only by fuzzy-grounded evidence is currently trusted identically
   to one backed by exact grounding). Strictly additive to the "never
   upgrade" invariant (only ever demotes `pass`, never touches a `fail`).
   Ship this first; validate with P18's own proposed labeled holdout when
   one exists, but the code change does not need to wait for it.

2. **P24 - `tomd:page-failed` marker + `_gate_no_page_failures`.** Genuine
   architecture-shaped gap (page-level failure visibility, matching the
   olmOCR/nougat industry pattern the baseline documents) closed with a
   purely deterministic, zero-LLM-token mechanism that fits the existing
   fidelity contract (document-level fail, page-level diagnosis). Before
   coding: decide the closed reason-enum semantics (what counts as
   "exhausted," and whether to also cover the both-paths-empty case this
   review surfaced) and build injected-defect test fixtures per P24's own
   acceptance bar (>=80% correct-page hard-fail, >=95% false-fail-free on
   the golden corpus).

3. **P14 - VLM-lane deletion/quarantine.** Not new capability, pure
   maintainability payoff, near-zero runtime risk (the code is already
   unreachable). The only real decision is product, not engineering: delete
   outright, or keep as a documented, explicitly-quarantined "do not
   resurrect without a plan" module. Keep this decoupled from the
   dual-prompt-authority consolidation P14 also recommends — that touches
   the live production PDF-judge path and deserves its own review, separate
   from deleting dead code.

4. **P16 - gate-triggered re-convert loop.** Real value if built correctly,
   but the highest-uncertainty item here: half the proposed trigger map
   needs to be fixed (drop or redesign `extract_vector` as a text-coverage
   remedy) and the one surviving trigger (`ml_tables`) needs an
   infrastructure decision (declare + verify `docling` availability) before
   any orchestration code is worth writing. Do this last, and only after an
   instrumented pilot (P16's own "what would change my mind" bar: recovers
   human-verified pass on >=3 of 10 gate-failed papers without any attempt
   passing on degraded fallback markdown).

## What NOT to adopt, and why

- **`extract_vector=True` as a retry trigger for `unigram_coverage`/
  repeat-ngram fails (P16).** Per tomd's own documented behavior, enabling
  it can drop body paragraphs that overlap a vector cluster, trading text
  content for an opaque image ref — plausibly the opposite of the intended
  effect. If vector-figure misclassification turns out to be a real
  contributor to a specific paper's coverage loss, that needs its own
  targeted investigation, not a blanket retry trigger.
- **Any temperature escalation or silent weaker-engine substitution
  on retry (P16, citing olmOCR).** All four personas and the baseline agree:
  this is conversion-yield engineering the ecosystem uses to avoid
  discarding a whole document, not a QA pattern; it would invert the
  "never auto-pass on a degraded attempt" invariant this project already
  holds.
- **langextract's Tier-3 LCS (0.75 coverage / 1/3 density) and
  `MATCH_LESSER` (P18).** Confirmed present and real in the clone, and
  confirmed to accept gapped-wrong-span matches by design (its own oracle
  test codifies this). Already correctly rejected by whisker's own
  `grounding.py` docstring; nothing in this re-verification changes that.
- **Declaring the two-tier cascade "fixed" and moving on (P14 implicit
  risk).** The derived-signal fix is real and live in the code, but no
  post-fix escalation count was found in any research doc. Treat the
  cascade's health as unconfirmed, not resolved, until one fresh corpus run
  reports a non-zero (or explicitly still-zero) escalation rate under the
  new triggers.
- **Bundling P14's prompt-authority consolidation with the VLM-lane
  deletion.** They read as one refactor in the persona report but carry
  very different risk profiles (dead code vs. the live PDF-judge path);
  splitting them lets the zero-risk cleanup ship immediately without
  waiting on review of the riskier one.
