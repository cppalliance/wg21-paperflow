# opus-A - Meta-review (consolidation of 144 persona reports + 6 verifier replays)

Role: Opus-tier meta-review. The six Composer verifiers (145-150) performed the
independent numeric replays; this pass consolidates, resolves contradictions,
and assigns final downgrade/upgrade status to every load-bearing claim.

## Contradiction resolutions

1. **Prefix caching status (P15/P40 vs P96/P93).** RESOLVED by live probe
   (146-verifier, raw scrape in `_scratch/research-tapetum-llm-speedup/`):
   `enable_prefix_caching=True` on alliance-pod, lifetime token hit rate
   **96.66%** over 131,568 requests; mean queue/prefill/decode/E2E =
   **2.38 / 0.46 / 5.91 / 9.01 s**, TPOT 27.8 ms (~36 tok/s). Consequences:
   - P40/P100's "APC off" claim is WRONG; the server-flag delta shrinks to
     MBT 8192->16384 + retention env + (optional) MTP.
   - P93's "prefill-bound, ~17s of 20s" model is wrong for the live pod;
     it stands only as the counterfactual for APC-miss traffic.
   - The pod is **decode + queue bound**: 5.91 s decode + 2.38 s queue
     dominate. Output-token discipline and call elimination outrank further
     prefill levers. P15's 600-1100 s claim is DOWNGRADED to the in-paper
     document-prefix share only (the random guard tag still zeroes reuse of
     the 10-40k-token user payload across a paper's ~6 serial calls; the
     measured 0.46 s prefill mean is cross-tenant and includes tiny probes).
   - Caveat carried into synthesis: lifetime pod metrics are cross-tenant;
     a fleet-window scrape (P96 playbook) is required before/after each lever.

2. **Monolith redundancy (P16 vs 147-verifier).** MODIFIED: verdict delta
   without monolith cnf-findings is **1/181** (not 4/181); monolith wall share
   is **226 s / 7.5%** (not 17%). Monolith stays (cheap insurance, only
   document-wide lens); the lever is dropped from the packages.

3. **Metadata short-circuit (P17/P34 vs 145-verifier).** CONFIRMED-MODIFIED:
   232/378 metadata-non-pass papers ran **1047 unit checks, 44.6% of 2345
   calls, ~1341 s**, with **zero** suggested-verdict or fusion drift when
   stripped (capping happens before units: `pdf_judge.py:711-712`,
   `fusion.py:187-189`). Real cost: **35 defect groups on 30 papers** vanish
   from inspect reports. Split adoption: metadata-**fail** tier = full skip
   (141 calls); metadata-**review** tier = policy decision (keep 1 top unit,
   or run-and-report without verdict effect).

4. **Stacking arithmetic (P48 vs 148-verifier).** MODIFIED: P48 was ~12%
   optimistic. Reconciled MODERATE wall **~596 s central, 530-670 s band**.
   AGGRESSIVE does NOT reliably reach <=300 s.

5. **Quality-gate noise floor (P47 vs 150-verifier).** The ">=25% flip rate"
   is from 20 borderline PIDs under identical c=32 reruns, not a fleet A/A.
   Gate protocol corrected: measure a true 381-paper A/A flip floor once,
   then gate levers against it; dev-replay recall + untouched holdout stay.

## Verified free wins (no verdict-semantics change)

- Error tombstones carry no fingerprint -> 6 papers re-cascade every warm run
  (~55 s of 64.8 s). Fix + `--retry-errors` flag -> warm ~10-15 s. (P46, 150 CONFIRMED)
- Monolith call lacks per-call `asyncio.wait_for`; a hang holds a fleet slot
  ~20 min (P26). Add timeout.
- Sync CPU in async path blocks the event loop (screen_pages up to ~17 s on
  large docs; ~98 s fleet total). `to_thread` + candidate-token caching
  (~30-40 s). (P28/P43)
- LJF paper ordering: ~60-180 s tail trim, output-order invariant
  (`asyncio.gather` returns in input order, P29 verified).
- Per-call timing instrumentation in sidecars + /metrics scrape playbook
  (P79/P96): prerequisite for all future claims.

## Verified conditional levers (need lane-version bump + A/B)

- Guard tag: per-paper `HMAC(fleet_secret, pid)` is security-equivalent
  (escaping in `pipeline/tools.py` is the load-bearing control; randomness is
  defense-in-depth). Conditions: secret-keyed (never bare hash(pid)), tags
  kept out of author-readable artifacts. (P45, 149-verifier SAFE-WITH-CONDITIONS)
  + user-message reorder ([static][shared candidate_md][unit fields LAST]),
  matching langextract's layout (P85) and vLLM block-hash chain (P92).
- Metadata short-circuit per resolution 3. Text lane included (458 of the
  1047 are text-lane; P42/147 CONFIRMED text lane = 50% of fleet wall).
- Escalation dedupe: 18/18 escalations duplicated a unit check (~23 s, hygiene).
- Verdict-first / conditional `reasoning` on pass-path unit checks: ~55 of
  ~77 output tokens on 70% of unit calls have no downstream consumer (P14/P31);
  decode-bound pod makes this material (~3-6 min claimed, overlaps with call
  elimination; reconciled inside the 148 stack).
- Dual-pod sharding: ~1.9x on remaining wall; per-pod `Semaphore(16)` (P143),
  deterministic index split by default, opt-in least-busy if the shared pod
  is contended (P140: fixed split loses ~950 s if one pod is 50% busy);
  fingerprint keys the shard SET not the per-paper pod (P21).
- MTP speculative decoding: MODERATE tier only; vLLM issue #42518 shows temp-0
  divergence (verify batch-shape); needs A/B. (P38/P103)

## Rejected levers (with grounds)

multi-unit prompt packing (RuVerBench double-digit drops; P12), sglang
migration (>=18 recent radix-cache correctness fixes, no verified single-node
V4-Pro win; P113), litellm as dependency (435 packages, fights ModelBackend
contract; P144 - copy patterns only), vLLM offline `run_batch` (cannot target
a running server; P41), HTTP tuning (P27 garbage), prompt compression (P33
garbage, <=13 s), cross-paper memoization (P36 garbage, 0/116 revision pairs
identical), chunk parallelism (P30: 0 papers chunk post-strip; the serial
rationale is stale but dormant), guided JSON as a speed lever (P74/P95:
~100 s ceiling, drift risk), deeper client queues (P71/P77: 32 in-flight is
right for 16 MoE slots behind the RunPod proxy).

## The user's premise, adjudicated

All five anti-steelman personas (docling P57, marker P69, olmocr P81, mineru
P121, unstructured P126, langextract P91) converge with file:line evidence:
the surveyed "fast" repos do **extraction with small dense models (0.25-7B)**
and perform **zero production LLM-judge verification**. Docling's 3.8 pages/s
is a 258M VLM; olmocr's 1600-deep queue feeds a 7B at 16k context; langextract
has no PDF support at all. Our 2284 x ~20 s MoE verification fleet is a
different workload class. The comparison still surfaced real waste (above),
but "the others showed 5-10 min is possible for this task" is false as stated.

## Long-term direction (validated by the ecosystem scan)

olmocr's fine-tuned dense 7B beating its GPT-4o teacher (P76) + SLMJury
(14B judge = 89.55% oracle agreement) + surya's task decomposition (P131)
all point at the CLAUDE.md fine-tune direction: distill unit-check judgments
(1510 labeled examples per cold run) into a small dense model on our own
pods. 6-12 week program; the near-term packages do not depend on it.
P131's sharper near-term variant: the metadata/outline check largely
duplicates deterministic logic (`source_router.py`, `html_outline.py`);
replacing 377 MoE calls (~471 s) with a deterministic diff is the cheapest
AGGRESSIVE-tier item, gated on an A/B that shows the LLM adds no findings
the diff misses.
