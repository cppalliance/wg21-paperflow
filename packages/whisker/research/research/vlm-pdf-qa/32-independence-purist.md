# 32 - Independence-Purist

**Verdict:** usable-with-conditions — the operator directive ("deterministisch ist deterministisch und LLM ist LLM, die prüfen unabhängig voneinander und vergleichen dann die Ergebnisse") is satisfiable only by variant (a) or a stripped variant (b) with det signals removed from the LLM prompt; the current tapetum_llm lane and variant (c) violate it by design.
**Confidence:** high

## Findings

- [CRITICAL] **Today's LLM lane injects the full deterministic verdict and signal bundle into every triage and adjudicate user message, biasing the model toward det's conclusion before it reads the markdown.** Evidence: `_build_triage_message` embeds `Whisker verdict`, `soft_flags`/`hard_flags`, `unigram_coverage`, `coverage`, `lossy_table_count`, `table_parse_errors`, `mojibake_count` — `packages/whisker/src/whisker/tapetum_llm/adjudicate.py:369-392`; `_build_adjudicate_message` repeats whisker verdict and flags — `adjudicate.py:403-417`; authority doc instructs triage to "focus your reading on the flagged dimension first" — `packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md:128`; Step 0 explicitly attaches whisker signals to state — `tapetum_llm.md:112-114`. (No separate `prompts.py` in this lane; prompts live in `tapetum_llm.md` plus the message builders in `adjudicate.py`.) Impact: under the operator directive this is **verdict contamination**, not a second opinion; fusion compares a rubber-stamped echo against det, not uncorrelated errors.

- [CRITICAL] **Removing det signals from the LLM prompt does not break fusion: fusion consumes only sidecar verdict fields, never prompt text.** Evidence: `fuse_verdicts` reads `whisker.get("verdict")`, `tapetum.get("suggested_verdict")`, `confidence`, `axis_findings`, `status` — `packages/whisker/src/whisker/tapetum_llm/fusion.py:117-227`; `TapetumResult` persists `whisker_verdict` as provenance metadata only — `packages/whisker/src/whisker/tapetum_llm/models.py:100-124`, `adjudicate.py:320-334`. Impact: det-signal excision from prompts is a **safe, required** change for independence; fusion assumptions in `research/hybrid-llm-scoring/SYNTHESIS.md:13-14` (ordinal asymmetric matrix, uncorrelated errors) stay valid only after that excision.

- [HIGH] **Variant classification against the operator directive.** (a) **VLM sees page image ONLY → structured inventory → deterministic Python compares inventory to markdown** = fully independent lanes: VLM never sees det signals or det verdict; comparison code is deterministic (satisfies directive literally). Evidence: RaV-IDP reconstruction-as-validation pattern — `05-web.md` Q5; no det fields in comparison path by construction. (b) **VLM sees page image + markdown slice, judges directly** = shares **det INPUT** (tomd output) but not **det SIGNALS**; acceptable-with-conditions if whisker verdict/flags/metrics are absent and prompts forbid treating markdown as authoritative — coarse/DOCR-Inspector prior art — `05-web.md` Q5. (c) **Current lane + PDF added while retaining whisker header injection** = **still contaminated**; adding pixels does not restore independence when `adjudicate.py:379-392` remains. Impact: only (a) or decontaminated (b) can feed fusion's uncorrelated-error thesis; (c) must be rejected.

- [HIGH] **Fusion value assumes uncorrelated errors; shared substrates correlate failures across lanes.** Evidence: `research/hybrid-llm-scoring/SYNTHESIS.md:13-14` — merge rules (`llm_clear_soft_review`, `llm_escalate_major`, `llm_rescue_heading`) assume det and LLM can disagree meaningfully; det and planned VLM rasterizer both use **PyMuPDF** — tomd conversion `packages/tomd/src/tomd/lib/pdf/pipeline.py:1405-1407`, det content check `packages/tomd/src/tomd/lib/check_content.py:259-261`, baseline reuse path `research/vlm-pdf-qa/00-baseline.md:76,84`. **Correlation estimate:** (i) **tomd markdown** — variant (b) shares 100% of conversion output with det's scored artifact (perfect input correlation); variant (a) shares markdown only in the deterministic compare step, not in the VLM encoder (0% prompt correlation). (ii) **PyMuPDF substrate** — det `page.get_text()` and VLM `page.get_pixmap()` share MuPDF font/CMap/render bugs: a garbled CMap poisons det token coverage (`score.py:156-160`) **and** VLM pixels simultaneously → **correlated false-pass** (both lanes agree the page "looks fine") or **correlated false-fail** (both see garbage). olmocr's poppler subprocess (`00-baseline.md:14`) reduces renderer correlation at the cost of a second rasterization dep. (iii) **Det signals in prompt** — current design ≈ **1.0 error correlation** on escalation direction (LLM told which axis det already doubted). Impact: fusion's 44% review-queue shrink (`SYNTHESIS.md:13`) is measured on a **contaminated** lane; post-decontamination disagreement rates are unknown and may be lower.

- [HIGH] **The page→markdown-chunk pairing paradox is real, but alignment metadata can flow without verdict contamination.** Evidence: converted markdown has **no page numbers** — tomd emits continuous body text (`packages/tomd/src/tomd/CLAUDE.md:43-48`); tapetum chunks on H2 only, with no page map — `packages/whisker/src/whisker/tapetum_llm/chunking.py:129-136`; det-side `check_paper_content` already builds a per-token `page_map` from PyMuPDF page text independent of whisker verdict — `packages/tomd/src/tomd/lib/check_content.py:304-316,564-573`; `missing_regions` carry `page` + `token_start`/`token_end` on the **source** stream — `check_content.py:531-542`, surfaced in whisker sidecar — `packages/whisker/src/whisker/score.py:235-241,276-277`. **Safe boundary:** precompute `{page_index, md_char_start, md_char_end}` in pure Python (from `check_content` token alignment or coarse page/H2 heuristics) and pass **only** page index + md slice + raster to the VLM. **Forbidden:** passing `verdict`, `soft_flags`, `unigram_coverage`, or "focus on flagged dimension" derived from det (`tapetum_llm.md:128`). Impact: pairing is a **structural index**, not a second verdict; using det's `missing_regions` as optional slice hints is borderline (location metadata, not verdict) and should be logged separately from whisker sidecar fields to avoid prompt leakage.

- [MED] **Candidate selection (`select_candidates`) is a separate contamination class: it gates WHO gets LLM/VLM adjudication using det metrics, not what the model sees.** Evidence: pass-tier selection triggers on `lossy_table_count`, `unigram_coverage - coverage`, etc. — `packages/whisker/src/whisker/tapetum_llm/adjudicate.py:99-126`; benign-region skip uses `soft_flags` + `unigram_coverage` — `adjudicate.py:129-138`. Impact: selection skews which papers receive a second opinion (documented blind spot in `SYNTHESIS.md:48`); it does **not** invalidate fusion math on adjudicated papers, but strict independence purists may want uniform selection (all det-pass papers) or PDF-only triggers decoupled from whisker flags.

- [MED] **System prompt still frames the LLM as "second opinion after whisker scored this conversion," even if headers are stripped.** Evidence: `tapetum_llm.md:33` ("A deterministic gate (whisker) already scored this conversion; you give a second opinion"); RESCUE case references whisker hard flags — `tapetum_llm.md:72-74`. Impact: decontamination requires rewriting authority text, not only deleting header lines in `adjudicate.py`.

- [LOW] **Tier-2 replay of tier-1 reasoning is intra-lane contamination, not det contamination, but reduces effective independence inside the LLM cascade.** Evidence: `_build_adjudicate_message` injects tier-1 reasoning/concern — `adjudicate.py:409-420`. Impact: acceptable for cost control; orthogonal to det/LLM lane separation.

## False-pass hypothesis

Det **pass** on token-preserving table cell swap (`unigram_coverage` blind by design — `packages/whisker/src/whisker/score.py:130-138`); decontaminated variant (b) VLM at 150 DPI hallucinates the swapped cell text from the page image (HQH OCR-category ~60% hallucination — `05-web.md` Q4) and returns **pass** with high confidence; fusion sees det=pass + llm=pass → `FUSION_RULE_AGREE` — `fusion.py:217-227` → combined advisory **pass** while the corruption remains. Variant (a) with deterministic inventory diff is the mitigation: the compare step must catch token-preserving swaps structurally, not via VLM agreement.

## False-fail hypothesis

Faithful conversion with footer/page furniture stripped by tomd (`packages/tomd/src/tomd/CLAUDE.md:215-224`); independent VLM compares page raster to md slice, flags "Document #: P####" absent from markdown as wording/structure defect (`15-false-fail-hunter.md:8`); det already soft-flags region-only review when `unigram_coverage >= REGION_BENIGN_UNIGRAM_FLOOR` — `packages/whisker/src/whisker/score.py:183-190`, `constants.py:91-93`; fusion det=pass + llm=fail(major) → merged **review** only — `fusion.py:204-215`. Operator queue inflates without blocking ship.

## What would change my mind

A/B on ≥30 labeled WG21 PDFs comparing **(a)** page-inventory + deterministic diff vs **(b)** decontaminated image+md-slice judge (no det signals in prompt), measuring (i) disagreement rate with det on pass-tier papers, (ii) incremental catch of token-preserving false passes, and (iii) fused false-pass rate under `fuse_verdicts` — if (a) or (b) shows >2× independent disagreement vs today's contaminated lane at ≤10% extra merged false-pass, verdict flips to **usable** with that variant locked.

---

## Recommendation (variant)

**Adopt variant (a) as the target architecture; ship decontaminated variant (b) only as an interim if inventory extraction is not ready.**

1. **VLM lane:** rasterize each PDF page (`get_source_path` — `packages/paperstore/src/paperstore/sqlite_backend.py:1119-1135`); VLM emits per-page structured inventory (tables, headings, normative phrases, figure captions) with **no markdown and no whisker fields** in the prompt.
2. **Deterministic compare lane (extend whisker or new pure-Python module):** diff inventory against `paper.md` (token/set/structural rules); emit `suggested_verdict` + `axis_findings` into the existing tapetum sidecar shape for fusion.
3. **Interim (b):** if inventory schema slips, VLM may see page image + md slice paired via page index only; **delete** `adjudicate.py:379-387` and `403-417` whisker blocks; rewrite `tapetum_llm.md:33,112-128,72-74`.

Prefer **poppler or pypdfium2** for VLM rasterization when PyMuPDF correlation with det `get_text()` is unacceptable (`00-baseline.md:14,38`); keep PyMuPDF only where reuse is mandatory and document the shared-failure risk.

## Contamination checklist (implementation gate)

| Check | Pass criterion | Evidence anchor |
|-------|----------------|-----------------|
| No det verdict in LLM/VLM user message | Prompt contains zero of: `Whisker verdict`, `verdict:`, det pass/fail/review | `adjudicate.py:381,415` removed |
| No det flags in prompt | No `soft_flags`, `hard_flags`, `Flags:` line | `adjudicate.py:370,407` removed |
| No det metrics in prompt | No `unigram_coverage`, `coverage`, `lossy_tables`, `table_errors`, `mojibake` | `adjudicate.py:383-387` removed |
| No "focus flagged dimension" instruction | System/triage text does not reference whisker signals | `tapetum_llm.md:128` rewritten |
| No det verdict as VLM precondition | System prompt does not say whisker already scored | `tapetum_llm.md:33` rewritten |
| Alignment metadata only | Page→slice map uses `{page, char_start, char_end}`; no whisker sidecar JSON in VLM prompt | `check_content.py:304-316` as optional indexer |
| Fusion unchanged | `fuse_verdicts(whisker, tapetum)` still pure dict merge | `fusion.py:117-227` |
| Sidecar provenance | `whisker_verdict` in `TapetumResult` is write-time metadata, not model input | `models.py:101-123` |
| Renderer independence (optional hard gate) | VLM rasterizer ≠ PyMuPDF if measuring uncorrelated errors | `00-baseline.md:84` vs poppler `14` |
| Selection documented | If `select_candidates` still uses det metrics, report as coverage skew, not independence | `adjudicate.py:83-111` |
