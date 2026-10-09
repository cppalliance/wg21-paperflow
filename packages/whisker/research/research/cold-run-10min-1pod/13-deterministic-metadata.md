# 13 - Deterministic Metadata/Outline Diff

**Verdict:** A/B only — the metadata LLM call is structurally redundant with data `source_router` / `html_outline` already extract; ~471 s at S=16 is arithmetic-solid, but PDF outline noise and prompt-encoded lenience mean ship requires holdout parity, not code-only promotion.
**Confidence:** high

**Corpus constraint:** single `alliance-pod`, S_eff fixed at **16** (`00-baseline.md:23-24`). Dual-pod is out of scope.

---

## Executive answer

| Question | Answer |
|----------|--------|
| **Shippable today?** | **No.** AGGRESSIVE tier; 0/1 at HEAD (`cold-run-10min/10-impl-status-auditor.md:21,57`). |
| **Reject?** | **No.** Call class is a bounded structured diff, not generative judgment (`131-surya-model-sizing.md:10`). |
| **Recommendation** | **A/B only** — implement `compare_metadata_outline()`, replay 381 sidecars + 48-paper holdout; ship only if ≤5% metadata verdict drift **and** zero fused-verdict changes. |

---

## Savings (S=16)

| Input | Value | Evidence |
|-------|------:|----------|
| Metadata LLM calls / cold fleet | **377** | `tapetum-llm-speedup/00-baseline.md:22` (381 monolith − 4 HTML/text-only skips) |
| Mean per-call wall | **20 s** | `cold-run-10min-1pod/00-baseline.md:24` |
| Server slots | **16** | `cold-run-10min-1pod/00-baseline.md:23` |

```
Δwall = 377 × 20 / 16 = 471.25 s ≈ 471 s (~7.9 min)
N_rem = 2284 − 377 = 1907 calls
```

Stacking note: metadata-fail **short-circuit** (v11, ~−1341 s) is already landed and **orthogonal** — it skips units when metadata caps verdict; this lever **eliminates the metadata LLM itself** on all 377 papers (`131-surya-model-sizing.md:18`).

After both levers on a 3003 s baseline (no dual-pod):

```
3003 − 1341 (short-circuit) − 471 (deterministic metadata) ≈ 1191 s (~20 min)
```

Still above the 600 s goal; this lever is necessary but not sufficient (`cold-run-10min-1pod/00-baseline.md:27-28`).

---

## What the LLM call does today

| Step | Location | Behavior |
|------|----------|----------|
| Entry (PDF) | `pdf_judge.py:700-714` | After monolith; `source_metadata = page_units[0].text`, outline from font-size `heading_candidates` (`694-698`). |
| Entry (HTML) | `adjudicate.py:505-519` | First 3 outline headings + section-0 text (`505-511`); full outline list (`515`). |
| Compare | `unit_judge.py:231-273` | `run_metadata_outline_check` → one `run_judge_task` with `MetadataOutlineCheck`. |
| Candidate parse | `unit_judge.py:220-228` | `_candidate_structure_packet`: YAML block + ATX `hN: title` list. |
| Verdict fold | `pdf_judge.py:737-740`, `adjudicate.py:382-389` | `fail` forces fail; `review` demotes pass → review. |
| Fusion cap | `fusion.py:187-189` | `metadata_outline_check.verdict != pass` → `_source_aware_requires_review`. |
| Short-circuit | `pdf_judge.py:742-759`, `adjudicate.py:521-531` | Non-pass metadata skips units/page esc (unless audit flags). |

Schema (`models.py:262-295`): `title_matches`, `document_number_matches`, `date_matches`, `heading_drift[]`, `missing_sections[]`, `verdict` — all mechanically checkable.

---

## Deterministic assets already in tree

| Asset | Location | Reuse for metadata diff |
|-------|----------|-------------------------|
| HTML outline extract | `html_outline.py:128-147` | `extract_heading_outline` / `extract_heading_outline_normalized` |
| Secno strip | `html_outline.py:44-50`, `119-125` | `normalize_heading_text` — fixes PR #295 class when **both** sides normalized |
| HTML level+title diff | `source_router.py:286-312` | `route_html_units`: occurrence-aware title key + `source_level` vs `candidate_section.level` |
| PDF title-presence | `source_router.py:236-255` | Large-font lines missing as headings (signal only, **not** level compare) |
| TOC chrome filter | `source_router.py:163-164`, `286-289` | `_is_sanctioned_toc_title` |
| Candidate headings | `unit_judge.py:217-228` | `_MARKDOWN_HEADING_RE`, `_FRONT_MATTER_RE` |
| Front-matter keys | `gates.py:34-75` | `_split_front_matter`, `_REQUIRED_FRONT_MATTER_KEYS` — extend for `document`/`date` regex |
| Table compare (orthogonal) | `table_compare.py` | Not metadata; do not conflate |

**Gap:** HTML router already performs deterministic outline level diff inside routing (`source_router.py:298-312`). The metadata LLM **re-asks the same question** on HTML papers. PDF lane never compares ATX levels to source — only font-size candidate list vs candidate title keys (`pdf_judge.py:694-698`, `source_router.py:236-255`).

---

## What the LLM uniquely adds (must be encoded or accepted as loss)

These are **prompt rules**, not irreducible model capability (`131-surya-model-sizing.md:16`, `unit_judge.py:114-127`):

| LLM rule | Prompt anchor | Deterministic port |
|----------|---------------|-------------------|
| Ignore TOC entries, page numbers, running headers/footers | `unit_judge.py:119-120` | `_is_sanctioned_toc_title` + extend PDF page-1 chrome strip (dot-leader lines, suffixed page numbers — mirror `gates.py:132-184` TOC leak patterns) |
| "Cosmetic source formatting is not a defect" | `unit_judge.py:118` | Whitespace/case fold on compare keys (`source_router.py:35-41` `_text_key`); **do not** fuzzy-match document PID or title tokens |
| Map PDF title-block prose → YAML fields | `unit_judge.py:115-117`, `pdf_judge.py:699` | Regex extract `P\d{4}R\d+`, title line, date from page-1 text layer; compare to candidate YAML — ambiguous → **`review`**, not pass |
| Heading drift string format | `models.py:271-274` | Emit `f"{source_tag}:{title} -> h{cand.level}:{title}"` from level mismatch |
| Date format lenience | implicit in LLM behavior | **Risk:** ISO vs prose dates — policy: exact PID/title **fail**; date mismatch **review** only (`131-surya-model-sizing.md:24`) |
| PDF font-size outline noise | N/A (LLM lenient) | **Risk:** page-1 prose lines listed as `heading_candidates` → false `missing_sections` if strict (`131-surya-model-sizing.md:28`) — cap PDF-only missing-section at **review** unless document PID wrong |

**What LLM does *not* uniquely add (already false-clear or duplicate):**

- PR #282 heading level (`###` vs `<h2>`): LLM **false-cleared at 1.00** with outline injected (`golden-qa-gap/00-baseline.md:63`). Deterministic HTML router **would** catch (`source_router.py:298-312`). Replacing LLM improves recall on HTML; PDF level drift remains hard until PDF outline normalizer exists.
- PR #295 secno: both sides read `1. Abstract` without strip — **both** LLM and naive diff false-pass; **secno strip in `html_outline.py` fixes both** (`131-surya-model-sizing.md:10`).

**Net:** LLM adds fuzzy lenience on noisy PDF page-1 metadata, not detection power. Port = explicit rules + conservative defaults (`review` on ambiguity).

---

## Proposed design: `compare_metadata_outline()`

New pure function in `unit_judge.py` (or `metadata_compare.py` under `tapetum_llm/`), returning `MetadataOutlineCheck` without `run_judge_task`.

### Signatures

```python
def compare_metadata_outline(
    pid: str,
    source_metadata: str,
    source_outline: list[str],  # "h2: Title" or "page N, font X: Title"
    candidate_md: str,
    *,
    source_kind: Literal["pdf", "html"],
    html_outline: list[tuple[str, str]] | None = None,
) -> MetadataOutlineCheck: ...
```

### Algorithm (file:line anchors for each branch)

1. **Candidate packet** — reuse `unit_judge.py:220-228` (`_candidate_structure_packet`).
2. **Front matter**
   - Parse candidate YAML keys via `gates.py:37-75` pattern.
   - Extract from `source_metadata`: document PID regex, title (first substantial line or `Title:` field), date if present.
   - `document_number_matches`: case-insensitive PID equality — mismatch → **`fail`**.
   - `title_matches`: normalized token-set overlap ≥ threshold or substring — mismatch → **`review`** (not fail unless empty/wrong paper).
   - `date_matches`: exact normalized ISO if both sides ISO; else **`review`** on mismatch, **`pass`** if candidate date absent.
3. **Outline — HTML** (`source_kind == "html"`)
   - `outline = html_outline or extract_heading_outline_normalized(html_source)` (`html_outline.py:138-147`).
   - For each `(source_tag, title)` in order with occurrence index (`source_router.py:285-312`):
     - Skip `_is_sanctioned_toc_title(title)` (`source_router.py:163-164`).
     - Match candidate section by `_text_key(normalize_heading_text(title))` + occurrence.
     - Level mismatch → append to `heading_drift`; missing → `missing_sections`.
4. **Outline — PDF**
   - Parse `source_outline` lines from `pdf_judge.py:694-698` format OR accept pre-parsed `(level_hint, title)` from font size (map font rank → h1/h2 heuristic, or treat as unordered title set).
   - Compare candidate ATX levels for matched titles (same occurrence logic as HTML).
   - Unmatched font lines: **`review`** via `missing_sections`, not **`fail`**, unless title is in a curated "structural heading" set (all-caps short lines).
5. **Verdict fold** (mirror `models.py:283-295`)
   - Any `fail` field (document PID) → `verdict=fail`.
   - Any drift/missing/date/title flag → `verdict=review`.
   - Else `pass`.
6. **Wire-in**
   - `pdf_judge.py:700-714`: replace `await run_metadata_outline_check(...)` with `compare_metadata_outline(...)` behind `--deterministic-metadata` flag initially.
   - `adjudicate.py:512-519`: same; pass `extract_heading_outline_normalized` output.
   - Keep `run_metadata_outline_check` for A/B shadow mode (log both, ship deterministic only after gate).

### Tests to add

| Case | Basis |
|------|-------|
| Clean HTML outline | `test_unit_judge.py:427-451` |
| TOC chrome ignored | `test_unit_judge.py:453-473` + `_is_sanctioned_toc_title` |
| Secno normalized match | PR #295 fixture |
| Level drift HTML | `source_router.py:298-312` signal → metadata `heading_drift` |
| Wrong document PID | hard fail |
| PDF noisy page-1 | cap at review (`131-surya-model-sizing.md:28`) |

---

## A/B plan (required before ship)

### Phase 0 — Shadow (no fleet behavior change)

1. Implement `compare_metadata_outline()`.
2. On fleet run with `TAPETUM_METADATA_SHADOW=1`, run **both** deterministic and LLM; persist `metadata_outline_check_det` beside existing field in sidecar.
3. Diff script over `whisker/llm/*.tapetum.json`:
   - `verdict` agreement rate
   - field-level deltas on `heading_drift`, `missing_sections`, booleans
   - recomputed `suggested_verdict` + `fuse_verdicts` (`pdf_judge.py:737-740`, `fusion.py:187-189`)

**Stop/go:** If **>5%** papers disagree on `metadata_outline_check.verdict` **or** **any** fused advisory verdict changes vs LLM path → **do not ship** deterministic-only (`131-surya-model-sizing.md:32`).

### Phase 1 — Holdout quality gate

| Set | N | Purpose |
|-----|--:|---------|
| Dev-replay golden PRs | 9 | #282–#286, #290, #293–#295 — known defect classes |
| Active holdout | 48 | Human-verified anchors (`cold-run-10min/25-quality-gate-protocol.md`) |
| Full fleet shadow | 381 | Regression + agreement rate |

Per paper record: metadata verdict (det vs LLM), whether deterministic **caught** a known golden defect LLM missed (expect HTML heading level ↑), whether deterministic **false-fails** clean papers.

**Pass criteria (all required):**

1. Verdict agreement ≥ **95%** on 381 shadow run.
2. **Zero** fused `combined_verdict` changes vs LLM control on holdout+replay.
3. Deterministic **≥ LLM** recall on HTML heading-level defects (PR #282/#295).
4. PDF false-fail rate ≤ **2%** on clean papers (review demotion acceptable; fail not).

### Phase 2 — Ship

1. Default `compare_metadata_outline()`; remove LLM call from hot path.
2. Bump `_LANE_VERSION` (`cli.py:119-122`).
3. Drop `metadata` from prompt fingerprint / `--force` class list (`cli.py:505-512` contract).
4. Optional: keep LLM metadata behind `--llm-metadata-audit` for `--inspect` only.

### Rollback

Flag `--llm-metadata` restores `run_metadata_outline_check` (`unit_judge.py:231-273`).

---

## False-pass hypothesis

Deterministic date normalization too loose (`January 15, 2024` vs `2024-01-15` both pass) while a wrong **year** slips through token overlap — advisory pass on wrong revision date. Mitigation: PID + title hard checks; date mismatch always **review** unless byte-equal after ISO parse.

Deterministic PDF outline treats body subsection promoted to ATX as `missing_sections` but caps at **review** — operator ignores advisory review on clean papers (noise, not silent pass).

---

## False-fail hypothesis

Strict PDF page-1 `source_metadata = page_units[0].text` (`pdf_judge.py:699`) includes abstract prose; deterministic parser treats lines as missing YAML fields → **fail** on `document_number_matches` when PID appears only on page 2. Mitigation: scan first **N** chars / lines for PID regex before fail; mirror LLM lenience with **review**.

Font-size `heading_candidates` include non-headings → spurious `heading_drift` → metadata **review** → fusion cap (`fusion.py:187-189`) on clean papers that LLM passes. Mitigation: PDF missing-section/drift capped at **review** not **fail**; require PID mismatch for **fail** (`131-surya-model-sizing.md:28`).

---

## What would change my mind

- Shadow run shows **≥98%** verdict agreement **and** deterministic catches PR #282 on HTML without new false-fails → upgrade to **shippable** without further holdout delay.
- Shadow run shows **>5%** verdict drift **or** any holdout fused-verdict change → **reject** deterministic replacement; keep LLM or train surya-style ~66M classifier on sidecar labels (`131-surya-model-sizing.md:32`).
- Fresh cold run at HEAD + deterministic metadata ≤ **1250 s** at S=16 with zero holdout regressions → confirms arithmetic contribution toward 600 s target (still needs verdict-first / other levers).

---

## Implementation checklist (whisker-only)

| # | Task | Anchor |
|---|------|--------|
| 1 | Add `compare_metadata_outline()` | new module or `unit_judge.py` after `:228` |
| 2 | HTML outline branch | `source_router.py:286-312`, `html_outline.py:138-147` |
| 3 | PDF outline branch | `pdf_judge.py:694-698`, `normalize_heading_text` |
| 4 | Front-matter extract | extend `gates.py:60-75` patterns |
| 5 | CLI flag + shadow | `cli.py`, env `TAPETUM_METADATA_SHADOW` |
| 6 | Sidecar field | `pdf_judge.py:1098`, `models.py:357` |
| 7 | Tests | `tests/test_unit_judge.py` + holdout fixtures |
| 8 | `_LANE_VERSION` bump | `cli.py:119-122` |

**Package boundary:** all changes under `packages/whisker/` only.
