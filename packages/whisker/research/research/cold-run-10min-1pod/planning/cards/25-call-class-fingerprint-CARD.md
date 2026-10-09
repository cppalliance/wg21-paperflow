# CARD: Call-class fingerprint (single-pod ops)

## Bottom line (3 sentences max)
Per-call-class fingerprints kill the “one prompt edit → full 381-paper rerun” tax by skipping unchanged call classes and replaying cached outputs. **Cold first-run impact is 0** on empty `whisker/llm/`. Not on the ≤600 s critical path; ship after v11 cold levers, before the next prompt/`_LANE_VERSION` churn cycle.

## Numbers that matter
- True cold / `--force`: **2284** calls, **3003 s** — **0 s** saved
- Warm unchanged: **375/381** skip in **64.8 s** (whole-paper gate today)
- Unit-prompt-only edit today: ~**3003 s**; with class split: ~**1888 s** (−37%)
- Monolith- or metadata-only edit with class split: ~**471–476 s** (−84%)
- Routing-only bump (prompts unchanged): re-run ~**758** mono+meta → ~**2055 s** (−32%)

## Architecture implication
Split monolithic `prompt_sha256` into class hashes (`monolith`, `metadata`, `unit`, `page_escalation`, `ideal_verify`) plus optional per-unit keys. Normalize HMAC guard tags out of cache keys; bump per-class version when merge/fold logic changes. Always re-LLM monolith+metadata on `md_sha256` change; provide `--no-llm-cache` for A/B.

## Cite / do not re-open
- Claiming call-class fingerprint closes the single-pod cold gap
- Expecting greenfield cold savings from cache plumbing alone
- Invalidating whole-paper skip on observability fields (`call_timings`)
- Skipping monolith on front-matter-only md changes

## Links to related reports
- `research/cold-run-10min-1pod/25-call-class-fingerprint.md` (this source)
- `00-baseline.md`, `10-impl-status-1pod.md`
- Prior: `cold-run-10min/30-per-unit-fingerprint.md`, `tapetum-llm-speedup/{19-incremental-granularity,135-promptfoo-concurrency-caching}.md`
