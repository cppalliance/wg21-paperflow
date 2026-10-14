# 29 - Inspect consumer tradeoff (metadata short-circuit vs fleet cold run)

**Verdict:** usable-with-conditions — metadata short-circuit is **verdict-safe** on the default nightly fleet path (no `--all-pages`, no `--inspect`); it trades away **inspect-channel completeness** on ~61% of papers (232/378 ok sidecars) while **`report-merged` fusion rollups remain correct**.
**Confidence:** high

## Executive answer

| Question | Answer |
|----------|--------|
| **Fleet cold run uses `--all-pages`?** | **No.** Bare `whisker-tapetum-llm` (full corpus, incremental skip) runs routed mode only. Throughput baseline logged `all_pages=False` on every paper (`research/tapetum-llm-throughput/14-steelman.md:20`). |
| **Short-circuit OK for nightly fleet?** | **Yes** — for the fleet's actual job (advisory fusion rollup + sidecar freshness). **No** — if the operator treats fleet sidecars as the source for later `--fuse-only --inspect` or expects page-scoped triage quotes without re-running audit flags. |
| **When to keep full cascade** | Any run where humans read `tapetum-inspect.md` or sidecar `defect_groups` matter: **`--inspect`**, **`--exhaustive-units`**, **`--all-pages`** (golden-PR per `pr-golden-review.md`), explicit PID adjudication for triage, dev-replay/holdout validation before call-graph lever merges. |

---

## Fleet mode vs audit mode (three orthogonal knobs)

| Flag | Fleet cold default | Golden-PR / operator audit |
|------|--------------------|----------------------------|
| `--all-pages` | off | on for PDF per-PID review (`pr-golden-review.md:61`) |
| `--inspect` | off | on (writes `whisker/llm/tapetum-inspect.md`) |
| `--exhaustive-units` | off (implied by `--inspect` when used) | on via `--inspect` |

CLI wiring (`cli.py:1326-1328`): `exhaustive_units = args.exhaustive_units ∨ args.inspect` → **`--inspect` bypasses metadata short-circuit** even without `--all-pages`.

Short-circuit guard (`pdf_judge.py:748-752`):

```python
if metadata_check.verdict != "pass" and not all_pages and not exhaustive_units:
    metadata_short_circuited = True
```

Fleet cold run therefore **does** execute metadata short-circuit on metadata fail/review papers. It **does not** produce an inspect report unless `--inspect` was passed (inspect is a separate CLI flag, not part of nightly automation).

---

## What inspect completeness is lost

When short-circuit fires, the PDF lane skips **page escalations** and **`run_unit_checks`** entirely (`pdf_judge.py:798-987`). HTML lane mirrors with early return in `_run_html_unit_checks` (`adjudicate.py:521-531`).

### Sidecar fields emptied or vacuous

| Field | Short-circuited value | Inspect impact |
|-------|----------------------|----------------|
| `unit_checks` | `[]` | No per-unit verdict table, no unit-level defects |
| `defect_groups` | `[]` | Defect groups section omitted in inspect (`inspect_report.py:419-444`) |
| `page_escalations` | `[]` (PDF) | No page-attributed missing-content quotes from escalation path |
| `risk_signals` | `[]` | Risk-signal section empty (normally capped at 5 in inspect) |
| `unit_coverage` | `coverage_complete=True`, `checked=0`, `mode=metadata_short_circuit` | Fusion-correct but human-misleading if reader ignores `mode` |
| `unit_selection` | all empty lists | Page coverage table shows every page as `unit check: none` |

Measured v10 replay (P145 / persona 17): **232** metadata-non-pass papers would have run **1047** unit checks (**44.6%** of fleet LLM calls) that **cannot change merged verdict** after metadata cap + fusion `source_aware_review_cap` (`fusion.py:187-189`, `410-423`).

### Diagnostic depth lost (not verdict)

| Loss class | Quant (v10 replay) | Example |
|------------|-------------------|---------|
| Zero-defect unit latency only | **692/1047 (66%)** unit calls | Pure wall-time waste even pre-short-circuit |
| Accepted unit defects under metadata `review` | **19 papers** | e.g. P1000R8 `table_corruption` on `page:1` — merged already `review`, but inspect loses the table quote |
| Unit `defect_groups` on metadata `fail` | **11/32** fail papers | e.g. P4231R0 — 2 accepted `content_omission` quotes; fail locked, but operator cannot see *where* body text dropped |
| Page escalation corroboration | **~15** PDF calls on metadata-non-pass set | Screen-flagged pages get no scoped LLM confirmation |
| Dev-replay recall on defect types | **35 defect groups / 30 papers** (P145) | Fleet flip gate passes; localized `page_content_omission` / `table_corruption` groups absent from sidecar |

What **remains** in sidecar and inspect for short-circuited papers: monolith verdict/reasoning, **metadata/outline check** block, ideal verification (when ideal exists), whisker-vs-tapetum headline, fusion rule (`source_aware_review_cap`).

---

## Who consumes inspect reports?

Inspect is **human-facing triage**, not an automated downstream gate.

### Primary consumers

| Consumer | Artifact | Uses inspect? | Short-circuit impact |
|----------|----------|---------------|----------------------|
| **Golden-PR operator** | `tapetum-inspect.md` via `--all-pages --inspect` | **Yes** — load-bearing step 3 (`pr-golden-review.md:61-72`) | **None** — audit flags bypass short-circuit |
| **Corpus sighting / menu review** | `tapetum-inspect.md` | **Yes** — side-by-side whisker vs advisory (`inspect_report.py:8-17`, `menu.py:122`) | **None** when `--inspect` used |
| **Ad-hoc PID triage** | terminal + optional inspect | **Sometimes** | **High** if operator runs bare fleet PID then reads sidecar/inspect without audit flags |

### Related but distinct consumers (not `tapetum-inspect.md`)

| Consumer | Artifact | Reads short-circuited sidecars? | Impact |
|----------|----------|--------------------------------|--------|
| **Fleet operator rollup** | `whisker/llm/report-merged.md/json` | **Yes** — rebuilt every full run (`cli.py`, `fusion_report.py`) | **Low** — fusion uses metadata cap; counts correct; no localized quotes needed |
| **CI / `--gate`** | deterministic `whisker/det/` only | N/A | **None** — LLM lane never gates (`whisker/CLAUDE.md`) |
| **Dev-replay / holdout QA** | sidecar `defect_groups`, not inspect markdown | **Yes** when validating call elimination levers | **Medium** — recall on defect groups can drop while verdict histogram unchanged (`47-quality-equivalence.md:26`) |
| **`--fuse-only --inspect`** | regenerates inspect from existing sidecars | **Yes** | **High** — fleet sidecars lack unit evidence; inspect looks "complete=true" with empty findings |

### Non-consumers

- No package imports `inspect_report` in production paths beyond CLI persistence.
- Fusion engine reads sidecar JSON directly, not inspect markdown (`fusion.py`).
- Incremental fingerprint skip does not read inspect output.

---

## False-pass / false-fail hypotheses

**False-pass (inspect channel):** Operator runs nightly fleet, later `--fuse-only --inspect`, sees metadata `pass` or fusion `review` with `coverage_complete=True` and empty defect groups on a paper that would have had accepted unit findings under full cascade — clears triage without opening source pages 8/9 (PR #286 class). Merged verdict unchanged; **human** false-clear.

**False-fail (attention):** Metadata `review` + heading drift in metadata block sends reviewer into outline fixes while skipped unit checks would have pointed at table corruption (P1000R8 class). Verdict already `review`; wasted human attention, not verdict regression.

---

## Recommendation matrix

| Run type | Short-circuit | Rationale |
|----------|---------------|-----------|
| Nightly bare fleet (381 papers, incremental) | **Keep ON** | Saves ~1047 unit + ~15 page-esc calls (~1331 s upper bound); fusion identical; no inspect artifact; steady-state mostly fingerprint skip |
| Golden-PR / ideal validation | **Bypass** (`--all-pages --inspect`) | Full page audit + inspect report is the contract |
| Metadata-non-pass paper needing localized quotes | **Re-run PID with `--inspect`** (or `--exhaustive-units`) | Bypass without `--all-pages` still restores unit path |
| Pre-merge lever A/B (call graph change) | **Full cascade + dev-replay** | Verdict-only gates miss defect-group recall drops |
| Post-fleet human triage on sidecars | **Do not use `--fuse-only --inspect` alone** | Re-adjudicate flagged PIDs with audit flags |

### MODERATE alternative (not HEAD default)

Persona 17 Tier A+B: skip units on metadata **`fail` only**; on metadata **`review`**, run **1** highest-severity routed unit. Saves **847** calls vs **1047**, preserves one representative quote per review paper for inspect — at cost of **706** extra calls vs Tier C.

---

## What would change my mind

1. Any v11 default-fleet sidecar where stripping `unit_checks` changes `suggested_verdict` or `fusion.combined_verdict` (P145 count today: **0**).
2. Operator workflow proof that nightly fleet sidecars feed `--fuse-only --inspect` as primary triage without PID re-run — would flip nightly recommendation to **Tier B** or mandatory `--inspect` on metadata-non-pass subset.
3. Dev-replay recall drop on metadata short-circuit Tier C exceeding the −0.05 gate (`47-quality-equivalence.md:12`) — would require at least review-tier partial unit retention.

---

## References

- Short-circuit design + code map: `research/cold-run-10min/17-metadata-short-circuit-design.md`
- P145 replay quant: `research/tapetum-llm-speedup/17-metadata-short-circuit.md`
- Fusion-dead re-verify: `research/cold-run-10min/24-fusion-dead-reverify.md`
- Inspect consumer gap analysis: `research/llm-golden-verification-gap/personas/c19-downstream-consumer.md`
- Fleet vs exhaustive modes: `research/tapetum-llm-throughput/14-steelman.md:20`
- Golden-PR inspect contract: `.cursor/commands/pr-golden-review.md:61-72`
