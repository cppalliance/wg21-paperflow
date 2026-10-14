# opus-D — Ground-Truth / Provenance / Risk-Claim Re-Verification

Meta-reviewer D. Every provenance-sensitive claim below was re-checked against the
actual file on disk (not the persona's summary). Repos under
`packages/whisker/research/repos/` are git-ignored, so Glob/Grep miss them; all
repo reads were done via direct `Read` / `cmd dir`. Verdict tags: **VERIFIED**
(claim holds as stated), **CORRECTED** (claim holds but a fact was wrong or
scoped wrong), **DROPPED/OVERSTATED** (claim's severity or framing is not
supported by the file), **UNPROVEN** (claim cannot be established from the cited
artifact).

---

## 1. surya license (claim: GPL? OpenRAIL-M? revenue-capped? + does OCRErrorPredictor exist)

**VERIFIED (persona 26 accurate, incl. the "GPL is not the issue" call).**

Two license files exist in the repo root:

- `packages/whisker/research/repos/surya/LICENSE` — **Apache License 2.0**, verbatim (`LICENSE:1-51`). This covers the **source code only**.
- `packages/whisker/research/repos/surya/MODEL_LICENSE` — **"AI PUBS OPEN RAIL-M LICENSE (MODIFIED)", Version 0.1** (`MODEL_LICENSE:1-3`). This covers the **model weights/checkpoints**.

Exact terms confirmed in `MODEL_LICENSE`:
- **Revenue cap** (`Attachment A, Commercial 2(a)`, `MODEL_LICENSE:56`): no commercial use if you generated more than the stated cap in prior-year gross revenue (except personal/research use).
- **Funding cap** (`Commercial 2(b)`, `:57`): same trigger on total equity/debt funding raised.
- **Competing-product ban** (`Commercial 2(c)`, `:58`): no use if you make available a product/service that competes with the Licensor (datalab.to). Commercial license URL: `:59` (`https://www.datalab.to/`).
- **Share-a-Like** (`Section 8`, `MODEL_LICENSE:39`): the license must apply to Model derivatives **and to Output and derivatives of the Output**.
- **Use-based restrictions must be flowed down** to downstream users (`Section 4/5`, `:31,36`).

**Correction to persona 26's numbers (license is internally inconsistent, not persona 26's error):** the cap lines write the amount two ways in the same clause — the **words say "two million US Dollars"** while the **numeral says "$5,000,000"** (`MODEL_LICENSE:56-57`, both). Persona 26 quoted the numeral (`$5,000,000`); that is a literal quote, but any downstream legal memo must flag the word/numeral discrepancy in the upstream license itself.

**It is NOT GPL.** Persona 26's explicit statement "GPL is not the issue here, OpenRAIL-M revenue/compete/share-alike is" is correct and important: the code is Apache-2.0, the weights are the encumbrance.

**OCRErrorPredictor exists — VERIFIED.** `surya/ocr_error/__init__.py:13` defines
`class OCRErrorPredictor(BasePredictor)`. `__call__(self, texts: List[str], ...)`
(`:18`) → text-only, no image input. Inference is a hard `logits.argmax(dim=1)`
(`:47`) inside `settings.INFERENCE_MODE()` (`:45`), returning
`OCRErrorDetectionResult(texts=..., labels=[ID2LABEL[p] ...])` (`:50-51`). Default
batch sizes `{"cpu": 8, "mps": 8, "cuda": 64}` (`:16`). Persona 26's "text-only,
binary argmax, no confidence threshold" characterization is faithful to the code.

---

## 2. olmOCR weights license (claim: Apache 2.0 per 05-web.md — consistent?)

**VERIFIED-as-consistent, with a provenance boundary.**

- On disk: `packages/whisker/research/repos/olmocr/LICENSE` = **Apache 2.0** (code/toolkit). That is all the repo ships.
- `05-web.md` Q1 and Q2 both assert the **weights** (`allenai/olmOCR-2-7B-1025-FP8`, BF16 sibling, and the 0225 preview) are **Apache 2.0** — internally consistent across the two cards.
- **Boundary:** the weights license is a HuggingFace model-card claim, **not locally verifiable from this workspace** (no weights, no `MODEL_LICENSE` in the olmocr repo). Unlike surya — where a `MODEL_LICENSE` file let me prove OpenRAIL-M on disk — the olmocr weights-Apache claim rests entirely on the web card. Treat it as HIGH-confidence-web, not disk-verified. The **contrast with surya is the key provenance point**: olmocr = permissive (if the card is accurate), surya weights = encumbered.

---

## 3. Security claim: does olmocr splice raw PDF text into prompts? (personas 10 vs 20 CONTRADICT)

**CONTRADICTION RESOLVED. WINNER: persona 20. Persona 10's [CRITICAL] live-path framing is OVERSTATED.**

Read of `olmocr/olmocr/pipeline.py` and `olmocr/olmocr/prompts/prompts.py`:

- **Production inference path** = `build_page_query()` → `try_single_page()`. The user message content is exactly two parts: `{"type":"text","text": build_no_anchoring_v4_yaml_prompt()}` then the base64 image (`pipeline.py:138-141`). `build_no_anchoring_v4_yaml_prompt()` (`prompts.py:164-170`) is a **static instruction string with NO `RAW_TEXT` and NO PDF text interpolation**. This is the only prompt `build_page_query` ever sends.
- **`RAW_TEXT_START`/`RAW_TEXT_END` splicing lives in NON-production prompts:**
  - `build_openai_silver_data_prompt` / `_v2` (`prompts.py:7-32`) — commented "prompt we use for getting chat gpt 4o to convert documents into our **silver training data**". Training-data generation, not inference.
  - `build_finetuning_prompt` (`prompts.py:147-153`) — commented "base prompt used for **training and running the fine tuned model**", but the actual production `build_page_query` does **not** call it. Persona 20 correctly locates real usage in `train/` + bench.
- **`make_fallback_result` (`pipeline.py:233-250`)** does call `get_anchor_text(..., pdf_engine="pdftotext")`, but that pdftotext string is written into the **output** field `PageResponse.natural_text` — it is NOT fed back into any LLM prompt.

**Resolution:** the live olmocr path is image + static instruction, **zero raw-PDF-text-into-prompt**. Persona 20 states this precisely. Persona 10 tagged "olmocr additionally splices raw PDF text into prompts unescaped" as **[CRITICAL]** — yet persona 10's own evidence sentence concedes "olmocr ships image + static text only in the live path". Persona 10 is therefore **self-contradictory** and conflates a training/bench pattern with production. The **valid** residue of persona 10's point is a *porting hazard* ("do not copy the `RAW_TEXT_*` finetuning prompt into a QA lane"), which is real but is **not a production vulnerability in olmocr** and should not carry CRITICAL-live severity. Persona 20 also independently recommends dropping the anchor/pdftotext path — the two agree on the action, they disagree only on whether it is a live olmocr fact (it is not).

---

## 4. SERVICES.toml VRAM-full claim for alliance-pod (claim: no room / no vision service)

**SPLIT VERDICT. "No vision service" = VERIFIED. "alliance-pod VRAM is full / no room" = UNPROVEN from SERVICES.toml (inference, not a recorded fact).**

Read of `SERVICES.toml` in full:

- **VERIFIED:** every `[services.*]` LLM entry is `backend = "vllm_thinking"` or `backend = "anthropic"`. Models: `deepseek-v4-pro` (×2 pods), `deepseek-r1-distill-70b`, `google/gemma-4-31B-it`, `Qwen/Qwen3.6-27B`, `Qwen/Qwen3-235B-A22B-FP8`, `Qwen/Qwen3-32B`, `claude-opus-4-6` (`:47-164`). **No vision model, no `vision_capable` flag** (only `thinking_capable`/`tools_capable`). Personas 00 and 30 are correct that a VLM is a new service + new backend key.
- **CORRECTION / UNPROVEN:** `SERVICES.toml` records **no VRAM, no GPU count, no `--tensor-parallel-size`, no `--gpu-memory-utilization`, no `--max-num-seqs`** — none of it. Persona 30's [CRITICAL] "alliance-pod GPU is saturated … a 7B VLM cannot share it" is **not derivable from SERVICES.toml**; it is inferred from (a) the *sibling* pod's NAME `h200x8-deepseek-v4-pro` and (b) an external batching-research doc. The `alliance-pod` entry itself (`:64-74`) has **no hardware spec at all** — only `base_url`, `model = deepseek-v4-pro`, `max_context_window = 393216`, and a comment that it "Runs 24/7; billed per hour of uptime, NOT per token". Note `alliance-pod` and `h200x8-deepseek-v4-pro` are **two distinct running instances** (different `base_url`), same model.
- **Net:** the *conclusion* (need a second pod for a VLM) is reasonable, but the provenance is an **inference from a pod name**, not a VRAM figure in the config. Model boundary: this flips if the actual `alliance-pod` GPU allocation is ever recorded. Do not cite SERVICES.toml as evidence of VRAM saturation; cite it only for "no vision service exists today".

---

## 5. Fidelity: what ACTUALLY happens when one chunk fails (chunking.py + adjudicate.py)

**VERIFIED (persona 34's "one failed chunk aborts the whole paper" is correct) + one CORRECTED doc/code discrepancy.**

Read of `adjudicate.py` chunk loop (`:209-223`) and error stub (`:506-519`), plus `chunking.py`:

- The oversize chunk loop is:
  ```
  for index, chunk in enumerate(chunks):
      parts.append(await run_agent(ctx, spec, user_msg))   # adjudicate.py:222
  state.tier1 = aggregate_adjudications(parts, len(chunks))
  ```
  There is **NO `try/except` around `run_agent`**. If any chunk's `run_agent` raises (schema-retry exhaustion or connection error), the exception propagates out of `_custom_triage`; `aggregate_adjudications` is never reached, `state._result` is never set, and `adjudicate_paper` returns the terminal stub `TapetumResult(suggested_verdict=review, confidence=0.0, status="error", primary_concern="pipeline did not produce a result")` (`:507-519`). **No 11-of-12 partial aggregate is ever emitted.** This is fidelity-correct (fail-not-partial) for the current markdown lane.
- The single-chunk path (`:210-213`) behaves identically: a raised `run_agent` → `status="error"`.
- `chunk_markdown` (`chunking.py:129-164`) returns `partial=True` **only** when a single H2 section exceeds `max_chars` and is hard-split (`:148-150`). `_custom_decide` then forces `pass → review` when `state.partial` (`adjudicate.py:303-304`). `aggregate_adjudications` also defensively returns `review, confidence 0.0` on empty `parts` (`chunking.py:239-248`), but that branch is unreachable in the failed-chunk case (exception fires first).

**CORRECTED (doc/code mismatch, genuine provenance nit):** `_PipelineState.partial`'s
docstring claims the flag is set when "a single H2 section larger than the budget
was hard-split, **or a chunk call failed**" (`adjudicate.py:163-166`). **No code
path sets `partial=True` on a failed chunk call.** `state.partial` is assigned
exactly once, from `chunk_markdown`'s return (`:216`). A failed chunk aborts to
`status="error"` (which is *stronger* than partial-review, so safety is not
harmed), but the docstring overstates the mechanism. Persona 34's finding stands;
the code comment is the thing that is wrong.

---

## 6. Corpus composition: "198/387 papers are HTML-only" (claim vs baseline's "189 PDFs")

**VERIFIED — and it exposes an undercount in the baseline that several personas inherited.**

`data/paperstore` counts (direct `dir` enumeration):
- `.pdf` = **189**
- `.html` = **198**  (`.htm` = 0)
- pids present as BOTH pdf and html = **0** (Compare-Object on stems)
- ⇒ **189 + 198 = 387 source papers; 198 (51.2%) are HTML-only with no PDF sibling.**

The user's "198/387 HTML-only" is **exactly correct**.

**Provenance impact (upgrade this):** `00-baseline.md:80` says "189 PDFs … also 189
total under `data/`" and frames the corpus as 189 papers. That silently **drops
the 198 HTML papers**. Consequences:
- A **VLM-on-PDF** QA lane is **structurally inapplicable to 51% of the corpus** — HTML papers have no PDF to rasterize. Any "always feed the original PDF" mandate (`00-baseline.md:5`) covers at most 189/387 papers; the other 198 need a different (DOM/screenshot) path or are excluded.
- Persona 15's review-queue math uses a "189-PDF corpus" denominator (`15:10`) and its 189-scaled projections; the correct source denominator is 387, and the PDF-eligible denominator is 189. Its *ratios* on the det-pass tier are unaffected, but any "corpus-wide" scaling to 189 understates total papers by ~half.

---

## Summary table of dispositions

| # | Claim | Disposition |
|---|-------|-------------|
| 1 | surya weights = OpenRAIL-M (rev/funding cap, compete ban, share-a-like); code = Apache; not GPL | **VERIFIED** (note license's own "two million"/"$5,000,000" word-vs-numeral inconsistency) |
| 1 | `OCRErrorPredictor` exists, text-only, argmax | **VERIFIED** (`ocr_error/__init__.py:13,18,47`) |
| 2 | olmOCR weights Apache 2.0 | **VERIFIED-consistent** (web/HF card; code LICENSE on disk is Apache; weights not disk-verifiable) |
| 3 | olmocr splices raw PDF text into prompts (persona 10 CRITICAL) | **DROPPED/OVERSTATED**; production path is image+static prompt (`pipeline.py:138-141`, `prompts.py:164-170`). Persona **20 wins**. |
| 4 | alliance-pod VRAM full / no room (persona 30 CRITICAL) | **UNPROVEN from SERVICES.toml** (no VRAM fields; inferred from pod name). "No vision service" = **VERIFIED**. |
| 5 | one failed chunk aborts the whole paper → status=error, no partial (persona 34) | **VERIFIED**; plus **CORRECTED** `_PipelineState.partial` docstring overstates ("or a chunk call failed" sets no flag). |
| 6 | 198/387 papers HTML-only | **VERIFIED** (0 pdf/html overlap; baseline's "189 papers" undercounts; VLM-on-PDF covers ≤189/387). |
