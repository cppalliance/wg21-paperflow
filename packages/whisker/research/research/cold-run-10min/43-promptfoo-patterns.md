# 43 - Promptfoo concurrency and caching vs fingerprint skip

**Verdict:** usable — promptfoo's patterns are call-level response cache + suite resume + AIMD concurrency; they are strictly finer than our whole-paper fingerprint for warm/partial reruns, and **strictly useless for a true cold fleet** (empty cache / no sidecars). Nothing in promptfoo beats whole-paper fingerprint *for cold runs*, because cold has nothing to skip.
**Confidence:** high

## Findings

- [CRITICAL] **Promptfoo caches successful provider HTTP responses by full request identity, not by suite or "paper" fingerprint.** Evidence: docs state keys include provider id + prompt/request digest + provider config + context vars ([Caching Configuration](https://www.promptfoo.dev/docs/configuration/caching/)); OpenAI chat path goes through `fetchWithCache` (`src/providers/openai/chat.ts`); fetch keys are `fetch:v3:<sha256(canonicalized url/method/headers/body/format)>` with optional `:repeatN` suffix (`src/cache.ts`, issue [#9509](https://github.com/promptfoo/promptfoo/issues/9509) for cross-process stable HMAC of secrets). Defaults: disk at `~/.promptfoo/cache`, TTL **14 days**, enabled unless `--no-cache` / `PROMPTFOO_CACHE_ENABLED=false`. Errors, empty bodies, and rate-limit paths are not treated as durable hits. Impact on **our cold 3003 s**: **0 s** — first run fills cache; every one of ~2284 distinct judge prompts is a miss. Impact on **warm/dev**: closer to litellm call-cache (`tapetum-llm-speedup/142-litellm-caching.md`) than to `_compute_fingerprint` (`cli.py:595-648`): a unit-prompt-only edit can miss only unit-shaped requests while replaying monolith/metadata if those request digests are unchanged.

- [CRITICAL] **Our skip is whole-paper all-or-nothing; promptfoo has no equivalent paper gate.** Evidence: `_fingerprint_matches` requires every fingerprint key equal (coverage-mode superset only exception) before skipping the entire adjudication (`cli.py:679-702`, `1257-1301`); one `md_sha256` or monolithic `prompt_sha256` change re-runs the full ~6-call cascade (`30-per-unit-fingerprint.md:10`). Promptfoo instead: (a) **response cache** at call granularity; (b) **`--resume`** skips completed `(testIdx, promptIdx)` pairs from the eval DB ([CLI pause/resume](https://www.promptfoo.dev/docs/usage/command-line/), issue [#7606](https://github.com/promptfoo/promptfoo/issues/7606)); (c) **`--retry-errors`** re-runs only ERROR cells. Impact: warm unchanged fleet — our fingerprint already wins (**64.8 s**, 375/381 skip, `00-baseline.md:20`) without replaying LLM JSON from a global disk cache. Partial edit / prompt-class bump — promptfoo-style **call keys** (or our proposed per-unit / call-class hashes in persona 30) beat whole-paper. **True cold** — neither skip mechanism fires.

- [HIGH] **Concurrency: promptfoo default maxConcurrency=4 + AIMD adaptive scheduler; we already run fixed c=32 against 16 server slots.** Evidence: `evaluateOptions.maxConcurrency` defaults to 4 ([configuration reference](https://www.promptfoo.dev/docs/configuration/reference/)); CLI `-j/--max-concurrency`; rate-limit docs describe AIMD (halve on 429, +1 on sustained success, proactive cut when remaining quota &lt;10%) ([Rate Limits](https://www.promptfoo.dev/docs/configuration/rate-limits/), PR [#7262](https://github.com/promptfoo/promptfoo/pull/7262), `docs/scheduler-architecture.md`). Our fleet: `_DEFAULT_CONCURRENCY = 32`, `_MAX_TESTED_CONCURRENCY = 32`, c=381 historically catastrophic (`cli.py:125-138`); baseline forbids slots=32 and c&gt;32 without new evidence (`00-baseline.md:28-29`). Impact: adopting AIMD does **not** cut cold wall when the bottleneck is decode slots and call count; it only softens 429 storms. Our oversubscribe-to-16-slots policy is already more aggressive than promptfoo's conservative default.

- [HIGH] **In-flight request dedupe is a promptfoo nicety we cannot exploit under HMAC guard tags.** Evidence: `fetchWithCache` coalesces concurrent identical `cacheKey` fetches (`src/cache.ts` inflight map). Tapetum appends per-call random guard tags (`unit_judge.py` / `pdf_judge.py` `SRC{token_hex(4)}` pattern cited in `142-litellm-caching.md:10`), so concurrent papers never share a request digest even if markdown overlapped. Impact: **0 s cold**; would need sentinel-normalized keys for any dedupe/cache hit across retries of the *same* call.

- [HIGH] **Repeat / namespace patterns map to our A/A flip protocol, not to cold throughput.** Evidence: when `repeat > 1`, cache is namespaced per repeat index so each iteration keeps a distinct cached output while still replaying on re-run ([issue #8480](https://github.com/promptfoo/promptfoo/issues/8480), `withCacheNamespace` in Node API). Our quality gate needs `--force` cold A1/A2 for flip measurement (`tapetum-llm-speedup/47-quality-equivalence.md`), which is the opposite of cache-hit warm. Impact: use namespaces / `--no-cache` discipline for equivalence runs; do not count repeat-cache as a 10 min lever.

- [MED] **Call-level cache (promptfoo/litellm) is better than whole-paper for *reruns*, worse as a UX for *fleet skip*.** Evidence: persona 142 and 30 already sized this — cold empty cache still **2284 calls / ~3003 s**; unit-prompt-only bump saves ~968–1115 s only when prior call records exist; one-page tomd fix wants per-unit skip (~60 s vs ~120 s per paper), not paper-level re-cascade. Promptfoo's TTL (14 d) is coarser invalidation than our content-addressed sidecar fingerprint (infinite TTL, self-invalidating on hash change). Prefer: keep whole-paper gate for unchanged papers; add call-class / call-level keys for partial invalidation; do not replace fingerprint with TTL disk cache alone.

- [LOW] **CI pattern of hashing config files into Actions cache keys is suite packaging, not adjudication skip.** Evidence: common CI recipes key `~/.promptfoo/cache` on `hashFiles(promptfooconfig.yaml, tests, prompts)` (Green Report resume article). That is equivalent to bumping `_LANE_VERSION` / prompt contract — fleet-wide miss when prompts change. No cold-path win.

## Comparison matrix

| Mechanism | Granularity | Cold fleet (empty store) | Warm unchanged | Partial edit / prompt-class bump | Interrupted run |
|-----------|-------------|--------------------------|----------------|----------------------------------|-----------------|
| **Our whole-paper fingerprint** | Paper sidecar | No skip (3003 s) | 375/381 skip (64.8 s) | Full paper re-cascade | N/A (per-paper restart) |
| **Promptfoo response cache** | Per HTTP/LLM call | All miss | Replay identical calls | Only changed digests miss | Helps if cache survived |
| **Promptfoo `--resume`** | `(testIdx, promptIdx)` | N/A (new eval) | N/A | N/A | Skip completed cells |
| **Promptfoo AIMD `-j`** | Request slots | Throughput only | Throughput only | Throughput only | Throughput only |
| **Proposed per-unit / call-class** (persona 30) | Call class / unit | No skip | Same as whole-paper for full match | Partial re-LLM | Partial |

## Answer: anything better than whole-paper fingerprint for cold runs?

**No.**

For a greenfield cold run (no sidecars, empty LLM response cache), skip granularity is irrelevant: every paper and every call is a miss. Promptfoo's call-level cache, resume DB, and AIMD scheduler do not reduce the first-run call census (~2284) or the 16-slot decode wall.

What *is* better than whole-paper fingerprint:

- **Warm / surgical / prompt-bump reruns:** call-level or call-class keys (promptfoo/litellm style, or persona 30 per-unit) beat all-or-nothing paper fingerprints.
- **Cold wall toward 10 min:** still the settled non-skip levers — metadata-fail short-circuit, APC/prefix reuse, dual-pod, verdict-first schema, client stalls (`00-baseline.md:32-38`) — not a smarter fingerprint.

## False-pass hypothesis

**Stale call-cache hit after schema tighten without schema in the key:** promptfoo stores provider JSON; if `response_format` / schema is omitted from the digest, an old structured body could replay under a stricter Pydantic model. Mitigation already in our fingerprint (`schema_sha256`) and required for any call-level port (`142-litellm-caching.md` false-pass).

## False-fail hypothesis

**none found for cold** — empty cache cannot invent fails. For warm call-cache: replaying a prior `fail` when the operator wanted a fresh MoE sample is intentional freeze, not a false-fail relative to the first adjudication.

## What would change my mind

A measured cold fleet where **≥10% of the 2284 call payloads are byte-identical across different PIDs** (after stripping guard tags) would make in-flight dedupe / shared call-cache a real cold lever. Today HMAC tags and per-paper markdown make that false; if proven, promptfoo-style request coalescing would matter on cold, not just warm.
