# C07 — Prompt-Injection Boundary Auditor

**Mandate:** Verify prompt injection defenses in the LLM lane.
**Gate dimensions:** G5 (prompt-injection defense), D6 (structured output)
**Auditor:** Prompt-Injection Boundary Auditor
**Date:** 2026-07-19

---

## Summary

The tapetum_llm advisory lane uses the `pipeline` framework's prompt-injection defense consistently. Paper text and model-derived free-text fields are wrapped with `inject_untrusted` / `guard_instruction` before entering any LLM prompt. Structured output (D6) is enforced on all LLM calls via pydantic `output_type`. Evidence quotes are grounded post-hoc and unverifiable quotes are dropped. The defense is comprehensive with minor observations noted.

---

## Finding 1: Triage message wraps paper markdown via inject_untrusted

- **Severity:** PASS (correctly implemented)
- **Claim:** The triage step wraps the paper markdown through `ctx.inject_untrusted()` before it enters the LLM prompt.
- **Evidence:**
  - `adjudicate.py:579`: `wrapped_md = ctx.inject_untrusted(md)` — paper markdown is wrapped.
  - `adjudicate.py:580`: `return header + wrapped_md` — wrapped markdown appended after trusted header.
  - `adjudicate.py:547-550`: Comment: "Independence: no deterministic-lane signals ... are injected. The LLM judges the markdown on its own."
- **Affected gate/dimension:** G5
- **Confidence:** 1.0
- **False-pass hypothesis:** None. The wrapping uses the framework's `inject_untrusted` which adds delimiter tags and escape sequences.
- **False-fail hypothesis:** None.

## Finding 2: Adjudicate message wraps BOTH markdown AND tier-1 outputs

- **Severity:** PASS (correctly implemented)
- **Claim:** Tier-1 free-text fields (reasoning, concern) are themselves model output derived from untrusted paper text, so they are also wrapped before tier-2.
- **Evidence:**
  - `adjudicate.py:598-601`: `tier1_text = ctx.inject_untrusted(f"Tier 1 reasoning: {tier1.reasoning}\n" f"Tier 1 concern: {tier1.primary_concern}")` — model-derived text is treated as untrusted.
  - `adjudicate.py:610`: `wrapped_md = ctx.inject_untrusted(state.paper_md)` — paper markdown also wrapped in the adjudicate step.
  - `adjudicate.py:587-589`: Comment explicitly states: "a paper that smuggled instructions into tier 1's reasoning must not have them replayed to tier 2 as trusted prose."
- **Affected gate/dimension:** G5
- **Confidence:** 1.0

## Finding 3: PDF judge uses inject_untrusted and guard_instruction

- **Severity:** PASS (correctly implemented)
- **Claim:** The PDF-text-layer judge wraps both raw PDF text and converted markdown with `inject_untrusted` and adds `guard_instruction` to the system prompt.
- **Evidence:**
  - `pdf_judge.py:44`: `from pipeline.tools import guard_instruction, inject_untrusted`
  - `pdf_judge.py:401`: `system = PAGE_JUDGE_SYSTEM_PROMPT + "\n" + guard_instruction(tag)` — guard instruction appended to system prompt.
  - `pdf_judge.py:406-408`: `inject_untrusted(page_text, tag)` and `inject_untrusted(tomd_md, tag)` — both inputs wrapped.
  - `pdf_judge.py:627-631`: Same pattern for the monolith judge: `guard_instruction(tag)` in system, `inject_untrusted(pdf_text, tag)` and `inject_untrusted(tomd_md, tag)` in user message.
  - Tag generation uses `secrets.token_hex(4)` for uniqueness per call.
- **Affected gate/dimension:** G5
- **Confidence:** 1.0

## Finding 4: Unit judge (HTML path) uses inject_untrusted and guard_instruction

- **Severity:** PASS (correctly implemented)
- **Claim:** The HTML source-aware unit checks wrap source text and candidate markdown through `inject_untrusted`.
- **Evidence:**
  - `unit_judge.py:30`: `from pipeline.tools import guard_instruction, inject_untrusted`
  - `unit_judge.py:148`: `system = METADATA_CHECK_SYSTEM_PROMPT + "\n" + guard_instruction(tag)`
  - `unit_judge.py:152-158`: Four `inject_untrusted` calls wrapping source metadata, source outline, candidate front matter, and candidate headings.
  - `unit_judge.py:580`: `system = UNIT_CHECK_SYSTEM_PROMPT + "\n" + guard_instruction(tag)`
  - `unit_judge.py:586-588`: `inject_untrusted(source_text, tag)` and `inject_untrusted(candidate_md, tag)`.
- **Affected gate/dimension:** G5
- **Confidence:** 1.0

## Finding 5: Structured output enforced on all LLM calls (D6)

- **Severity:** PASS (correctly implemented)
- **Claim:** Every LLM call uses a pydantic `output_type`, never free-text-to-regex parsing.
- **Evidence:**
  - `adjudicate.py:521-525`: Hook table declares `output_type=Adjudication` for triage and adjudicate steps.
  - `models.py:84-106`: `Adjudication(BaseModel)` — full pydantic model with constrained fields (`reasoning`, `axis_findings`, `verdict`, `confidence`, `evidence_spans`, `primary_concern`).
  - `models.py:30`: `Verdict = Literal["pass", "fail", "review"]` — verdict is a constrained literal, not free text.
  - `models.py:32-40`: `FidelityAxis = Literal[...]` — axis names are constrained literals.
  - `models.py:109-146`: `PageJudgment(BaseModel)` with `model_validator` enforcing consistency between `content_missing` and `missing_content`.
  - `models.py:216-238`: `UnitCheck(BaseModel)` with `model_validator` enforcing `verdict_matches_defects`.
  - `models.py:180-213`: `MetadataOutlineCheck(BaseModel)` with `model_validator` enforcing `pass_requires_no_mismatch`.
  - Field-level constraints: `confidence: float = Field(ge=0.0, le=1.0)`, `max_length=MAX_MISSING_QUOTES`, word-budget descriptions.
- **Affected gate/dimension:** D6
- **Confidence:** 1.0

## Finding 6: Evidence grounding drops unverifiable quotes

- **Severity:** PASS (correctly implemented)
- **Claim:** Post-hoc grounding verifies every LLM-cited evidence quote against the paper markdown; unlocatable quotes are dropped.
- **Evidence:**
  - `grounding.py:248-335` (`ground_spans`): Three-tier verification: exact monotonic DP, fuzzy substring, fuzzy ratio. Unlocatable quotes increment `dropped`.
  - `adjudicate.py:305`: `grounded, dropped = ground_spans(working.evidence_spans, state.paper_md)` — grounding runs in the decide step.
  - `adjudicate.py:321-341`: Safety demotions: ungrounded fail/review -> review; pass with all evidence dropped -> review; pass with fuzzy-only evidence -> review.
  - `grounding.py:308-309`: Post-alignment guard: `if normalized_text(markdown[start:end]) == norm_quote` — the char interval must normalize to the quote.
- **Affected gate/dimension:** G5
- **Confidence:** 1.0

## Finding 7: Test coverage for injection-adjacent behavior

- **Severity:** PASS (adequate test coverage)
- **Claim:** Tests verify grounding logic, candidate evidence classification, and evidence demotion paths.
- **Evidence:**
  - `test_tapetum_llm.py:51-118` (`TestGrounding`): verbatim match, normalized match, hallucinated quote dropped, fuzzy floor edge, empty quote dropped.
  - `test_tapetum_llm.py:120-458` (`TestCandidateEvidenceClassification`): 25+ parametrized tests for semantic parity, operator mismatch, case sensitivity, sanctioned markers, repeated quotes, markdown markup equivalence.
  - `test_tapetum_llm.py:646-757`: Decide step tests: grounding in action, low-confidence demotion, all-evidence-dropped demotion, empty-evidence pass preserved, fuzzy-only demotion.
  - `test_tapetum_llm.py:1041-1057`: Prompt consistency tests (covers all axes, sanctioned markers declared, severity-verdict coupling).
- **Affected gate/dimension:** G5, D6
- **Confidence:** 0.95
- **False-pass hypothesis:** No explicit adversarial injection test (e.g., a paper containing "Ignore all instructions" in its body). However, the defense is structural (delimiter wrapping + structured output), not behavioral, so an adversarial content test would test the LLM, not the defense code.

## Finding 8: Independence invariant (no deterministic signals in prompts)

- **Severity:** PASS (correctly implemented)
- **Claim:** The LLM lane never receives deterministic-lane verdicts, flags, or metrics in any prompt (confirmation-bias defense).
- **Evidence:**
  - `adjudicate.py:547-550`: Comment on triage: "Independence: no deterministic-lane signals (verdict, flags, metrics) are injected."
  - `adjudicate.py:592-594`: Comment on adjudicate: "Independence: no deterministic-lane signals (verdict, flags) are injected."
  - `adjudicate.py:219-225` (`_custom_select`): Loads whisker sidecar into `state.whisker_signals` but this is used only in `_custom_decide` for the `whisker_verdict` field of the result (output, not input to the LLM).
- **Affected gate/dimension:** G5
- **Confidence:** 1.0

---

## Observation: No direct `wrap_source` usage (uses `inject_untrusted` instead)

The CLAUDE.md references `pipeline.tools.wrap_source` as the canonical defense. The tapetum_llm code uses `ctx.inject_untrusted()` (from `StepContext`) and `pipeline.tools.inject_untrusted` / `guard_instruction` directly. These are the same underlying mechanism: `inject_untrusted` IS the function that wraps untrusted content with delimiter tags and escape sequences. `wrap_source` is a higher-level wrapper used in the dissect pipeline; `inject_untrusted` is the primitive. The defense is equivalent.

---

## Verdict

**G5: CLEAN.** All paper text and model-derived free-text entering LLM prompts is wrapped with `inject_untrusted` / `guard_instruction`. The defense is structural and comprehensive.

**D6: CLEAN.** Every LLM call uses a pydantic `output_type` with constrained fields, model validators, and literal types. No free-text-to-regex parsing anywhere.
