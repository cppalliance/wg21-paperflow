# a03 - Archaeologist: llm-evidence-reliability

**Verdict:** usable-with-conditions — the corpus correctly diagnosed one-sided missing-quote overclaiming and its Step 1 two-sided filter landed in `grounding.py`/`models.py`, but it scoped itself to evidence precision on LLM-proposed quotes and never addressed generation recall, unit routing, or golden-contract rules that explain PR #286/#295.
**Confidence:** high

## Findings

- [CRITICAL] The corpus's primary finding was one-sided PDF evidence: `ground_spans` ran source-only, then sidecars falsely labeled every survivor `"present in PDF text layer, absent from markdown"` at 40% precision (8/20 genuinely absent on the nine-PR replay). Evidence: `research/llm-evidence-reliability/00-baseline.md:27-39`, `SYNTHESIS.md:28-34`, runtime replay table `SYNTHESIS.md:47-53`. Impact: operators and fusion treated sidecar quotes as proven absences when mechanics only proved source copy fidelity. Answer-class: 4.

- [CRITICAL] SYNTHESIS prescribed a conservative two-sided post-filter: LLM continues to propose missing content; mechanics classify each source-grounded quote as `present_in_candidate`, `candidate_not_found`, `ambiguous`, or drop as `source_ungrounded`, without NLI/RAG or gating. Evidence: `SYNTHESIS.md:9-26`, `103-129`. Impact: this is subtractive verification only — it refutes false missing quotes but cannot surface defects the model never quotes. Answer-class: 4.

- [HIGH] Step 1 landed in production: `classify_candidate_evidence()` wraps `ground_spans` on the candidate, tri-state constants, semantic-operator parity, and surface guards (front matter, TOC, tables, math). Evidence: `grounding.py:50-52`, `96-106`, `225-245`, `419-585`; wired from `pdf_judge.py:688`, `771`, `unit_judge.py:540`. Impact: fixes the 12/20 false-missing sidecar class from the 2026-07-16 replay; does not create new defect detections. Answer-class: 4.

- [HIGH] Sidecar schema extensions landed in `TapetumResult`: `evidence_dispositions`, `evidence_summary`, deterministic sort keys, schema v7. Evidence: `models.py:343-344`, `361-387`; disposition shape emitted at `pdf_judge.py:348`, `535`. Impact: provenance for quote-level refutation/abstention exists; `UnitCheck.verdict_matches_defects` (`models.py:315-320`) still accepts pass-with-empty-defects, so schema cannot force the model to inspect the right unit. Answer-class: 4.

- [HIGH] The corpus explicitly scoped away verdict/generation recall: "Evidence precision, not verdict recall, is the target" and "Do not automatically rewrite the LLM verdict in Step 1." Evidence: `00-baseline.md:24`, `SYNTHESIS.md:131-133`. Impact: even perfect candidate filtering leaves PR #286 (0 accepted defect groups) and PR #295 (0 generated defect claims) untouched when upstream generation/routing fails. Answer-class: 4, 5.

- [MED] Table-semantics research predicted PR #286-class misses but was not implemented: document-wide `ground_spans` cannot compare poll-table cell geometry; grid-scoped row-join/neighbor locate was research-only. Evidence: `10-table-semantics.md:8-12`, `24-36`; partial mitigation only as `_table_tokens_are_present` → `ambiguous` at `grounding.py:558-561`, not cell-level compare. Impact: wrapped `SF`→`S` poll defects remain invisible to evidence verification even if quoted. Answer-class: 1, 2.

- [MED] Persona 26 and 30 anticipated the golden-PR failure mode: boilerplate quotes survive two-sided demotion while "the deciding defect (table cell, `constexpr` line) never appears in evidence," and empty `missing_content` yields pass with no quote audit. Evidence: `26-adversary.md:12`, `28`; `30-steelman.md:10`. Impact: corpus predicted verification asymmetry in substance but framed it as quote-precision hygiene, not as zero recall power on human-verified blockers. Answer-class: 3, 4.

- [LOW] Rejected or dropped follow-ons: NLI/RAG/BM25 chunk retrieval (`SYNTHESIS.md:168-176`, `20-retrieval-verification.md:12-13`), automatic verdict demotion on quote cleanup (`SYNTHESIS.md:177-178`), full `VerifiedClaim` sidecar enum (`17-claim-schema.md:25-86` — partially superseded by `evidence_dispositions`), and olmOCR-style `_present_within` shared helper (`02-candidate-absence.md:14`, `29-simplicity.md:63`). Impact: no recall mechanism was proposed beyond "LLM keeps proposing"; dropped items were precision/surface refinements, not defect discovery. Answer-class: 4, 5.

## False-pass hypothesis

PR #295 HTML: metadata/outline returns `pass` with empty `heading_drift` because `html_outline.py` collects all heading descendant text — the corpus never studied heading normalization or secno stripping (`00-baseline.md:62-64`). Two-sided evidence verification accepts zero generated claims (`00-baseline.md:74-75`); `classify_candidate_evidence` is a no-op when the model emits nothing, and fusion still caps at `review` via coverage-only `source_aware_review_cap`.

## False-fail hypothesis

PR #284-class: a source-grounded prose quote genuinely absent from markdown is classified `candidate_not_found` at `grounding.py:580` — honest "could not locate," not proven absence. If an operator treats `candidate_not_found` as confirmed missing content (legacy sidecar habit from pre-v4 `"absent from markdown"` labels), a faithful conversion with link-wrapped xrefs could still look like a defect until human review.

## What would change my mind

A runtime trace showing PR #286 or #295 produced source-grounded missing-content quotes that `classify_candidate_evidence` demoted to `present_in_candidate` or `ambiguous` — proving verification ate a real human-verified blocker rather than upstream never generating it. Current baseline record: PR #286 one false page-13 claim died as `ambiguous=1`; PR #295 generated defect claims: 0 (`00-baseline.md:50-54`, `74-75`).
