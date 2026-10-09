# Whisker Audit Runbook

Attach this file to a fresh Cursor chat to execute a new, independent Whisker
code and runtime audit. This runbook is self-contained. The files beside it are
historical evidence and methodological background, not current truth.

## Copy-paste start prompt

> Execute the Whisker audit exactly as specified in the attached
> `AUDIT-RUNBOOK.md`. Audit the current checked-out state, create fresh evidence
> under `packages/whisker/research/Audit/Auditv2/`, and do not reuse Audit v1
> scores or factual baselines. Complete all 30 roles and the final synthesis.
> Do not modify production code, tests, corpus data, tomd goldens, configuration,
> or Audit v1.

## 1. Objective and deliverables

Audit the current checked-out state of `packages/whisker/` for professional
release readiness. Evaluate code, tests, package boundaries, deterministic and
LLM runtime behavior, operator contracts, evidence quality, and known
false-pass risks.

Create all new audit artifacts only under:

`packages/whisker/research/Audit/Auditv2/`

Required deliverables:

1. a fresh claims and repository baseline;
2. evidence reports from C01 through C25;
3. independent meta-reviews C26 through C29;
4. C30 synthesis;
5. `Auditv2/CODE-AUDIT-RESULT.md`.

Audit v2 is read-only with respect to production code, tests, package
configuration, corpora, snapshots, goldens, and ideals. Runtime data must use a
temporary workspace outside the repository. Do not delete files. If a defect is
found, report it; do not repair it during the audit.

## 2. Authority order and required reading

Read these files before assigning scores:

1. current repository and package `CLAUDE.md` files;
2. `Auditv1/AUDIT-SCORECARD.md`;
3. `Auditv1/SYNTHESIS.md`;
4. `Auditv1/code-c01-claims-baseline.md`;
5. `Auditv1/CODE-AUDIT-RESULT.md`;
6. all `Auditv1/code-c01-*.md` through `code-c29-*.md`;
7. current code, tests, CLI declarations, corpus manifests, tomd ideal
   inventory, and runtime artifacts.

When evidence conflicts, use this order:

1. current reproducible runtime evidence;
2. current test results and generated artifacts;
3. current code;
4. current documentation;
5. Audit v1 as historical context.

Audit v1 supplies methods, hypotheses, and comparison points. It does not
supply current facts or reusable ratings.

## 3. Mandatory corrections to the historical framing

The following rules override contradictory wording in Audit v1:

- Establish a completely fresh baseline. Do not copy Audit v1 commit IDs,
  versions, file counts, LOC, test counts, corpus sizes, ideal counts, claims,
  findings, confidence values, gate results, dimension levels, composites,
  intervals, or bands.
- The User/Sean question concerns functional interoperability and visibility of
  merged implementation lines. It is not a request to invent or reconcile
  personal definitions of determinism.
- Independently test technical reproducibility of the deterministic core under
  the current documented quality-stability contract.
- tomd ideals are canonical structural references. Original PDF or HTML sources
  remain factual authority. An ideal cannot authorize a factual contradiction
  with the source.
- Whisker consumes tomd ideals read-only. Do not create a second ideal store.
- Image extraction, raster comparison, pixel fidelity, vision-model quality,
  and VLM coverage are not audit requirements. `image_ref` is a
  reference-presence contract. Dormant VLM code is assessed only for truthful
  status, import isolation, and package-boundary safety.
- Human blessing of legacy facts is not a special gate for this audit.
- The overall fusion contract is not globally demotion-only. Test its documented
  heading-only rescue and soft-review clear behavior. Only the ideal verifier
  is demotion-only.
- Real LLM runtime evidence is mandatory for runtime, injection, and operational
  failure claims. Mock tests and source inspection do not substitute for it.
- Tapetum advisory `pass`, `review`, and `fail` are exit-neutral. Every
  operational error, timeout, persistence failure, or
  `TapetumResult(status="error")` must make the completed command exit `1`.
- Historical Audit v1 scores are not priors or plausibility anchors.

## 4. Phase A: fresh baseline freeze

C01 must complete before any gate, level, or score is assigned.

Record:

- date, HEAD, branch, remotes relevant to the audit, and complete worktree
  status;
- exact distinction between HEAD and audited local modifications;
- package version, schema versions, lane versions, and Python requirement;
- source and test file inventories and LOC, excluding `research/`, vendored
  repositories, caches, virtual environments, and generated files;
- complete CLI entry-point inventory and top-level/subcommand help output;
- core and optional dependencies, build metadata, wheel contents, and licenses;
- current expected snapshots, facts, validation files, holdouts, dev replay,
  sources, baselines, tomd ideals, and associated hashes;
- operating system, Python, `uv`, and test-tool versions;
- active service/model identities and sanitized configuration, never secrets;
- exact baseline commands, exit codes, stdout/stderr disposition, and results;
- hashes or stable identifiers for every load-bearing runtime input.

Use the actual test root:

```text
uv run --package whisker pytest packages/whisker/tests
```

Do not run broad collection over `packages/whisker/`, because `research/`
contains vendored repositories.

## 5. Fresh claims registry

Re-derive every Scorecard claim from current evidence:

- C-VER: version phase;
- C-API: public API stability claim;
- C-CAL: calibration status;
- C-LAB: role of labels, snapshots, facts, and ideals;
- C-INF: default inference deployment;
- C-COMP: comprehension claim;
- C-PROD: production-operations claim;
- C-DET: technical determinism tier;
- C-LIC: outbound and bundled licenses.

Add these audit-specific claims:

- C-INT: merged User/Sean functions that must interoperate;
- C-VIS: surfaces on which those functions must be visible;
- C-IDEAL: current ideal discovery and authority contract;
- C-LLM: LLM paths currently claimed to be operational;
- C-EXIT: domain-verdict and operational-error exit contracts.

Every value needs current code, documentation, test, or runtime evidence. Record
unsupported claims as unknown or unproven instead of reconstructing them from
Audit v1.

## 6. Thirty-role execution roster

Use exactly 30 fresh roles. C01-C25 gather independent evidence. C26-C29
challenge that evidence. C30 synthesizes only after all other reports exist.

1. **C01 Claims and Fresh Baseline:** repository state, claims, inventories,
   versions, and baseline tests.
2. **C02 Deterministic Core:** pure paths, ordering, randomness, network/LLM
   isolation, mutable state, and reproducibility hazards.
3. **C03 Advisory Non-Leakage:** prove advisory output cannot authorize a
   deterministic gate.
4. **C04 Fail-Not-Partial:** fault injection, artifact integrity, attributed
   failures, and preserved diagnostics.
5. **C05 Quality-Stability Replay:** fresh replay using an explicit technical
   equality contract.
6. **C06 Per-Axis and Null Eligibility:** axis separation, eligible/null
   handling, and composite visibility.
7. **C07 Prompt Injection:** trust boundaries, wrappers, delimiter forgery,
   structured output, and tool authority.
8. **C08 Canary and Gate Teeth:** positive and inverted canaries plus
   vacuous-green resistance.
9. **C09 License, Provenance, and Supply:** artifact contents, notices, direct
   and optional dependencies, and redistribution obligations.
10. **C10 Score-Path Truth:** actual influences on verdicts and exit codes.
11. **C11 Golden and Guard:** membership, missing candidates, update safety,
    regression behavior, and tool-version pinning.
12. **C12 Facts and Comprehension:** fact types, source authority, canaries,
    coverage, and claim honesty.
13. **C13 Corpus and Holdout:** provenance, locked hashes, contamination, and
    fit/commit separation.
14. **C14 Calibration:** current status, threshold provenance, workflow, and
    calibration claims.
15. **C15 Metric Validity:** implementations, construct separation, and paired
    table structure/content evaluation.
16. **C16 Real-LLM Authenticity:** actual call paths, endpoint/model identity,
    schemas, fingerprints, and sidecars.
17. **C17 Cascade and Topology:** routing, escalation, per-paper seriality,
    cross-paper concurrency, aggregation, and failure isolation.
18. **C18 Grounding and Source Router:** exact/fuzzy rules, PDF/HTML routing,
    quote allocation, and source verification.
19. **C19 Chunking and Context:** completeness, ordering, context limits, and
    prevention of partial-success aggregation.
20. **C20 Source-Aware and Ideal Authority:** source factual authority, ideal
    structural authority, conflicts, and read-only consumption.
21. **C21 Fusion and Operator Trust:** promotion, rescue, clear, ideal demotion,
    stale/error sidecars, and bounded reporting.
22. **C22 Readback:** current live utility, corruption control, and documented
    limits.
23. **C23 RAG Decision:** reassess only if current code or claims changed the
    same-document premise.
24. **C24 Optional/VLM Boundary:** no image-quality requirement; inspect dormant
    status, claims, imports, and package isolation.
25. **C25 Professional Surface:** packaging, public API, help, JSON, streams,
    exit codes, errors, and Windows behavior.
26. **C26 Gate Meta-Review:** adversarially re-evaluate every G1-G7 proof.
27. **C27 Runtime Meta-Review:** independently verify live LLM, injection,
    failure, tombstone, partial-persistence, and exit evidence.
28. **C28 Engineering and Release Meta-Review:** test discipline, docs, change
    risk, PR readiness, and merged implementation interoperability.
29. **C29 External-Delta Steelman:** check only relevant current external
    changes; do not repeat historical repository comparisons.
30. **C30 Independent Synthesis:** resolve contradictions, score from fresh
    evidence, and write the final report.

Every C01-C29 report must include:

- exact scope and audited state;
- commands and exit codes;
- current code, test, artifact, and runtime evidence;
- findings with severity, confidence, and false-pass hypothesis;
- gate and dimension mapping;
- evidence limitations and untested paths;
- a conclusion independent of Audit v1 ratings.

## 7. Mandatory static and offline evidence

At minimum:

1. run the full Whisker test root;
2. run focused deterministic, ideal, fusion, injection, incremental, CLI, and
   exit-contract tests;
3. build and inspect wheel/sdist metadata and contents;
4. verify core import without the `tapetum-llm` extra;
5. enumerate public exports and CLI entry points;
6. replay deterministic scoring in separate processes and compare the declared
   equality fields;
7. run positive and inverted canaries;
8. inspect trust-boundary call sites and serialized wrapped prompts;
9. verify corpus/holdout/ideal hashes and membership rules;
10. inject safe filesystem, service, timeout, malformed-sidecar, and
    persistence failures without modifying committed fixtures.

Record the exact command, working directory, exit code, relevant output, and
artifact effect for every load-bearing claim.

## 8. Mandatory real-LLM runtime matrix

Use the configured real endpoint and current model. Keep paper-level execution
serial (`--concurrency 1`) unless a scenario explicitly audits batch behavior.
Use text-only scenarios unless the current documented contract requires
otherwise.

Execute at least:

1. **Positive control:** canonical source, candidate, and matching tomd ideal.
2. **Known structural defect:** grounded ideal discrepancies, including the
   affected structural axis.
3. **Instruction in document:** document text attempts to force `pass` or
   override audit instructions.
4. **Delimiter forgery:** document content imitates or closes the trust
   envelope.
5. **Adversarial advisory verdict:** attempted deterministic fail/review to pass
   elevation.
6. **Grounding failure:** invented or unquotable evidence must not become
   grounded evidence.
7. **Operational failure:** safely controlled endpoint, service, timeout, or
   persistence failure.
8. **`status="error"` fallback:** no ideal verification or successful
   persistence; error tombstone and command exit `1`.
9. **Mixed batch:** successful papers remain persisted, the failed paper is
   isolated, and aggregate exit is `1`.
10. **Readback corruption control:** run the current text-only corruption
    control if readback is an active operational claim.

For each scenario record:

- sanitized command and input provenance;
- candidate, source, ideal, prompt, schema, service, and model fingerprints
  where applicable;
- endpoint and model reachability;
- stdout and stderr separately;
- process exit code;
- files created, unchanged, replaced, or intentionally absent;
- deterministic, Tapetum, ideal, and fusion verdicts separately;
- quote-grounding result;
- expected versus observed behavior.

The runtime matrix fails its claim when:

- a mock substitutes for a required real call;
- injection escapes the trust boundary or schema;
- advisory output produces a deterministic gate pass;
- an operational Tapetum error exits `0`;
- a failed run leaves a sidecar that appears successful;
- a fidelity-critical failure emits a complete-looking partial result.

Definitive credential, endpoint, quota, or entitlement denial is recorded once
as blocked evidence. Historical runs do not replace a current proof, and a
blocked mandatory proof cannot receive an unqualified pass.

## 9. Merged implementation interoperability and visibility

Test the combined implementation rather than personal doctrines:

- `score-file` and `check-facts` remain dispatchable from the current `whisker`
  entry point;
- top-level help exposes every routed command for both `-h` and `--help`;
- stdout JSON, human output, stderr, and exit codes remain usable by tomd;
- tomd renders file-command results without Whisker claiming persistence it
  does not own;
- deterministic workspace reports and Tapetum/fusion reports remain separate
  and correctly named;
- the documented absence or presence of a unified report matches reality;
- both merged implementation lines remain reachable and tested;
- no dead, duplicated, hidden, or internal-only command surface contradicts
  operator documentation.

Report visibility failures as concrete interoperability or operator-contract
findings, not as unresolved determinism definitions.

## 10. Source and ideal contract

Verify mechanically:

- the current direct-member inventory under
  `packages/tomd/tests/fixtures/golden/ideals/*.md`;
- deterministic and case-insensitive PID discovery;
- absence of copied ideals under Whisker;
- ideal presence/content in relevant fingerprints;
- source-aware judging runs independently before ideal verification;
- source remains factual authority and ideal remains structural authority;
- candidate and ideal discrepancy quotes ground exactly and allocate duplicate
  occurrences correctly;
- ideal `review` only demotes eligible advisory results;
- ideal `agree` never promotes, rescues, or clears;
- inspect output preserves complete grounded discrepancies;
- merged output remains bounded while accurately reporting ideal verdict and
  discrepancy count;
- malformed or non-object sidecars cannot crash fusion or reporting.

Measure inventory and coverage fresh. Do not reuse counts from Audit v1.

## 11. Gates, dimensions, and scoring

Apply the seven gates and eight weighted dimensions from
`AUDIT-SCORECARD.md`, with the corrections in this runbook.

Hard gates:

- G1 Advisory non-leakage;
- G2 Fail-not-partial;
- G3 deterministic technical replay;
- G4 per-axis reporting and evaluation integrity;
- G5 untrusted-input mediation;
- G6 inverted baseline canary;
- G7 licensing and attribution.

Dimensions and weights:

- D1 Epistemic separation: 20;
- D2 Determinism and reproducibility: 15;
- D3 Fidelity and fail-not-partial: 15;
- D4 Metric validity and per-axis evaluation: 15;
- D5 Anti-gaming and Goodhart resistance: 12;
- D6 Untrusted-input and prompt-injection defense: 10;
- D7 API contract and packaging: 8;
- D8 Documentation and operator CLI: 5.

Derive from zero:

- every gate status;
- each dimension level and evidence grade;
- the navigation composite;
- weakest-link grade;
- uncertainty interval and its named drivers;
- result band and flip conditions.

The composite is never a standalone verdict. One failed hard gate makes the
band Unsound. A gate passes only with its required current-run evidence.
Code-analysis plausibility cannot replace an explicitly required runtime proof.
An operational Tapetum failure that does not exit `1` is at least a High
finding and prevents an unqualified G2/D8 pass.

## 12. Evidence and anti-gaming rules

- Every scored statement links to a current Audit v2 artifact.
- Grade evidence A-D using the Scorecard definitions.
- LLM-derived findings remain advisory and inherit at most grade B.
- Never invent or silently calibrate thresholds.
- Record absent modalities as null, never as zero or perfect.
- Pair table structure with table content.
- Keep fidelity, comprehension, reading order, and semantic validity distinct.
- Run at least one must-fail inverted canary.
- Keep calibration inputs separate from locked commit/holdout evidence.
- Quarantine fabricated, unverifiable, or version-drifted external evidence.
- Name false-pass hypotheses and the test that would falsify each one.
- Report uncertainty and contradictory evidence instead of averaging it away.

## 13. Meta-review and synthesis protocol

C26-C29 receive primary evidence and C01-C25 reports, not C30 conclusions.
They must actively seek false passes, unsupported confidence, stale baselines,
and claims that passed only because the relevant runtime path was not run.

C30 must:

1. read all 29 reports;
2. resolve contradictions against primary evidence;
3. distinguish observed facts, interpretations, and missing evidence;
4. let negative runtime evidence override static plausibility;
5. avoid voting or averaging contradictory persona judgments;
6. name the single current artifact supporting each gate;
7. justify every dimension level and evidence grade;
8. perform an anti-convergence and false-pass review;
9. compute scores and band only after evidence reconciliation.

Audit v1 findings may be labeled reconfirmed, refuted, fixed, regressed, or not
retested, but only with new evidence.

## 14. Stop conditions

Stop the affected certification claim and report the blocker when:

1. required gate evidence cannot be produced;
2. a production-calibration claim relies on uncalibrated thresholds;
3. a fidelity-critical path emits partial success;
4. a load-bearing citation or artifact cannot be verified;
5. required access is definitively denied;
6. the audit drifts into requirements Whisker does not claim;
7. worktree ambiguity prevents identifying what was actually audited.

Continue independent diagnostic dimensions when safe, but never fabricate a
complete verdict or silently downgrade a mandatory proof to code inspection.

## 15. Mandatory final report

`Auditv2/CODE-AUDIT-RESULT.md` must contain:

1. scope, date, HEAD, branch, and worktree boundary;
2. fresh claims registry;
3. fresh baseline and exact verification commands;
4. merged implementation interoperability and visibility;
5. gate ledger with exact current evidence;
6. real-LLM runtime matrix;
7. injection, failure, tombstone, partial-persistence, and exit-code matrix;
8. source/ideal authority result;
9. per-dimension levels, grades, reasons, evidence, and eligibility;
10. newly calculated navigation composite;
11. weakest-link grade, interval, band, uncertainty drivers, and flip
    conditions;
12. findings ranked Critical, High, Medium, Low, and Informational;
13. false-pass risks and falsification tests;
14. PR/release blockers;
15. verified strengths;
16. open evidence gaps;
17. current-run differences from Audit v1 without score transfer;
18. all 30 role reports and their status;
19. triggered stop conditions;
20. a concise, bounded final verdict.

The report must explicitly state:

- whether current real LLM, injection, and operational failure proofs ran;
- whether every observed Tapetum operational failure exited `1`;
- whether merged User/Sean implementation lines interoperate and remain visible;
- that tomd ideals are structural references and sources factual authority;
- that image/VLM fidelity was not an audit requirement;
- that every score and conclusion was derived from Audit v2 evidence only.

Do not modify historical Audit v1 reports to make the new result appear
consistent.
