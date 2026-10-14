# C08 Canary and Gate Teeth

**Role**: Verify that inverted canaries and negative controls actually prove the deterministic and advisory gates have teeth, not just that they run.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771
**Gates**: G6 (Anti-gaming), D5 (Quality-stability)

## 1. Scope

Two independent teeth tests this run, deliberately kept separate because they
probe different lanes: a gross-loss canary against both the deterministic and
advisory lanes (ledger E17-E19), and the `whisker-readback --corrupt`
adversarial negative control against Lane 3 comprehension
(`raw/w6-readback-scan.md`).

## 2. Commands and Exits

Canary driver `rt4_canaries.py`, four mutations of the same ideal
(`25157` chars, 9 H2 sections), against the live pod (E17-E19). Readback:

```
uv run --package whisker -- whisker-readback --corpus packages\whisker\corpus --workspace <data> --out <tmp>\clean -v
uv run --package whisker -- whisker-readback --corpus packages\whisker\corpus --workspace <data> --out <tmp>\corrupt --corrupt -v
```

Both exit 0 (`raw/w6-readback-scan.md`, Commands section).

## 3. Current Evidence

### 3.1 Gross-loss canary: teeth confirmed (E17, C1)

C1 deleted `## 3. Platforms` (11757 chars, 46.7% of the document). Both
lanes failed it: deterministic `unigram_coverage` dropped to 0.5021 (hard
fail), and the LLM independently returned `fail` at confidence 1.0, naming
the omission exactly: *"The entire Section 3 (Platforms) and its subsections
3.1-3.8 are absent from the markdown. The markdown jumps directly from
Section 2 to Section 4."* This is unambiguous: at 46.7% deletion, nothing in
the pipeline waves it through.

### 3.2 Token-preserving canaries: the split result (E17-E19)

The other three canaries hold total token content constant and mutate
structure or symbols only:

| Canary | Mutation | det verdict | LLM | fused | caught by |
|---|---|---|---|---|---|
| C2 | reverse section order | pass | review (0.95) | **pass** | LLM only, then discarded |
| C3 | swap two table cells | pass | review (0.85) | review | LLM only |
| C4 | corrupt 14 code spans (`<memory_resource<`) | pass | review (0.98) | review | **neither** |

C3 is a genuine hybrid-architecture proof: the model found a defect no
lexical metric can see (*"the first data row is misaligned, with 'Yes'
appearing in the 'Category' column"*). C4 is the harder finding: fourteen
mangled header names are numerically invisible to both lanes.
`text_nid`/`content_recall`/`unigram_coverage` are byte-identical to the
control, and the model's reasoning string is byte-identical to the control's
too (E18). The normalizer (`clean_string`, alnum-only) strips the very
characters (`<`, `>`) that were corrupted, so this is structural, not a
tuning gap.

C2 is the sharpest false-pass this run surfaces: the model correctly detected
severe reordering (*"sections 4.2-4.7 appear before 4.1 ... This structural
corruption constitutes substantial reordering, failing the conversion"*) and
returned `suggested_verdict: review`, but the fused `combined_verdict` came
out `pass` (E19). The mechanism, traced in `fusion.py`, is that the
metadata/outline check independently voted `pass` (*"but all source sections
are present. Heading levels are consistent"*), the source-aware cap never
fires, and execution falls through to `fusion.py:538`
(`rule = FUSION_RULE_AGREE if det == llm else FUSION_RULE_WHISKER_ONLY`),
which takes the deterministic `pass` and drops the primary judge's `review`
entirely. This does not touch `score.py` or the exit code (`advisory` stays
true), but it is a defect in what the merged human-facing report says.

Ledger E20 measures this instability is not a one-off: three forced reruns
of the same three papers (identical model, identical prompts) show the
control produce `pass` in 1 of 4 total observations and C2 produce `pass` in
2 of 4, driven entirely by the metadata/outline check flipping between runs.

### 3.3 The readback negative control is weak (`raw/w6-readback-scan.md`)

Clean pass: 34/37 facts (91.9%), 3/5 papers pass every fact. Corrupt pass:
32/37 facts (86.5%), 2/5 papers pass every fact. The delta is two additional
fact failures out of 37, and two papers (P4182R0 8/8, P4234R0 6/6) pass every
single fact identically under corruption (`raw/w6-readback-scan.md`
Comparison table).

The corruption function, `_corrupt_markdown` (`readback.py:371-387`):

```python
def _corrupt_markdown(md: str) -> str:
    lines = md.split("\n")
    result = []
    for line in lines:
        if "|" in line and not line.strip().startswith("```"):
            cells = line.split("|")
            cells = list(reversed(cells))
            line = "|".join(cells)
        line = re.sub(r">=", "<=", line)
        line = re.sub(r"\^(\d+)", lambda m: f"^{int(m.group(1)) + 1}", line)
        result.append(line)
    return "\n".join(result)
```

Three transforms only: reverse pipe-table cells on any line containing `|`,
rewrite `>=` to `<=`, increment `^n` exponents. A paper with no pipe tables
and no `>=`/`^n` math is corrupted not at all beyond the prepended banner. Of
the two corrupt-only new failures (`raw/w6-readback-scan.md`), both are
`table-pipe-*` facts on N5040, which has pipe tables; P4182R0 and P4234R0
have none of the three corruptible surfaces and score identically clean vs.
corrupt.

The corruption also prepends a banner that tells the model, in plain
English, that the data has been tampered with (`readback.py:74-77`):

```python
_CORRUPT_PREFIX = (
    "--- CORRUPTION BLOCK: all tables, formulas, and references below have "
    "been scrambled for adversarial testing. Do not trust any data. ---\n\n"
)
```

This means any comprehension drop under `--corrupt` is confounded: the model
is not discovering scrambled data blind, it is told in advance to distrust
the document. A model that degraded ONLY because of the banner (not the
actual scrambling) would look identical in this data to one reacting to the
scrambling itself.

Finally, `readback_cli.py:205-219`: the CLI's `main()` returns `0` whenever
at least one paper ran, regardless of `total_fail`/`total_error`. There is no
threshold or exit-code signal on comprehension failure; the only visible
consequence is a printed summary line. `whisker-readback` cannot be wired
into a CI gate on its exit code alone; a human must read the printed pass
count.

### 3.4 A token-preserving corruption neither lane caught (E18)

Restated from 3.2 for the gate-teeth question directly: C4 is a corruption
that is real, structural, and human-obvious (`<memory_resource<` is not
valid C++ syntax and would be caught instantly by a human reading the
document), yet it produces zero signal on any deterministic axis and an
LLM reasoning string byte-identical to the clean control. Neither lane has
teeth against this specific corruption class (corrupted content INSIDE a
code span whose bracket characters are stripped by the normalizer before
comparison).

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | Gross content loss (46.7%) is caught by both lanes independently, with the LLM naming the omitted section exactly | Informational (confirms teeth) | HIGH |
| F2 | A live cell-swap canary (C3) is caught by the LLM lane only, proving the hybrid architecture's value | Informational | HIGH |
| F3 | A live code-span corruption canary (C4) is caught by neither lane; every deterministic axis and the LLM's own reasoning string are byte-identical to the clean control | HIGH | HIGH |
| F4 | A live reordering canary (C2) is correctly flagged by the LLM (`review`) but the fusion rule drops that signal and reports `pass`, driven by the metadata/outline check's independent `pass` vote | MEDIUM | HIGH |
| F5 | Advisory verdict instability (E20: control 1/4 pass, C2 2/4 pass across reruns) means a single clean canary run cannot be trusted as a stable measurement without repeat observations | MEDIUM | HIGH |
| F6 | The `--corrupt` negative control produces only 2 additional fact failures across 5 papers (34/37 to 32/37) because its corruption function only touches pipe-table cells, `>=`/`<=`, and `^n` exponents | HIGH | HIGH |
| F7 | The corruption banner prepended to the document explicitly tells the model the data is scrambled, confounding any comprehension-drop measurement with a prompt-level warning effect | MEDIUM | HIGH |
| F8 | `whisker-readback` exits 0 regardless of comprehension pass/fail counts; it cannot gate CI on its own exit code | LOW | HIGH |

## 5. False-Pass Hypothesis

**Could the gross-loss canary result (C1) be a false positive for "the gate
has teeth" in general?** Partially. C1 proves teeth against the single
crudest exploit class (delete an entire section). It says nothing about
subtler, token-preserving corruption, which is exactly what C2/C3/C4 probe.
Citing C1 alone as evidence the gate is robust would overstate the finding;
C4 in the same evidence set directly falsifies a general "the gate catches
corruption" claim.

**Could the readback 91.9%/86.5% numbers be read as "the negative control
worked"?** No, and this is the central risk this report exists to flag. A
healthy negative control should show a LARGE, unambiguous drop when the
input is adversarially corrupted; a 5.4 percentage-point drop, with 2 of 5
papers completely unaffected, is consistent with "the corruption function
barely touches most papers" rather than "the model is robustly recovering
facts despite corruption." The corruption function's narrow scope
(3.3) is the mechanical reason, verified against the actual code, not
inferred.

## 6. Gate/Dimension Mapping (PROPOSED)

| Gate | Dimension | Proposed status |
|------|-----------|------------------|
| G6 Anti-gaming | Gross content-loss detection | PROPOSED PASS (E17, both lanes, live) |
| G6 Anti-gaming | Token-preserving corruption detection | PROPOSED PARTIAL: LLM-only for cell-swap (C3), MISS for code-span corruption (C4) |
| D5 Quality-stability | Advisory lane run-to-run stability | PROPOSED FAIL-adjacent: measured 25-50% verdict flip rate on canary papers (E20), consistent with CLAUDE.md's own documented >= 25% claim |
| G6 Anti-gaming | `whisker-readback --corrupt` as a negative control | PROPOSED WEAK: mechanically narrow corruption function, confound via explicit banner, no exit-code gate |

## 7. Limitations

- The canary set (E17-E19) is four mutations of a single base document; it
  does not sample the corpus breadth the offline canaries in
  `test_comprehension_corpus.py` cover (scrambled table cell, mangled code
  snippet, flipped math relation, per Auditv2 C08 3.1, unaffected by this
  run's RED suite per ledger E1).
  This report does not re-verify those three offline canaries; ledger E1
  confirms none of the 3 failing tests are in that file.
- The readback corruption analysis is mechanical (reading `_corrupt_markdown`
  and the pass-rate table); it does not include a controlled experiment that
  isolates the banner's confounding effect from the actual scrambling (e.g.
  a run with the banner but no scrambling).
- Advisory instability (E20) is measured on 3 papers across 4 observations
  each; this is a small sample consistent with, but not a full replication
  of, CLAUDE.md's own >= 25% claim.

## 8. Conclusion

Teeth are real but narrow. The gate stops the crudest attack (delete
half the document) with both lanes agreeing and the LLM naming the exact
missing section. It also catches one class of subtle, token-preserving
corruption (table cell swap) via the LLM lane alone, which is the strongest
argument for the hybrid architecture existing at all. But the same evidence
set contains a token-preserving corruption (code-span bracket mangling) that
neither lane catches, a reordering canary the advisory lane correctly flags
and then silently drops via a fusion rule interaction, and measured
verdict instability on the very canary papers used to make the teeth claim.
Separately, the `whisker-readback --corrupt` control, the tool this project
built specifically to validate Lane 3 comprehension is more than
theater, is itself weak: its corruption function is narrow enough that 2 of
5 real papers are unaffected by it, it primes the model with an explicit
scrambling warning, and its CLI does not gate on its own findings.

**Plain statement:** the readback negative control does not have teeth in
its current form. It demonstrates a small, corruption-surface-dependent
comprehension drop, confounded by an explicit warning banner, on a control
that cannot fail a CI run by its own exit code.

## 9. Delta vs Auditv2

Auditv2's C08 was entirely offline: three corpus canaries in
`test_comprehension_corpus.py`, verified by running pytest, with the explicit
limitation "Real-LLM runtime is BLOCKED (E9); the `whisker-readback`
validation is not re-verified." Its gate verdict was an unqualified PASS.
This run supplies exactly the missing runtime evidence Auditv2 could not
obtain (live canaries against the real pod, and a live execution of
`whisker-readback --corrupt`), and the result complicates rather than
confirms the prior PASS: gross-loss teeth are reconfirmed, but the newly
possible live tests surface a live token-preserving miss (C4), a live
fusion-swallowed detection (C2), measured advisory instability (E20), and a
structurally weak negative control that Auditv2 could only take on faith.
