# C22 Readback

**Role**: Audit the readback comprehension lane, including its architecture and, newly this run, a live negative control that tests whether it can detect degradation at all.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771
**Gates**: G6 (Baseline canary, inverted), D5 (Anti-gaming / Goodhart)

## 1. Scope

Auditv2 verified the readback utility's architecture entirely offline:
answer-blind question generation, the grounded-quote anti-sycophancy gate,
the `--corrupt` methodology, standalone service resolution, and the D1
exemption for raw `httpx`. This run adds the evidence Auditv2's own
Limitations flagged as missing: a live `--corrupt` run against the real
pod, on the real corpus, producing an actual clean-vs-corrupt delta this
file can grade honestly rather than describe as a well-designed
methodology in the abstract.

## 2. Commands and Exits

```
$env:PYTHONIOENCODING="utf-8"
uv run --package whisker -- whisker-readback --corpus packages\whisker\corpus --workspace <data> --out <tmp>\clean -v      -> exit 0
uv run --package whisker -- whisker-readback --corpus packages\whisker\corpus --workspace <data> --out <tmp>\corrupt --corrupt -v -> exit 0
```

(`raw/w6-readback-scan.md`, Experiment 1, Commands section.) 5 of 6 corpus
papers ran (`EXAMPLE` skipped, no converted markdown). Data-dir file count
was 772 before and after (unchanged; read-only workspace access).

## 3. Current Evidence

### 3.1 Architecture, unchanged from Auditv2

`_generate_question()` (`readback.py:121-194`) generates per-fact-type
questions designed not to leak the expected answer lexeme, with an
explicit documented fix for the table fact type ("the pre-fix phrasing
leaked 'right: N5031, heading: Meeting' into the question",
`readback.py:155-159` per Auditv2's citation, not re-verified at that
exact line this run). `_grounded_quote()` (`readback.py:197-219` per
Auditv2) requires a fuzzy-matched verbatim quote for `present`/`code`/
`xref` facts; a bare "yes" without a quote fails. `absent`-fact passes are
marked `weak=True` (no quote possible for a negative claim). Table facts
use word-boundary cell matching (`_cell_value_in_answer`) specifically to
avoid "8" matching inside "18." The D1 exemption (raw `httpx`, not
`pipeline.run_agent`) is documented in the module docstring
(`readback.py:21-23` per Auditv2) on the grounds that read-back is
zero-shot Q&A with no pipeline steps or structured output, temperature
pinned to 0.0. None of this is contradicted by this run's live evidence;
it is the architecture the live numbers in 3.2-3.4 were produced by.

### 3.2 The corruption function's actual reach (`readback.py:371-387`)

```371:387:packages/whisker/src/whisker/tapetum_llm/readback.py
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

Three transforms, applied unconditionally to every line: reverse pipe-table
cells on any line containing `|`, rewrite `>=` to `<=`, increment `^n`
exponents. A paper with no pipe tables and no `>=`/`^n` math surface is
corrupted not at all beyond the prepended banner (3.3). This is the entire
corruption surface; no other transform exists in this function.

### 3.3 The corruption banner tells the model, in English, to distrust the document

```74:77:packages/whisker/src/whisker/tapetum_llm/readback.py
_CORRUPT_PREFIX = (
    "--- CORRUPTION BLOCK: all tables, formulas, and references below have "
    "been scrambled for adversarial testing. Do not trust any data. ---\n\n"
)
```

Prepended to the markdown whenever `--corrupt` is active
(`raw/w6-readback-scan.md`, "Pass/fail and corruption logic"). This means
the comparison is not "blind model reads clean text" vs "blind model reads
scrambled text"; it is "model reads clean text with no warning" vs "model
reads mostly-unscrambled text WITH an explicit warning that it has been
scrambled." Any comprehension drop under `--corrupt` is confounded between
these two effects and this run's evidence cannot separate them, because no
scenario was run with the banner present but the transform absent.

### 3.4 The live numbers (`raw/w6-readback-scan.md`, Experiment 1)

| PID | Clean score | Clean pass? | Corrupt score | Corrupt pass? |
|---|---|---|---|---|
| N5040 | 6/6 | yes | 4/6 | no |
| P0876R23 | 6/8 | no | 6/8 | no |
| P4182R0 | 8/8 | yes | 8/8 | yes |
| P4185R0 | 8/9 | no | 8/9 | no |
| P4234R0 | 6/6 | yes | 6/6 | yes |

Fact-level: clean 34/37 (91.9%), corrupt 32/37 (86.5%), a 5.4-point drop.
Paper-level: clean 3/5 papers pass every fact, corrupt 2/5. Two papers
(P4182R0, P4234R0) pass every single fact identically clean and corrupt.
The only two corrupt-only new failures are both `table-pipe-*` facts on
N5040, the one paper in this run's sample with pipe tables that the
transform actually touches. P0876R23 and P4185R0 already fail some facts
CLEAN (6/8 and 8/9), unrelated to corruption; P4185R0's one clean failure
(`table-anchored-true-zero`) recurs identically under `--corrupt`, i.e.
this is a pre-existing comprehension gap the corruption run neither
created nor fixed.

### 3.5 The CLI has no exit-code gate on comprehension

```205:219:packages/whisker/src/whisker/tapetum_llm/readback_cli.py
    if total_papers == 0:
        logger.error("no papers with verified facts found")
        return 1

    print(f"\n{'=' * 60}")
    print(
        f"READBACK SUMMARY: {total_papers} paper(s), "
        f"{total_pass} pass, {total_fail} fail, {total_error} error"
    )
    ...
    return 0
```

`main()` returns `0` whenever at least one paper ran, regardless of
`total_fail`/`total_error`. Both live runs in this file (clean, corrupt)
exited 0 (Section 2), including the corrupt run whose fact-level pass rate
was 86.5%. There is no threshold flag, no `--gate` equivalent, no non-zero
exit on any comprehension failure count. `whisker-readback`'s only visible
signal of comprehension health is a printed summary line a human must
read; it cannot be wired into a CI gate on its exit code alone.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | Question generation, anti-sycophancy grounding, and the D1 exemption remain code-sound and unchanged from Auditv2 | Informational | HIGH |
| F2 | The live clean-vs-corrupt fact-level delta is small (34/37 to 32/37, 5.4 points) and 2 of 5 papers show zero degradation under corruption | HIGH | HIGH |
| F3 | The corruption function's reach is limited to three surfaces (pipe-table cells, `>=`, `^n` exponents); a paper lacking all three is, by construction, essentially uncorrupted regardless of what the banner claims | HIGH | HIGH |
| F4 | The corruption banner explicitly tells the model the data is scrambled, confounding any measured comprehension drop with a prompt-level distrust cue rather than isolating the effect of the scrambling itself | MEDIUM | HIGH |
| F5 | The CLI exits 0 regardless of fail/error counts; comprehension failure produces no machine-readable signal | HIGH | HIGH |
| F6 | Two of five live papers (P0876R23, P4185R0) already fail some facts in the CLEAN run, independent of corruption; the negative control's baseline is not a clean 100% floor to begin with | MEDIUM | HIGH |

## 5. False-Pass Hypothesis

**Could the 91.9%/86.5% numbers be read as "the negative control worked,
comprehension degrades measurably under corruption"?** This is the
question this file exists to answer honestly, and the answer is no, not
as currently constructed. A healthy negative control should show a large,
unambiguous drop when the input is adversarially corrupted. A 5.4-point
drop, with 2 of 5 papers completely unaffected and the drop concentrated
entirely on the one paper type the transform actually reaches (pipe
tables), is equally consistent with "the corruption function barely
touches most papers" as with "the model is robustly recovering facts
despite corruption." Section 3.2's mechanical read of `_corrupt_markdown`
is the reason, verified against the actual code, not inferred from the
numbers alone: the transform has exactly three narrow surfaces, and a
table-free, math-free paper (three of five in this sample: P0876R23,
P4182R0, P4234R0 by inspection of the transform's applicability, though
this file did not independently confirm each paper's markdown lacks all
three surfaces beyond the pass-rate evidence) passes through effectively
unchanged.

**Could the drop be attributed to the corruption transform when it might
be the banner instead?** Not separable with this evidence. F4 stands:
the two confounds (mechanical scrambling, explicit distrust cue) were
never run independently of each other. This audit does not claim the
banner CAUSED the drop; it claims the experiment as designed cannot rule
that out, and a reader citing this run's numbers as proof the model is
"reacting to corruption" rather than "reacting to being told to distrust
the document" would be overclaiming.

**Honest verdict on whether this lane can currently detect degradation:**
partially, and narrowly. It clearly detects degradation on the one
corruption surface it actually mutates for a paper that has that surface
(N5040's pipe-table facts flipped from pass to fail). It demonstrably
fails to detect anything for papers, or fact types, outside that narrow
surface (P4182R0 and P4234R0 pass identically either way; no math/order/
xref/image_ref fact anywhere in this sample flipped under `--corrupt`).
Combined with the confound in F4 and the absent exit-code gate (F5), the
lane in its CURRENT form is a diagnostic aid for a human willing to read
the printed summary and inspect which paper types were actually mutated,
not a validated, general-purpose degradation detector, and it cannot be
trusted as either on its own to certify that the comprehension lane
"works" without also reading this file's caveats.

## 6. Gate/Dimension Mapping (PROPOSED)

| Gate | Dimension | Proposed status |
|------|-----------|------------------|
| D5 Anti-gaming / Goodhart | Question generation, anti-sycophancy grounding, D1 exemption | PROPOSED PASS (code-verified, unchanged from Auditv2) |
| G6 Baseline canary, inverted | `whisker-readback --corrupt` as a negative control | PROPOSED WEAK: narrow corruption surface (F3), banner confound (F4), no exit-code gate (F5) |
| G6 Baseline canary, inverted | Live degradation detection on the mutated surface specifically | PROPOSED PASS, narrow (N5040 pipe-table facts flipped correctly) |

## 7. Limitations

- This file did not independently verify, for each of the 5 papers, exactly
  which of the three corruption surfaces (pipe table, `>=`, `^n`) its
  markdown contains; the inference that 3 of 5 papers lack all three is
  drawn from the pass-rate evidence (identical clean/corrupt scores for
  P0876R23/P4182R0/P4234R0's unaffected facts) rather than from a direct
  content scan.
- No controlled experiment isolating the banner's effect from the actual
  scrambling (banner present, scrambling absent) was run; F4's confound is
  therefore a code-level and logical argument, not a directly measured
  isolated effect.
- This run's sample is 5 papers, 37 total facts; it is not a
  corpus-wide measurement, and paper-specific idiosyncrasies (P0876R23 and
  P4185R0's pre-existing clean failures) are not explained further here.
- The suite is RED (E1); `test_readback.py`'s specific pass/fail status
  among the 1784 passing / 3 failing was not independently re-checked this
  run, and per the batch's hard rule this file does not lean on its
  passing status as evidence the live behavior above is correct; the live
  numbers in 3.4-3.5 stand on their own runtime evidence.

## 8. Conclusion

The readback lane's architecture is sound and unchanged from Auditv2:
answer-blind questions, a grounded-quote anti-sycophancy gate, and a
documented, narrow D1 exemption. What Auditv2 could not test, because its
runtime evidence was blocked, is whether the tool this project built
specifically to validate comprehension actually demonstrates a
comprehension drop under adversarial corruption. It does, but only on the
narrow surface its corruption function actually reaches, confounded by an
explicit distrust banner, with no exit-code signal a CI system could act
on. The plain statement Auditv2 could not have written: the readback
negative control does not currently have broad teeth. It demonstrates a
small, corruption-surface-dependent comprehension drop on a control that
cannot fail a CI run by its own exit code, and it says nothing measurable
about comprehension of prose, cross-references, ordering, or math facts
under corruption, because the transform never touches those surfaces.

## 9. Delta vs Auditv2

Auditv2's C22 verified the same architecture (3.1) entirely by code
inspection against a runtime-BLOCKED ledger and concluded "All code-level
checks pass; live validation requires a pod endpoint," an explicitly
deferred verdict rather than a claim about live degradation detection.
This run supplies exactly that missing live evidence (Experiment 1,
`raw/w6-readback-scan.md`) and the result is not a simple confirmation: it
surfaces that the negative control, once actually run, has a narrow,
mechanically explainable corruption surface (F3) and a confounding banner
(F4) that Auditv2's code-only review had no occasion to examine, because
Auditv2 never had `_corrupt_markdown`'s live output to compare against a
clean baseline. Auditv2's F1-F3, F5-F6 (question design, grounded-quote
gate, D1 exemption, word-boundary matching) are reaffirmed unchanged. This
file replaces Auditv2's deferred "requires a pod endpoint" framing with a
specific, evidenced, and more qualified verdict on the one question that
endpoint access was meant to resolve.
