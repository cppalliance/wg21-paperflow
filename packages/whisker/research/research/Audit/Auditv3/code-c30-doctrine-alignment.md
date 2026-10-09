# C30 Doctrine Alignment

**Role**: Test whisker's stated doctrine, that the conversion target is
markdown a downstream LLM can read faithfully, not typographically perfect
markdown, against its actual measurement surface, and state plainly whether
the gate implements that doctrine or silently measures human-facing fidelity
instead.
**Audited state**: whisker 0.5.0, working tree, manifest
b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771
**Gates**: the deterministic hard gate itself (`gates.py` structural gates +
`UNIGRAM_COVERAGE_FAIL_EDGE`), `no_toc_leak`, `heading_monotone`, and the
verdict trichotomy in `score.py::_decide()`. PROPOSED only; this report
certifies no verdict.

## 1. Scope

Two questions in sequence. First, what does whisker's own documentary record
say the measurement target is: LLM-readability ("good enough for a
downstream reader to recover facts") or typographic/human fidelity
("looks like a human wrote it")? Second, does the live deterministic gate,
the surface that actually decides `pass`/`review`/`fail` and therefore the
only surface with teeth, measure the thing the doctrine claims, or something
else. The doctrine record is `raw/w4-doctrine-quotes.md`; the live test of
it is E17/E18 (four canaries) plus the `_decide()` logic itself.

## 2. Commands and Exits

```
rg -ni "perfect|byte-exact|human-grade|pixel" packages/whisker packages/tomd --glob "*.md" --glob "*.py"   (raw/w4 SS2)
rg -ni "llm.consum|llm.read|downstream|good.enough|comprehen|recover the paper|fact recovery" packages/whisker packages/tomd research --glob "*.md" --glob "*.py"   (raw/w4 SS3)
```
Canary driver: `rt4_canaries.py` (E17, E18), against `alliance-pod`, base
document 25157 chars / 9 H2 sections. No exit-code claim beyond what the
ledger already records (all four canary scorings are library-level scoring
calls, not CLI invocations; the deterministic `score.py::_decide()` logic
itself is not gated by a shell exit code at this granularity).

## 3. Current Evidence

### 3.1 The doctrine, in whisker's own words

`packages/whisker/src/whisker/CLAUDE.md:130-137` states the doctrine
directly: "Fidelity is not comprehension. A reflow can score high on every
Lane 2 axis and still scramble a table cell or drop a formula's exponent so
a downstream LLM reads 'row 3, column 2' wrong, with every fidelity metric
green. Only Lane 3 catches that." `CLAUDE.md:527-535` grounds this
empirically: the deterministic Lane 3 facts are "a deterministic PROXY for
what a downstream LLM must recover," validated once by a blind read-back
("hand a fresh LLM ONLY the converted markdown plus the fact questions...
compare to the verified facts"), explicitly rejecting a "regenerate similar
text" round-trip as "the WRONG test" because "resemblance measures fidelity,
not comprehension."

`packages/whisker/research/comprehension-poc-report.md:1,15-21` states the
same doctrine as the explicit reason Lane 3 exists at all: "Can an LLM that
consumes the converted markdown still READ it correctly... A faithful-looking
reflow can still scramble a table so 'row 3, column 2' reads wrong, and
every fidelity metric stays green. We wanted a test that gates on read ->
understood -> correct, not on resemblance to a golden file." No search for
"perfect," "byte-exact," "human-grade," or "pixel" across whisker or tomd
(`*.md`, `*.py`) turns up any verdict state, exit code, or fleet aggregate
named after typographic perfection (`raw/w4-doctrine-quotes.md` SS2, final
line: "No whisker verdict state, exit code, or fleet aggregate is named
'perfect'. No '% perfect' string found"). The doctrine, as documented, is
unambiguous and self-consistent: the target is LLM-recoverable content, not
human-typographic fidelity, and the project has been careful never to claim
the latter in its own vocabulary.

### 3.2 What actually gates: a single hard content signal, order-invariant by design

`score.py::_decide()` (`raw/w4-doctrine-quotes.md` SS4, verbatim lines
136-231) has exactly two ways to hard-fail: a structural gate failure
(`gates.py`), or `unigram_coverage < UNIGRAM_COVERAGE_FAIL_EDGE` (0.85).
`unigram_coverage` is, by the function's own docstring, "order-invariant
token-set recall," deliberately not the order-sensitive shingle `coverage`,
which is computed and reported but explicitly "never a verdict flag."
This is not an oversight; it is a documented design choice
(`CLAUDE.md:377-389`) citing Docling, Nougat, and OmniDocBench as precedent
for keeping reading order off the content gate.

### 3.3 The canary test: does the gate track the doctrine at the point that matters

E17 ran four mutations of the same 25157-character, 9-section document
through both the deterministic gate and the live LLM lane:

| Canary | Mutation class | Is this an LLM-comprehension defect? | det verdict | `unigram_coverage` | caught by |
|---|---|---|---|---|---|
| C1 | delete 46.7% of the document | Yes, unambiguously | fail | 0.5021 | both lanes |
| C2 | reverse section order (token-preserving) | Yes: destroys reading order, exactly the class LLM readers depend on | pass | 0.9542 (unchanged) | LLM only, then discarded by fusion (E19) |
| C3 | swap two table cells (token-preserving) | Yes: a "row 3, column 2" misread, the paper's own canonical example of what fidelity metrics miss | pass | 0.9542 (unchanged) | LLM only |
| C4 | corrupt 14 code-span identifiers (token-preserving) | Yes: a wrong C++ identifier is exactly the kind of fact a downstream LLM would consume and repeat as truth | pass | 0.9542 (unchanged) | **neither lane** (E18) |

C1 is the only mutation the deterministic gate detects, and it is the one
mutation that is also a straightforward token-deletion, precisely the class
`unigram_coverage` is built to catch. C2, C3, and C4 are all
token-preserving; `unigram_coverage` cannot distinguish "reordered,"
"swapped," or "corrupted-but-same-alphabet" from "unchanged," because it is,
by construction, a bag-of-tokens measure. This is not a bug in the
implementation; it is the literal, documented behavior of an order-invariant
recall statistic. The consequence is that the gate with teeth, the only
surface that produces a hard `fail`, is insensitive to exactly the three
defect classes (`CLAUDE.md:130-137`'s own two named examples, scrambled table
cell and dropped exponent, are C3's and C4's family) that the doctrine
section of the same file names as the reason Lane 3 must exist.

### 3.4 C4 is not a tuning gap, it is outside what the surface can represent

E18 traces why C4 (14 mangled code spans, `` `<memory_resource>` `` to
`` `<memory_resource<` ``) is invisible to **both** lanes, not just the
deterministic one: `text_nid` (0.8645), `content_recall` (0.9697), and
`unigram_coverage` (0.9542) are all numerically identical, to four decimal
places, between the control and C4. The normalizer chain
(`clean_string`, alnum-only, `CLAUDE.md:240-246`) strips the exact characters
(`<`, `>`) that were corrupted, before any comparison happens. This means
the deterministic surface cannot represent the defect at all, at any
threshold; it is not that 0.85 or 0.95 are miscalibrated for this class, it
is that the normalized text stream fed into every text-similarity axis has
already discarded the information needed to see it. The LLM lane's own
reasoning text is byte-identical between control and C4
("No content loss, corruption, or reordering found..."), meaning the model
did not see it either. Fourteen mangled header names, exactly the verbatim
C++ identifiers `CLAUDE.md`'s own invariant ("Text is the primary output...
LLM prompts must require verbatim data preservation," `packages/tomd/src/tomd/CLAUDE.md:113-117`)
treats as sacrosanct, pass through the entire measurement stack unflagged.

### 3.5 Contrast: the gates that DO have teeth are structural, not comprehension-targeted

`no_toc_leak` and `heading_monotone` are both hard gates (`gates.py`,
per `CLAUDE.md:261-268`, `869-882`). Neither targets an LLM-comprehension
failure mode directly. `no_toc_leak` catches a table of contents surviving
into the body, a defect a human skimming the rendered markdown would notice
immediately (a duplicated heading with a page number) but which does not, on
its own, prevent an LLM from recovering the paper's facts; a leaked TOC is
noise, not lost signal. `heading_monotone` catches a level-skip (H2 -> H4),
which `tapetum_llm.md:171` (`raw/w4-doctrine-quotes.md` SS5) explicitly
calls "cosmetic: severity minor, verdict review at most, never fail, since
a reader loses nothing," and which the project's own RESCUE mechanism
exists specifically to un-fail when it fires alone
(`tapetum_llm.md:183-185`: "that is a false-fail... The heading quirk alone
is never major"). Read plainly: the project's own advisory-lane system
prompt states, in writing, that the one deterministic hard gate outside the
content-coverage floor most often trips (64% of ref-free hard-fails,
`CLAUDE.md:875-878`) is a defect "a reader loses nothing" from. That is a
tidiness signal wearing a hard-fail's clothes, not a comprehension signal.
`no_toc_leak` is closer to genuinely structural (a leaked TOC could
plausibly confuse an LLM's section-boundary parsing) but its stated failure
modes in the known-gaps list (dot-leader TOCs, non-English headers,
false-positive on a legitimate ToC heading, `CLAUDE.md:869-874`) are about
detection completeness, not about which reader (human or LLM) the defect
harms.

### 3.6 The doctrine verdict

Read together, SS3.2 through SS3.5 support a specific, narrow conclusion,
not a blanket one. The deterministic hard gate does **not** measure
human-facing typographic fidelity; nothing in it rewards "looks like a human
wrote it" independent of content, and the project has been careful never to
claim that it does. But it also does not measure LLM-readability as the
doctrine defines it, "can a downstream LLM recover the paper's facts,"
except for one specific defect class: gross content deletion. The gate
measures **token-set presence**, a real and useful signal, but a strictly
narrower one than either doctrine target. It is best described as a
content-presence floor with two structural tripwires bolted on for reasons
that are honestly cosmetic (heading monotonicity) or detection-incomplete
(TOC leakage), not as an LLM-comprehension gate and not as a human-fidelity
gate. The actual LLM-comprehension work, the part of the doctrine that
addresses reordering, table-cell swaps, and identifier corruption, lives
entirely in Lane 3 (`facts.py`, deterministic but requiring per-paper
authored facts, currently a small corpus per `CLAUDE.md:516-525`) and in the
advisory LLM lane, which by design never gates (`CLAUDE.md:551-564`,
"NEVER hard-fails... never overwrites the whisker verdict on record"). The
gap is not that the doctrine is wrong or the code is dishonest; the gap is
that the doctrine is implemented, correctly, in a lane that structurally
cannot fail a paper, while the lane that can fail a paper implements a
narrower, honestly-different thing that the project's own prose sometimes
elides by calling all of it "the gate."

### 3.7 Goodhart exposure

`packages/whisker/src/whisker/CLAUDE.md:934` (Known gaps) and
`golden.py:8-17` (`raw/w4-doctrine-quotes.md` SS2) both state plainly that
golden ideals are hand-blessed by a human reviewing a diff, not an
independent oracle: "no repo has an automatic 'this file is 100% correct'
oracle. The committed expected file is a self-blessed snapshot of tomd
output, frozen by a HUMAN reviewing the diff." The Lane-2 fidelity metrics
(`nid`/`teds`/`mhs`) and now the ideal panel (`golden_ideals.py`) are scored
against those same hand-built ideals, and `constants.py` thresholds
(`UNIGRAM_COVERAGE_FAIL_EDGE`, `REF_NID_ADVISORY_EDGE`) are, by the
project's own "Calibration status" admission (`CLAUDE.md:486-501`), "adopted
from external repos, not fitted on our labeled corpus," "provisional." A
metric tuned against a hand-built ideal, then used to certify conversions
against that same family of ideals, is structurally exposed to Goodhart
drift: the tool could converge on producing markdown that scores well
against the specific structural conventions the human blessers favored
(bullet style, blank-line placement, heading nesting) without that
convergence tracking LLM-comprehension at all, precisely because
`unigram_coverage` (the only hard-gating axis) cannot see the difference
between "the ideal's structural conventions" and "the content." This audit
found no evidence of active Goodharting (no data showing scores improving
while comprehension measurably degrades), but the structural precondition
for it, a hand-built ground truth plus an order-invariant, cosmetics-blind
hard gate plus provisional thresholds, is present and documented by the
project itself, not discovered here.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---|---|---|
| F1 | The documentary doctrine is internally consistent and explicit: target is LLM-recoverable content, not typographic perfection; no verdict state is ever named "perfect" | Informational | HIGH |
| F2 | The deterministic hard gate's sole content-quality axis (`unigram_coverage`) is order-invariant by design and therefore structurally blind to reordering (C2), table-cell swap (C3), and identifier corruption (C4) | High | HIGH |
| F3 | C4's defect class is invisible to both lanes because the shared text normalizer strips the corrupted characters before any comparison runs; this is a representational ceiling, not a threshold-tuning gap | High | HIGH |
| F4 | The two structural gates that do hard-fail (`no_toc_leak`, `heading_monotone`) are, by the project's own advisory-prompt language, closer to human-tidiness signals than comprehension signals; `heading_monotone`'s own system prompt calls its trigger "cosmetic... a reader loses nothing" | Medium | HIGH |
| F5 | The actual comprehension-doctrine work (Lane 3 facts, advisory LLM lane) is architecturally confined to non-gating surfaces; the surface with teeth implements a narrower content-presence claim | High | HIGH |
| F6 | The measurement stack's calibration precondition (hand-built ideals, provisional thresholds) is a documented structural precondition for Goodhart drift, though no active drift was found in this audit | Medium | MEDIUM |

## 5. False-Pass Hypothesis

**Could Lane 3 (facts.py) be counted as closing the gap identified in F2/F5,
making the overall system doctrine-aligned even if the hard gate alone is
not?** Only for papers with authored facts. `CLAUDE.md:516-525` names 5
canonical corpus members with 37 verified facts total; `E8`'s fleet run
covers 381 papers. For the overwhelming majority of the fleet, Lane 3
contributes nothing (`facts.py:146-148`, `raw/w4-doctrine-quotes.md` SS3:
"a paper with no verified facts passes" vacuously), so the hard gate's
narrower content-presence measure is, in practice, the only signal most
papers ever receive. The persona research already in the repo
(`packages/whisker/research/persona/08-downstream-llm-consumer.md:8`,
cited in `raw/w4-doctrine-quotes.md` SS3) reaches the identical conclusion
independently: "`pass` is not an LLM-comprehension certificate... Lane 3
runs on 0/382 papers," and 96.3% of papers reach downstream pipelines "with
zero deterministic fact assertions enforced." This report's finding is
consistent with, not contradicted by, that prior internal research.

**Could the canary results (E17/E18) be an artifact of this one document's
structure rather than a general property of the gate?** No; the mechanism is
general. `unigram_coverage` is order-invariant and bag-of-tokens by its
docstring-level definition (`score.py`, `raw/w4-doctrine-quotes.md` SS4), not
by any property specific to the 25157-character canary document. Any
document subjected to a token-preserving reorder, swap, or character-level
substitution within the normalizer's alnum-CJK keep-set would produce the
same blindness. The canary demonstrates a documented, general property; it
does not discover a document-specific quirk. (Per C27, the specific
*document* used for this demonstration currently has a broken provenance
lock; that caveats reproducibility of this exact numeric run, not the
generality of the mechanism being demonstrated, which follows directly from
reading `score.py` and `metrics.py`'s normalizer chain.)

## 6. Gate/Dimension Mapping (PROPOSED)

- **Doctrine-documentation consistency: PROPOSED PASS.** The written record
  is honest, internally consistent, and never overclaims typographic
  perfection.
- **Doctrine-implementation alignment (the hard gate specifically): PROPOSED
  FAIL-UNPROVEN as an LLM-comprehension measure.** It is a defensible,
  well-formed content-presence floor; it is not what the doctrine section of
  the same file describes as the reason Lane 3 must exist.
- **Structural tripwires (`no_toc_leak`, `heading_monotone`) as
  comprehension gates: PROPOSED FAIL-UNPROVEN.** Both are better justified as
  tidiness/detection gates than comprehension gates; the project's own
  advisory-prompt language supports this characterization directly.
- **Lane 3 as the doctrine's actual implementation: PROPOSED
  PASS-PROVISIONAL, scoped.** Correct design, proven on its own small corpus
  (comprehension-poc-report.md), architecturally non-gating and currently
  near-zero fleet coverage.
- **Goodhart exposure: PROPOSED PASS-PROVISIONAL (precondition present, no
  active drift found).**

## 7. Limitations

- This report evaluates one 25157-character base document and its four
  mutations (E17/E18); it does not establish that every document in the
  381-paper fleet would exhibit identical blindness, only that the mechanism
  producing the blindness is general by construction.
- The Goodhart assessment (SS3.7) is a structural-precondition argument, not
  a measured drift; no time-series of scores-vs-comprehension was available
  to test for actual convergence pressure.
- This report does not attempt to design a replacement metric; it states
  what the current one does and does not measure.
- Per C27, the canary base document's provenance lock is currently failing
  (`test_dev_replay_schema.py:190`); this report's qualitative conclusions
  rest on the documented behavior of `unigram_coverage`/`clean_string`
  (general, code-level facts) more than on the specific numeric canary run,
  which should be re-verified once that lock is resolved.

## 8. Conclusion

Whisker's documentation states its doctrine honestly and has never claimed
typographic perfection; that much is unambiguous and this audit found
nothing contradicting it. But the surface that actually gates, the only one
with the power to fail a paper for the fleet at large, is not the doctrine's
implementation. It is an order-invariant, bag-of-tokens content-presence
floor, well-formed and useful for what it is, plus two structural tripwires
that the project's own advisory-lane prompt describes in terms closer to
human tidiness than LLM comprehension. The doctrine's actual implementation,
source-verified fact recovery, is real, correctly designed, and empirically
validated once, but it lives entirely in non-gating lanes and currently
covers a negligible fraction of the fleet. The honest statement is: whisker
measures token-set presence at the gate, and measures LLM-readability
directly only where a human has authored facts for that specific paper,
which is nearly nowhere yet. The documentation says one thing about intent;
the part of the system with enforcement power does a narrower, different,
still-useful thing; and the project's own prior internal research
(`08-downstream-llm-consumer.md`, `QA-RELIABILITY-VERDICT.md`) has already
reached compatible conclusions independently. This is not a claim that the
tool is dishonest. It is a claim that "pass" certifies less than the
doctrine section of its own documentation implies, and that the gap between
the two is precisely located: at the boundary between what gates
(order-invariant token presence plus two cosmetic tripwires) and what
doesn't (everything doctrine actually cares about, reordering, table
semantics, identifier fidelity).

## 9. Delta vs Auditv2

No Auditv2 predecessor exists for this claim; it is new in v3. Auditv1 and
Auditv2 treated the Lane 1/2/3 doctrine as an architectural given, documented
in `CLAUDE.md` and validated by the comprehension POC report, and audited
individual mechanisms against it (Auditv2's C06 per-axis null-eligibility,
C08 inverted canaries, and the broader C01-C25 primary reports) without
asking whether the aggregate measurement surface, as installed today,
actually implements the stated doctrine end-to-end, or whether components
long treated as settled (`unigram_coverage`, `no_toc_leak`,
`heading_monotone`) are quietly serving a different purpose than advertised.
This claim exists because Auditv3 is the first cycle to pair a documentary
record built specifically to state the doctrine's own words
(`raw/w4-doctrine-quotes.md`) with live canary evidence generated
specifically to test that documentary record against the running system in
the same audit (E17, E18). Auditv2's C08 (baseline canary) came closest,
proving the comprehension corpus's canaries had teeth on the papers that
have authored facts; it did not ask what the hard gate does on a paper that
has none, which is where this report's central finding (F2, F5) lives.
