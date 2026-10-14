# 50 - Steelman Decision

**Verdict:** adopt-component — Marker v2 is a serious general-purpose PDF converter (76% olmOCR-bench, ~5× MinerU throughput) whose Apache-2.0 *code* and deterministic table-recon core are worth selective reuse, but OpenRAIL-M weights, absent WG21 ins/del wording, VLM non-determinism, and whisker's tomd-coupled golden/facts contract forbid replacing `tomd` as the production convert path.
**Confidence:** high
**Decision vs our codebase:** adopt-component (not replace / not contribute-patch-first / not monitor-only)

Clone: `packages/whisker/research/repos/marker-v2.0.0/` @ `947d7688c0739297a7b9eb08b1a463e3a6853981` (tag/tree Marker 2.0.0). Comparison: `packages/tomd/src/tomd/` + root `CLAUDE.md` + `packages/whisker/src/whisker/CLAUDE.md`.

---

## Strongest case FOR replacing tomd with Marker v2

Argue this as if you wanted the merge tomorrow.

1. **Measured quality on a third-party bench tomd does not claim.** Marker balanced scores **76.0%** overall / **83.5%** born-digital on olmOCR-bench (1,403 PDFs; math, tables, multi-column, scans). Evidence: `README.md` Performance + Benchmarks tables (lines ~45, ~456–497). tomd's strength is WG21-tuned heuristics and golden QA (`tomd/CLAUDE.md`), not a published general-PDF leaderboard. For hard layouts, scans, and arXiv-style math (balanced arXiv math **83.9%**), Marker is the better *generic* engine.

2. **Throughput that matters at corpus scale.** On one B200, Marker balanced sustains **2.9 pg/s** vs MinerU pipeline **0.54 pg/s** (~**5×**), fast **7.4 pg/s**, fast-no-OCR **23.7 pg/s**. Evidence: `README.md` Benchmarks / Throughput (~450–517). A mailing-wide reconvert that is GPU-backed finishes in hours, not days, if convert quality is "good enough."

3. **Apache-2.0 code license is clean for integration.** `pyproject.toml:6` `license = { text = "Apache-2.0" }`; README badge and Commercial usage section state code is free commercially. Forking/vendoring *code* into paperflow does not create a GPL trap.

4. **Hybrid modes match our "LLM optional" instinct.** `--disable_ocr` is pure text-layer + 20M layout (CPU); `--use_llm` is opt-in; Ollama is a first-class LLM service (`README.md` Hybrid Mode / LLM services). The architecture already separates cheap digital path from VLM repair — closer to tomd's "deterministic first, LLM for uncertain" story than a full-page VLM-only tool.

5. **Portable pieces are real, not vapor.** `marker/processors/table_recon.py` is explicitly "trimmed to the deterministic, per-block core" with a deterministic judge (module docstring L1–8). Span schema already carries bold/italic/code/underline (`marker/schema/text/span.py:26–39`). Extensible `--processors` / `ConfigParser` surface (`README.md` Usage) is an adoption seam for WG21 post-processors without owning the whole stack.

6. **Whisker already wants a stronger second converter.** Whisker's oracle is markitdown (`reference.py:16–32`, `REFERENCE_ENGINES = ("markitdown",)`), scored advisory-only. Marker as an optional `REFERENCE_ENGINES` entry would raise the advisory signal on tables/math without touching the hard gate — the FOR case for *adoption*, and the thin edge of a replace narrative ("prove Marker beats tomd on Lane 2/3, then flip convert").

7. **Scanned / image-heavy PDFs are an admitted tomd gap.** tomd CLAUDE.md: scanned-page PDFs trip the 20-image cap and produce image-free markdown (`improvements.md` §4 cited in CLAUDE). Marker balanced's job is exactly that gap (old scans categories on the bench).

**Net FOR:** if paperflow's convert problem were "best markdown from arbitrary PDFs at GPU scale," Marker balanced wins the bake-off on public numbers, and Apache-2.0 code makes a hard fork legally tractable.

---

## Strongest case AGAINST replacing tomd with Marker v2

Argue this as if replace were malpractice.

1. **Code Apache-2.0 ≠ model OpenRAIL-M; shipping convert on Marker weights is a license and sovereignty failure.** README badges and Commercial usage (`README.md:9–10, 63–65`): model weights are modified AI Pubs OpenRAIL-M — free for research/personal/startups under **$5M** funding/revenue; commercial beyond that needs Datalab pricing. Root `CLAUDE.md` Invariants: "Public and reproducible. Anyone can clone this repo, run `paperflow dissect <pid>`, and replicate… No proprietary dependencies." Pulling OpenRAIL-gated weights into the default convert path breaks that contract for Alliance-scale commercial use and for random cloners who cannot accept Datalab's model terms. Model sovereignty (`CLAUDE.md:64–70`) requires open-weight models *under our control* (Gemma/Qwen/vllm_thinking); Surya/Marker artifacts from `models.datalab.to` (`marker/settings.py` `ARTIFACT_URL`) are not that stack. Default `--use_llm` is Gemini (`README.md:53`) — the opposite of sovereignty.

2. **WG21 ins/del wording is load-bearing in tomd and absent in Marker.** tomd PDF path step 8 is wording detection via HSV + strikethrough (`tomd/CLAUDE.md:21`, `lib/pdf/wording.py` `is_green_ins` / `is_red_del` / two-pass del). Emit produces `:::wording-add` / `:::wording-remove` / `<ins>`/`<del>` (`lib/pdf/wording_emit.py`, `lib/wording_cleanup.py`). HTML path renders wording divs (`lib/html/render.py:773–793`). Marker's `Span.formats` Literal set is plain/math/chemical/bold/italic/highlight/subscript/superscript/small/code/underline — **no strike, no ins/del, no color role** (`span.py:26–39`). A replace silently destroys the normative-diff signal LEWG/LWG readers and Lane-3 wording facts care about. That alone is a hard reject for "replace tomd."

3. **Determinism / Lane-1 golden contract.** tomd is dual-path MuPDF + spatial, confidence-flagged, no required VLM (`tomd/CLAUDE.md:5, 52–63`). Whisker Lane 1 (`golden.py`) byte-compares normalized markdown to committed `expected.md`; CLAUDE.md for whisker: deterministic, no LLM/network/randomness in the gate. Marker balanced/fast OCR routes through a Surya VLM server (`models.py:23–28`, `README.md:96`); continuous-batch VLM decode is the same class of variance `CLAUDE.md` Determinism and whisker tapetum docs already reject for gating (≥25% verdict-flip cited for LLM lane). Replacing convert with Marker would force a golden corpus rewrite *and* accept run-to-run drift unless permanently pinned to `--disable_ocr` — which scores **43.6%** overall / **0.0** arXiv math (`README.md:462, 488–496`), i.e. you paid for Marker and threw away its quality.

4. **Windows portability vs our actual developer surface.** User environment is win32; tomd deps are pymupdf/bs4/mistune/ftfy (`packages/tomd/pyproject.toml:8–14`) — native and light. Marker requires PyTorch (`README.md:73`), `torch>=2.7`, `transformers`, `surya-ocr` (`pyproject.toml:12–33`), and spawns vLLM **via Docker** on NVIDIA or llama.cpp elsewhere (`README.md:96`). That is a non-starter as the default local `paperflow convert` path on Windows laptops without WSL/Docker GPU theater. MPS fallbacks exist for Apple (`settings.py:42–43`); Windows is not a first-class documented happy path.

5. **Whisker is defined as QA for tomd, not a free-floating converter marketplace.** `whisker/CLAUDE.md:7–8, 36–37, 127–133`: "deterministic QA for tomd conversions"; depends on tomd; golden ideals live under `packages/tomd/tests/fixtures/golden/ideals/`; score-file/check-facts bridge tomd golden-QA. Replace-convert means re-blessing every corpus `expected.md`, re-authoring ideals, and re-validating Lane 3 facts against a new markdown dialect (front matter order, TOC strip, HTML `<table>` emit). Cost is months of QA debt for a gain that is mostly "better on non-WG21 PDFs."

6. **WG21 product surface Marker does not implement.** Strict YAML front-matter order (`CLAUDE.md` + `tomd/CLAUDE.md:147–182`), eight HTML generator families, TOC strip contract, uncertain markers + prompts.json, glyph placeholders, vector-figure opt-in — none of this is Marker's problem statement. Marker converters on disk are `pdf` / `ocr` / `table` only (`marker/converters/`). HTML/PPTX/DOCX need `[full]` extras and are not the WG21 mailing dual-path.

7. **Dependency blast radius.** Pulling torch/surya into the workspace venv contaminates every package resolve; tomd's "four runtime deps" invariant (`tomd/CLAUDE.md` runtime deps note) exists for CI hermeticity and clone-and-run. Marker is a product, not a library-shaped dependency.

**Net AGAINST:** replace trades a WG21-specialized, deterministic, Windows-friendly, BSL-self-contained converter for a GPU VLM pipeline whose *weights* are OpenRAIL-encumbered, whose output is non-stable under the mode that scores 76%, and which cannot emit wording diffs. That fails CLAUDE.md on reproducibility, sovereignty (for any VLM/LLM-boosted path), and product fidelity.

---

## Findings

- [CRITICAL] **OpenRAIL-M model license + $5M commercial cliff blocks default adoption of Marker weights.** Evidence: `README.md:9–10, 63–65`; `marker/settings.py` `ARTIFACT_URL`. Impact: cannot make Marker the production convert engine without a Datalab commercial deal *or* a weights-free `--disable_ocr` path that abandons the 76% claim.

- [CRITICAL] **ins/del wording exists in tomd (PDF+HTML) and has no Marker schema/render counterpart.** Evidence: `tomd/lib/pdf/wording.py`, `wording_emit.py`, `html/render.py:773+` vs `marker/schema/text/span.py:26–39`. Impact: replace is a normative-content regression for WG21 papers; not a "post-process later" gap.

- [HIGH] **76% / ~5× MinerU are real, but wrong leaderboard for our ship decision.** Evidence: Marker `README.md` bench tables; whisker/tomd optimize for WG21 golden + facts, not olmOCR macro-average. Impact: FOR case wins on general PDF; AGAINST wins on *our* acceptance tests.

- [HIGH] **VLM path conflicts with convert determinism and Lane-1 goldens; disable_ocr path conflicts with quality claims.** Evidence: `models.py` SuryaInferenceManager; bench overall 76.0 vs 43.6 no-OCR; whisker `CLAUDE.md` Lane 1 + determinism. Impact: no Marker mode simultaneously satisfies (stable goldens) and (76% quality).

- [HIGH] **Model sovereignty / default Gemini LLM boost.** Evidence: root `CLAUDE.md:64–70`; Marker `README.md:53` default `gemini-3.5-flash`. Impact: production convert must not grow a cloud-LLM dependency; Ollama-only still leaves Surya OpenRAIL OCR as the accuracy engine.

- [MED] **Deterministic `table_recon.py` is the highest-leverage portable component.** Evidence: `table_recon.py:1–8`, CPU text-layer grids, deterministic judge. Impact: adopt-component target #1 for tomd table quality without importing Surya.

- [MED] **Windows + Docker-vLLM is a portability cliff for the claimed balanced mode.** Evidence: `README.md:96`; user_info win32; tomd pymupdf-only. Impact: replace would split "works on Alliance GPU pod" from "works on contributor laptop."

- [MED] **Whisker oracle pluggability is the safe adoption seam.** Evidence: `reference.py` `REFERENCE_ENGINES`; advisory-only `ref_nid` (`whisker/CLAUDE.md`). Impact: Marker can raise advisory disagreement without owning `paperflow convert`.

- [LOW] **Apache-2.0 code + processor hooks make contribute-patch *possible* but low ROI for wording.** Evidence: Span format enum would need strike/color + a color-aware builder; Marker's layout path is VLM-centric, not HSV drawing correlation. Impact: upstreaming tomd wording is a multi-PR research project, not a quick patch — prefer local retain.

## False-pass hypothesis

Declaring "replace" because Marker scores 76% on olmOCR-bench while a WG21 wording paper's green/red strikethrough collapses to plain prose — whisker Lane 2 NID stays high (text present) and Lane 3 wording/order facts fail or are never authored, so the portfolio looks "better converted" while normative diffs are gone.

## False-fail hypothesis

Rejecting *all* Marker contact because OpenRAIL forbids *weight* redistribution — thereby ignoring Apache-2.0 `table_recon` heuristics and a disable_ocr/CPU research oracle that never loads OpenRAIL weights. That would false-fail the adopt-component option.

## What would change my mind

Flip **to replace** only if *all* of: (1) Datalab grants Alliance-compatible redistribution of needed weights *or* a fully self-hosted non-OpenRAIL OCR/layout stack under our control matches ≥ tomd golden/facts on a fixed WG21 holdout; (2) Marker (or our fork) emits wording-equivalent markup with measured recall on a wording-heavy PID set; (3) a pinned deterministic mode (seeded VLM *or* text-layer-only) byte-stabilizes Lane-1 goldens; (4) Windows contributors can `paperflow convert` without Docker GPU. Flip **to monitor-only** if even optional Marker-in-venv torch cost is rejected by maintainers. Flip **to contribute-patch** as primary only if Datalab accepts a wording/color span PR and we intend Marker-hosted convert (unlikely given sovereignty).

---

## Dimension scorecard

| Dimension | Replace? | Evidence anchor |
|---|---|---|
| License (code) | Friendly | Apache-2.0 `pyproject.toml:6` |
| License (models) | Hostile to default ship | OpenRAIL-M + $5M cliff `README.md:63–65` |
| Quality (olmOCR 76%) | Strong FOR general PDF | Bench tables `README.md` |
| Speed (~5× MinerU) | Strong FOR GPU fleet | 2.9 vs 0.54 pg/s |
| WG21 wording | Hard AGAINST | tomd `wording.py` vs Span formats |
| Model sovereignty | Hard AGAINST for VLM/LLM modes | `CLAUDE.md:64–70`; Gemini default |
| Determinism / goldens | Hard AGAINST for OCR modes | whisker Lane 1; Surya server |
| Windows portability | AGAINST for balanced | Docker vLLM; torch stack |
| Whisker lanes | AGAINST replace; FOR optional oracle | `reference.py`; tomd ideals |

---

## Final verdict

**adopt-component**

Do **not** replace `packages/tomd` with Marker as `paperflow convert`. Do **not** treat contribute-patch as the main line (wording upstream is the wrong architecture bet). Do **not** merely monitor: the deterministic table-recon core and the optional advisory-oracle experiment are actionable now.

Concrete adopt-component moves (priority order):

1. **Study/port** Marker's deterministic `table_recon` ideas into tomd's table path (Apache-2.0 code, no weights).
2. **Optional research/oracle only:** wire Marker behind an explicit non-default whisker `REFERENCE_ENGINES` entry or a scratch A/B harness on Alliance GPU — never the convert persistence path; prefer `--disable_ocr` or document OpenRAIL acceptance for research weights.
3. **Keep** tomd wording, front matter, HTML generators, and golden/facts corpus as the production contract.
4. **Monitor** Marker/Surya license and Chandra self-host terms; re-open replace only under the flip conditions above.

**Rejected alternatives:** `replace` (wording + OpenRAIL + determinism + Windows); `contribute-patch` as primary (wrong leverage vs local wording retain); `monitor-only` (under-uses Apache-2.0 table_recon and oracle seam).
