# C13 -- Corpus and Holdout Provenance Auditor

**Mandate:** Verify dev-replay/holdout separation, fingerprints, and leakage prevention.
**Auditor role:** Corpus and Holdout Provenance Auditor
**Date:** 2026-07-19
**Scope:** `corpus/holdout/manifest.json`, `corpus/dev-replay/labels.json`, `corpus/dev-replay/README.md`, `corpus/holdout/README.md`, `test_dev_replay_acceptance.py`, `test_dev_replay_schema.py`
**Focus dimension:** D5 (coverage and provenance)

---

## 1. Dev-Replay Corpus

### F1: labels.json has expected verdicts for 9 PRs

- **Severity:** INFO (confirmed correct)
- **Claim:** `dev-replay/labels.json` contains exactly 9 papers with complete ground-truth labels: PR number, source type, human verdict, defect groups, expected LLM verdict, expected deterministic verdict.
- **Evidence:** `labels.json` -- `"$schema": "dev-replay-labels-v1"`, 9 entries: `p4020r0` (PR #282), `p2040r0` (#283), `p0957r8` (#284), `p3556r0` (#285), `p1068r11` (#286), `p1122r3` (#290), `p0533r9` (#293), `p3411r5` (#294), `p3953r0` (#295).
- **Affected gate:** D5 (ground-truth completeness)
- **Confidence:** HIGH
- **Test coverage:** `TestDevReplayLabels.test_nine_papers` asserts `len(labels["papers"]) == 9`.

### F2: Labels are internally consistent

- **Severity:** INFO (confirmed correct)
- **Claim:** Papers with defects expect non-pass LLM verdict. Papers without defects expect LLM pass. Merge papers have no defects; request_changes papers have defects.
- **Evidence:** `test_dev_replay_acceptance.py:TestDevReplayConsistency` -- three tests: `test_defect_papers_expect_non_pass_llm`, `test_clean_papers_expect_pass_llm`, `test_human_verdict_aligns_with_defects`.
- **Confidence:** HIGH

### F3: Defect groups have valid structure

- **Severity:** INFO (confirmed correct)
- **Claim:** Every defect group has `type`, `description`, `affected_count > 0`, and a valid `severity` (low/medium/high/critical).
- **Evidence:** `test_dev_replay_schema.py:TestDevReplayLabels.test_defect_groups_have_valid_structure`.
- **Confidence:** HIGH

### F4: p0533r9 constexpr count mechanically verified

- **Severity:** INFO (confirmed correct)
- **Claim:** The 151 missing constexpr count was mechanically verified: PDF has 231, ideal has 80, delta = 151.
- **Evidence:** `labels.json` p0533r9 entry: `"affected_count": 151, "token": "constexpr"`. `test_dev_replay_schema.py:test_p0533r9_constexpr_count_verified` and `test_dev_replay_acceptance.py:TestP0533R9ConstexprCount.test_label_count` both assert `== 151`. The PDF-based test (`test_pdf_source_count`) checks `count == 231` from PyMuPDF extraction.
- **Confidence:** HIGH

---

## 2. Holdout Corpus

### F5: manifest.json locks candidates with SHA-256

- **Severity:** INFO (confirmed correct)
- **Claim:** `holdout/manifest.json` declares 3 active papers (`p1112r4`, `p3714r0`, `p4182r0`) with `locked_candidates` pinning source + candidate paths and SHA-256 fingerprints. Fingerprint drift fails the holdout test.
- **Evidence:** `manifest.json:8-29` -- each entry has `source_path`, `source_sha256`, `candidate_path`, `candidate_sha256`, `candidate_kind`. `test_dev_replay_schema.py:TestHoldoutAnchors.test_locked_candidate_dispositions` verifies SHA-256 of both source and candidate against the manifest.
- **Affected gate:** D5 (fingerprint integrity)
- **Confidence:** HIGH
- **False-pass hypothesis:** If a file changes on disk but the test is not run, the fingerprint drift is undetected until CI. This is by design (CI is the gate).
- **False-fail hypothesis:** A legitimate re-conversion that changes the candidate bytes (e.g., tomd version bump) would fail the fingerprint check. The fix is to update the manifest with new fingerprints after review. This is the intended ceremony.

### F6: p0533r9 quarantine (excluded from holdout metrics)

- **Severity:** INFO (confirmed correct)
- **Claim:** p0533r9 is listed under `quarantined` in the manifest with a clear reason ("Dev-replay PR #293 contamination; excluded from every holdout metric"). It is NOT in `locked_candidates` and NOT in the active `papers` list.
- **Evidence:** `manifest.json:31-33` -- `"quarantined": {"p0533r9": "Dev-replay PR #293 contamination..."}`. `test_dev_replay_schema.py:TestHoldoutAnchors.test_active_holdout_excludes_dev_replay` asserts `"p0533r9" in manifest["quarantined"]`.
- **Affected gate:** D5 (leakage prevention)
- **Confidence:** HIGH

### F7: Holdout papers are NOT used for threshold tuning

- **Severity:** INFO (confirmed correct)
- **Claim:** The holdout README explicitly states "No threshold tuning permitted against this set." The dev-replay README states "Thresholds and logic may be tuned against this set." The two sets are disjoint.
- **Evidence:** `holdout/README.md:3` -- "No threshold tuning permitted against this set." `dev-replay/README.md:7` -- "These are NOT holdout papers. Thresholds and logic may be tuned against this set." `test_dev_replay_schema.py:TestHoldoutAnchors.test_active_holdout_excludes_dev_replay` asserts `set(manifest["papers"]).isdisjoint(labels["papers"])`.
- **Affected gate:** D5 (leakage prevention)
- **Confidence:** HIGH

### F8: Holdout has sufficient anchor coverage

- **Severity:** INFO (confirmed correct)
- **Claim:** The holdout requires >= 48 total anchors across >= 4 distinct strata. The 8 valid strata are: metadata, headings, prose, punctuation, code, tables, figures, math.
- **Evidence:** `test_dev_replay_schema.py:TestHoldoutAnchors.test_all_anchors_valid_schema` asserts `total >= 48`. `test_strata_coverage` asserts `len(strata) >= 4`.
- **Confidence:** HIGH

### F9: Locked candidate dispositions verified against actual markdown

- **Severity:** INFO (confirmed correct)
- **Claim:** For each active holdout paper, the test loads the anchors, runs `classify_candidate_evidence` against the locked candidate markdown, and asserts each anchor's `expected_candidate_status` matches the actual disposition.
- **Evidence:** `test_dev_replay_schema.py:TestHoldoutAnchors.test_locked_candidate_dispositions:185-200` -- full SHA-256 verification + disposition comparison for all 3 active papers.
- **Confidence:** HIGH

### F10: Case and punctuation canaries catch drift

- **Severity:** INFO (confirmed correct)
- **Claim:** Two mutation canaries on p3714r0: changing case of `FLT_EVAL_METHOD` to `flt_eval_method` must change disposition from `present_in_candidate` to `ambiguous`. Changing `==` to `!=` in a code assertion must also become `ambiguous`.
- **Evidence:** `test_dev_replay_schema.py:TestHoldoutAnchors.test_case_and_punctuation_disposition_canaries`.
- **Confidence:** HIGH

---

## 3. Dev-Replay vs Holdout Separation

### F11: Complete disjointness

- **Severity:** INFO (confirmed correct)
- **Claim:** The 9 dev-replay papers and the 3 active holdout papers are completely disjoint sets. p0533r9 appears in dev-replay (as PR #293) and is quarantined from holdout.
- **Evidence:** `test_active_holdout_excludes_dev_replay` asserts `set(manifest["papers"]).isdisjoint(labels["papers"])` AND `"p0533r9" in manifest["quarantined"]`.
- **Confidence:** HIGH

---

## 4. Holdout Anchors Source Verification

### F12: Anchors verified against PDF source pages

- **Severity:** INFO (confirmed correct)
- **Claim:** `test_quotes_exist_on_declared_source_pages` opens the PDF source for each holdout paper and verifies that every anchor's `quote` text exists on the declared `source_location.page`.
- **Evidence:** `test_dev_replay_schema.py:231-257`.
- **Affected gate:** D5 (anchor provenance)
- **Confidence:** HIGH (test is conditional on PDF availability via `pytest.mark.skipif`)

---

## 5. Summary

| Finding | Severity | Dimension | Verdict |
|---------|----------|-----------|---------|
| F1: labels.json has 9 PRs with complete fields | INFO | D5 | CONFIRMED |
| F2: Labels internally consistent | INFO | D5 | CONFIRMED |
| F3: Defect group structure valid | INFO | D5 | CONFIRMED |
| F4: p0533r9 constexpr count verified | INFO | D5 | CONFIRMED |
| F5: Holdout locked with SHA-256 | INFO | D5 | CONFIRMED |
| F6: p0533r9 quarantined from holdout | INFO | D5 | CONFIRMED |
| F7: Holdout NOT used for threshold tuning | INFO | D5 | CONFIRMED |
| F8: >= 48 anchors, >= 4 strata | INFO | D5 | CONFIRMED |
| F9: Locked dispositions verified | INFO | D5 | CONFIRMED |
| F10: Case + punctuation canaries | INFO | D5 | CONFIRMED |
| F11: Complete dev-replay/holdout disjointness | INFO | D5 | CONFIRMED |
| F12: Anchors verified against PDF pages | INFO | D5 | CONFIRMED |

**Overall assessment:** The corpus provenance discipline is rigorous. Dev-replay and holdout are completely disjoint, SHA-256 fingerprints lock the evaluation inputs, p0533r9 is correctly quarantined, and the holdout README explicitly prohibits threshold tuning. All claims are backed by automated tests in CI.
