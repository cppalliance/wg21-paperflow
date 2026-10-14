# C17 Cascade and Topology

**Role**: Audit the two-tier cascade architecture.
**Audited state**: whisker 0.5.0, HEAD 51cb704 + local mods.
**Gates**: D1 (All LLM calls via pipeline), D2 (Model identity).

## 1. Scope

Verify the two-tier cascade design: escalation triggers, per-paper seriality,
cross-paper concurrency, aggregation rules for oversized papers, and failure
isolation.

## 2. Commands and Exits

```
uv run --package whisker pytest packages/whisker/tests/test_tapetum_llm.py -v
```

Exit: Offline tests pass (E1). Runtime cascade behavior BLOCKED.

## 3. Current Evidence

### 3.1 Two-tier cascade architecture

The cascade has four steps (0-3), defined in `tapetum_llm.md` lines 11-17:

| Step | Name | Model | LLM? |
|------|------|-------|------|
| 0 | Select | none | No (pure Python) |
| 1 | Triage | fast | Yes |
| 2 | Adjudicate | deep | Yes (conditional) |
| 3 | Decide | none | No (pure Python) |

Steps 0 and 3 are pure Python (no LLM). Steps 1 and 2 use the `fast` and
`deep` slots respectively. Currently both resolve to `alliance-pod`
(deepseek-v4-pro).

### 3.2 Escalation triggers

`_escalation_signals()` (adjudicate.py lines 252-275) defines three derived
uncertainty signals:

1. **SIGNAL_AXIS_CONFLICT**: Tier-1 per-axis verdicts contain both a `pass`
   AND a `fail` (internal contradiction). Measured: 123/198 papers had axis
   disagreement in production.

2. **SIGNAL_UNGROUNDED_EVIDENCE**: At least one Tier-1 evidence quote failed
   `ground_spans()` against the markdown. The model cited text that is not
   in the document.

3. **SIGNAL_CONFIDENCE_AMBIGUOUS**: Self-reported confidence falls in
   `[CONFIDENCE_AMBIGUOUS_LO (0.35), CONFIDENCE_AMBIGUOUS_HI (0.65)]`.
   Retained as one trigger among three but proven dead in production (0/198
   escalations via this signal alone; DeepSeek confidence never left
   [0.85, 1.00]).

All three signals are evaluated. If ANY fires, Step 2 runs. Signals are
sorted and recorded in the sidecar as `escalation_signals`.

### 3.3 Chunked papers (oversized aggregation)

`_custom_triage()` (adjudicate.py lines 228-249):
- Papers within `MAX_PAPER_MD_CHARS` (500,000) get a single LLM call.
- Oversized papers are split on H2 boundaries via `chunk_markdown()`.
- Chunks are triaged SERIALLY (one at a time, not parallel).
- Results are aggregated via `aggregate_adjudications()`.
- `state.chunked = True` is set, and `state.partial = True` if a hard-split
  occurred.

`_custom_adjudicate()` (lines 278-296): Chunked papers NEVER escalate to
Tier 2 (re-injecting full markdown would exceed context budget). The
aggregated Tier-1 stands.

### 3.4 Per-paper seriality (intra-paper)

Within one paper, the cascade is serial:
1. Step 0 (select) -> Step 1 (triage) -> Step 2 (adjudicate, conditional) -> Step 3 (decide)
2. For chunked papers, chunks are processed serially in `_custom_triage()`.
3. The pipeline `dispatch()` runs steps in sequence.

`tapetum_llm.md` line 27: `concurrency: 1` confirms one in-flight request
per paper for the cascade.

### 3.5 Cross-paper concurrency

`tapetum_llm/cli.py` controls batch-level parallelism:
- `--concurrency N` (default 32): Up to N independent papers adjudicated
  concurrently via `asyncio.gather()`.
- Server cap: 16 max sequences on the vLLM pod (overfill to 32 for backfill
  efficiency, documented in `tapetum_llm.md` lines 29-31).

Cross-paper concurrency is independent of per-paper seriality. Each paper
runs its own cascade; papers do not share LLM state.

### 3.6 Per-slot output token ceilings

`adjudicate.py` lines 87-91:
```python
_SLOT_MAX_TOKENS = {"fast": 1024, "deep": 2048}
_DEFAULT_MAX_TOKENS = 2048
```

These are bound at `AgentBackend` construction per slot. The deep slot gets
double the token budget for its more careful re-read.

### 3.7 Aggregation rules (worst-axis)

`worst_axis_verdict()` (from `chunking.py`) implements severity-aware
worst-axis folding: a `fail` axis only becomes a hard overall `fail` when
its severity is `major`. A non-major `fail` folds to `review`.

`aggregate_adjudications()` merges chunk results by taking the worst
per-axis finding across all chunks, then applies `worst_axis_verdict`.

### 3.8 Failure isolation

Per the cascade design, failures are isolated at multiple levels:

1. **Step-level**: If Step 1 produces no result (`state.tier1 is None`),
   Step 2 short-circuits (line 280: `if state.tier1 is None: return`).
   Step 3 also short-circuits (line 302: `if working is None: return`).

2. **Paper-level**: `_adjudicate_one()` in `cli.py` wraps each paper in
   a try/except firewall. A failed paper writes an error tombstone and
   the batch continues.

3. **Chunk-level**: Each chunk call is awaited individually. A chunk
   failure propagates to the paper level, which writes the error tombstone.

### 3.9 Safety demotions in Step 3

`_custom_decide()` (adjudicate.py lines 299-349) applies multiple safety
demotions (never upgrades):

- Ungrounded evidence + non-pass verdict: demote to review
- Pass with emitted but entirely dropped evidence: demote to review
- Pass with only fuzzy evidence: demote to review
- Sub-floor confidence (< 0.50): demote to review
- Partial read (oversized hard-split): demote to review

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | Three escalation triggers (axis conflict, ungrounded evidence, confidence band) | Informational | HIGH |
| F2 | Confidence band proven dead in production (0/198 escalations) | LOW (cosmetic dead gate) | HIGH |
| F3 | Chunked papers skip Tier 2 escalation (by design) | Informational | HIGH |
| F4 | Per-paper seriality enforced; cross-paper concurrency at 32 | Informational | HIGH |
| F5 | Severity-aware worst-axis aggregation prevents cosmetic fail escalation | Informational | HIGH |
| F6 | Five safety demotions in decide step, all one-way (never upgrade) | Informational | HIGH |

No violations found.

## 5. False-Pass Hypothesis

**Could a paper bypass the cascade and receive a verdict without proper evaluation?**

The only bypass is `select_candidates()` which filters papers before the
cascade. Papers not selected never enter the cascade and retain their
deterministic verdict only. Within the cascade, every paper that enters
gets at minimum a Tier-1 triage (Step 1) and a decide (Step 3). There is
no path to produce a `TapetumResult` without running these steps.

**Could the dead confidence band mask a needed escalation?**

The confidence band is one of THREE triggers. Axis conflict and ungrounded
evidence are the effective triggers. Production data shows these fire on
genuine contradictions. The dead band is cosmetic: removing it would not
change behavior.

## 6. Gate/Dimension Mapping

- **D1 (All LLM via pipeline)**: PASS. Text cascade uses `run_agent()` from
  pipeline. PDF judge uses `run_judge_task()` via `AgentBackend.run()`.
- **D2 (Model identity)**: PASS. `tier1_model` and `tier2_model` recorded
  in sidecar. Service names resolved from SERVICES.toml slots.

## 7. Limitations

- Runtime proof BLOCKED: cannot observe live escalation behavior, actual
  model responses, or real-world chunking of oversized papers.
- The confidence band trigger has been effectively dead. Its retention is
  harmless but adds dead code to the escalation logic.
- Cannot verify that the 32-paper concurrency interacts correctly with the
  16-slot server cap under load (requires a live pod).

## 8. Conclusion

The two-tier cascade is well-structured. Escalation triggers are
evidence-based (axis conflict, ungrounded evidence) rather than relying on
unreliable self-reported confidence. Per-paper seriality ensures
deterministic intra-paper ordering. Cross-paper concurrency (32) is
independent and isolated. Oversized papers are chunked and aggregated.
Five safety demotions in the decide step ensure advisory verdicts never
overstate confidence. The architecture is sound; runtime verification
requires a live endpoint.
