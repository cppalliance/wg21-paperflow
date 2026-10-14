# 106 - sglang-RadixAttention

**Verdict:** usable-with-conditions — sglang RadixAttention is real and DeepSeek-V4-Pro is supported, but for our tapetum-llm fleet the incremental win over a correctly tuned vLLM APC pod is small relative to migration cost; fix guard-tag placement and enable vLLM APC retention first, then benchmark sglang only if wall stays above target.
**Confidence:** medium

## Findings

- [CRITICAL] RadixAttention is a radix-tree KV index, not a separate attention kernel: `RadixCache` stores token-id paths in a `TreeNode` hierarchy, `match_prefix` walks the tree and returns concatenated KV indices for the longest cached prefix (`radix_cache.py:355-413`, `radix_cache.py:650-674`). `RadixAttention` (`layers/radix_attention.py:91-94`) is the model attention layer that consumes paged KV from that pool. Impact: same fundamental mechanism as vLLM APC (longest-prefix reuse); no magic bypass of our 6× full-document prefill unless prompts share a leading token sequence.

- [HIGH] Page granularity matches vLLM block APC: keys are truncated with `page_aligned()` before match/insert (`radix_cache.py:136-140`, `radix_cache.py:398`, `RadixKey.match:162-196`), and trailing sub-page tokens are explicitly not inserted into the tree (`radix_cache.py:535-537`). Impact: partial-block waste is identical in kind to vLLM's 16-token blocks; fixing prompt order helps both stacks equally; expected saving 0 incremental vs vLLM once both are page-aligned.

- [HIGH] Node splitting gives finer-grained reuse within pages only at page boundaries: when a match ends mid-segment, `_split_node` refines the tree (`radix_cache.py:661-662`, `radix_cache.py:676-696`). Impact: marginal vs vLLM hash-block splitting; at most low single-digit % extra hit rate on our long shared-document prefixes; not enough alone to justify pod migration (~0–120 s on 3003 s cold run).

- [HIGH] Cache-aware scheduling exists but defaults OFF and does not fit our serial per-paper call pattern. Policies `lpm` (longest-prefix-match) and `dfs-weight` sort the waiting queue by matched prefix length (`schedule_policy.py:147-151`, `schedule_policy.py:212-215`, `schedule_policy.py:312-322`); default `schedule_policy` is `fcfs` (`server_args.py:776-791`). In-batch prefix caching deprioritizes queued requests that share a long prefix with another waiter (`schedule_policy.py:278-308`, thresholds at `schedule_policy.py:77-86`). Impact: with 32 cross-paper concurrent clients but serial 6-call chains per paper (`00-baseline.md:36-42`), call N+1 is submitted only after call N finishes, so it never sits in the waiting queue alongside call N — LPM/in-batch buy ~0 s on the 3003 s run; vLLM APC on sequential submission already reuses call-1 KV for call-2..6 once prompts align.

- [HIGH] Our guard-tag at the end of the system prompt caps shared prefix before the full markdown, blocking both stacks equally. Baseline: random `SRC{hex}` tag appended to every judge system prompt breaks identity at the system tail (`00-baseline.md:48-52`). sglang requires identical leading token ids; `extra_key` namespaces are disjoint (`radix_cache.py:358-367`). Impact: until guard tag moves after shared content (user message tail) or becomes stable per paper, expected prefix hit rate stays near 0% for document body on BOTH vLLM and sglang — fixing this client-side is prerequisite and worth ~1000–1500 s if hits reach vLLM trace levels (74% hits, 4.5× throughput at 16 slots per `05-web.md` Q1); sglang adds no extra leverage here.

- [MED] Eviction: configurable LRU (default), LFU, SLRU, priority (`evict_policy.py:16-65`, `utils.py:55-74`, `radix_cache.py:565-592`, default `radix_eviction_policy: lru` at `server_args.py:862-874`). DeepSeek-V4 uses hybrid SWA radix with tombstone-aware matching (`swa_radix_cache.py:888-943`). Impact: SLRU/LFU could reduce scan pollution when 381 papers cycle (`05-web.md` Q4 UniCache note), maybe 5–10% hit-rate stability under 16-slot pressure vs vLLM LRU after PR #43447 retention fix — quality risk none if hits are identical tokens; worth A/B only after vLLM baseline is tuned.

- [MED] DeepSeek-V4-Pro on sglang: model registered (`models/deepseek_v4.py:98`, `627`), defaults hook exists (`arg_groups/deepseek_v4_hook.py:14-63`), MTP/EAGLE speculative paths present. Impact: migration is technically feasible but operational risk is real — olmOCR moved sglang→vLLM at v0.1.75 (`05-web.md` Q2), our pydantic-ai structured-output stack is vLLM-validated, and a second serving stack doubles ops surface; budget 2–5 engineer-days for parity bake-off before any fleet cutover.

- [LOW] RadixAttention can be disabled (`disable_radix_cache`, `server_args.py:880-882`); default enabled. HiCache hierarchical/offload paths add complexity we do not need for a single-pod judge fleet. Impact: none for speedup decision.

## False-pass hypothesis

Fixing guard-tag placement and enabling prefix cache on either stack could let a stale KV prefix from paper A partially match paper B if prompts were incorrectly structured (shared static prefix without per-paper `extra_key` isolation). sglang namespaces via `RadixKey.extra_key` (`radix_cache.py:74-75`, `358-367`); our client must keep per-paper salt in `extra_key` or ensure divergence before any paper-specific source text. Silent wrong-unit verdict if document KV is reused across papers.

## False-fail hypothesis

Aggressive SLRU eviction (`radix_eviction_policy=slru`) under 381-paper cold scan could evict hot in-flight paper prefixes before call 6, forcing full re-prefill and inflating wall time without changing verdicts — looks like a regression, findings unchanged. Same class of false-fail as vLLM APC LRU scan pollution (`05-web.md` Q4).

## What would change my mind

A controlled replay of 20 representative tapetum papers (6 serial calls each, guard-tag fixed, 16 slots) showing sglang `--schedule-policy lpm` achieves >15% lower aggregate prefill wall than vLLM APC with PR #43447 + retention env on the same H200 pod, with identical structured JSON outputs — would flip to "pod migration worth evaluating."
