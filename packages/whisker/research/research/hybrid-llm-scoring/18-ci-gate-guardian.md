# 18 - CI Gate Guardian

**Verdict:** usable-with-conditions (+ merged scoring can ship without breaking the CI contract only if top-level `verdict` and `whisker --gate` stay deterministic-only, merged fields are namespaced with `advisory: true`, and any future gate flag lives on a separate advisory CLI never wired to default CI)
**Confidence:** high

## Findings

- [CRITICAL] **The only CI gate input today is deterministic `WhiskerResult.verdict`; line 275 is the sole exit-code choke point.** Evidence: `_verdict_exit_code` maps verdict lists against `_GATE_ACCEPTS` (`__main__.py:80-84`, `122-128`); `_score_main` returns `_verdict_exit_code([r.verdict for r in results], args.gate)` (`__main__.py:275`); exit constants `0/1/3/5` at `constants.py:136-139`. Impact: writing `merged_verdict` into `WhiskerResult.verdict`, passing fused verdicts into `_verdict_exit_code`, or aliasing `hybrid.verdict` to top-level `verdict` would silently retarget CI without changing `--gate` documentation (C1 violation).

- [CRITICAL] **Seven in-repo consumers assume sidecar top-level `verdict` is the deterministic on-record verdict; co-locating merged data in the same file must not repurpose that key.** Evidence: `select_candidates` branches on `r.get("verdict")` for PRIMARY/SECONDARY/RESCUE (`adjudicate.py:82-96`); `inspect_report.format_paper_section` reads `whisker.get("verdict")` and compares to `tapetum.suggested_verdict` (`inspect_report.py:48-56`, `125-128`); `TapetumResult` snapshots `whisker_verdict` from sidecar (`adjudicate.py:309-310`, `models.py:118`); `build_report` / `render_report_md` / `render_summary` count and color on `r.verdict` only (`report.py:37-38`, `84`, `118`, `228-255`); `WhiskerResult.to_dict` emits closed deterministic schema (`score.py:89-115`); `_collect_sidecar_dicts` loads `*.whisker.json` for tapetum batch (`cli.py:197-200`). Impact: a nested `hybrid.verdict` is safe; renaming or overwriting top-level `verdict` breaks candidate selection, inspect diffs, and report rollups. `packages/cli` has zero whisker imports (grep: no matches), so leak surface is whisker internals plus operator scripts reading `data/whisker/`.

- [CRITICAL] **`--gate-merged` on the main `whisker` command must be rejected outright; it contradicts C1 verbatim.** Evidence: C1 (`00-baseline.md:38`): tapetum_llm "NEVER gates, is never in the `whisker --gate` CI contract"; CLAUDE.md tapetum section repeats "NEVER hard-fails, is never in the `whisker --gate` CI contract" (`CLAUDE.md:369-371`); tapetum CLI docstring: "never touches `whisker --gate`" (`cli.py:11-13`). Impact: any flag on `whisker` that maps exit codes 3/5 from a merged or LLM-inclusive verdict redefines the CI contract the docs freeze. An opt-in gate on a **separate** entry point (e.g. `whisker-tapetum-llm --gate-merged`) is architecturally separable but still fights C1's "NEVER gates" if wired to CI; treat it as a local/scheduled human workflow only, never `.github/workflows/tests.yml`.

- [HIGH] **`report.json` `counts` is a single-lane `{pass, review, fail}` dict tied to deterministic results; three verdict columns require namespaced rollups or a sibling artifact.** Evidence: `build_report` sets `"counts": _counts(ordered)` where `_counts` sums `r.verdict` (`report.py:37-38`, `87-95`); tests assert `report["counts"]["pass"]` against whisker verdicts only (`test_report.py:46-51`); whisker persists `report.json` from `build_report(results)` with no tapetum input (`__main__.py:250-252`). Impact: adding merged counts into the same `counts` object without keys like `counts.deterministic` / `counts.merged` makes dashboards and scripts that read `counts.fail` ambiguous. Recommended: keep whisker `report.json` deterministic-only; emit `report-merged.json` with `counts: { deterministic: {...}, tapetum: {...}, merged: {...} }` (persona 16).

- [HIGH] **Merged CLI exit code must always be 0 (advisory), mirroring tapetum.** Evidence: tapetum `_EXIT_OK = 0` and `sys.exit(_EXIT_OK)` unconditionally (`cli.py:37`, `400`); module docstring: "exit code always 0 for advisory" (`cli.py:11-13`). Impact: a merged-report command that returns 3/5 on `merged_verdict` becomes a shadow CI gate even if not default; operators will script against it. Persist `advisory: true` on every merged payload (`models.py:135` precedent); document "not CI contract" in CLI help.

- [HIGH] **Batch scoring errors are excluded from gate verdicts but visible in the footer; merged logic must not promote errored/skipped papers.** Evidence: per-paper exceptions increment `errored` and skip the result list (`__main__.py:218-223`); `_verdict_exit_code` runs only on successfully scored `results` (`__main__.py:275`); footer reports errored separately (`report.py:242-246`). Impact: if fusion treats missing tapetum as pass-equivalent (worst-of) or missing whisker as green, batch holes become false passes. Baseline: 6/200 tapetum errors leave no sidecar (`00-baseline.md:51`); fusion must use `combined_rule: "whisker_only"` / `tapetum_available: false` (persona 13), never synthetic LLM pass.

- [MED] **Default `--gate review` already collapses 54% of papers into exit 0; merged triage must not replace this binary without explicit operator opt-in.** Evidence: runtime distribution 134 pass / 232 review / 15 fail deterministic (`00-baseline.md:48-49`); `_GATE_ACCEPTS["review"]` accepts pass and review (`__main__.py:80-84`); only `VERDICT_FAIL` yields exit 5 at default gate (`__main__.py:124-125`). Impact: a merged-sorted terminal summary or `report-merged.md` sorted by `merged_verdict` is fine for human triage (persona 16), but wiring merged sort into `whisker --gate` or replacing `render_summary` (`__main__.py:263-268`) would change CI semantics and break `test_report.py` contracts.

- [LOW] **GitHub CI today does not invoke `whisker --gate`; the contract is latent but binding for operators.** Evidence: `.github/workflows/tests.yml:65` runs `pytest packages/whisker/tests` only; no subprocess exit-code tests for gate (`16-test-suite-auditor.md` finding cited in persona 09). Impact: gate regressions would not fail CI until integration tests exist; merged work should add subprocess tests asserting `whisker --gate` ignores `hybrid`/`tapetum` keys and reads only deterministic `verdict`.

### Guardrail specification (mandate detail)

| Surface | Deterministic on record | Merged / LLM |
|---------|-------------------------|--------------|
| `<pid>.whisker.json` top-level `verdict` | Whisker-only, never overwritten by tapetum/fusion | Nested `tapetum` + `hybrid` blocks with own `schema_version`, `advisory: true` (persona 15) |
| Merged verdict field name | N/A | `hybrid.verdict` or `combined_verdict` inside advisory block; **never** bare `verdict` at top level |
| `whisker --gate` exit | `[r.verdict for r in results]` only (`__main__.py:275`) | Unchanged; no merged input |
| Merged CLI exit | N/A | Always `0` (`cli.py:400` pattern) |
| `report.json` | `counts` = deterministic trichotomy (`report.py:93`) | Separate `report-merged.json` with namespaced counts |
| `report.md` footer | `=== F failed, R review, P passed ===` on det counts (`report.py:237-255`) | Fusion footer labels lane: `merged: X fail, Y review, Z pass (det: …, llm: …)` |
| `--gate-merged` | **Reject** on `whisker` (C1) | Optional on advisory-only CLI; default off; never in CI workflow |

**Preserve-on-rewrite:** when deterministic `whisker --all` rewrites sidecars, extension keys `tapetum`/`hybrid` must round-trip (`__main__.py:246-248` today deletes them; persona 15 CRITICAL). Set `hybrid.stale: true` when fingerprint mismatches.

### Three-tier footer / `report.json` counts (unambiguous layout)

Whisker `report.json` (unchanged contract):

```json
"counts": { "pass": 134, "review": 232, "fail": 15 }
```

`report-merged.json` (new artifact, tapetum-owned):

```json
"counts": {
  "deterministic": { "pass": 134, "review": 232, "fail": 15 },
  "tapetum": { "pass": 101, "review": 76, "fail": 17, "error": 6 },
  "merged": { "pass": 88, "review": 89, "fail": 17, "whisker_only": 187 }
}
```

Terminal: whisker keeps one footer (`report.py:237-255`); fusion CLI prints a **second** labeled footer so `=== 15 failed ===` is never read as merged fail without the prefix `merged:`.

## False-pass hypothesis

Whisker `pass` on a PRIMARY false-pass (table/cell swap, high `unigram_coverage`, no tapetum sidecar because `select_candidates` never selected it, `adjudicate.py:86-88`, `101-113`): fusion with `combined_rule: "whisker_only"` yields `merged_verdict=pass`. If an operator scripts `jq '.hybrid.verdict'` without checking `tapetum_available` or treats missing LLM as confirmation, the paper ships with semantic corruption the LLM lane exists to surface (`00-baseline.md:49`, 123/194 disagree when tapetum did run).

## False-fail hypothesis

Uncapped worst-of fusion: whisker `pass` + tapetum `suggested_verdict=fail` (major tables, e.g. P4003R0, `00-baseline.md:50`) → `merged_verdict=fail`. If that field ever feeds exit codes or replaces top-level `verdict`, CI blocks a paper the deterministic gate accepted. Persona 13's escalation matrix caps combined at `review` unless whisker is already `fail`; raw worst-of breaks C1.

## What would change my mind

Subprocess integration tests in `packages/whisker/tests` that (1) write sidecars with nested `hybrid: { "verdict": "fail", "advisory": true }` while top-level `verdict` is `pass`, run `whisker --gate pass`, and assert exit `0`; (2) run a tapetum fusion CLI with `--gate-merged fail` and assert it is **not** invoked from `.github/workflows/tests.yml`; plus a documented CI recipe using only `whisker --no-reference --gate review` on deterministic output. Passing those would flip the verdict to **usable** unconditionally.
