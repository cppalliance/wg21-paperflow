# 21 - False-fail hunter (review mode)

**Verdict:** usable-with-conditions — REVIEW mode kills the fleet cost/noise exponent for triage load (expected false flags scale as `n·p`, not `1-(1-p)^n`), but the planned `--all-pages` path reuses `UNIT_CHECK_SYSTEM_PROMPT` without the escalation prompt’s cross-page “anywhere in markdown” clause or binding quote prohibitions, and `verify_unit_evidence` still demotes sanctioned page-1/TOC quotes to `ambiguous`, which forces per-unit and document `review` via `evidence_uncertain` even when no verified defect survives.
**Confidence:** high

## Findings

- [CRITICAL] **REVIEW-mode triage load is linear, not worst-page-wins compound.** Evidence: FLEET doc false-review rate `P(doc review) = 1 - (1-p)^n` (`research/per-page-judging/20-false-fail-hunter.md:8`); REVIEW mode assumes a human dismisses each spurious page finding independently, so **expected false findings per golden review `E[F] = n·p`** (Binomial mean). Computed table (show work: `E = n × p`):

  | n | p=0.5% | p=1% | p=2% | p=5% |
  |---|--------|------|------|------|
  | 15 | **0.075** | **0.15** | **0.30** | **0.75** |
  | 33 | **0.165** | **0.33** | **0.66** | **1.65** |
  | 40 | **0.20** | **0.40** | **0.80** | **2.00** |

  **Noise-dominated triage** (more than one spurious finding to dismiss per review on average): `n·p > 1` → at **p=5%** all three n values; at **p=2%** only **n=40** (0.80 is high but below 1.0); at **p=1%** none reach 1.0 (max 0.40). On a clean golden expecting ~0 true defects, even **E[F]=0.33** (n=33, p=1%) means a third of reviews carry a bogus item. Prior fleet calibration **p ≤ 0.0032** for ≤10% doc auto-review at n=33 (`20-false-fail-hunter.md:8`) maps to **E[F] ≤ 0.106** here — same precision bar, different aggregation cost model. Impact: mode change removes corpus-scale explosion (`00-baseline.md:36`) but does **not** relax the per-page precision requirement.

- [CRITICAL] **Unit-check prompt partially inherits conversion sanctions but misses escalation-only clauses that block structural false-fails.** Evidence: `_UNIT_CONVERSION_CONTRACT` at `unit_judge.py:67-76` covers title-block→YAML, TOC removal, furniture drop, figure imaged text, dehyphenation, wording markup. Escalation uses the fuller `_CONVERSION_CONTRACT` at `pdf_judge.py:153-189` plus `PAGE_JUDGE_SYSTEM_PROMPT` extras at `pdf_judge.py:238-241,251-253`: explicit YAML key list (“If those values appear in the YAML block, they are NOT missing”), leaked-TOC inverse, HTML-comment sanction, wording-color caveat, and **“Content from this page counts as present if it appears ANYWHERE in the markdown.”** `_check_one_unit` binds only `UNIT_CHECK_SYSTEM_PROMPT` (`unit_judge.py:672`). Impact: cross-page reflow tails (`20-false-fail-hunter.md:16`) remain structurally exposed in all-pages mode; page-1/TOC are prompt-sanctioned but with weaker binding than escalation.

- [HIGH] **Sanctioned page-1/TOC quotes still force `review` through `evidence_uncertain`, not through verified defects — so “no guaranteed false finding” is only half true.** Evidence: `classify_candidate_evidence` marks front-matter labels and TOC/furniture quotes as `CANDIDATE_AMBIGUOUS` (`grounding.py:545-576`); `verify_unit_evidence` excludes ambiguous from `verified_defects` (`unit_judge.py:356-360`) but sets `evidence_uncertain` when `CANDIDATE_AMBIGUOUS > 0` (`unit_judge.py:381-388`), yielding unit `verdict = "review"` (`unit_judge.py:390-394`); PDF lane folds any unit review into document review (`pdf_judge.py:884-885`). Impact: a model that obeyed the contract and quoted `"Document Number: P1068R11"` still produces a non-pass unit on page 1; all-pages multiplies this across every page call. Prompt inheritance alone does not fix aggregation demotion.

- [HIGH] **Cross-page reflow is the largest all-pages-only gap: unit prompt lacks escalation’s global-presence rule; grounding search is document-wide but verbatim quote discipline is not.** Evidence: PAGE escalation: “appears ANYWHERE in the markdown, in any order” (`pdf_judge.py:238-241`); unit check: “faithfully preserves the source content for THIS UNIT ONLY” (`unit_judge.py:99-100`) with `source_quote must be verbatim from the SOURCE TEXT` (`unit_judge.py:118-119`); tomd joins pages when prior block lacks terminal punctuation (`tomd/CLAUDE.md:231-232`, cited in `20-false-fail-hunter.md:16`). `classify_candidate_evidence` searches full `candidate_md` (`unit_judge.py:632-633`) so joined sentences may refute dangling tails mechanically — but the LLM is still asked unit-local fidelity first, and dehyphenation/reflow quotes can miss fuzzy floors (`grounding.py:39`, `20-false-fail-hunter.md:14`). Impact: join sites on a 33-page paper are recurring false-fail candidates unless the unit prompt copies the escalation scope rule.

- [MED] **Figure/diagram in-diagram text: prompt parity exists; mechanical parity does not.** Evidence: both prompts sanction “text inside figures/images is legitimately imaged” (`unit_judge.py:73`, `pdf_judge.py:171-173`). No grounding regex exempts arbitrary diagram-axis fragments (`grounding.py:545-576` covers front matter/TOC/furniture only). Alt/caption band checks are absent from unit path. Impact: vector-figure pages (`20-false-fail-hunter.md:18`) add stochastic false `content_omission` defects that survive to `verified_defects` when quotes are exact in raw and absent from md body.

- [MED] **Fleet “doc review probability” still applies if the operator treats any unit `review` as a failed golden — mode change is triage-cost, not verdict-cost.** Evidence: `P(≥1 page false-flags) = 1-(1-p)^n` unchanged; at n=33, p=1% → **28.3%** (`1-(0.99)^33=0.283`), p=2% → **48.7%**, p=5% → **81.7%**. REVIEW mode assumes the human filters these; automatic document verdict still uses worst-unit-wins fold (`pdf_judge.py:884-885`). Impact: sidecar may read `review` on clean goldens at rates fleet math predicted unless aggregation demotes sanctioned/ambiguous unit outcomes.

- [LOW] **Prior web/agreeableness evidence survives mode change as a precision floor, not a coverage argument.** Evidence: LLM judges TNR <25% on incorrect outputs (`05-web.md:33`); pdf-parse-bench scoped table judging, not whole-page QA (`05-web.md:32`). Impact: all-pages increases recall of real defects on one golden (`00-baseline.md:36`) but does not lower the required **p ≤ ~0.3%/page** calibrated false-positive rate.

## False-pass hypothesis

All-pages unit checks with full markdown injected may **false-pass** a localized drop on page 13 (p0957r8-class) when that page’s call under-attends but neighboring pages’ prose appears in the shared candidate — same attention lottery as fleet analysis (`20-false-fail-hunter.md:26`), mitigated only if deterministic recall or det fusion still fires (`pdf_judge.py:711-716`, `20-false-fail-hunter.md:26`).

## False-fail hypothesis

**P1068R11-class 15-page golden, `--all-pages`:** page-1 unit check quotes title-block metadata; grounding marks it `ambiguous` (`grounding.py:545-547`), unit returns `review` with zero verified defects but `evidence_uncertain=true` (`unit_judge.py:381-394`); page 4 with a cross-page join quotes dangling tail `"listed in"`; without the escalation anywhere-in-markdown clause the model returns `content_omission`; if the tail is not located in md, it becomes a verified defect (`unit_judge.py:356-360`). Human triage spends minutes on ≥2 pages on an otherwise faithful conversion.

## What would change my mind

A labeled replay on ≥30 golden PDFs in planned all-pages mode measuring (a) **verified-defect false-positive rate ≤0.3%/page** and (b) **unit/document `pass` rate on clean pages after ambiguous-sanction demotion**, with `UNIT_CHECK_SYSTEM_PROMPT` sharing `_CONVERSION_CONTRACT` + PAGE escalation scope text — showing ≤0.1 structural false units per paper without losing p0957r8 page-13 detection.
