# tapetum_llm sighting run over all review candidates (2026-07-01)

First full advisory run of the `tapetum_llm` lane over the whole candidate set,
on the Alliance self-hosted pod (`alliance-pod`, deepseek-v4-pro, 24/7, billed
per hour not per token). Advisory only: nothing here changes a whisker gate
verdict.

## Setup

- Command: `whisker-tapetum-llm --review-all --inspect --trace --service fast=alliance-pod --service deep=alliance-pod --service default=alliance-pod`
- Candidates from `select_candidates` over 382 whisker sidecars: **201**.
- Prompt: the hardened `tapetum_llm.md` (code LLM-readability rules, table
  header/caption mode added this cycle).

## Outcome

- **196 / 201 adjudicated**; 5 failed (see Weaknesses). 200 tapetum sidecars on
  disk (incl. prior smoke runs).
- Suggested-verdict distribution over the 200 sidecars: **pass=76, review=111,
  fail=13**.
- Tier2 escalations: **0** (every tier1 landed outside the ambiguous band; the
  cascade never needed the deep model this cycle).

### Override yield (whisker verdict -> advisory suggested verdict)

| whisker | advisory | count | reading |
|---|---|---:|---|
| review | pass   | 72  | advisory clears 72 review papers as clean (triage win) |
| review | review | 101 | advisory agrees a human should look |
| review | fail   | 13  | advisory escalates concern |
| fail   | review | 6   | **false-fail rescues** (likely shippable) |
| pass   | review | 4   | possible false-pass caught |
| pass   | pass   | 4   | agreement |

The headline is the 72 `review -> pass` (advisory says no human needed) and the
6 `fail -> review` rescues. These are the two populations the lane exists to
find.

## Fix validations

- **False-fail rescue (P3941R4): PASS.** whisker `fail` -> advisory **`review`**,
  confidence 0.95, structure axis `review`/`minor`, primary concern "Heading
  level jump from H2 to H4 in the Wording section ... does not affect content
  fidelity", 1 grounded evidence span. The severity-aware decide fold behaves
  exactly as designed: a cosmetic heading jump no longer reads as a hard fail.
- **Oversize / 413 handling (P2728R12): PASS structurally.** The paper chunks
  into **7 parts** and there is **not a single HTTP 413** anywhere across the 201
  papers. The chunking + serial triage path works.

## Weaknesses found

1. **Model JSON-output robustness (5 papers).** N5044, P2728R11, P2728R12,
   P3725R2, P3842R1 all fail with `JSONDecodeError` (consistently near "line 49
   column 17"), NOT 413 and NOT pod 500. deepseek-v4-pro wraps its structured
   output in a ```json fence and, for these large/complex inputs, emits JSON that
   does not parse even after the 2-attempt retry budget. This is a model
   structured-output quality issue, independent of our chunking work. Candidate
   fixes (future): raise `output_retries`; harden JSON extraction/repair in the
   model backend; or use a more JSON-reliable model for these. The pervasive
   "Raw JSON parse failed (attempt 1), retrying" warnings (which usually recover)
   are the same root cause.
2. **Transient pod instability.** Mid-run the pod returned a burst of ~74
   `InternalServerError` (HTTP 500) and recovered on its own (live probe 200,
   tail all green). A targeted re-run of the failed PIDs filled 84/89. Because
   billing is per hour and the pod is 24/7, re-running is free; a future runner
   could add automatic retry-on-500 with backoff to make a single invocation
   self-healing.

## Suggested review targets for SG (potential golds)

- The 6 `fail -> review` rescues: confirm they are genuinely shippable.
- The 13 `review -> fail`: advisory thinks these are worse than whisker flagged.
- The 4 `pass -> review`: advisory suspects a false pass the gate let through.

## Artifacts

- Run logs: `data/tapetum-run201b.log`, `data/tapetum-refill.log`,
  `data/tapetum-p2728r12.log` (gitignored).
- Per-paper sidecars: `data/whisker/<pid>.whisker.tapetum.json`.
- Side-by-side report: `data/whisker/tapetum-inspect.md`.
