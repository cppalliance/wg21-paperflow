# 15 — Verdict-first design: UnitCheckClear micro-schema + fail-path bifurcation

**Verdict:** usable-with-conditions — two-stage `UnitCheckClear` → `UnitCheckDefects`
bifurcation is the highest-yield decode shrink on the surviving metadata-pass unit
path; rescale after v11 short-circuit yields **~92 s central (~77–110 s)** from
unit bifurcation alone and **~155 s central (~124–155 s)** for the full MODERATE
verdict-first stack, all at **S=16**. Does not close the ≤600 s gap without other
levers (dual-pod blocked in this corpus).
**Confidence:** medium-high (grounded in measured P50 completions + overlap-correct
stacking from `11-wall-arithmetic.md`)

**Hard constraint:** Single `alliance-pod`, S_eff = **16** only (`00-baseline.md`).

---

## Problem statement

After v11 metadata Tier A+B short-circuit (−847 unit calls, **−1059 s @ S=16**),
the fleet is still decode-bound on surviving unit checks:

| Metric | Pre-short-circuit | Post-short-circuit (Tier A+B) |
|--------|------------------:|------------------------------:|
| Fleet calls | 2284 | **1419** |
| Unit checks | 1510 | **663** |
| Zero-defect unit checks | 1057 (70%) | **~463** (69.8% of survivors) |
| Per-call wall | ~20 s | ~20 s (unchanged) |
| Single-pod MODERATE wall | — | **~1493 s** |

70% of unit checks emit a full nested `UnitCheck` JSON with empty `defects[]`
while the model still decodes `reasoning` (40 words), five-field `DefectFinding`
grammar states, and `max_length=5` array bounds — all consumed on the pass path
for no downstream value.

Evidence: `UnitCheck` at `models.py:298-320`; P50 pass JSON **77 tok** with
**~55 tok** in `reasoning` alone (`47-max-tokens-shrink.md:16`, `14-output-token-surgeon.md:8`);
fusion and grounding skip unit reasoning on pass (`unit_judge.py` persists only).

---

## Anchor: current `UnitCheck` schema

From `packages/whisker/src/whisker/tapetum_llm/models.py`:

```
UnitCheck {
  reasoning: str          # "At most 40 words" — FIRST field (CoT floor, models.py:14-15)
  unit_id: str
  defects: list[DefectFinding]  # max_length=5 — nested array-of-objects
  verdict: Verdict
  confidence: float      # ge=0.0, le=1.0
}
DefectFinding {           # models.py:231-259 — 7 fields, 3 free strings
  defect_type: str, source_unit, source_quote, candidate_location,
  affected_count: int≥1, severity: Literal×4, reasoning
}
@model_validator verdict_matches_defects  # models.py:315-320
```

Field order is deliberate: `reasoning` first forces auditable CoT before verdict
(`models.py:12-16`). That trades decode tokens for inspectability on **every** call,
including the 70% pass path where nothing reads the prose.

Grammar cost (62-schema-slim): nested `defects[]`, free `defect_type: str`,
`max_length=5`, and `ge`/`le` on numeric fields push vLLM XGrammar toward
context-dependent mask work or Outlines fallback (`62-schema-slim-web.md:88-104`).

---

## Design: bifurcated two-stage unit gate

### Stage 1 — `UnitCheckClear` (micro-schema, ~70% of unit calls)

Ship a separate `output_type` for the default pass path:

```python
class UnitCheckClear(BaseModel):
    """Pass-path micro-schema: no defects nest, verdict locked to pass."""

    unit_id: str = Field(
        description="The unit checked: 'page:5' or 'section:Motivation'"
    )
    verdict: Literal["pass"] = Field(
        description="Clear path only; non-pass routes to UnitCheckDefects."
    )
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(
        default="",
        description="Optional; at most 10 words. Empty on clean pass preferred.",
    )

    @model_validator(mode="after")
    def pass_is_clean(self) -> UnitCheckClear:
        if self.verdict != "pass":
            raise ValueError("UnitCheckClear requires verdict pass")
        return self
```

**Field order:** `unit_id` → `verdict` → `confidence` → optional `reasoning`
(verdict-first, inverted from current reasoning-first `UnitCheck`).

**Target emitted JSON:** ~15–25 tok (`47-max-tokens-shrink.md:44`) vs P50 **77 tok**
today — **~52–62 tok saved per clear call**.

**XGrammar profile (62-schema-slim Tactic A):** flat object, no nested array, no
`maxItems`/`ge`/`le` in served schema (validators post-parse). Stays on cached
XGrammar fast path; ~46% envelope share on current pass JSON drops to ~25%.

**`max_tokens` pairing (`47-max-tokens-shrink.md:39-44`):** pass cap **128**
(1.5× retry ceiling **192**); useless without schema change — cap alone saves 0 s
when model still decodes 77-tok JSON.

### Stage 2 — `UnitCheckDefects` (fail/review path, current shape slimmed)

Only when Stage 1 does not settle the unit:

```python
class UnitCheckDefects(BaseModel):
    """Full defect path — current UnitCheck shape, enum-hardened."""

    unit_id: str
    verdict: Verdict  # pass | review | fail
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(
        description="At most 40 words: what was compared."
    )
    defects: list[DefectFinding] = Field(default_factory=list, max_length=5)
    # DefectFinding: defect_type → Literal[...] (Tactic B, 62-schema-slim)
    # @model_validator verdict_matches_defects — unchanged semantics
```

**Tactic B deltas (`62-schema-slim-web.md:165-180`):**

1. `defect_type: str` → closed `Literal` of the eight categories already listed
   in the Field description (`models.py:234-236`).
2. Drop `ge`/`le`/`maxItems` from the **served** JSON schema; keep Pydantic
   validators + `ModelRetry` after parse (same pattern as `verdict_matches_defects`).
3. Cap quote length in prompt, not grammar `maxLength`.

**`max_tokens` on fail path (`47-max-tokens-shrink.md:40-41`):** **768**
(P90 ~395 tok + margin + 1.5× retry → 1152 effective ceiling).

Do **not** lower the global judge agent default below 768 until routing exists
(`47-max-tokens-shrink.md:56-57`).

### Routing logic (whisker-local, `unit_judge.py`)

```
for each routed unit:
  clear = await run_judge_task(..., UnitCheckClear, max_tokens=128)
  if clear.verdict == "pass" and clear.confidence >= UNIT_CLEAR_CONFIDENCE_FLOOR:
      persist as UnitCheck-equivalent (defects=[], verdict=pass)
  else:
      defects = await run_judge_task(..., UnitCheckDefects, max_tokens=768)
      persist defects result
```

**Escalation triggers to Stage 2:**

| Trigger | Rationale |
|---------|-----------|
| Stage 1 returns `confidence < floor` (e.g. 0.85) | Ambiguous clear |
| Router marked unit high-risk (`table_presence`, keyword delta) | Skip Stage 1 optional fast-path |
| Deterministic pre-screen finds recall below floor | Fail-closed: never clear without Stage 2 |
| Stage 1 transport/parse failure | Retry on Defects schema |

**Optional pessimistic mode:** always run Stage 1 first (no router skip) to
maximize grammar savings; accept +1 call on ~30% defect-path papers
(~200 extra calls × 20 s / 16 ≈ **+250 s** worst case — do not ship without
holdout proof that Stage 1 miss rate ≤5%).

**Recommended default:** run Stage 1 only on metadata-pass papers with
router confidence below high-risk threshold; defect-prone units go straight to
Stage 2 (zero added calls on known-fail path).

### Downstream compatibility

Map both stages to existing `UnitCheck` before persistence:

```python
def to_unit_check(clear: UnitCheckClear) -> UnitCheck:
    return UnitCheck(
        reasoning=clear.reasoning or "unit matches",
        unit_id=clear.unit_id,
        defects=[],
        verdict="pass",
        confidence=clear.confidence,
    )
```

Sidecar schema, fusion, and fingerprint hashes must include `unit_schema_variant`
in the lane fingerprint when A/B-ing.

---

## Savings arithmetic (post short-circuit rescale, S=16)

### Stacking rule (non-negotiable)

From `11-wall-arithmetic.md:18-28`:

```
wall = (N_rem × L) / S_eff + T + C − L_abs
```

Apply **L_abs** (verdict-first decode shrink) on **survivors only**. Do not sum
full-fleet −250 s verdict estimate — 847 eliminated unit checks included ~692
zero-defect calls that verdict-first would have shrunk (**~319 s phantom** if
naively stacked).

### UnitCheckClear component (bifurcation decode shrink)

| Input | Value | Source |
|-------|------:|--------|
| Surviving unit checks post Tier A+B | 663 | `11-wall-arithmetic.md:37` |
| Pass-shaped survivors (69.8%) | **463** | `50-router-false-economy.md:32` |
| Current pass P50 | 77 tok | `47-max-tokens-shrink.md:16` |
| `UnitCheckClear` target | ~20 tok | `47-max-tokens-shrink.md:44`, `62-schema-slim-web.md:153` |
| Tok saved per clear call | **~57 tok** | 77 − 20 |
| Decode rate (pass unit) | ~70 tok/s | `00-baseline.md`, `47-max-tokens-shrink.md:20` |

**Decode-only wall saving:**

```
Δwall_unit = pass_survivors × (tok_saved / tok_rate) / S
           = 463 × (57 / 70) / 16
           ≈ 24 s
```

**Proportional per-call decode model** (matches MODERATE stack closure):

Pass unit decode ≈ (77/235) × 5.91 s ≈ **1.94 s** of the ~20 s call
(fleet mean output 235 tok, decode mean 5.91 s — `47-max-tokens-shrink.md:20`).

```
Δwall_unit = pass_survivors × (57/77) × 1.94 / 16
           = 463 × 0.714 × 1.94 / 16
           ≈ 40 s
```

**Grammar bifurcation uplift (XGrammar fast path, 62-schema-slim):**
Removing nested `DefectFinding[]` on 463 calls avoids context-dependent mask
expansion; local estimate **+30–50 s** at batch 16 (direction from
`62-schema-slim-web.md:49-86`, not yet measured on alliance-pod).

| UnitCheckClear @ S=16 | Low | Central | High |
|------------------------|----:|--------:|-----:|
| Decode shrink only | 24 | **40** | 55 |
| + grammar fast path | 77 | **92** | 110 |

### Full MODERATE verdict-first stack @ S=16 (includes metadata + monolith)

Rescaled from full-fleet naive **−250 s** × survivor ratio **1419/2284**:

```
Δwall_full = 250 × (1419 / 2284) ≈ 155 s
```

Range from overlap sensitivity (`11-wall-arithmetic.md:39`, `47-max-tokens-shrink.md:24`):
**−124 to −155 s**.

| Component | Calls (survivors) | Est. Δwall @ S=16 |
|-----------|------------------:|------------------:|
| `UnitCheckClear` bifurcation | ~463 pass units | **~92 s** (central) |
| `MetadataOutlineCheck` reasoning 40→15 words | 377 | ~8–14 s |
| `PdfJudgment` reasoning 60→20 words on pass | 381 | ~10–18 s |
| **Full stack** | 1419 | **~155 s** (central), **124–155 s** range |

### Single-pod wall after short-circuit + verdict-first

```
wall_post = wall_MODERATE_single_pod − Δwall_full
          ≈ 1493 − 155
          ≈ 1338 s (~22 min)
```

Still **~738 s above** the ≤600 s target (`00-baseline.md:27-28`). Verdict-first
is necessary MODERATE lever #3; not sufficient alone on one pod.

---

## Quality gates (ship blockers)

1. **48-paper holdout:** ≥95% verdict stability vs current schemas
   (`14-output-token-surgeon.md:44`, `47-max-tokens-shrink.md:48`).
2. **Dev-replay 9 golden PRs:** zero silent demotions on table/cell defects
   (`25-quality-gate-protocol.md`).
3. **No vacuous pass widening:** keep `verify_unit_evidence`, keyword delta
   groups, deterministic post-checks (`47-max-tokens-shrink.md:61-62`).
4. **Stage 2 miss rate:** if Stage 1 false-clear rate >5% on holdout, disable
   optimistic routing (always Stage 2 on high-risk signals).
5. **Determinism guard:** do not delete semantic axes on clear path beyond
   omitting empty `defects[]`; fewer fields can raise MoE variance
   (`62-schema-slim-web.md:25-28`, `13-determinism-guardian.md`).

---

## False-pass hypothesis

`UnitCheckClear` with empty `reasoning` on 463 survivor pass calls removes auditable
CoT (`models.py:14-15`). Model returns `{verdict:"pass", defects implicit []}` without
comparing localized source — widening the selection gap (only 16/381 merged verdicts
changed by LLM today, `00-baseline.md`). Mitigation: deterministic post-checks +
holdout A/B before fleet rollout (`47-max-tokens-shrink.md:61-62`).

## False-fail hypothesis

Running Stage 1 then Stage 2 on every unit doubles call count on defect papers
(~200 units × 20 s / 16 ≈ **+250 s**). Mitigation: router-gated Stage 2 skip for
high-risk units; never run bifurcation on `--inspect` / `exhaustive_units` paths
without accounting for doubled N.

## What would change my mind

`--debug` logging of `usage.completion_tokens` per call on 20-paper replay after
`UnitCheckClear` lands: if pass median **>30 tok**, caps below 128 are unsafe; if
median **≤20 tok** and wall delta ≥**90 s** measured (not modeled), central
estimate upgrades; if verdict flips exceed ≥25% rerun instability baseline, revert
to single-schema `UnitCheck` with reasoning cap only.

---

## Implementation checklist (whisker-only)

| Step | File | Change |
|------|------|--------|
| 1 | `models.py` | Add `UnitCheckClear`, `UnitCheckDefects`; enum `defect_type` |
| 2 | `unit_judge.py` | Two-stage routing; `to_unit_check()` mapper |
| 3 | `judge_task.py` | Optional `max_tokens` forward (`47-max-tokens-shrink.md:26-27`) |
| 4 | `unit_judge.py` | Pass **128** / fail **768** caps at call site |
| 5 | Fingerprint | Bump `_LANE_VERSION`; hash schema variant |
| 6 | Tests | Holdout replay fixtures; Stage 1→2 escalation cases |

---

## Executive summary

| Question | Answer |
|----------|--------|
| **UnitCheckClear bifurcation @ S=16 (post short-circuit)** | **~92 s** central (range **77–110 s**) |
| **Full verdict-first MODERATE stack @ S=16** | **~155 s** central (range **124–155 s**) |
| **Single-pod wall after both levers** | **~1338 s** (~22 min) — still misses ≤600 s |
| **Closes 10 min alone?** | **No** — needs additional N cuts or blocked dual-pod |

**Primary return value for parent agent:** estimated verdict-first savings after
short-circuit rescale at **S=16** = **~155 s** (full stack) / **~92 s** (unit
bifurcation only).
