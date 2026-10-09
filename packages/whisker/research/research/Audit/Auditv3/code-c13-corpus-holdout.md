# C13 Corpus and Holdout

**Role**: Audit corpus hygiene, dev-replay vs holdout separation, and overfitting exposure.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771.
**Gates**: D5 (corpus integrity, PROPOSED), D4 (scoring accuracy, PROPOSED). See 00-PRECONDITIONS.md for target-pin status.

## 1. Scope

Determine, by direct enumeration rather than assumption, whether the dev-replay
set (9 golden PRs) and the holdout set (locked LLM-evidence candidates)
actually contain disjoint PIDs and with what exact counts. Assess whether
`p0533r9`'s quarantine correctly closes the one documented overlap risk.
Assess whether the score-pinning golden set's PID overlap with both dev-replay
and holdout compromises isolation. Interpret the `TestHoldoutAnchors::
test_locked_candidate_dispositions[p4182r0]` failure recorded in E1 for what
it says about the holdout's actual lock state this run. Assess whether the
audit's own live-LLM evidence base (C15-C18) is concentrated on a small,
reused PID set.

## 2. Commands and Exits

| Evidence | Command / source | Result |
|---|---|---|
| E1 | `uv run --package whisker pytest packages/whisker/tests -q --tb=line` | exit 1: 3 failed, 1784 passed, 8 skipped, 3 xfailed |
| — | `packages/whisker/corpus/dev-replay/labels.json` read | 9 paper keys |
| — | `packages/whisker/corpus/holdout/manifest.json` read | 3 active papers, 1 quarantined |
| — | `packages/whisker/tests/test_dev_replay_schema.py` read | schema + isolation assertions |
| — | `packages/whisker/tests/test_score_pinning.py` read | 19-stem golden set |
| — | SHA-256 of `corpus/P4182R0.expected.md` vs `tomd/.../golden/ideals/p4182r0.md` | `bfc2d8f8...` vs `e54f344f...`, distinct files |

## 3. Current Evidence

### 3.1 Dev-replay and holdout PIDs, enumerated

Dev-replay (`corpus/dev-replay/labels.json`, 9 keys): `p4020r0` (PR282),
`p2040r0` (PR283), `p0957r8` (PR284), `p3556r0` (PR285), `p1068r11` (PR286),
`p1122r3` (PR290), `p0533r9` (PR293), `p3411r5` (PR294), `p3953r0` (PR295).

Holdout active (`corpus/holdout/manifest.json` `papers`): `p1112r4`,
`p3714r0`, `p4182r0`. Holdout quarantined: `p0533r9`, annotated "Dev-replay PR
#293 contamination; excluded from every holdout metric because it is PR
#293."

Set intersection of the 9 dev-replay PIDs and the 3 active holdout PIDs is
empty: **0 shared PIDs**. `p0533r9` is the one PID that would have collided
(it is dev-replay PR#293) and it is explicitly excluded from the active
holdout set via the `quarantined` block, not merely omitted. This is a
different assurance than "never added": the manifest records that it was
identified and pulled out, and `test_active_holdout_excludes_dev_replay`
(`test_dev_replay_schema.py:142-147`) asserts both the disjointness and the
quarantine annotation programmatically. That test is not among E1's three
failures, so it held on this run.

### 3.2 The holdout-anchor test failure (E1)

E1 records `test_dev_replay_schema.py::TestHoldoutAnchors::
test_locked_candidate_dispositions` failing with `AssertionError: p4182r0`.
That test (`test_dev_replay_schema.py:180-200`) does three things per active
holdout paper: (1) re-hashes the locked source and candidate files and
compares against `manifest.json`'s pinned SHA-256 (`_sha256`, lines 45-46,
189-190), (2) re-runs `classify_candidate_evidence` over the paper's
committed anchors against the locked candidate text (`_candidate_
dispositions`, lines 58-74), (3) asserts every anchor's live disposition
still equals its `expected_candidate_status` (lines 197-200). The assertion
message format is `f"{pid}:{anchor['anchor_id']}"`, and E1 reports the
message as literally `p4182r0` with no anchor id suffix visible in the
`--tb=line` summary, which is consistent with either the SHA-256 assertions
at lines 189-190 firing first (candidate or source file changed since the
manifest was pinned) or a disposition mismatch on an anchor whose id string
was truncated in the one-line traceback. The ledger (E1) does not resolve
which; the manifest's designed purpose is exactly to make this failure mode
loud rather than silent (holdout/README.md: "Fingerprint drift fails the
holdout instead of silently changing labels"). Whichever branch fired, the
holdout for `p4182r0`, the one candidate not backed by a byte-exact tomd
snapshot but by "human_blessed_tomd_ideal" (`manifest.json` `candidate_kind`
for `p4182r0`), did not reproduce cleanly against its own lock this run.

### 3.3 p4182r0 is reused across three evidentiary roles

The PID `p4182r0` (case-insensitively `P4182R0`) appears in three separate,
differently-governed corpora simultaneously:

1. **Lane-3 comprehension corpus** (`corpus/P4182R0.facts.jsonl`,
   `.expected.md`, `.validation.md`): "the original POC member" per
   `whisker/CLAUDE.md`, backing 8 verified facts and the one-time LLM
   readback validation.
2. **tapetum_llm evidence holdout** (`corpus/holdout/p4182r0.anchors.jsonl`,
   locked via `manifest.json` to `packages/tomd/tests/fixtures/golden/
   ideals/p4182r0.md`): one of 3 locked candidates for LLM evidence
   precision/recall measurement, explicitly "no threshold tuning permitted"
   (`holdout/README.md`).
3. **This audit's own live-runtime base material** (ledger E13-E20): "Base
   material: golden ideal p4182r0.md against source p4182r0.pdf"
   (ledger §C header) for the ten-scenario matrix, the prompt-injection
   probe, and all four metrology canaries.

The Lane-3 corpus snapshot (`corpus/P4182R0.expected.md`, SHA-256
`bfc2d8f8...`) and the holdout's locked candidate (`packages/tomd/tests/
fixtures/golden/ideals/p4182r0.md`, SHA-256 `e54f344f...`) are confirmed
distinct files (verified this run, not assumed): different provenance
(whisker's own Lane-1 stability snapshot vs tomd's human-blessed golden-QA
ideal), so roles 1 and 2 do not share bytes even though they share a PID.
Role 3 (the audit's own canary base document, "25157 chars, 9 H2 sections",
E17) is very likely the same tomd ideal used in role 2 given the identical
description in ledger §C's header, though the ledger does not print that
file's hash for direct confirmation. The overlap that matters is not
byte-identity, it is that one paper carries the evidentiary weight for three
independent claims in this batch (C15's canaries, C16's authenticity trace,
C17/C18's topology trace) plus whisker's own comprehension-gate history. A
reader of C15-C18 should know the underlying document is not independently
resampled per claim.

### 3.4 Dev-replay carries no candidate lock; holdout does

`corpus/holdout/manifest.json` pins `source_sha256` and `candidate_sha256`
per active paper. `corpus/dev-replay/labels.json` (schema
`dev-replay-labels-v1`) pins neither: its 9 paper records carry `pr`,
`source_type`, `human_verdict`, `defect_groups`, `expected_llm_verdict`,
`expected_det_verdict`, and no path or hash field at all
(`test_dev_replay_schema.py:90-100` enumerates every required field and none
is a hash). This is consistent with the documented design
(`dev-replay/README.md`: "Thresholds and logic may be tuned against this
set"), but it also means nothing mechanically detects when the underlying
golden content a dev-replay label was written against has since changed.

### 3.5 Score-pinning's golden set overlaps both corpora, and two dev-replay members just drifted

`test_score_pinning.py`'s `_GOLDEN_STEMS` (19 entries) includes 5 dev-replay
PIDs (`p0533r9`, `p0957r8`, `p1068r11`, `p3556r0`, `p1122r3`, `p2040r0`,
six by exact count) and 2 holdout PIDs (`p3714r0`, `p1112r4`), scored only
through `whisker.gates.run_gates` and tomd's `compute_metrics`, never through
`tapetum_llm`. This overlap does not by itself compromise holdout isolation
for LLM-evidence testing, because score-pinning never touches the LLM lane
or its thresholds; it is a different instrument measuring a different
surface (deterministic gates/QA metrics) on the same PDF/markdown pair.

E1's two `test_score_pinned` failures land exactly on dev-replay members:
`p3556r0` (PR#285, `expected_det_verdict: "fail"`, one `toc_leak` defect
group, severity medium) shows `gate mismatch` against the committed
baseline, and `p2040r0` (PR#283, `expected_det_verdict: "pass"`, zero
defect groups) shows `max_heading_level: actual=3, expected=4`. The
pinning harness is explicitly designed to catch "silent regressions AND
silent improvements" alike (`whisker/CLAUDE.md` Lane 1 description); E1
does not state which direction either drift went, only that the current
run disagrees with the committed `score-baseline.json`. Because
`dev-replay/labels.json` pins no candidate hash (3.4), there is no
mechanical way from the corpus files alone to confirm whether the golden
content backing these two labels is still the content the label text
describes.

### 3.6 Provenance discipline carried forward from Auditv2

`corpus/README.md`'s honest-status declaration ("all `verified` facts to
date were authored and source-verified by the agent, at the user's
direction; no fact has been independently blessed by a human yet") and the
`checked: draft` / `checked: verified` gate (`facts.py`, `CHECKED_VERIFIED`)
are unchanged in this pass; not re-verified line-by-line this run, carried
from Auditv2 §3.7 as still-present code shape.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---|---|---|
| F1 | Dev-replay (9 PIDs) and active holdout (3 PIDs) are set-disjoint by direct enumeration; the one PID that would collide (`p0533r9`) is explicitly quarantined, not merely absent, and the isolation is asserted by a passing test | INFO | HIGH |
| F2 | `TestHoldoutAnchors::test_locked_candidate_dispositions[p4182r0]` failed this run (E1); the holdout's own designed tripwire (fingerprint or disposition drift) fired on the one candidate backed by a human-blessed ideal rather than a byte-exact snapshot | HIGH | HIGH |
| F3 | `p4182r0` simultaneously serves as the Lane-3 comprehension POC member, a locked LLM-evidence holdout candidate, and this audit's own live-canary base document; the three roles use at least two distinct underlying files but the same PID, concentrating this batch's live evidentiary weight on one paper | MEDIUM | HIGH |
| F4 | Dev-replay carries no source/candidate SHA-256 lock (unlike holdout's `manifest.json`), so nothing mechanically detects staleness between a label's defect description and the current golden content | MEDIUM | HIGH |
| F5 | Two of E1's three failures land on dev-replay PIDs (`p3556r0`, `p2040r0`) in the score-pinning suite, the mechanism documented to catch exactly this class of silent drift; direction of drift (regression vs. fix) is not established by the ledger | MEDIUM | HIGH |
| F6 | Score-pinning's 19-stem golden set overlaps both dev-replay (6 PIDs) and holdout (2 PIDs), but exercises only deterministic gates/QA, never the LLM lane or its thresholds, so this overlap is a different instrument on the same document, not tuning contamination of holdout evidence | INFO | MEDIUM |

## 5. False-Pass Hypothesis

**Could the holdout appear locked while having silently drifted?** Before
this run, yes: nothing outside `test_locked_candidate_dispositions` runs the
SHA-256 comparison, and a reader trusting `holdout/README.md`'s "No
threshold tuning permitted against this set" without running the suite
would not know the lock had failed. This run, the test fired (F2), which is
the tripwire working as designed rather than a false pass; the false-pass
risk is in a workflow that reads the README's claim without also reading
E1's exit code.

**Could dev-replay's unlocked labels mask a stale ground truth silently?**
Yes, structurally: `test_all_papers_have_required_fields` and
`test_defect_groups_have_valid_structure` (`test_dev_replay_schema.py:90-112`)
validate the JSON shape of `labels.json`, not its continued correctness
against the current golden bytes. `test_score_pinning.py` is the only
mechanism that would surface such drift, and it did (F5), but only for gate
booleans and QA scalars, not for the defect-group narrative text itself
(e.g. whether `p3556r0`'s documented `toc_leak` is still present in the
current golden).

## 6. Gate/Dimension Mapping (PROPOSED)

| Gate | Dimension | Status (PROPOSED) |
|---|---|---|
| D5: Corpus integrity | Dev-replay / holdout PID isolation | PROPOSED PASS (F1), with an open holdout-lock exception (F2) |
| D5: Corpus integrity | Holdout fingerprint lock enforcement | PROPOSED FAIL-OPEN this run (F2); mechanism exists, fired, unresolved as of E1 |
| D4: Scoring accuracy | Dev-replay label currency vs. current golden | PROPOSED UNVERIFIED (F4, F5); no hash lock exists to adjudicate |

## 7. Limitations

- The ledger's `--tb=line` capture of `test_locked_candidate_dispositions`
  does not distinguish a SHA-256 mismatch from a disposition mismatch; this
  report reads the test's own branch order (hash checks precede disposition
  checks in the function body) but does not re-run the test with `-v` to
  confirm which assertion fired first.
- Whether `p3556r0`'s and `p2040r0`'s `test_score_pinned` failures represent
  a regression or an accepted fix is not determinable from E1 or the source
  files read; would require diffing the current golden markdown against
  whatever produced `score-baseline.json`, which is out of scope for a
  corpus-hygiene claim and belongs to a scoring-regression investigation.
- Whether ledger §C-D's canary base document is byte-identical to the
  holdout's locked `p4182r0.md` candidate was not directly hash-verified in
  this pass (only inferred from matching descriptions); a direct hash
  comparison would close this gap.
- Per 00-PRECONDITIONS.md §1, the working tree carries 7205 uncommitted
  insertions; this report is only reproducible against the pinned manifest
  aggregate, not from a clean clone.

## 8. Conclusion

Dev-replay and holdout are PID-disjoint by direct count (9 vs. 3, zero
overlap), and the one PID that would have collided is explicitly quarantined
rather than silently omitted, with a passing test asserting both facts.
That said, the holdout's own fingerprint-lock test failed this run on its
one non-byte-exact candidate (`p4182r0`), which is precisely the failure
mode the lock exists to surface loudly rather than let pass silently; this
audit did not further disambiguate a hash mismatch from a disposition
mismatch. Separately, the same PID (`p4182r0`) backs three distinct
evidentiary roles across this repository and this very audit batch, and
dev-replay's labels carry no hash lock at all, which the two dev-replay
score-pinning failures (F5) show is not a theoretical gap: something already
drifted without a mechanical alarm before this run's pinning suite caught
it. No verdict is rendered on whether this constitutes overfitting exposure;
the counts and the failure are reported for the synthesis to weigh.

## 9. Delta vs Auditv2

Auditv2's C13 (HEAD 51cb704, no runtime lane) reported all of dev-replay
separation, `p0533r9` quarantine, and "no holdout data in test
parametrization" as PASS/INFO with HIGH confidence, and explicitly called the
holdout manifest "a documentation artifact, not a machine-readable locked
file" (Auditv2 §7). That description is now stale: `corpus/holdout/
manifest.json` and `test_dev_replay_schema.py::TestHoldoutAnchors` are
machine-readable and machine-checked, and Auditv3 observed that check
actively fail (F2), a runtime fact Auditv2's dirtier, LLM-blocked target
state could not produce. Auditv2 never enumerated dev-replay and holdout
PIDs against each other explicitly (it cited CLAUDE.md prose describing "9
golden PRs" and "48 anchors across 3 non-replay papers" without listing
them); this report performs that enumeration directly (§3.1) and confirms
the documented claim rather than assuming it. Auditv2 did not identify the
`p4182r0` triple-role overlap (F3) or the dev-replay hash-lock asymmetry
(F4); both are new findings enabled by reading the holdout corpus, which did
not exist as a locked manifest at Auditv2's audit time, or existed but was
not exercised as machine-checked evidence.
