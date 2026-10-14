# 08 - Fingerprint-Incremental-Auditor

**Verdict:** usable-with-conditions — incremental skip is wired correctly for the bare full run and tonight's sidecars will skip 377/381; the 4 error tombstones correctly force retry; `_LANE_VERSION` and prompt/schema hashes cover most invalidation paths, but logic-only changes without a version bump can still serve stale verdicts, and coverage modes share one sidecar path so a routed fleet run can overwrite an `--all-pages` artifact (not silent stale reuse).
**Confidence:** high

## Findings

- [CRITICAL] Next bare full run cost is **~45–120 s wall**, not ~2886 s. Measured fingerprint check for all 381 papers: **377 matches, 4 mismatches, 0.87 s serial (2.3 ms/paper)**; merged-report rebuild: **6.05 s**. The 4 mismatches are exactly the 4 ERROR tombstones (no fingerprint). With client c=32 the 4 LLM retries run in parallel; at tonight's **7.6 s/paper** fleet mean (`00-baseline.md:41–42`) expect **~30–60 s** for those four plus ~7 s overhead. Impact: the 48 min run was a one-time cold invalidation, not the new steady-state price.

- [CRITICAL] Bare full run auto-enables incremental; `--force` disables it. `full_run = True` when no PIDs and no `--review-all` (`cli.py:960–965`); `incremental = not args.force` only in full-run mode (`cli.py:1070–1073`); argparse documents the contract (`cli.py:347–361`). Impact: operator needs no flag for skip-on-next-run; `--force` is the explicit cold-rerun escape hatch.

- [HIGH] Tonight's cold rerun claim is confirmed in sidecars, with a git nuance. Working tree `_LANE_VERSION = 9` (`cli.py:112–114`, uncommitted); committed HEAD still has `_LANE_VERSION = 6` (`git show HEAD:packages/whisker/.../cli.py`). All **377 success sidecars** store `"lane_version": 9` and `"coverage_mode": "default"` (runtime inventory of `data/whisker/llm/*.tapetum.json`). Baseline's "8→9" (`00-baseline.md:43–45`) is comment-history shorthand; the literal invalidation jump in this workspace was **6→9** plus new fingerprint keys (`coverage_mode`, ideal fields). Impact: next run skips all unchanged papers; any peer on committed v6 without tonight's sidecars would still cold-run.

- [HIGH] Fingerprint inputs are comprehensive for content/service/prompt invalidation. `_compute_fingerprint` hashes converted markdown (`md_sha256`), staged source (`source_sha256`), concatenated system prompts (`prompt_sha256`), JSON service/model contract (`model` field — actually full `_effective_model_contract` output, `cli.py:523–560`, stored at `cli.py:597`), output schemas (`schema_sha256`), ideal presence/content and verifier identities when applicable (`cli.py:601–614`), lane label, `_LANE_VERSION`, and `coverage_mode` (`cli.py:563–616`). PDF prompt contract includes `UNIT_CHECK_SYSTEM_PROMPT` which embeds `CONVERSION_CONTRACT` (`cli.py:473–480`, `unit_judge.py:129–140`). Impact: the 07-22 `CONVERSION_CONTRACT` expansion **would have invalidated caches via `prompt_sha256` even without a version bump**; service/pod switches invalidate via the `model` JSON (service name, `base_url`, `model` id in `_SAFE_SERVICE_FIELDS`, `cli.py:87–97`).

- [HIGH] `coverage_mode` correctly prevents cross-mode cache reuse but does **not** isolate files. Modes: `default` / `exhaustive` / `all_pages` via `_coverage_mode_for_paper` (`cli.py:184–192`); stored in fingerprint (`cli.py:615`); documented in `tapetum_llm.md:134`. All modes write the **same path** `whisker/llm/<pid>.whisker.tapetum.json` (`cli.py:426–433`, `668`, `693`). A routed fleet run after an `--all-pages` run sees `coverage_mode` mismatch → re-evaluates (good), then **overwrites** the all-pages sidecar (destructive, not a silent stale-verdict bug). Impact: operators must not assume an all-pages sidecar survives a subsequent bare fleet run.

- [MED] ERROR tombstones force retry, not skip. `_write_error_tombstone` writes `status="error"` with **no** `fingerprint` block (`cli.py:725–754`). `_read_existing_fingerprint` returns `None` when absent (`cli.py:619–629`); `_fingerprint_matches` returns `False` (`cli.py:632–639`). Tonight's four: `P3400R3`/`P3977R0` (`PdfLaneError`), `P4182R0`/`P4228R0` (`IdealVerificationError`) — all `fingerprint: null` (runtime sidecar read). Fusion treats `status="error"` as unusable (`fusion.py:154–159`). Impact: next run re-adjudicates exactly the 4 failures; footer will read `4 evaluated, 377 skipped (incremental)`.

- [MED] Match logic is one-directional on new keys: `_fingerprint_matches` requires `old.get(k) == v` for every key in **new** fingerprint (`cli.py:639`). Old sidecars missing a newly added field (e.g. pre-v9 without `coverage_mode`) never match until re-evaluated. Impact: safe for rollout (forces refresh); operators must expect one cold run after fingerprint schema extensions.

- [LOW] Fingerprint-check exceptions fail open to full LLM eval. The skip path wraps `_compute_fingerprint` in `try/except` and sets `fp = None` on error (`cli.py:1153–1172`), forcing adjudication. Impact: a broken file read costs one LLM call, not a stale skip.

## False-pass hypothesis

A post-processing or routing logic change in `pdf_judge.py`, `unit_judge.py`, or `adjudicate.py` that does **not** alter any hashed prompt text, Pydantic schema JSON, `_LANE_VERSION`, source/markdown bytes, service config, ideal file, or `coverage_mode` would leave fingerprints matching and serve a stale advisory verdict. Example: tightening `_source_aware_requires_review` in `fusion.py` without bumping `_LANE_VERSION` — fusion reads existing sidecars and would not re-run the judge, so merged reports could reflect old unit-coverage semantics.

## False-fail hypothesis

Run `whisker-tapetum-llm --all-pages P1234R0` (thorough, `coverage_mode=all_pages`), then a bare fleet run on the same corpus: fingerprint mismatch forces a **routed** re-eval and overwrites the all-pages sidecar at the same path. Fusion/report consumers lose the exhaustive artifact; this is overwrite/data-loss, not a wrong skip, but an operator running both modes on the same PID without archiving would perceive it as "my thorough verdict disappeared."

## What would change my mind

A timed bare `whisker-tapetum-llm` run tomorrow that skips fewer than 377 papers (with unchanged markdown, source, prompts, services, and code) would prove a fingerprint bug — either a field not hashed that changed, or a match-path defect.
