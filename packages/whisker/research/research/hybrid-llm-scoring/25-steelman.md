# 25 - Steelman (Minimalism Defender)

**Verdict:** usable-with-conditions (+ goals 1–3 are already ~80% shipped; the remaining work is a pure sidecar joiner and one named advisory tier in reports, not a new pipeline or schema surgery.)
**Confidence:** high

## Findings

- [CRITICAL] **Goal 1 is done: tapetum_llm is a production advisory lane with persistence, grounding, and cascade.** Evidence: `tapetum_llm.md:1-13` (authority doc, advisory-only); `models.py:89-136` (`TapetumResult`, `"advisory": true`); `cli.py:207-217` (writes `<pid>.whisker.tapetum.json` into `data/whisker/`); runtime `00-baseline.md:48-49` (194/200 adjudicated, 123/194 differ from whisker). Impact: the swarm should adopt mechanics from external repos into this lane, not replan Lane 4 (`whisker-llm-lane4-plan.md:80-92` already superseded by shipped `tapetum_llm`).

- [CRITICAL] **Goal 2 is done for "alongside deterministic results"; same-file is optional and costlier than the user thinks.** Evidence: `cli.py:212` (tapetum sidecar colocated: `{stem}.tapetum.json` next to `{stem}.whisker.json`); `models.py:101-118` (`whisker_verdict` embedded as join key); `00-baseline.md:50` (example sidecars on disk). Impact: persisting both lanes in one JSON requires whisker CLI preserve-on-rewrite (`__main__.py:246-248` full-overwrites today; `15-sidecar-schema.md:8-9`) and creates two-writer torn-state risk. **Separate files + join at read time satisfies goal 2 without touching C2.**

- [HIGH] **Goal 3 partially exists: `tapetum-inspect.md` IS the merge view; it lacks only a NAMED combined tier.** Evidence: `inspect_report.py:8-18` ("Joins a whisker sidecar … with a tapetum sidecar … into one Markdown report"); `inspect_report.py:55-56` (`agree` / `DIFFERS` on `(whisker.verdict, tapetum.suggested_verdict)`); `cli.py:231-243` (`_persist_inspect` → `tapetum-inspect.md`). Impact: goal 3 is "add `combined_verdict` + rule label + optional `<pid>.fusion.json`", not rebuild adjudication.

- [HIGH] **The merge should be a ~200-line pure-function joiner + one new report artifact, not a pipeline.** Evidence: `inspect_report.py` is 119 LOC of deterministic join already; fusion logic reuses `worst_axis_verdict` severity fold (`chunking.py:106-123`) and tapetum demotion rules (`tapetum_llm.md:163-164`, `adjudicate.py` decide step cited in authority doc). `.cursor/rules/development-discipline.mdc:9-18` (Minimalism Ladder: YAGNI → stdlib → existing dep → one line → minimum that works); `:22-25` ("No abstraction … no scaffolding for later … Deletion over addition"). Impact: `tapetum_llm/fusion.py` with `fuse_sidecars(whisker: dict, tapetum: dict | None) -> FusionResult` plus `fusion_report.py` (mirror `inspect_report.py`) meets goal 3 at the lowest rung that satisfies C1/C4.

- [HIGH] **Pre-empt: weighted numeric composites without calibration = pseudo-precision; reject candidate (b).** Evidence: `score.py:118-184` (gate verdict = rules, not a score; `00-baseline.md:16-17`); `bench.py` is the only true `overall` mean (`00-baseline.md:23-24`); `QA-RELIABILITY-VERDICT.md:66-67` ("0 calibration … PROVISIONAL edges"); `tapetum-llm-decision-synthesis.md:44-45` ("Nothing is calibrated"); anti-pattern `tapetum-llm-decision-synthesis.md:158-159` ("single `overall` composite"). Impact: showing `ref_overall` and tapetum `confidence` as **separate lane columns** (`report.py:108-109`, `models.py:120`) is honest; blending them implies a gate the deterministic lane never defined.

- [HIGH] **Pre-empt: same-file persistence (Option A in persona 15) = write-ownership conflict; keep two sidecars + optional third fusion file.** Evidence: `__main__.py:246-248` (whisker `--all` overwrites entire sidecar from `WhiskerResult.to_dict()`); `score.py:84-115` (closed key set, no extension round-trip); `15-sidecar-schema.md:8-10`. Impact: concurrent `whisker --all` + `whisker-tapetum-llm` on the same PID can silently drop nested `tapetum`/`hybrid` blocks; separate files preserve C1 (deterministic record immutable) and C2 (one-way import).

- [MED] **Prior research already decided: advisory-only, never gates, severity-aware fold — do NOT relitigate.** Evidence: C1 `00-baseline.md:38`; `tapetum_llm.md:3-4` ("never part of `whisker --gate`, never hard-fails, never overwrites the whisker verdict"); `whisker-llm-lane4-plan.md:43-53` (olmOCR rejects LLM-as-judge in scoring loop; Lane 4 advisory only); `chunking.py:106-123` + `tapetum_llm.md:56-64` (fail requires `major` severity). Impact: any merge that lets tapetum `fail` override whisker `pass` into combined `fail` violates the architecture settled in June 2026.

- [MED] **The one genuinely new decision this request forces: name the merged tier and where it renders.** Evidence: inspect report shows two lanes but no third column (`inspect_report.py:65-68`); whisker `report.md` is deterministic-only (`report.py:98-123`, `__main__.py:254-255`). Impact: pick **`combined_verdict`** (advisory, `advisory: true`) with rule id e.g. `llm_escalate_major`; render in (1) `<pid>.fusion.json` or batch `hybrid-report.json`, (2) extended `tapetum-inspect.md` header table `whisker | tapetum | combined | rule`, (3) optional tapetum CLI terminal summary — **not** in `whisker --gate` output or top-level `verdict` field.

### Do NOT build

| Item | Why not | Anchor |
|---|---|---|
| New LLM pipeline / third cascade tier for merge | Merge is deterministic join of existing sidecars | `development-discipline.mdc:13`; `inspect_report.py:16-17` |
| Nested `tapetum`/`hybrid` inside `<pid>.whisker.json` | Full overwrite + two writers | `__main__.py:246-248`; `15-sidecar-schema.md:8-9` |
| `WHISKER_SCHEMA_VERSION` bump for LLM fields | Deterministic contract must stay closed | `00-baseline.md:17`; `constants.py` pin per `15-sidecar-schema.md:18-19` |
| Confidence-weighted or averaged numeric "hybrid score" | Uncalibrated pseudo-precision | `QA-RELIABILITY-VERDICT.md:66-67`; `tapetum-llm-decision-synthesis.md:158-159` |
| Worst-of raw verdicts (tapetum fail → combined fail on whisker pass) | LLM becomes shadow gate; breaks C1 | `00-baseline.md:38-44`; `13-score-fusion-architect.md:14-15` |
| Import `tapetum_llm` from `score.py` / whisker core | Violates C2 isolation | `00-baseline.md:39` |
| Relitigate "should tapetum gate CI?" | Decided: no | `whisker-llm-lane4-plan.md:94-98`; `tapetum_llm.md:3` |
| Calibration sprint before shipping display merge | Display merge does not need fitted weights; calibration is a separate track | `tapetum-llm-decision-synthesis.md:124-138`; `QA-RELIABILITY-VERDICT.md:120-122` |

## False-pass hypothesis

PRIMARY false-pass never sent to tapetum: whisker `pass` with table row/cell swap, high `unigram_coverage`, no PRIMARY risk signals (`tapetum-llm-decision-synthesis.md:25-30`, `select_candidates` PRIMARY at `adjudicate.py:86-88` per synthesis doc). Conservative fusion returns `combined_verdict=pass` / `whisker_only` when tapetum sidecar absent; the 76-paper row-swap attack (74 pass) remains uncaught by merge unless candidate selection expands.

## False-fail hypothesis

Whisker `fail` on heading-monotone-only (`gates.py:96-112`, RESCUE in `tapetum-llm-decision-synthesis.md:41-43`) with tapetum `suggested_verdict=review` after severity fold (`chunking.py:117-120`, validated P3941R4 `tapetum-sighting-run-2026-07-01.md:41-45`). A merge rule that locks `combined_verdict=fail` whenever whisker is `fail` cannot rescue via combined tier; operator must read tapetum column in inspect report (by design: deterministic record stays fail, C1).

## What would change my mind

Measured evidence that same-file Option A with preserve-on-rewrite survives concurrent `whisker --all` + tapetum batch without lost extension keys (integration test requested in `15-sidecar-schema.md:32`) **and** that operators actually consume per-paper merged JSON (not just markdown inspect) — would justify nested sidecar complexity over the two-file + `fusion.py` steelman.
