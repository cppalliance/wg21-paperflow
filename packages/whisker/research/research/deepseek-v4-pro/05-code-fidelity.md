# 05 - Code-Fidelity

**Verdict:** usable-with-conditions — V4-Pro has credible code *reading* proxies (SWE-bench, agentic repair) but published scores are overwhelmingly *generation* benchmarks; the tapetum `code` axis is a static fidelity audit with no PDF ground truth and no V4-Pro CRUXEval-style verification numbers, so treat confident `pass` on code-heavy papers as unvalidated until a human-verified fact corpus exists.

**Confidence:** medium

## Findings

- [HIGH] **LiveCodeBench 93.5% measures synthesis from problem statements, not conversion-fidelity judgment.** Evidence: HuggingFace model card and arXiv:2606.19348 report LiveCodeBench Pass@1 93.5% (Think Max); tapetum `code` axis asks whether fenced C++/grammar/`requires` blocks in *already-converted* markdown are intact (`tapetum_llm.md:38-47`, `00-baseline.md:32-36`). Impact: the headline coding score is the wrong task family; it overstates trust for "detect garbled code in markdown."

- [HIGH] **Within-model generation spread (93.5 / 76.8 / 63.9) shows benchmark choice dominates the story.** Evidence: same V4-Pro card reports LiveCodeBench 93.5%, HumanEval 76.8%, BigCodeBench 63.9% (3-shot) on base models (arXiv:2606.19348 Table 2; HuggingFace `deepseek-ai/DeepSeek-V4-Pro`). Impact: even before the gen-vs-verify gap, "practical/library" code (BigCodeBench) is ~30 points below competitive-programming generation; WG21 examples (templates, concepts, grammar productions) resemble library-style snippets more than LiveCodeBench tasks.

- [HIGH] **Literature documents generation–understanding decoupling; V4-Pro publishes no CRUXEval-class score.** Evidence: CRUXEval (arxiv:2401.03065) finds "many recent high-scoring models on HumanEval show no improvements" on code execution/reasoning; distilled models with strong HumanEval do not improve on CRUXEval-I/O. DeepSeek-Coder-V2 reports 70.0% / 75.1% on CRUXEval-I/O-COT (prior generation), but V4-Pro technical report lists LiveCodeBench, Codeforces, SWE-bench — not CRUXEval. Impact: we lack direct evidence V4-Pro can reliably *verify* code semantics; extrapolation from LiveCodeBench is unsupported.

- [MED] **SWE-bench Verified 80.6% is the best published proxy for reading existing code, but it is repair-not-audit.** Evidence: arXiv:2606.19348 § evaluation uses bash + file-edit agent on real repos; resolved rate 80.6% (Think Max). SWE requires locating bugs in messy multi-file context and emitting patches — closer to tapetum than LiveCodeBench, still not "compare markdown code block to source PDF." Impact: supports moderate code comprehension; does not prove sensitivity to subtle conversion artifacts (reflow, merged fences, `>>` spacing).

- [MED] **WG21 C++ corruption classes are subtle; whisker hard-gates only catch empty fences.** Evidence: `code_format.py:12-22` documents PDF kerning artifacts around `<`/`>` (`template <typename From >`); tapetum contract flags reflow, merged fences, garbled identifiers (`tapetum_llm.md:47`); whisker `_gate_no_empty_code` only fails empty fenced blocks (`gates.py:115-129`, `00-baseline.md:104-110`). Impact: the advisory lane is the deliberate catch for code garbling that survives `unigram_coverage`; model must distinguish tomd's intentional normalization from real damage — a hard discrimination task with no automated oracle.

- [MED] **94% hallucination rate (AA-Omniscience) threatens invented code-defect evidence.** Evidence: `00-baseline.md:188-190` — model rarely abstains; `ground_spans` requires verbatim substring match. Impact: hallucinated corruption quotes are dropped (good), but the model may still emit confident `pass` with empty evidence on corrupted code, producing a false pass the decide step cannot demote.

- [LOW] **2026-07-01 tapetum sighting run adjudicated 196/201 papers but published no per-axis code breakdown.** Evidence: `tapetum-sighting-run-2026-07-01.md` — 0 tier-2 escalations (all triage outside ambiguous band), 5 JSON parse failures on complex papers. Impact: no empirical code-axis precision/recall from our deployment; fast and deep slots were both alliance-pod (V4-Pro), so the cascade did not exercise the planned Gemma-fast / V4-deep split for code triage.

- [LOW] **Text-only serving cannot cross-check against PDF source pixels.** Evidence: `00-baseline.md:211-214` — no vision input; tapetum sees markdown only. Impact: code-axis judgment is rubric-based C++ literacy, not pixel-level verification; acceptable for advisory use but caps ceiling on "prove this fence matches the PDF."

## False-pass hypothesis

A `requires` clause or nested template line is reflow-wrapped inside a fence so a single logical token breaks across two lines (e.g. `requires\n  same_as<T, decltype(f(x))>` split mid-identifier). The block remains syntactically plausible C++, passes whisker's `no_empty_code` gate and order-blind unigram coverage, and V4-Pro adjudicates `pass` because identifiers and angle brackets "look like WG21 code" without treating the spurious line break as a major defect — yet a committee member copying the example gets wrong code.

## False-fail hypothesis

tomd's sanctioned PDF kerning cleanup in `code_format.py` emits spaces inside template-ids (`template <typename To, typename From >`, `converting_limits_throws <To, From >()`). V4-Pro flags the **code** axis as `fail`/`major` for "garbled identifiers" when the output is intentional, readable normalization — a false fail on an artifact the converter deliberately preserves for safety.

## What would change my mind

A Lane-3-style corpus of **≥20 WG21 papers** with human-verified `code` facts (present/absent/order on critical template lines, `requires` clauses, grammar productions) run blind against V4-Pro adjudication, showing **≥90% recall** on injected corruption cases and **≤5% false-fail** on clean tomd-normalized templates — mirroring the P4182R0 comprehension validation (`whisker/CLAUDE.md` Lane 3 POC).
