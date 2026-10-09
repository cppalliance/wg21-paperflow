# 30 - Steelman of the Current Design

**Verdict:** usable-with-conditions — prompt-only absence judgment plus one-sided source grounding is architecturally correct for an advisory lane; the 40% quote-precision gap is a labeling and post-filter defect, not proof the LLM-comparison core should be replaced.
**Confidence:** medium

## Findings

- [CRITICAL] **The lane never binds shipping on quote precision; verdict authority stays deterministic.** Evidence: `fusion.py:12-13` (advisory-only), `fusion.py:148-170` (whisker_fail_locked), `whisker/CLAUDE.md:34-35` (no LLM in CI gate). The nine-PR replay improved human agreement **4/9 → 7/9** while quote-level candidate-absence precision was only **8/20 = 40%** (`00-baseline.md:16-24`). Impact: the measured failure is evidence-ranking noise in sidecars, not a broken verdict contract; replacing the whole design overstates the operational harm.

- [CRITICAL] **The monolith judge already performs bidirectional comparison in-prompt; source grounding answers the harder half (hallucination).** Evidence: `pdf_judge.py:493-497` injects both `RAW PDF TEXT` and `CONVERTED MARKDOWN`; `pdf_judge.py:513-520` grounds quotes against the PDF text layer via `ground_spans`; `PageJudgment` docstring at `models.py:107-112` scopes escalation to "presence-scoped confirmation of a deterministic screen flag, not open-ended absence detection." Impact: the LLM sees both corpora and is asked to diff them; post-hoc verification correctly proves the quote exists in source (the claim models most often fabricate). AbsenceBench (`05-web.md:37-43`) shows models fail absence when given both documents — that is why whisker keeps the lane advisory and pairs the LLM with deterministic demotion floors, not why the comparison step should be deleted.

- [HIGH] **What already works: anti-hallucination, localization, and genuine defect discovery.** Evidence: `ground_spans` three-tier exact/fuzzy pipeline (`grounding.py:171-241`, langextract-port per `05-web.md:47-53`); `ground_page_quotes` length-relative fuzzy on flagged pages (`grounding.py:244-278`, `constants.py:176-181`); p0957r8 page-13 escalation with five grounded `[p13]` quotes after `screen_pages` flagged recall 0.881 (`per-page-judging/SYNTHESIS.md`, `tapetum-golden-review-findings-2026-07-14.md:200-209`); PR #293 **5/5** genuinely absent `constexpr` quotes plus 31 dropped declarations the deterministic lane missed (`00-baseline.md:19`, `golden-qa-gap/SYNTHESIS.md:182`). Impact: source-grounded quotes are high-signal operator breadcrumbs even when 60% are reformatted-not-absent; the lane's value is **where** and **what to inspect**, matching Marker/pdf-parse-bench "deterministic pairing first, LLM after unresolved pairs" (`05-web.md:20-35`).

- [HIGH] **Deterministic companions already cap false-pass without a candidate oracle.** Evidence: `pdf_judge.py:527-538` demotes pass→review on `content_recall` / `text_nid` floors; `screen_pages` + `PAGE_RECALL_FLOOR` isolate localized loss (`constants.py:144-154`, calibrated gap 0.8810 vs 0.9129); per-page escalation only on flagged pages, confirmed gaps cap verdict at review (`pdf_judge.py:540-592`); `fusion.py:174-190` blocks `llm_clear_soft_review` when `missing_region_count > 0` because "the LLM cannot verify content absence" for that signal class. Impact: the architecture already admits LLM absence claims are untrusted for **upgrade** decisions; it uses them for **downgrade/localization** under mechanical guardrails — the honest split the web corpus converges on (`05-web.md:180-190`).

- [HIGH] **Text-lane grounding is already two-sided for defect claims (presence in markdown).** Evidence: `adjudicate.py:285-321` grounds evidence spans against `state.paper_md`; ungrounded non-pass demotes to review; pass with only fuzzy grounding demotes; pass with emitted-but-dropped evidence demotes (`adjudicate.py:303-312`). Impact: the text cascade proves the symmetric pattern exists in-tree for "this defect quote is in the output"; the PDF lane's asymmetry is a deliberate scope choice (prove source quote is real, trust in-prompt diff for absence) not an accidental omission.

- [MED] **A full two-sided verifier risks false negatives on sanctioned conversion behavior.** Evidence: `normalized_text()` is punctuation-insensitive (`00-baseline.md:52-53`); judge prompts sanction YAML front matter, TOC removal, figure text, reflow/dehyphenation (`models.py:109-119`, `pdf_judge.py:199-236`); olmOCR `TextPresenceTest` needs length-relative edit guards (`05-web.md:14-18`). Impact: naive candidate `ground_spans` on normalized markdown would suppress real hits (PR #293 `constexpr` with spacing drift) while fixing obvious FPs (PR #285/#290 prose already present); the threshold design is non-trivial and belongs behind labeled replay, not assumed superior to prompt+source-grounding.

- [MED] **The sidecar overstates provenance; the fix is honest labeling, not architectural reversal.** Evidence: `pdf_judge.py:401-404` labels every retained quote `"present in PDF text layer, absent from markdown"` though only source presence is verified (`00-baseline.md:37-39`). Impact: operators and downstream research read a stronger claim than code proves; correcting reason codes and filtering candidate-located quotes preserves the current LLM discovery role while closing the precision gap without NLI, new dependencies, or CI binding.

## False-pass hypothesis

**PR #285 / #290 quote batch (12/12 candidate-present).** The model quotes prose and date lines that survive `normalized_text` substring search in the candidate markdown (`00-baseline.md:17-18`). An operator trusting the sidecar reason string `"absent from markdown"` wastes review time on ghost defects. The verdict demotion stack still worked (human agreement 7/9), so the false-pass is **evidence-list pollution**, not a shipped broken paper.

## False-fail hypothesis

**PR #293 `constexpr` with whitespace or fence drift.** A strict candidate-side exact match on `normalized_text` could drop quotes that are genuinely absent semantically but partially recoverable via fuzzy tier, demoting a real code-axis hit the deterministic lane missed. Two-sided verification must use the same length-relative and fuzzy rescue tiers as source grounding (`ground_page_quotes`, `05-web.md:14-18`) or it trades 60% quote FPs for silent FNs on the highest-value catch in the replay.

## What would change my mind

A labeled holdout of the 20 replay quotes (plus ≥30 new hand-adjudicated quote/source-page labels on WG21 papers) showing that **candidate-side `ground_spans` with olmOCR-style `present | absent | ambiguous` routing** achieves **≥90% absence precision** and **≤10% false-negative rate** on genuinely absent content (PR #293 class), **without** demoting verdict-level agreement below the current 7/9 replay baseline. If candidate checking cannot hit that bar, prompt-only absence plus source grounding remains the smaller, maintainable surface (`29-simplicity` concern).

## Minimum concession (if 40% precision is unacceptable)

Keep prompt-only absence discovery and one-sided source grounding; add a **candidate locate pass** before sidecar emission only:

1. For each source-grounded quote, run existing `ground_spans(quote, tomd_md)` (or `ground_page_quotes` on the scoped page).
2. Emit `present | absent | ambiguous` per quote; never write `"absent from markdown"` unless candidate locate fails at the chosen threshold.
3. Drop or demote quotes where candidate exact/fuzzy locate succeeds (LitRAG pattern: `05-web.md:55-61`).
4. Cap PDF-lane verdict demotion on **confirmed absent** quotes only; do not add NLI, new dependencies, or CI gate binding.

Estimated scope: extend `grounding.py` + `pdf_judge.py:to_sidecar_dict()` reason codes (~40 LOC), reusing `rapidfuzz` and constants already in-tree. The LLM keeps proposing; mechanics decide which quotes survive — the web corpus's lowest-risk pattern (`05-web.md:192-194`) applied as a filter, not a redesign.
