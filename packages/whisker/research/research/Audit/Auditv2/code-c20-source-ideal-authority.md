# C20 Source-Aware and Ideal Authority

**Role**: Audit source vs ideal authority and ideal consumption boundaries.
**Audited state**: whisker 0.5.0, HEAD 51cb704 + local mods.
**Gates**: D4 (Ideal as structural reference, not factual authority), D1 (All LLM via pipeline).

## 1. Scope

Verify that the source document (PDF/HTML) is the factual authority, the
ideal is structural reference only, whisker does not copy ideals into its
own tree, and ideal consumption from tomd is read-only.

## 2. Commands and Exits

```
uv run --package whisker pytest packages/whisker/tests/test_golden_ideals.py -v
```

Exit: Offline suite passes (E1). Ideal scoring is pure Python (no LLM).

## 3. Current Evidence

### 3.1 Ideal location: tomd owns, whisker reads

`golden_ideals.py` line 51:
```python
_IDEALS_RELPATH = Path("packages") / "tomd" / "tests" / "fixtures" / "golden" / "ideals"
```

Ideals live ONLY in `packages/tomd/tests/fixtures/golden/ideals/`. Whisker
discovers them by walking up the directory tree to the workspace root
(`find_ideals_dir()`, lines 73-91). It never copies, moves, or creates
ideal files.

`ideal_path()` (lines 94-106) does a case-insensitive stem lookup on the
directory. `list_ideal_stems()` (lines 109-111) returns sorted lowercase stems.

### 3.2 Read-only consumption

`golden_ideals.py` line 29: "Pure functions; the module never writes.
Callers persist." The module has no `write`, `mkdir`, `open(..., 'w')`, or
any mutation operation. It only calls `candidate.is_file()` and reads file
content.

No tomd-private imports exist in `golden_ideals.py`. The module imports
only from `whisker.bench`, `whisker.metrics`, and `whisker.tables`.

### 3.3 Source is factual authority in ideal verifier

`ideal_verify.py` line 26-38 (system prompt):
```
"The source remains the highest authority for factual content. The ideal
is human-blessed STRUCTURAL ground truth for how that source should be
represented in Markdown."
```

The ideal verifier explicitly states source authority over ideal authority.
The prompt instructs the LLM to compare candidate vs ideal for structural
representation, not to treat the ideal as the absolute truth about content.

### 3.4 Ideal verdict is advisory and demotion-only

`golden_ideals.py` lines 24-27 (docstring):
```
Verdict policy: ideal agreement stays ADVISORY (a review flag at most,
never a hard fail).
```

In `score.py` `_decide()` (lines 205-215), ideal results produce only
soft flags:
```python
if value is not None and value < floor:
    soft.append(f"ideal {axis} {value:.3f} < {floor} (advisory)")
```

These are soft flags (review at most, never hard fail). The `ideal ` prefix
on these flags is used by fusion to block LLM clear operations.

### 3.5 Ideal in fusion: demotion-only

`fusion.py` implements multiple ideal-related rules:

1. **ideal_review_cap** (constants.py line 138): When the ideal verifier
   returns `review` (discrepancies found), a non-fail combined advisory
   verdict is capped at `review`. An LLM `pass` cannot produce combined
   `pass` when the ideal disagrees.

2. **ideal `agree` never promotes**: There is no code path where
   `ideal_verdict == "agree"` upgrades, rescues, or clears any verdict.

3. **clear_blocked_ideal_flag** (constants.py line 150): Deterministic
   soft flags with the `ideal ` prefix block the `llm_clear_soft_review`
   rule. Even without ideal verifier data in the tapetum sidecar, the
   deterministic ideal signal prevents LLM soft-review clearing.

### 3.6 Ideal verifier grounding

`ideal_verify.py` `_require_raw_exact_evidence()` (lines 114-131):
Every discrepancy must cite raw exact quotes from both the candidate
AND the ideal. If either quote cannot be grounded (found verbatim in its
respective document), `IdealVerificationError` is raised, failing the
paper's advisory run rather than emitting partial evidence.

This is stricter than the main grounding: no fuzzy tier, no ambiguous
state. Exact or fail.

### 3.7 Ideal fingerprinting

`tapetum_llm.md` lines 86-89: Incremental fingerprints include ideal
presence/content, verifier prompt contract, output schema, service
configuration, and model identity. Adding, changing, or removing an ideal
invalidates the cached result. Existing sidecars without ideal data remain
readable.

### 3.8 No ideal copies in whisker

Grep evidence: no file under `packages/whisker/` has a `.md` extension
that duplicates a tomd ideal. The `_IDEALS_RELPATH` constant points to
`packages/tomd/`. No code in whisker creates files under that path.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | Source declared as factual authority in ideal verifier system prompt | Informational | HIGH |
| F2 | Ideal files live in tomd, whisker reads them read-only via path lookup | Informational | HIGH |
| F3 | Ideal verdict is demotion-only: review cap, never promote, agree is neutral | Informational | HIGH |
| F4 | Deterministic ideal soft flags block LLM clear even without verifier data | Informational | HIGH |
| F5 | Ideal verifier requires raw exact quotes (no fuzzy), fails on ungrounded | Informational | HIGH |
| F6 | Incremental fingerprints include ideal presence and content | Informational | HIGH |

No violations found.

## 5. False-Pass Hypothesis

**Could an ideal override the source as factual authority?**

The system prompt explicitly states source authority. The ideal verifier
compares structural representation, not factual content. Even if the LLM
misinterpreted the instruction, the ideal verdict is demotion-only in
fusion: it can cap at review but never promote to pass or override a fail.
The deterministic lane's `_decide()` treats ideal results as soft flags only.

**Could removing an ideal silently change behavior?**

Removing an ideal removes the `ideal ` soft flags from `_decide()` and the
`ideal_review_cap` from fusion. A paper that was previously capped at
review due to ideal disagreement would now be eligible for LLM clear. This
is by design (documented in tapetum_llm.md lines 86-89: fingerprint
includes ideal presence, so the sidecar is invalidated). However, the
behavioral change is one-directional: removal can only relax verdicts (from
review to pass), never tighten them.

## 6. Gate/Dimension Mapping

- **D4 (Ideal as structural reference)**: PASS. Source is factual authority.
  Ideal is structural ground truth. No ideal promotes, rescues, or overrides.
- **D1 (All LLM via pipeline)**: PASS. Ideal verifier uses `run_task()` from
  pipeline with `output_type=IdealVerification`.

## 7. Limitations

- Cannot verify live ideal verifier behavior (runtime BLOCKED).
- Cannot verify that the LLM correctly interprets the source-over-ideal
  authority instruction in practice.
- The ideal path discovery depends on directory-tree walking; non-standard
  workspace layouts could fail silently (returns None, skips ideals).

## 8. Conclusion

The source-vs-ideal authority claim holds. The source is explicitly declared
as factual authority in the ideal verifier system prompt. Ideals live in
tomd's fixture tree and are consumed read-only by whisker. Ideal verdicts
are strictly demotion-only in both the deterministic lane (soft flags) and
fusion (review cap, agree is neutral). The ideal verifier requires exact
raw quotes for grounding, failing on ungrounded evidence rather than
emitting partial results.
