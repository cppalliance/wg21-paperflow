# C29 External Delta

**Role**: Compare whisker's actual, in-repo measurement design against
markitdown, marker, docling, and nougat on the axes that matter for WG21
papers, grounded strictly in what is present in this repository. No
competitor benchmark numbers are invented; where no in-repo citation exists,
the comparison is stated qualitatively and marked uncited.
**Audited state**: whisker 0.5.0, working tree, manifest
b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771
**Gates**: none of whisker's internal gates are audited directly here; this
is a comparative-positioning report. PROPOSED scope only.

## 1. Scope

Four named tools (markitdown, marker, docling, nougat) against whisker's
design, restricted to what this repository's own code, docs, and prior
research state about each. Two of the four (markitdown, marker) are not
hypothetical comparisons: markitdown is a live, wired dependency
(`ref_engine` field in every score record) and marker has a working adapter
in `survey/adapters/marker.py`. Docling and nougat are referenced in
documentation and design rationale but are not wired dependencies.

## 2. Commands and Exits

```
uv run --package whisker python -c "import whisker; ..."   (E5, exit 0, confirms markitdown import chain)
```
No live competitor run was executed in this batch; comparison is drawn from
existing repo artifacts (`raw/w3-deps-packaging.md`, `raw/w4-doctrine-quotes.md`,
`packages/whisker/src/whisker/CLAUDE.md`, `_output/chatlight-marker-tool-evaluation.md`).

## 3. Current Evidence

### 3.1 markitdown: the only wired, in-production comparison

`markitdown[pdf]>=0.1.6` is a core dependency
(`raw/w3-deps-packaging.md` Task 1, `pyproject.toml` dependencies list).
Every deterministic score record carries a `ref_engine` field (E9's 30-field
list includes `ref_engine`), defaulting to `markitdown`
(`raw/w2-cli-surface.md` SS3.2, `--reference {markitdown}` "default:
markitdown"). whisker's own docs are explicit about the comparison's limits:
`CLAUDE.md:144-147` states markitdown is "an independent but WEAK converter,
advisory only," and the verdict logic (`score.py` SS4 in
`raw/w4-doctrine-quotes.md`) never hard-fails on cross-converter disagreement
("agreement != correctness"; `ref_teds`/`ref_mhs` are "reported per-axis but
never flag at all"). This is the one comparison in this list backed by
live, structured evidence in every score record, not documentation alone.

### 3.2 marker: named in the repo as evaluated-and-rejected, then re-admitted as a monitored competitor

`_output/chatlight-marker-tool-evaluation.md` (lines 15-22, 52-60) documents
that marker was formally evaluated as a candidate **replacement** for tomd
alongside Docling, MinerU, olmOCR, and others, and rejected: "keiner davon
deckt tomds WG21-Probleme ab (ins/del wording, verbatim C++, Font/Color-Spans,
Dual-Path-Confidence)"; specifically "bei ins/del wording: 0," and marker is
characterized as "all-or-nothing," not a hint-capable layout component the
way Surya/Docling layout signals are. The same source records marker's
license as GPL-3.0 (its summary table, row 1: "Marker (Datalab/Surya, ~1B
params, GPL-3.0)"). This licensing fact is directly load-bearing for E7's
finding of "no GPL-family package in the core dependency set": marker cannot
be a core dependency under whisker's own license posture, which is
consistent with where it actually lives, `survey/adapters/marker.py`
(`raw/w3-deps-packaging.md` Task 3, wheel listing), a monitored, isolated,
subprocess-based competitor inside the `survey` subsystem, not an import.

Notably, `survey/` and its marker adapter are **not mentioned anywhere** in
`packages/whisker/src/whisker/CLAUDE.md`'s architecture map or module layout
(the file's own table of contents, `CLAUDE.md:1-33`, lists constants, the
three lanes, the corpus, the opt-in LLM layer, and greppable conventions;
`survey` appears nowhere). The marker comparison exists as working, tested
code (93 test functions across 8 `test_survey_*.py` files, `raw/w1-test-suite.md`
section 5) but is undocumented in the file every other module-level
description lives in.

### 3.3 docling: cited for design rationale, not wired

Docling appears in whisker's own doctrine as a comparator for methodology,
not as code. `CLAUDE.md:377-382` (verdict model section) cites Docling's
`set(word_tokenize)` precision/recall approach as one of three external
precedents (with Nougat and OmniDocBench) for keeping reading order off the
content gate. `CLAUDE.md:411-413` cites "OpenDataLoader nulls such axes" and
Docling's `verify_table_v2` as the source of the "null-eligibility" pattern
for ineligible axes. No docling package appears in `pyproject.toml`
dependencies (core or extra, `raw/w3-deps-packaging.md` Task 1). The
comparison here is architectural precedent, correctly cited to specific
CLAUDE.md line ranges, not a live benchmark number.

### 3.4 nougat: cited once, as the sole prior-art comprehension tester

`packages/whisker/src/whisker/CLAUDE.md:135` (also echoed in
`raw/w4-doctrine-quotes.md` section 3, `CLAUDE.md:135`): "across the 28
surveyed converters, none has an automatic '100% correct' oracle, and only
`olmocr` tests comprehension at all." This line names **olmocr**, not
nougat, as the comprehension precedent; nougat's only in-repo mention found
in the doctrine evidence is the set-F1 citation
(`CLAUDE.md:381`, "Nougat reports set-F1"), again a methodology precedent for
content-vs-order separation, not a comprehension claim. **This report
corrects the premise of comparing whisker's Lane 3 against nougat on
comprehension specifically: the repo's own citation for that axis is olmocr,
not nougat.** Any comprehension comparison against nougat specifically would
be uncited; the correctly-cited comparison is against olmocr.

### 3.5 The axis that actually matters for WG21 papers: none of the four have it, by whisker's own account

`CLAUDE.md:130-137`: "across the 28 surveyed converters, none has an
automatic 'this file is 100% correct' oracle, and only `olmocr` tests
comprehension at all." whisker's Lane 3 (`facts.py`) is presented as filling
that gap for WG21-specific content (verbatim C++ identifiers, table
row/column semantics, math relations) via deterministic, source-verified
assertions, not an LLM oracle. No qualitative claim here is contradicted by
anything in this audit's own evidence: `raw/w4-doctrine-quotes.md` confirms
no verdict state or fleet aggregate anywhere in whisker is named "perfect,"
and the four canaries (E17, E18) show the same deterministic surface that
implements this claim has real, documented blind spots (reordering, table
swap, code mangling) that a bag-of-tokens measure cannot see, a limitation
this report states plainly rather than treating as disqualifying: none of
markitdown, marker, docling, or nougat is shown anywhere in this repo to
catch those defect classes either.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---|---|---|
| F1 | markitdown is the only live, structurally-evidenced comparison (`ref_engine`, `ref_*` fields); comparison is explicitly advisory-only by whisker's own design | Informational | HIGH |
| F2 | marker was evaluated as a tomd replacement and rejected on WG21-specific axes (ins/del wording scored 0); its GPL-3.0 license is the documented reason it can only be a monitored, isolated competitor | Informational | HIGH |
| F3 | The `survey/` marker-monitoring subsystem is working, tested code entirely absent from `CLAUDE.md`'s architecture map | Medium | HIGH |
| F4 | Docling and nougat comparisons in whisker's own docs are methodology citations, not live benchmarks; no docling/nougat dependency exists in this repo | Informational | HIGH |
| F5 | The repo's own cited comprehension precedent is olmocr, not nougat; a nougat-comprehension comparison would be uncited | Low | HIGH |
| F6 | No evidence in this repo shows any of the four external tools catching the specific defect classes (reordering, table-cell swap, code-span mangling) that E17/E18 show whisker's own hard gate also misses | Informational | HIGH |

## 5. False-Pass Hypothesis

**Could whisker's Lane 3 (comprehension) claim be a false differentiator, if
one of the four tools secretly also does source-verified fact assertion?**
Nothing in this repo's research corpus supports that; the 28-converter survey
underlying `CLAUDE.md:135` is cited as the source for "only olmocr tests
comprehension at all," and this audit has no independent access to re-verify
that survey's completeness. This report accepts the claim as documented but
flags, per the hard rule against inventing competitor numbers, that it is
not independently re-verified here.

**Could the marker rejection (F2) be stale, given it predates this audit by
an unspecified interval?** The evaluation is dated by its content to
predate the `survey/` subsystem's existence as a monitoring tool (the
Slack-thread-style Q&A in `_output/chatlight-marker-tool-evaluation.md`
reads as historical record, not a live re-test). Whether marker's specific
ins/del-wording score would differ on a current marker release is not
established here; that question is exactly what `survey/adapters/marker.py`
exists to answer on an ongoing basis, per `CLAUDE.md`'s absent-but-implied
purpose for the subsystem, but no current survey run output was found in
this audit's evidence set.

## 6. Gate/Dimension Mapping (PROPOSED)

- **Comparative positioning: PROPOSED PASS.** Every named comparison in this
  report traces to an in-repo citation; no competitor benchmark number was
  invented.
- **Documentation completeness for the `survey/` subsystem (new, no
  Auditv2 predecessor): PROPOSED FAIL-UNPROVEN.** A working, tested
  competitor-monitoring capability is undocumented in the file that
  documents everything else.

## 7. Limitations

- No live `whisker survey run marker` output exists in this audit's evidence
  set; the marker comparison is grounded entirely in the historical
  evaluation document and the adapter's presence, not a fresh run.
- Docling and nougat's current (2026) capabilities were not independently
  researched; this report states only what this repository's own text
  claims about them, per the hard rule against inventing figures.
- Whether the 28-converter survey behind the "only olmocr tests
  comprehension" claim is current or itself dated was not re-verified.

## 8. Conclusion

Grounded strictly in-repo, whisker's actual competitive position is narrower
and more specific than a general "we compare well" claim would suggest: it
has one live, structurally-evidenced comparison (markitdown, explicitly
advisory), one historically-evaluated-and-rejected full-replacement
candidate that is now monitored rather than integrated (marker, blocked from
core specifically by its GPL-3.0 license), and two comparisons that exist
only as design-methodology citations with no wired code (docling, nougat).
The repo's own comprehension-testing precedent citation is olmocr, not
nougat, a correction this report makes rather than repeating the premise
uncritically. The one differentiator whisker's docs claim, source-verified
fact recovery as opposed to fidelity resemblance, is not shown anywhere in
this repo to be matched by any of the four named tools, but this report
cannot independently confirm that absence either; it is stated as documented,
not as independently benchmarked.

## 9. Delta vs Auditv2

Auditv2's `code-c29-external-delta.md` explicitly declined to perform a real
comparison, reasoning that its one-day delta from Auditv1's full 28-tool
survey made a fresh survey pointless, and deferred entirely to that prior
survey's findings ("No external delta invalidates any whisker design decision
or audit finding"). This report does not defer; per this audit's explicit
instruction, it grounds a direct comparison against four named tools in
what is actually present in the current repository, rather than citing a
prior survey by reference. In doing so it surfaces something Auditv2's
delta-only framing could never have found: the `survey/` marker-monitoring
subsystem, which did not factor into either Auditv1's survey or Auditv2's
report at all, is real, tested, working code, and it is simultaneously
undocumented in the project's own architecture map. This is a genuinely new
observation, not a re-statement of Auditv1's tool-by-tool survey. It also
corrects a premise (nougat vs. olmocr as the comprehension citation) that
neither prior audit had reason to check, since neither attempted a
named-tool-by-named-tool comparison against the specific doctrine claims.
