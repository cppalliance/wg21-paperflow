# Repo scan: microsoft/markitdown

**Does it verify LLM-readability?** **no** (partial: deterministic structural/substring QA only; no comprehension, fact recovery, or downstream LLM eval)

Scanned: shallow clone at `packages/whisker/research/repos/markitdown` (read-only, 2026-07-06).

---

## Findings

1. **[HIGH] Marketing claims LLM consumability; tests never measure it.** README positions output "for use with LLMs" and argues GPT-4o "speaks Markdown" (`README.md:10`, `README.md:27-34`). CI runs `hatch test` only (`tests.yml:17-18`). No comprehension corpus, no read-back harness, no downstream benchmark.

2. **[HIGH] Core QA is hand-authored substring anchors, not LLM verification.** Every format vector declares `must_include` / `must_not_include` (`_test_vectors.py:11-12`). Module tests assert `string in result.markdown` (`test_module_vectors.py:65-68`). Same pattern drives CLI tests (`test_cli_vectors.py:59-62`). This is extraction fidelity, not "can an LLM recover facts."

3. **[HIGH] Reading-order gates use monotonic `find()` chains (closest portable pattern to olmOCR order facts).** Borderless inventory PDF: header → first table → variance → extended review → second table → recommendations (`test_pdf_tables.py:225-271`). Receipt PDF: store header → transaction → items → subtotal → total → payment → rewards → return policy (`test_pdf_tables.py:456-493`). Normalization strips backslashes before search (`test_pdf_tables.py:16`).

4. **[MED] Negative structural assertions catch false tables and duplication without LLM involvement.** Academic PDF must have zero pipe chars and zero extracted tables (`test_pdf_tables.py:609-618`). Receipt caps table rows `<5` (`test_pdf_tables.py:1110-1113`). Borderless inventory caps duplicate SKU count `<=4` (`test_pdf_tables.py:287-291`).

5. **[MED] Committed goldens use loose structural tolerance, not byte diff or comprehension.** Full-output tests compare line counts within `<=2`, pipe-count floors, and section anchors; golden `.md` content is not byte-diffed (`test_pdf_tables.py:750-777`, `807-813`). Skip if expected golden missing (`test_pdf_tables.py:740-741`).

6. **[MED] LLM in-repo is a conversion feature (image captioning), not an eval judge.** Optional `llm_caption()` calls OpenAI vision API (`_llm_caption.py:48-50`). Tests verify caption plumbing: mock checks prompt passthrough (`test_module_misc.py:465-506`); live test (skipped without `OPENAI_API_KEY`) checks caption contains planted string `5bda1dd6` and color words (`test_module_misc.py:509-532`). No test asks an LLM whether markdown is readable.

7. **[LOW] Multi-entry-point parity is tested (local, stream, URI, CLI).** Same vectors exercise seven conversion paths (`test_module_vectors.py:57-159`, `test_cli_vectors.py:43-125`). Whisker uses markitdown as reference oracle; parity belongs in whisker CI if adopted, not in markitdown's LLM-readability story.

8. **[LOW] No threshold calibration, ROC, or fitted operating points.** All gates are exact integers or substring presence. Confirms redteam claim that `calibrate.py` is ahead of markitdown on formal threshold fitting.

---

## Portable to whisker (ranked)

1. **Section-order gate** — monotonic `find()` chain on candidate md after `replace("\\", "")`; schema field `section_order: [[anchor0, anchor1, ...]]`. Source: `test_pdf_tables.py:225-271`. Closes the reading-order hole guard explicitly dropped from regression axes.

2. **Per-paper `must_include` / `must_not_include`** — hard substring tripwires alongside NID/TEDS. Source: `_test_vectors.py:11-12`, `test_module_vectors.py:65-68`. Complements Lane 3 facts for phrases not yet in corpus.

3. **Negative structural gates** — `forbid_char: "|"`, `max_table_rows`, `max_substring_count` per paper class. Source: `test_pdf_tables.py:287-291`, `609-618`, `1110-1113`. Catches spurious tables and duplication metrics miss.

4. **Structural snapshot floors** — `{line_count, pipe_count, table_row_count}` with slack (markitdown uses `<=2` lines). Source: `test_pdf_tables.py:754-777`. Cheap backstop for catastrophic collapse.

5. **Normalization-before-assert** — backslash strip + `rstrip()` per line before anchor/order checks. Source: `test_pdf_tables.py:16`, `750-751`. Symmetric with mdream's `trimEnd()` pattern.

6. **NOT portable as comprehension proof** — markitdown's LLM caption tests (`test_module_misc.py:509-532`) verify optional vision input wiring only. Do not adopt as Lane 3 substitute.

---

## Cross-check vs redteam report

| Redteam claim (`packages/whisker/research/redteam/markitdown.md`) | Verdict | Evidence |
|---|---|---|
| Gates on per-format substring anchors, not scalar deltas | **Confirmed** | `_test_vectors.py:11-12`, `test_module_vectors.py:65-68` |
| Ordered `str.find()` section chains | **Confirmed** | `test_pdf_tables.py:225-271`, `456-493` |
| Negative structural assertions (no `\|`, receipt `<5` rows, dup cap) | **Confirmed** | `test_pdf_tables.py:287-291`, `609-618`, `1110-1113` |
| Committed goldens + line-count `<=2`, not byte diff | **Confirmed** | `test_pdf_tables.py:750-777` |
| Seven entry-point permutations | **Confirmed** | `test_module_vectors.py:57-159` |
| No ROC/threshold calibration in-repo | **Confirmed** | No calibrate module; hand-set asserts only |
| Top portable: section-order gate | **Confirmed** | Still highest-leverage deterministic pattern here |

**Contradictions:** none found. Redteam accurately describes markitdown as a structural/substring regression repo, not an LLM-readability verifier. The double irony for whisker stands: the reference oracle it trusts for advisory scoring does not verify its own output's LLM comprehension anywhere in CI.
