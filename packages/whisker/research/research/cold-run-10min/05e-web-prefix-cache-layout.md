# 05e - Web: vLLM APC prompt layout (delta, 2026-07-24)

**Scope:** Automatic prefix caching (APC) layout for **6 serial judge calls** that
share one long `candidate_md`. Fresh web forage + cross-check against prior
tapetum cards (`15-prefix-cache-enabler`, `92-vllm-apc-internals`).

**Verdict:** usable — external sources converge on one recipe: static first,
shared document next, call-specific query last; never put a per-call random
nonce in the system prefix. Prefer per-paper HMAC/sha256 tag (or vLLM
`cache_salt` stable per paper) over `secrets.token_hex` per call.

---

## Concrete recipe: 6 serial calls, one candidate markdown

Goal: calls 2–6 reuse KV for the shared document body after call 1 prefills it.

```
┌─────────────────────────────────────────────────────────────────────┐
│ SHARED PREFIX (byte/token-identical across all 6 calls)             │
│                                                                     │
│  [1] STATIC SYSTEM                                                  │
│      - role + CONVERSION_CONTRACT + shared safety floor             │
│      - NO timestamps, NO per-call nonce, NO per-call schema dump    │
│      - optional: fixed schema-version pin ("output format vN")      │
│                                                                     │
│  [2] PER-PAPER GUARD (stable for this paper's 6-call cascade)       │
│      - tag = SRC{hmac_sha256(secret, pid)[:8]}   # preferred        │
│        OR SRC{sha256(pid)[:8]}                   # no secret needed │
│      - NOT secrets.token_hex() per call                             │
│      - if using vLLM isolation: same cache_salt for all 6 calls     │
│        (extra_body.cache_salt = f"paper:{pid}")                     │
│                                                                     │
│  [3] SHARED DOCUMENT (the expensive part)                           │
│      - Paper: <pid>                                                 │
│      - CANDIDATE MARKDOWN wrapped once:                             │
│          <<<{tag}>>> ...escaped candidate_md... <<</{tag}>>>        │
│      - identical bytes on every call                                │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ diverge only below here
┌─────────────────────────────────────────────────────────────────────┐
│ VARIABLE SUFFIX (call-specific; MUST be last)                       │
│                                                                     │
│  [4] CALL TASK                                                      │
│      - unit id / risk signal / page # / metadata field set          │
│      - scoped SOURCE TEXT for this unit (if any)                    │
│      - call-specific output schema / JSON instructions              │
│        (put schema HERE, not in system, if schemas differ per call) │
└─────────────────────────────────────────────────────────────────────┘
```

### Per-call mapping (illustrative tapetum cascade)

| Call | Shares [1]+[2]+[3]? | Suffix [4] contains |
|------|---------------------|---------------------|
| 1 monolith | establishes cache | monolith rubric + any page hints |
| 2 metadata | yes **only if** same system as #1 | metadata schema + field checklist |
| 3–N unit | yes among units with same system | Unit / Risk / SOURCE TEXT only |
| page escalate | yes among escalations with same system | page raw + page rubric |

**Hard constraint from instructor #1403 / Anthropic order:** if structured
output is encoded as **tools at position 0**, different `response_model` per
call busts the entire prefix. For cross-schema APC: keep tools empty/constant
and put the schema text in the **user suffix** (JSON / MD_JSON style), or
unify one system stub and move task+schema to the tail.

**Expected reuse:** with identical system across unit checks, calls 2–5 hit
document KV (~80–85% prefill skip on doc body). Monolith vs metadata vs unit
still diverge at token 0 unless system prompts are unified (separate A/B).

**Server knobs (DeepSeek-V4 / alliance-pod):**
`enable_prefix_caching=True`, `VLLM_PREFIX_CACHE_RETENTION_INTERVAL=32768`,
keep `--max-num-seqs 16`. Measure `vllm:prefix_cache_hits / queries`.

---

## Finding cards

### A. vLLM APC — long document, serial queries

- **[CRITICAL] Official APC workload #1 is exactly our shape**
  https://docs.vllm.ai/en/stable/features/automatic_prefix_caching/
  "Long document query": process the document once; later requests with the
  same prefix skip recomputing it. Offline example uses one long markdown
  table prefix + two different questions.
  Impact: serial 6-call paper is the textbook APC win; decode time unchanged.

- **[CRITICAL] Hash chain is prefix-exact from token 0; only full blocks cache**
  https://docs.vllm.ai/en/stable/design/prefix_caching/
  Block hash = `(parent_hash, block_token_ids, extra_keys)`. Default block
  size 16 tokens. One early token change invalidates all downstream blocks
  even if `candidate_md` is identical.
  Impact: guard/nonce/timestamp before the document = no document reuse.

- **[HIGH] APC only helps prefill, not decode**
  Same vLLM feature doc. No gain when answers are long or prefixes never match.
  Impact: our mean decode ≫ prefill in baseline; still worth it because the
  document is huge and resent 6× — prefill skip still moves wall.

- **[HIGH] LRU + scan pollution under multi-paper concurrency**
  Design doc free-queue: freed blocks re-enter in reverse order; LRU head
  evicted under pressure. gingerlabs / UniCloud-style notes: hot shared-doc
  prefixes can be scanned out by unique prompts.
  Impact: optimize **in-paper serial** reuse first; cross-paper reuse is bonus.

- **[MED] Empty-prefix APC can add overhead (~37% in squeezebits)**
  Prior card `05-web.md` Q4. Enable APC only with layout that actually hits,
  or expect hash overhead with no benefit.

### B. HMAC / cache_salt vs random nonce

- **[CRITICAL] Per-call random nonce in system prompt is a cache buster**
  Manus Context Engineering: single-token change at prefix start kills KV reuse.
  https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus
  OpenAI Prompt Caching 201 / DigitalOcean: static-first, dynamic-last; never
  put timestamps / request IDs early.
  Impact: today's `SRC{secrets.token_hex(4)}` on every call (prior `15`) is the
  anti-pattern for document-level APC.

- **[CRITICAL] Prefer stable per-paper HMAC (or sha256) over random nonce**
  For injection delimiters you need unpredictability to outsiders, not
  uniqueness per call. `HMAC(server_secret, pid)[:8]` (or `sha256(pid)[:8]` if
  no secret) is **stable across the 6 calls** and still not forgeable from
  paper text alone when secret is held server-side.
  Contrast: random nonce maximizes isolation but forces 0% document sharing.
  Prior internal tradeoff: `15-prefix-cache-enabler` MED finding.

- **[HIGH] vLLM `cache_salt` is for tenant isolation, not per-call entropy**
  https://docs.vllm.ai/en/stable/design/prefix_caching/
  https://github.com/vllm-project/vllm/pull/17045
  Salt is injected into the **first block hash**; only same-salt requests share
  KV. Use one salt per paper (or per trust group) for all 6 calls. A random
  salt per call = same as random nonce: isolates you from yourself.
  Impact: `extra_body={"cache_salt": f"paper:{pid}"}` pairs with HMAC tag.

- **[HIGH] Quarantine all volatility after the document**
  Production guides (oh-bug, sankalp blog, Anthropic skills prompt-caching):
  time, user id, trace id, experiment arm → end of prompt or out of prompt.
  Impact: even "harmless" debug fields in system kill APC for everyone.

### C. Variable query last (layout law)

- **[CRITICAL] Canonical order: system → static context → shared doc → query**
  https://theneuralbase.com/vllm/learn/intermediate/optimal-prompt-structure-for-caching/
  https://developers.openai.com/cookbook/examples/prompt_caching_201
  Whitespace is part of the key; use fixed templates, not f-strings with
  variable spacing.
  Impact: current unit layout putting Unit/Risk/SOURCE **before** full
  `candidate_md` zeros cross-unit document reuse (prior `15` CRITICAL).

- **[HIGH] Measured pattern: N questions over one document**
  gingerlabs (prior `05-web` Q4): Qwen3-32B, 20 questions / one doc → TTFT
  4343→970 ms (−78%), output throughput +254% with APC when query is last.
  Impact: our 6-call cascade should copy that shape literally.

- **[HIGH] Deterministic serialization in the prefix**
  Manus + sankalp: `sort_keys=True` on any JSON in the shared prefix; stable
  tool/schema ordering. Unordered dict dumps → silent cache misses.
  Impact: if schemas live in prefix, pin field order; better: move varying
  schemas to suffix.

### D. langextract / instructor / outlines

- **[HIGH] Instructor #1403: multi-agent + one long doc — schema placement**
  https://github.com/567-labs/instructor/discussions/1403
  Tools/system sit at the front of the cache key. Different `response_model`
  as tools → prefix miss before the document. Fix patterns:
  1. Shared doc in system (or early user) with cache breakpoint; agent
     instructions + schema **after**.
  2. `Mode.MD_JSON` / JSON mode so schema is text in the suffix, tools empty.
  3. OpenAI automatic prefix: keep system+doc identical; let schema differ late.
  Impact: if our 6 calls use different structured schemas via tool-mode, unify
  tool block or move schema to user tail — otherwise document APC never fires
  across call types.

- **[HIGH] Instructor prompt_caching docs: move variables to message end**
  https://python.useinstructor.com/concepts/prompt_caching/
  OpenAI: "move all variable parts of the prompt to the end." Anthropic:
  put `cache_control` on the large shared block; query text after it.
  Impact: matches vLLM APC layout exactly for OpenAI-compatible pods.

- **[MED] Langextract: description + examples first, question last**
  https://github.com/google/langextract/blob/main/langextract/prompting.py
  `QAPromptGenerator.render`: `description` → optional context → few-shot
  examples → `Q: {question}` → `A:`. PR #447 `PromptParts(prefix, examples,
  suffix)` shares few-shot preamble across batch prompts (memory + cache-key
  stability via identical string hashes).
  Impact: same static-prefix / variable-suffix discipline; do **not** put
  per-chunk `additional_context` before examples if you want example KV reuse.

- **[MED] Outlines: constrained decode is orthogonal; layout still engine-owned**
  Outlines enforces output structure; prefix caching is the serving engine
  (vLLM/SGLang). Modular handbook: front-load static, query last, deterministic
  serialization. SGLang RadixAttention is finer-grained but same layout law.
  Impact: switching to outlines/guided decode does not fix a bad prefix order.

---

## Anti-patterns (do not ship)

| Anti-pattern | Why it fails APC |
|---|---|
| `tag = secrets.token_hex(4)` per call in system | Diverges before document |
| Unit / Risk / SOURCE before full `candidate_md` | Document never in shared prefix |
| Per-call schema as tools at request head | Tools order precedes system+doc |
| Timestamp / pid / trace in system | Busts org-wide system cache too |
| Random `cache_salt` per call | Self-isolation; no reuse |
| Unsorted JSON in shared prefix | Silent token divergence |

---

## False-pass / false-fail (layout lever)

**False-pass:** Reorder doc-before-unit so APC hits; model overweight global MD
and under-read scoped SOURCE → miss localized defect. Holdout A/B required.

**False-fail:** Enable APC + retention but keep per-call random tags and
unit-before-doc layout → operators see "APC on" with no wall win (or slight
hash overhead), conclude APC is useless.

## What would change my mind

10-paper canary: per-paper HMAC tag + doc-before-query + retention=32768;
if `prefix_cache_hits/queries` on calls 2–6 stays &lt;10%, layout is not the
bottleneck (eviction / hybrid SWA / system divergence dominate).
