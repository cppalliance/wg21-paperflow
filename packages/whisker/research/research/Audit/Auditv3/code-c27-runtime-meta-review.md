# C27 Runtime Meta-Review

**Role**: Adversarially assess whether this audit's own live-LLM runtime
evidence (E13-E20) is sufficient to support any of the verdicts drawn from
it, as distinct from asking whether the evidence exists at all.
**Audited state**: whisker 0.5.0, working tree, manifest
b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771
**Gates**: R1-R10 (Auditv2's runtime scenario taxonomy, re-applied against
Auditv3's E13-E20), PROPOSED.

## 1. Scope

Not "did the runtime lane run" (it did; 00-PRECONDITIONS.md SS2 is GREEN) but
"is what ran enough." This means quantifying breadth (how many distinct
documents, models, pods, reruns) against the claims the ledger draws from it,
and stating explicitly what would have to be run before any of E13-E20 should
be treated as a settled measurement rather than a first probe.

## 2. Commands and Exits

Drivers: `rt2_llm_matrix.py` (E13-E15), `rt3_stress.py` (E16),
`rt4_canaries.py` (E17-E18), `rt7_repeat.py` (E20). All against a throwaway
paperstore workspace, `--concurrency 1`. Pod reachability probe:
`uv run --package whisker --extra tapetum-llm python probe2.py`
(00-PRECONDITIONS.md SS2.2), exit implicit 0 (script output captured, not a
pytest run).

## 3. Current Evidence

### 3.1 What actually ran

| Axis | What the ledger shows |
|---|---|
| Model | `deepseek-v4-pro`, `max_model_len=393216`, confirmed via `/v1/models` (00-PRECONDITIONS.md SS2.2). No second model was probed or compared. |
| Pod | One pod, `alliance-pod`. |
| Base documents for the LLM matrix (E13) | One paper, `p4182r0` (golden ideal vs its PDF source), for 9 of 10 scenarios; S8 adds a 3-paper mixed batch. |
| Base document for the canary battery (E17, E18) | The same paper, `p4182r0.md`/`p4182r0.pdf`, mutated four ways. |
| Stability reruns (E20) | 3 forced re-runs each of 3 papers (control, C2, C4), all derived from the same base document; combined with the original canary run, 4 observations per paper, 12 total. |
| Fleet-scale runtime coverage | 381 papers scored (E8), but that run is the deterministic lane only, zero LLM calls. |

The live LLM lane, across every scenario in this ledger, touches at most a
handful of distinct source documents, overwhelmingly one (`p4182r0`) and its
synthetic mutations. The 381-paper fleet run that exists in this audit never
invokes the advisory lane at all.

### 3.2 A new problem: the canary base document's own provenance lock is red

`p4182r0`'s ideal file, `packages/tomd/tests/fixtures/golden/ideals/p4182r0.md`,
is the exact file the E13-E20 canary battery is built on
("Base material: golden ideal `p4182r0.md` against source `p4182r0.pdf`",
shared-evidence-ledger.md section C header). That same file is the locked
candidate for `p4182r0` in the holdout provenance manifest
(`packages/whisker/corpus/holdout/manifest.json:23-29`,
`candidate_path: "packages/tomd/tests/fixtures/golden/ideals/p4182r0.md"`,
`candidate_kind: "human_blessed_tomd_ideal"`). `test_dev_replay_schema.py`'s
`test_locked_candidate_dispositions` re-hashes that exact file and compares
it to the locked `candidate_sha256`
(`packages/whisker/tests/test_dev_replay_schema.py:190`). That assertion is
one of the three current suite failures (E1): `AssertionError: p4182r0` at
line 190, the candidate-hash check, not the source-hash check at line 189.

This means the file backing the entire live-LLM canary battery no longer
matches the hash that was locked when its human-verified anchor dispositions
(present/absent/reordered, checked against the source) were certified. The
canary results in E17/E18 are real observations against whatever is on disk
today; they are not currently backed by a passing provenance check that the
disk content matches what was independently verified. This is not a claim
that the canary results are wrong, the mutations were applied to the current
file and the LLM read the current file. It is a claim that the "this is the
paper we already know the ground truth for" assumption underneath the whole
battery is, right now, unverified by the project's own mechanism for
verifying it.

### 3.3 Sample size for the stability claim

E20's flip-rate measurement rests on 4 observations per paper across 3
papers. `CLAUDE.md:573-575` cites ">= 25% verdict-flip rate" as a historical,
un-re-measured figure; E20 reproduces a comparable number (25% for control,
50% for C2) but from a sample too small to bound a confidence interval
meaningfully. 2 flips out of 4 runs (C2) and 1 out of 4 (control) are
consistent with a wide range of true flip rates.

### 3.4 The audit's own methodology already produced one false negative

00-PRECONDITIONS.md SS2.1 records that this audit's first attempt to check
pod reachability, using `urllib` with a default user-agent, returned HTTP
403 from every real endpoint **and** from a deliberately nonexistent control
subdomain, which looked like proof of an outage. The actual cause was
Cloudflare rejecting the client signature before routing, unrelated to pod
status. The correct diagnosis required capturing the response body, not just
the status code, and switching to a browser user-agent. This is not evidence
about whisker's code; it is direct, first-party evidence that runtime
reachability checks are easy to get wrong in exactly the silent way that
would make a live system look falsely dead, in this codebase or any
auxiliary tooling written the same way.

### 3.5 Target-state caveat compounds the runtime caveat

00-PRECONDITIONS.md SS1 and SS5: the audited target is a working tree with
7205 uncommitted insertions across 44 files plus untracked whole packages,
pinned by content manifest rather than commit. "Reproducibility from a clean
clone remains impossible for this run." Combined with SS1 above, a future
reader cannot reproduce E13-E20 from git alone (no commit to check out) and
cannot re-verify that `p4182r0.md`'s content is what the holdout manifest
believes it locked (the check that would confirm this is currently failing).
The runtime evidence is real but sits on an unreproducible, provenance-broken
base.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---|---|---|
| F1 | Live LLM runtime evidence exists (E13-E20) where Auditv2 had none; this is a genuine capability upgrade | Informational | HIGH |
| F2 | Nearly all live-LLM evidence derives from one base document (`p4182r0`) on one model, one pod | High | HIGH |
| F3 | The canary battery's base document has a currently-failing provenance lock (`test_dev_replay_schema.py:190`) | High | HIGH |
| F4 | Stability sample (E20) is 4 observations per paper across 3 papers; too small to bound the flip-rate claim | Medium | HIGH |
| F5 | This audit's own preconditions work independently demonstrates that naive reachability checks produce false-outage signals | Medium | HIGH |
| F6 | The audited target is an uncommitted, manifest-pinned working tree, so E13-E20 cannot be reproduced from git alone by a future reader | Medium | HIGH |

## 5. False-Pass Hypothesis

**Could the C1 canary result (both lanes catch a 46.7% deletion) be
sufficient on its own to certify the gate has teeth, independent of the
provenance concern?** C1's result is a real, direct observation and stands
regardless of F3: a document was mutated and both lanes flagged it. What F3
undermines is not "did the mutation get caught," it is the implicit claim
"the base document, before mutation, is the well-understood, previously
human-verified ground truth everyone believes it is." That second claim is
what the holdout manifest exists to certify, and it currently does not.

**Could F2 be dismissed because deterministic coverage (E8, 381 papers) is
large?** No; E8 is explicitly the deterministic lane only, per its own
description in the ledger. It provides zero evidence about the advisory
lane's behavior across the fleet. The two coverage claims (381 papers
deterministic, ~1 paper live-LLM) answer different questions and cannot
substitute for each other.

## 6. Gate/Dimension Mapping (PROPOSED)

- **R1-R2, R5 (positive control, known defect, adversarial verdict):
  PROPOSED PASS-PROVISIONAL.** Ran and held on the available evidence; breadth
  is the open question (F2), not correctness of what ran.
- **R3-R4 (prompt injection, delimiter forgery): PROPOSED PASS-PROVISIONAL.**
  Two live probes on one document; held, but two probes cannot establish
  resistance to "sophisticated" injection per Auditv2's own bar.
- **R6-R9 (grounding failure, operational failure, tombstone path, mixed
  batch): PROPOSED PARTIAL.** S6 (nonexistent service slot, E13) exercises
  the operational-error path and exits correctly (exit 1, no verdict); S8
  exercises a 3-paper mixed batch successfully. Neither is an adversarial
  grounding-failure or forced-timeout probe; Auditv2's specific scenarios for
  those remain effectively untested.
- **R10 (readback corruption control): PROPOSED NOT RUN in this ledger's
  scope** (readback is documented but no `rt*` driver output for it appears
  in E13-E20).
- **Provenance of the canary substrate (new, no Auditv2 predecessor):
  PROPOSED FAIL-UNPROVEN.** The base document's own lock is red.

## 7. Limitations

- This report did not attempt to independently recompute `p4182r0.md`'s
  current SHA-256 against the manifest value; it relies on the pytest
  assertion (E1) as the evidence that they differ.
- No second model or second pod was available to probe cross-model
  stability; the entire live-LLM matrix is confined to whatever
  `alliance-pod` serves today.
- Whether `p3556r0`'s pinning failure (the other E1 pinning failure) touches
  any document used in the live-LLM matrix was not checked; only `p4182r0`'s
  provenance chain was traced here because it is the documented canary base.

## 8. Conclusion

Judged only on "did the scenarios run," this audit is a large improvement
over Auditv2's zero-for-ten. Judged on "is this enough evidence to treat the
numbers as settled," the honest answer is no. The breadth is narrow (one
model, one pod, effectively one base document), the stability sample is too
small to bound a flip-rate claim with any confidence, and the specific
document the entire canary argument rests on currently fails its own
provenance check. None of this means the observations are false; C1's
deletion-detection result and E16's rescue-path result are real and useful.
It means the step after this audit is not "cite these numbers" but "run them
again, wider, and fix the provenance lock first." Before anyone should treat
E13-E20 as settled: (1) resolve the `p4182r0` candidate-hash mismatch and
re-verify or re-lock the holdout manifest; (2) run the canary battery against
at least 2-3 additional base documents of different structural profile
(table-heavy, code-heavy, math-heavy); (3) increase the stability rerun count
per document well past 4 to bound a usable confidence interval; (4) probe a
second model or pod, even briefly, to distinguish "this model's behavior"
from "the architecture's behavior"; (5) commit the audited tree, or at
minimum tag it, so a future reader can reproduce the base state without
trusting a manifest file.

## 9. Delta vs Auditv2

Auditv2's `code-c27-runtime-meta-review.md` found all ten runtime scenarios
BLOCKED, root-caused to a single missing credential, and concluded "the
blocked runtime matrix is an evidence gap, not a finding of deficiency,"
recommending that once credentials became available, "all 10 scenarios can
be run in a single session to close all gaps simultaneously." Auditv3 did
exactly that: the pod is live, and most scenarios have at least one
observation.

But running the scenarios did not close the gaps the way Auditv2 implicitly
assumed it would. Auditv2 treated "blocked" and "run" as the only two states
worth distinguishing; this report's contribution is showing that "run" is not
the same as "sufficient," and that running the scenarios narrowly surfaced a
new, more specific problem Auditv2 had no way to anticipate: the substrate
document for the canary evidence has a broken provenance lock, discoverable
only once someone actually tried to run the live battery and cross-checked
its base file against the rest of the test suite. Auditv2's recommendation
("run them in a single session") turned out to be necessary but not
sufficient; this report's recommendation is narrower and harder: fix the
provenance lock, then widen the sample before drawing conclusions from it.
