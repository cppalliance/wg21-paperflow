# C13 Corpus and Holdout

**Role:** Audit corpus provenance, holdout isolation, and contamination
boundaries.
**Audited state:** whisker 0.5.0, HEAD 51cb704, Python 3.12.10, pytest 8.4.2.
**Date:** 2026-07-20

## 1. Scope

Verify that the 5 corpus papers have committed artifacts with provenance, that
the holdout manifest is locked, that dev-replay is separate from the holdout,
that `p0533r9` is quarantined, and that no holdout data appears in test
parametrization.

## 2. Commands and Exits

| Evidence | Command / source | Exit |
|----------|-----------------|------|
| E1 | Full test suite 1406p/8s/3x | 0 |
| E2 | Comprehension corpus 9p (3 canaries pass) | 0 |

## 3. Current Evidence

### 3.1 Corpus composition (5 papers)

The corpus directory (`packages/whisker/corpus/`) contains artifacts for 5
canonical papers:

| Paper | .expected.md | .facts.jsonl | .validation.md | Notes |
|-------|-------------|-------------|----------------|-------|
| P4182R0 | Yes | Yes (8 facts) | Yes | Original POC member |
| P4185R0 | Yes | Yes (9 facts, 4 math) | Yes | Math-heavy |
| P4234R0 | Yes | Yes | No | $-identifiers, code/xref |
| N5040 | Yes | Yes | No | Pipe AND HTML tables |
| P0876R23 | Yes | Yes | No | Poll tables, code, xref |

Total: 5 expected snapshots, 5 facts files, 37 verified facts across all papers.

The corpus directory also contains:
- `README.md`: schema documentation and lane descriptions
- `EXAMPLE.facts.jsonl`: worked example for fact authoring

### 3.2 Hermetic CI gate

`test_comprehension_corpus.py` discovers corpus pairs dynamically:

```python
_CORPUS = Path(__file__).resolve().parent.parent / "corpus"

def _corpus_pairs() -> list[tuple[str, Path, Path]]:
    for facts_path in sorted(_CORPUS.glob(f"*{_FACTS_SUFFIX}")):
        pid = facts_path.name[: -len(_FACTS_SUFFIX)].upper()
        expected_path = _CORPUS / f"{pid}{_EXPECTED_SUFFIX}"
        if expected_path.is_file():
            pairs.append((pid, facts_path, expected_path))
```

Guard: `test_corpus_has_at_least_one_comprehension_paper` prevents a vacuous
suite if all snapshots are deleted.

### 3.3 Canary tests (3 exploit classes)

Three canaries prove the gate has teeth, one per exploit class:

1. **Scrambled table cell** (P4182R0, line 83): replaces
   `(CUDA, SYCL) | No |` with `| Yes |`, asserts the `tableA-gpu-coro-no`
   fact fails.

2. **Mangled code snippet** (P4234R0, line 104): replaces
   `asm("Image$$ER_ZI$$Base")` with `asm("Image__ER_ZI__Base")`, asserts the
   `code-asm-alias` fact fails.

3. **Flipped math relation** (P4185R0, line 125): replaces
   `\(x^{2k} \geq 0\)` with `\(x^{2k} \leq 0\)`, asserts the
   `math-even-power-nonneg` fact fails.

All three canaries target verified facts and assert specific fact IDs fail,
preventing vacuous green from any direction.

### 3.4 Dev-replay separation

The dev-replay set is separate from the corpus. Per CLAUDE.md:

> The 9 golden PRs (#282-#286, #290, #293-#295) are the development replay set
> with expected verdicts (`corpus/dev-replay/labels.json`).

The score pinning test uses tomd golden fixtures (19 papers), which are a third
distinct set. The corpus (5 papers), dev-replay (9 PRs), and score-pinning
(19 goldens) do not share membership.

### 3.5 p0533r9 quarantine status

Per CLAUDE.md:
> `p0533r9` is retained only as quarantined audit history and is excluded
> from every holdout metric because it is PR #293. Never tune thresholds
> on the holdout.

`p0533r9` appears in the score-pinning baseline (`_GOLDEN_STEMS` list) as one
of the 19 tomd golden fixtures, but it is NOT in the whisker corpus (no
`p0533r9.facts.jsonl` or `P0533R9.expected.md` in `corpus/`). It is annotated
as a known gate failure in `_EXPECTED_GATE_FAILURES`:
```python
_EXPECTED_GATE_FAILURES = {
    "p0533r9": {"no_toc_leak"},
    ...
}
```

### 3.6 No holdout data in test parametrization

The comprehension corpus test (`test_comprehension_corpus.py`) discovers papers
dynamically from the corpus directory. The score pinning test
(`test_score_pinning.py`) uses a hardcoded list of tomd golden fixture stems.
Neither test parametrizes against holdout data. The holdout manifest (mentioned
in CLAUDE.md as "48 source-page-verified anchors across 3 non-replay papers and
7 strata") is a documentation-level construct used for the LLM advisory lane's
evaluation, not wired into any pytest parametrization.

### 3.7 Provenance discipline

The corpus README documents the provenance chain:
> Honest status (2026-07-09): all `verified` facts to date were authored and
> source-verified by the agent, at the user's direction; no fact has been
> independently blessed by a human yet.

Facts ship as `checked: draft` and are promoted to `checked: verified` only
after source verification. The code enforces this:
```python
CHECKED_VERIFIED = "verified"
# ...
checked = rec.get("checked") == CHECKED_VERIFIED
```
(facts.py line 85, 543)

Only verified facts gate (facts.py `FactReport.passed`, line 148):
```python
def _enforced(self) -> list[FactCheck]:
    return [c for c in self.checks if c.verified]
```

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | 5 corpus papers with committed snapshots and facts files | PASS | HIGH |
| F2 | 37 verified facts across 5 papers, all passing in CI | PASS | HIGH |
| F3 | 3 canaries cover table, code, and math exploit classes | PASS | HIGH |
| F4 | Dev-replay (9 PRs) is separate from the corpus (5 papers) | PASS | HIGH |
| F5 | p0533r9 is quarantined: not in corpus, annotated as expected gate failure | PASS | HIGH |
| F6 | No holdout data in test parametrization | PASS | HIGH |
| F7 | Provenance chain is honest: agent-authored and source-verified, human blessing pending | INFO | HIGH |
| F8 | **Gap: No hash-based integrity check on corpus files.** The corpus files are tracked in git (implicit integrity via git hashes) but there is no explicit SHA-256 manifest locking each file's content. A corrupted snapshot would be caught by the comprehension test failing, not by a hash check. | LOW | HIGH |
| F9 | **Gap: Validation files exist only for P4182R0 and P4185R0.** The remaining 3 papers (P4234R0, N5040, P0876R23) have no `.validation.md` documenting the one-time LLM readback. | LOW | MEDIUM |

## 5. False-Pass Hypothesis and Falsification

**Hypothesis:** The comprehension corpus gate could pass vacuously if all
facts files contained only `checked: draft` facts.

**Falsification:** `test_verified_facts_hold_against_snapshot` (line 75-76)
explicitly asserts:
```python
verified = [c for c in report.checks if c.verified]
assert verified, f"{pid}: facts file has no checked:verified fact"
```

A paper with no verified facts fails the test. Additionally,
`test_corpus_has_at_least_one_comprehension_paper` (line 58) prevents a
vacuous suite from zero corpus pairs.

## 6. Gate/Dimension Mapping

| Gate | Dimension | Status |
|------|-----------|--------|
| D5: Corpus integrity | Provenance, isolation | PASS |
| D4: Scoring accuracy | Canary sensitivity | PASS |

## 7. Limitations

- The corpus is small (5 papers, 37 facts). Structural diversity relies on
  intentional stratum coverage (tables, math, code, xref, image_ref) rather
  than statistical sampling.
- Human blessing of agent-authored facts is pending (documented in corpus
  README). This is an honest status declaration, not a defect.
- The holdout manifest is a documentation artifact, not a machine-readable
  locked file. Its isolation is enforced by convention (CLAUDE.md rules)
  rather than by code.

## 8. Conclusion

The corpus has clean provenance: 5 papers with committed artifacts, 37 verified
facts, 3 canary tests covering distinct exploit classes, separation from the
dev-replay set, and p0533r9 properly quarantined. The hermetic CI gate prevents
vacuous green from both sides (no verified facts, and no corpus pairs). The
main gap is the absence of explicit hash-based integrity locking and incomplete
validation documentation for wave-2 papers.
