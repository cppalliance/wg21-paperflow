# P25 — Observability, Tracing & Failure-Handling Researcher

**Persona:** 25 (Cluster G). **Date:** 2026-07-18. **Scope:** External method and bar only. No whisker production-code inspection, no whisker verdict.

---

## 1. Question restated

What external bar should a **document QA / batch analytical pipeline** meet for **observability and failure handling**: structured logging (not ad-hoc stdout), a deliberate **trace vs debug** artifact split (concise progress vs full-fidelity I/O), **fail-closed / fail-not-partial** behavior when fidelity cannot be guaranteed, actionable error surfacing, and **fault-injection** validation that those behaviors hold under injected faults?

This persona researches *how to audit* those properties and *what mature systems do*, not whether any specific package satisfies them.

---

## 2. Proposed audit criteria

Each criterion lists: **how to measure**, **audit-method** (from `00-FRAME.md` §5), **scoring-design hook** (§6), **gaming vector + anti-gaming guard**, **evidence grade**, and **Tier 1–2 sources**.

### Criterion O1 — Structured logging with stable schema (no `print()` in library paths)

**Bar:** Production pipeline code emits logs through a hierarchical logger with a **stable, machine-parseable schema** (typed fields, consistent keys), not unstructured stdout or ad-hoc `print()`. Human-readable message text is supplementary; queryable attributes carry operational facts (paper/run ID, stage, severity, outcome).

**How to measure:** Conformance checklist on a representative run artifact set: (a) every pipeline stage emits at least one log record with named fields retrievable without regex; (b) severity uses a fixed enum aligned to purpose (INFO = progress, DEBUG/TRACE = diagnostic detail); (c) zero library-path `print()` / stderr progress conflated with result channel. Spot-check mapping against OpenTelemetry log severity bands (INFO 9–12, DEBUG 5–8, TRACE 1–4).

**Audit-method:** Conformance checklist (#1); Observability / fault-injection audit (#11).

**Scoring-design hook:** Feeds §6.1 dimension *observability/failure*; candidate §6.2 gate if library code uses `print()` for operational telemetry (violates operator contract).

**Gaming vector:** Emit one JSON line at startup while rest of pipeline prints freely.

**Anti-gaming guard:** Require per-stage sampled records with mandatory correlation keys (run ID, stage name) and severity-appropriate volume (progress at INFO, I/O dumps only at DEBUG/TRACE).

**Evidence grade:** A (multiple Tier-1 converging: OpenTelemetry Logs Data Model, Python logging HOWTO, OTel structured-log guidance).

**Sources:** OpenTelemetry Logs Data Model (Stable, 2024+); OpenTelemetry Logs concepts; Python 3 Logging HOWTO (docs.python.org, 2026).

---

### Criterion O2 — Trace context correlation across stages

**Bar:** Log records that belong to one logical run share **TraceId / SpanId** (or equivalent run-scoped correlation ID propagated through all stages). Operators can pivot from a failure symptom to the same run’s earlier stages without guessing.

**How to measure:** Run a multi-stage pipeline once; verify ≥95% of stage-boundary records share one correlation identifier. Attempt cross-signal join: given an ERROR record, retrieve all records for that run in time order without manual ID hunting.

**Audit-method:** Observability / fault-injection audit (#11); Reproducibility replay (#8) when correlating reruns.

**Scoring-design hook:** §6.1 sub-criterion; supports §6.3 evidence grade propagation (missing correlation lowers confidence on failure diagnosis).

**Gaming vector:** Set correlation ID only on the final error line.

**Anti-gaming guard:** Automated check that *every* stage transition record includes the ID; fail if any stage omits it.

**Evidence grade:** A (OpenTelemetry log data model mandates TraceId/SpanId fields; trace semantic conventions define span boundaries).

**Sources:** OpenTelemetry Logs Data Model — Trace Context Fields; OpenTelemetry Trace Semantic Conventions (general/trace).

---

### Criterion O3 — Trace artifact vs debug artifact separation (concise progress vs full-fidelity I/O)

**Bar:** The system maintains **two deliberate observability tiers**:

| Tier | Purpose | Content contract |
|------|---------|------------------|
| **Trace / progress** | Answer “did it run, in what order, with what shape?” | Per-step headings, counts, truncated samples, every state field written to pipeline state; **no silent steps**; bounded size suitable for human scan |
| **Debug** | Answer “what exactly did each LLM/tool see and return?” | Append-only, **untruncated** request/response pairs per call identity; ground truth for model-behavior diagnosis |

Trace is not a summary of debug with secrets stripped unless redaction policy is documented. Debug is not required for normal operator success; trace is.

**How to measure:** (1) Execute a run with `--trace` and `--debug` (or equivalent flags). (2) Confirm trace size grows ~linearly with step count, not with prompt token count. (3) Confirm debug entry for a chosen LLM call contains full structured I/O matching what the step consumed/produced. (4) Confirm a step that writes pipeline state but produces “nothing visible” still appears in trace with an explicit empty marker.

**Audit-method:** Documentation-completeness audit (#9) for artifact contract; Observability / fault-injection audit (#11).

**Scoring-design hook:** §6.1; strong candidate §6.2 gate for QA tools: emitting a “complete” user-facing result without a trace that proves all executed steps ran.

**Gaming vector:** Dump everything into trace at INFO, claim debug exists but cap at 200 chars; or write verbose prose trace that omits state fields.

**Anti-gaming guard:** Schema checklist: trace must list every pipeline-state mutation key; debug must pass byte-for-byte or structured-equality check on one injected canned call; trace must fail review if median line length exceeds a declared bound while debug is empty.

**Evidence grade:** B (pattern assembled from OTel severity separation + SRE symptom/cause split + Great Expectations result-format tiers; no single standard names “trace vs debug files,” but converging practice).

**Sources:** OpenTelemetry Logs Data Model — SeverityNumber bands; Google SRE Book Ch.6 — symptoms vs causes, golden signals for paging vs logs for root cause; Great Expectations `result_format` levels (BOOLEAN_ONLY → COMPLETE); SRE Workbook Ch.4 — metrics/structured logging for ops vs deeper investigation.

**Contradiction surfaced:** SRE also recommends **graceful degradation** under overload (serve degraded results rather than fail). For **QA/fidelity pipelines**, OWASP fail-closed and data-integrity practice invert that default: a partial QA verdict is worse than no verdict. The audit must classify the tool as *fidelity-first* (fail-not-partial) vs *availability-first* (degraded mode documented and never used for gate outputs).

---

### Criterion O4 — Fail-closed / fail-not-partial on fidelity-critical paths

**Bar:** When any **fidelity-critical** stage fails (LLM unreachable, schema validation exhausted, critical dependency timeout, unrecoverable parse error), the pipeline **stops**, returns a **clear error** (not exit 0), and **does not emit** a result mistakable for a complete QA outcome. No silent skip of gates, no “best effort” partial report without explicit incomplete marking (and for gate tools, incomplete marking is still a fail).

**How to measure:** Fault-injection battery (see O7): for each critical failure mode, assert (a) non-zero exit or explicit failed status, (b) no golden/output artifact updated, (c) error message names failing stage, (d) debug transcript preserved for post-mortem.

**Audit-method:** Observability / fault-injection audit (#11); Adversarial probing (#6) for “success with hollow output.”

**Scoring-design hook:** §6.2 **hard gate** (non-compensatory): partial QA output on failure is an automatic audit fail regardless of weighted score.

**Gaming vector:** Catch exceptions, log a warning, write an empty but schema-valid result; return exit 0.

**Anti-gaming guard:** Canary fault tests must fail the run; CI asserts artifact absence + exit code; review catch blocks for broad `except` that return success-shaped payloads.

**Evidence grade:** A (OWASP RAG Security §14 fail-closed; OWASP §12 pipeline observability ties failure visibility to stage identity).

**Sources:** OWASP Cheat Sheet — RAG Security §12 (Monitoring), §14 (Fail-Closed Design); Google SRE Book Ch.22 — fail early and cheaply under overload (contrasted above for QA domain).

---

### Criterion O5 — Differentiated error surfacing (retriable vs permanent, stage-attributed)

**Bar:** Errors expose: **stage name**, **failure class** (transient retriable vs permanent), **stable error code or type**, and **action hint** (retry, fix input, check service). Exception records use structured fields (`exception.type`, `exception.message`, stack where safe), not only a prose string. Artificial/control-flow exceptions (e.g., HTTP 404 as exception rather than status) should not pollute ERROR severity per OTel exception guidance.

**How to measure:** Review error paths under injected faults; score pass if ≥90% of failure modes include stage attribution and if retryable errors are distinguishable without reading stack traces. Map records to OpenTelemetry exception semantic conventions.

**Audit-method:** Conformance checklist (#1); Observability / fault-injection audit (#11).

**Scoring-design hook:** §6.1; feeds §6.4 anti-gaming (generic “Error occurred” fails criterion).

**Gaming vector:** Single generic error string for all failures.

**Anti-gaming guard:** Table-driven fault injection with expected error codes per fault; fail if two distinct faults produce identical surface messages.

**Evidence grade:** A (OpenTelemetry Semantic Conventions for Exceptions in Logs, Stable).

**Sources:** OpenTelemetry — Semantic conventions for exceptions in logs; Google SRE Book Ch.22 — separate retriable vs non-retriable error conditions.

---

### Criterion O6 — Real-time progress telemetry for long batch runs

**Bar:** For runs whose wall time exceeds a declared threshold (e.g., minutes), operators receive **incremental progress signals** during execution, not only post-completion metrics. Periodic/batch pipelines that report metrics only on job completion leave operators blind during failures (Google SRE Ch.25).

**How to measure:** Start a run known to exceed threshold; verify progress events arrive before final completion with monotonic step counters or heartbeat timestamps. Simulate mid-run kill; confirm partial progress is reconstructable from artifacts/logs.

**Audit-method:** Maturity-model scoring (#2) levels 0–4 on progress visibility; Observability audit (#11).

**Scoring-design hook:** §6.1 sub-criterion for operator UX overlap; §6.6 uncertainty if only tested on fast fixtures.

**Gaming vector:** Log “Starting…” and “Done” only.

**Anti-gaming guard:** Require N≥3 intermediate progress events for pipelines with ≥3 steps on a throttled fixture.

**Evidence grade:** B (SRE Book Ch.25 — monitoring problems in periodic pipelines; continuous pipelines expose real-time metrics by design).

**Sources:** Google SRE Book Ch.25 — Monitoring Problems in Periodic Pipelines; SRE Workbook Ch.4 — freshness of monitoring data for incident response.

---

### Criterion O7 — Fault-injection / chaos-style validation of failure behavior

**Bar:** The project maintains an **automated fault-injection suite** (CI or scheduled) that: defines steady-state success metrics; injects realistic faults (dependency down, slow LLM, malformed intermediate, disk full on debug writer); hypothesizes fail-closed behavior; and **detects regression** when failure handling weakens. Experiments have bounded blast radius and automatic stop conditions.

**How to measure:** Enumerate ≥5 fault scenarios with documented expected outcomes. Run suite in CI; require pass. Map to Chaos Engineering four-step loop (steady state → hypothesis → inject → compare).

**Audit-method:** Observability / fault-injection audit (#11); Adversarial / red-team probing (#6) for failure modes.

**Scoring-design hook:** §6.2 gate candidate: no fault-injection tests for fidelity-critical paths = fail; §6.4 anti-gaming (tests that only cover happy path).

**Gaming vector:** Tests that mock failures but never assert on output artifacts or exit codes.

**Anti-gaming guard:** Each test must assert **negative** outcome (no complete result file, non-zero exit) and **positive** observability outcome (error record + preserved debug).

**Evidence grade:** A (Principles of Chaos Engineering; Google SRE Ch.22 Testing for Cascading Failures).

**Sources:** Principles of Chaos Engineering (principlesofchaos.org, last update 2019-03); Google SRE Book Ch.22 — Testing for Cascading Failures (load/fault tests until failure, blackhole backends).

---

### Criterion O8 — Load/overload failure mode discipline (no death-spiral partial commits)

**Bar:** Under overload, components **fail early** with explicit rejection rather than hang, retry-storm, or commit partial state that downstream treats as complete. Retry policy uses backoff; synchronized retries are avoided. Documented behavior when saturation occurs.

**How to measure:** Load test until breaking point (SRE Ch.22); observe whether system rejects new work while preserving in-flight integrity; verify no “hanging chunk” silent stall without telemetry (SRE Ch.25).

**Audit-method:** Observability / fault-injection audit (#11); Comparative benchmarking (#3) against SRE overload patterns.

**Scoring-design hook:** §6.1; §6.6 sensitivity note when only tested at small corpus scale.

**Gaming vector:** Infinite retry without deadline on failed stage.

**Anti-gaming guard:** Inject slow dependency with timeout; assert bounded wall time and fail-not-partial outcome.

**Evidence grade:** A (Google SRE Book Ch.21–22 overload and cascading failure guidance).

**Sources:** Google SRE Book Ch.22 — Addressing Cascading Failures; Ch.25 — hanging chunk / restart-without-checkpoint problem.

---

### Criterion O9 — Observability supports security/compliance reconstruction (stage-level audit trail)

**Bar:** For pipelines processing untrusted or governed content, observability must support **reconstructing which inputs influenced which outputs** at stage granularity (document/chunk IDs, tool calls, model invocations), aligned with OWASP RAG §12 “full pipeline” logging for incident response. Redaction policy documented; no black-box “answer in, verdict out.”

**How to measure:** Given a canned run, independent reviewer traces output verdict to stored stage artifacts within one correlation ID. Checklist from OWASP §12 Do/Don’t.

**Audit-method:** Conformance checklist (#1) against OWASP; Documentation-completeness (#9).

**Scoring-design hook:** §6.1; intersects security dimension weighting; §6.3 grade drops if trace lacks stage inputs.

**Gaming vector:** Log verdict only; store inputs ephemerally.

**Anti-gaming guard:** Incident-reconstruction drill: provide trace + debug, ask reviewer to name retrieved/analyzed segments without reading source code.

**Evidence grade:** A (OWASP RAG Security §12, Tier 1 OWASP Cheat Sheet Series).

**Sources:** OWASP Cheat Sheet — RAG Security §12 Monitoring and Incident Response.

---

### Criterion O10 — Anti-Goodhart: observability criteria resist cosmetic compliance

**Bar:** Observability maturity is not satisfied by “has logging” or “has --debug flag” alone. Criteria require **proven behavior under fault** (O7), **artifact separation** (O3), and **fail-not-partial** (O4).

**How to measure:** Apply §6.4 checklist: for each O1–O9, confirm stated gaming vector is closed by anti-gaming guard in CI or audit script.

**Audit-method:** Anti-gaming / Goodhart stress (#7).

**Scoring-design hook:** §6.4 master rule for observability dimension.

**Gaming vector:** Empty debug file created on every run; trace copied from template.

**Anti-gaming guard:** Randomized fault injection seed per CI run; hash debug content against live call count.

**Evidence grade:** B (assembled from FRAME §6.4 + chaos/SRE evidentiary practice).

**Sources:** `00-FRAME.md` §6.4; Principles of Chaos Engineering — steady-state hypothesis disproof.

---

## 3. External benchmark / exemplar bar

**Composite bar (professional QA pipeline):**

| Maturity | Structured logging | Trace / debug | Failure handling | Fault injection |
|----------|-------------------|---------------|------------------|-----------------|
| **0** | stdout/print | none | silent partial success | none |
| **1** | text logs | single verbose log | some errors surfaced | manual only |
| **2** | leveled logging | combined file | fail sometimes | ad-hoc scripts |
| **3** | schema-stable logs + correlation IDs | separate trace + debug contracts | fail-closed on critical paths | ≥5 automated faults in CI |
| **4** | OTel-aligned fields + span correlation | trace proves state coverage; debug replayable | fail-not-partial + attributed errors + overload discipline | chaos-style continuous experiments with blast-radius controls |

**Exemplar practices (external, not whisker):**

- **OpenTelemetry:** Logs as first-class signal with TraceId/SpanId, SeverityNumber bands separating operational progress from diagnostic depth, exception attributes on ERROR/WARN records.
- **Google SRE:** Golden signals for symptom alerting; logs/traces for cause analysis; batch pipelines need **in-run** telemetry; test until failure to learn overload behavior; prefer fail-early over hang-and-partial-commit.
- **Principles of Chaos Engineering:** Steady-state metrics, controlled fault variables, automated continuous experiments, minimized blast radius.
- **OWASP RAG Security:** Full-stage pipeline logging for reconstruction; **fail-closed** at every stage when controls fail; never silent degradation on security/fidelity paths.
- **Great Expectations:** Explicit **result_format** fidelity tiers (summary vs COMPLETE debug) — analog for separating operator summary from engineer-grade validation detail.
- **Python logging (stdlib):** Library code uses `logging`, not `print()`, for operational events; hierarchical loggers for stage namespaces.

**Domain tension (must not hide):** SRE *graceful degradation* and *serve degraded results* apply to **user-facing availability**. Document **QA / analytical fidelity** tools should adopt **fail-not-partial** (OWASP fail-closed, data-integrity framing) for gate outputs. An audit rubric must tag which subpaths are allowed to degrade (e.g., optional advisory LLM) vs which must fail closed (deterministic gate).

---

## 4. Recommended weight & gate recommendations

**Dimension weight (observability/failure):** Recommend **8–12%** of composite weighted score — material but not drowning packaging/docs. Rationale: without observability, other dimensions cannot be audited reproducibly; SRE and OWASP treat pipeline visibility as prerequisite for incident response and compliance. Exact number deferred to Opus synthesis with other personas.

**Hard gates (conjunctive, §6.2):**

| Gate | Criterion | Rationale |
|------|-----------|-----------|
| **G-OBS-1** | O4 Fail-not-partial on fidelity path | Partial QA verdict destroys trust; OWASP fail-closed; non-compensatory |
| **G-OBS-2** | O3 Trace proves all executed steps / state writes | Silent steps = unauditable gate; anti-Goodhart |
| **G-OBS-3** | O7 Automated fault-injection suite ≥5 scenarios with negative assertions | Happy-path-only testing structurally cannot prove failure handling |
| **G-OBS-4** | O1 No library `print()` for operational telemetry | Operator contract / structured observability baseline |

**Not a hard gate (weighted only):** O6 real-time progress (important for long runs but scale-dependent); O8 overload testing (may be maturity-level 3+ requirement).

**Confidence band driver (§6.6):** Contested application of graceful degradation vs fail-not-partial widens score band until domain classification (fidelity-first vs availability-first) is explicit in docs.

---

## 5. Sources

Tier labels per `00-FRAME.md` §4. All URLs stable as of 2026-07-18.

| Tier | Source | Version / date | URL |
|------|--------|----------------|-----|
| **1** | OpenTelemetry — Logs Data Model | Status: **Stable** | https://opentelemetry.io/docs/specs/otel/logs/data-model/ |
| **1** | OpenTelemetry — Logs (concepts) | Current | https://opentelemetry.io/docs/concepts/signals/logs |
| **1** | OpenTelemetry — Semantic conventions for exceptions in logs | Status: **Stable** (parts Development) | https://opentelemetry.io/docs/specs/semconv/exceptions/exceptions-logs/ |
| **1** | OpenTelemetry — Trace semantic conventions (general) | Status: Mixed | https://opentelemetry.io/docs/specs/semconv/general/trace/ |
| **1** | Google SRE Book — Monitoring Distributed Systems (Ch.6) | 2017 (CC BY-NC-ND 4.0) | https://sre.google/sre-book/monitoring-distributed-systems/ |
| **1** | Google SRE Book — Addressing Cascading Failures (Ch.22) | 2017 | https://sre.google/sre-book/addressing-cascading-failures/ |
| **1** | Google SRE Book — Data Processing Pipelines (Ch.25) | 2017 | https://sre.google/sre-book/data-processing-pipelines/ |
| **1** | Principles of Chaos Engineering | Last update **2019-03** | https://principlesofchaos.org/ |
| **1** | OWASP Cheat Sheet Series — RAG Security (§12, §14) | Current | https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html |
| **1** | Python — Logging HOWTO | Python **3.14** docs | https://docs.python.org/3/howto/logging.html |
| **1** | Python — `logging` module reference | Python **3.14** docs | https://docs.python.org/3/library/logging.html |
| **2** | Google SRE Workbook — Monitoring (Ch.4) | 2018 | https://sre.google/workbook/monitoring/ |
| **2** | Great Expectations — Choose result format | Docs v **1.19** | https://docs.greatexpectations.io/docs/core/trigger_actions_based_on_results/choose_a_result_format/ |

**Source count:** **13 distinct Tier 1–2 primary sources** (11 Tier 1, 2 Tier 2).

**Contradictions surfaced:**

1. **Graceful degradation vs fail-not-partial:** SRE overload guidance permits degraded responses; OWASP RAG and QA-fidelity doctrine require fail-closed. Resolution: classify subpaths; gates apply only to fidelity-critical outputs.
2. **Chaos in production vs CI-only:** Principles of Chaos prefer production experiments; QA tools should run fault injection in CI/hermetic fixtures first, with optional staged production chaos — audit should score both separately.
3. **OTel body vs attributes for structured data:** OTel community still refining event payload placement; audit should require stable schema somewhere (attributes or documented body map), not prescribe exporter-specific layout.

---

## 6. Overlap statement

This persona researched **external observability and failure-handling standards only**. It did **not**:

- Open, inspect, or score whisker production code (no whisker `file:line`, no whisker verdict).
- Clone, fork, or copy whisker or third-party code.
- Re-audit whisker error-handling findings in **`persona/`** (deterministic-core code audit) or **`llm-stack/`** (tapetum fail-not-partial / injection code audit).
- Address LLM throughput, batching, or concurrency tuning covered by **`llm-batching/`**.
- Duplicate **`p24`** (privacy/data governance) or **`p23`** (prompt-injection defense standards), though OWASP §12 intersects observability for security reconstruction.

**Prior folder avoided:** `persona/` and `llm-stack/` error-handling code scores; boundary held at external method + fault-injection bar.

---

**Strongest criterion (single bar):** **O4 — Fail-closed / fail-not-partial on fidelity-critical paths**, because it is the only observability-adjacent requirement that is **non-compensatory** for a QA pipeline: without it, trace and debug artifacts can be perfect while operators receive **false confidence** from partial outputs — the failure mode observability exists to prevent.
