# 23 - `_LANE_VERSION` bump economics

**Verdict:** usable-with-conditions — `_LANE_VERSION` is the **logic-only** fleet invalidation lever; prompt and schema edits already force full 381-paper cold runs via `prompt_sha256` / `schema_sha256` without a bump. During active lane work (Jul 2026), cold-run frequency is **~4/month** at git commit cadence or **~18/month** if every changelog line is treated as a separate ship; developer tax per bump is **~50 min wall today** (~**100 min** if A/A is run) or **~10 min** after MODERATE levers land.
**Confidence:** high on mechanism and git facts; medium on forward monthly rate (v7–v11 were uncommitted bundles, not one commit each).

**Sources:** `git log -p -S "_LANE_VERSION"` and `git blame` on `packages/whisker/src/whisker/tapetum_llm/cli.py` (read-only, 2026-07-24); `tapetum_llm.md:322-334`; `150-verifier-warmrun-quality.md`; `19-incremental-granularity.md`; `00-baseline.md`.

---

## Executive summary

| Question | Answer |
|----------|--------|
| **Cold runs per month from `_LANE_VERSION` alone** | **~4/month** (operational, 2 git bumps in 15 days) to **~18/month** (comment-log cadence, 9 increments in 15 days). Steady-state planning number: **~4/month** (`SYNTHESIS.md:54-56`, `150-verifier`). |
| **Wall cost per bump (381 papers, bare full run)** | **~3003 s (~50 min)** cold today (`00-baseline.md:18`); **~596 s (~10 min)** MODERATE target unchanged by bump frequency. |
| **Quality-gate tax per bump regime** | **+~50 min** for A2 if no cached A/A baseline (`25-quality-gate-protocol.md:54-62`). Bundled lever ship: **~100 min** measurement before B run. |
| **Which levers need a bump?** | **Logic/post-process/routing/fusion/coverage-mode key/short-circuit** changes that do **not** alter hashed prompt text or Pydantic schema JSON. |
| **Which levers do *not* need a bump?** | **Prompt text**, **schema JSON**, **model/service contract**, **md/source bytes**, **ideal file** changes (auto-invalidate). **Pure scheduling** (LJF, `to_thread`, timeouts) if verdict-identical and fingerprint unchanged. |

---

## Mechanism (why a bump forces cold)

`_LANE_VERSION` is copied into every sidecar fingerprint as `lane_version` (`cli.py:101-103`, `630`). Bare full runs enable incremental skip by default; `_fingerprint_matches` requires all keys equal (`cli.py:679-702`). Any bump makes **381/381** sidecars miss on the next fleet run unless `--force` was already used.

Comment at `cli.py:101-102`:

> Bump when lane logic changes **without a prompt change**. The fingerprint includes this, so an incremental run re-evaluates all papers after a bump.

Prompt and schema changes **already** invalidate via `prompt_sha256` and `schema_sha256` (`cli.py:595-632`) — a bump is redundant for those but still mandatory when logic changes without touching hashed prompt/schema text (`08-fingerprint-incremental-auditor.md:26` fusion tightening example).

---

## Git history of `_LANE_VERSION` in `cli.py`

### Commits that change `_LANE_VERSION = N`

| Commit | Date | Value | Notes |
|--------|------|-------|-------|
| `58a978c` | 2026-07-09 | **2** | First introduction of fingerprint + `_LANE_VERSION` (large tapetum_llm CLI landing). |
| `c59139c` | 2026-07-17 | **6** | Fail-closed source-aware golden QA; **v3–v6 bundled** in one commit (per changelog comments). |
| `51cb704` | 2026-07-17 | **6** | Health probe only; lane version unchanged. |
| Working tree (uncommitted) | 2026-07-24 | **11** | **v7–v11** comment history + value in one local edit block (`git blame`: "Not Committed Yet" for lines 110–123). |

`git log -G "_LANE_VERSION = [0-9]"` finds **only two** commits (`58a978c`, `c59139c`) — not one commit per changelog line.

### Changelog lines vs git reality (v2–v11)

| Version | Documented change | Documented date | In git as separate bump? |
|---------|-------------------|-----------------|--------------------------|
| v2 | `models.py` Field caps + `_SLOT_MAX_TOKENS` | 2026-07-08 | Yes (`58a978c`) |
| v3 | Per-page recall screen + page escalations | 2026-07-15 | Bundled → v6 |
| v4 | Source-grounded missing-content provenance | — | Bundled → v6 |
| v6 | Mandatory metadata/outline + fail-closed unit coverage | — | Yes (`c59139c`) |
| v7 | Ideal verifier + ideal fingerprint fields | — | Uncommitted bundle |
| v8 | Fusion ideal validation | — | Uncommitted bundle |
| v9 | `coverage_mode` fingerprint key | — | Uncommitted bundle |
| v10 | Pre-filter unroutable units before quota | — | Uncommitted bundle |
| v11 | Metadata-fail short-circuit; HMAC guard tag; user reorder; error tombstone fingerprints | — | Uncommitted bundle |

(v5 absent in log; v4→v6 jump is intentional in comments.)

**Operational cold runs in Jul 8–23 window:** **2 committed invalidations** (v2 ship, v6 ship) plus **≥1 local session** for v7–v10/11 work that produced measured v10 cold **3003.4 s** (`tapetum-llm-speedup/00-baseline.md:17`).

---

## Cold runs per month (estimates)

Assume each `_LANE_VERSION` bump triggers **one** full 381-paper bare run (incremental on, all miss). `--force` and quality-gate A/A runs are **additional** wall, not counted in the table below.

### Three cadence models

| Model | Bumps / 15 days (Jul 8–23) | Bumps / month (×2) | Cold wall / month (50 min) | Cold wall / month (10 min target) |
|-------|----------------------------|--------------------|----------------------------|-----------------------------------|
| **A — Comment-log** (every version line = ship) | 9 (v2→v10) | **~18** | **~15 h** | **~3 h** |
| **B — Git commit** (only `_LANE_VERSION =` changes) | 2 | **~4** | **~3.3 h** | **~40 min** |
| **C — Steady-state plan** (`SYNTHESIS`, `150-verifier`) | ~2 | **~4** | **~3.3 h** | **~40 min** |

**Recommended planning number:** **~4 full cold runs per month** while the lane is actively evolving; **~0–1/month** once bumps stop (warm path **64.8 s**, `00-baseline.md:20`).

**Inflation caveat:** Model A matches `49-steelman-defender.md` (~1.7 days/bump) but **overstates** ops frequency because v3–v6 and v7–v11 were **batched**, not shipped as separate fleet runs (`150-verifier-warmrun-quality.md:12`).

### Non-`_LANE_VERSION` cold triggers (same 381-paper cost)

These force the same cascade **without** bumping `_LANE_VERSION`:

| Trigger | Fingerprint key | Typical dev cadence |
|---------|-----------------|-------------------|
| Unit/metadata/monolith **prompt** edit | `prompt_sha256` (monolithic contract hashes all lane prompts) | **Full fleet** on any prompt touch; **~50 min** today |
| **Schema** / `Field(description=…)` change | `schema_sha256` | Same as prompt |
| **`CONVERSION_CONTRACT`** expansion | `prompt_sha256` via embedded contract | Jul 22 expansion invalidated fleet **even without bump** (`08-fingerprint-incremental-auditor.md:14`) |
| **Pod / model** switch | `model` (service contract JSON) | Ad hoc |
| **Ideal** add/change | `ideal_*` fields | Per golden QA wave |
| **`--force`**, A/A, A/B gate | N/A (operator) | **+1–3×** ~50 min per lever bundle (`25-quality-gate-protocol.md`) |

---

## Developer cadence cost of prompt/schema levers

### Per-edit fleet cost (today, whole-paper fingerprint)

| Lever type | Bump required? | Papers re-LLM | Approx wall (16 slots, ~20 s/call) | Notes |
|------------|----------------|---------------|-------------------------------------|-------|
| **Unit prompt only** | No (`prompt_sha256`) | **381** | **~3003 s (~50 min)** | `_pdf_prompt_contract()` concatenates monolith + page + metadata + unit prompts (`cli.py:505-512`, `19-incremental-granularity.md:8`) |
| **Metadata prompt only** | No | **381** | **~50 min** | Same monolithic hash |
| **Monolith prompt only** | No | **381** | **~50 min** | Same |
| **Schema-only** (Pydantic JSON) | No (`schema_sha256`) | **381** | **~50 min** | Auto-invalidates |
| **Logic-only** (fusion fold, routing quota, screen caps) | **Yes** | **381** | **~50 min** | No prompt/schema delta → stale pass without bump |
| **Scheduling-only** (LJF, thread offload) | No | **0** (warm skip) | **~65 s** warm | Verdict-identical; no fingerprint change |

### Quality-gate overhead (prompt/schema/routing levers)

For levers that change call graph or LLM inputs (`25-quality-gate-protocol.md:38-44`):

| Activity | Extra wall (today) |
|----------|-------------------|
| A/A noise floor (once per `_LANE_VERSION` regime) | **~100 min** (2× ~50 min) or **~50 min** with weekly cached A2 |
| Bundled B (short-circuit + HMAC + dual-pod) | **~50 min** + post-hoc gates |
| **Total ship tax** for one logic+bump release | **~150–200 min** wall + analysis |

MoE **verdict flip** on borderline papers (~25% on 20-PID subset, not 381) means prompt levers need equivalence-vector diff, not byte-identical sidecars (`150-verifier-warmrun-quality.md:14-21`).

### Future: call-class fingerprints (not shipped)

Splitting `prompt_sha256` per call class would cut prompt-only cold cost (`19-incremental-granularity.md:10`):

| Prompt edit scope | Wall today | Wall with class hashes |
|-------------------|------------|------------------------|
| Unit only | ~50 min | **~31 min** (~1510 calls) |
| Metadata only | ~50 min | **~8 min** (~377 calls) |
| Monolith only | ~50 min | **~8 min** (~381 calls) |

**`_LANE_VERSION` bump with unchanged prompts** (e.g. v10 routing): still **~50 min** today; class-scoped `lane_version_unit` would reduce to **~31 min** for unit-only logic (`19-incremental-granularity.md:18`).

---

## Which levers need `_LANE_VERSION` bump (checklist)

### **Must bump** (logic / merge / routing without prompt or schema hash change)

| Change class | Example (version log) | Why bump |
|--------------|----------------------|----------|
| Post-processing / verdict fold | v4 candidate provenance | Python logic, same prompts |
| Page screen / escalation caps | v3 | Call graph, not prompt text |
| Unit routing / quota / pre-filter | v10 unroutable pre-filter | Selection logic |
| Metadata-fail short-circuit | v11 | Skips calls without prompt change |
| Fusion read path | v8 ideal validation in fusion | Sidecar merge semantics |
| New fingerprint **key** (mode discrimination) | v9 `coverage_mode` | Old sidecars lack key → match fail anyway, but bump documents ship |
| Field caps affecting runtime without schema JSON delta | v2 | Edge case: behavior change not captured in schema hash |

### **Do not bump** (other fingerprint keys suffice)

| Change class | Invalidates via |
|--------------|----------------|
| Any system prompt text | `prompt_sha256` |
| Pydantic schema / Field descriptions in JSON schema | `schema_sha256` |
| Service / model / base_url | `model` contract |
| tomd reconversion | `md_sha256` |
| Source re-download | `source_sha256` |
| Ideal markdown add/change | `ideal_sha256`, `ideal_*` |
| HMAC tag / user message **reorder** | **Ambiguous:** v11 documents as bump; reorder may not change system `prompt_sha256` — bump is the safe ship habit |

### **Do not bump** (no fingerprint change; warm-only)

| Lever | Condition |
|-------|-----------|
| LJF fleet ordering, `to_thread`, monolith `wait_for` | Verdict-identical; no hash input change |
| Dual-pod shard (future) | Only if shard set is **not** in fingerprint and scheduling is provably verdict-neutral |
| Server APC / KV flags | Infrastructure; Tier A spot-check only (`25-quality-gate-protocol.md:19`) |

**Rule of thumb:** if the change can alter advisory verdict without changing any hashed prompt, schema, source, markdown, model, ideal, or coverage field, **bump `_LANE_VERSION`** (or split class-scoped lane versions when that lands).

---

## False-pass hypothesis

Shipping fusion or routing logic **without** bump and **without** prompt/schema change leaves fingerprints matching; incremental skip serves **stale** unit coverage or merged verdicts (`08-fingerprint-incremental-auditor.md:26` `_source_aware_requires_review` example).

## False-fail hypothesis

Bumping `_LANE_VERSION` on every prompt edit **and** relying on `prompt_sha256` is redundant but not wrong (double invalidation). **False operational fail:** treating each changelog line as a separate monthly cold run when work was batched → over-budgeting developer time by **~4×** vs git cadence.

## What would change my mind

- **Separate git commits** for v7, v8, v9 with dates spanning Jul 18–22 → raise Model A toward **~12–15 cold runs/month** during that sprint.
- **30-day calendar** with zero `_LANE_VERSION` bumps and warm ≤90 s → lower steady-state to **~0–1 cold/month** (`31-steelman-target.md:107-109`).
- **Call-class fingerprints shipped** → replan prompt-edit economics using per-class wall table above; `_LANE_VERSION` bumps for routing-only fixes drop toward **~31 min** instead of **~50 min**.
