# Meta-Reviewer A: Benchmark Validity

**Date:** 2026-07-02
**Scope:** Re-verify every benchmark number in `00-baseline.md`, `01-benchmark-hunter.md`, `03-english-training-auditor.md`, `09-long-context-auditor.md`, `15-token-budget-skeptic.md` against primary sources.
**Primary sources consulted:** arXiv:2606.19348 (DeepSeek-V4 technical report, full text), NIST CAISI evaluation page (nist.gov, May 2026), Artificial Analysis AA-Omniscience benchmark definition + V4 release article, HuggingFace `DeepSeek-V4-Flash` README benchmark tables, llmreference.com, and corroborating trade press.
**Method:** Each number traced to the table/cell it came from. Model-card (self-reported) numbers separated from independent-harness numbers. Column labels re-checked against the source tables because that is where the errors clustered.

---

## Verified Claims (with corrected sources where needed)

### 1. NIST CAISI numbers — ALL VERIFIED, cited correctly

Every CAISI number in the four persona files and the baseline is accurate against the NIST page and corroborating reporting:

| Claim (persona) | Verified value | Source |
|---|---|---|
| ~8-month capability lag | Confirmed; V4-Pro ≈ GPT-5 (released ~8 mo before eval) | NIST CAISI |
| IRT Elo 800 ± 28 | Confirmed exactly | NIST; TheNeuralFeed; gncrypto |
| GPT-5.5 Elo 1260 ± 28, Opus 4.6 Elo 999 ± 27, GPT-5.4 mini 749 ± 46 | Confirmed exactly | NIST; theweatherreport.ai |
| ARC-AGI-2 semi-private **46%** (Opus 63%, GPT-5.5 79%) | Confirmed exactly | NIST; TheNeuralFeed |
| PortBench **44%** (GPT-5.5 78%) | Confirmed exactly | NIST; TheNeuralFeed |
| CTF-Archive-Diamond 32% (GPT-5.5 71%) | Confirmed exactly | NIST; theweatherreport.ai |
| CAISI SWE-bench Verified 74% (vs GPT-5.5 81%) | Confirmed | gncrypto (CAISI table) |
| "V4 scores better on self-reported evals than on CAISI evals" | Confirmed (paraphrase of NIST Figure 3 caption) | NIST |

Persona 01's [CRITICAL] CAISI finding is the single best-sourced claim in the swarm. The two held-out benchmarks (ARC-AGI-2 semi-private, PortBench) and the Elo spread are quoted correctly to the digit. **Upgrade: keep as CRITICAL, confidence high.**

One minor internal-anchor slip in persona 01: it writes "CAISI GPQA-Diamond 90% (near GPT-5.5 96%)". The 90% V4 value is correct, but the reference it should cite is **Opus 4.6 at 91%** (the reported CAISI pairing), not "GPT-5.5 96%," which I could not source. The V4 number is fine; the comparison anchor is unverified. Corrected below.

### 2. MRCR / CorpusQA scores — VERIFIED against the arXiv table

arXiv:2606.19348 §5.3 "Long" table (V4-Pro-Max row) reads:
- **MRCR 1M (MMR): Opus 4.6 = 92.9, Gemini-3.1-Pro = 76.3, V4-Pro = 83.5**
- **CorpusQA 1M (ACC): Opus 4.6 = 71.7, Gemini = 53.8, V4-Pro = 62.0**

Baseline §1, persona 01 [HIGH], persona 03, and persona 09 [CRITICAL] all cite 83.5 vs 92.9 and 62.0 vs 71.7 correctly. **Verified, confidence high.**

Persona 09's arXiv quote is verbatim-accurate: "retrieval performance remains highly stable within a 128K context window. While a performance degradation becomes visible beyond the 128K mark." That is exactly the source text. **Verified.**

### 3. Core benchmark comparisons — VERIFIED, correctly labeled as self-reported

From the arXiv "modes" table (V4-Pro-Max column) and HF README:
- **SWE-bench Verified 80.6%** — model-card / self-report (V4-Pro-Max). Opus 4.6 = 80.8, Gemini = 80.6. Confirmed.
- **LiveCodeBench 93.5%** — model-card (Think Max, pass@1). Confirmed; highest reported number on the board.
- **MMLU-Pro 87.5%** — model-card (V4-Pro-Max EM). Confirmed exactly.
- **Terminal-Bench 2.0 67.9%** (Opus 65.4) — model-card. Confirmed.
- **HumanEval 76.8 (Pass@1), MMLU 90.1 (5-shot), C-Eval 93.1, MMLU-Pro base 73.5** — all confirmed in the base-model table.

Persona 01's [HIGH] framing is correct and important: **80.6% SWE-bench is DeepSeek self-report, not independently reproduced.** Independent harnesses land lower (CAISI 74%, and the community Vals.ai/benchr numbers persona 01 cites are in the 77% range). This separation of self-reported vs independent is the right call. **Verified, keep HIGH.** (Vals.ai 77.40% and benchr labeling I could partially corroborate; the *direction* — independent < vendor — is firmly confirmed by CAISI's 74%.)

### 4. AA-Omniscience 94% — VERIFIED and interpreted CORRECTLY

The number and, more importantly, its meaning are right in every file that cites it:
- Artificial Analysis: "V4 Pro and V4 Flash both have a very high hallucination rate of **94% and 96%** ... when they don't know the answer they nearly always respond anyway." Confirmed.
- AA-Omniscience **Index = -10** for V4-Pro-Max, an 11-point improvement over V3.2 (-21). Confirmed exactly (persona 01).

**Interpretation check (the trap in this question):** AA's own definition is *"Hallucination Rate = incorrect / (incorrect + partial + not attempted)"* — the share of **non-correct responses** where the model guessed wrong instead of abstaining. It is **NOT** "94% of all answers are wrong." Baseline §5.1, persona 01 [CRITICAL], and persona 03 all describe it as "almost never abstains when uncertain," which is the correct reading. No persona overstated it as a blanket wrongness rate. **Verified, interpretation sound, keep CRITICAL.**

### 5. Architecture / efficiency numbers — VERIFIED

1.6T total / 49B active, 1M native context, CSA+HCA hybrid, Muon optimizer, 128K vocabulary, 27% inference FLOPs / ~10% KV cache vs V3.2 — all confirmed against arXiv and llmreference. Persona 09's efficiency figures (27% FLOPs, 10% KV) are accurate.

---

## Downgraded Claims (insufficient evidence)

### D1. BigCodeBench attribution is WRONG — column mislabel propagated from the baseline
**Affected: `00-baseline.md` §1 line 44, `03-english-training-auditor.md` [MED].**

The arXiv/HF base-model table columns are `V3.2-Base | V4-Flash-Base | V4-Pro-Base` and read `BigCodeBench (Pass@1) 3-shot: 63.9 | 56.8 | 59.2`.

- **63.9 is DeepSeek-V3.2-Base, not V4-Pro.** V4-Pro-Base = **59.2**.
- Baseline lists "BigCodeBench Pass@1 | 63.9" under V4-Pro. **Wrong model.**
- Persona 03 wrote "BigCodeBench Pass@1: 63.9 (V4-Pro-Base) / 59.2 (V4-Pro-Max)." **Both labels wrong:** 63.9 = V3.2-Base; 59.2 = V4-Pro-*Base* (the mode-split table has no BigCodeBench row at all, so a "V4-Pro-Max = 59.2" figure does not exist).

Persona 03 even notes it "matches historical baseline 63.9 in 00-baseline.md" — which confirms this is a **baseline error propagating downstream**, not independent corroboration. **Downgrade both to corrected: V4-Pro-Base BigCodeBench = 59.2; drop the 63.9-as-V4 claim.** Does not change persona 03's verdict, but the number must be fixed at the baseline.

### D2. MRCR 8-needle "0.82 @ 256K → 0.59 @ 1M" — secondary source, conflicting attribution
**Affected: baseline §5.2, `01` [HIGH], `09` [CRITICAL]/[HIGH].**

The arXiv report gives only a **figure (Figure 9)** and the qualitative "stable through 128K, degrades beyond" statement — **no 0.82/0.59 table**. The numeric anchors come from the **HuggingFace release blog** (per personas 01/09) — but **baseline §5.2 attributes the same numbers to "Skywork stress tests via jacksunwei.me."** Two different secondary attributions for one number pair. The numbers are internally consistent across the swarm but are **not from the primary source and their provenance is muddled.** **Downgrade from CRITICAL/asserted-fact to MEDIUM: real degradation trend confirmed by arXiv; the specific 0.82/0.59 values are secondary-source, single-origin, attribution-inconsistent.**

### D3. Digital Applied NIAH-2 multi-needle numbers — single unverified blog
**Affected: `09` [HIGH] "single 96%@200K→78%@1M; 8-needle 84%@200K→41%@1M (-37 pts)."**

These come entirely from one blog (digitalapplied.com). No primary or second-source corroboration found. The **qualitative** claim — multi-needle degrades far worse than single-needle, and tapetum_llm's task is multi-needle-shaped — is sound and well-argued. The **specific percentages** rest on one unverifiable source. **Downgrade the numbers to LOW-confidence illustration; keep the structural argument.**

### D4. Persona 15's central tokenizer claim contradicts the arXiv report
**Affected: `15-token-budget-skeptic.md` [HIGH] "V4-Pro does not use the same tokenizer as V3/R1."**

arXiv:2606.19348 §4.1 states plainly: *"on top of the DeepSeek-V3 tokenizer, we introduce a few special tokens for context construction, and still remain the vocabulary size to be 128K."* So V4 **inherits the V3 BPE tokenizer** with the same 128K vocab plus a handful of special tokens. The `tokenizer_class` difference persona 15 cites (`PreTrainedTokenizerFast` vs `LlamaTokenizerFast`) is a HF **wrapper/serialization** distinction, not a different BPE merge table. The chars/token ratio should therefore track V3/R1 closely, which **undercuts the premise** that R1-family measurements "don't transfer." **Downgrade from [HIGH] to [MED]:** re-measuring on V4 is still good hygiene (the special tokens and packing changes have marginal effects), but the "different tokenizer, must recalibrate" framing is factually weak. Persona 15's *code-heavy floor* concern (chars/token drops on dense code) is orthogonal and stands on its own.

### D5. Persona 09 selectively truncates the arXiv long-context sentence
**Affected: `09` [CRITICAL].**

The quote is verbatim-correct but stops mid-argument. The full arXiv sentence continues: *"...the model's retrieval capabilities at 1M tokens remain remarkably strong compared to both proprietary and open-source counterparts."* Dropping DeepSeek's own mitigating clause is defensible for a skeptic, but a validity review should note it: the persona presents the degradation half and omits the vendor's framing. **Not a misquote; flag as one-sided quoting.** Verdict unaffected (the skepticism is still warranted given MRCR 83.5 < Opus 92.9), but note it.

---

## Dropped Claims (could not reproduce)

### X1. GSM8K 92.6% (baseline §1 line 41)
Not present in any arXiv or HF table I could locate; GSM8K is deprecated/saturated for frontier models (which post ~96%+), and the V4 report uses HMMT/AIME/Apex/HLE for math, not GSM8K. A 92.6 is both **unsourced and implausibly low** for this tier. **Drop until a source is produced.** Not cited by any persona — it lives only in the baseline table.

### X2. MGSM multilingual math "84.4" (baseline §5.7)
No MGSM 84.4 found in the tables. **84.4 is the verified value for Chinese-SimpleQA (V4-Pro-Max)** — strongly suggesting the baseline **mislabeled Chinese-SimpleQA as MGSM.** **Drop the "MGSM 84.4" claim; the 84.4 belongs to Chinese-SimpleQA.** Persona 03 correctly uses 84.4 for Chinese-SimpleQA, so the persona is right and the baseline is wrong.

### X3. "DeepSWE ~7.5–8% pass@1" (persona 01 [HIGH])
Obscure, single-mention, no reproducible source. Adds nothing the CAISI 74% and SWE-bench Pro 55.4% do not already establish. **Drop as unverifiable clutter** (does not affect the finding, which is otherwise well-supported).

---

## New Evidence Found

1. **SWE-bench Pro 55.4% is firmly corroborated** across three independent write-ups (llmreference, Thomas Wiegold, HF table: V4-Pro-Max = 55.4). Wiegold adds peer context: Opus 4.7 = 64.3, Kimi K2.6 = 58.6, GLM-5.1 = 58.4 — **V4-Pro is *last* among that open/closed cohort on the harder coding suite.** This strengthens persona 01's [HIGH] "code axis weaker on messy real-repo diffs" more than the personas realized; worth promoting.

2. **Independent Terminal-Bench divergence:** llmreference reports **BenchLM's independent June 2026 harness at 59.1** vs the vendor's 67.9. Same pattern as SWE-bench (independent < vendor). Reinforces the "trust independent harnesses, discount self-report" theme.

3. **AA-Omniscience token cost:** jacksunwei corroborates V4-Pro burned **~190M tokens (~4× field average)** running the AA index. Not a fidelity number, but material to the token-budget persona (15) and to any cost modeling — the cheap per-token price partially evaporates at task level.

4. **CTF-Archive-Diamond provenance:** theweatherreport.ai identifies it as 285 hard CTF challenges from ASU's pwn.college — useful for anyone assessing how relevant the cyber gap is to this document-fidelity use case (answer: not very).

---

## Summary Assessment

**The load-bearing numbers are solid.** The two claims that matter most for the swarm's thesis — the NIST CAISI 8-month lag with its held-out ARC-AGI-2 (46%) / PortBench (44%) / CTF (32%) sub-scores, and the AA-Omniscience 94% hallucination-when-uncertain rate — are **verified to the digit and interpreted correctly.** The MRCR 83.5-vs-92.9 and CorpusQA 62.0-vs-71.7 gaps are confirmed against the arXiv table. The SWE-bench 80.6% / LiveCodeBench 93.5% / MMLU-Pro 87.5% figures are real and correctly flagged as self-reported (independent harnesses run 5–7 points lower).

**The errors cluster in two places, both fixable:**
1. **Column-label mistakes in the baseline that propagated to personas** — BigCodeBench 63.9 is V3.2-Base, not V4-Pro (should be 59.2); "MGSM 84.4" is actually Chinese-SimpleQA; GSM8K 92.6 is unsourced and should be dropped. These are transcription/attribution errors, not fabrications.
2. **Secondary-source numbers presented with more certainty than warranted** — the MRCR 8-needle 0.82/0.59 pair (secondary, conflicting attribution) and the Digital Applied multi-needle percentages (single blog). Downgrade to MEDIUM/LOW; the underlying degradation *trend* is real per arXiv.

**One factual correction to a persona premise:** Persona 15's "V4 uses a different tokenizer, R1 numbers don't transfer" is contradicted by the arXiv report (V4 = V3 tokenizer + a few special tokens, same 128K vocab). Re-measurement is still prudent, but the alarm is overstated.

Net: **no claim critical to the "usable-with-conditions, not frontier-parity" conclusion collapses.** The swarm's headline risks (hallucination-when-uncertain, long-context multi-needle degradation, independent < self-reported) survive verification. Fix the baseline's four column/attribution errors and the swarm's evidentiary base is clean.

---

### 3-line verification summary
1. **Verified to the digit:** all NIST CAISI numbers (8-mo lag, Elo 800/1260/999, ARC-AGI-2 46%, PortBench 44%, CTF 32%), the MRCR 83.5-vs-92.9 / CorpusQA 62.0-vs-71.7 gaps, and SWE-bench 80.6% / LiveCodeBench 93.5% / MMLU-Pro 87.5% (correctly labeled self-reported); the AA-Omniscience 94% is real and interpreted correctly as "guesses instead of abstaining," not blanket wrongness.
2. **Downgraded/corrected:** BigCodeBench 63.9 is V3.2-Base not V4-Pro (V4-Pro-Base = 59.2, error propagated from baseline to persona 03); MRCR 8-needle 0.82/0.59 and Digital Applied multi-needle % are secondary/single-source (→ MEDIUM/LOW); persona 15's "different tokenizer" premise is contradicted by arXiv (V4 keeps the V3 tokenizer, 128K vocab).
3. **Dropped as unreproducible:** GSM8K 92.6% (unsourced, implausibly low), "MGSM 84.4" (actually Chinese-SimpleQA), and "DeepSWE ~7.5–8%" (obscure, adds nothing) — none is load-bearing, so the swarm's core conclusion stands.
