# Opus Meta-Review D - Provenance (llm-stack)

Scope: audited **24 findings across 16 of the 22 persona reports** (01, 02, 03, 04, 06, 08, 09, 10, 11, 13, 17, 18, 19, 20, 21, 22), prioritizing CRITICAL/HIGH. Every cited anchor was re-opened against live source at HEAD, against `00-baseline.md`, or against `05-web.md`. Method: read the file, confirm the line says what the persona claims (not just that the line exists).

Legend: **VALID** = anchor exists and says what the persona claims. **STALE** = claim correct, line number shifted (with cause). **FABRICATED** = anchor does not exist / does not support the claim. **MISQUOTED** = anchor exists but is materially mis-characterized.

Two whole-file freshness causes recur and are **not** persona error (per the task's freshness notes):
- **REVERT** (`model_backends.py`): the raw-JSON retry-budget change was reverted. `_RAW_JSON_MAX_ATTEMPTS` no longer exists; budget is `max_attempts = min(2, request_limit)` at **line 300**. The revert removed ~11 lines, so every persona citation into that file is shifted ~11 lines *up* from HEAD. Confirmed shifts: pins `321-323`→`310-312`/`333-335`; thinking-budget `305-309`→`294-298`; malformation retry append `409-416`→`398-405`; truncation branch `388-404`→`377-393`; `_extract_json`/`json.loads` `373-375`→`362-364`; failure string now reads "after 2 attempt(s)" not "after 3".
- **REFACTOR** (`cli.py`): a `--concurrency N` flag (line 150-157) and an `asyncio.Semaphore`(line 299) + `gather`(line 353) worker (`_adjudicate_one`, 302-349) replaced the old serial `for pid in pids` loop. Every persona citation of the "serial loop `cli.py:277-317`" and "no concurrency flag" is stale by this refactor.

## Sampled findings audit (persona-file: finding -> anchor VALID | STALE | FABRICATED | MISQUOTED)

1. **04 / 08 / 03 [CRITICAL] per-step `max-output`/`thinking-budget` parsed but never forwarded by `run_agent`** -> **VALID (the linchpin finding, fully verified).** `runner.py:266-272` calls `agent.run(system, user_msg, output_type, tools=, label=, debug_log=, request_limit=)` with no `max_tokens`/`thinking_budget`. `agents.py:127-133` docstring does promise "Per-step overrides come from `StepMeta.max_output_tokens` via the runner." `prompt.py:389-390` maps `max-output`/`thinking-budget` into `StepPrompt`. `adjudicate.py:391` hardcodes `max_tokens=4096`, no `thinking_budget`. `model_backends.py` only sets `thinking_token_budget` when `thinking_budget is not None` (now line 294-298). Every link in the three personas' evidence chain checks out.

2. **04 [MED] docstrings/CLAUDE.md name phantom `StepMeta`; public dataclass is `StepPrompt`** -> **VALID.** `prompt.py` returns `StepPrompt(...)` (line 380) and the fields live on `StepPrompt` (108-123); `agents.py:128,133` and `pipeline/CLAUDE.md` say `StepMeta`. Real doc drift.

3. **04 [HIGH] `## Config concurrency` parsed but `adjudicate_paper` hardcodes `default_concurrency=1`** -> **VALID.** `tapetum_llm.md:23` declares `concurrency: 1`; `adjudicate.py:409` hardcodes `default_concurrency=1` (does not read `prompt.config`).

4. **08 [HIGH] "two-tier cascade" is same-service, never escalated** -> **VALID.** `tapetum_llm.md:17-19` (fast/deep/default all `alliance-pod`), gate `adjudicate.py:206-208`, baseline `escalated=0/197` (`00-baseline.md:46`). All anchors confirmed.

5. **08 [HIGH] tier-2 silently disabled for chunked papers** -> **VALID.** `adjudicate.py:200-204` returns early when `state.chunked` with the exact "later upgrade" comment; `tapetum_llm.md:147` describes the band gate without disclosing the chunked skip.

6. **08 / 03 / 01 sampling pins + thinking-off** -> **STALE (REVERT shift, claim VALID).** Pins `temperature=0.0, top_p=1.0, seed=0` are real at 310-312 (stream) / 333-335 (non-stream), not `321-323/344-346`. Thinking gated at 294-298, not `305-309`. Substance correct.

7. **01 [HIGH] tier-1 reasoning injected UNWRAPPED into the tier-2 prompt** -> **VALID.** `adjudicate.py:342-345` embeds `tier1.reasoning`/verdict/worst_axis/concern raw; only `state.paper_md` is wrapped at `:348` via `inject_untrusted`. Confirmed.

8. **01 [HIGH] `SERVICES.toml` supports/uses literal API keys, contradicting the loader docstring** -> **VALID (strong, security-relevant).** `services.py:12-13` docstring: "the key itself is never in the file." `services.py:155-167` implements the literal `api_key` branch (elif `raw_api_key` at 166-167). `SERVICES.toml:50` is a live literal `api_key = "sk-w80putgan2qou8"` (and 79, 90, 102, 113, 132 are more literals). Contradiction is real.

9. **01 [MED] untrusted JSON hits `json.loads` before pydantic, no size cap** -> **STALE (REVERT shift, claim VALID).** `_extract_json`+`json.loads`+`model_validate` are at 362-364, not `373-375`.

10. **01 [LOW] governing doc names `pipeline.tools.wrap_source`, which does not exist** -> **VALID.** Root `CLAUDE.md` Prompt-injection section says `wrap_source`; `tools.py` exposes `inject_untrusted`/`escape_guard_delimiters`/`guard_instruction` (49-62). No `wrap_source` anywhere.

11. **10 [CRITICAL] decide never requires grounded evidence for a `pass`** -> **VALID.** `adjudicate.py:237-238` demotes only `!= VERDICT_PASS and not grounded`; `tapetum_llm.md:99` tells faithful conversions to return `pass` with empty evidence. Confirmed.

12. **10 [HIGH] sanctioned tomd markers are attacker-reachable HTML comments** -> **VALID.** `tapetum_llm.md:83-91` lists the sanctioned markers and instructs the model never to lower a verdict for them.

13. **22 [CRITICAL] short generic quotes exceed the 0.90 fuzzy floor against a whole-document haystack** -> **VALID.** `grounding.py:39` normalizes the entire markdown; `grounding.py:51` accepts `partial_ratio(norm_quote, norm_md)/100 >= EVIDENCE_FUZZY_FLOOR` (`constants.py:50` = 0.90). Reproduced-number claims are the persona's own runtime, methodology sound.

14. **22 / 10 [CRITICAL/MED] `normalized_text` erases math/table delimiter chars so corrupt-math quotes ground** -> **VALID with a MISQUOTE caveat.** `metrics.py:338-340` (`normalized_text = clean_string(textblock2unicode(text))`) and `metrics.py:115-126` (`clean_string`, `[^\w\u4e00-\u9fff]`) confirmed. **Caveat:** the personas (and `00-baseline.md:76`) list `_` among the chars `clean_string` strips, but `_` is a `\w` char and is KEPT by that regex; any subscript-`_` loss happens earlier in `textblock2unicode` LaTeX folding, not `clean_string`. The net-effect claim (`$E=mc^2$` -> `Emc2`, `^`/`$`/`|` gone) is correct and demonstrated; only the attribution of `_`-stripping is imprecise, and it inherits the baseline's own framing.

15. **22 [HIGH] `pass` verdicts need zero grounded evidence** -> **VALID.** Same `adjudicate.py:237-238` gate; `tapetum_llm.md:99`. Confirmed.

16. **21 [CRITICAL] ambiguous band never fired; confidence never in [0.35,0.65]** -> **VALID.** Gate `adjudicate.py:206-208`, `constants.py:22-23`. Uses **198** sidecars (drift-correct per note 3). Reproduced histogram is the persona's own.

17. **21 [CRITICAL] anti-calibration: every `fail` at confidence >=0.95** -> **VALID (anchors).** `models.py:84` (`confidence: float Field(ge=0,le=1)`, no calibration constraint), `constants.py:28` decision floor, `adjudicate.py:239-240` applied. Statistical claim is fresh reproduction.

18. **21 / 11 [MED] chunk aggregation uses min confidence, sorted axes** -> **VALID.** `chunking.py:187` `confidence = min(a.confidence for a in parts)`; `chunking.py:184` `[best[axis] for axis in sorted(best)]`.

19. **20 [CRITICAL] malformation retries append full `raw_content` + nudge into history** -> **STALE (REVERT shift, claim VALID).** The append is at 398-405, not `409-416`; truncation branch (no echo) at 377-393, not `388-404`. Behavior exactly as described.

20. **20 [HIGH] attempt-3 recovered 7/9; raising 2->3 correct** -> **STALE / superseded by REVERT.** The `_RAW_JSON_MAX_ATTEMPTS = 3` state the persona audited has been reverted; HEAD is `min(2, request_limit)` (line 300). The empirical narrative was accurate at run time but its recommendation is now moot at HEAD. Expected per freshness note 1; not persona error.

21. **19 [HIGH] `response_format=json_schema` blocked until vLLM >=0.20.1 (#41199), CJK is #41985 MLA-decode** -> **VALID (web anchors).** `05-web.md:24-26` (#41132), `:16-18` (#16577), `:30-32` (#41985), `:74-76` (structured outputs / guided_json deprecated) all say what the persona claims. Its `model_backends.py:76-85`/`_RAW_JSON_MAX_ATTEMPTS` references are STALE (REVERT).

22. **09 [CRITICAL/HIGH] batch firewall writes no failure sidecar; rerun leaves stale pass** -> **VALID (against refactored cli.py).** `_persist_result` runs only on the success path (line 319); the `except Exception` firewall (334-345) writes nothing, no tombstone. `models.py:106-124` `to_dict` omits `partial`/`chunked`. Line numbers (`cli.py:304-315` etc.) are STALE by the REFACTOR, but every claim holds against current code.

23. **13 [HIGH] pydantic-ai declared with no version floor; only uv.lock pins it** -> **VALID (manifest anchors).** `whisker/pyproject.toml:28` bare `pydantic-ai`, `:17` `rapidfuzz>=3.14.5,<4`, `:30` `python-dotenv>=1.0` all confirmed. Its `model_backends.py` line refs carry the REVERT shift.

24. **02 [HIGH] Apache-2.0 verbatim OmniDocBench normalizers on the grounding path, no NOTICE** -> **VALID.** `grounding.py:19` imports `normalized_text`; `metrics.py` carries the OmniDocBench/PubTabNet ports (whisker `CLAUDE.md` confirms they are verbatim Apache-2.0 ports). BSL headers on all sampled modules confirmed (lines 1-6). Genuine, non-fabricated finding.

Also spot-checked and VALID: `06`/`17` cite the pre-refactor serial loop `cli.py:277-288` (STALE by REFACTOR); `18`'s proposed semaphore+gather+input-order design is essentially what the refactor actually shipped, and its LOW "CLI has no flag yet" is now false-at-HEAD (expected).

## Personas with systematic provenance problems (if any)

**None attributable to persona error.** No fabricated anchors were found in any sampled report; every file:line, baseline number, and `05-web.md` URL/line I checked exists and supports its claim. The two large staleness clusters are repo-side changes the task pre-declared:

- **`model_backends.py` REVERT** touches 06, 09, 13, 17, 19, 20 (and the baseline itself). All cite `_RAW_JSON_MAX_ATTEMPTS = 3` / `model_backends.py:76-85` and the ~11-line-shifted region. Expected per freshness note 1.
- **`cli.py` REFACTOR** touches 06, 09, 17, 18. All cite the serial loop / "no `--concurrency` flag." Expected per freshness note 2.

Minor imprecisions (sub-finding, do not flip any verdict): the Triage per-step budget lines are `tapetum_llm.md:117-118`, but `00-baseline.md:79` and persona **04** wrote `118-119` (off by one); personas 03 and 08 got it right at `117-118`. Persona **11** cited `tapetum_llm.md:55` for the heading-cosmetic sentence that is actually line 54. Persona **06** has a reversed range typo `prompt.py:248-245`. The `clean_string` strips-`_` framing (personas **22**, **10**, and the baseline) is the one genuine MISQUOTE, and it is shared with the baseline rather than invented by a persona.

## Net assessment (3-6 sentences)

Provenance across the sampled findings is strong: out of 24 audited findings I found **zero fabricated anchors** and **zero substantive misquotes that alter a verdict**, only one shared minor mischaracterization (`clean_string` "strips `_`", which it does not) that the baseline itself propagated. The load-bearing CRITICAL findings (per-step budget non-wiring, cascade-never-escalated, pass-needs-no-grounding, fuzzy-floor false-pass, literal API keys, no-failure-sidecar) are each verified end-to-end against live source and are trustworthy to act on. The dominant provenance noise is stale line numbers from two repo-side changes the task flagged in advance: the `model_backends.py` retry-budget revert (~11-line up-shift, `_RAW_JSON_MAX_ATTEMPTS` gone, budget back to `min(2, request_limit)`) and the `cli.py` `--concurrency`/`gather` refactor; both are expected and the underlying claims survive against current code, except that persona 20's "raise 2->3" recommendation is now moot at HEAD. Corpus-count drift (197 vs 198) is reconciled correctly by the personas that re-reproduced (11, 21, 22, 06) and does not constitute error either way. Bottom line: these reports are evidence-grounded, not hallucinated; a synthesis can rely on their anchors after mechanically re-resolving `model_backends.py` and `cli.py` line numbers to HEAD.
