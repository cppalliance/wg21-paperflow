# 23 - Isolation Guardian

**Verdict:** usable-with-conditions (+ merge computation, persistence, and merged rendering belong in `tapetum_llm` behind the existing `whisker-tapetum-llm` CLI; core `report.py` and `WhiskerResult` must stay tapetum-free; JSON sidecars on disk are the sanctioned join interface, not Python imports across the boundary.)
**Confidence:** high

## Findings

- [CRITICAL] **C2 is an import rule, not a filename ban.** `CLAUDE.md:408-409` and `tapetum_llm/__init__.py:25-27` state "whisker core never imports `tapetum_llm`." Core `__init__.py:10-106` exports only deterministic modules (`score`, `report`, `bench`, …) with zero tapetum symbols. A core function that reads `<pid>.whisker.tapetum.json` by path convention does **not** violate the literal invariant (no `import whisker.tapetum_llm`), but it **does** violate the architectural intent: the deterministic lane would acquire LLM sidecar schema knowledge and merge semantics. Impact: keep filename knowledge and join logic in `tapetum_llm`; core may optionally preserve opaque extension keys on rewrite (persona 15) without parsing them.

- [CRITICAL] **Existing dependency edges are one-way and must stay that way.** `tapetum_llm/cli.py:30-33` imports `whisker.__main__._render_progress`, `whisker.score.sidecar_path` / `whisker_output_dir`, and tapetum-internal modules only. Reverse grep confirms no `from whisker.tapetum` in core library files outside `menu.py:156,169` (CLI, listed in `test_claude_invariants.py:40` as `_CLI_MODULES`). Impact: placement (a) `tapetum_llm/fusion.py` extends the legal direction; placement (c) in `report.py` couples core rendering to hybrid semantics even if import-clean.

- [HIGH] **Placement (a) is the only placement that matches existing patterns end-to-end.** `inspect_report.py:8-17` already joins whisker + tapetum **plain dicts** ("Library returns strings; the CLI persists"). `cli.py:207-217` persists tapetum sidecars beside whisker sidecars using `sidecar_path(pid, backend).stem` + `.tapetum.json`; `cli.py:220-228` reads whisker sidecars back as dicts. `cli.py:131-135,383-385` shows the `--inspect` flag pattern for an optional post-adjudication artifact. Recommended modules: `tapetum_llm/fusion.py` (`fuse_sidecars(whisker: dict, tapetum: dict | None) -> FusionResult`), `tapetum_llm/fusion_report.py` (`render_fusion_md`, `render_fusion_summary`), wired from `cli.py` via `--fuse` (or default-on with `--inspect`). Impact: goals 1–3 without touching `WhiskerResult.verdict` (C1) or `score.py` gate path.

- [HIGH] **C4 splits cleanly inside tapetum_llm: library returns data, CLI persists.** `report.py:10-12` documents the same contract for deterministic reports; `models.py:17-18` repeats it for `TapetumResult`. `__main__.py:240-255` is the sole deterministic persistence site. Merge persistence must follow `cli.py:207-217` (new `<pid>.fusion.json` and/or `report-merged.md`), never `score_paper` / `WhiskerResult.to_dict`. Impact: joint persistence is legal in tapetum CLI; illegal inside `fusion.py` if it calls `write_text`.

- [MED] **Placement (b) a third console script is import-legal but architecturally redundant.** A `whisker-fuse` reading both `*.whisker.json` and `*.whisker.tapetum.json` with pure dict code would not import `tapetum_llm` and would not break C2. Dict-level coupling at the JSON boundary is already sanctioned: `inspect_report.py:45-46` takes `(whisker: dict, tapetum: dict | None)`; `cli.py:197-200` glob-scans sidecars as dicts. Spirit of C2 is preserved when coupling is **on-disk artifacts**, not Python module edges. However, `pyproject.toml:33-35` already defines exactly two entry points (`whisker`, `whisker-tapetum-llm`); a third script duplicates the join pass `cli.py` already performs for `--inspect` and fragments operator workflow. Impact: use (b) only for offline re-merge without re-adjudication; default home remains (a).

- [MED] **Placement (c) core `report.py` optional merged columns is the riskiest legal option.** `render_report_md` accepts `list[WhiskerResult]` only (`report.py:98-100`); `build_report` serializes deterministic results (`report.py:87-95`). Extending signatures with optional `tapetum_overlays: dict[str, dict]` avoids a tapetum import but drags hybrid semantics into the CI-facing deterministic report writer (`__main__.py:254-255` → `report.md`). `test_report.py:46-50` contract-tests deterministic sort/count behavior. Impact: if merged columns are needed in Markdown, add `report-merged.md` from `fusion_report.py`, not columns in core `report.md` (aligns with persona 16).

- [MED] **Test placement convention: tapetum-prefixed files under `packages/whisker/tests/`.** Lane tests live in `test_tapetum_llm.py:8-15` (imports from `whisker.tapetum_llm.*`); core report tests in `test_report.py:13-14`. Fusion unit tests belong in `test_tapetum_llm.py` (alongside `TestInspectReport` at `test_tapetum_llm.py:428-494`) or a sibling `test_tapetum_fusion.py`; do not add tapetum assertions to `test_report.py`. Menu dispatch tests in `test_menu.py:28-36` require `MENU_ITEMS` and `_DISPATCH` keys stay aligned when adding a fuse prompt flag.

- [LOW] **Menu integration point is options 2–3 via `_prompt_tapetum_flags`.** `menu.py:50-56` lists five actions; options 2 and 3 call `tapetum_main(["--review-all"] + flags)` (`menu.py:158-159,171-172`) where flags come from `_prompt_tapetum_flags` (`menu.py:114-123`, `--inspect` default yes). A `--fuse` flag belongs in that prompt list and in `cli.py`'s argparse beside `--inspect` (`cli.py:131-135`). Option 5 (`menu.py:227-245`) reads deterministic `report.md` only; merged view should target `report-merged.md` or extend option 5 with a file chooser later.

### Recommended placement (single choice)

**Home:** `packages/whisker/src/whisker/tapetum_llm/fusion.py` + `fusion_report.py`, invoked and persisted from `tapetum_llm/cli.py` (`--fuse`), surfaced in `menu.py` via `_prompt_tapetum_flags`.

**Dependency-edge diagram (prose):**

```
whisker core (score.py, report.py, __main__.py)
  ↑ read-only imports (sidecar_path, whisker_output_dir, _render_progress)
  │
tapetum_llm/
  ├── adjudicate.py → pipeline, paperstore (LLM lane)
  ├── inspect_report.py → (no whisker/tapetum imports; plain dict in/out)
  ├── fusion.py       → (NEW) plain dict in/out; may import tapetum_llm/chunking.py for severity fold only
  ├── fusion_report.py→ (NEW) plain dict in/out; mirrors inspect_report pattern
  └── cli.py          → fusion + fusion_report + inspect_report; sole writer of *.fusion.json / report-merged.*
  ↑ lazy import
menu.py (CLI only, optional extra gate via _has_tapetum_llm)
```

No arrow from whisker core → tapetum_llm. JSON files (`*.whisker.json`, `*.whisker.tapetum.json`, `*.fusion.json`) are the cross-lane interface at rest.

## False-pass hypothesis

If merge rendering were added to core `report.py` with optional tapetum overlay dicts loaded by `__main__.py` from `*.whisker.tapetum.json`, a future maintainer could wire `combined_verdict` into `render_summary` triage (`report.py:145-163`) and accidentally surface merged tiers in `whisker --gate` output, letting the advisory lane influence CI exit codes (`__main__.py:275`, C1). Keeping fusion out of core eliminates that import-adjacent footgun.

## False-fail hypothesis

If a third standalone script (placement b) re-merges sidecars using stale tapetum JSON after `whisker --all` rewrote deterministic fields (`__main__.py:246-248`, no fingerprint today per `models.py:114-136`), operators could see `combined_verdict=review` from a tapetum snapshot whose embedded `whisker_verdict` no longer matches the on-record verdict, falsely elevating triage priority. Fusion should run in the adjudication CLI immediately after fresh reads, or carry a `whisker_fingerprint` check in `fusion.py`.

## What would change my mind

An explicit CLAUDE.md amendment stating "whisker core may read tapetum sidecar JSON for report rendering without importing tapetum_llm" **and** a core `__main__` path that loads overlays only when `importlib.util.find_spec("pipeline")` succeeds (mirroring `menu.py:35-41`) while `--gate` output remains pure `WhiskerResult` — would flip the recommendation toward optional merged columns in a tapetum-free code path inside `__main__.py`, still not inside `report.py`.
