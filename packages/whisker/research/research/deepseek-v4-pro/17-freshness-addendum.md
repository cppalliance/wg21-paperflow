# Freshness Addendum: 2026-07-02 Verification Pass

**Date:** 2026-07-02 (same day as the main research, late-morning verification pass)
**Method:** 4 parallel Composer-2.5 scouts, web-only verification, no file or endpoint interaction.
**Overall verdict:** MOSTLY-CURRENT (4/4 scouts). No core finding flipped. The serving-stack section of the main research required corrections; benchmark and behavioral findings hold.

---

## Scout 1: Release freshness (DeepSeek model family, 2026-04-24 to 2026-07-02)

**Verdict: MOSTLY-CURRENT.**

- **No successor checkpoint.** The `deepseek-ai/DeepSeek-V4-Pro` safetensor shards on HuggingFace are unchanged since April 27. Only a README/technical-report commit (`b5968e9`, ~2026-06-24).
- **DSpark variants (~2026-06-27):** `DeepSeek-V4-Pro-DSpark` and `DeepSeek-V4-Flash-DSpark` are the **same checkpoint** with a speculative-decoding drafter attached (DeepSpec tooling, github.com/deepseek-ai/DeepSpec). Serving optimization, not a capability change. Claims lossless output distribution, 57-78% faster decode on Pro.
- **Preview-to-stable graduation announced:** V4 goes official **mid-July 2026** with peak/off-peak API pricing (TechNode, 2026-06-30). Same model IDs.
- **V4.1 is rumor only:** community reports of `DeepSeek-V4.1-Flash` in web-chat gray testing (2026-06-16); no HuggingFace weights, no API model ID, no official confirmation.
- **Legacy alias retirement:** `deepseek-chat` / `deepseek-reasoner` retire **2026-07-24 15:59 UTC** (announced April 24, unchanged).
- Official API changelog (api-docs.deepseek.com/updates) has **no entries after 2026-04-24**.

## Scout 2: Benchmark currency

**Verdict: MOSTLY-CURRENT.**

- **NIST CAISI:** released May 1, page-updated May 2 (metadata only). PortBench 44%, ARC-AGI-2 46%, CTF-Archive-Diamond 32%, ~8-month frontier lag: **all unchanged**. No June follow-up.
- **AA-Omniscience 94% hallucination rate: unrevised.** Still the canonical number (Artificial Analysis, April 24 article; June Suprmind update confirms 94% Pro / 96% Flash).
- **AA Intelligence Index rebaseline:** 52 -> 44 under methodology v4.1 (June 2026). Methodology change, **not a re-run**; does not affect our citations.
- **arXiv:2606.19348 has no v2/v3.** The "Updated 2026-06-19" metadata is the initial arXiv posting (ID prefix 2606 = June), not a revision. All self-reported table numbers verified unchanged (SWE 80.6%, LiveCodeBench 93.5, MMLU-Pro 87.5, GSM8K 92.6, HMMT 95.2, LongBench-V2 51.5, MRCR-1M 83.5 vs Opus 4.6 92.9).
- **New third-party data to fold in:**
  - Vals.ai SWE-bench Verified **82.8%** (leaderboard updated 2026-07-01, #1 open-weight).
  - CAISI SWE-bench **74%** (held-out agentic harness). SWE-bench spread worth citing: 74% (CAISI) / 80.6% (self-report) / 82.8% (Vals.ai).
  - Epoch AI ECI now live: **rank 28/203**, ECI 147-156 (90% CI).
  - Neo Research safety evaluation (2026-06-02): cyber ~3-6 months behind Western frontier; jailbreak rate 0.6% -> 77.8% with a 2023 template. Safety-adjacent, not capability-leaderboard material.

## Scout 3: vLLM serving stack

**Verdict: MOSTLY-CURRENT, with the largest corrections of the pass.**

- **Latest vLLM: v0.24.0 (2026-06-29).** Recommended production target moves from ">= 0.21.0" to **v0.24.0**. The three parser flags are unchanged: `--tokenizer-mode deepseek_v4 --tool-call-parser deepseek_v4 --reasoning-parser deepseek_v4` (plus `--enable-auto-tool-choice`).
- **Issue status corrections (main research cited these as open):**

| Issue | Status | Fixed in |
|---|---|---|
| vllm#41132 (structured output + thinking -> JSON in reasoning) | CLOSED 2026-05-01 | v0.20.1 (PR #41199) |
| vllm#41240 (DSML wrapped/reserved args) | CLOSED 2026-05-06 | v0.21.0+ (PR #41801) |
| vllm#41483 (H200 V4-Pro MTP crash) | CLOSED 2026-05-06 | v0.20.2 (PR #41665) |
| vllm#40801 (DSML fragment leak, auto+streaming) | Closed by author 2026-06-25, **no merged fix**; recovery PR #45862 still open | watchlist |

- **New June 2026 issues (missed by the main research):**

| Issue | Opened | Severity |
|---|---|---|
| vllm#46256: `deepseek_v4` tokenizer ignores `add_generation_prompt`/`continue_final_message`; silent wrong output on assistant-terminated multi-turn | 2026-06-21 | Critical (silent wrong output) |
| vllm#46796: V4-Flash fails to start on B300/SM103 (DeepGEMM launch error) | 2026-06-26 | Critical (startup; workaround on v0.24.0) |
| vllm#46710: malformed output when inline system messages preserved in-place | 2026-06-25 | High (correctness) |
| vllm#47174: `--kv-cache-dtype auto` silently wrong on Blackwell SM120 (should be `fp8_ds_mla`) | 2026-06-30 | High (config trap) |

- **New recommended config since April (recipes, not flag renames):** `--attention_config.use_fp4_indexer_cache=True`, cudagraph compilation-config, explicit `--kv-cache-dtype fp8`, `--enable-expert-parallel`. v0.24.0 replaces internal `CUDA_VISIBLE_DEVICES` handling with `device_ids`.
- **DeepSeek hosted-API issues (not self-host, still open):** #1376 (`tool_choice="required"` rejected in thinking mode), #1257 (thinking defaults to English, updated 2026-06-27), #1464 (non-streaming ~30s TTFT from default thinking, 2026-06-29).

## Scout 4: Community feedback (June 2026)

**Verdict: MOSTLY-CURRENT.**

- **All five baseline claims confirmed in June, none fixed:** abstention failure, JSON/structured-output issues with thinking enabled, long-context degradation past 128K, strong English (thinking defaults to English), no V4-VL.
- **New failure modes (June community digest, deepseek-ai/DeepSeek-V3#1471, 2026-07-01):**
  - #1453: empty responses (out=0) after tool results fed back in streaming+function-calling; persists once triggered.
  - #1448: illegal JSON in tool calls (unescaped quotes).
  - #1464: non-streaming + default thinking -> 28-32s TTFT, breaks ~30s client timeouts.
  - #1244 (ongoing): tool calls emitted as plain text in `content`, sometimes with a Chinese preamble; worsens with ~40+ tools.
  - #1465: V4-Flash cache hit rate 40-50% vs Pro 90%+ (ops cost issue).
- **Long-context nuance:** Skywork stress tests (cited via jacksunwei digest) show failures past 128K are **non-deterministic**: the Lightning Indexer sporadically misses compressed blocks, rather than smooth monotonic MRCR decay.
- **No multimodal:** no V4-VL through June; consumer "Image Recognition Mode" is a chat/app gray-scale module, not available via API. Speculation of V4.5/V4-VL in Q3 2026 (unconfirmed).
- **No silent weight swap detected.** June changes are serving-layer (DSpark) and quant plumbing (community GGUF still experimental/Flash-only; sub-Q4 GGUF a quality dead end due to native FP4 MoE experts).

---

## Impact on the main research

1. **SYNTHESIS.md finding 3 / RESEARCH-PAPER.md blocking condition 3 corrected:** vLLM floor moves to v0.24.0; the three cited vLLM issues are fixed, replaced on the watchlist by #46256/#46710/#47174/#40801-edge and the hosted-API trio #1448/#1453/#1464.
2. **Benchmark sections gain the SWE-bench spread (74/80.6/82.8) and the AA index rebaseline note.** The 94% abstention number, the CAISI numbers, and all arXiv table numbers are confirmed current.
3. **Temporal validity sharpened:** V4 graduates preview -> stable mid-July 2026 (possible behavior deltas on the hosted API; self-hosted weights unaffected), legacy aliases retire 2026-07-24.
4. **No verdict change:** usable-with-conditions stands. No core finding was invalidated.
