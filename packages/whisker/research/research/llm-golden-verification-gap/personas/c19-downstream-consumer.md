# c19 - Downstream consumer advocate

**Verdict:** usable-with-conditions (The lane emits conservative `review` and persists rich sidecar JSON, but the surfaces a golden-PR operator actually reads — deterministic pass, inspect metadata `pass`, high confidence, empty defect groups — contain zero actionable pointers to the verified blockers on pages 8/9 or the four secno H2s; only expert sidecar forensics or the manual fidelity diff would find them.)
**Confidence:** high

## Findings

- [CRITICAL] PR #286 operator screen: nothing on the default rendered path names pages 8/9 or poll-table corruption. Evidence: deterministic `pass`, all six gates green, QA 100 (`00-baseline.md:41-42`, `PR286-LLM-FALSE-CLEAR.md:131-133`); default `whisker` terminal hides passes (`report.py:298-299`, `report.py:314-315`); LLM `review` conf 0.98 with metadata/outline `pass` (`00-baseline.md:46-47`); inspect shows `Unit coverage: complete=False, checked=5, unchecked=4` but **does not print** `unchecked_unit_ids` (`inspect_report.py:184-195` — counts only, IDs live in sidecar `unit_coverage.unchecked_unit_ids`: pages 5, 6, 8, 9 per baseline); `defect_groups` section omitted when empty (`inspect_report.py:198-199`); risk signals capped at five with truncated detail (`inspect_report.py:225-238`, baseline nine `heading_drift` signals, none table-typed). Impact: an operator following `/pr-golden-review` Step 3 without Step 2 sees green deterministic + outline pass + “4 unchecked” with no “go to pages 8/9 table headers” instruction. Answer-class: 2, 5.

- [CRITICAL] PR #295 operator screen: nothing points at the four `span.secno` H2 labels. Evidence: metadata/outline `pass`, empty `heading_drift` (`00-baseline.md:62-64`, `html_outline.py:66-81` collects secno text so source and candidate both read `1. Abstract`); inspect renders `heading drift: none` (`inspect_report.py:175`); checked units were `section:1` (false “candidate missing” for bikeshed chrome) and `section:6` (script-polluted recall 0.0437), not sections bearing secno H2s (`00-baseline.md:66-73`); zero defect groups, zero evidence dispositions. Deterministic lane shows `review` only from advisory `ref_nid` 0.8081 (`PR286-LLM-FALSE-CLEAR.md:168-169`), not secno. Impact: metadata/outline `pass` reads as “headings verified” while the golden-contract violation is invisible on every rendered surface. Answer-class: 1.

- [HIGH] Actionability audit — rendered lane output vs operator utility (PR #286 / PR #295). Evidence: classifications from `inspect_report.py`, `report.py`, `fusion_report.py`, baseline runtime.

  | Output piece | PR #286 | PR #295 | Class |
  |---|---|---|---|
  | Deterministic verdict + gates | `pass`, no flags | `review` (ref_nid advisory only) | **Mood** / unrelated pointer |
  | Terminal `whisker` line | Hidden (pass) | `ref_nid` low flag | Mood |
  | LLM `suggested_verdict` + conf 0.98/1.0 | `review` | `review` | Mood (“something”) |
  | Metadata/outline block | `pass`, drift none | `pass`, drift none | **False clearance** |
  | Unit coverage counts | incomplete, 4 unchecked | incomplete, 1 unchecked | Mood (no WHERE) |
  | Risk signals (≤5 shown) | `heading_drift` prose | title/subtitle/script noise | Mood / false pointer |
  | Defect groups table | absent (0) | absent (0) | — |
  | Evidence dispositions | 1 ambiguous (page 13 false claim) | absent (0 claims) | Misleading (looks like verification ran) |
  | Fusion / terminal rule | `source_aware_review_cap` | same | Mood |
  | `LLM reasoning` narrative | page-13 headings, not tables | triage prose | Unverified mood |

  Impact: no rendered field is an **actionable pointer** (“open candidate lines 382–433” / “strip secno on H2s 1–4”). Answer-class: 4, 5.

- [HIGH] `inspect_report.py` drops the fields an operator needs for low-recall triage. Evidence: sidecar persists `checked_unit_ids`, `unchecked_unit_ids`, `unit_checks`, `risk_signals` (full list), `page_screen`, `textlayer_diff`, per-paper `fusion` (`pdf_judge.py:551-555`, `unit_judge.py:325-334`); inspect renders only coverage **counts** (`inspect_report.py:190-195`), first five risk signals (`inspect_report.py:231-238`), no unit-check verdict table, no fusion subreason, no “gates not run” manifest. `format_report` fusion rollup is header-only (`inspect_report.py:339-346`). Impact: even a diligent reviewer reading `tapetum-inspect.md` cannot see that `page:8`/`page:9` or secno sections were routed-but-skipped without opening raw JSON. Answer-class: 5.

- [HIGH] Proposed output contract for a **useful low-recall lane** (consumer requirements, not implemented). Always render: (1) **Routed-units table** — every `unit_id`, signal type(s), severity, checked/unchecked/failed/no-packet, one-line selection or displacement reason (cap overflow, missing packet, passed clean); (2) **Coverage vs detection banner** — `review` because `coverage_incomplete` vs `verified_defects` with distinct subreasons (improvement-bugs §P1); (3) **Deterministic gap manifest** — explicit list of contract checks the deterministic lane and metadata/outline did **not** run (table cells, secno strip, list cardinality, rendered-Markdown semantics); (4) **Claim accounting** — `generated_claims`, `accepted`, `refuted`, `abstained`, never conflate zero dispositions with clean verification; (5) **Per-unit one-line outcome** from `unit_checks` even when `defect_groups` is empty. Impact: operators could treat LLM lane as a checklist (“these units unchecked → human must open source pages 8–9”) without parsing sidecar JSON. Answer-class: 5.

- [MED] Trace/debug artifacts: HTML path partially helps; PDF path fails the CLAUDE.md trace contract on the incident paper. Evidence: review command `--trace --debug` (`PR286-LLM-FALSE-CLEAR.md:120`); PR #286 PDF trace **absent** — `judge_pdf_extraction` has no `trace` parameter, CLI forwards debug only (`cli.py:1114-1118`, `pdf_judge.py:567-573`, baseline `PR286-LLM-FALSE-CLEAR.md:144`); debug transcript **present** at `<pid>.debug.tapetum_llm.md` and would log unit LLM I/O for pages 1,2,3,4,13 only, not a concise “pages 8/9 displaced” summary. PR #295 text lane forwards trace (`cli.py:1173-1178`, `adjudicate.py:679-689`) — pipeline steps 0–3 would confirm triage/decide ran, but trace summarizes step outputs, not golden-contract secno rule; debug shows prompts with unnormalized outlines (`html_outline.py:66-81`), which explains the miss only to someone who already knows the contract. Impact: observability does not substitute for inspect rendering; PDF trace gap removes the fastest post-run audit on the table blocker paper. Answer-class: 2, 5.

- [LOW] `/pr-golden-review` correctly treats manual ideal-vs-source diff as load-bearing (`.cursor/commands/pr-golden-review.md:17`, `:41-47`), but Step 3 prose overstates what the operator sees from LLM output (“compares heading outline extracted from the source”, `:52-56`) — contradicted by PR #295 metadata `pass` with secno retained. Impact: operators trusting Step 3 wording without Step 2 will false-clear; whisker output is advisory triage, not golden verification, but the command text does not warn that inspect omits unchecked unit IDs. Answer-class: 5.

## False-pass hypothesis

Golden-PR reviewer runs Step 3 only on PR #295: reads inspect `Metadata/outline check: pass`, `heading drift: none`, deterministic gates green, LLM `review` with zero defect groups and interprets fusion as “LLM checked headings, found nothing structural” — merges while four H2s retain `1.`–`4.` secno labels (`00-baseline.md:59-64`). The inspect metadata block is an active false-clearance signal.

## False-fail hypothesis

PR #286 operator sees LLM `review` conf 0.98, one `ambiguous` evidence row for a refuted page-13 heading claim (`00-baseline.md:50-51`), and four unchecked units — spends review time on page-13 heading noise and “incomplete coverage” while the six-instance poll-table blocker on pages 8/9 (never named in inspect) remains unexamined. False-fail on reviewer attention, not verdict.

## What would change my mind

One shipped `tapetum-inspect.md` excerpt from a replay at baseline hashes showing a **Routed units** table with `page:8`/`page:9` rows marked `unchecked (cap displacement)` and a banner `review: coverage_incomplete — not verified_defects`, plus PR #295 rows for secno-bearing sections marked `not_checked (outline normalization not applied)`, without the operator opening sidecar JSON — proving the consumer contract closes the pointer gap.
