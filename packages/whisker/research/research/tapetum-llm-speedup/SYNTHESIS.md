# SYNTHESIS - tapetum-llm cold-run speedup (50 min -> 5-10 min target)

- Date: 2026-07-23. HEAD: 51cb704. Swarm: 1 cloner + 5 web foragers + 138
  personas + 6 verifiers (150 Composer 2.5 subagents), Opus meta-review.
- Corpus: 381 papers, 2284 LLM calls, 2903 s (48.4 min) cold, 64.8 s warm.
  Pod: DeepSeek-V4-Pro (MoE) on 1xH200, vLLM, 16 server slots, client c=32.
- Verdict on the target: **~9-11 min cold is reachable with verified levers
  (MODERATE package). <=5 min requires the AGGRESSIVE tier and carries real
  quality-validation cost. Warm runs drop from 65 s to ~10-15 s with one bug fix.**

## 1. Answer to the question "warum sind die anderen schneller?"

They are not running our workload. Verified with file:line evidence across
docling, marker, olmocr, MinerU, unstructured, langextract: all of them do
**extraction** with **small dense models (258M-7B)** and have **no
production LLM-judge verification step at all**. Docling's 3.8 pages/s comes
from a 258M-parameter VLM; olmocr feeds a fine-tuned 7B with single pages at
16k context; langextract cannot even read PDFs. We run 2284 verification
calls against a MoE judge with 10-40k-token evidence payloads and fail-closed
grounding. That is a different workload class, and "gleiche Qualität" rules
out their main trick (drop verification, shrink the model, accept partial
results).

**But** the swarm found genuine waste on our side. The levers below are
verified against our own runtime data, not vibes.

## 2. What we do badly (verified, ranked by impact)

| # | Finding | Evidence | Verified saving |
|---|---------|----------|-----------------|
| 1 | **44.6% of all LLM calls are fusion-dead.** 232/378 papers fail/review the metadata check, which caps the verdict BEFORE unit checks run; the 1047 subsequent unit calls (PDF+text lanes) cannot change any verdict. | 145-verifier replay: 0 verdict drift, 0 fusion drift when stripped. Cost: 35 defect groups on 30 papers vanish from inspect reports. | ~1341 s |
| 2 | **Random per-call guard tag kills KV reuse of the document payload.** Each paper sends its 10-40k-token candidate ~6x serially; the fresh `secrets.token_hex` tag + unit-fields-first ordering forces full re-prefill each time. APC on the pod is ON and healthy (96.66% lifetime hit rate, live probe), so this is purely our prompt layout. | 149-verifier: per-paper `HMAC(secret, pid)` is security-equivalent (escaping is the load-bearing control). langextract/vLLM layout confirms [static][document][query-last]. | few hundred s (in-paper prefix reuse) |
| 3 | **Decode waste on the pass path.** The pod is decode-bound (5.91 s decode vs 0.46 s prefill mean). 70% of unit checks return zero defects yet emit ~55 tokens of `reasoning` nobody consumes. | P14/P31, pod metrics via 146-verifier. | ~180-360 s (overlaps #1) |
| 4 | **One pod, 16 slots, fixed.** Client batching works as designed (c=32 overfills 16 slots); the ceiling is the single H200. Dual-pod sharding with per-pod Semaphore(16) and deterministic index split is contract-compatible. | P21/P140/P143. | ~1.9x on remaining wall |
| 5 | **Error tombstones have no fingerprint** -> 6 error papers re-run the full cascade on every warm run (~55 s of the 64.8 s warm run). | P46, 150-verifier CONFIRMED. | warm 65 s -> ~10-15 s |
| 6 | **Client-side stalls**: sync CPU in the async path (screen_pages ~17 s on big docs, event loop blocked), no per-call timeout on the monolith (a hang holds a fleet slot ~20 min), random paper order lets a 300 s paper start last. | P26/P28/P29/P43. | ~90-220 s + tail-risk removal |
| 7 | **The metadata/outline LLM call may be deterministic-replaceable.** It largely re-derives what `source_router`/`html_outline` already compute; 377 calls, ~471 s. | P131; AGGRESSIVE tier, needs A/B proving the LLM adds nothing. | ~471 s |

Non-findings worth naming: prefix caching is NOT off (earlier persona claims
downgraded after a live `/metrics` probe), the monolith is only 7.5% of wall
(kept), HTTP tuning / prompt compression / cross-paper memoization are noise,
multi-unit packing and an sglang migration are rejected on quality/maturity
grounds. Full ledger in `opus-A-meta-review.md`.

## 3. Packages (148-verifier reconciled arithmetic)

| Package | Levers | Cold wall | Semantics |
|---------|--------|-----------|-----------|
| BASELINE | - | 2903 s (48.4 min) | - |
| **CONSERVATIVE** | tombstone fingerprints, guard-tag HMAC + prompt reorder, LJF ordering, to_thread + token caching, monolith timeout, server flags (MBT 16384, APC retention env), dual-pod shard | **~685-856 s (11-14 min)** | verdicts unchanged; lane-version bump for the prompt reorder |
| **MODERATE** | + metadata-fail short-circuit, escalation dedupe, verdict-first pass-path schema, MTP spec-decode (A/B-gated) | **~596 s central, 530-670 s (9-11 min)** | inspect reports lose sub-findings on already-failed papers; verdicts unchanged (verified) |
| AGGRESSIVE | + deterministic metadata diff (P131), router tightening, dense-judge offload | ~300-500 s; **<=300 s NOT reliably reachable** | requires full A/B revalidation per lever |

Steady state after the program: warm (nothing changed) ~10-15 s; N changed
papers ~ N x 6 calls amortized at c=32; true cold runs only on lane-version
bumps (~every 7.5 days at current dev cadence, 150-verifier).

## 4. Quality gate (non-negotiable, corrected by 150-verifier)

1. Measure a true 381-paper A/A rerun flip floor ONCE (the quoted 25% flip
   rate came from 20 borderline PIDs, not the fleet).
2. Every lever that touches prompts/schemas/routing: fleet A/B against that
   floor + dev-replay recall (35 labels) + untouched holdout.
3. Levers that only change scheduling/caching/sharding: verdict-identity
   check suffices (byte-diff of sidecar verdicts).
4. Per-call timing instrumentation + /metrics scrape (P96 playbook) before
   and after each lever; no more lifetime cross-tenant numbers as evidence.

## 5. Recommended order of execution

1. **Free wins, no semantics change** (1 day): tombstone fingerprints +
   `--retry-errors`, monolith `wait_for`, `to_thread` + candidate-token cache,
   LJF ordering, per-call timing in sidecars.
2. **Cache enablement** (lane-version bump): per-paper HMAC guard tag +
   user-message reorder; operator applies server flags. Verify with
   fleet-window /metrics scrape.
3. **Call elimination** (lane-version bump + A/B): metadata-fail
   short-circuit (fail tier full skip; review tier keeps 1 top unit or runs
   report-only), escalation dedupe.
4. **Dual-pod sharding** (per-pod Semaphore(16), deterministic split,
   shard-set in fingerprint).
5. Optional AGGRESSIVE items one at a time, each behind its own A/B:
   deterministic metadata diff, verdict-first schema, MTP.

## 6. Long-term (validated direction, separate program)

olmocr's fine-tuned dense 7B beats its GPT-4o teacher; SLMJury's 14B judge
hits 89.55% oracle agreement. Each cold run already produces ~1510 labeled
unit-check judgments: distilling the unit check into a small dense model on
our own pods is the CLAUDE.md fine-tune path and the only credible route to
"docling-class" speed at our quality bar. 6-12 weeks; nothing above depends
on it.

## Report ledger

Persona reports `10-*.md` .. `144-*.md`, verifiers `145-*.md` .. `150-*.md`,
web findings `05-web.md`, baseline `00-baseline.md`, meta-review
`opus-A-meta-review.md`, all in this directory. Raw probe data in
`_scratch/research-tapetum-llm-speedup/`.
