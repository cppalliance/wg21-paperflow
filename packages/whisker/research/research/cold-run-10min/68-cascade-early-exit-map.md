# 68 - Cascade Early-Exit Map (in-paper call order)

**Verdict:** usable
**Confidence:** high

Code anchors at HEAD: `cli.py`, `pdf_judge.py`, `unit_judge.py`, `adjudicate.py`.
Prior: `17-metadata-shortcircuit-design.md`, `00-baseline.md` (44.6% unit-call elimination).

**Scope:** Exact **per-paper serial** LLM call order and every branch that skips
later calls. Cross-paper concurrency (`cli._run`, default c=32) is orthogonal;
within one paper all LLM calls are serial (D11 via `judge_task.run_judge_task`).

---

## Lane routing (CLI)

| Condition | Lane | Entry |
|-----------|------|-------|
| `source == pdf` AND `judge_agent` resolved AND NOT `--text-only` | PDF-text-layer | `pdf_judge.judge_pdf_extraction` |
| else (HTML, or `--text-only`, or judge service missing) | Markdown text | `adjudicate.adjudicate_paper` |

Both lanes optionally append **ideal verification** after the lane completes
(`cli._attach_ideal` → `ideal_verify.verify_against_ideal`) when a tomd golden
ideal exists for the PID.

---

## CLI-level exits (before in-paper LLM chain)

| # | Gate | Location | Skips |
|---|------|----------|-------|
| C0 | `--fuse-only` | `cli._run:1044` | Entire adjudication batch |
| C1 | Empty PID list | `cli._run:1067` | Batch |
| C2 | Incremental fingerprint match | `cli._adjudicate_one:1257–1301` | **All** in-paper LLM calls for that paper |
| C3 | `--review-all` candidate filter | `cli._run:1052–1054` + `adjudicate.select_candidates` | Papers not selected never enter `_adjudicate_one` |

**C2 details:** Auto-on full fleet run (`incremental = not --force`). Explicit PIDs /
`--review-all` require `--incremental`. Superset skip: existing sidecar with
higher `coverage_mode` satisfies lower-rank request. Error tombstones skip unless
`--retry-errors`.

---

## PDF lane: ordered in-paper LLM calls

**File:** `pdf_judge.judge_pdf_extraction` (568–1102)
**Agent:** single `judge_agent` (deep/default slot), shared guard tag per paper.

### Pre-LLM (deterministic, always)

| Step | Symbol | Early exit? |
|------|--------|-------------|
| P0 | Extract text layer, context budget check | **Hard fail** (`PdfLaneError`) if over budget; no LLM |
| P1 | `screen_pages` | No LLM; trivial pages (`tokens < PAGE_MIN_TOKENS`) marked `skipped=True`, never escalated |

### LLM call sequence (serial)

| Order | Call | Function | Always? |
|-------|------|----------|---------|
| **1** | Monolith whole-document judge | `run_judge_task` → `PdfJudgment` | **Yes** |
| **2** | Metadata + outline check | `unit_judge.run_metadata_outline_check` | **Yes** |
| **3..3+N** | Page escalation (0–N) | `_escalate_page` → `PageJudgment` | **Conditional** |
| **4..4+M** | Unit checks (0–M) | `unit_judge.run_unit_checks` → `_check_one_unit` × M | **Conditional** |
| **5** | Ideal verification | `ideal_verify.verify_against_ideal` | **Conditional** (CLI, ideal file exists) |

### Early-exit branches (PDF)

| After step | Condition | Lines | Skipped calls | Verdict note |
|------------|-----------|-------|---------------|--------------|
| **E-PDF-1** | `metadata_check.verdict != "pass"` AND NOT `all_pages` AND NOT `exhaustive_units` | 742–759, 798 guard | **All** page escalations + **all** unit checks | Largest fleet savings (~44.6% of LLM calls). Sidecar `unit_coverage.mode = "metadata_short_circuit"`. |
| **E-PDF-2** | `len(flagged_pages) > MAX_PAGE_ESCALATIONS` (5) | 803–816 | Page-escalation LLM calls (0 made) | Verdict capped `pass → review` on screen evidence alone |
| **E-PDF-3** | `len(flagged_pages) == 0` | 802, 818 loop empty | Page-escalation calls | — |
| **E-PDF-4** | NOT `all_pages` AND `risk_signals` empty | 934–945 | `run_unit_checks` never invoked | Monolith + metadata only (2 calls) |
| **E-PDF-5** | `run_unit_checks` returns `None` | 317–354 in `unit_judge` | Unit loop | No signals and no `required_unit_ids` |
| **E-PDF-6** | Quota: routed mode caps at `MAX_UNIT_CHECKS` (5) | 378–381, 402 loop | Unchecked risky units (not LLM-skipped mid-loop; never scheduled) | `exhaustive_units` / `--inspect` removes cap |
| **E-PDF-7** | Unit with empty `unit_text_map` entry | 405–411 | That unit's `_check_one_unit` | Required units → `unchecked`; optional → skip |

**Audit bypass for E-PDF-1:** `--all-pages`, `--exhaustive-units`, `--inspect`
(wired via `cli` `exhaustive_units=` at 1326–1328).

**Typical call counts (PDF, no ideal):**

| Scenario | LLM calls |
|----------|-----------|
| Metadata non-pass + fleet default | **2** (monolith + metadata) |
| Metadata pass, clean screen, no router signals | **2** |
| Metadata pass, 2 flagged pages, 3 quota units | **2 + 2 + 3 = 7** |
| `--all-pages`, N physical pages | **2 + 0..5 esc + N unit** (esc still capped at 5) |

---

## Text lane: ordered in-paper LLM calls

**File:** `adjudicate.adjudicate_paper` → pipeline hooks (`_build_hooks`, 642–653)
**Agents:** `fast` (triage + source checks), `deep` (tier-2 adjudicate)

### Pipeline steps (serial)

| Order | Step | Hook | LLM? |
|-------|------|------|------|
| **0** | Select | `_custom_select` | No (load MD, strip binary, read whisker sidecar) |
| **1** | Triage (tier 1) | `_custom_triage` | **Yes** (1 or K calls) |
| **2** | Adjudicate (tier 2) | `_custom_adjudicate` | **Conditional** (0 or 1) |
| **3** | Decide | `_custom_decide` | Mixed (post-process + source checks) |

### Tier-1 triage call shape

| Condition | Calls |
|-----------|-------|
| `len(paper_md) <= MAX_PAPER_MD_CHARS` | **1** `run_agent` (fast) |
| Oversized (chunked on H2) | **K** serial `run_agent` (one per chunk), aggregated → `state.chunked=True`, `state.partial` may be set |

### Tier-2 adjudicate early exits

| ID | Condition | Lines | Skips |
|----|-----------|-------|-------|
| **E-TXT-1** | `state.tier1 is None` | 292–293 | Tier-2 call |
| **E-TXT-2** | `state.chunked` (oversized paper) | 298–299 | Tier-2 call (413 avoidance; tier-1 aggregate stands) |
| **E-TXT-3** | `_escalation_signals(tier1)` empty | 301–303 | Tier-2 call |

**Escalation signals** (264–287): axis conflict (pass+fail axes), ungrounded
evidence (grounding dropped quotes), confidence in ambiguous band
(`CONFIDENCE_AMBIGUOUS_LO..HI`).

### Decide-step source checks (after tier-1/2, still in-paper)

Branch on source kind inside `_custom_decide` (377–381):

#### HTML path: `_run_html_unit_checks` (486–554)

| Order | Call | Always? |
|-------|------|---------|
| H1 | `run_metadata_outline_check` | **Yes** (HTML) |
| H2..H2+M | `run_unit_checks` → `_check_one_unit` × M | **Conditional** |

| Early exit | Condition | Lines | Skips |
|------------|-----------|-------|-------|
| **E-HTML-1** | `metadata_outline_check.verdict != "pass"` AND NOT `state.exhaustive` | 523–531 | **All** unit checks |
| **E-HTML-2** | `section_units` empty | 533–534 | Unit checks |
| **E-HTML-3** | `route_html_units` → no `risk_signals` | 539–540 | Unit checks |
| **E-HTML-4** | Same quota/cap as PDF via `run_unit_checks` | — | Unchecked units beyond `MAX_UNIT_CHECKS` unless exhaustive |

#### PDF-on-text-lane path: `_run_pdf_unit_checks` (557–639)

Used when `--text-only` or judge service missing. **No metadata call** on this path.

| Order | Call | Always? |
|-------|------|---------|
| P-T1 | Deterministic `route_pdf_units` + `compare_pdf_tables` | No LLM |
| P-T2..P-T2+M | `run_unit_checks` | **Conditional** |

| Early exit | Condition | Lines | Skips |
|------------|-----------|-------|-------|
| **E-PTXT-1** | Not a PDF source | 566–567 | Entire PDF unit block |
| **E-PTXT-2** | Page-unit extraction fails | 571–573 | Unit checks (warning, return) |
| **E-PTXT-3** | No `risk_signals` after routing (+ table diffs) | 624–625 | Unit checks |

#### Text lane ideal verification

Same as PDF: **CLI** `_attach_ideal` after `adjudicate_paper` returns (1420–1422).

**Typical call counts (text, no ideal):**

| Scenario | LLM calls |
|----------|-----------|
| Small paper, confident tier-1, HTML metadata fail | **1 + 1 = 2** (triage + metadata; units skipped) |
| Small paper, no escalation signals, no HTML/PDF unit path triggers | **1** |
| Escalation fires, HTML metadata pass, 3 quota units | **1 + 1 + 1 + 3 = 6** (triage + tier2 + metadata + units) |
| Chunked oversized | **K** triage only (no tier-2) + source checks |

---

## unit_judge: internal call order

### `run_metadata_outline_check` (231–273)

- **One LLM call per invocation**, always when caller reaches it.
- No internal early exit.

### `run_unit_checks` (317–528)

| Phase | Behavior | Early exit |
|-------|----------|------------|
| Entry | `risk_signals` empty AND `required_unit_ids` empty | **Return `None`** — zero LLM calls |
| Selection | `_select_units_with_quotas` + required promotion | Units beyond cap never enter loop |
| Loop | Serial `_check_one_unit` per selected `unit_id` | Skip iteration if no source packet (405–411) |
| Post | `verify_unit_evidence`, defect aggregation | No LLM |

Each `_check_one_unit` (770–808): one `run_judge_task` → `UnitCheck`.

---

## Master ordered list (LLM calls only)

Legend: **→** serial; `(?)` = may be skipped by early exit.

### PDF lane (primary fleet path)

```
C2 incremental skip (?)
→ [1] monolith PdfJudgment
→ [2] metadata/outline MetadataOutlineCheck
→ E-PDF-1 metadata short-circuit (?)
    → if NOT short-circuited:
        → [3..3+N] page escalation PageJudgment × N  (N ≤ 5, E-PDF-2/3)
        → E-PDF-4/5/6/7
        → [4..4+M] unit check UnitCheck × M  (M ≤ 5 routed, or all pages)
→ [5] ideal verification (?)
```

### Text lane

```
C2 incremental skip (?)
→ [1] tier-1 triage Adjudication × (1 or K chunks)
→ E-TXT-1/2/3 (?)
    → [2] tier-2 adjudicate Adjudication (?)
→ _custom_decide (deterministic grounding/demotion)
→ HTML only:
    → [3] metadata/outline MetadataOutlineCheck
    → E-HTML-1/2/3/4 (?)
    → [4..4+M] unit check UnitCheck × M (?)
→ PDF text-only:
    → E-PTXT-1/2/3 (?)
    → [3..3+M] unit check UnitCheck × M (?)
→ [last] ideal verification (?)
```

---

## Early-exit summary table

| ID | Layer | Trigger | Calls eliminated | Safe for verdict? |
|----|-------|---------|------------------|-------------------|
| C2 | CLI | Fingerprint match | Entire paper | Yes (unchanged inputs) |
| E-PDF-1 | pdf_judge | Metadata ≠ pass (fleet) | Page esc + all units | Yes (verified zero drift, P145) |
| E-PDF-2 | pdf_judge | >5 flagged pages | Page esc LLM | Partial (screen-only demotion) |
| E-PDF-3 | pdf_judge | 0 flagged pages | Page esc LLM | Yes |
| E-PDF-4 | pdf_judge | No router signals | Unit checks | Yes (monolith stands) |
| E-PDF-5 | unit_judge | No signals + no required | Unit loop | Yes |
| E-PDF-6 | unit_judge | Quota cap | Unchecked units | Coverage incomplete → review cap |
| E-TXT-2 | adjudicate | Chunked paper | Tier-2 | By design (no full-doc tier-2) |
| E-TXT-3 | adjudicate | No escalation signals | Tier-2 | Yes (confident tier-1) |
| E-HTML-1 | adjudicate | Metadata ≠ pass (fleet) | All units | Yes (same algebra as E-PDF-1) |
| E-HTML-2/3 | adjudicate | No sections / no signals | Unit checks | Yes |
| E-PTXT-3 | adjudicate | No PDF risk signals | Unit checks | Yes |

**Not early exits (demotions only, post-LLM):** deterministic recall/nid floors
(pdf_judge 766–777), grounding drops, severity-aware decide (adjudicate 314–373),
incomplete all-pages coverage (pdf_judge 1040–1048).

---

## Call-count arithmetic (fleet v10 baseline)

| Metric | Value |
|--------|-------|
| Papers | 381 |
| LLM calls (pre-short-circuit accounting) | ~2284 (~6.0/paper) |
| Metadata short-circuit eligible | 232 papers metadata ≠ pass |
| Unit calls saved | 1047 (44.6%) |
| Page-esc calls saved (PDF subset) | ~15 |
| Minimum PDF paper (short-circuited) | 2 calls |
| Maximum PDF paper (routed, no ideal) | 2 + 5 + 5 = 12 |
| Maximum PDF `--all-pages` | 2 + 5 + page_count |

---

## False-pass / false-fail hypotheses

**False-pass:** Short-circuit on metadata **review** skips unit checks that could
surface body-level defects invisible to metadata/outline comparison. Mitigated by
monolith call still running; risk is localized semantic corruption with clean
front matter.

**False-fail:** Page-screen cap (E-PDF-2) demotes to review without scoped LLM
confirmation when >5 pages flag; human must inspect screen evidence.

---

## What would change this map

- Reordering metadata before monolith (would change prefix-cache layout, not
  early-exit IDs).
- Tier-2 escalation for chunked text papers (new call slot after E-TXT-2 removal).
- Per-unit incremental fingerprints (`30-per-unit-fingerprint.md`) would add
  CLI-level C2 granularity inside the unit loop.
