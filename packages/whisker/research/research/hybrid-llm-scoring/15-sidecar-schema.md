# 15 - Sidecar Schema (Persistence + Merge Layout)

**Verdict:** usable-with-conditions — Option A (nested extension blocks in `<pid>.whisker.json` with core preserve-on-rewrite) meets goals 2–3 and C1/C2, but only if whisker gains opaque key round-trip and tapetum becomes the sole writer of extension keys; concurrent det+LLM runs still need a documented ordering rule.
**Confidence:** high

## Findings

- [CRITICAL] **`whisker --all` full-overwrites each sidecar from `WhiskerResult.to_dict()` with no read-merge; any nested LLM block in the same file is deleted today.** Evidence: `__main__.py:246-248` (`json.dumps(result.to_dict(), ...)` with no prior read); `score.py:84-115` (`to_dict` emits a closed deterministic key set only). Impact: Option A is impossible without a core change to preserve extension keys (`tapetum`, `hybrid`) on rewrite; this is the primary blocker for goal 2 "same file."

- [HIGH] **Two independent writers already target the same directory with separate filenames; merge-in-one-file requires re-homing tapetum persistence.** Evidence: deterministic write at `__main__.py:240-248`; LLM write at `tapetum_llm/cli.py:207-217` (`<stem>.tapetum.json` beside `sidecar_path`); `_collect_sidecar_dicts` scans only `*.whisker.json` (`cli.py:197-200`). Impact: tapetum owns LLM persistence today; moving LLM data into `.whisker.json` is a tapetum CLI change plus whisker preserve logic, not a core import of tapetum (C2 satisfied).

- [HIGH] **Option B (two sidecars + `<pid>.whisker.merged.json`) maximizes crash isolation but fails the "ideally same file" goal and triples artifact count.** Evidence: 381 deterministic sidecars and 204 tapetum sidecars on disk (00-baseline runtime); separate persist paths (`__main__.py:246-248`, `cli.py:212-216`). Impact: 381×3 files, three-way staleness (det/tapetum/merged), and consumers must join; satisfies C1/C2 cleanly but works against user goal 2.

- [HIGH] **Option C (report-level join only) cannot persist per-paper merged JSON without new artifacts; core report is deterministic-only.** Evidence: `build_report` / `render_report_md` accept `list[WhiskerResult]` only (`report.py:87-95`, `98-123`); `report.json`/`report.md` rewritten from det results alone (`__main__.py:250-255`). Impact: goal 3 merged score visible in terminal/JSON per paper needs either sidecar fields or a third file; `tapetum-inspect.md` (`cli.py:231-243`) is human-only and not machine-joinable for CI.

- [MED] **Re-run semantics need a deterministic fingerprint, not timestamps alone; neither sidecar records `scored_at` or source hash today.** Evidence: `WhiskerResult.to_dict` has no run metadata (`score.py:89-115`); `TapetumResult.to_dict` records `whisker_verdict` snapshot but no hash of the whisker payload (`models.py:114-136`). Impact: after `whisker --all` then stale tapetum, or tapetum rerun after det change, merged consumers must detect mismatch via `tapetum.whisker_verdict` vs top-level `verdict` (123/194 disagree per 00-baseline) or an explicit `whisker_fingerprint` field.

- [MED] **`WHISKER_SCHEMA_VERSION` bump (currently 3, `constants.py:166`) should NOT be required for optional extension keys; tapetum sub-schema gets its own version.** Evidence: pinning test asserts `to_dict()["schema_version"] == WHISKER_SCHEMA_VERSION` (`test_score.py:149-154`); guard hard-fails stale baselines (`guard.py:266-271`, persona 27). Impact: top-level schema 3 stays the deterministic contract; `tapetum.schema_version` and `hybrid.schema_version` version LLM/merge shapes independently — backwards compat for 381 existing sidecars (no extension keys) without invalidating guard/score pins.

- [LOW] **Six tapetum errors leave no LLM sidecar; merge design must represent absent/errored LLM lane explicitly (C5).** Evidence: 00-baseline runtime (6 errors, no tapetum sidecar). Impact: `hybrid` block must distinguish `tapetum: null`, `tapetum.status: "error"`, and fresh adjudication — never emit a merged pass that implies LLM confirmation when the lane failed.

## False-pass hypothesis

P4182R0-class case from 00-baseline: deterministic `pass` (high `unigram_coverage`, clean gates) while tapetum would `fail` on tables/semantic corruption (`p4003r0` example: whisker review → tapetum fail, confidence 0.95). A merged rule of "deterministic pass wins" or averaging lanes would falsely accept token-preserving table/cell corruption the LLM lane exists to catch.

## False-fail hypothesis

RESCUE population (`select_candidates` heading-monotone-only fails, `CLAUDE.md:377-378`): deterministic `fail` from `gate:heading_monotone` (`score.py:152-154`) while tapetum folds cosmetic structure to `review` via severity-aware `worst_axis_verdict` (`chunking.py:34-51`). A merged rule of "worst verdict wins" without severity fold would falsely reject shippable cosmetic heading jumps.

## What would change my mind

An integration test proving concurrent `whisker --all` and `whisker-tapetum-llm --review-all` against the same PID never loses extension keys without file locking — if lost updates are reproducible, Option B (separate files + merged artifact) becomes the safer recommendation despite failing "same file."

---

## Option tradeoffs (mandate detail)

### (A) Nested `tapetum` (+ `hybrid`) in `<pid>.whisker.json`

| Dimension | Assessment |
|-----------|------------|
| **Who writes** | Whisker CLI owns top-level deterministic keys (`__main__.py:246-248`). Tapetum CLI owns `tapetum` and `hybrid` via read-modify-write on the same path (`sidecar_path`, `score.py:307-314`). Core preserves opaque keys on det rewrite (new ~5 lines in `__main__.py`, no tapetum import — C2). |
| **Crash consistency** | Single file per paper after each complete write; partial write still possible mid-`write_text`. Safer than two-file torn state if tapetum writes atomically (write temp + rename). |
| **det rerun after LLM** | Whisker overwrites det fields, **must preserve** `tapetum`/`hybrid`. Set `hybrid.stale: true` or leave stale until tapetum recomputes; consumers compare `tapetum.whisker_fingerprint` to hash of current det payload. |
| **LLM rerun after det** | Tapetum re-reads sidecar, snapshots `whisker_verdict` + fingerprint, writes fresh `tapetum` + `hybrid`. |
| **Staleness** | `tapetum.whisker_fingerprint` = stable hash of canonical det JSON (exclude extension keys). Optional `tapetum.scored_at` ISO8601 for humans. |
| **schema_version** | Top-level stays `3`. Add `tapetum.schema_version: 1`, `hybrid.schema_version: 1`. No bump to `WHISKER_SCHEMA_VERSION` for optional keys. |
| **381 existing sidecars** | Valid unchanged; extension keys appear on first tapetum run. Migrate 204 `.tapetum.json` files with one-shot import or dual-read deprecation period. |

### (B) Two sidecars + `<pid>.whisker.merged.json`

| Dimension | Assessment |
|-----------|------------|
| **Who writes** | Unchanged det/tapetum writers; new joiner (tapetum lane or thin CLI) writes merged third file. |
| **Crash consistency** | Worst case: det fresh, tapetum stale, merged missing — three states to reconcile. |
| **Re-run semantics** | Explicit: merged carries `sources.whisker_mtime` / `sources.tapetum_mtime` or content hashes; stale when either input newer than merged. |
| **schema_version** | New `MERGED_SCHEMA_VERSION`; det stays 3; tapetum still unversioned today (`models.py:114-136`). |
| **381 existing sidecars** | Fully compatible; no det format change. |

Fails user goal 2 ("ideally same file"); best when file-locking/concurrency cannot be ruled out.

### (C) Two sidecars + merge at report level only

| Dimension | Assessment |
|-----------|------------|
| **Who writes** | Det → `report.json`/`report.md` (`__main__.py:250-255`); tapetum → `.tapetum.json` + optional `tapetum-inspect.md` (`cli.py:207-243`). Joiner extends report render only. |
| **Crash consistency** | Reports and sidecars diverge by design; no per-paper merged persistence. |
| **Re-run semantics** | `whisker --all` regenerates report without tapetum columns unless a second pass (`whisker-tapetum-llm --inspect` or new `whisker report --hybrid`) reads both sidecars. |
| **schema_version** | Report schema bump if `build_report` gains hybrid rows; sidecars untouched. |
| **381 existing sidecars** | Compatible; lowest implementation risk. |

Does not persist merged per-paper JSON (goal 3 partial); inspect report is not structured JSON.

---

## Recommendation: Option A with preserve-on-rewrite

**One file:** `data/whisker/<pid>.whisker.json`

**Layout (concrete fields):**

```json
{
  "schema_version": 3,
  "pid": "P4003R0",
  "verdict": "review",
  "coverage": 0.9123,
  "unigram_coverage": 0.9456,
  "ref_overall": 0.3083,
  "gates": [],
  "hard_flags": [],
  "soft_flags": ["..."],
  "missing_regions": [],
  "extra_regions": [],

  "tapetum": {
    "schema_version": 1,
    "advisory": true,
    "scored_at": "2026-07-06T18:42:11Z",
    "whisker_verdict_snapshot": "review",
    "whisker_fingerprint": "sha256:8f3a…",
    "suggested_verdict": "fail",
    "confidence": 0.95,
    "escalated": true,
    "tier1_model": "…",
    "tier2_model": "…",
    "axis_findings": [],
    "grounded_evidence": [],
    "ungrounded_dropped": 0,
    "escalation_signals": [],
    "primary_concern": "…",
    "reasoning": "…"
  },

  "hybrid": {
    "schema_version": 1,
    "advisory": true,
    "computed_at": "2026-07-06T18:42:11Z",
    "stale": false,
    "whisker_fingerprint": "sha256:8f3a…",
    "tapetum_scored_at": "2026-07-06T18:42:11Z",
    "lanes": {
      "deterministic": "review",
      "tapetum": "fail"
    },
    "verdict": "fail",
    "confidence": 0.95,
    "rule": "severity_aware_worst_of_lanes",
    "rationale": "tapetum major tables fail escalates over det review"
  }
}
```

**Absent/error LLM lane (C5):**

```json
"tapetum": null,
"hybrid": {
  "schema_version": 1,
  "advisory": true,
  "stale": false,
  "lanes": { "deterministic": "review", "tapetum": null },
  "verdict": "review",
  "rule": "deterministic_only",
  "rationale": "tapetum lane absent or errored"
}
```

**Invariants preserved:**

- C1: top-level `verdict` remains deterministic record; `hybrid.verdict` is advisory (`advisory: true`, never consumed by `--gate`).
- C2: whisker core only preserves unknown keys; all tapetum/hybrid logic stays in `tapetum_llm`.
- C4: library still returns dataclasses; CLI persists (tapetum CLI writes extensions after `adjudicate_paper`, `cli.py:312-319`).
- C5: no merged pass when tapetum errored unless `rule` explicitly documents deterministic-only fallback.

**Implementation sketch (not in scope for this report):**

1. `__main__.py`: before `write_text`, load existing sidecar if present; copy keys in `("_extensions",)` or explicitly `("tapetum", "hybrid")` into new dict after `to_dict()`.
2. `tapetum_llm/cli.py`: replace `_persist_result` separate file with read-modify-write on `sidecar_path`; compute `whisker_fingerprint` from sorted det subset; write `tapetum` + `hybrid`; deprecate `.whisker.tapetum.json`.
3. Report/terminal: extend `render_report_md` or add tapetum report pass to read extension keys for `| det | tapetum | hybrid |` columns (Option C machinery, fed from same file).

**Operational rule:** run `whisker --all` before `whisker-tapetum-llm --review-all`, or accept `hybrid.stale: true` until tapetum reruns — document in `tapetum_llm.md`.
