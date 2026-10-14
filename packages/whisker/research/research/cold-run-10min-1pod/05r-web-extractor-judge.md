# 05r - Web: MinerU / marker / docling / olmocr — LLM verification / judge stages?

**Forage date:** 2026-07-24  
**Question:** Did these extractors add in-pipeline LLM *verification* (judge) stages in 2025–2026, or are they still extraction-(+optional refine)-only?  
**Fleet context:** cold-run ≤10 min on one DeepSeek pod; baseline forbids cloud LLM judges and "just use docling" (wrong workload). This card checks whether extractors quietly grew a *judge* we should steal patterns from, not whether to replace tapetum verification with an extractor.

**Bright line used here:**
- **Extraction / refine:** LLM or VLM produces or edits the document text (part of convert).
- **Judge / verify:** separate pass that scores, accepts/rejects, or fail-closes against source fidelity (what whisker/tapetum does).
- **Eval-only:** LLM-as-judge in benchmarks or product rubrics, not in the convert path.

---

## Verdict (one line)

**Still extraction-only for convert.** None of the four cores added a fail-closed LLM *verification* stage on the extraction path. Adjacent ecosystem pieces (mineru-refine, Marker LLMScorer, Docling confidence / docling-sdg Judge) are refine, eval, or SDG critique — not a drop-in replacement for unit-check judges.

---

## Finding cards

### MinerU (`opendatalab/MinerU`)

- **[HIGH] Core convert remains extraction; optional LLM is title hierarchy only**  
  https://github.com/opendatalab/MinerU/blob/master/docs/en/usage/quick_usage.md · https://github.com/opendatalab/MinerU/blob/077b3101/mineru/utils/llm_aided.py  
  `llm-aided-config` / `title_aided` calls an OpenAI-compatible model to assign heading levels (≤4). Default `enable: false`. Not a source-vs-markdown fidelity judge; no accept/reject gate on parse quality.  
  **Class:** refine (structure labels), not judge.

- **[MED] Quality inspection is visual / artifact, not LLM**  
  https://github.com/opendatalab/MinerU/blob/master/docs/en/reference/output_files.md  
  `layout.pdf`, `span.pdf`, `model.json`, `middle.json` for human/debug inspection. Pipeline/VLM backends emit parse artifacts; no documented post-parse LLM verification step in MinerU 3.x release notes.

- **[HIGH] Ecosystem miss: `mineru-refine` — LLM *judge* of structural suspects + mechanical fidelity**  
  https://pypi.org/project/mineru-refine/0.12.0/ · https://github.com/LcpMarvel/mineru-refine  
  Third-party post-processor (not in MinerU core). Mechanical detectors flag suspects (pseudo-headings, cross-page splits, header/footer bleed, etc.); LLM chooses among fixed fix ops; **machine gates** enforce `C_out ⊆ C_in` and roll back violations. Default text judge DeepSeek; vision (Qwen-VL) for split/garbled tables. **fail-open** if LLM missing. Opt-in layers: OCR confusion fix, table re-transcription.  
  **Class:** closest thing to an "extractor judge" in this forage — but it is a *fixer/linter*, fail-open, and outside official MinerU.  
  **Portable idea only:** mechanical suspect set → small LLM pick-one-op → deterministic fidelity gate. Does **not** replace analytical unit checks; orthogonal workload.

- **[LOW] MinerU-Document-Explorer `judge_claim`**  
  https://github.com/opendatalab/MinerU-Document-Explorer/commit/bfa547dd646a73420def48f2d2af117f0ebc48cc  
  Deep-research wiki tool: agent records claim verdicts (`verified` / `contradicted` / …). Handler is data-in/data-out (no LLM inside the tool). Wrong product surface for PDF extraction QA.

### Marker (`datalab-to/marker`)

- **[HIGH] `--use_llm` is optional refinement inside convert, not a verification stage**  
  https://github.com/datalab-to/marker/  
  Flag improves tables (cross-page merge), inline math, form values via Gemini/Ollama (default `gemini-2.0-flash`). Pipeline steps still: OCR/layout → block clean → **optional LLM improve** → combine. Output is still markdown; no separate pass/fail judge against the page.  
  **Class:** extraction refine.

- **[MED] LLM-as-judge lives in benchmarks only**  
  https://github.com/datalab-to/marker/blob/d63e3d94/benchmarks/overall/scorers/llm.py  
  `LLMScorer` rates markdown vs page image (0–5 overall + field scores) for leaderboard/eval. Not wired into `marker_single` convert.  
  **Class:** eval-only.

- **[LOW] Datalab Platform "rubrics"**  
  https://www.datalab.to/platform  
  Hosted pipeline product: periodic rubric scoring / regression. Closed platform layer; not an open-source Marker convert stage.

### Docling (`docling-project/docling`)

- **[HIGH] Convert path: confidence grades, not LLM judge**  
  https://docling-project.github.io/docling/advanced/confidence-scores/ · service expose 2026-06-18 https://github.com/docling-project/docling/commit/166003b64aefd18447fed1513445facb33d732ce  
  Since v2.34.0, `ConversionResult.confidence` carries `mean_grade` / `low_grade` (`EXCELLENT|GOOD|FAIR|POOR`) from **model certainty**, not an LLM re-read of the page. Docs warn: high confidence ≠ accuracy; table scoring incomplete. Useful as a cheap gate for human review routing.  
  **Class:** heuristic / model-confidence gate. Baseline already says "just use docling" is wrong workload.

- **[MED] `docling-sdg` Judge critiques QA pairs, not parse fidelity**  
  https://github.com/docling-project/docling-sdg/ · https://pypi.org/project/docling-sdg/  
  Synthetic-data pipeline: LLM Judge scores groundness / feasibility / usefulness of generated Q&A. Downstream of Docling parse; does not verify markdown against PDF.  
  **Class:** SDG critique (eval of generated questions).

- **[LOW] Third-party risk screens (deterministic)**  
  https://github.com/realraelrr/docling-skill · https://github.com/MMoney1988/pdf-quality-report  
  Manifest risk levels, provenance/bbox sanity, coverage signals. Explicitly not semantic fidelity audits.

### olmOCR (`allenai/olmocr`)

- **[HIGH] Production path is VLM extraction only; no LLM verification stage**  
  https://github.com/allenai/olmocr/blob/main/README.md · ACL 2026 demo https://aclanthology.org/2026.acl-demo.62/  
  Convert: render pages → finetuned 7B VLM → markdown / Dolma. Retries / filters / guided decoding exist; no second-model "judge the OCR" step in the pipeline CLI.

- **[HIGH] Official evaluation deliberately rejects LLM-as-judge**  
  https://arxiv.org/abs/2502.18443 · https://github.com/allenai/olmocr/tree/main/olmocr/bench  
  olmOCR-Bench = binary unit tests (presence, order, tables, math via KaTeX). Paper states this avoids fuzzy gold and LLM-as-judge bias. olmOCR 2 / ACL 2026: RL with **visual unit tests** as rewards — still not an LLM judge in convert.  
  **Class:** deterministic unit-test eval (closest *philosophy* cousin to tapetum unit checks; different domain: OCR facts vs analytical claims).

- **[LOW] Third parties bolt LLM-as-judge onto bench failures**  
  e.g. Unsiloed re-scores strict olmOCR-Bench fails with GPT-class judge for "semantic rescue." External analysis, not part of allenai/olmocr.

---

## Matrix

| System | In-convert LLM? | Role | Separate LLM *verify/judge* on convert? | Closest quality signal |
|--------|-----------------|------|------------------------------------------|------------------------|
| MinerU | Optional `title_aided` | Heading levels | **No** (core) | Visual PDFs / JSON; **mineru-refine** ecosystem fixer |
| Marker | Optional `--use_llm` | Refine tables/math/forms | **No** | Bench `LLMScorer`; Platform rubrics |
| Docling | No (VLM optional for some pipelines) | Extract | **No** | `confidence` grades (model certainty) |
| olmOCR | VLM *is* the extractor | Extract | **No** | Binary unit tests (bench + RL rewards) |

---

## Any new judge we missed?

| Candidate | Missed before? | Worth treating as a "judge" for this corpus? |
|-----------|----------------|-----------------------------------------------|
| **mineru-refine** (LLM + mechanical `C_out ⊆ C_in`) | **Yes — flag it.** Only real LLM *judging* loop attached to an extractor ecosystem in this forage. | Pattern interest only (suspect → pick-op → machine gate). Fail-open; wrong product for analytical fail-closed verification. Cloud/default DeepSeek judge conflicts with baseline "no cloud LLM judges" unless pointed at Alliance endpoints. |
| Marker `--use_llm` / LLMScorer | No if already counted as refine/eval | Scorer is eval-only; `--use_llm` is refine. |
| Docling confidence grades | Mildly new (v2.34+) | Not LLM; cheap gate pattern only. |
| docling-sdg `Judge` | Easy to misread from names | QA SDG, not extraction verify. |
| MinerU-Document-Explorer `judge_claim` | Easy false positive | Research-claim tooling, not parse QA. |
| olmOCR visual unit tests | Known bench design | Deterministic OCR facts — inspirational for *unit-test shape*, not a new LLM judge stage. |

**Bottom line for cold-run-10min-1pod:** no extractor shipped a built-in fail-closed LLM verification stage that would cut tapetum call count. Do not expect MinerU/marker/docling/olmocr to absorb verification work. The only ecosystem novelty worth a footnote is **mineru-refine** as a structural fixer with LLM pick + machine fidelity, not as a substitute for analytical judges.

---

## False-pass / false-fail traps

- **False-pass:** treating Marker `--use_llm` or MinerU `title_aided` as "they added verification" — those rewrite/label, they do not gate.
- **False-fail:** claiming "zero LLM anywhere" — Marker and MinerU both have optional LLM *aid*; olmOCR *is* a VLM extractor; Docling has confidence grades.
- **Name collision:** "Judge" in docling-sdg / Document-Explorer / mineru-refine vision `judge_split_table` ≠ analytical claim verification.

## What would change this card

- MinerU or Marker shipping a documented convert-path step: score(source, md) → accept|reject with fail-closed default.
- Docling replacing confidence grades with an LLM re-read fidelity check in core `DocumentConverter`.
- olmOCR adding a second-pass LLM judge (contradicting their published bench philosophy).
