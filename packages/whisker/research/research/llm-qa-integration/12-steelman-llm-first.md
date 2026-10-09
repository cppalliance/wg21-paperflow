# 12 - Steelman-LLM-First

**Verdict:** usable-with-conditions — the deterministic-first split is defensible for CI reproducibility, but advisory-only LLM authority is structurally insufficient for the semantic defect classes that actually ship broken WG21 markdown; the operator's doubt is directionally correct.
**Confidence:** medium

## Findings

- [CRITICAL] **Deterministic gates are blind to token-preserving semantic corruption.** The hard gate keys on structural invariants plus order-invariant `unigram_coverage` (`score.py:149-151`, `constants.py:37-38`), so section permutations, table row/cell swaps, and wording-markup misplacement can all pass when every token survives. The tapetum authority doc explicitly assigns row/cell swap detection to the LLM tables axis because "the deterministic token gate is blind to this" (`tapetum_llm.md:84`). Lane 3 `table` facts catch cell neighbors only where authored (`facts.py:360-370`); the corpus covers 5/381 papers (`CLAUDE.md` comprehension section). Impact: the gate optimizes for "words present," not "meaning preserved," which is the failure mode operators care about on normative papers.

- [HIGH] **Heading-level fidelity is a semantic class no current det gate can adjudicate without source context.** `_gate_heading_monotone` only forbids H-skips in the markdown AST (`gates.py:96-112`); it does not compare converted levels to source HTML/PDF structure and cannot detect `### References` when the source is `<h2>References</h2>`. PR #282 documented a human request-changes on a whisker pass/1.00 while the LLM false-cleared despite injected outline (`golden-qa-gap/00-baseline.md:63`, `html_outline.py:8-14`, `adjudicate.py:387-407`). Impact: det pass is a false comfort on HTML lane; even outline-equipped LLM judgment failed here (MC5), which argues for **deterministic source-outline diff OR LLM authority on that diff's output**, not for keeping LLM advisory-only on clean passes.

- [HIGH] **The selection gap means advisory LLM never sees the highest-risk population under the cheap path.** `--review-all` filters to lossy-table/mojibake/review/rescue cohorts and explicitly never reaches "clean-pass papers with token-preserving corruption" (`CLAUDE.md:485-492`). Full corpus runs are the workaround but fusion still cannot move CI exit codes (`fusion.py:12-13`, `__main__.py` gate contract). Impact: the architecture as deployed lets the worst false-pass class bypass both det escalation and operator attention unless every paper is LLM-scored every run.

- [HIGH] **Reference repos prove LLM-in-the-loop improves output when mechanically guarded, without using LLM-as-CI-gate.** Marker retries table rewrites when its own LLM score `< 4` (`00-baseline.md:26`, `llm_table.py:213-225` per baseline scout); olmOCR uses the VLM as the conversion engine and supervises quality with 7,010 deterministic unit-test rewards, not an LLM judge (`00-baseline.md:28`, `05-web.md / Q5 / olmOCR 2`). Langextract validates every LLM extraction span with exact DP → partial → fuzzy LCS (`00-baseline.md:34`, mirrored in `grounding.py:171-189`). Impact: the ecosystem pattern is "LLM proposes / rewrites, mechanical checks decide and retry" — whisker inverted this to "mechanical decide, LLM advise post hoc," leaving table/wording repair loops unimplemented.

- [HIGH] **We already built the guarded escalation primitive; we refuse to let it bind shipping.** PDF per-page screen flags low recall pages deterministically, then scoped LLM calls may confirm missing content with PDF-grounded quotes; confirmed gaps demote pass→review inside the lane (`pdf_judge.py:287-312`, `540-592`, `ground_page_quotes`). Fusion can escalate det=pass + LLM major fail → combined review (`fusion.py:228-240`, `test_fusion.py:172-188`) but labels the result advisory-only (`fusion.py:12-13`). Impact: the safest incremental authority grant — localized, grounded, never solo-fail — is implemented and tested but deliberately excluded from `whisker --gate pass`.

- [MED] **Deterministic-only authority over-fails on WG21-legitimate heading shapes while under-catching semantics.** Nine papers hard-fail solely on `heading_monotone` with `uni≈0.999` (persona evidence cited in `00-baseline.md` comparison context; gate at `gates.py:105-109`). Fusion rescue demotes heading-only det fail to combined review, never pass (`fusion.py:149-160`), but CI still exits fail on det alone. Meanwhile 2026-07-16 PR replay: det+LLM agreement with humans improved 4/9→8/9 after MC2 gate work, and all four new hard fails came from the deterministic gate with LLM confirming (`00-baseline.md:61-63`). Impact: we spend mechanical authority on markdownlint pedantry and spend LLM authority only where operators opt in.

- [MED] **Industry and maintainer docs converge on cascade, not either/or — but our cascade stops one layer short.** Deterministic-first, LLM-for-semantic-remainder is the named 2026 pattern (`05-web.md / Q4 / Deterministic vs LLM-Judge Evals 2026 Guide`; `05-web.md / Q4 / Deterministic Guardrails`). olmOCR maintainers reject LLM-as-judge for benchmarks precisely because soft metrics miss one-char semantic errors — then use programmatic tests as rewards (`05-web.md / Q5 / olmOCR-Bench README`). Impact: giving LLM **bounded** authority on semantic remainder is aligned with external practice; giving it **unbounded** CI veto is not (zero/31 repos, `00-baseline.md:43-44`).

## False-pass hypothesis

**P4020R0-class HTML heading drift (PR #282).** Whisker det pass (all gates green, high `unigram_coverage`). No `heading_monotone` trip because `### References` is monotone. Deterministic gates cannot compare to source `<h2>References</h2>`. Under `--review-all`, the paper is invisible (clean pass, no lossy-table signal). Full-run LLM with outline still false-cleared in production (`golden-qa-gap/00-baseline.md:63`), so **LLM authority without a deterministic outline diff remains unreliable for this class** — but det-only authority is guaranteed false-pass.

## False-fail hypothesis

**P3941R2 wording-paper H2→H4 jump.** Det hard-fails `gate:heading_monotone` (`gates.py:105-109`) with excellent content metrics; fusion rescue yields combined review only (`fusion.py:149-160`), while CI `--gate pass` still fails on det. Granting LLM clear/rescue **hard** effect on heading-only fails would reduce false-fail rate but risks shipping genuine structure breaks if the LLM over-rescues — mitigated by keeping rescue capped at review, never pass.

## What would change my mind

A labeled replay showing **grounded, major-severity LLM escalations on det=pass papers** (tables/wording/per-page confirmed missing) achieve ≥90% precision vs human golden-QA verdicts **and** `<5%` spurious `--gate pass` blocks across 30+ papers — measured with position-swap debiasing (`05-web.md / Q2 / Position Bias`) and reported grader-disagreement at temp=0 (`05-web.md / Q2 / Temperature Control`). If precision is lower, the correct move is narrower authority (per-page confirmed missing only), not full LLM CI gating.

---

## Concrete proposal (single decision to grant LLM)

**Decision:** Bind **`FUSION_RULE_LLM_ESCALATE_MAJOR`** and **PDF per-page confirmed missing** (`pdf_judge.py:589-592`) to the **operational ship verdict** when operators run `whisker --gate pass` with tapetum sidecars present — i.e., det=pass + grounded major-axis fail OR grounded per-page `content_missing` → **hard review** (exit 3), never a solo hard fail.

**Why this one:** It targets the defect classes det cannot see (table/wording/per-page loss) using primitives already in-tree; it does not let LLM overturn det fail; it mirrors marker's "LLM score triggers retry/demotion, heuristics gate CI" split (`00-baseline.md:26-27`, `05-web.md / Q5 / Marker CI gates heuristic only`).

**Guardrails (non-negotiable):**

| Guardrail | Anchor |
|---|---|
| Schema-locked verdict + axis findings (no free-text parse) | D6; tapetum pydantic models |
| temp/seed pinned, serial calls | D5, D11; `CLAUDE.md` Determinism |
| Evidence grounding required; ungrounded demoted | `grounding.py:171-241`; adjudicate #277 demote |
| Major severity only for text-lane escalate | `fusion.py:230-231`; `constants.py:47-50` |
| Per-page: screen decides WHERE, LLM only confirms WITH PDF quotes | `pdf_judge.py:540-542`, `572-574` |
| Position-swap if any pairwise LLM compare added later | `05-web.md / Q2 / Position Bias` |
| LLM never sole hard-fail; det fail stays locked | `fusion.py:148-170`, `22-23` |
| Report grader-disagreement rate on golden set | `05-web.md / Q2 / Temperature Control` |

**Honest costs:**

- **Compute:** Full-corpus tapetum run required (selection gap); pod billed hourly, not per-token (`CLAUDE.md` cost model), but serial page escalations add latency (`constants.py:168`, `cli.py:97-98`).
- **Determinism:** temp=0 reduces variance, does not eliminate pass/fail flips (`05-web.md / Q2 / Temperature Control`); binding CI on LLM escalations introduces flake risk the 31-repo survey explicitly avoided (`00-baseline.md:43-44`, `05-web.md / Q1 / agent-testing-non-deterministic-ci`).
- **Calibration tax:** MC5 shows self-reported confidence is anti-calibrated (`golden-qa-gap/00-baseline.md:68`, `tapetum-golden-review-findings-2026-07-14.md:86-89`); hard binding must use grounded evidence + severity, not confidence alone.
- **Operator load:** More `--gate pass` blocks → more human review; cheaper than shipping swapped poll-table cells on a normative wording paper.
- **Scope limit:** HTML heading-level still needs deterministic outline diff (`golden-qa-gap/SYNTHESIS.md T3.3`); LLM-with-outline alone failed PR #282 — do not expand LLM authority there without the diff pre-check.

**What we should NOT do (steelman honesty):** Promote LLM to mechanical CI fail gate on free-text quality (0/31 repos, `00-baseline.md:43-44`); drop deterministic gates for TOC leak / empty tables (`gates.py:209-218`, MC2 closure); or trust ungrounded confident passes (64% empty-evidence passes, findings doc `:86-91`).
