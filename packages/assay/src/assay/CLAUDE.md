# assay

Two-pass structural analysis pipeline for WG21 proposals. Project-wide rules live in the root `CLAUDE.md`; framework rules in `packages/pipeline/src/pipeline/CLAUDE.md`.

## Authority

`assay.md` is the upstream authority for pipeline structure. It defines the step sequence, step metadata (model slot, max-output, thinking-budget, tools), and all LLM-facing instructions. Python conforms.

## What this pipeline does

Two-pass architecture: Pass 1 (Steps 0-8) extracts mechanically and derives a thesis. Pass 2 (Steps 9-17) verifies, researches, and analyzes with the thesis injected. Six lenses: Performance, Design, Specification, Usability, Ecosystem, Rationale. The pipeline produces a structural assay report and persists all intermediate artifacts (claims, evidence, gaps, thesis, findings) to paperstore for downstream consumption by agora.

18 steps (0-17), all serial.

## Layout

- `assay.md` - prompt document and pipeline authority.
- `models.py` - Pydantic models for domain types, LLM output types, and pipeline state.
- `harness.py` - pure Python: collect/dedup, gap upgrade, challenge kill filters, synthesize verdict. No LLM, no network I/O.
- `rag.py` - ephemeral RAG index: build vector index over cited papers, query for evidence injection. No LLM, embedder only.
- `pipeline.py` - async orchestration: step hooks, dispatch loop, `assay_paper()` / `assay_since()` entry points.
- `render.py` - renders the assay report and diagnostic trace.

## Pipeline steps

```
 0. Receive        validate path, load metadata                   (pure Python)
 1. References     mechanical ref extraction, cross-check          (pure Python)
 2. Index          build RAG index over cited papers               (pure Python, embedder)
 3. Survey         blanking, chunking, wording signal, triage      (pure Python)
 4. Extract        per-chunk item extraction                       (LLM, C calls)
 5. Decide         per-chunk claim support judgment                (LLM, C calls)
 6. Classify       turn unsupported claims into gaps               (LLM, C calls)
 7. Collect        dedup items, group gaps, aggregate asks         (pure Python)
 8. Derive         thesis compression, load-bearing identification (LLM, 1 call)
 9. Verify         cross-check claims against companion papers     (LLM, 1 call)
10. Research       per-lens external evidence lookup              (LLM, 6 calls)
11. Probe          stale refs, author overlap                      (pure Python)
12. Analyze        per-chunk analysis with thesis                  (LLM, C calls)
13. Rationale      SD-4 checklist, quality findings               (LLM, 1 call)
14. Challenge      cross-examine findings                          (LLM)
15. Couple         compound dynamic detection                      (LLM, 1 call)
16. Synthesize     promote Major, derive verdict                   (pure Python)
17. Report         render markdown                                 (pure Python)
```

LLM steps resolve model slots from ``assay.md`` metadata (``**model:**``, ``**max-output:**``, ``**thinking-budget:**``). Pure-Python steps declare ``**model:** none``.

## Invariants

- `assay.md` is the authority. Step metadata drives model slot and budget.
- No prompt strings in Python. All LLM-facing text comes from `assay.md` at runtime via `ctx.sections`. The step body text above `---` is the prompt; text below `---` is documentation.
- `harness.py` stays pure Python. No LLM calls, no network I/O.
- Fully batch. No interactive steps. No user identity.
- Paper text never enters the main context. All paper access through sub-agent calls with `ctx.inject_untrusted(format_numbered_lines(...))`.
- Serial execution. All LLM calls are sequential `for` loops with `await agent.run()`. No `asyncio.gather`, no `run_task`.
- Intermediate artifacts (claims, evidence, gaps, thesis, findings) are persisted to paperstore via `_persist_step` for downstream agora consumption.
- All LLM output types are frozen `BaseModel` with `output_type=`. Post-LLM fixup via `model_copy(update=...)`.
- Open-weight models are the production target. Prompts and schemas must work with `vllm_thinking` backends (Gemma, Qwen), not just Anthropic. Schema compliance issues on smaller models are solved with retries and prompt engineering. See root `CLAUDE.md` Model sovereignty.
