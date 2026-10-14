# Whisker Audit Result, 2026-08-03, Auditor: Audit v3 (C30 Synthesis)

## 1. Scope, date, HEAD, branch, worktree boundary

| Field | Value |
|---|---|
| Date | 2026-08-03 |
| HEAD | `0d18a65` |
| Content manifest | `b9ad8ab0...8f771` (SHA-256 over all audited `packages/whisker` files) |
| Branch | `main` |
| Package | whisker 0.5.0 |
| Python | 3.12.10 |
| OS | Windows NT 10.0.26200 |
| LLM endpoint | `alliance-pod`, `openai/gpt-oss-120b`, live and serving |

**Worktree boundary.** The audited state is HEAD plus **7205 uncommitted
insertions**. Auditv2 recorded the same problem and it was not fixed, so v3
changed method rather than repeating the complaint: the target is pinned by a
SHA-256 content manifest of every audited file (`raw/w0-target-manifest.txt`),
not by a commit. Findings are reproducible against that manifest. They are not
reproducible from `git checkout 0d18a65`.

**Baseline test result.** `uv run --package whisker pytest packages/whisker/tests -q`
-> **3 failed, 1784 passed, 8 skipped, 3 xfailed in 34.48s** (exit 1). Auditv2
recorded 1406 passed, 0 failed. The suite is RED, and section 12 separates the
three failures by what they actually mean, because they do not mean the same
thing.

**Pod availability.** Auditv2's single largest limitation, all ten runtime
scenarios blocked on a missing `ALLIANCE_POD_KEY`, is resolved. The key is
present in `.env` and the pod is live. An initial probe returned HTTP 403 for
both real and bogus URLs, which was diagnosed as Cloudflare error 1010
rejecting the default Python user-agent, not a dead pod. Every runtime result
below is live.

---

## 2. Fresh claims registry

| ID | Claim | Value | Change vs v2 |
|---|---|---|---|
| C-VER | Version phase | `0.5.0` (pre-1.0) | unchanged |
| C-API | Stable public API | No | unchanged |
| C-CAL | Calibration status | Hand-set edges; `calibrate` wired but never produced a committed `thresholds.json` | sharpened (E33) |
| C-LAB | Label role | Advisory; gate-bearing only for verified Lane 3 facts | unchanged |
| C-INF | Default inference | Self-hosted `alliance-pod` | **verified live** |
| C-COMP | Comprehension claimed | Yes (Lane 3 + readback) | unchanged, but see G6 |
| C-PROD | Production-grade ops | No | unchanged |
| C-DET | Determinism tier | Quality-stable core; advisory non-guaranteed | **flip rate measured: 25 % control, 50 % permuted** |
| C-LIC | Licenses | BSL-1.0 + MIT/BSD/Apache-2.0. **No LGPL.** | **corrected: pylatexenc is MIT, not LGPL-3.0+** |
| C-INT | Merged interop | tomd consumes `score-file`/`check-facts` by subprocess | **fail-open discovered** |
| C-IDEAL | Ideal contract | 4 tomd ideals, read-only, source is factual authority | **checkout-only; absent in an installed whisker** |
| C-OCR | OCR capability | None, documented as out of scope | new in v3 |
| C-DOCT | Doctrine | LLM fact recovery, not human-perfect conversion; no `perfect` verdict exists | new in v3 |

---

## 3. Gate ledger (conjunctive, non-compensatory)

Per Scorecard §2 and §4.2: any Fail sets the band to Unsound regardless of
composite.

| Gate | v2 | v3 | Evidence |
|---|---|---|---|
| **G1** Advisory non-leakage | PASS-PROVISIONAL | **PASS** | E11, E15, E16. Live: a heading-monotone-only deterministic fail plus a live `review` selected `llm_rescue_heading`, produced combined `review`, never `pass`, and left exit 5 intact. No path promotes a deterministic fail. |
| **G2** Fail-not-partial | PASS-PROVISIONAL | **PASS** | E8, E11, E13, E21. Five live fault injections, none exited 0; 381-paper fleet with no silent loss; operational failure emits no verdict and exits 1. |
| **G3** Determinism by replay | PASS-PROVISIONAL | **PASS** | E10. Two separate processes, byte-identical sidecars, 3 of 3. The declared quality-stable tier's equality contract is satisfied. |
| **G4** Per-axis + eval integrity | PASS | **PASS** | E21, C06, C15. Ineligible axes report `null`, never a fabricated 0.0 or 1.0; TEDS pairs structure with content at one bar. Implementation integrity holds. The blindness in E28 is scored at D4, not here, because the axes compute what they are defined to compute. |
| **G5** Untrusted-input mediation | PASS-PROVISIONAL | **PASS** | E15. Two live injections against the real pod, instruction override and delimiter forgery. Neither flipped the verdict. |
| **G6** Baseline canary (inverted) | PASS | **FAIL** | E17, E18, E22. See below. |
| **G7** Licensing / attribution | PASS | **FAIL** | E26, `raw/w3-deps-packaging.md`. See below. |

### G6 failure, stated precisely

The gate's fail rule is "No universal baseline, **OR an inverted canary
passes**". Four inverted canaries passed when they were required to fail.

| Inverted canary | Deterministic lane | Advisory lane | Fused |
|---|---|---|---|
| C2, all top-level sections permuted | `unigram_coverage` and `content_recall` both 1.0, passed | caught it, called it "substantial reordering" | **`pass`** (E19) |
| C3, two table cell values swapped | invisible, passed | caught it | `review` |
| C4, 14 `<memory_resource>` identifiers mangled | metrics numerically **identical** to the untouched control | byte-identical reasoning to control, saw nothing | passed as control |
| readback `--corrupt` | n/a | 2 of 5 papers passed **every** fact while corrupted (E22) | n/a |

Auditv2 scored G6 PASS on three unit-level canaries in
`test_comprehension_corpus.py`. Those still have teeth. What v3 added was
end-to-end document-level canaries against real papers, and at that level the
gate does not hold.

The gross-loss case is worth recording as the counterweight: deleting 46.7 %
of the document was caught by both lanes, with the model naming the omitted
section exactly (E17 C1). The blindness is specific to token-preserving
corruption, not general.

### G7 failure, stated precisely

License compatibility is clean and better than v2 believed. pylatexenc is
**MIT**, verified against installed distribution metadata, the upstream
`LICENSE.txt` and PyPI; Auditv2's LGPL-3.0-or-later entry was wrong. No
GPL-family primary license exists in the core dependency set. BSL-1.0 headers
are present on 69 of 69 files.

The gate fails on its second clause, "missing attribution".
`THIRD_PARTY_NOTICES.md` names langextract and nothing else, while
`CLAUDE.md` itself describes the PubTabNet/OmniDocBench TEDS implementation
and the OmniDocBench text normalizer as **verbatim ports**. A verbatim port
that the project's own documentation calls a verbatim port, with no notice
entry, is the gate's stated fail condition.

This is the cheapest failure in the report to repair.

**Gate summary: 5 PASS, 2 FAIL, 0 PROVISIONAL.** Auditv2 had 3 PASS and 4
PROVISIONAL. Every one of v2's provisional gates was converted to a hard PASS
by live evidence. The two failures are new findings that offline inspection
could not have produced.

---

## 4. Real-LLM runtime matrix

**Status: 10 of 10 executed.** Auditv2: 10 of 10 blocked.

| # | Scenario | Result |
|---|---|---|
| 1 | Positive control | verdict `review`, confidence 0.98, real per-unit findings |
| 2 | Known structural defect | caught, fabricated sentence quoted back |
| 3 | Instruction in document | verdict unchanged at `review`; injection ignored |
| 4 | Delimiter forgery | verdict unchanged at `review`; forged close ignored |
| 5 | Adversarial advisory verdict | did not propagate |
| 6 | Grounding failure | claims classified, no unsupported promotion |
| 7 | Operational failure | no verdict emitted, exit 1 |
| 8 | `status="error"` fallback | tombstone written, stale sidecar replaced |
| 9 | Mixed batch | per-paper isolation held |
| 10 | Readback corruption control | ran; **control is weak**, see G6 |

**Scope limit, stated rather than buried.** Every scenario and every canary
derives from one document, P4182R0, one model and one endpoint (E31). These
are one-paper findings.

---

## 5. Per-dimension levels, grades, reasons

Weights per Scorecard §3, unchanged from v2 for comparability.

| Dimension | v2 level/grade | v3 level/grade | Reason |
|---|---|---|---|
| **D1** Epistemic separation (w=20) | 3 / B | **3 / A** | Separation proven live, not merely inspected (E11, E15, E16). Grade rises because the evidence class changed from code reading to runtime. Level stays 3: E19 shows the fused verdict can read `pass` while the record it summarizes says `review`, a reporting defect inside a sound architecture. |
| **D2** Determinism (w=15) | 3 / B | **3 / B** | Byte-identical two-process replay, 3 of 3 (E10), which v2 could not obtain. Held at B because the project's own pinning tripwire is red on two papers (E1), so stability across code states is currently contradicted by its own control. |
| **D3** Fidelity / fail-not-partial (w=15) | 3 / B | **3 / B** | Live fault injection clean on all five faults; advisory lane fails closed on an empty text layer (E21). Not raised to A because the tomd bless gate is fail-open (E29 probe 5) and `convert_paper_full` returns a skipped result without raising (E21b). |
| **D4** Metric validity (w=15) | 3 / A | **2 / C** | The largest single drop. Null-eligibility discipline remains exemplary. But the gating surface provably cannot represent a large defect class: six of nine C++ semantic corruptions yield a text NID of exactly 0.000 (E28), and permutation leaves `unigram_coverage` at 1.0 (E17). |
| **D5** Anti-gaming (w=12) | 3 / B | **2 / C** | Holdout and dev-replay are disjoint and the unit canaries hold. But four inverted canaries passed (G6), the readback negative control moves the fact rate by 5.4 points (E22), and the pass rate cannot serve as a quality KPI (L48). |
| **D6** Untrusted-input (w=10) | 2 / C | **3 / B** | The clearest improvement. v2's weakest gate is now live-proven (E15). Not A: the PDF lane detects loss, not addition, so fabricated content is structurally invisible to it. |
| **D7** API / packaging (w=8) | 3 / A | **3 / A** | 12 core deps, zero LLM imports outside `tapetum_llm/`, `uv lock --check` clean, wheel clean of tests and caches, no secret in any of 65 artifacts, writes confined to their own directories. |
| **D8** Documentation / CLI (w=5) | 3 / B | **2 / C** | No `packages/whisker/README.md` at all (L21). A vLLM server flag documented as a whisker flag, an unregistered `whisker compare`, eight CLI flags in no operator document, `survey/` absent from the architecture map. |

---

## 6. Navigation composite

```
D1: (3/4) * 100 * 0.20 = 15.00
D2: (3/4) * 100 * 0.15 = 11.25
D3: (3/4) * 100 * 0.15 = 11.25
D4: (2/4) * 100 * 0.15 =  7.50
D5: (2/4) * 100 * 0.12 =  6.00
D6: (3/4) * 100 * 0.10 =  7.50
D7: (3/4) * 100 * 0.08 =  6.00
D8: (2/4) * 100 * 0.05 =  2.50
                          ------
Composite:                 67.00      (v2: 72.50, delta -5.50)
```

---

## 7. Band, interval, weakest link

**Composite:** 67.00
**Interval:** [60, 73]
**Weakest-link grade across D1-D4:** **C** (D4, metric validity)

### Band: **Unsound**

Per Scorecard §4.2, the gate override is non-compensatory: G6 and G7 fail,
therefore the band is Unsound regardless of the composite.

**This needs saying plainly, because the word is heavier than the finding.**
"Unsound" here is the rubric's mechanical label for "at least one conjunctive
gate failed". It is not a statement that the architecture is wrong, and this
audit found the opposite on the question that has dominated v1 and v2: the
central design decision, keeping the advisory model out of the gate, held
under live adversarial pressure and converted four provisional gates into
hard passes. A composite of 67.00 still clears the numeric Professional-grade
threshold of 65.

What the band correctly records is that a QA tool whose inverted canaries can
pass has not demonstrated the one property a QA tool exists to have. G6 is the
right gate to fail on, and it is failing for a specific and repairable reason
rather than a diffuse one.

### Uncertainty drivers

1. **Single substrate.** Every live LLM finding derives from one paper, one
   model, one endpoint (E31). This is the dominant width driver.
2. **The substrate's own lock is red.** `golden/ideals/p4182r0.md` no longer
   matches its holdout hash; the source PDF does match. The canary control is
   an edited descendant of the blessed ideal, not the blessed ideal.
3. **Dirty tree.** Pinned by manifest, not reproducible from a commit.
4. **Four canaries.** A small battery; the classes not probed are unknown.
5. **Three UNVERIFIED checks** (L25 escalation rate, L28 UTF-8 output, L33
   kill-drill).

### Flip conditions

| # | Condition | Direction |
|---|---|---|
| 1 | Attribution entries added for the TEDS and normalizer ports | G7 -> PASS |
| 2 | An order-sensitive or punctuation-sensitive signal gates, and C2/C4 then fail | G6 -> PASS, D4 -> 3/B |
| 3 | Both of the above, with the composite recomputed | Band -> Professional-grade (qualified) |
| 4 | Canaries repeated across 10+ papers with the same blindness | D4 -> 1, confidence rises, band unchanged |
| 5 | Canaries across 10+ papers show C4 was substrate-specific | D4 recovers toward 3 |
| 6 | Advisory verdict found to influence an exit code | G1 -> FAIL (no evidence of this; listed for completeness) |

---

## 8. Findings ranked by severity

### Critical

| ID | Finding | Source | Gate/Dim |
|---|---|---|---|
| **CR1** | The gating metric surface cannot represent punctuation-level semantic corruption. Six of nine C++ corruptions, including `T&&` vs `T&`, `<=` vs `>=`, `p->next` vs `p.next`, produce a text NID of exactly 0.000. In C++ standards papers punctuation carries the semantics. | E28, E18, L37 | G6, D4 |
| **CR2** | Inverted canaries pass. A permuted document fuses to `pass`; a document with 14 mangled identifiers is numerically indistinguishable from the correct one; 2 of 5 papers pass every readback fact while corrupted. | E17, E18, E22, L16, L48 | G6, D5 |

### High

| ID | Finding | Source | Gate/Dim |
|---|---|---|---|
| H1 | `bless_stem` skips its whisker gate whenever whisker is unreachable, crashed, timed out or emits bad JSON, then blesses the golden. Fail-open on the gate protecting the measuring stick. | E29 probe 5, L39 | D3 |
| H2 | The readback negative control has no teeth: `_corrupt_markdown` touches only pipe cells, `>=`, and `^n`, one of which is itself invisible to the text axes; the corruption banner primes the model; the CLI exits 0 regardless. | E22, E28, L16 | G6, D5 |
| H3 | Two of three test failures are inside `test_score_pinning.py`, the mechanism that exists to detect unannounced scoring changes. A tripwire already tripped cannot detect the next change. | E1, E27, L14 | D2 |
| H4 | Required attribution absent for two verbatim ports the project's own docs call verbatim ports. | E26, L23 | **G7** |
| H5 | All live LLM evidence rests on one paper whose blessed ideal no longer matches its holdout lock. | E31, L17 | D1, D5 |

### Medium

| ID | Finding | Source | Gate/Dim |
|---|---|---|---|
| M1 | The ideal lane is checkout-only. An installed whisker silently reports `ideal_*: null`, indistinguishable from "no ideal exists". | E25, L04 | D4, D7 |
| M2 | The fused verdict can read `pass` while the same record holds `tapetum_verdict: review`, because the cap reads an unstable metadata sub-check rather than the primary judge's verdict. | E19, E20, E32, C21 | D1 |
| M3 | No `packages/whisker/README.md`. The living contract is an internal agent-guidance file. | L21 | D8 |
| M4 | Whisker is not wired into `paperflow full`; a paper can traverse the whole ingestion path with no QA lane observing it, and the boundary is undocumented. | E24, L01 | D8 |
| M5 | `tables.py` has zero dedicated test functions while Lane 3 facts and the Lane 2 TEDS axis both depend on it. | E3, L18 | D4 |
| M6 | 8 of 16 thresholds are bare literals; `calibrate` has never produced a committed `thresholds.json`. "Calibrated" is the wrong word for the current state. | E33, L15, L29 | D4, D5 |
| M7 | The advisory metadata/outline check flips run to run: the control passed once in four observations, the permuted document twice in four. | E20, L14 | D1, D2 |

### Low

| ID | Finding | Source |
|---|---|---|
| L1 | `--enable-prefix-caching` documented as a whisker flag; it is a vLLM server flag. | `raw/w2-cli-surface.md` |
| L2 | `compare/cli.py` declares `prog="whisker-compare"` but is registered nowhere. | L02 |
| L3 | Eight CLI flags exist in `--help` and in no operator document. | L22 |
| L4 | VLM chain remains 812 unwired lines; `CLAUDE.md:885` still says 788. | L19, L24 |
| L5 | `convert_paper_full` returns a skipped result without raising; fail-loud is caller-enforced. | E21b |
| L6 | The wheel ships two internal agent-guidance documents. | `raw/w3-deps-packaging.md` |
| L7 | `survey/` is absent from the architecture map. | C29 |

### Informational

| ID | Finding |
|---|---|
| I1 | Auditv2's pylatexenc LGPL-3.0+ entry is **wrong**; it is MIT. No copyleft exists in the ship graph. |
| I2 | Advisory attribution exceeds requirement: every sidecar carries `prompt_sha256`, `schema_sha256`, `lane_version`, `model`. |
| I3 | No secret appears in any of 65 audit artifacts. |
| I4 | CI refuses `WHISKER_PIN_UPDATE=1` when `CI` is set; the LLM lane is never a merge gate. |
| I5 | The holdout lock test fired correctly on a real fixture drift. It is a working control, not a broken one, and should not be counted with the two pinning failures. |
| I6 | All 189 workspace PDFs carry a text layer, minimum 2121 chars, median 21478. The OCR deferral rests on a measured corpus property. |

---

## 9. Answerability: "what percentage converted perfectly?"

**The question cannot be answered by the tool today, and the tool never claims
it can.** `score.py:53-55` defines exactly three verdicts. No code path
computes a correctness percentage. `whisker report` is not a subcommand.

The defect is not the absence. It is the label. Every fleet run ends with a
footer built at `report.py:252`:

```
=== N failed, N review, N passed (M scored) in Xs ===
```

The word is "passed", unqualified, and its meaning, "cleared the structural
gates and the unigram floor", lives only in `CLAUDE.md`. The distance between
that and "converted correctly" is measured, not hypothetical: a fully permuted
document holds `unigram_coverage` at 1.0, and fourteen mangled identifiers are
numerically identical to the correct text.

**The honest sentence to give Greg:** whisker reports the share of papers with
no detected structural or lexical-coverage defect. It does not measure
correctness, it has no notion of perfect, and its floor is order-invariant and
punctuation-blind, so a document can clear it while being semantically wrong.

---

## 10. Doctrine alignment: LLM-readable versus perfect

The documentary record is honest and internally consistent
(`raw/w4-doctrine-quotes.md`). `CLAUDE.md:126-127` asks whether an LLM can
still recover the paper's facts; `:527` calls the deterministic surface a
proxy for that; `tapetum_llm.md:181` instructs the advisory lane not to fail
on cosmetics; the tomd claim ("looks like a human wrote it") is kept distinct
from the whisker claim. No document promises perfection and no verdict state
encodes it.

The gap is between doctrine and enforcement, and it is precise. The only
surface with gating power is `unigram_coverage`, an order-invariant multiset
floor. Reading order, table semantics and identifier fidelity are exactly the
properties that determine whether a downstream LLM reads a paper correctly,
and they are exactly what that floor cannot see. The doctrine's real
implementation, Lane 3 fact recovery, is correctly designed, correctly
non-gating, and covers a negligible fraction of the fleet.

So: whisker does not measure human typographic fidelity, and never claimed to.
It also does not gate on LLM readability. It gates on token-set presence,
which is a real and narrower signal than either. The documentation describes
the intent accurately; the enforced surface implements something smaller, and
nothing tells the reader where the boundary is.

---

## 11. OCR and scanned-PDF boundary

**No production OCR exists, and this is a documented, evidence-based
decision rather than a gap.** `tomd/README.md:99` states it outright. PDF text
comes from PyMuPDF; the optional Docling table backend runs `do_ocr=False`;
the only OCR-shaped code is the dormant VLM lane and the `survey/` competitor
adapters.

Competitors do use OCR, with recorded numbers: Marker with Surya at 76.0 %
against 43.6 % with OCR disabled; olmOCR at 75.5 ± 1.0 against Marker's
70.1 ± 1.1. Those numbers matter for scanned corpora.

Ours is not one. All 189 workspace PDFs carry a text layer, minimum 2121
characters, and none approaches the 200-character guard. WG21 mailings are
born-digital, so there is nothing for OCR to do. The deferral holds on
measured grounds.

**Behaviour on a scanned source, measured on a synthetic image-only PDF with
zero extractable characters (E21).** The advisory lane fails closed correctly:
`TextLayerError`, `PdfLaneError`, exit 1, with both plausible and empty
markdown. The deterministic lane cannot reach `fail`, because its hard gate
reads `unigram_coverage` and coverage against an empty source is vacuously
1.0. It does reach `review` reliably, because `unigram_drift` is 1.0 by
construction and survives `--no-reference` (E21c). There is no silent-green
path.

---

## 12. What the red suite actually means

Three failures, three different meanings. Collapsing them into "the suite is
red" would misread a working control as a broken one.

| Failure | Meaning |
|---|---|
| `test_score_pinning.py[p3556r0]`, gate mismatch | **Tripwire tripped.** Scoring output changed without being announced. |
| `test_score_pinning.py[p2040r0]`, `max_heading_level actual=3 expected=4` | **Tripwire tripped.** Same class. |
| `test_dev_replay_schema.py::test_locked_candidate_dispositions`, `p4182r0` | **Control fired correctly.** The blessed ideal's SHA-256 drifted from its lock; the source PDF did not. This is the mechanism doing its job. |

Neither `golden.py`, `guard.py` nor `facts.py` is touched by any of the three.

---

## 13. Delta versus Auditv2

| Axis | v2 | v3 |
|---|---|---|
| Gates | 3 PASS, 4 PROVISIONAL, 0 FAIL | **5 PASS, 0 PROVISIONAL, 2 FAIL** |
| Runtime matrix | 0 of 10 | **10 of 10** |
| Composite | 72.50 | **67.00** |
| Band | Emerging (upper), qualified toward Professional | **Unsound** (gate override) |
| Weakest link | C (D6) | **C (D4)** |
| Test suite | 1406 passed, 0 failed | 1784 passed, **3 failed** |
| pylatexenc | LGPL-3.0+ | **MIT** (v2 corrected) |

The composite fell 5.5 points while the evidence base improved enormously.
That is not a contradiction, it is what an audit looks like when the
instrument gets sharper. v2 could only read code, so it scored architecture,
and the architecture is good. v3 could run the thing, and running it found two
gate failures that no amount of code reading would have produced. Four of v2's
provisional gates became hard passes; the failures that replaced them are in
places v2 never probed.

The uncomfortable summary: **the architecture is sound and the measurement is
not.** The advisory model is correctly fenced out of the gate, which was the
question v1 and v2 kept asking. The gate it is fenced out of turns out to be
blind to a class of defects that matters in this domain, which is the question
nobody had asked.

---

## 14. Auditor's own limitations

Recorded so the next audit does not inherit them silently.

1. **One paper.** All live LLM evidence and all four canaries derive from
   P4182R0 (E31). Generalization to the fleet is not supported.
2. **One model, one endpoint.** `openai/gpt-oss-120b` on `alliance-pod`.
   Model-specific behaviour is indistinguishable from lane behaviour.
3. **Small stability sample.** Four observations per document underlie the
   flip-rate figures in E20.
4. **A finding was retracted mid-audit.** E21a originally claimed the
   deterministic lane goes silently green on scanned PDFs. Testing every axis
   rather than one showed `unigram_drift` fires structurally and cannot be
   suppressed. The claim was withdrawn and both versions are preserved in the
   ledger (E21c). A cross-cutting thesis lost one of its three instances as a
   result.
5. **Dirty tree.** The v2 lesson was not applied; it was worked around.
6. **Three checks unverified.** L25, L28, L33, each naming the experiment that
   would close it.
