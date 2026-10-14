# 17 - Claim-Schema Designer

**Verdict:** usable-with-conditions (+ a minimal per-quote `VerifiedClaim` record can extend `grounded_evidence` without touching LLM `output_type` schemas, but only if `reason` stops asserting candidate absence and new fields are additive under `schema_version` 4)
**Confidence:** high

## Schema comparison

| Dimension | langextract `Extraction` | unstructured `Element` | whisker `EvidenceSpan` / sidecar | whisker `PdfJudgment` / `PageJudgment` |
| --- | --- | --- | --- | --- |
| Granularity | Model extraction unit | Document element (paragraph/table) | Per-quote evidence span | Paper or page verdict + quote list |
| Quote text | `extraction_text` | `text` | `quote` | `missing_content[]` (raw strings) |
| Class / axis | `extraction_class` | `category` | `axis` (`FidelityAxis`) | implicit `structure` in PDF lane |
| Source locate | `char_interval` + `alignment_status` | `metadata.coordinates`, `page_number` | `status` (`exact`/`fuzzy`), `start`/`end` (markdown lane only) | source via `ground_spans` / `ground_page_quotes` on PDF text |
| Candidate locate | none | none | none in PDF lane; markdown lane grounds into candidate | none (model asserts absence; no post-hoc check) |
| Match quality | `AlignmentStatus` enum (4 tiers) | `detection_class_prob`, `routing_score` | binary keep/drop + `exact`/`fuzzy` | `confidence` float only |
| Ungrounded signal | `char_interval is None` | N/A (element always has text) | increment `ungrounded_dropped` | drop quote, no structured reason |
| Ambiguity | implicit (fuzzy tier) | `routing` + `routing_score` | none | none |
| Provenance | `attributes`, `extraction_index` | `enrichment_origins`, `detection_origin` | `reason` string (human) | `reasoning` (60 words) |
| Decision coupling | downstream consumer filters `char_interval is None` | eval metrics per element type | adjudicate demotion on dropped evidence | sidecar `reason` falsely couples source+candidate (`pdf_judge.py:401-404`) |

**Portable patterns:** langextract's `char_interval is None` reject signal and graded `alignment_status` (`langextract/core/data.py:43-47`, `63-92`); unstructured's separation of detection confidence from categorical grade (`elements.py:168`, `204-206`); olmOCR/LitRAG bidirectional locate + tri-state (`05-web.md:14-18`, `157-159`); whisker `facts.py` `present`/`absent` with `max_diffs` as the candidate oracle shape (`facts.py:324-326`, `441-444`).

**Non-portable:** unstructured element taxonomy (whisker outputs markdown, not `Element` trees); langextract `MATCH_LESSER` / LCS fuzzy spans (whisker research rejects wrong-span risk, `langextract/20-grounding-alignment-specialist.md:18`); expanding `PdfJudgment` / `PageJudgment` with verification fields (violates D6 stability floor and mixes LLM assertion with deterministic proof).

## Proposed minimal record: `VerifiedClaim`

One dict per quote, emitted in `grounded_evidence` (text lane) and PDF-lane sidecars. Deterministic post-processing only; LLM schemas unchanged.

```python
# Research contract (not implemented). All fields optional except quote on read path.
VerifiedClaim = {
    "quote": str,                    # verbatim LLM quote (existing)
    "axis": str,                     # existing; default "structure" in PDF lane
    "reason": str,                   # human summary (existing); MUST NOT assert absence alone

    # --- new in schema_version 4 (additive) ---
    "source_status": str,            # ungrounded | exact | fuzzy
    "candidate_status": str,         # unverified | present | absent | ambiguous
    "source_span": {"start": int, "end": int} | None,
    "candidate_span": {"start": int, "end": int} | None,
    "match_score": float | None,     # 0.0-1.0; partial_ratio or alignment score used
    "reason_code": str,              # machine enum (below)
    "ambiguity": bool,               # True when candidate_status == "ambiguous"
    "decision_effect": str,          # machine enum (below)
}
```

### Field semantics

| Field | Values | Meaning |
| --- | --- | --- |
| `source_status` | `ungrounded` / `exact` / `fuzzy` | Result of locate in PDF text (or page text for `[pN]` quotes). Maps from `GroundedSpan.status` (`grounding.py:46-47`, `52-60`) or drop. |
| `candidate_status` | `unverified` / `present` / `absent` / `ambiguous` | Result of locate in `tomd_md`. `unverified` = pre-v4 sidecars or verifier skipped. `present` refutes LLM missing claim (`02-candidate-absence.md:21`). |
| `source_span` | char interval or `null` | PDF-text offsets when `source_status == exact`; `null` for fuzzy/ungrounded (langextract parity: interval only when exact). |
| `candidate_span` | char interval or `null` | Markdown offsets when candidate locate is exact; `null` for fuzzy/ambiguous/absent. |
| `match_score` | `0.0`–`1.0` or `null` | Best candidate-side score at decision time (e.g. `partial_ratio/100` or `_present_within` alignment). `null` when `source_status == ungrounded`. |
| `reason_code` | see enum | Why this classification, independent of verdict prose. |
| `ambiguity` | bool | Denormalized flag for consumers that do not parse `candidate_status`. |
| `decision_effect` | see enum | What the verifier did to verdict/evidence aggregation. |

### `reason_code` (minimal enum)

| Code | When |
| --- | --- |
| `llm_source_hallucination` | `source_status == ungrounded` |
| `verified_missing` | source grounded, `candidate_status == absent` |
| `false_missing_present` | source grounded, `candidate_status == present` |
| `ambiguous_overlap` | source grounded, `candidate_status == ambiguous` |
| `sanctioned_front_matter` | present after YAML/body mapping (`pdf_judge.py:132-136`) |
| `sanctioned_toc_removed` | quote is TOC/furniture (`pdf_judge.py:137-146`) |
| `sanctioned_dehyphenation` | present only after dehyphenation/reflow |
| `sanctioned_markup` | present inside wording/figure sanctioned surface |
| `fuzzy_source_only` | source `fuzzy`, candidate not exact (cap at review) |

Start with these nine; extend only with replay evidence. Do not encode gate names or flag prose (`03-api-contract-design.md:12`).

### `decision_effect` (minimal enum)

| Effect | When |
| --- | --- |
| `drop_quote` | `source_status == ungrounded` (existing `ungrounded_dropped`) |
| `retain_missing` | `candidate_status == absent` and source grounded |
| `suppress_missing` | `candidate_status == present` (remove from `missing_content`) |
| `abstain` | `candidate_status == ambiguous` (do not count as missing evidence) |
| `demote_verdict` | aggregate policy: surviving quotes all `present`/`ambiguous` (`03-bidirectional-design.md:48-57`) |
| `none` | informational only (markdown lane positive evidence) |

## Layering: what stays where

| Layer | Keep unchanged | Add |
| --- | --- | --- |
| `PdfJudgment` (`pdf_judge.py:244-260`) | `verdict`, `missing_content`, `confidence`, `reasoning` | nothing (LLM assertion only) |
| `PageJudgment` (`models.py:104-130`) | `content_missing`, `missing_content`, `confidence`, `reasoning` | nothing |
| `PdfJudgeResult.to_sidecar_dict` (`pdf_judge.py:373-421`) | top-level keys, `axis_findings`, `textlayer_diff`, `page_screen`, `page_escalations` | per-quote `VerifiedClaim` fields inside `grounded_evidence`; counters `verified_missing_count`, `false_missing_count`, `ambiguous_count` |
| `TapetumResult.grounded_evidence` (`models.py:137-141`, `adjudicate.py:340-343`) | `quote`, `status`, `start`, `end` | same `VerifiedClaim` extensions; PDF lane sets `candidate_status` after bidirectional pass |
| `page_escalations[]` (`pdf_judge.py:577-582`) | `page`, `content_missing`, `grounded_quotes`, `confidence` | optional `claims: [VerifiedClaim]` per page; `content_missing` derived from any `retain_missing` |

**Rule:** LLM fields describe what the model *claims*; `VerifiedClaim` fields describe what determinism *proved*. Never write candidate absence into `reason` unless `candidate_status == absent`.

## Backward compatibility

1. **`schema_version`:** bump tapetum PDF sidecar `3 → 4` when any quote carries `source_status` / `candidate_status`. Text-lane sidecars without bidirectional verify stay at current version until populated.
2. **Additive keys only:** existing consumers (`fusion.py`, `inspect_report.py:95`, `cli.py:408`) read `quote`, `axis`, `reason`, `status`, `start`, `end`. New fields are ignored if absent.
3. **`reason` string:** deprecate `"present in PDF text layer, absent from markdown"` (`pdf_judge.py:401-404`). v4 template: `"source {exact|fuzzy} in PDF text layer"` plus optional `"; candidate {present|absent|ambiguous}"` only when `candidate_status` is set. v3 sidecars remain valid.
4. **`status` alias:** keep `status` as `source_status` for markdown-lane entries (`exact`/`fuzzy`) so `TapetumResult.to_dict` sort keys unchanged (`models.py:177-180`).
5. **`candidate_status: unverified`:** default when bidirectional verifier not run; consumers must treat like today's one-sided evidence (do not assume absence).
6. **No `PdfJudgment` / `PageJudgment` field additions:** preserves D6 schema stability (`models.py:12-16`, `MODELS.md` constrained-decoding floor). Verification is strictly post-hoc.
7. **Deterministic serialization:** sort `grounded_evidence` by `(quote, source_span.start or -1)`; round `match_score` to 4 decimals; enum strings lowercase snake_case.

## Findings

- [CRITICAL] **`grounded_evidence.reason` is a false bidirectional claim today.** Evidence: `pdf_judge.py:401-404` hard-codes `"absent from markdown"` for every source-grounded quote; `00-baseline.md:27-39` shows 12/20 replay quotes were present in markdown. Impact: schema must split `source_status` and `candidate_status`; a single `reason` string must not encode both.

- [HIGH] **langextract's minimal portable core is `char_interval` + `alignment_status`, not the full `Extraction` dataclass.** Evidence: `langextract/core/data.py:74-77`, `43-47`; whisker already ports Tier-1 monotonic DP (`grounding.py:14-21`, `102-115`). Impact: `source_span` + `source_status` mirror langextract; candidate leg is whisker-specific and absent from langextract.

- [HIGH] **unstructured proves provenance belongs in metadata, not in verdict prose.** Evidence: `elements.py:171-175` (`enrichment_origins`), `204-206` (`routing`, `routing_score`); docling grade-first pattern (`05-web.md:176-178`). Impact: `reason_code` + `decision_effect` are the machine contract; `reason` stays human-facing only.

- [HIGH] **`candidate_status` tri-state is load-bearing, not binary.** Evidence: `05-web.md:182-190` (recurring `present | absent | ambiguous`); `03-bidirectional-design.md:28-35`; AbsenceBench weakness (`05-web.md:37-43`). Impact: `ambiguity: true` and `decision_effect: abstain` must exist or precision gains trade for false-fail demotions.

- [MED] **`match_score` should be diagnostic, not gating.** Evidence: unstructured/docling treat numerics as informational (`05-web.md:176-178`); whisker `confidence` already demotes mechanically (`pdf_judge.py:525-526`). Impact: expose score for calibration holdouts; verdict policy keys off `candidate_status` + `reason_code`, not a float threshold in v1.

- [MED] **Page escalation needs claim-level records, not only `grounded_quotes` strings.** Evidence: `pdf_judge.py:577-582` bundles quotes without spans; `576` sets `content_missing` from source-grounded quotes only. Impact: `page_escalations[].claims[]` reuses `VerifiedClaim`; `content_missing` becomes derived.

- [LOW] **`PdfJudgment` / `PageJudgment` should remain assertion-only.** Evidence: `models.py:104-112` scoped question design; mixing proof fields into `output_type` blurs LLM claim with deterministic verification (`00-baseline.md:95-96`). Impact: keeps retry/schema stability; inspect report reads enriched sidecar.

## False-pass hypothesis

A quote `"Document number: P2900R0"` grounds exact in PDF title block (`source_status: exact`) and maps to YAML front matter in markdown (`candidate_status: present`, `reason_code: sanctioned_front_matter`). Without `reason_code`, a consumer matching only `candidate_status == present` clears the quote but still displays legacy `reason` asserting absence, and a human ships on stale v3 semantics.

## False-fail hypothesis

A genuine miss (PR #293 `constexpr`, `00-baseline.md:19`) gets `candidate_status: ambiguous` because whole-document `partial_ratio` lands in the gray band (`03-bidirectional-design.md:42-43`). `decision_effect: abstain` removes it from `missing_content` and demotes verdict to `review`, hiding a real fail. Mitigation: `verified_missing` when source is `exact` and `match_score` is strictly below floor; `ambiguous` only when source is `fuzzy` or score inside band.

## What would change my mind

A schema contract test on committed nine-PR replay sidecars asserting: (1) every v4 `grounded_evidence` entry has `source_status` and `candidate_status`; (2) no entry with `candidate_status in {present, ambiguous}` carries `decision_effect: retain_missing`; (3) `inspect_report.py` and `fusion.py` pass unchanged on v3 fixtures with `candidate_status` absent. Failing (3) would require a parallel `verified_claims[]` array instead of extending `grounded_evidence`.
