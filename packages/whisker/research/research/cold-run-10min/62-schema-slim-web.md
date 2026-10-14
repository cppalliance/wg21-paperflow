# 62 — Web forage: xgrammar / outlines / guidance overhead on MoE decode + UnitCheck schema slim

**Query:** Constrained-decoding overhead (XGrammar, Outlines, Guidance/llguidance) on MoE
decode for nested Pydantic/JSON schemas, plus concrete ways to slim
`UnitCheck` / `DefectFinding` so the grammar engine stays on the fast path.

**Scope:** 2024–2026 web sources (XGrammar paper/blog, vLLM structured-decode
intro, SqueezeBits guided-decoding bench, llguidance docs, Red Hat / course
notes). Evidence cards first; UnitCheck tactics grounded in
`packages/whisker/src/whisker/tapetum_llm/models.py` (`UnitCheck` → nested
`list[DefectFinding]`).

**Local schema shape (anchor):**

```
UnitCheck { reasoning, unit_id, defects: DefectFinding[≤5], verdict, confidence }
DefectFinding { defect_type:str, source_unit, source_quote, candidate_location,
                affected_count:int≥1, severity:Literal×4, reasoning }
```

Nesting depth is shallow (2) but the **array-of-objects** + free-string leaves
are what expand PDA states / context-dependent tokens.

**Known local tension (do not ignore):**
`research/tapetum-llm-throughput/13-determinism-guardian.md` warns that
shrinking field *count* can raise rerun variance on Qwen MoE. Slim tactics
below target **grammar / envelope cost**, not "delete semantic axes." Prefer
bifurcation and enum-hardening over deleting `verdict`/`confidence`.

---

## Finding cards

### 1. Naive Outlines-era tax was per-token mask work; XGrammar was built to kill it

- **Title:** Outlines vs XGrammar vs llguidance: Constrained Decoding Without the Throughput Tax
- **URL:** https://dreaming.press/posts/outlines-vs-xgrammar-vs-llguidance.html
- **Summary:** First-gen FSM masking (Outlines lineage) recomputes legal-token
  sets every decode step; nested JSON + large vocab makes that a real critical-
  path tax at batch. XGrammar splits context-independent (precomputable,
  cacheable) vs context-dependent tokens, keeps a pushdown stack for nesting,
  and overlaps mask work with the GPU forward; paper claims up to ~100× faster
  per-token grammar processing and near-zero end-to-end overhead when
  co-designed with the engine. llguidance (Guidance backend) reports ~50 µs
  single-core mask for a 128k tokenizer. vLLM `auto` prefers XGrammar and
  falls back to guidance / outlines / lm-format-enforcer when the schema needs
  unsupported features.
- **Relevance:** HIGH
- **MoE note:** On MoE, the GPU forward is already heavy (expert routing /
  all-to-all). Overlap helps only while mask CPU stays under forward time; if
  mask or compile stalls, the whole batch waits (see card 3).

### 2. XGrammar paper: nested CFG is where the win (and the state) lives

- **Title:** XGrammar: Flexible and Efficient Structured Generation Engine for LLMs (arXiv)
- **URL:** https://arxiv.org/pdf/2411.15100
- **Summary:** Regex-style engines struggle with arbitrarily nested JSON;
  XGrammar uses a pushdown automaton. Benchmarks (Llama-3.1-8B, RTX 4090):
  under ~40 µs/token mask for JSON Schema / CFG-JSON; up to ~3× vs best
  baseline on JSON Schema and **>100× on nested CFG** workloads. End-to-end
  TPOT overhead cited elsewhere from the same lineage as ~1% on simple
  schemas when overlapped (Microscale lesson: 6.2→6.3 ms batch-1).
- **Relevance:** HIGH
- **Conflict note:** "Near-zero" is for *well-supported, cache-friendly*
  schemas with overlap. Nested arrays-of-objects still expand PDA states;
  complexity shows up as compile cost / context-dependent fraction, not as
  "JSON Schema is free forever."

### 3. SqueezeBits: repetitive simple schema → XGrammar; complex/dynamic → stalls on vLLM

- **Title:** Guided Decoding Performance on vLLM and SGLang
- **URL:** https://blog.squeezebits.com/guided-decoding-performance-vllm-sglang
- **Summary (2025-09, Qwen3-8B/32B, H100):** XGrammar precomputes
  context-independent masks and caches grammars; for **complex** schemas with
  many context-dependent tokens, "performance may degrade." On repetitive
  simple schemas, XGrammar beats LLGuidance. On **unique complex** schemas
  (`Github_medium`), XGrammar on vLLM shows **erratic throughput drops**
  attributed to CPU bottlenecks during mask generation for new complex
  grammars (engine-wide stalls). vLLM guided decode already drops vs baseline
  at batch ≥8 when mask gen is not overlapped; SGLang hides more by
  overlapping mask with GPU. LLGuidance is better for one-off complex
  schemas (lazy automaton, trie walk) but loses on repeated simple schemas.
- **Relevance:** HIGH for MoE fleet at `max-num-seqs` 16
- **Tapetum map:** Unit checks reuse one fixed `UnitCheck` schema → XGrammar
  cache should hit. The remaining risk is **schema complexity** (nested
  `DefectFinding[]` + free strings + numeric bounds), not schema churn.

### 4. Unsupported keywords force Outlines / guidance fallback (slow path)

- **Title:** vLLM #12201 — `minItems`/`maxItems` fail on xgrammar; fallback gaps
- **URL:** https://github.com/vllm-project/vllm/issues/12201
- **Summary:** XGrammar historically **warns/ignores** array `minItems` /
  `maxItems` (also `uniqueItems`, contains-family). vLLM's auto-fallback to
  Outlines did not always catch these keywords, so you can get either
  (a) wrong unconstrained array lengths or (b) a silent trip onto a slower
  backend when the filter *does* fire. Separate PRs add Outlines fallback for
  regex/`pattern` and numeric-range features XGrammar lacked.
- **Relevance:** HIGH for `defects: list[...] max_length=5` and
  `affected_count: int ge=1` / `confidence: float ge/le`
- **Implication:** Pydantic `max_length` on lists and `ge`/`le` on numbers are
  exactly the kind of JSON-Schema constraints that historically left the
  XGrammar fast path. Prefer prompt-side caps + post-validators (already used
  for `verdict_matches_defects`) over grammar-enforced bounds when decode
  cost matters.

### 5. Guidance/llguidance: fast TTFT on large schemas; still not free on deep nests

- **Title:** Structured outputs in vLLM (Red Hat) + llguidance README
- **URLs:** https://developers.redhat.com/articles/2025/06/03/structured-outputs-vllm-guiding-ai-responses ;
  https://github.com/guidance-ai/llguidance
- **Summary:** Guidance backend computes masks on the fly (good TTFT / large
  or novel schemas). XGrammar wins cached long generations. llguidance claims
  ~50 µs avg mask (JSON Schema Bench), but full masks can be ~1.5 ms; rare
  tails still tens of ms. Course notes (The Neural Base) claim deep nesting
  (5+ levels) can add measurable latency (cited 5–15%, up to ~20–30% for
  heavy item counts) — treat magnitudes as vendor-ish, direction as real:
  **depth × array fan-out × free-text leaves** raise context-dependent work.
- **Relevance:** MED
- **MoE note:** Alliance MoE decode is already expert-bound; a 1–2 ms mask
  may hide, a compile stall or Outlines fallback will not.

### 6. Local envelope math: UnitCheck JSON is ~half schema tokens when clean

- **Title:** Prior local model (tapetum speedup #108)
- **URL:** (workspace) `research/tapetum-llm-speedup/108-sglang-structured-output.md`
- **Summary:** Zero-defect `UnitCheck` ~167 chars (~42 tok), ~46% envelope;
  one-defect ~404 chars (~100 tok), ~50% envelope. Decode is a small slice of
  ~20 s/call wall (~7%), so schema slim alone cannot hit 5–10 min fleet, but
  it still cuts (a) grammar complexity, (b) fallback risk, (c) output tokens
  on the ~1510 unit calls/paper path.
- **Relevance:** HIGH for prioritization

---

## UnitCheck: what makes the grammar fat

| Feature | Why it costs | Location |
|---|---|---|
| `defects: list[DefectFinding]` | Nested object CFG + array PDA; every field name is a context-dependent branch | `models.py` UnitCheck |
| Free `defect_type: str` | Open string vs closed enum → huge legal-token sets inside the nest | DefectFinding |
| Per-defect free strings (`source_quote`, `candidate_location`, `reasoning`) | Long unconstrained spans inside the nested object | DefectFinding |
| `max_length=5` on list | Historically weak/ignored or Outlines-fallback on XGrammar | UnitCheck.defects |
| `ge`/`le` on ints/floats | Numeric-range keywords historically unsupported → fallback | confidence, affected_count |

---

## Three concrete schema-slim tactics

### Tactic A — Bifurcate the common pass path (biggest win)

Ship two `output_type`s:

1. **`UnitCheckClear`**: `{ reasoning, unit_id, verdict: Literal["pass"], confidence }` — **no** `defects` field.
2. **`UnitCheckDefects`**: current nested shape (or Tactic B/C slimmed nest), only when the clear call returns non-pass *or* a cheap heuristic says the unit is risky.

Web rationale: XGrammar's cache + near-zero path loves a tiny repetitive schema;
SqueezeBits shows complex nested schemas are what stall vLLM CPU. Local
rationale: ~70% of unit calls are zero-defect (`108` / cold-run baseline), so
most MoE decode steps never enter the nested PDA.

Stability guard: keep the same semantic fields on the defect path; do not
delete axes on the clear path beyond omitting an empty list.

### Tactic B — Enum-harden leaves; drop grammar bounds

Inside `DefectFinding` (or the defect-path schema):

1. Change `defect_type: str` → `Literal["qualifier_omission", "heading_drift", ...]`
   (the categories already listed in the Field description).
2. Drop JSON-Schema `maxItems` / `ge`/`le` from the *served* schema (keep
   Pydantic validators / `ModelRetry` after parse — you already do
   `verdict_matches_defects`).
3. Cap quote length in the **prompt** ("max 25 words") rather than
   `maxLength` in the grammar if the backend still struggles with string
   bounds.

Web rationale: closed enums shrink context-dependent token sets; avoiding
`minItems`/`maxItems`/numeric ranges keeps vLLM on XGrammar instead of
Outlines. Outlines fallback reintroduces the throughput tax the MoE pod
cannot afford at batch 16.

### Tactic C — Flatten or collapse the nest (cut PDA depth / fan-out)

Pick one, in order of preference:

1. **Single optional defect object** (or `max 1` via product rule, not
   `maxItems`): `defect: DefectFinding | None` instead of `list` of five.
   Scale stays in `affected_count`; representative quote stays one.
2. **Flat parallel arrays** at the top level (same length, validated after):
   `defect_types[]`, `source_quotes[]`, `severities[]` — removes
   object-in-array nesting (the CFG pain point in the XGrammar paper) at the
   cost of a length-alignment validator.
3. **Strip low-signal nest fields**: drop `candidate_location` and
   per-defect `reasoning` from the structured schema; keep one top-level
   `reasoning` (already present). Cuts ~2 free-string leaves per defect.

Web rationale: nested CFG / array-of-objects is where engines either win big
(XGrammar) or stall (complex mask); flattening reduces states. Local
rationale: defect groups are already "representative + count," not exhaustive
evidence (`whisker` CLAUDE.md), so `list≤5` is product luxury, not a
correctness requirement.

---

## What not to do

- Do not strip `verdict` / `confidence` / top-level `reasoning` hoping for
  determinism wins; prior guardian evidence says fewer fields can *increase*
  variance.
- Do not assume "XGrammar ⇒ free" on MoE: at batch ≥8 on vLLM, mask CPU
  still taxes TPOT if not overlapped; complex nests amplify that.
- Do not add `$ref`-heavy or recursive Pydantic models; they are the classic
  fallback / compile-timeout triggers on JSONSchemaBench-style suites.

---

## Sources

1. https://dreaming.press/posts/outlines-vs-xgrammar-vs-llguidance.html
2. https://arxiv.org/pdf/2411.15100
3. https://blog.mlc.ai/2024/11/22/achieving-efficient-flexible-portable-structured-generation-with-xgrammar
4. https://vllm.ai/blog/2025-01-14-struct-decode-intro
5. https://blog.squeezebits.com/guided-decoding-performance-vllm-sglang
6. https://github.com/vllm-project/vllm/issues/12201
7. https://developers.redhat.com/articles/2025/06/03/structured-outputs-vllm-guiding-ai-responses
8. https://github.com/guidance-ai/llguidance
9. https://www.microscale.academy/act/serving/lesson/constrained-decoding
10. Workspace: `packages/whisker/src/whisker/tapetum_llm/models.py`,
    `research/tapetum-llm-speedup/108-sglang-structured-output.md`,
    `research/tapetum-llm-throughput/13-determinism-guardian.md`
