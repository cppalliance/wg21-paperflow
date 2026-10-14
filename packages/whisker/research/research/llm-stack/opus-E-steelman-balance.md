# Opus Meta-Review E - Steelman + Balance (llm-stack)

Self-target: `packages/pipeline/src/pipeline/` (framework, READ-ONLY) + `packages/whisker/src/whisker/tapetum_llm/` (advisory lane).
Decision axis for a self-target: keep / harden / redesign. All claims below re-verified against code this run (HEAD state), not taken on persona faith.

Scope law applied throughout: a recommendation is **whisker-local** only if it lands entirely inside `packages/whisker`; a change touching `packages/pipeline` or `packages/paperstore` is **out-of-scope-pipeline** and parked; a change to the running vLLM deployment or `SERVICES.toml`/secrets config is **infrastructure**. The retry-budget bump (2->3) was already reverted for exactly this reason and is confirmed reverted below.

---

## Verified strengths (with file:line)

Every strength here was opened and read, not inherited from persona 17.

- **Advisory contract is real and airtight.** The CLI docstring states "never touches `whisker --gate`, never changes whisker verdict, exit code always 0" (`cli.py:11-14`) and `_EXIT_OK = 0` is the only exit constant (`cli.py:37`). A false-negative pass therefore cannot pollute the deterministic CI gate. This is the single most important property: it caps the blast radius of every other defect in this review. The lane can be miscalibrated and still be safe to run.

- **Fail-not-partial and never-upgrade demotions are enforced in the decide step, read line by line.** `_custom_decide` recomputes the overall verdict from the severity-aware worst axis, overriding the model's self-reported overall so a minor axis fail cannot become a hard fail (`adjudicate.py:229-232`). Safety demotions only ever move toward review, never toward pass: ungrounded non-pass -> review (`adjudicate.py:237-238`), sub-floor confidence -> review (`adjudicate.py:239-240`), partial read that came out pass -> review (`adjudicate.py:245-246`). There is no code path that upgrades a verdict. Verified: `suggested_verdict` is only ever assigned `VERDICT_REVIEW` in the demotion block.

- **The raw-JSON retry policy splits truncation from malformation, and this is not marketing.** Read at `model_backends.py:361-410`: on `finish_reason == "length"` it grows `effective_max` by `_RETRY_MAX_TOKENS_GROWTH`, capped at the context window, and **re-issues the original two-message request** with no truncated-output echo and no "invalid JSON" nudge (`:377-393`); only genuine malformation appends the bad turn plus a corrective user message (`:394-406`). The truncation branch is precisely the anti-context-contamination behavior the literature (arXiv 2605.08563, `05-web.md` Q5) says naive loops get wrong. The malformation branch does echo history, which is a real weakness (see criticisms), but the split itself is sound engineering.

- **Sampling pins are baked at the call site, not aspirational.** Both the streaming and non-streaming `chat.completions.create` calls pin `temperature=0.0, top_p=1.0, seed=0` (`model_backends.py:310-312` and `:333-335`). D5 is mechanically satisfied.

- **Prompt-injection defense is a first-class, correct implementation.** `escape_guard_delimiters` neutralizes forged start/end tags before wrapping (`tools.py:38-46`), `inject_untrusted` wraps in per-run random tags (`tools.py:49-52`, tag from `secrets.token_hex` at `:33-35`), `guard_instruction` tells the model to treat delimited text as data (`tools.py:55-62`), and the scoped `read_paper` tool re-wraps every chunk and clamps to `max_lines=500` (`tools.py:94-100`, `:70`). This is more than most extraction stacks ingesting adversarial WG21 markdown ever build.

- **Grounding is an active post-hoc verifier, exercised in production.** `ground_spans` checks each quote by normalized substring OR `rapidfuzz.partial_ratio >= EVIDENCE_FUZZY_FLOOR` and drops empty-normalized quotes (`grounding.py:44-54`, floor `constants.py:50`). 9/197 sidecars dropped at least one span (`00-baseline.md:47`), so it is load-bearing, not decorative.

- **Determinism hygiene on the output path is verified good.** Persona 03 checked and I concur from the baseline anchors: `select_candidates` sorted (`adjudicate.py:94`), `TapetumResult.to_dict` sorts spans/axes (`models.py:116-119`), chunk aggregation sorts axes (`chunking.py:184`). The `Adjudication` schema carries 7 fields, above the >=5-field constrained-decoding stability floor (`models.py:80-86`, `MODELS.md:36-53`).

**Steelman one-liner:** this is a serious stack with the *hard* parts right (advisory isolation, fail-not-partial, injection defense, sampling determinism, truncation-aware retry). What is wrong is calibration, disclosure, and grounding tightness, none of which is a wrong foundation. That is the definition of *harden*, not *redesign*.

---

## Decision-relevant criticisms vs noise

Ranked by whether the finding should move the keep/harden/redesign decision. "Decision-relevant" = changes what we do. "Noise" = true but does not change the decision (out-of-scope with no tapetum-behavior impact, mooted by another action, or theoretical under current runtime).

### Decision-relevant (act on these)

1. **The two-tier cascade is single-tier in production.** `escalated=true` in 0/197 sidecars; the ambiguous band `[0.35, 0.65]` (`constants.py:22-23`) never fires because DeepSeek self-reports 0.85-1.00 (mean 0.9586), and even if it fired both `fast` and `deep` resolve to the same `alliance-pod` (`tapetum_llm.md:17-19`), so escalation is a no-op model swap (personas 21, 08, 12, 16). Verified at the gate: `adjudicate.py:206-208`, and chunked papers skip tier2 entirely (`adjudicate.py:203-204`). **Relevance: HIGH.** This is the headline honesty gap. It does not break correctness (single-tier DeepSeek still produces safe advisory sidecars), so it is calibration + documentation debt, which is a *harden*, not a *redesign*.

2. **Self-reported confidence is anti-calibrated and is the wrong escalation trigger.** Every suggested `fail` carries confidence >= 0.95 (persona 21). The model expresses real internal conflict (per-axis verdicts disagree on 123/198 papers) while reporting 0.95 overall. **Relevance: HIGH.** The fix is not "tune the band"; it is "escalate on a derived signal" (axis disagreement, ungrounded-drop count, retry count). Whisker-local.

3. **The stated false-pass mission is under-delivered.** PRIMARY (whisker-pass papers with risk signals) delivered 1 substantive catch in 6 (persona 16); cross-chunk section swaps and table row swaps can pass at 0.95 with empty evidence (persona 12 hypotheses a/b/c). The `cov_unigram_gap` trigger, the direct permuted-section proxy, fired on 0/6 PRIMARY papers (persona 16). **Relevance: HIGH** for whether the lane earns its keep. Counterweight (kept fair): RESCUE works 9/9 and the review-amplifier role produced 18 real table/structure `fail` sidecars. So the lane delivers value on two of three populations; PRIMARY needs selector + order-check hardening. Whisker-local.

4. **A `pass` requires zero grounded evidence.** By contract (`tapetum_llm.md:99`) and code (`adjudicate.py:237-238` demotes only non-pass), all 73 production passes carry no machine-verified span (personas 12, 07). **Relevance: MEDIUM-HIGH.** A confident hallucinated pass is schema-indistinguishable from a real one. Whisker-local, but gate the fix on a labeled mini-eval (forcing corroboration on every pass risks manufacturing review noise).

5. **Grounding accepts generic short quotes and math-corrupted quotes.** `partial_ratio` on a whole-document haystack scores 0.90+ for boilerplate like "the following table"; `normalized_text` strips `^ _ | $`, so `$E=mc$` grounds against `$E=mc^2$` (persona 22, reproduced). **Relevance: MEDIUM.** Tempered honestly: grounding only *softens* non-pass verdicts, so a weak floor prevents a demotion-to-review, it does not manufacture a shippable pass. Still worth a min-quote-length gate + locality gate. Whisker-local (`grounding.py`, `constants.py`).

6. **Failure/rerun leaves a stale or absent sidecar; partial state is not disclosed.** On rerun failure the old `pass` sidecar survives (no tombstone/error write, `cli.py:289`, `:304-315`); `partial`/`chunked` are omitted from `to_dict` (persona 09). **Relevance: MEDIUM.** Data-integrity gap, cheap, whisker-local (`cli.py`, `models.py`).

7. **CJK-token-injection hard-failure class (9/200).** Root cause is a vLLM MLA FP8 decode bug (#41985), fixed upstream by #42287; DeepSeek-V4 structured-output routing needs #41199 (>= v0.20.1) (personas 19, 20, 03; `05-web.md` Q2/Q1). **Relevance: HIGH, but the fix is infrastructure, not code.** This is the accepted resolution per the task brief. The 2->3 retry bump that personas 07/20 lean on is **reverted** (confirmed `max_attempts = min(2, request_limit)` at `model_backends.py:300`); do not reintroduce it in pipeline.

8. **Over-review noise: 84/106 reviews are structure-only minor heading cosmetics** the prompt itself calls shippable (persona 11). **Relevance: MEDIUM.** A decide-step fold (sole non-pass axis == structure + minor -> pass) is whisker-local, but persona 11's own bar is right: gate it on a labeled holdout, because if human-pass rate on those is <=50% the 54% review rate is correct conservatism.

9. **Per-step budgets are not wired; thinking is off; triage runs at 4096 not 2048.** The most-cited CRITICAL (personas 04, 08, 03, 07): `run_agent` never forwards `spec.step.max_output_tokens`/`thinking_budget` (`runner.py:266-272`), contradicting the `agents.py:127-133` docstring. **Relevance: HIGH in substance, but the framework fix is OUT-OF-SCOPE (pipeline).** Critical balancing correction the personas missed: tapetum builds its own `AgentBackend` per slot at flat `max_tokens=4096` with no `thinking_budget` (`adjudicate.py:388-396`), and step->slot is 1:1 (triage=fast, adjudicate=deep). So the authority-doc *intent* (fast 2048/1024, deep 4096/4096) is achievable **whisker-locally** by constructing those two agents with the right per-slot kwargs, since `AgentBackend.run` resolves `None` to construction defaults. The runner-forwarding contract stays parked; the observable defect (thinking off, wrong budgets) is fixable in `adjudicate.py`.

### Noise (true but does not move the decision)

- **Framework-contract hygiene with no tapetum impact:** phantom `StepMeta` docstring, `run_task` missing overrides, `dispatch` parallel branch running serially (persona 04 MED/LOW). All pipeline-internal; tapetum uses custom hooks calling `run_agent` and runs serial. Out-of-scope and behaviorally inert for this lane. Note for the record, do not act.
- **Malformation-retry history echo / context contamination** (personas 20, 03, 01). Real, but (a) lives in `model_backends.py` = out-of-scope, and (b) largely mooted once #42287 removes the CJK trigger that causes the retries. Park.
- **Tier1->tier2 unwrapped injection** (persona 01 HIGH). Theoretical today: tier2 never fires (escalated=0). Becomes live only if calibration is fixed; harden it in the same change, not before.
- **`## Config concurrency` parsed but ignored** (persona 04): 1-line whisker-local tidy, no runtime effect today. Trivial.
- **Test-suite gaps that target pipeline paths** (persona 07 CRITICAL is a `test_runner.py` test = out-of-scope). The whisker-side test gaps (CLI batch loop, cascade boundary values, confident-pass-with-dropped-spans) are real and whisker-local.

---

## Recommended verdict band + decision

**Verdict band: usable-with-conditions.** No persona of 22 returned `garbage`; the modal and correct verdict is usable-with-conditions. The stack's hard invariants (advisory isolation, fail-not-partial, injection defense, sampling pins, truncation-aware retry) are implemented and verified. The conditions are calibration, disclosure, grounding tightness, and one infrastructure upgrade, all bounded and none foundational.

**Decision: HARDEN (keep the architecture, fix the operating points).**

Justification, weighed against the redesign alternative:

- **Why not `keep` as-is:** four independent findings (dead cascade, under-delivered PRIMARY mission, evidence-free pass, stale-sidecar) show the lane does not yet reliably do the one job it exists for (catch token-preserving false-passes) and can hide data loss. Shipping it unchanged is not honest given the authority doc's cascade and cost narrative.
- **Why not `redesign`:** every defect has a local remedy that survives the governing invariants (D1-D11, model-sovereignty, fail-not-partial). Nothing requires re-architecting the framework or the lane. The advisory contract already contains the blast radius. Redesign would discard working, tested injection/determinism/retry machinery to fix calibration and disclosure, which is disproportionate.
- **Highest-leverage single action is infrastructure, not code:** upgrade the pod (#42287 + #41199). It retires the primary `MODELS.md:121` retire-when row and the hard-failure class with zero code change.
- **The load-bearing honesty fix is whisker-local:** make the cascade either genuinely two-tier (split the `deep` slot to a different model) or collapse it to an honest single tier in the authority doc, and switch escalation to a derived uncertainty signal. Both live in `packages/whisker`.

---

## Actionable recommendations bucketed

### whisker-local (implementable entirely inside `packages/whisker`)

1. **Fix the cascade at the trigger, not the band.** In `_custom_adjudicate` (`adjudicate.py:195-212`) gate escalation on a derived uncertainty signal (per-axis verdict disagreement, `ungrounded_dropped > 0`, or malformation-retry occurrence) instead of the scalar self-reported `confidence`, which is anti-calibrated. Refit `CONFIDENCE_AMBIGUOUS_LO/HI` (`constants.py:22-23`) only after a labeled mini-eval exists. (Personas 21, 12, 16.)
2. **Achieve the documented per-step budgets and thinking in `adjudicate.py`.** In the agent construction dict (`adjudicate.py:388-396`) pass per-slot `max_tokens`/`thinking_budget`: `fast` -> 2048/1024, `deep` -> 4096/4096, matching `tapetum_llm.md`. This delivers the authority-doc intent with no pipeline edit (`AgentBackend.run` resolves `None` to construction defaults). Requires the `alliance-pod` backend be `thinking_capable`; if not, keep thinking off and document it. (Substance of personas 04/08/03/07, remedied locally.)
3. **Harden grounding.** In `ground_spans` (`grounding.py:44-54`) add a minimum normalized-quote-length gate before the whole-document fuzzy path (short quotes must satisfy substring, not fuzzy), and/or add a locality/coverage gate. Consider raising `EVIDENCE_FUZZY_FLOOR` (`constants.py:50`) or requiring a matched char interval. (Persona 22.)
4. **Give `pass` a corroboration requirement on PRIMARY candidates**, or annotate every pass as "unverified (no grounded span)" in the sidecar. Gate the stricter form on a labeled mini-eval to avoid manufacturing review noise. (Personas 12, 07.)
5. **Close the disclosure/idempotency gaps in `cli.py`/`models.py`.** On adjudication failure, write an error/tombstone sidecar (`failed: true`, exception class) or delete the stale one (`cli.py:289`, `:304-315`); add `partial` and `chunked` to `TapetumResult.to_dict` (`models.py:106-124`); extend partial demotion beyond pass-only (`adjudicate.py:245-246`) so a partial-read fail/review is flagged partial. (Persona 09.)
6. **Strengthen PRIMARY selection and add a deterministic order check.** Make `select_candidates`/`_has_pass_risk_signals` (`adjudicate.py:82-109`) actually forward the `cov_unigram_gap` permuted-section proxy, and inject an H2 section-index manifest so cross-chunk reordering is detectable (`chunking.py`, `adjudicate.py:187-192`). (Personas 16, 12.)
7. **Add `--concurrency N` (default 1) paper-level fan-out in `cli.py`** using a CLI-local `asyncio.Semaphore` + `gather` with input-order merge, per persona 18's design. This is the sanctioned D11 hook (never touch framework semaphores). Determinism-safe only under batch-invariant infra (below) or with an explicit "N>1 optimizes wall-clock, not rerun identity" note in `--help`/`tapetum_llm.md`.
8. **Consider a decide-step fold for structure-only-minor -> pass**, gated on a labeled holdout showing >=80% of those are human-shippable (persona 11's bar). Do not ship blind.
9. **Wrap tier1 fields before they enter the tier2 prompt** in `_build_adjudicate_message` via `ctx.inject_untrusted` (`adjudicate.py:342-348`); validate PID before path construction (`cli.py`). Do these alongside the cascade fix, since tier2 is dead until then. (Persona 01.)
10. **Correct the docs** (`tapetum_llm.md`, `whisker/CLAUDE.md`): rewrite the cascade section to match same-service reality or the new split; disclose the chunked-tier2 skip; soften "verbatim" grounding to reflect OmniDocBench normalization; soften the "every call is deterministic" claim to serial-but-not-bit-exact. (Persona 08.)
11. **Add whisker-side regression tests**: CLI batch-loop firewall + retry filter, cascade boundary values (0.34/0.35/0.65/0.66), and confident-pass-with-all-spans-dropped. (Persona 07, whisker-side only.)

### infrastructure / pod (no repo code change)

1. **Upgrade `alliance-pod` to vLLM >= 0.20.1 containing #42287 (CJK MLA decode fix) and #41199 (DeepSeek-V4 structured-output routing).** Highest-leverage single action; retires `MODELS.md:121` and the 9/200 hard-failure class. Re-run the 200-paper batch to confirm hard failures drop. (Personas 19, 20, 03.)
2. **Provision a genuinely larger/different `deep` model pod and repoint the `deep` slot** (`SERVICES.toml` add service + `tapetum_llm.md` slot map, or `--service deep=NAME`). Without this, a working escalation is still a no-op model swap. If no second pod is justified, do the honest single-tier collapse instead (whisker-local doc change). (Personas 21, 08, 12.)
3. **Enable `VLLM_BATCH_INVARIANT=1`** if paper-level `--concurrency N>1` is adopted, to keep advisory verdicts stable under continuous batching (~50% throughput cost). Optional given the lane is advisory; required if we want rerun-comparable distributions. (Personas 03, 18.)
4. **Move the `SERVICES.toml` literal `api_key` to an env reference** and rotate (`services.py:155-167`, `SERVICES.toml`). Secret hygiene; config action, not code. (Persona 01.)
5. **(Precondition, optional) enable `response_format=json_schema` + `--reasoning-parser deepseek_v4`** on the upgraded pod, so a future opt-in guided-decoding backend flag has a server to talk to. (Persona 19 adoption checklist.)

### out-of-scope-pipeline (park it; would require editing `packages/pipeline`)

1. **Forward `spec.step.max_output_tokens`/`thinking_budget` from `run_agent` to `AgentBackend.run`** (`runner.py:266-272`) and fix the `agents.py:127-133` docstring. Correct fix for the general framework contract, but pipeline is read-only. Parked. (The tapetum-visible symptom is remedied by whisker-local item #2 above.)
2. **Re-raise the raw-JSON retry budget 2->3** (`model_backends.py:300`). Already reverted by policy; the CJK failure class is handled by the pod upgrade. Do not reintroduce. (Personas 07, 20.)
3. **Clean-restart the malformation retry (drop the history echo)** (`model_backends.py:394-406`). Real anti-contamination improvement, but pipeline-internal and mostly mooted by #42287. Parked. (Personas 20, 03, 01.)
4. **Wire `dispatch` parallel branch to `gather_concurrent`, and validate `spec.step.thinking_budget` in `validate_capabilities`** (`runner.py:358-375`, `validate.py:121-128`). Framework hygiene, no tapetum impact today. Parked. (Persona 04.)
5. **Pydantic-ai history-trimming / VLLMProvider adoption** (`MODELS.md:117-121` retire-whens). Upstream-dependent framework work. Parked.
