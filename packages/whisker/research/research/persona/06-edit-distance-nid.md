# 06 - Edit-Distance / NID Reviewer

**Verdict:** usable-with-conditions (+ core NED/`normalized_text` match OmniDocBench; rapidfuzz parity is regression-tested but not corpus-re-goldened; normalization blind spots and uncalibrated advisory edge limit trust in `ref_nid` alone)
**Confidence:** medium

## Findings

- [HIGH] **All-punctuation / symbol-only strings collapse to identical empty normalized text, scoring NID=1.0 on the oracle path.** Evidence: `clean_string` keeps only `\w` + CJK (`metrics.py:116-126`); `score.py:212` compares `text_nid(normalized_text(a), normalized_text(b))`; runtime on `('!!!','???')`, emoji-only pairs, and `'# ## | * * *'` vs `'--- === ...'` all yield `normalized_text→''` and `text_nid=1.0`. Impact: cross-converter advisory agreement can read perfect when both sides lost all alphanumeric content (image-heavy pages, corrupted empty output); only structural gates and `unigram_coverage` catch this, not `ref_nid`.

- [MED] **`normalized_text` does not strip YAML front matter; metadata tokens enter the edit distance.** Evidence: `clean_string` docstring omits front-matter stripping (`metrics.py:118-126`); `CLAUDE.md:149-150` documents this as intentional; runtime front-matter vs plain-body pair yields `norm_fm='titleImportantTitledocumentP9999R0authorAliceRealHeadingContenthere'` vs `norm_plain='RealHeadingContenthere'` and `text_nid≈0.31`; baseline §3b: mean `ref_nid=0.836`, 147/382 below `REF_NID_ADVISORY_EDGE=0.85` (`constants.py:87`). Impact: advisory review flags fire on formatting/metadata divergence even when body prose matches (see `test_score.py:232-250` where body dominance masks the delta); edge is provisional per §5.

- [MED] **rapidfuzz ↔ historical GPL Levenshtein parity is evidenced by frozen literals and spot checks, not a full-corpus re-golden.** Evidence: `test_edit_distance_parity.py:26-35` bakes 7 string + 3 integer-sequence vectors captured pre-migration; `pyproject.toml:17` pins `rapidfuzz>=3.14.5,<4`; runtime 20×200-char random pairs and 50k-char pair match `normalized_edit_distance` to bit-identical NED; 353 tests green (§2). Impact: swap is safe for tested inputs; a future rapidfuzz major bump or Unicode edge case could drift scores without a 382-paper baseline refresh (`text-edit-distance.md:124`).

- [MED] **Whole-document oracle NID and block-matched NID diverge on empty-after-normalize blocks.** Evidence: `match_blocks` drops blocks where `normalize(b)==''` (`match.py:153-158`); empty match list → `block_metrics` returns `nid=0.0` (`match.py:257-258`); whole-document path on the same punctuation-heavy strings gave `text_nid≈0.15` vs `block_text_nid=0.0` at runtime. Impact: bench `nid` and score `ref_nid` are not comparable axes (by design per `CLAUDE.md:169-174`), but auditors must not treat block NID as a substitute for oracle NID.

- [LOW] **`_ned` in `match.py` duplicates `normalized_edit_distance` without `_normalize_text`.** Evidence: `match.py:100-107` vs `metrics.py:64-78`; blocks are pre-normalized via `normalize=normalized_text` (`match.py:144-145`) so scores align. Impact: maintenance footgun only; no measured score drift.

- [LOW] **CJK is preserved; non-CJK scripts and emoji are stripped.** Evidence: `_CLEAN_KEEP_RE = r"[^\w\u4e00-\u9fff]"` (`metrics.py:115-116`); runtime `text_nid('中文测试','中文试验')=0.5`, Latin vs CJK `=0.0`. Impact: correct OmniDocBench alphabet for WG21 corpus; non-CJK math symbols outside LaTeX `$...$` folds are lost before NED.

- [LOW] **`text_nid` applies whitespace collapse (`_normalize_text`, `metrics.py:84-85,350`) on inputs that `score.py` already passes through `normalized_text`.** Evidence: `score.py:212`; redundant but harmless because `clean_string` already removed whitespace (`metrics.py:121-124`). Impact: none on scores; naming suggests `text_nid` is raw-text safe when oracle path pre-normalizes.

## False-pass hypothesis

A paper whose converted markdown retains only markdown syntax and symbols (no `\w`/CJK survivors after `clean_string`) while the oracle emits the same class of content-free noise: both sides normalize to `''`, `ref_nid=1.0` (`score.py:212`), no advisory flag, and structural/`unigram_coverage` gates must carry the verdict alone. Example runtime: `text_nid(normalized_text('!!!'), normalized_text('???'))==1.0`.

## False-fail hypothesis

tomd output with full YAML front matter (`title`, `document`, `author` keys) scored against a markitdown oracle that emits the same body words without YAML: front-matter tokens inflate the normalized string prefix, depressing `ref_nid` to ~0.31 in runtime (below `REF_NID_ADVISORY_EDGE=0.85`) and triggering advisory review on 147/382 papers (baseline §3b) even when body prose is faithful (`test_score.py:232-250` passes only when body dominates).

## What would change my mind

A post-migration run over all 382 converted papers asserting `max(abs(old_nid - new_nid)) == 0` per paper (or a labeled 30–50 paper set with measured TPR/FPR for `REF_NID_ADVISORY_EDGE`), plus either front-matter stripping in `normalized_text` or evidence that YAML token delta is <0.01 NID on ≥95% of the corpus.
