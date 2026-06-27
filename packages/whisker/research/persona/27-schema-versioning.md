# 27 - Schema / Versioning Reviewer

**Verdict:** usable-with-conditions — guard baselines are fail-closed on schema/kind/tool_versions, but score artifacts (`report.json`, sidecars) are write-only with no read validation, so stale schema-1 files mislead humans and external tooling, not whisker's live gate.
**Confidence:** high

## Findings

- [CRITICAL] **Nothing in whisker READS `data/whisker/report.json` for scoring or gating.** Evidence: `00-EVIDENCE-BASELINE.md` §3b (`schema_version = 1` vs code `3`); only write path is `(out_dir / "report.json").write_text(...)` (`__main__.py:242-244`); no `read_text`/`json.loads` on score reports anywhere under `packages/whisker/src`. Impact: the stale artifact **cannot silently pass whisker's own QA** — but operators comparing §3b counts (126/236/20) to §3a (163/205/14) may trust a pre-v2 oracle run whose field semantics differ from today's `_decide` (`score.py:118-184`).

- [HIGH] **Guard baselines hard-fail on stale schema before any per-paper diff.** Evidence: `_validate_baseline` requires `schema_version == WHISKER_SCHEMA_VERSION` (`guard.py:266-271`, `constants.py:166`); `test_schema_mismatch_baseline_raises` (`test_guard.py:177-181`). Impact: a schema-1 guard baseline cannot pass guard after the v2/v3 bumps — migration is explicit `--update`, not silent drift.

- [HIGH] **`tool_versions` mismatch hard-fails when present; embedded at write time.** Evidence: `baseline_from_rows` stamps `tool_versions: collect_tool_versions()` (`guard.py:236-238`); mismatch raises `ValueError` (`guard.py:276-288`); `test_tool_version_mismatch_hard_fails` (`test_guard.py:247-251`). Impact: a tomd/whisker bump cannot silently green-light against wrong-era metric rows — the PyMuPDF version-keyed lesson is implemented for guard.

- [HIGH] **`whisker bench --baseline` has no schema/kind contract — unlike guard.** Evidence: guard validates via `_validate_baseline` (`guard.py:251-305`); bench only does `base["aggregate"]["overall"]` after bare `json.loads` (`__main__.py:328-340`), no `schema_version` check. Impact: a stale **bench leaderboard** (not score `report.json`, which lacks `aggregate`) could silently drive a meaningless corpus-mean regression compare; pointing bench at score `report.json` fails closed with `KeyError` on `aggregate`, not a silent pass.

- [MED] **No automatic migration 1→2→3; CHANGELOG documents regenerate-only.** Evidence: `CHANGELOG.md:107-114` (upgrade → `whisker guard --update`, stale schema-2 hard-fails by design); `constants.py:157-165` (bumps document `tool_versions`, null-eligibility, `content_recall`); zero migration helpers in src. Impact: migration is **safe fail-closed** (stale baselines error) but **not zero-touch** — every bump needs human `--update` and diff review.

- [MED] **`tool_versions` gate is skipped if the field is absent on an otherwise schema-3 baseline.** Evidence: check guarded by `if base_versions is not None` (`guard.py:277-288`); no test for missing `tool_versions`. Impact: a hand-edited baseline with `schema_version: 3` but no `tool_versions` bypasses the toolchain stamp — unlikely via `baseline_from_rows`, but possible via manual JSON.

- [LOW] **Per-paper sidecars are write-only; stale schema-1 sidecars can mislead external readers.** Evidence: sidecars written each successful score (`__main__.py:232-241`); `WhiskerResult.schema_version` stamped in `to_dict` (`score.py:82-90`); no loader in src. Impact: same class of stale-artifact hazard as `report.json` for dashboards that read `<pid>.whisker.json` without checking `schema_version`.

- [LOW] **CLAUDE.md bench example conflates artifact types.** Evidence: `whisker bench --corpus ./gt --baseline whisker/report.json` (`CLAUDE.md:92`) vs score report shape `{count, counts, results}` (`report.py:87-95`) vs bench shape `{aggregate, rows}` (`__main__.py:314-318`). Impact: misconfiguration errors loudly (`KeyError`), not silent pass — but documents the wrong baseline file for bench.

## False-pass hypothesis

A CI job or dashboard reads `data/whisker/report.json` at schema **1** (126 pass / 236 review / 20 fail, §3b) and treats those verdicts as current without re-running `whisker --all` — shipping decisions based on pre-v3 semantics (oracle-heavy review pile, old `ref_overall` averaging) while code now stamps schema **3** (`constants.py:166`). Whisker itself never loads that file, so the false pass is **outside** the package, not inside `_decide`.

## False-fail hypothesis

After upgrading to schema **3**, an operator runs `whisker guard --baseline corpus/guard.json` still at schema **1**; `_validate_baseline` raises (`guard.py:266-271`) and CLI exits error (`__main__.py:422-424`). That is correct fail-closed behavior, but reads as "whisker broke" until `--update` — not a conversion false fail, a versioning ritual false alarm.

## What would change my mind

A repo-wide grep (or integration test) showing any whisker entry point that **loads** `report.json` or `<pid>.whisker.json` to drive verdicts or exit codes without checking `schema_version == WHISKER_SCHEMA_VERSION` — that would flip guard-adjacent artifacts from "human hazard" to "silent false pass inside whisker."
