# 28 - determinism-auditor

**Verdict:** usable-with-conditions — the routed-only path already serializes units with a stable severity-then-numeric-page sort, and per-unit LLM prompts are isolated, but the planned `--all-pages` merge is not implemented yet; it fails determinism unless required `page:N` units bypass the empty-signal guard, skip quota caps, dedupe by `unit_id`, and iterate in explicit numeric page order rather than a bare set union.
**Confidence:** high

## Findings

- [HIGH] Routed unit iteration order is deterministic today: signals are sorted by `(severity_rank, _unit_id_sort_key(unit_id), signal_type, detail)` before grouping (`unit_judge.py:290-299`), `risky_unit_ids` inherits that stable first-seen order from dict insertion (`unit_judge.py:300-303`), and `_unit_id_sort_key` numeric-sorts `page:13` after `page:2` (`unit_judge.py:122-133`, `test_defect_accountability.py:189-197`). Impact: capped and exhaustive routed runs replay the same unit sequence; all-pages should **not** reuse severity-first ordering for the full required set — baseline intent is every `page:N` (`00-baseline.md:44`), so execution and audit order should be `sorted(required_unit_ids, key=_unit_id_sort_key)` (page 1..N).

- [HIGH] The planned required-units extension is undefined in current code and breaks determinism of coverage semantics if copied naively: `run_unit_checks` returns `None` when `risk_signals` is empty (`unit_judge.py:287-288`), so an all-pages paper with zero router hits never enters the unit loop; `pdf_judge.py:837-850` only calls `run_unit_checks` inside `if risk_signals`. Impact: two all-pages runs both “deterministically” skip all unit checks — stable, but wrong; implementors must inject `required_unit_ids` before the guard and always materialize a `UnitJudgeResult`.

- [HIGH] Union of required pages and routed pages can be stable and checked exactly once if keyed by `unit_id`: `signals_by_unit` is a dict keyed by `unit_id` with list append (`unit_judge.py:300-302`), and the execution loop walks `selected_unit_ids` once with `await _check_one_unit` (`unit_judge.py:317-334`). Impact: a page with both a risk signal and required status must land in `signals_by_unit[unit_id]` exactly once; required-only pages need an empty signal list or a fixed synthetic placeholder (not a second loop pass). Duplicate entries in `selected_unit_ids` would double LLM spend and break audit counts.

- [MED] No unsorted dict/set iteration feeds LLM prompts on the current PDF unit path: `signal_detail` is `"; ".join(...)` over the ordered `unit_signals` list (`unit_judge.py:331`), and `source_router.py` uses sets only for membership tests (`source_router.py:175-178`, `192-194`, `240-243`), not for prompt assembly. `_aggregate_defects` sorts group output before return (`unit_judge.py:499-505`). Impact: D7 is satisfied today; the all-pages merge must not introduce `list(set(required) | set(routed))` without an explicit sort — set iteration order is hash-seed sensitive and would violate run-to-run ordering discipline for `selected_unit_ids`, `checked_unit_ids`, and debug transcripts.

- [MED] Adding required units does **not** change LLM inputs for a routed unit that is checked in both fleet and all-pages modes: `_check_one_unit` receives only that unit’s `source_text`, full `candidate_md`, and joined signal details — no prior unit results or sidecar state (`unit_judge.py:673-680`), and upstream monolith/metadata/escalation steps in `judge_pdf_extraction` run before unit checks regardless of coverage mode (`pdf_judge.py:639-823`, `837-850`). Impact: semantic stability for the same routed `page:N` is preserved across modes; document-level verdict may differ because more units demote to `review` (`unit_judge.py:390-393`, `pdf_judge.py:884-885`), which is intentional coverage expansion, not cross-unit context contamination.

- [MED] Quota selection must be bypassed in all-pages mode: `_select_units_with_quotas` (`unit_judge.py:136-174`) can leave routed units unchecked when `max_checks < len(risky_unit_ids)` (`unit_judge.py:304-311`), and non-exhaustive PDF runs hard-cap at `MAX_UNIT_CHECKS` because `pdf_judge.py:843-850` never passes `exhaustive=True`. Impact: all-pages must set `max_checks = len(required_unit_ids)` (or skip quota entirely) — otherwise two runs both “deterministic” but systematically omit the same capped subset, which is coverage failure not randomness.

- [LOW] Audit-side ordering has a minor inconsistency: `unchecked_unit_ids` is emitted as `sorted(set(unchecked_unit_ids))` with default string sort (`unit_judge.py:423`), so `page:10` sorts before `page:2` lexically, unlike `_unit_id_sort_key` used elsewhere. Impact: run-to-run stable but operator/debug trace page order disagrees with numeric page order; all-pages sidecar should sort unchecked/checked IDs with `_unit_id_sort_key` for coherent audit replay.

- [LOW] Serial LLM execution is preserved and all-pages only lengthens the serial chain: unit checks await one at a time (`unit_judge.py:317-334`), page escalations await sequentially (`pdf_judge.py:744-754`), and `run_judge_task` deliberately avoids the global pipeline semaphore (`judge_task.py:63-68`) while the CLI bounds paper-level concurrency (`pdf_judge.py:640-641`, `00-baseline.md:25`). Impact: D11 serial discipline holds; a 40-page all-pages run is 40 additional serial unit calls, not new in-paper parallelism.

## False-pass hypothesis

Implementor merges `required_unit_ids` with routed IDs via `selected = list({*required, *risky})` without sorting, documents “deterministic all-pages,” and operators diff two runs with different `PYTHONHASHSEED` values — `checked_unit_ids` and debug `unit-check-*` label order differ even though per-unit verdicts match, so regression harnesses falsely pass functional parity while failing reproducibility discipline.

## False-fail hypothesis

Operator compares fleet capped run (severity-first, 5 units) against all-pages run (numeric page 1..N) and treats different `unit_checks` list ordering or sidecar `unit_selection[].reason` values as non-deterministic regression — a process false-fail unless fingerprints and ordering conventions are mode-specific (`00-baseline.md:44` separate fingerprint).

## What would change my mind

A landed `--all-pages` implementation with a test that runs the same 15-page fixture twice under different `PYTHONHASHSEED` values and asserts identical `checked_unit_ids`, `unit_selection` order (numeric page order), and per-`unit_id` prompt payloads for overlapping routed pages versus a capped fleet run on the same fixture.
