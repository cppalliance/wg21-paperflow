# Opus Meta-Review E - Steelman + Balance (langextract)

Scope: keep the verdict fair, not a pile-on. I verified the steelman persona (17)
against source, strengthened its claims where the code supports more, then weighed
every persona criticism for decision-relevance to OUR use case: WG21 conversion-
fidelity adjudication in `packages/whisker/src/whisker/tapetum_llm/`, whose
`grounding.py` grounds LLM evidence spans against paper markdown. Hard constraint
folded into every recommendation: `packages/pipeline` and `packages/paperstore`
are READ-ONLY; any adoption lands inside `packages/whisker` only. All anchors
into the target are relative to `packages/whisker/research/repos/langextract/`.

## Verified strengths (with file:line)

Every steelman code claim reproduced. Two are stronger than 17 stated; one enum
fact in the baseline is slightly off.

- **Monotonic exact-occurrence DP is real and better-engineered than described.**
  `_select_monotonic_matches` (`langextract/resolver.py:1113-1185`) is not a naive
  "successive positions" scan: it is a weighted Pareto-frontier DP that maximizes
  total matched token count, uses `bisect` for O(log n) predecessor lookup over a
  monotone frontier (`resolver.py:1137-1154`), reconstructs the selection via a
  backpointer `_ChainNode` chain (`resolver.py:1180-1185`), and tie-breaks toward
  the earliest-ending chain so repeated mentions resolve to successive occurrences.
  `_apply_monotonic_exact_matches` (`resolver.py:1188-1243`) then assigns
  `MATCH_EXACT` with a `char_interval` derived from tokenizer char spans plus a
  chunk `char_offset` (`resolver.py:1235-1240`). This is the single highest-value
  mechanism, and it is stronger than steelman finding #1 credited: it is a correct,
  test-backed DP, not a heuristic. Our `ground_spans` substring test
  `norm_quote in norm_md` (`packages/whisker/src/whisker/tapetum_llm/grounding.py:49`)
  is occurrence-agnostic and returns no position at all.

- **Graded `AlignmentStatus` + `char_interval` return shape.** Verified enum at
  `langextract/core/data.py:43-47`. Correction to the baseline/steelman: the enum
  has FOUR members (`MATCH_EXACT`, `MATCH_GREATER`, `MATCH_LESSER`, `MATCH_FUZZY`),
  not the three the baseline lists (`00-baseline.md:15`); the extra `MATCH_GREATER`
  does not change the argument but the roster should be accurate. Spans are set at
  `resolver.py:1237-1241`. Our lane returns only `(grounded_spans, dropped_count)`
  (`grounding.py:56`) with no location, so this is a genuine locatability upgrade
  for the tapetum `--inspect` artifact.

- **Dual-gate LCS fuzzy matcher.** Constants verified at `resolver.py:57-58`
  (`_FUZZY_ALIGNMENT_MIN_THRESHOLD = 0.75`, `_FUZZY_ALIGNMENT_MIN_DENSITY = 1/3`).
  `_accept_lcs_match` (`resolver.py:1377-1404`) enforces coverage
  (`matches >= ceil(extraction_len * threshold)`) AND density
  (`matches / span_len >= 1/3`), and `_best_lcs_spans` (`resolver.py:1287-1363`) is
  a real O(n·m²) rolling-row DP that tracks the tightest span per achievable match
  count. The density gate is a legitimate mechanism our single document-level
  `partial_ratio >= 0.90` floor (`grounding.py:51`, `constants.py:50`) lacks: it
  explicitly rejects scattered subsequence hits. (Caveat below: this same tier is
  where the false-positive risk lives, so its value is as an *idea*, not code to
  port verbatim.)

- **Index-keyed ordered parallel yield.** Verified exactly at
  `langextract/providers/gemini.py:487-504`: pre-sized `results[None]*len`, drain
  `as_completed`, write `results[index]`, None-hole check, yield in input order,
  and fail the whole batch on any worker exception (`gemini.py:494-503`). This is
  the same contract as our `StepContext.gather_concurrent` and matches our
  fail-not-partial fidelity invariant. It is a correctness-confirming datapoint,
  not new capability for us (see the product-skeptic point below).

- **Plural stemming.** Verified at `resolver.py:1275-1281`: `lru_cache(10000)`,
  lowercases, strips a trailing `s` when `len>3` and not `ss`. ~7 LOC, closes a
  narrow inflection false-negative gap before fuzzy.

- **First-pass-wins overlap merge.** Verified at `langextract/annotation.py:46-84`:
  later-pass extractions are appended only when their `char_interval` does not
  overlap an earlier one (`annotation.py:71-82`), both intervals required non-None.
  A clean, determinism-friendly fold if tapetum ever runs multi-pass extraction.

- **Test depth on the ported mechanism.** 522 test functions, 37 resolver + 16
  fuzzy-case (`00-baseline.md:25`). Real regression coverage for the exact DP we
  would port. Honest caveat from persona 07: the *public entry path* is largely
  mock-verified (Issue #245 shipped a `TypeError` past the suite), but the resolver
  internals we would lift are behavior-tested.

## Criticisms that are decision-relevant for us vs noise

**Decision-relevant (they shape or bound what we adopt):**

- **LCS gapped wrong-span acceptance** (11 CRITICAL, 20 CRITICAL, 10 CRITICAL).
  `_best_lcs_spans` is subsequence-based; at 0.75/0.333 a 3-token extraction can
  ground to a 9-token noisy window (`fuzzy_alignment_cases_test.py:213-222`,
  `resolver.py:1377-1404`). This is the decisive reason NOT to port Tier 3 as-is.
  It matters precisely because tapetum is a fidelity system: a wrong span in an
  inspect report actively misleads a human reviewer. Mitigation is cheap
  (post-verify `markdown[char_interval]` against the quote, or keep our 0.90 floor
  as the fuzzy tier).

- **Threshold non-portability** (20 HIGH). 0.75 coverage is looser than our 0.90
  document floor; the constant cannot be transplanted, calibration would need a
  labeled tapetum corpus. Bounds the recommendation: adopt the DP, not the numbers.

- **CJK / mixed-script `char_interval` bugs** (Issue #334; 20, 12, 14). WG21 papers
  carry Unicode math, en-dashes, non-Latin author names. Real risk the moment we
  emit spans; today our span-free path sidesteps it. Argues for a narrow ASCII-
  first port with a substring post-check.

- **Cloud deps + no self-hosted schema path + model sovereignty** (13, 22, 19, 15).
  `google-genai`/`google-cloud-storage` are unconditional deps (`pyproject.toml:35-36`);
  no vLLM `guided_json` (grep 0 hits); OpenAI-compatible self-hosted parse success
  <20% (Issue #414). Decision-relevant and dispositive against importing the
  library, and doubly so under our constraint: `pip install langextract` would drag
  cloud SDKs and the schema path we cannot use, and the only sane integration is a
  code port into `packages/whisker`, not a dependency touching pipeline/paperstore.

- **Product-skeptic reality check** (16). Partially correct and the strongest honest
  counter to the steelman: (a) our dominant measured pain is JSON hard-fails
  (9/200), which langextract *worsens* (no schema-retry, `resolver.py:309-321`);
  (b) `gather_concurrent` already exists in-stack and is unused by tapetum, so the
  batching "adoption" buys nothing new. Both are decision-relevant and true. Where
  16 overreaches: dismissing the monotonic DP as "trace prettiness." Repeated-
  mention disambiguation is a genuine gap in our first-occurrence-blind substring
  test, and per whisker's own docs the `--inspect` lane exists specifically for
  human review, so locatable evidence has real audit value in a fidelity product.

**Noise (or out of scope for what we would actually adopt):**

- **Prompt-injection absence** (21, 01 CRITICAL): true about langextract, but
  irrelevant to a grounding-code port. We already have `wrap_source`/`inject_untrusted`
  in pipeline and tapetum uses it (`adjudicate.py:327,348`). We would never import
  their prompt assembly. Keep as a "do not regress / do not copy their prompt path"
  note, not a blocker.
- **max_workers=10 / batch defaults / 429 storms** (03, 06, 18, parts of 16):
  noise for a grounding port; relevant only to concurrency we are not copying.
- **`resolver_params` TypeError, API-contract footguns, `_compat` debt, god-module
  maintainability** (04, 07, 05): all dissolve when you port ~150 LOC of pure DP
  instead of vendoring `resolver.py` or calling the public API.
- **SSRF `fetch_urls`, plugin `entry_point.load()` RCE, unredacted debug logging**
  (01 HIGH): library-runtime features we would not import. Noise for a code port.
- **License** (02): Apache-2.0 permits the port; only obligation is retaining the
  "Copyright Google LLC" attribution / adding a `THIRD_PARTY_NOTICES` entry. A
  checkbox, not a risk.

## Recommended verdict band + decision

**Verdict band: usable-with-conditions. Decision: adopt-partially.**

The fair split is by unit of adoption. As a *dependency or wholesale library*,
langextract is garbage-tier for us: it hard-requires cloud SDKs, has no working
self-hosted schema path, worsens our dominant JSON-failure mode, ships injection-
blind prompt assembly, and could not land inside `packages/whisker` without also
importing machinery we are forbidden to wire through the read-only pipeline. That
is the honest floor, and personas 13/16/19 are right about it. But as a *source of
a specific, well-tested algorithm*, it is usable-with-conditions: the monotonic
exact-occurrence DP plus graded `AlignmentStatus`/`char_interval` return is a
verified, regression-covered upgrade to our occurrence-blind, position-free
`ground_spans`, and it is decision-relevant (repeated-mention disambiguation and
inspect-report locatability are real gaps, not prettiness). The steelman survives
verification on the grounding and batching mechanisms; it does not survive on
schema, self-hosting, or "import the package." Adopt the DP by re-implementing it
inside `packages/whisker`, explicitly reject the LCS Tier-3 density matcher (keep
our 0.90 `partial_ratio` as the fuzzy tier), and gate any emitted span with a
`markdown[char_interval]` post-check to neutralize the wrong-span CRITICAL.

## Top portable detail we could adopt inside packages/whisker only

Re-implement the **monotonic exact-occurrence DP + graded span return** as a
span-emitting upgrade to `ground_spans` (`packages/whisker/src/whisker/tapetum_llm/grounding.py`),
ported (not imported) from `resolver.py:1113-1243`, ~150 LOC, landing entirely in
`packages/whisker`:

- Tokenize the normalized quote and normalized markdown; run `_select_monotonic_matches`
  so repeated evidence phrases (section titles, normative wording, table headers,
  "This paper proposes") map to successive non-overlapping positions in model
  output order instead of always the first substring hit.
- Return `(quote, char_interval, AlignmentStatus)` per span so the `--inspect`
  artifact reports "exact at chars 4120-4187" instead of a bare kept/dropped count.
- Keep the current EVIDENCE_FUZZY_FLOOR = 0.90 `partial_ratio` (`constants.py:50`)
  as the fuzzy fallback tier; do NOT port the 0.75/0.333 LCS gate (wrong-span
  CRITICAL, uncalibrated for us, CJK-fragile).
- Add a one-line post-alignment guard: reject any exact span whose
  `markdown[char_interval]` does not equal the quote after normalization.
- Optional +7 LOC: the `_normalize_token` plural stem before the exact pass.

No new dependency, no cloud SDK, no change to `pipeline`/`paperstore`, and the
fuzzy behavior stays on our calibrated floor. This captures the one thing
langextract genuinely does better than us while shedding everything the other 21
personas correctly flag.
