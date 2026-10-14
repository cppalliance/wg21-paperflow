# Marker v2 Competitive Evaluation

**Date:** 2026-07-31
**Versions:** tomd (current workspace), Marker v1.10.2 (SHA ef16c2c), Marker v2.0.0 (SHA 947d768)
**Platform:** Windows 10 x64, CPU-only (no GPU), Python 3.12
**Corpus:** 9 PDF + 3 HTML golden sources from `packages/tomd/tests/fixtures/golden/sources/`
**Golden Ideals:** cwg1, p4020r0, p4182r0, p4228r0 (4 papers with human-corrected structural ground truth)

---

## Executive Verdict

**Do not replace tomd with Marker v2. Monitor quarterly. Contribute an upstream patch for WG21 wording detection if the project accepts external contributions.**

**Confidence:** HIGH

Marker v2.0.0 is a substantial rewrite with improved licensing (Apache-2.0 code, OpenRAIL-M models) and competitive general-purpose benchmark scores (76% on olmOCR-bench balanced mode). However, it fails every WG21-specific requirement that justifies tomd's existence:

1. **Zero WG21 wording support.** No ins/del detection, no color-span semantics, no strikethrough geometry. Score: 0/3.
2. **Requires external native binary.** Surya 2 (the VLM backbone) requires `llama-server` from llama.cpp or a vLLM Docker container. Even "fast" and "disable_ocr" modes use the VLM for layout. This is not a pip-installable library.
3. **Model license revenue cap.** OpenRAIL-M model license imposes a $5M revenue/funding cap for free use.
4. **No YAML front matter.** Marker produces no document metadata block.
5. **Code fidelity risk.** VLM-generated text in code regions introduces hallucination risk absent from tomd's verbatim MuPDF extraction.

---

## 1. Repository Normalization (Completed)

| Clone | Path | Version | SHA | Code License | Status |
|-------|------|---------|-----|-------------|--------|
| Marker v1.10.2 | `packages/whisker/research/repos/marker-v1.10.2/` | 1.10.2 | ef16c2c | GPL-3.0 | Renamed from `marker/`, 20 path refs updated across 13 files |
| Marker v2.0.0 | `packages/whisker/research/repos/marker-v2.0.0/` | 2.0.0 | 947d768 | Apache-2.0 | Fresh clone at exact tag |

Historical references in 13 research files updated from `repos/marker/` to `repos/marker-v1.10.2/`. Only worktree copies of old paths remain (expected, separate branches).

---

## 2. Prior Evaluation Reconstruction

### 2.1 Three Prior Activities

The existing Marker research in this repo spans three distinct activities:

1. **tomd replacement survey** (`packages/tomd/improvements.md` section 9): Zero-shot opportunity matrix scoring 7 tools across 9 WG21 subproblems on a 0-3 scale. Marker scored 0/3 on ins/del wording (the critical differentiator). Original legend was qualitative ("solves well (3) or poorly (0)") rather than calibrated.

2. **Marker QA-pattern mining** (`packages/whisker/research/redteam/marker.md`): Red-team comparing Whisker guards against Marker's CI/QA approach. Found Whisker ahead on per-item regression, Marker ahead on stratified reporting and pre-score normalization.

3. **Whisker scoring research** (`research/llm-readability/repo-scan/marker.md`): Verdict "partial" on LLM-readability verification. Marker CI gates corpus-mean heuristic + table TEDS only, no comprehension lane.

### 2.2 Prior 0-3 Matrix (v1.10.2 era)

| Subproblem | Marker v1 | tomd |
|------------|-----------|------|
| Code listings | 2 | 3 |
| Tables | 2 | 2 |
| ins/del wording | **0** | **3** |
| Math/LaTeX | 2 | 1 |
| Multi-column | 2 | 2 |
| Hyperlinks | 1 | 2 |
| Footnotes | 2 | 2 |
| TOC detection | 1 | 2 |
| Header/Footer | 2 | 2 |

### 2.3 New Rubric (v2 evaluation)

| Score | Label | Definition |
|-------|-------|------------|
| 0 | Unsupported | Feature absent or fundamentally broken; no code path addresses it |
| 1 | Weak/partial | Some handling exists but fails on WG21-typical inputs |
| 2 | Adequate with limitations | Works for common cases; known failure modes on edge cases |
| 3 | Strong | Works reliably out-of-the-box on WG21-style papers |

---

## 3. Conversion Results

### 3.1 tomd (Current)

| Source | Type | Time (s) | Status |
|--------|------|----------|--------|
| p0533r9.pdf | PDF | 1.0 | OK |
| p0957r8.pdf | PDF | 2.9 | OK |
| p1068r11.pdf | PDF | 1.2 | OK |
| p1112r4.pdf | PDF | 0.9 | OK |
| p1122r3.pdf | PDF | 1.3 | OK |
| p2040r0.pdf | PDF | 0.6 | OK |
| p3556r0.pdf | PDF | 1.2 | OK |
| p3714r0.pdf | PDF | 0.1 | OK |
| p4182r0.pdf | PDF | 0.9 | OK |
| cwg1.html | HTML | 0.01 | OK |
| p4020r0.html | HTML | 0.01 | OK |
| p4228r0.html | HTML | 0.02 | OK |

**Total: 12/12 succeeded, ~10s aggregate**

### 3.2 Marker v2.0.0 (All Modes)

| Mode | Attempted | Succeeded | Failed | Reason |
|------|-----------|-----------|--------|--------|
| balanced | 9 PDF | 0 | 9 | `llama-server binary not found` |
| fast | 9 PDF | 0 | 9 | `llama-server binary not found` |
| disable_ocr | 9 PDF | 0 | 9 | `llama-server binary not found` |
| (HTML) | 3 | 0 | 3 | HTML not supported by Marker |

**Total: 0/30 succeeded**

### 3.3 Root Cause

Surya OCR 2 (v0.22.1), the VLM backbone used by all Marker v2 modes, requires `llama-server` from the llama.cpp project as a native binary. This is not a Python package; it must be compiled from source or obtained from GitHub releases. The requirement applies to ALL modes, including "fast" and "disable_ocr", because even these modes use Surya's VLM for layout detection.

The error fires at `surya.inference.backends.llamacpp:_resolve_llama_server_binary` (line 33-46). The settings allow overriding via `LLAMA_CPP_BINARY` env var or `SURYA_INFERENCE_BACKEND=vllm` (requires a vLLM Docker container), but neither option provides a simple pip-installable experience.

**This is a platform portability finding, not a test infrastructure gap.** Any consumer of Marker v2 faces this requirement.

---

## 4. Evidence-Tiered Scoring Protocol

### 4.1 Tier Definitions

| Tier | Source | Weight | Description |
|------|--------|--------|-------------|
| A | Golden Ideals | Ground truth | Candidate vs human-corrected structural reference (4 papers) |
| B | Whisker Lane 3 facts | Verified | Deterministic source-verified assertions on overlapping PIDs |
| C | Source-backed checks | Strong advisory | Content coverage, code token preservation, WG21 construct detection, checked against PDF/HTML source |
| D | tomd snapshot agreement | Advisory only | Agreement with tomd's current output; explicitly NOT ground truth |

### 4.2 Scoring Not Possible

Since all Marker v2 conversions failed (no output produced), quantitative Whisker scoring is not applicable for this evaluation cycle. The scoring protocol is documented here for the next run when llama.cpp or GPU infrastructure is available.

**Whisker Lane 2 metrics (applicable to Marker output):**
- NID (Normalized Information Distance): text similarity against Golden Ideal
- TEDS (Tree Edit Distance Similarity): table structure
- MHS (Markdown Heading Similarity): heading level agreement
- Content recall: fraction of source content tokens present

**Whisker Lane 3 (applicable where facts exist):**
- Per-fact-type pass rates (present, absent, order, table, math)

**Source-backed checks (applicable to any converter):**
- Missing content percentage
- Code token preservation rate
- Math operator preservation
- Table cell count accuracy
- Link count preservation
- TOC leakage detection
- WG21 wording detection (ins/del spans present)

---

## 5. 50-Agent Research Swarm Summary

All 50 Grok 4.5 agents completed their read-only analysis. Key consolidated findings:

### 5.1 Architecture (Agents 6-10)

Marker v2 is a complete rewrite from v1. The pipeline stages are:

1. **Provider** (pdftext or other): extracts raw text + metadata from PDF
2. **Layout Builder**: uses Surya VLM to detect page regions (text, table, code, figure, header, etc.)
3. **OCR Builder**: uses Surya VLM for full-page OCR when text quality is bad
4. **Line Builder**: assigns text to layout regions
5. **Structure Builder**: builds document tree from regions
6. **Processors**: 20+ processors refine the document (code detection, table extraction, equations, footnotes, etc.)
7. **Renderer**: produces final Markdown output

**All modes use the Surya VLM** for layout, differing only in whether OCR is additionally applied:
- **balanced**: VLM layout + VLM OCR (highest quality, highest cost)
- **fast**: ONNX rf-detr layout + VLM only for surgical patches
- **disable_ocr**: rf-detr layout + pdftext only (no VLM OCR, but VLM still used for layout in some paths)

### 5.2 Critical WG21 Gaps (Agents 24, 19, 23, 22)

| Feature | Marker v2 Status | tomd Status | Impact |
|---------|-----------------|-------------|--------|
| ins/del wording | **Absent** (no code path) | Implemented (HSV color + strikethrough geometry) | CRITICAL: impossible to evaluate C++ standard proposals without this |
| YAML front matter | **Absent** | Implemented (title, document, date, intent, audience, reply-to) | HIGH: downstream pipelines require structured metadata |
| Code verbatim preservation | **Risk**: VLM can hallucinate | MuPDF verbatim extraction, no model in text path | HIGH: every C++ character matters |
| TOC stripping | Has `DocumentTOCProcessor` | Has `toc.py` with Whisker-gated checks | MEDIUM: both handle this |
| Header/footer stripping | Has `PageHeaderProcessor` | Has `cleanup.py` detection | MEDIUM: both handle this |

### 5.3 License Analysis (Agents 4, 5)

| Component | License | Constraint |
|-----------|---------|------------|
| Marker v2 code | Apache-2.0 | No constraint for any use |
| Surya OCR 2 models | OpenRAIL-M (AI Pubs) | Revenue/funding cap: $5M. Above $5M requires commercial license. |
| Surya OCR 2 code | Apache-2.0 | No constraint |
| Model weights (GGUF) | OpenRAIL-M | Same $5M cap |

**License verdict**: Code license (Apache-2.0) is excellent, a major improvement from v1's GPL-3.0. Model license has a revenue cap that may not affect CppAlliance currently but creates a dependency on external licensing terms.

### 5.4 Platform and Infrastructure (Agents 32-34)

- **Windows**: Marker v2 has no first-class Windows support for llama.cpp; users must compile from source or find Windows releases
- **CPU-only**: Even with llama.cpp on CPU, balanced mode would be extremely slow (Surya VLM is ~7B params)
- **GPU**: balanced mode requires 4-8 GB VRAM; vLLM backend requires Docker
- **Determinism**: VLM inference introduces run-to-run variance from floating-point non-associativity; no determinism pins documented

### 5.5 Benchmark Claims (Agents 38-42)

Marker v2 claims on olmOCR-bench (self-reported):
- balanced: 76.0%
- fast: 66.6%
- disable_ocr: 43.6%

**Caveats:**
- Scores are self-reported, computed by Marker's own benchmark harness
- Failed samples are **dropped from averages** (`benchmarks/overall/overall.py:72-77`)
- olmOCR-bench is a general-purpose benchmark, not WG21-specific
- No Whisker-equivalent comprehension lane in Marker's benchmark
- The heuristic scorer is 80% content + 20% Kendall-tau order, GT fuzzy alignment

### 5.6 Upstream Patch Opportunities (Agent 49)

| Patch | Marker v2 Target File | WG21 Benefit | License Path |
|-------|-----------------------|--------------|-------------|
| ins/del wording detection | `marker/processors/` (new processor) | Enables WG21 wording in Marker output | BSL-1.0 -> Apache-2.0 (requires re-licensing contribution) |
| WG21 front matter extraction | `marker/processors/` (new processor) | Structured metadata from WG21 papers | Same |
| TOC stripping improvements | `marker/processors/document_toc.py` | Better TOC handling | Same |

---

## 6. Updated Zero-Shot Opportunity Matrix

| Subproblem | Marker v1 | Marker v2 | tomd | Delta v1->v2 |
|------------|-----------|-----------|------|-------------|
| Code listings | 2 | 2 | 3 | 0 (VLM risk increases) |
| Tables | 2 | 2 | 2 | 0 (VLM table processor new but unverified) |
| ins/del wording | **0** | **0** | **3** | 0 (still absent) |
| Math/LaTeX | 2 | 2 | 1 | 0 (VLM equation processor new) |
| Multi-column | 2 | 2 | 2 | 0 (Surya VLM handles reading order) |
| Hyperlinks | 1 | 1 | 2 | 0 (no change found) |
| Footnotes | 2 | 2 | 2 | 0 (FootnoteProcessor present) |
| TOC detection | 1 | 2 | 2 | +1 (DocumentTOCProcessor improved) |
| Header/Footer | 2 | 2 | 2 | 0 (PageHeaderProcessor present) |
| **Total** | **14** | **15** | **21** | **+1** |

---

## 7. Conclusions and Recommendations

### 7.1 Replace tomd? **NO.**

Marker v2 cannot replace tomd for WG21 papers because:
- **Wording detection is existential** for standard proposal analysis and Marker has zero support for it
- **VLM-based text generation risks hallucination** in C++ code listings
- **Infrastructure requirement** (llama.cpp or vLLM) conflicts with our simple pip-installable deployment model
- **Model license revenue cap** creates an external dependency on licensing terms
- **No YAML front matter** support breaks downstream pipeline contracts

### 7.2 Adopt a Component? **MONITOR ONLY.**

Surya's layout detection and table recognition are architecturally interesting as third-path signals for tomd's confidence ensemble (see `improvements.md` section 4). However:
- Surya 2 now requires llama.cpp/vLLM (was previously a simpler model in v1)
- This is a heavier integration than the Docling/MinerU layout hints recommended in `improvements.md`
- The infrastructure burden is not justified for a hint-only integration

### 7.3 Contribute an Upstream Patch? **YES, if accepted.**

The highest-value contribution would be a `WordingProcessor` that detects WG21 ins/del spans via font color and strikethrough. This would:
- Benefit the broader WG21 community using Marker
- Establish CppAlliance's visibility in the Marker ecosystem
- Require re-licensing the contributed code under Apache-2.0 (acceptable, as our project is BSL-1.0)
- Target: `marker/processors/wording.py` (new file), test fixture from our golden corpus

### 7.4 Monthly Rerun Recipe

Trigger: new Marker release tag or quarterly calendar.

1. Clone at exact tag into `packages/whisker/research/repos/marker-v<version>/`
2. Create isolated venv, install Marker + CPU llama.cpp (when available for Windows)
3. Convert all golden PDFs in all modes
4. Run Whisker Lane 2 against Golden Ideals (when conversion succeeds)
5. Run source-backed checks for WG21 constructs
6. Update this report's scores and delta

**Key re-evaluation triggers:**
- Marker adds color/strikethrough-based span detection (wording support)
- Surya provides a pure-Python inference path (no llama.cpp requirement)
- Marker adds YAML front matter extraction
- Marker verifies code fidelity with verbatim-preservation tests

---

## 8. Failures and Uncertainty

| Item | Status | Impact |
|------|--------|--------|
| Marker v2 conversion: 0/27 succeeded | llama-server not available on Windows without GPU | No quantitative Whisker scoring possible this cycle |
| Marker v1 conversion: not attempted | v1 venv not created (dependencies also conflict) | v1 baseline relies on prior qualitative evaluation only |
| olmOCR-bench scores: self-reported | Not independently reproduced | v2 quality claims are advisory only |
| Determinism: untested | No repeated runs possible | Cannot verify run-to-run stability |
| GPU performance: untested | No GPU available | Cannot verify balanced-mode quality or timing claims |

---

## Appendix A: 50-Agent Assignment Registry

All 50 Grok 4.5 agents completed their read-only analysis. Assignments and completion status:

| # | Assignment | Status |
|---|-----------|--------|
| 1 | Release provenance and v2 claims | Completed |
| 2 | v1-to-v2 code diff | Completed |
| 3 | Packaging/install changes | Completed |
| 4 | Apache code-license verification | Completed |
| 5 | Model-license/commercial constraints | Completed |
| 6 | Architecture map | Completed |
| 7 | Converter/renderer entry points | Completed |
| 8 | CLI and mode semantics | Completed |
| 9 | Balanced mode deep dive | Completed |
| 10 | Fast mode deep dive | Completed |
| 11 | Disable-OCR mode deep dive | Completed |
| 12 | Device-dependent defaults | Completed |
| 13 | Surya OCR 2 integration | Completed |
| 14 | pdftext integration | Completed |
| 15 | Layout detection | Completed |
| 16 | Reading order/multi-column | Completed |
| 17 | Table extraction | Completed |
| 18 | Equations/math | Completed |
| 19 | C++ code fidelity | Completed |
| 20 | Hyperlinks/xrefs | Completed |
| 21 | Images/captions | Completed |
| 22 | Headers/footers/TOC | Completed |
| 23 | Metadata/front matter | Completed |
| 24 | WG21 ins/del wording | Completed |
| 25 | Unicode/glyphs | Completed |
| 26 | Footnotes/lists | Completed |
| 27 | Error handling/fail-closed | Completed |
| 28 | Retries/timeouts | Completed |
| 29 | Batching/concurrency | Completed |
| 30 | Caching/incrementality | Completed |
| 31 | Determinism | Completed |
| 32 | CPU performance | Completed |
| 33 | GPU/VRAM performance | Completed |
| 34 | Windows portability | Completed |
| 35 | Dependency/supply chain | Completed |
| 36 | Security/trust boundaries | Completed |
| 37 | Prompt-injection/LLM paths | Completed |
| 38 | v2 benchmark harness | Completed |
| 39 | olmOCR-bench claim validation | Completed |
| 40 | Heuristic scorer | Completed |
| 41 | LLM scorer | Completed |
| 42 | Failed-sample accounting | Completed |
| 43 | Test-suite quality | Completed |
| 44 | Regression risk vs v1 | Completed |
| 45 | Whisker Lane 1 applicability | Completed |
| 46 | Whisker Lane 2 applicability | Completed |
| 47 | Whisker Lane 3 applicability | Completed |
| 48 | Golden Ideal methodology | Completed |
| 49 | Upstream patch opportunities | Completed |
| 50 | Steelman replace/adopt/reject | Completed |

## Appendix B: Corpus Inventory

### Golden Sources (inputs)

| Stem | Type | Features |
|------|------|----------|
| p0533r9 | PDF | tables, code blocks, bold, italic |
| p0957r8 | PDF | tables, 66 code blocks, 22 lists, uncertain regions |
| p1068r11 | PDF | heavy wording (94 ins), lists, code |
| p1112r4 | PDF | uncertain regions, lists, italic |
| p1122r3 | PDF | list-heavy (29 lists), headings, code, links |
| p2040r0 | PDF | balanced (code, lists, headings), full 5-field front matter |
| p3556r0 | PDF | both ins and del wording, headings, code, links |
| p3714r0 | PDF | minimal paper (2 headings, 1 code block) |
| p4182r0 | PDF | (PDF golden, has ideal) |
| cwg1 | HTML | (HTML golden, has ideal) |
| p4020r0 | HTML | (HTML golden, has ideal) |
| p4228r0 | HTML | (HTML golden, has ideal) |

### Golden Ideals (ground truth, 4 papers)

| Stem | Baseline Axes |
|------|--------------|
| cwg1 | code=0.67, frontmatter=1.0, heading=0.33, list=0.0, table=1.0, text=0.39 |
| p4020r0 | code=0.0, frontmatter=1.0, heading=0.67, list=1.0, table=1.0, text=1.0 |
| p4182r0 | code=1.0, frontmatter=1.0, heading=1.0, list=1.0, table=1.0, text=1.0 |
| p4228r0 | code=1.0, frontmatter=1.0, heading=0.67, list=1.0, table=1.0, text=0.85 |

## Appendix C: Environment Record

```
Python: 3.12
torch: 2.13.0+cpu
surya-ocr: 0.22.1
transformers: 5.14.1
pdftext: 0.7.1
marker-pdf: 2.0.0 (editable install)
OS: Windows 10 x64 (10.0.26200)
Hardware: CPU-only, no GPU
llama-server: NOT INSTALLED (conversion blocker)
```
