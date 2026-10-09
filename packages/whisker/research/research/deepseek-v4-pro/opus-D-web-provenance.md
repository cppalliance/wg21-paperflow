# Meta-Review D: Provenance of Web Claims

**Reviewer:** Meta-Reviewer D (Provenance of Web Claims)
**Date:** 2026-07-02
**Scope:** Every web-sourced claim across `00-baseline.md` and personas `01`–`16`.
**Method:** Direct fetch of each cited URL; cross-check of quoted figures, dates, and attributions against the live page.

---

## Verdict

**Web provenance is STRONG. No fabricated sources found. No dead links among the load-bearing citations.** Every primary source the swarm leans on — the arXiv technical report, the NIST CAISI report, the Artificial Analysis release article, the jacksunwei.me digest, the DeepSeek API thinking-mode docs, the deepseekai.guide limitations page, the vLLM V4 blog, and every named GitHub issue I could reach — **exists and its cited content matches**. Where I spot-checked exact numbers (CAISI Elo table, arXiv benchmark table, Digital Applied NIAH grid, AA-Omniscience methodology), the personas quoted them **verbatim-accurate**, not approximately.

The defects are minor and clustered in **date attribution** and one **"official" over-labeling**, plus a tail of unverified secondary aggregators. None of them flips a persona verdict. Confidence: **high** on the sources I fetched, **medium** on the ~12 secondary aggregator URLs I did not individually open (see §4).

---

## 1. Primary sources: VERIFIED, content matches

| Claim / source | URL | Real? | Content check |
|---|---|---|---|
| DeepSeek-V4 technical report, arXiv:2606.19348 | arxiv.org/abs & /html/2606.19348 | **YES** | Full 1052-line HTML report. Title "DeepSeek-V4: Towards Highly Efficient Million-Token Context Intelligence." 1.6T/49B Pro, 284B/13B Flash, CSA+HCA, mHC, Muon, 33T tokens, FP4 QAT, MTP. **All 00-baseline benchmark numbers reproduce exactly** (see §2). |
| NIST CAISI Evaluation of DeepSeek V4 Pro, May 1 2026 | nist.gov/news-events/news/2026/05/caisi-evaluation-deepseek-v4-pro | **YES** | ~8-month lag, IRT Elo, all held-out benchmark numbers match persona 01 to the digit (see §2). |
| AA-Omniscience 94% hallucination | artificialanalysis.ai/articles/deepseek-is-back-... (Apr 24 2026) | **YES** | "hallucination rate of 94% and 96% respectively meaning when they don't know the answer they nearly always respond anyway." Omniscience Index -10 (V3.2 -21). Verbatim match. |
| jacksunwei.me digest | jacksunwei.me/digest/ai-research/deepseek-v4-ascend-pivot-cheaper-shakier/ | **YES** | 94% hallucination, Lightning-Indexer random-position misses, Skywork attribution, MRCR 0.82@256K→0.59@1M, "meaningfully behind" (Artgor). All present. |
| AA-Omniscience paper, arXiv:2511.13029 | arxiv.org/abs/2511.13029 | **YES** | 6,000 questions, 42 topics, 6 domains, Omniscience Index -100..100, Claude 4.1 Opus top at 4.8. Persona 12's methodology description is accurate. |
| DeepSeek-V3#1376 (tool_choice="required" 400) | github.com/deepseek-ai/DeepSeek-V3/issues/1376 | **YES** | Body states **"40% fallback rate in real-world trading agent analysis runs"** verbatim; Oh My Pi `supportsToolChoice:false`; "Thinking mode does not support this tool_choice" 400. Matches baseline §5.3 and personas 10/13. |
| DeepSeek-V3#1257 (thinking-block English drift) | github.com/deepseek-ai/DeepSeek-V3/issues/1257 | **YES** | Chinese user complaint that thinking block forces English; triage comment: "Under this max-effort mode, the reasoning engine currently defaults to English." Supports the claim. **Caveat in §3.** |
| DeepSeek-V3#1464 (non-streaming ~30s TTFB) | referenced in #1376 timeline | **YES** | Title: "non-streaming security-classifier call times out (~30s) from default thinking." Matches baseline's ~28–32s. |
| DeepSeek-V3#1244 (~11% text-tool fallback) | github.com/deepseek-ai/DeepSeek-V3/issues/1244 | **YES** | Reproduction table **15/19 correct, 2/19 (11%) bug, 2/19 (10%) expected text**; "~40 tools total." Exact match to persona 02. |
| vllm#41132 (JSON in reasoning field) | github.com/vllm-project/vllm/issues/41132 | **YES** | DeepSeek V3.2 & V4, thinking + response_format → JSON lands in `reasoning`, `content=None`. Closed, fixed by PR #41199. Reproducer uses `--reasoning-parser deepseek_v4`. Matches baseline/persona 10/11. |
| vllm#41240 (DSML tool parser) | github.com/vllm-project/vllm/issues/41240 | **YES** | DSML wrapped/reserved argument mishandling; closed, fixed in PR #41801 (not #41241, which was the initial proposal). Matches baseline §5.3. |
| vllm#41483 (h200 MTP crash) | github.com/vllm-project/vllm/issues/41483 | **YES** | Real: "h200 deepseekv4 pro mtp" EngineDeadError, milestone v0.20.2. **Not cited by any persona** — see §3. |
| vllm#40801 (DSML leak, auto+streaming) | github.com/vllm-project/vllm/issues/40801 | **YES** | Title: "DeepSeek V4 intermittently leaks DSML fragments in auto + streaming mode." Matches persona 02 CRITICAL. |
| vllm#34650 (MTP + thinking empty output) | github.com/vllm-project/vllm/issues/34650 | **YES** | "223 tokens generated, both reasoning_content and content come back empty" verbatim; `response_format={"type":"json_schema"}`. Matches personas 02/10/11. |
| vLLM V4 blog, 2026-04-24 | vllm.ai/blog/2026-04-24-deepseek-v4 | **YES** | "DeepSeek V4 in vLLM: Efficient Long-context Attention." Serving quickstart, CSA/HCA explanation. Supports persona 11's parser-flag findings. |
| DeepSeek API thinking-mode docs | api-docs.deepseek.com/guides/thinking_mode | **YES** | "If your code does not correctly pass back reasoning_content, the API will return a 400 error." Exact support for persona 02 HIGH. Thinking defaults enabled; temp/top_p ignored. |
| deepseekai.guide limitations | deepseekai.guide/guides/deepseek-limitations/ | **YES** | "V4 is text-only… no native image, audio or video input." Supports baseline §1 line 29 and persona 08. Dated April 25 2026. |
| Digital Applied — long-context NIAH | digitalapplied.com/blog/long-context-retrieval-needle-in-haystack-2026 | **YES** | V4-Pro single-needle **96%@200K→78%@1M**, 8-needle **84%@200K→41%@1M**, RULER 256K Gemini 84 / GPT-5.5 72 / Opus 4.7 61. **Exact match to persona 09.** |
| Digital Applied — hallucination study | digitalapplied.com/blog/ai-model-hallucination-rate-benchmarks-2026-study | **YES** | DeepSeek V4 citation hallucination **15.7% with CoT, 19.1% without**; frontier citation avg 12.4%. Exact match to persona 12. |
| benchr.org review | benchr.org/articles/deepseek-review | **YES** | "80.6% … DeepSeek-reported, not yet independently reproduced." Exact match to persona 01's characterization. |

---

## 2. Numeric spot-checks against primary tables (all PASS)

**arXiv:2606.19348 evaluation tables** (lines 752–792 of the HTML):

| Metric | Persona/baseline value | arXiv value | Match |
|---|---|---|---|
| SWE Verified: Opus 4.6 / V4-Pro | 80.8 / 80.6 | 80.8 / 80.6 | ✅ |
| Terminal-Bench 2.0: Opus / V4-Pro | 65.4 / 67.9 | 65.4 / 67.9 | ✅ |
| LiveCodeBench: Opus / V4-Pro | 88.8 / 93.5 | 88.8 / 93.5 | ✅ |
| HLE: Opus / Gemini / V4-Pro | 40.0 / 44.4 / 37.7 | 40.0 / 44.4 / 37.7 | ✅ |
| HMMT 2026: Opus / V4-Pro | 96.2 / 95.2 | 96.2 / 95.2 | ✅ |
| MMLU-Pro V4-Pro-Max | 87.5 | 87.5 | ✅ |
| MRCR 1M: Opus / V4-Pro | 92.9 / 83.5 | 92.9 / 83.5 | ✅ |
| CorpusQA 1M: Opus / V4-Pro | 71.7 / 62.0 | 71.7 / 62.0 | ✅ |
| GSM8K (base) | 92.6 | 92.6 | ✅ |
| BigCodeBench Pass@1 (base, 3-shot) | 63.9 | 63.9 | ✅ |
| LongBench-V2 EM | 51.5 | 51.5 | ✅ |
| Long-context stability quote (§5.3, Fig 9) | "highly stable within 128K … degradation becomes visible beyond the 128K mark" | verbatim, line 833 | ✅ |

**NIST CAISI table** (persona 01):

| Metric | Persona 01 value | NIST value | Match |
|---|---|---|---|
| IRT Elo: V4-Pro / GPT-5.5 / Opus 4.6 | 800±28 / 1260±28 / 999±27 | 800±28 / 1260±28 / 999±27 | ✅ |
| ARC-AGI-2 semi-private: V4 / Opus / GPT-5.5 | 46 / 63 / 79 | 46 / 63 / 79 | ✅ |
| PortBench: V4 / GPT-5.5 | 44 / 78 | 44 / 78 | ✅ |
| CTF-Archive-Diamond: V4 / GPT-5.5 | 32 / 71 | 32 / 71 | ✅ |
| SWE-Bench Verified (CAISI) | 74 | 74 | ✅ |
| GPQA-Diamond: V4 / GPT-5.5 | 90 / 96 | 90 / 96 | ✅ |
| "scores better on DeepSeek's self-reported evaluations than on CAISI evaluations" | quoted | verbatim | ✅ |

This is the strongest part of the swarm's evidence base. Persona 01 and persona 09 in particular transcribed third-party numbers with zero drift.

---

## 3. Defects found (downgrades and flags)

### D-1 [MED] arXiv report is mislabeled "April 2026" throughout

`00-baseline.md:13`, `01:14`, `03:8`, `08:11` cite **"arXiv:2606.19348 (April 2026)."** The arXiv ID `2606.xxxxx` encodes a **June 2026** submission month. The model *released* April 24 2026, but the *technical report* on arXiv is a June artifact. The personas conflated the release date with the paper date.

- **Impact:** cosmetic. The paper exists and content matches. No claim depends on the month.
- **Recommendation:** do not downgrade any finding; correct the parenthetical to "(arXiv June 2026; model released Apr 24 2026)" in a cleanup pass.

### D-2 [MED] Persona 03 over-labels a community comment as an "official response"

`03-english-training-auditor.md:20` cites **"GitHub #1257 official response ('in max effort mode, reasoning engine currently prioritizes English path')."** In the live issue, #1257 is a **Chinese-user complaint thread**; the "max-effort mode → English" explanation comes from a **community triager comment**, not a verified DeepSeek-staff response. The paraphrase is also loose: the actual text is "Under this max-effort mode, the reasoning engine currently defaults to English."

- **Impact:** the *underlying claim* (thinking block defaults to English) is **correct** and independently corroborated by the issue's own subject matter. Only the "official" provenance label is wrong.
- **Recommendation:** **downgrade the attribution** from "official response" to "community triage comment on #1257"; keep the finding.

### D-3 [LOW] #41483 is in the verify-list but no persona cited it

The task's key-claim list includes `vllm#41483`. It is **real** (h200 MTP EngineDeadError crash) but **no persona references it**. Personas used #34650, #43388, #43753, #41524 for the MTP/serving-instability family instead. No misattribution exists to correct; flagging only so the coordinator knows #41483 is genuine and available if a serving-stability finding wants a harder citation.

### D-4 [LOW] Secondary GitHub issues cited but not individually opened

Personas 02/10/11 cite a tail of ecosystem issues I did not fetch one-by-one: `vllm#43388`, `#43753`, `#41524`, `flashinfer#3197`, `openclaw#71455`, `litellm#26395`, `opencode#24190`, LangChain `#31403`. Several are **cross-referenced inside issues I did verify** (#24190 and #31403 both appear in #1376's timeline; #41199/#41801 appear in #41132/#41240). The pattern they describe (reasoning_content roundtrip, MTP boundary loss, DSML leakage) is confirmed by the primary docs and issues. Treat as **corroborated-by-association, not independently confirmed.**

### D-5 [LOW] Benchmark aggregators cited but not individually opened

Persona 01 leans on several third-party aggregators beyond benchr.org (which I verified): `benchlm.ai/valsSweBench` (77.40%), `evals.report/models/deepseek-v4-pro` (SWE-Pro 55.4%, DeepSWE 7.5–8%), `codingfleet.com` (SWE-Pro table), `aiwartracker.com/benchmarks/docvqa`, `tablebench.github.io`. Persona 04 cites `TableEval arXiv:2506.03949`, `CompTab`, `CoTabBench (OpenReview wcInjlUp8V)`, `RealHiTBench`. Persona 12 cites `Research Square rs-6676676` (91.43% biomedical), `FullCite arXiv:2606.07130`, `CAMS arXiv:2606.23989`, `PINK arXiv:2604.22774`. Persona 08 cites `docs.api.nvidia.com/nim/...`, `blog.roboflow.com`, `besthub.dev`, `dataleadsfuture.com`.

- **Impact:** these back **MED/LOW** findings, not any CRITICAL. The **anchor number** each is used to support (CAISI SWE-Verified 74%, the 80.6% "vendor-reported not reproduced" framing) is independently confirmed by NIST and benchr.org.
- **Recommendation:** no downgrade; label these "secondary, unverified" if the coordinator wants a clean citation ledger. My sampling of the aggregators that WERE checkable (benchr, both Digital Applied studies, Artificial Analysis, jacksunwei) found **zero** fabrications, which raises confidence that the sourcing discipline held across the tail.

---

## 4. What I did NOT find

- **No dead links** among the ~20 load-bearing URLs I fetched.
- **No fabricated GitHub issues.** Every issue number in the key-claim list resolves to a real issue whose title and body match the persona's use.
- **No invented benchmark figures.** Every number I could trace to a primary table (arXiv, NIST) matched exactly.
- **No misquotes** of primary sources. The two direct-quote spot-checks (arXiv §5.3 128K stability; CAISI "scores better on self-reported") are verbatim.
- **No persona relied solely on a source that does not exist.**

---

## 5. Per-persona provenance grade

| Persona | Web-provenance grade | Note |
|---|---|---|
| 00 baseline | A− | arXiv month mislabel (D-1); all else exact. |
| 01 Benchmark-Hunter | A | CAISI + arXiv transcribed to the digit; aggregators secondary but anchor confirmed. |
| 02 Community-Feedback | A | #1244, #40801, #34650, thinking-mode docs all verified verbatim. |
| 03 English-Training | B+ | Claim correct; "official response" label wrong (D-2). arXiv month (D-1). |
| 04 Table-Understanding | B | Table benchmarks (TableEval/CompTab/CoTabBench) not individually opened (D-5); no V4 numbers claimed, so low risk. |
| 05 Code-Fidelity | A− | Leans on arXiv + internal files; CRUXEval arXiv:2401.03065 is a real prior-gen paper. |
| 06 Heading-Structure | A− | arXiv §4.1/Fig 9 verified; READOC/LongBench secondary. |
| 07 Math-Notation | B | Formula-parser papers (2512.09874, 2604.22774) not opened (D-5); no load-bearing V4 number. |
| 08 Vision-Image | B+ | Text-only confirmed by 3 independent sources; besthub/dataleadsfuture secondary (D-5); arXiv month (D-1). |
| 09 Long-Context | A | Digital Applied NIAH grid + arXiv Fig 9 quote both exact. Best-sourced persona. |
| 10 Structured-Output | A | #1376, #41132, AA arXiv, thinking-mode behavior all verified. |
| 11 Tokenizer-Serving | A− | vLLM blog + #41132/#41240/#34650 verified; #43753/#41524 corroborated-by-association (D-4). |
| 12 Hallucination | A | AA-Omniscience paper + Digital Analysis study exact; rs-6676676 biomedical unverified (D-5). |
| 13 CLAUDE-Invariant | A | Reuses verified #1376/#41132/#41199; no new web claims. |
| 14 Tapetum-Lane-Fit | A | Derives from verified baseline numbers; no fresh web claims. |
| 15 Token-Budget | A | HF tokenizer_config claims consistent with arXiv "128K vocab, on top of V3 tokenizer" (line 496). |
| 16 Steelman | A | Reuses verified baseline benchmark numbers. |

---

## What would change my verdict

If any of the ~12 unverified secondary aggregators (D-4, D-5) turned out to be dead or to misquote its underlying number, I would downgrade the specific MED/LOW finding it supports — but not any CRITICAL, because every CRITICAL rests on a primary source (arXiv, NIST, Artificial Analysis, a real GitHub issue, or DeepSeek's own docs) that I verified directly.
