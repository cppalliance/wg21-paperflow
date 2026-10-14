# v2 Charter - Exhaustive line-level verification (40-agent wave)

Date: 2026-07-22. Workspace SHA 51cb704. Corpus: packages/whisker/research/repos/ at the SHAs pinned in ../00-baseline.md. Orchestrator: Fable 5 (charter + synthesis only). All reading agents: composer-2.5-fast.

## Rules

- No experiments, no guesses. Every statement carries a file:line citation or is marked NOT VERIFIED.
- Exhaustive means exhaustive: enumerate every match, every call site, every code path. "Representative examples" are a violation.
- If a file or directory could not be fully covered, the report must say so explicitly under "Coverage gaps".
- Read-only. Never modify any repo clone or workspace file. Each agent writes exactly one report file under research/all-pages-llm-coverage/v2/.

## Claims under test

- **C1 (negative existential):** At the pinned SHAs, NO repo in the corpus contains a production code path where an LLM/VLM judges an ALREADY-PRODUCED conversion output against the source document per page/chunk/unit (i.e. verification of existing output, as our tapetum_llm lane does). Benchmark/eval harnesses count and must be classified too.
- **C2 (positive classification):** Every LLM/VLM invocation site in the LLM-bearing repos is classified as extraction (model produces the output), refinement (model fixes selected blocks of its own pipeline's output), eval-harness (scores outputs offline), or other, with file:line.
- **C3 (our defects):** At 51cb704: (a) cli.py passes `exhaustive` only on the text lane, PDF branch never receives it; (b) empty risk router yields `coverage_complete=True` with zero checked units and fusion trusts it; (c) `_compute_fingerprint` encodes no coverage mode, so `--exhaustive-units` changes behavior without changing the cache key.
- **C4 (decision-critical foreign facts):** (a) olmocr-bench refuses to score when any (pdf, page) lacks a test and auto-injects a per-page BaselineTest; (b) langextract's `extract()` defaults to suppressing parse errors, silently dropping a failed chunk's extractions; (c) marker's `--use_llm` is block-selective (a text-only page can get zero LLM calls) with reject-and-keep gates.

## Required report template (all agents)

```
# <NN> - <scope>
**Claims tested:** C1/C2/C3/C4 (subset)
**Exhaustive:** yes | no (list what was not covered under Coverage gaps)

## Method
Exact search commands run (rg patterns) and files read in full.

## Inventory
(table or list; EVERY item, file:line, one-line role/finding each)

## Verdict on the claim(s)
CONFIRMED / REFUTED (with the refuting file:line) / PARTIALLY (explain)

## Coverage gaps
What was not read and why. "None" only if truly none.

## What could still hide a counterexample
```

## Search floor for LLM call-site agents (minimum rg patterns, add more)

openai, anthropic, claude, gemini, google.genai, genai, litellm, vllm, ollama, chat.completions, completions.create, messages.create, generate_content, GenerativeModel, transformers, AutoModel, .generate(, pipeline(, predict, invoke, prompt, system_prompt, LLM, VLM, gpt-, llama, qwen. Case-insensitive where sensible. Exclude nothing by default; mark test/docs/example hits as such but list them.
