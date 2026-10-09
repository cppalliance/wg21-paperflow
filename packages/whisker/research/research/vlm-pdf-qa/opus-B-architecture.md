# opus-B - Architecture adjudication (soundness of proposed architecture/gates)

**Meta-reviewer:** Opus B. **Mandate:** decide ONE architecture for feeding original PDFs to the whisker LLM QA lane, independent of the deterministic lane, fused afterward. **Method:** code-verified re-check of the load-bearing claims, then adjudication of contenders A/B/C/D against the operator directive and the five hard constraints.

Operator directive (verbatim intent): the LLM lane must ALWAYS receive the original PDF; the deterministic lane and the LLM lane judge INDEPENDENTLY; the two verdicts are compared/fused afterward. German original: *"deterministisch ist deterministisch und LLM ist LLM, die prüfen unabhängig voneinander und vergleichen dann die Ergebnisse."*

---

## 0. Re-verification of load-bearing claims (read the code, not the reports)

| Claim under test | Verdict | Evidence (file:line, read this session) |
|---|---|---|
| `adjudicate.py` injects deterministic signals into the LLM prompts | **TRUE** | `_build_triage_message` embeds `Whisker verdict:`, `Flags:`, and `Metrics: uni=/cov=/lossy_tables=/table_errors=/mojibake=` into every triage header before the markdown — `adjudicate.py:379-392`. `_build_adjudicate_message` repeats `Whisker verdict:`, `Flags:`, `Escalation signals:` for tier-2 — `adjudicate.py:413-424`. The lane sees det's conclusion before it reads anything (32-independence-purist CRITICAL #1 confirmed verbatim). |
| Fusion consumes ONLY verdict fields, never prompt text | **TRUE** | `fuse_verdicts(whisker, tapetum)` reads exactly: `whisker.verdict`, `soft_flags`, `hard_flags`, `ref_nid`; `tapetum.suggested_verdict`, `confidence`, `axis_findings[].{verdict,severity}`, `status` — `fusion.py:117-227` (`_tapetum_is_usable` :85-93, `_has_major_axis_fail` :96-101, branches :142-227). Zero prompt text touched. **Corollary:** stripping det signals from the LLM prompt is a safe, fusion-preserving change (32-independence CRITICAL #2 confirmed). |
| Evidence is grounded ONLY against the converted markdown | **TRUE (and decisive)** | `ground_spans(spans, markdown)` grounds `EvidenceSpan.quote` against `state.paper_md` — `grounding.py:170-240`; `EvidenceSpan.quote` docstring "must be an exact substring of the converted markdown" — `models.py:50-60`. `_custom_decide` demotes any ungrounded non-pass to `review` — `adjudicate.py:295-296`. So a FAIL whose evidence lives only in the PDF pixels (the defect is absent from / wrong in the markdown) is demoted to `review`, then `llm==fail` is false, so `llm_escalate_major` never fires — `fusion.py:206`. Image-only findings are structurally swallowed. |
| No page attribution anywhere in the tapetum result | **TRUE** | `EvidenceSpan` (axis/quote/reason), `AxisFinding` (axis/verdict/severity/note), `TapetumResult`, `to_dict` all lack a `page` field — `models.py:50-141` (17-downstream-consumer CRITICAL #2 confirmed). |

Both operator-named claims hold. The grounding-contract and page-attribution facts are the two constraints the personas under-weighted and they drive the decision below.

---

## 1. Verdict per contender

### (A) VLM-as-judge per page: image-only inventory, then deterministic compare
**Verdict: sound-but-costly (independence-clean, second choice).**
- Independence: HIGHEST of the judge options. The VLM never sees the markdown or det signals; the compare is deterministic Python. Two genuinely independent lanes, then compare — a literal reading of the directive (32-independence-purist rates only (A) or a decontaminated (B) as directive-compliant).
- Hallucination: the inventory-extraction step still runs a zero-shot-ish VLM exposed to HQH ~60% OCR-category hallucination and MTabVQA 37% EM / 2.1-11.8% open-source on rendered tables (`05-web.md` Q4), but the deterministic COMPARE catches token-preserving swaps structurally instead of letting the VLM confirm the markdown (no anchoring bias, unlike B).
- Grounding: the compare emits defects locatable in the markdown, so evidence CAN ground; not hobbled the way B is by image-only findings.
- Page attribution: NATURAL — an inventory is per-page; (A) is the only judge that structurally solves the page-attribution CRITICAL, IF a `page` field is added.
- Cost: HIGHEST net-new build. Requires (i) the full multimodal pipeline thread (new keyword-only `user_media`, a new `VllmVisionBackend`, a `vision_capable` service — 31-integrator CRITICAL/HIGH), (ii) a robust structured page-inventory schema (Dolphin's layout-inventory is the closest analogue but is CONVERSION, free-text, needs D6 wrapping — 23-dolphin-analyst), and (iii) a brand-new deterministic comparator module.

### (B) VLM-as-judge per page: image + markdown slice, direct judging
**Verdict: REJECTED as primary.**
- Independence: FAILS the directive. (B) is a SINGLE fused image+markdown judgment, not two independent lanes that compare afterward. It shares 100% of det's scored artifact (the tomd markdown) as VLM input (32-independence: perfect input correlation).
- Hallucination: WORST profile. The judge sees the markdown and the page together; HQH ~60% OCR hallucination + anchoring bias means it confirms corrupted markdown it "reads" off the image (13-adversary CRITICAL; 18-skeptic false-pass P3844-class).
- Grounding: its groundable evidence, by construction, only covers defects VISIBLE in the markdown slice it was shown — which DEFEATS the entire purpose of opening the PDF (image-only defects produce ungrounded fails → demoted to review → swallowed by fusion, per §0).
- Alignment: tomd emits no page markers; pairing a page image to a markdown slice is an unsolved alignment problem (13-adversary CRITICAL, 32-independence HIGH).
- Only acceptable as a decontaminated INTERIM inside (D), never as the architecture.

### (C) VLM-as-second-converter (olmOCR-style transcription) + deterministic diff vs tomd
**Verdict: RECOMMENDED.**
- Independence: HIGH and clean. olmOCR transcribes the PDF from pixels, never sees tomd's markdown or det signals; a deterministic diff compares two independent extraction paths, then fuses. Directive-compliant (an LLM/VLM DOES receive the original PDF; the lanes are independent; the compare is afterward).
- Hallucination: DECISIVELY the lowest. olmOCR-2-7B is a purpose-built, finetuned CONVERSION model (Apache-2.0, olmOCR-Bench 82.4%, tables 84.9 — `05-web.md` Q1/Q2), NOT a zero-shot judge staring down the 60% OCR / 37% table-EM wall. This is exactly the product-decision-skeptic's #1 recommendation and the independence-purist's structural mitigation.
- Grounding: SIDESTEPS the killer contract entirely. (C) does not use `EvidenceSpan`/`ground_spans` at all; it produces deterministic agreement scores (reuse `text_nid`/`teds`/table scoring). No image-only-evidence demotion, no swallowed findings.
- Cost: LOWEST net architecture. It EXTENDS whisker's existing second-converter oracle pattern (`score.py` already runs markitdown as a second converter and scores agreement; `reference.py` `REFERENCE_ENGINES` is pluggable — whisker `CLAUDE.md`). No pipeline multimodal message-type plumbing is required: olmOCR runs on its OWN vLLM OpenAI-compatible endpoint and returns markdown that whisker diffs deterministically. The 31-integrator CRITICAL cost (threading images through `run_agent`/`ModelBackend.run`) is AVOIDED.
- HTML-only (51%): degrades cleanly — the oracle already handles HTML via markitdown; (C) simply keeps the markitdown oracle for the 198 HTML papers and adds an olmOCR oracle for the 189 PDFs.
- Page attribution: olmOCR is per-page, so per-page diff findings are available.
- Known weaknesses (bound the fallback): correlated errors when BOTH converters miss the same element (24-nougat false-pass), and diff format-sensitivity (24-nougat MED false-fail). Both are measurable on a labeled holdout and are the trigger for (D).

### (D) Hybrid tiers
**Verdict: FALLBACK (and the natural growth path).**
- Shape: (C) as the always-on, cheap, hallucination-resistant independent PDF lane for ALL 189 PDFs; escalate ONLY the papers where the deterministic diff DISAGREES (or existing det risk-signals fire) to a decontaminated (A)-style image-only-inventory VLM judge for a semantic second read on the contested pages.
- Why fallback not primary: it pays the FULL multimodal-pipeline cost (31-integrator) on top of (C), so it is only justified once (C)'s labeled-holdout numbers prove the diff alone misses the target class. It also directly answers the skeptic's "value is narrow / cost front-loaded" objection by spending the expensive judge only where two independent transcriptions already disagree.

---

## 2. Decision

**Adopt (C): VLM-as-second-converter (olmOCR-style transcription) + deterministic diff against tomd, implemented as an independent whisker deterministic advisory axis (extending the existing oracle/`reference.py` pattern), NOT inside the det-contaminated `tapetum_llm` prompt lane.**

**Fallback: (D)** — keep (C) as the cheap always-on independent PDF lane; add a decontaminated, image-only-inventory (A)-style VLM judge fired ONLY on papers where (C)'s diff disagrees or det risk-signals fire, with mandatory page attribution and evidence grounded to markdown. Trigger the fallback iff a labeled holdout (>=30 WG21 PDFs) shows (C)'s diff misses the token-preserving semantic-corruption class at an unacceptable rate or false-fails on formatting drift beyond ~10%.

**Explicitly REJECT (B) as the architecture:** it violates lane independence (single fused image+markdown judgment), has the worst hallucination/anchoring exposure, and its groundable evidence only covers markdown-visible defects — the one thing the PDF lane must transcend.

**Gate additions required regardless of contender (from §0 code facts):**
1. Strip all det signals from any surviving LLM prompt (32-independence contamination checklist; `adjudicate.py:379-392,413-424`). (C) inherits this for free by not using the prompt lane.
2. Add a `page` field to any per-page finding surfaced to operators (`models.py:50-141` gap).
3. Add a `schema_version` to the tapetum sidecar before extending it (17-downstream HIGH; `models.py:118-141`).
4. Add an explicit `source_kind` (pdf/html/none) branch so the 51% HTML corpus degrades to a defined state, never `llm: -` ambiguity (17-downstream CRITICAL).
5. Keep the VLM/second-converter OFF the `whisker --gate` contract; fusion stays advisory (`fusion.py:12-13`).

---

## 3. Top 5 verified constraints that drove the decision

1. **The markdown-grounding contract swallows image-only findings.** `ground_spans` binds `EvidenceSpan.quote` to `state.paper_md` (`grounding.py:170-240`, `models.py:50-60`); an ungrounded non-pass is demoted to `review` (`adjudicate.py:295-296`), so `llm_escalate_major` never fires (`fusion.py:206`). Any judge whose evidence lives in pixels (A/B) is hobbled; a deterministic-diff second-converter (C) sidesteps the contract entirely. **Decisive against B, cost-adds to A, free for C.**
2. **Zero-shot VLM-as-judge hallucination is uncontrolled; a finetuned converter is not.** HQH ~60% OCR-category hallucination, MTabVQA 37% EM (frontier) / 2.1-11.8% (open-source) on rendered tables, DOCR-Inspector needs a 7B finetune (`05-web.md` Q4/Q5). olmOCR-2-7B is Apache-2.0, olmOCR-Bench 82.4% (`05-web.md` Q1/Q2). **(C) trades an unbounded judge risk for a measurable converter-agreement signal.**
3. **The pipeline has NO multimodal path; adding one is the dominant cost of A/B/D.** `run_agent`/`AgentBackend.run`/`ModelBackend.run` all type `user_message: str`; `inject_untrusted` is text-only (00-baseline:72-73; 31-integrator CRITICAL). (C) needs a vision vLLM SERVICE but NOT the image-through-`run_agent` plumbing, because olmOCR returns markdown that whisker diffs deterministically. **(C) is the lowest net-new architecture; it extends the existing pluggable oracle (`reference.py` `REFERENCE_ENGINES`).**
4. **51% of the corpus is HTML-only; "always PDF" is undefined for half of it.** 198/387 HTML-only, 189 PDFs, 0 with both (17-downstream CRITICAL; `get_source_path` returns whatever is staged, `sqlite_backend.py:1119-1135`). (C) degrades to the existing markitdown oracle for HTML with zero new branches; A/B/D's judge simply cannot run on HTML and needs an explicit no-PDF state.
5. **Fusion consumes only verdicts, and the prompt lane is det-contaminated.** `fuse_verdicts` reads only verdict/confidence/axis-severity/soft-hard-flags/ref_nid (`fusion.py:117-227`), so a second-converter axis drops in as a `suggested_verdict`+`axis_findings` (or a new advisory `ref_*` axis) with no fusion change; meanwhile the current LLM prompt injects the det verdict (`adjudicate.py:379-392`), which any directive-compliant design must remove. **(C) satisfies the directive's independence by never entering the contaminated prompt lane at all.**
