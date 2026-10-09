# P21 — Operator & CLI-UX Researcher

**Persona:** 21 of 30 (Cluster F: Documentation & operator UX)  
**Date:** 2026-07-18  
**Scope:** External method and standards only. No whisker production-code inspection.

---

## 1. Question restated

What external bar defines **professional developer-tool CLI UX** for a QA/extraction package, and how should that bar become **repeatable audit criteria** for whisker's operator surface? This persona covers: exit-code contracts for CI scripting, `stdout`-is-result / `stderr`-is-progress separation, machine-readable output (`--json` and structured format flags), triaged end-of-run summaries (pytest/ruff/eslint patterns), actionable error messages, and progress/animation behavior that remains safe under piping and non-TTY CI logs.

---

## 2. Proposed audit criteria

Each criterion is scored on a **0–4 maturity ladder** unless marked as a **hard gate** (pass/fail). Evidence grades follow `00-FRAME.md` §6.3: **A** = multiple Tier-1 corroborating; **B** = single Tier-1 or converging Tier-2; **C** = Tier-3 only or contested; **D** = Tier-4/speculative.

### Criterion U1 — Documented exit-code contract (hard gate candidate)

| Field | Value |
|---|---|
| **Criterion** | CLI documents a stable exit-code taxonomy: **0** = success (including "found issues" when that is the intended success semantics for a check mode), **non-zero** = failure modes mapped to distinct causes where practical. Exit codes are part of the public contract, not implementation details. |
| **How to measure** | Read `--help`, README operator section, and docs for an exit-code table. Run scripted matrix: success path, domain failure (e.g. QA gate failed), usage error, config/internal error. Verify shell `$?` matches documented values. Compare to exemplar tables (pytest seven codes, ruff 0/1/2, ESLint 0/1/2). |
| **Audit method** | Conformance checklist (§5.1) |
| **Scoring hook** | §6.1 dimension: documentation/operator-UX; **§6.2 hard gate**: undocumented or inconsistent exit codes break CI conjunctive gates |
| **Gaming vector** | Always exit 0; exit 1 for both "tests failed" and "could not read config" so CI cannot distinguish fixable vs operational failure. |
| **Anti-gaming guard** | CI integration test asserts ≥3 distinct exit paths with documented meanings; usage/config errors must not share code with domain QA failure unless explicitly documented and justified. |
| **Evidence grade** | **A** |
| **Sources** | clig.dev §The Basics (exit codes); pytest Exit codes reference; ESLint CLI Exit Codes; sysexits.h(3head) BSD convention |

**Contradiction surfaced:** clig.dev states "return zero on success, non-zero on failure" universally, while **check/lint modes** (ruff `--check`, ESLint) treat "found violations" as exit **1** (successfully completed scan with findings). **Resolution rule:** document **two success classes** if needed: (a) operational success with findings = non-zero by design for CI; (b) operational failure (crash, bad args) = higher codes (2+). Exemplar precedent: ruff uses **2** for config/internal errors only.

### Criterion U2 — stdout / stderr stream discipline

| Field | Value |
|---|---|
| **Criterion** | Primary **machine-parseable result** (final verdict, JSON payload, diff, transformed artifact) goes to **stdout**. Human progress, logs, warnings, and diagnostic chatter go to **stderr**. Piping stdout to another tool yields only the result stream. |
| **How to measure** | Run representative commands redirecting stdout and stderr separately (`cmd > out 2> err`). Confirm JSON/final status on stdout; progress and errors on stderr. Verify pipe composition: `cmd \| jq` works without log noise in jq input. |
| **Audit method** | Conformance checklist (§5.1) + reproducibility replay (§5.8) |
| **Scoring hook** | §6.1 operator-UX; §6.2 gate if stdout mixes progress text with JSON (breaks automation) |
| **Gaming vector** | Print "Processing…" banners to stdout; emit JSON fragments interleaved with human text on stdout. |
| **Anti-gaming guard** | Automated test: parse stdout as JSON (when `--json`) without preprocessing; stderr may be non-empty but stdout must be single consumable artifact. |
| **Evidence grade** | **A** |
| **Sources** | clig.dev §The Basics (stdout/stderr); POSIX stdio.h (stdout/stderr definitions); Google Python Style Guide error-message channel guidance |

### Criterion U3 — Machine-readable output mode (`--json` or equivalent)

| Field | Value |
|---|---|
| **Criterion** | Structured output flag (e.g. `--json`, `--output-format json`) emits **valid, complete JSON** (or JSON Lines where documented) on stdout for primary results; schema fields are stable and documented; human-only formatting (colors, grouping headers, emoji) disabled in this mode. |
| **How to measure** | Run with JSON flag; validate with `jq empty` or JSON schema if published. Compare field presence across versions for backward compatibility. Confirm `--json` suppresses decorative output on stdout per clig.dev. |
| **Audit method** | Conformance checklist + comparative benchmarking (§5.3 vs ruff/eslint) |
| **Scoring hook** | §6.1 operator-UX; §6.4 anti-gaming (JSON must encode real verdicts, not cosmetic pass) |
| **Gaming vector** | `--json` prints pretty human table with JSON-ish strings; schema changes silently between patch releases. |
| **Anti-gaming guard** | Contract test: golden JSON snapshot or schema validation in CI; breaking field removals require semver-major or explicit schema version field. |
| **Evidence grade** | **A** |
| **Sources** | clig.dev §Output (`--json`); Ruff `output-format` setting (json, json-lines); ESLint `--format json` |

### Criterion U4 — CI-native output format variants

| Field | Value |
|---|---|
| **Criterion** | Beyond generic JSON, tool supports ≥1 **CI annotation format** where applicable (e.g. GitHub Actions, GitLab code quality, SARIF, JUnit XML) via `--output-format` or dedicated flag, documented with stable field mapping. |
| **How to measure** | Run with `github`, `gitlab`, `junit`, or `sarif` format; verify file/stdout validates against consumer schema. Check exemplar: ruff supports github/gitlab/junit/azure/sarif; pytest `--junit-xml`. |
| **Audit method** | Comparative benchmarking (§5.3) |
| **Scoring hook** | §6.1 operator-UX (maturity levels 0–2 = none; 3 = one format; 4 = multiple + docs) |
| **Gaming vector** | Format emits placeholder paths/line numbers that CI cannot anchor to repo files. |
| **Anti-gaming guard** | Sample integration job consumes output and posts at least one inline annotation tied to real file:line from fixture repo. |
| **Evidence grade** | **B** |
| **Sources** | Ruff `output-format` docs (github, gitlab, junit, sarif); pytest JUnitXML docs; ESLint `--format json` + `--output-file` |

### Criterion U5 — Triaged end-of-run summary

| Field | Value |
|---|---|
| **Criterion** | After execution, CLI prints a **compact summary block** listing failures/issues by category with enough context to act without re-reading full logs (pytest "short test summary info", ruff grouped/concise, ESLint error count footer). Summary respects signal-to-noise: group repeated error types under one header. |
| **How to measure** | Run multi-failure fixture; verify summary lists each failure with identifier (test node id, file:line, rule id). Count lines in summary vs full log; summary must appear on stderr (human) or structured tallies in JSON. |
| **Audit method** | Documentation-completeness audit (§5.9) applied to operator output |
| **Scoring hook** | §6.1 operator-UX; §6.4 anti-gaming |
| **Gaming vector** | Summary says "3 errors" without locations; duplicates same message per occurrence without grouping. |
| **Anti-gaming guard** | Require each summary entry includes **action locator** (path, test name, or rule id); cap summary repetition via grouping (clig.dev §Errors). |
| **Evidence grade** | **A** |
| **Sources** | clig.dev §Errors (grouping, signal-to-noise); pytest §Producing a detailed summary report (`-r` / short test summary); Ruff `grouped`/`concise` formats |

### Criterion U6 — Actionable error messages (hard gate candidate)

| Field | Value |
|---|---|
| **Criterion** | Anticipated errors are rewritten for humans: answer **what went wrong** and **how to fix it** (Google error-message model). Expected failures suggest the next command or flag. Unexpected failures offer debug path without drowning default output (trace to file or `--verbose`). |
| **How to measure** | Trigger top-N documented failure modes (missing file, bad flag, permission, config). Score messages against checklist: specific cause, user-actionable remedy, no raw stack trace on default path. |
| **Audit method** | Conformance checklist + maturity model (§5.2) |
| **Scoring hook** | **§6.2 hard gate**: trust-boundary/operator failures that only print exception class name fail professional bar |
| **Gaming vector** | Generic "Error: invalid input"; catch-all "Something went wrong" with exit 1. |
| **Anti-gaming guard** | Rubric sample: ≥80% of cataloged error paths include explicit remediation text; spot-check against Google "unactionable/vague" anti-patterns list. |
| **Evidence grade** | **A** |
| **Sources** | Google Technical Writing — Writing Helpful Error Messages; Google §General error handling rules; clig.dev §Errors |

### Criterion U7 — TTY-aware human vs machine output

| Field | Value |
|---|---|
| **Criterion** | Color, emoji, spinners, and progress bars activate **only on interactive TTY** (check stdout/stderr independently). Non-TTY (CI, pipes) disables animations and respects `NO_COLOR`, `TERM=dumb`, and `--no-color`. Scripts directed to use `--json`/`--plain` for stability. |
| **How to measure** | Run same command with stdout to pipe vs TTY; diff output. Set `NO_COLOR=1` and verify no ANSI. Confirm clig.dev rule: no animations when stdout not a TTY. |
| **Audit method** | Conformance checklist + fault-injection (§5.11 simulated CI) |
| **Scoring hook** | §6.1 operator-UX; §6.4 anti-gaming (cosmetic CI log noise) |
| **Gaming vector** | Unconditional progress bar renders hundreds of lines in CI ("Christmas tree" logs). |
| **Anti-gaming guard** | CI job captures log line count with piped stdout; fail threshold if progress frames exceed N lines without `--verbose`. |
| **Evidence grade** | **A** |
| **Sources** | clig.dev §Output (TTY heuristic, NO_COLOR, animations); clig.dev §Progress; no-color.org (cited by clig.dev) |

### Criterion U8 — Quiet / silent modes for automation

| Field | Value |
|---|---|
| **Criterion** | `-q`/`--quiet` or `-s`/`--silent` suppresses non-essential stderr chatter while **preserving exit-code semantics** (ruff: silent still exits 1 on violations). Avoid forcing users to redirect stderr to `/dev/null` to get clean automation. |
| **How to measure** | Run quiet + check mode; verify exit code unchanged vs verbose; stdout still emits required machine payload when requested. |
| **Audit method** | Conformance checklist |
| **Scoring hook** | §6.1 operator-UX |
| **Gaming vector** | `--quiet` hides errors and returns 0; silent mode drops JSON on stdout. |
| **Anti-gaming guard** | Quiet-mode test matrix must include a failing case that still exits non-zero and emits structured output when `--json` combined. |
| **Evidence grade** | **B** |
| **Sources** | clig.dev §Output (`-q` option); Ruff `--silent` help text; pytest `-q` verbosity docs |

### Criterion U9 — Layered verbosity

| Field | Value |
|---|---|
| **Criterion** | Multiple verbosity levels (`-v`, `-vv`, or `--verbose` tiers) scale detail monotonically: default = operator-sufficient; higher = diagnostic. pytest precedent: progress characters → per-test lines → full diffs. |
| **How to measure** | Run identical failing fixture at default, `-v`, `-vv`; verify strictly increasing detail without changing pass/fail outcome. |
| **Audit method** | Maturity model (§5.2) |
| **Scoring hook** | §6.1 operator-UX |
| **Gaming vector** | `-v` changes exit code or masks failures in noise. |
| **Anti-gaming guard** | Exit code invariant across verbosity levels for same inputs. |
| **Evidence grade** | **B** |
| **Sources** | pytest §Managing pytest's output (verbosity); clig.dev §Saying (just) enough |

### Criterion U10 — Signal handling and fast interrupt

| Field | Value |
|---|---|
| **Criterion** | On SIGINT (Ctrl-C), program responds immediately with user-visible message, bounded cleanup timeout, and non-zero exit; second interrupt may force skip (documented). Long operations remain interruptible. |
| **How to measure** | Start long batch; send SIGINT; measure time-to-message and process exit. Verify no orphan temp files without docs. |
| **Audit method** | Observability / fault-injection audit (§5.11) |
| **Scoring hook** | §6.1 operator-UX (overlaps P25 method, criterion stays UX-facing) |
| **Gaming vector** | Ignore SIGINT until batch completes; swallow interrupt exit code as 0. |
| **Anti-gaming guard** | Automated SIGINT test expects exit ≠ 0 within T seconds and message on stderr. |
| **Evidence grade** | **B** |
| **Sources** | clig.dev §Signals and control characters |

### Criterion U11 — Check vs mutate mode clarity

| Field | Value |
|---|---|
| **Criterion** | Tools that both analyze and modify state expose explicit modes (`--check`, `--fix`, `--dry-run`) with distinct exit semantics and stdout payloads documented per mode. Mutations summarize what changed on success (clig.dev "tell the user when state changes"). |
| **How to measure** | Run check mode on dirty fixture → non-zero + no writes. Run fix mode → writes + summary. ruff: `format` vs `format --check`; ESLint `--fix-dry-run` + `--format json`. |
| **Audit method** | Conformance checklist + comparative benchmarking |
| **Scoring hook** | §6.1 operator-UX; §6.2 gate if default command mutates without warning |
| **Gaming vector** | Default run modifies files while CI expects check-only. |
| **Anti-gaming guard** | CI default invokes check/dry-run subcommand; document mutating default as maturity level 0. |
| **Evidence grade** | **A** |
| **Sources** | clig.dev §Output (state change messaging); Ruff formatter exit codes (`--check`); ESLint `--fix` / `--fix-dry-run` |

### Criterion U12 — Suggested next commands in help and errors

| Field | Value |
|---|---|
| **Criterion** | Help text and common errors suggest **copy-pasteable next commands** (git-style). Concise help on missing required args; full `--help` with examples leading (clig.dev §Help). |
| **How to measure** | Run bare subcommand; verify concise help with example + pointer to `--help`. On common errors, output includes suggested fix command. |
| **Audit method** | Documentation-completeness audit (§5.9) |
| **Scoring hook** | §6.1 operator-UX; §6.4 anti-gaming ("documented" → operator can succeed from messages alone) |
| **Gaming vector** | Help exists but examples are non-functional placeholders. |
| **Anti-gaming guard** | Doc test: execute first example from `--help` in clean env without modification. |
| **Evidence grade** | **B** |
| **Sources** | clig.dev §Help (concise vs full, examples, suggest commands); clig.dev §Errors |

---

## 3. External benchmark / exemplar bar

### Tier-1/Tier-2 exemplar signals (from public docs, not code audit)

| Practice | clig.dev | pytest | Ruff | ESLint |
|---|---|---|---|---|
| Exit code table documented | 0 / non-zero rule + map failures | 0–6 public enum | 0/1/2 per subcommand | 0/1/2 documented |
| stdout vs stderr | Primary output vs messaging | Captured separately in tests | Violations to stdout in JSON | Formatted report to stdout |
| Machine JSON | `--json` pattern | JUnit XML, reportlog ecosystem | `output-format=json` | `--format json` |
| CI formats | Encourage stable flags | `--junit-xml` | github, gitlab, sarif, azure | JSON + custom formatters |
| Triaged summary | Group errors, high SNR | `-r` short test summary | grouped/concise | Error/warning counts |
| Actionable errors | Rewrite for humans | Assertion context + diff tiers | Fix hints via rules | Rule docs linked |
| TTY-safe progress | No animation if not TTY | N/A (test runner) | N/A | Color off if not TTY |
| Check vs fix | Tell user state changed | N/A | `--check`, `--fix` | `--fix`, `--fix-dry-run` |

**Professional bar (synthesis-level):** A QA-tool CLI meets **U1+U2+U6** as floor (CI cannot run without them), **U3+U5+U7** as target (automation + human triage in CI and local dev), and **U4+U11** as best-in-class alignment with ruff/pytest/eslint ecosystems. Operator UX is **not** decorative: it is the trust surface through which extraction-QA verdicts enter CI conjunctive gates (per `00-FRAME.md` §6.2).

**Where exemplars diverge (do not cargo-cult):** ESLint's default `stylish` format is human-first; whisker should default human-readable but **document JSON/check as CI path** (ruff precedent). sysexits.h granular codes (64–78) are optional; pytest's six-code enum is sufficient if documented. Emoji/symbol decoration (clig.dev permissive) may be wrong for conservative WG21 tooling; prefer maturity level 2 without emoji unless user research supports it.

---

## 4. Recommended weight & gate recommendation

| Recommendation | Rationale |
|---|---|
| **Dimension weight: 8%** of composite (shared documentation/operator cluster with P20; operator UX is load-bearing for CI adoption but narrower than eval-science dimensions) | CLI UX enables operators and agents to run gates reliably; weight cites clig.dev + pytest precedent that exit/stream contracts are foundational, not differentiators. |
| **Hard gates (conjunctive): U1, U2, U6** | **U1:** CI conjunctive gates require predictable `$?` (whisker docs already claim exit-code CI contract per `00-FRAME.md` §3 category note; audit must verify). **U2:** Mixed streams break automation. **U6:** Opaque errors fail "operator can succeed from docs/messages alone" (§6.4). |
| **Soft gates (cap dimension at level 2): U3** if absent | No JSON/structured output caps automation maturity; acceptable only for library-only consumption without CLI automation. |
| **Strongly recommended, not gated: U5, U7, U11** | Triaged summaries, TTY-safe output, and check/fix separation differentiate professional QA tools from script prototypes. |
| **Evidence propagation** | Dimension composite inherits weakest grade among U1–U3 load-bearing criteria (expected **A** when sourced against clig.dev + pytest + ruff). |
| **Contested criteria discount** | U4 CI format breadth: not all tools need SARIF; apply §6.5 — lower weight if JSON + one CI format present. |

---

## 5. Sources

### Tier 1 — Authoritative / primary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S1 | Command Line Interface Guidelines (clig.dev) | https://clig.dev/ | Current (2024–2026 maintainer edition) |
| S2 | POSIX.1-2017 — `<stdio.h>` (stdout/stderr definitions) | https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/stdio.h.html | IEEE Std 1003.1-2017 |
| S3 | pytest — Exit codes reference | https://docs.pytest.org/en/stable/reference/exit-codes.html | pytest 9.x stable docs |
| S4 | Google Technical Writing — Writing Helpful Error Messages | https://developers.google.com/tech-writing/error-messages | Current Google Developers curriculum |
| S5 | Google Technical Writing — General error handling rules | https://developers.google.com/tech-writing/error-messages/error-handling | Current Google Developers curriculum |
| S6 | ESLint — Command Line Interface (Exit Codes section) | https://eslint.org/docs/latest/use/command-line-interface | ESLint 9.x docs |

### Tier 2 — Strong secondary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S7 | Ruff — Settings (`output-format`) | https://docs.astral.sh/ruff/settings/#output-format | Ruff 0.15.x docs (2026) |
| S8 | Ruff — Formatter exit codes | https://docs.astral.sh/ruff/formatter/ | Ruff 0.15.x docs (2026) |
| S9 | pytest — Managing pytest's output | https://docs.pytest.org/en/stable/how-to/output.html | pytest 9.x stable docs |
| S10 | sysexits.h — BSD exit status conventions | https://man7.org/linux/man-pages/man3/sysexits.h.3head.html | man-pages 6.18 (2025-09-21) |

### Tier 3 — Contextual (corroboration only)

| ID | Source | URL |
|---|---|---|
| S11 | no-color.org convention | https://no-color.org/ |
| S12 | Nielsen Norman Group — Error Message Guidelines | https://www.nngroup.com/articles/error-message-guidelines/ (cited by clig.dev) |

**Source count:** 6 Tier-1 + 4 Tier-2 = **10 distinct Tier 1–2 sources** (floor ≥3 satisfied).

**Strongest criterion:** **U2 — stdout / stderr stream discipline**, because it is the compositional invariant (McIlroy pipeline rule cited in clig.dev) that makes every other automation criterion (JSON piping, CI redirection, conjunctive gates) mechanically reliable; violating it collapses U3–U5 regardless of documented exit codes.

---

## 6. Overlap statement

This persona researched **external CLI/operator UX standards and exemplars only**. It did **not** open whisker production code, cite whisker `file:line`, score whisker, clone/fork/copy code, or duplicate:

- **`persona/`** — prior code-level whisker audits (including any CLI scoring there).
- **`p20-documentation-agent-guidance.md`** — documentation/agent-guidance completeness matrix (this persona covers operator **runtime UX**, not doc corpus structure).
- **`p04-cicd-test-maturity.md`** — CI/test-suite maturity standard (this persona covers CLI **surface** contracts that CI consumes, not test hermeticity or mutation testing).
- **`p25-observability-failure-handling.md`** — trace/debug/logging/fail-closed pipeline behavior (U10 signal handling touches UX only; observability depth belongs to P25).

Boundary held: **operator-UX criteria and external bar**, handed to synthesis as rubric inputs for the documentation/operator-UX dimension.
