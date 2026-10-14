# 12 - Prefix-Cache Code Auditor

**Verdict:** usable — v11 already ships HMAC per-paper guard tags and APC-friendly user reorder on the PDF lane; per-call `secrets.token_hex(4)` remains only as a library fallback and in `ideal_verify`, not on the production CLI path.
**Confidence:** high

## Findings

- [CRITICAL] **Production CLI no longer draws per-call random guard tags on the PDF lane.** `whisker-tapetum-llm` generates one run secret (`run_guard_secret = secrets.token_hex(16)` at `packages/whisker/src/whisker/tapetum_llm/cli.py:1172`) and passes `guard_tag=_paper_guard_tag(run_guard_secret, pid)` into `judge_pdf_extraction` (`cli.py:1331-1333`). `_paper_guard_tag` is `SRC{hmac.new(run_secret, pid, sha256).hexdigest()[:8].upper()}` (`cli.py:467-479`). Impact: the blocker named in `research/tapetum-llm-speedup/15-prefix-cache-enabler.md:8` is **fixed at HEAD** for fleet PDF runs; APC can reuse identical system suffix + delimiter openers across a paper's ~6 serial calls. Quality risk: none (149-verifier-guard-tag security model).

- [CRITICAL] **Per-call random fallback still exists in judge modules, but only when `guard_tag=None`.** Pattern at every PDF/text-judge call site: `tag = guard_tag or f"SRC{secrets.token_hex(4)}"` (`pdf_judge.py:395`, `pdf_judge.py:660`, `unit_judge.py:250`, `unit_judge.py:789`). Docstrings explicitly document the fallback (`pdf_judge.py:605-606`, `unit_judge.py:783-784`). Impact: direct library/test invocations without `guard_tag` still break cross-call prefix identity; fleet CLI is unaffected. Exact fix path if fallback must die: remove the `or f"SRC{secrets.token_hex(4)}"` branches and require callers to pass `guard_tag` (or thread `_paper_guard_tag` from CLI into any new entry points).

- [CRITICAL] **APC-friendly user layout is implemented for the high-volume call types.** Unit checks lead with shared payload: `CANDIDATE MARKDOWN:\n{inject_untrusted(candidate_md, tag)}\n\n` then `Paper:` / `Unit:` / `Risk signal:` / `SOURCE TEXT` (`unit_judge.py:791-798`). Page escalations lead with `CONVERTED MARKDOWN (full document):` before page-specific raw text (`pdf_judge.py:397-403`). Docstrings cite the intended prefix `[system_prompt + guard_instruction][CANDIDATE MARKDOWN:...]` (`unit_judge.py:785-787`, `pdf_judge.py:391-393`). Impact: calls 2–5 within a paper can share the large markdown KV block once tag + system prompt match — the main lever from `15-prefix-cache-enabler.md:10-11`. Monolith remains single-call (`pdf_judge.py:662-665`: `Paper` → `RAW PDF TEXT` → `CONVERTED MARKDOWN`); metadata check is also unreordered (`unit_judge.py:252-261`) but is one call per paper and explicitly marked "not prefix-cache sensitive" (`unit_judge.py:243-245).

- [HIGH] **Guard primitives are centralized in `pipeline/tools.py`; tapetum imports them directly.** `escape_guard_delimiters` (`tools.py:38-46`), `inject_untrusted` (`tools.py:49-52`), `guard_instruction` (`tools.py:55-62`). SRC tag format: `f"<<<{tag}>>>\n{escaped}\n<<<END_{tag}>>>"`. System assembly pattern (all PDF-lane call types): `SYSTEM_PROMPT + "\n" + guard_instruction(tag)` then user blocks with `inject_untrusted(..., tag)`. Monolith: `JUDGE_SYSTEM_PROMPT` + guard (`pdf_judge.py:660-665`). Metadata: `METADATA_CHECK_SYSTEM_PROMPT` + guard (`unit_judge.py:250-261`). Unit: `UNIT_CHECK_SYSTEM_PROMPT` + guard (`unit_judge.py:789-798`). Page: `PAGE_JUDGE_SYSTEM_PROMPT` + guard (`pdf_judge.py:395-403`). Impact: cross-type full-document KV sharing remains impossible because system prompts diverge at token 0 (`15-prefix-cache-enabler.md:12` still holds); only same-type calls (unit↔unit, page↔page) share the reordered prefix.

- [HIGH] **Cross-check vs verifier 149 (guard-tag): claims match code; recommendation is implemented.** 149 argued HMAC(secret, pid) over per-call random and over bare `sha256(pid)[:8]`. Code matches: HMAC keyed by per-run secret, 8-hex uppercase digest, `SRC` prefix (`cli.py:467-479`). Tests lock stability: same secret+pid → same tag, different pid or secret → different tag, format `SRC[0-9A-F]{8}` (`packages/whisker/tests/test_pdf_judge.py:1975-1997`). 149's load-bearing escape claim matches `pipeline/tools.py:38-46` and `packages/pipeline/tests/test_tools.py:19-26`. Impact: security review gate from 149 is satisfied at code level; ship still needs debug hygiene (149:24) and holdout A/B for reorder attention shift.

- [HIGH] **Cross-check vs verifier 146 (prefix-cache contradiction): pod-side claims stand; client-side blockers are partially cleared.** 146 measured APC already on (`enable_prefix_caching=True`, ~96.7% lifetime token hits) while tapetum counterfactual prefill remained ~17 s uncached. At HEAD, client guard-tag randomization on the fleet path is gone and unit/page reorder is in place, so 146's "guard tags do not zero APC but block document-level sharing" is now **half obsolete for PDF fleet runs** (document-level sharing is structurally enabled). Monolith + metadata still use unique user layouts and different system prompts, so not all six calls share one full prefix. Impact: estimated envelope from `15-prefix-cache-enabler.md:22` (~600–1100 s prefix-only) remains plausible but unmeasured post-v11; 146's decode-dominated lifetime means (~5.91 s decode vs 0.46 s prefill) still caps how much wall time prefix wins buy.

- [MED] **Text lane (HTML `adjudicate_paper`) still uses pipeline `StepContext._guard_tag = field(default_factory=_random_tag)` (`pipeline/runner.py:117-126`), not `_paper_guard_tag`.** One random tag per pipeline run (not per call), injected via `ctx.inject_untrusted` in `_build_triage_message` / `_build_adjudicate_message` (`adjudicate.py:707`, `adjudicate.py:726-738`). CLI text path (`cli.py:1402-1414`) does not pass `run_guard_secret`. Impact: HTML papers (~minority of fleet) do not get HMAC-stable tags; APC reuse is run-stable only. Fix path: thread `_paper_guard_tag(run_guard_secret, pid)` into `adjudicate_paper` and replace `StepContext` tag factory for tapetum.

- [MED] **`ideal_verify.py` still uses per-call random tags** (`ideal_verify.py:142-143`: `CANDIDATE_{token_hex}`, `IDEAL_{token_hex}`). Optional post-judge call; does not affect the six-call PDF cascade. Impact: negligible wall time; prefix-cache irrelevant unless ideal verification volume grows.

- [LOW] **Lane version documents the change.** `_LANE_VERSION = 11` changelog entry: "per-paper HMAC guard tag replaces random per-call tags for prefix-cache reuse; user message reorder puts shared candidate markdown first" (`cli.py:119-122`). Fingerprints bump forces re-eval after deploy. Impact: incremental skip cache invalidates correctly after this lever ships.

## Prompt assembly reference (file:line)

| Call type | System prompt | User message order |
|-----------|---------------|-------------------|
| Monolith | `JUDGE_SYSTEM_PROMPT` + `guard_instruction(tag)` (`pdf_judge.py:660-661`) | Paper → RAW PDF TEXT (wrapped) → CONVERTED MARKDOWN (wrapped) (`pdf_judge.py:662-665`) |
| Metadata | `METADATA_CHECK_SYSTEM_PROMPT` + guard (`unit_judge.py:250-251`) | Paper → SOURCE METADATA → SOURCE OUTLINE → CANDIDATE FRONT MATTER → CANDIDATE HEADINGS (`unit_judge.py:252-261`) |
| Unit check | `UNIT_CHECK_SYSTEM_PROMPT` + guard (`unit_judge.py:789-790`) | **CANDIDATE MARKDOWN** → Paper → Unit → Risk signal → SOURCE TEXT (`unit_judge.py:791-798`) |
| Page escalation | `PAGE_JUDGE_SYSTEM_PROMPT` + guard (`pdf_judge.py:395-396`) | **CONVERTED MARKDOWN** → Paper → Page → RAW PDF TEXT (page) (`pdf_judge.py:397-403`) |

Shared contract block: `CONVERSION_CONTRACT` appended inside monolith/page/unit system prompts via `unit_judge.py` import chain (`pdf_judge.py:193`, `unit_judge.py:140`).

## Is random tag still present?

| Path | Random per call? | Notes |
|------|------------------|-------|
| Fleet PDF CLI (`judge_pdf_extraction`) | **No** | HMAC per-paper tag (`cli.py:1331-1333`) |
| Library fallback (`guard_tag=None`) | **Yes** | `secrets.token_hex(4)` at four call sites above |
| HTML text lane (`adjudicate_paper`) | **No per call; yes per run** | `_random_tag()` once per `StepContext` (`runner.py:117`) |
| Ideal verifier | **Yes** | Two fresh tags per call (`ideal_verify.py:142-143`) |

## Exact path to fix (remaining gaps)

1. **Already done (no action):** `cli.py:467-479` + `cli.py:1172` + `cli.py:1331-1333`; unit/page user reorder in `unit_judge.py:791-798`, `pdf_judge.py:397-403`; `guard_tag` plumbed through `pdf_judge.py:709,824,932,944` and `unit_judge.py:429`.
2. **Optional hardening:** Delete `or f"SRC{secrets.token_hex(4)}"` fallbacks in `pdf_judge.py:395,660` and `unit_judge.py:250,789`; require `guard_tag: str` (breaking for tests that omit it — update `test_pdf_judge.py` / `test_unit_judge.py` fixtures).
3. **HTML lane parity:** Pass `_paper_guard_tag` into `adjudicate_paper` and set `StepContext._guard_tag` explicitly instead of `_random_tag` (`adjudicate.py:799-806`, `cli.py:1402-1414`).
4. **Server (unchanged from 15/146):** APC already enabled on pod per 146; no client code path required beyond prompt identity.

## Estimated saving confidence

| Lever | Status at HEAD | Saving estimate | Confidence |
|-------|----------------|-----------------|------------|
| Per-paper HMAC tag (system + delimiters) | **Implemented** (PDF CLI) | +30–60 s on 3003 s cold run (`15:22`) | **Medium** — code-ready; not re-measured post-v11 |
| Unit/page user reorder (shared markdown prefix) | **Implemented** | +500–900 s (`15:22`, ~75% of unit calls cacheable) | **Medium** — structural prerequisite met; hit rate needs cold-fleet delta scrape (146:31) |
| Server APC + retention | Pod live per 146 | +60–180 s static-system slice (`15:22`) | **High** for pod state; **Low** incremental if already enabled |
| Combined prefix envelope | Partially unblocked | ~600–1100 s (20–37%) (`15:22`) | **Medium** — overlaps metadata short-circuit (v11, ~1341 s class) already implemented separately |

**Bottom line:** Random per-call tags are **not** on the production PDF fleet path. Prefix-cache client prerequisites from persona 15 are **largely landed**; remaining work is HTML-lane tag parity, optional fallback removal, and a measured cold-fleet A/B — not the core PDF fix. Saving confidence is **medium** (architecture correct, dollars unproven without interval metrics).

## False-pass hypothesis

Treating v11 code presence as delivered wall-time savings without a post-v11 cold fleet run: metadata short-circuit already removes 44.6% of unit calls (`145-verifier-metadata-short-circuit`), so the incremental gain from prefix reuse applies only to the surviving call mix — overstating the 500–900 s reorder band if measured against the pre-short-circuit baseline.

## False-fail hypothesis

Re-running persona 15 verbatim and concluding "0% APC hits because per-call random tags" — that claim is **stale** for PDF fleet runs at HEAD; operators might reject an already-shipped lever and hunt for a bug that was fixed in `_LANE_VERSION` 11.

## What would change my mind

A cold 381-paper fleet with v11, `--force`, and 10 s `/metrics` delta scrapes showing interval `prefix_cache_hits/queries` still below 20% on unit-check labels **after** metadata short-circuit — would downgrade reorder savings to garbage and implicate server-side prompt hashing or concurrency interference despite correct client layout.
