# P20 — Documentation & Agent-Guidance (CLAUDE.md) Researcher

**Persona:** 20 of 30 (Cluster F — Documentation & operator UX)  
**Date:** 2026-07-18  
**Scope:** External method and benchmark only. No whisker production-code inspection, no whisker verdict, no whisker `file:line` citations.

---

## 1. Question restated

What external bar should a **professional hybrid QA package** meet for (a) human-facing technical documentation and (b) **agent-guidance files** (`CLAUDE.md`, `AGENTS.md`, nested package rules), and how should that bar become **audit criteria**—especially a **doc-completeness matrix** covering contract, usage, invariants, failure modes, calibration status, known gaps, architecture map, and greppable conventions?

The downstream audit must answer: *Can a new operator or coding agent succeed from the docs alone, without reverse-engineering source?*

---

## 2. Proposed audit criteria

Each criterion includes: how to measure, audit method (from `00-FRAME.md` §5), scoring-design hook (§6), gaming vector + anti-gaming guard, evidence grade, and Tier 1–2 sources.

### Criterion P20-C01 — Diátaxis quadrant coverage (human docs)

**Statement:** Published documentation separates **tutorials**, **how-to guides**, **reference**, and **explanation** into distinct, correctly typed pages. Cross-quadrant blur (e.g., tutorial bloated with explanation, reference mixed with procedural steps) is treated as a functional-quality failure.

**How to measure:** Build a coverage matrix: rows = the four Diátaxis modes; columns = major product surfaces (install/CLI, deterministic gate, advisory LLM lane, metrics/calibration, operator troubleshooting). Score each cell: **Present & correctly typed** / **Present but mis-typed** / **Absent**. Target: all cells **Present & correctly typed** for a "professional" bar; incubating bar allows one **Absent** on explanation if reference + how-to cover the gap.

**Audit method:** Documentation-completeness audit; conformance checklist (Diátaxis compass).

**Scoring hook:** §6.1 (documentation/operator-UX dimension, maturity 0–4); §6.4 anti-gaming.

**Gaming vector:** Empty stub pages or README-only content labeled "docs."

**Anti-gaming guard:** Random-sample 3 pages per quadrant; apply Diátaxis compass (action vs cognition × study vs work). Mis-typed pages count as absent. Require at least one runnable tutorial with verifiable end state.

**Evidence grade:** A (multiple Tier-1 converging: Diátaxis official + CNCF IA criteria).

**Sources:** [Diátaxis start-here](https://diataxis.fr/start-here/) (2026 site); [Diátaxis quality](https://diataxis.fr/quality/) (2026); [CNCF techdocs IA criteria](https://github.com/cncf/techdocs/blob/main/docs/analysis/criteria.md) (LF/CNCF, ongoing).

---

### Criterion P20-C02 — Functional doc quality (accuracy, completeness, consistency, clarity, navigation)

**Statement:** Documentation meets independently assessable **functional quality** dimensions before any "deep quality" claim: accurate vs product behavior, complete for stated personas, terminologically consistent, clear to target audience, and navigable (findable happy path ≤3 clicks or equivalent TOC depth).

**How to measure:** Per-dimension checklist (5 dimensions × sample of 10 high-traffic pages + README + CLI `--help` parity check). **Pass** = zero accuracy failures on sampled pages; ≤1 completeness gap with documented escalation path; glossary or canonical term list resolves synonym drift; new-user path signposted from README/root doc.

**Audit method:** Documentation-completeness audit; maturity-model scoring (0–4 per dimension).

**Scoring hook:** §6.1; §6.3 (accuracy failures downgrade evidence grade to C minimum for that finding).

**Gaming vector:** Accurate but incomplete docs; marketing language masking missing reference material.

**Anti-gaming guard:** Cross-check 5 documented CLI flags/commands against `--help` output; cross-check 3 documented invariants against test names or grep-able constants (audit stage later—Stage 0 defines the check). Fail if documented behavior contradicts help text.

**Evidence grade:** A (CNCF + arc42 + Diátaxis functional quality theory).

**Sources:** [CNCF criteria — accuracy/IA/new-user](https://github.com/cncf/techdocs/blob/main/docs/analysis/criteria.md); [arc42 documentation principles Req-1–Req-11](https://arc42.org/principles-of-technical-documentation) (2026); [Diátaxis quality — functional vs deep](https://diataxis.fr/quality/).

---

### Criterion P20-C03 — Contract & invariant documentation (operator + agent)

**Statement:** A single **contract doc** (or dedicated section in package `CLAUDE.md` / root docs) enumerates: public behavioral contract, **invariants** (must always hold), **failure modes** (what happens when violated), **calibration status** (fitted vs placeholder thresholds), and **known gaps** (explicit non-goals). Categories already named in whisker research framing—lanes, hard gate vs advisory overlay, exit codes, trace/debug, thresholds—must appear as **named, greppable entries**, not implied behavior.

**How to measure:** Contract checklist (minimum 8 entries): (1) deterministic vs advisory boundary, (2) what can/cannot gate release, (3) exit-code table, (4) trace vs debug artifact spec, (5) threshold/calibration provenance, (6) failure-not-partial rule, (7) known gaps/roadmap, (8) architecture map (components + data flow). Score: count present / 8; **≥7/8** = pass bar; missing calibration status or failure modes = automatic partial.

**Audit method:** Documentation-completeness audit; conformance checklist.

**Scoring hook:** §6.2 **candidate hard gate** (missing invariant/failure-mode docs for a safety-critical contract); §6.4.

**Gaming vector:** Vague prose ("we fail safely") without testable failure semantics.

**Anti-gaming guard:** Each invariant must include **detectable violation** (symptom, exit code, or log/trace field). Each failure mode must state **fail-closed vs fail-open**. Auditor attempts one documented "happy path" run from docs only (later stage).

**Evidence grade:** B (arc42 Req-1/Req-4 + CNCF API/CLI reference completeness + agent-guidance exemplars).

**Sources:** [arc42 principles](https://arc42.org/principles-of-technical-documentation); [CNCF criteria — CLI/API reference completeness](https://github.com/cncf/techdocs/blob/main/docs/analysis/criteria.md); [OpenAI Codex AGENTS.md layering](https://developers.openai.com/codex/guides/agents-md) (2026).

---

### Criterion P20-C04 — Architecture map & greppable conventions

**Statement:** Documentation includes an **architecture map** (components, trust boundaries, package boundaries) and a **conventions index** (naming patterns, module-level constants, logging vs print, library-returns-data) written so operators and agents can **grep** the codebase using documented tokens (e.g., `shortcut:`, threshold constant names, tool namespaces).

**How to measure:** (a) Architecture diagram or structured text map with ≥5 labeled components and trust-boundary callouts. (b) Conventions section lists ≥5 greppable patterns with example search strings. (c) Reference doc structure mirrors code architecture where applicable (Diátaxis reference rule).

**Audit method:** Documentation-completeness audit; comparative benchmarking (Docling AGENTS.md structure section).

**Scoring hook:** §6.1; §6.4.

**Gaming vector:** File-tree dump without trust boundaries; conventions that duplicate linter config without agent-actionable rules.

**Anti-gaming guard:** Map must mark **trust boundaries** (untrusted input paths). Conventions must include at least one **do-not** rule with rationale. Random grep: 3 documented tokens must resolve to real symbols (later code stage).

**Evidence grade:** B (Diátaxis reference architecture rule + Docling exemplar).

**Sources:** [Diátaxis start-here — reference mirrors structure](https://diataxis.fr/start-here/); [Docling AGENTS.md — project structure + code standards](https://github.com/docling-project/docling/blob/main/AGENTS.md) (2026).

---

### Criterion P20-C05 — Runnable examples & version currency

**Statement:** Task and reference docs ground claims in **copy-paste runnable examples** with stated prerequisites, expected output, and version scope. Examples are treated as part of the contract (arc42 Req-2 current; CNCF new-user samples).

**How to measure:** Sample 5 how-to/reference pages: each must have ≥1 fenced code block with language tag, prerequisites, and expected outcome. Release notes or changelog linked from docs index. **Pass:** 5/5 runnable on stated platform; **Partial:** 3–4/5; **Fail:** ≤2/5 or undated breaking-change instructions.

**Audit method:** Documentation-completeness audit; reproducibility replay (doc commands re-executed).

**Scoring hook:** §6.1; §6.3.

**Gaming vector:** Pseudocode labeled as example; examples requiring undeclared secrets/paths.

**Anti-gaming guard:** Examples must declare env vars and data prerequisites explicitly. Stale version numbers flagged against package version metadata (later stage).

**Evidence grade:** A (CNCF new-user + arc42 Req-2/Req-11).

**Sources:** [CNCF criteria — new user content](https://github.com/cncf/techdocs/blob/main/docs/analysis/criteria.md); [arc42 principles](https://arc42.org/principles-of-technical-documentation).

---

### Criterion P20-C06 — AGENTS.md root contract (cross-tool agent orientation)

**Statement:** Repository ships a root **`AGENTS.md`** (open Markdown, no required schema) covering at minimum: project overview, **build/test commands**, **code standards**, **testing instructions**, and **security/trust-boundary notes**. File is **living documentation** (version-controlled, reviewed with behavior changes). Monorepos add **nested `AGENTS.md`** per package; nearest file wins on conflict.

**How to measure:** Section checklist against [agents.md](https://agents.md/) recommended sections: overview ✓, build ✓, test ✓, style/conventions ✓, security ✓, PR/commit expectations (recommended). Line budget: **≤200 lines root** (orientation, not encyclopedia)—excess triggers split-to-nested-files finding per Anthropic/Codex practice. Nested package file present for library package if monorepo.

**Audit method:** Conformance checklist; comparative benchmarking (Docling, firecrawl, OpenAI Codex discovery rules).

**Scoring hook:** §6.1; §6.4.

**Gaming vector:** Generic LLM boilerplate; duplicated README; 800-line root file agents truncate.

**Anti-gaming guard:** Every listed test command must be executable verbatim from repo root or documented cwd. Root file must link to deeper docs rather than duplicate reference material ([AgentPatterns AGENTS.md as ToC pattern](https://agentpatterns.ai/standards/agents-md/)). Flag if combined nested chain exceeds tool byte limits (Codex default 32 KiB—split required).

**Evidence grade:** A (agents.md official + OpenAI Codex guide + Docling exemplar).

**Sources:** [agents.md official](https://agents.md/) (AAIF/Linux Foundation steward, 2026); [OpenAI Codex AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md) (2026); [Docling AGENTS.md](https://github.com/docling-project/docling/blob/main/AGENTS.md).

---

### Criterion P20-C07 — CLAUDE.md / tool-specific rules (behavioral contract for agents)

**Statement:** Projects using Claude Code (or equivalent) maintain **`CLAUDE.md`** at repo and/or package scope as a **behavioral contract**: build commands, architecture in ≤3 sentences, conventions, explicit **do-not** boundaries, and pointers to path-scoped rules. Target **≤200 lines per file**; topic-specific rules use **`.claude/rules/` with `paths:` frontmatter** so context loads only when relevant.

**How to measure:** Checklist: (1) committed project-root or package `CLAUDE.md`, (2) line count ≤200 or documented split plan, (3) no contradictory rules across nested files, (4) path-scoped rules for ≥2 distinct areas (tests vs prod, package vs monorepo root), (5) verifiable instructions ("if removed, agent would err" test from Anthropic guidance). Optional `@import` allowed for organization but does not reduce token load.

**Audit method:** Documentation-completeness audit; conformance checklist.

**Scoring hook:** §6.1; §6.4.

**Gaming vector:** CLAUDE.md as full architecture dump; stale rules contradicting AGENTS.md.

**Anti-gaming guard:** Cross-file consistency review: AGENTS.md and CLAUDE.md must not conflict on test/build commands. Prefer AGENTS.md for cross-tool shared rules; CLAUDE.md for Claude-specific hooks/rules only ([Anthropic memory docs hierarchy](https://code.claude.com/docs/en/memory)).

**Evidence grade:** A (Anthropic official Claude Code memory documentation, Tier 1 vendor primary).

**Sources:** [Anthropic Claude Code — memory / CLAUDE.md](https://code.claude.com/docs/en/memory) (2026); [Claude Help Center — CLAUDE.md context](https://support.claude.com/en/articles/14553240-give-claude-context-claude-md-and-better-prompts); [agents.md — relationship to README and tool files](https://agents.md/).

---

### Criterion P20-C08 — Agent guidance: workflow & win conditions (exemplar pattern)

**Statement:** High-maturity repos document **agent workflows** as numbered sequences with **win conditions** and **verification commands** before task completion (firecrawl pattern), not only static conventions. Package-level agent files state **when to run which tests**, **scope limits**, and **finish gates** (`make validate`, targeted pytest, etc.).

**How to measure:** Agent file includes: (1) ordered workflow for non-trivial change (≥4 steps), (2) explicit finish gate command(s), (3) scope/discipline rules (Docling: no trivial tests, pathlib, typed models). Score 0–4 maturity.

**Audit method:** Comparative benchmarking; maturity-model scoring.

**Scoring hook:** §6.1; §6.4.

**Gaming vector:** "Run tests" without naming commands; finish gate omitted so agents stop early.

**Anti-gaming guard:** Finish gate must be a single copy-paste command block. Workflow must include failure-path step (what to do when tests fail).

**Evidence grade:** B (Docling + firecrawl AGENTS.md — Tier 2 exemplar maintainer files).

**Sources:** [Docling AGENTS.md — When making changes / Before finishing](https://github.com/docling-project/docling/blob/main/AGENTS.md); [firecrawl AGENTS.md — E2E-first workflow](https://github.com/firecrawl/firecrawl/blob/main/AGENTS.md).

---

### Criterion P20-C09 — Operator success path (docs-alone reproduction)

**Statement:** A **new operator** (human) can install, run the primary QA command on a sample input, interpret exit codes, and locate trace/debug artifacts using only published docs—without reading source. CNCF "getting started" and happy-path criteria apply.

**How to measure:** Timed doc-walk audit (scripted): given only docs, perform install → run → interpret result → find diagnostics. Record blockers. **Pass:** zero source-code opens required; **Partial:** one ambiguity with workaround documented; **Fail:** any mandatory source open.

**Audit method:** Documentation-completeness audit (primary); reproducibility replay.

**Scoring hook:** §6.2 **candidate hard gate** for operator-facing QA tool; §6.4 (closes "documented" Goodhart).

**Gaming vector:** README quickstart that omits failure interpretation; docs assuming monorepo insider paths.

**Anti-gaming guard:** Getting-started must link forward to troubleshooting and trace/debug sections. Exit-code table mandatory (pairs with P21 operator UX; P20 owns doc presence, P21 owns CLI contract quality).

**Evidence grade:** A (CNCF new-user + getting-started criteria).

**Sources:** [CNCF criteria — new user content & happy path](https://github.com/cncf/techdocs/blob/main/docs/analysis/criteria.md); [agents.md — sections for effective agent work](https://agents.md/).

---

### Criterion P20-C10 — Documentation maintenance process

**Statement:** Documentation has **ownership**, contribution/review path, and is updated in the same change process as behavior (CNCF content creation processes; arc42 Req-7/Req-11).

**How to measure:** CONTRIBUTING or equivalent names doc reviewers; MAINTAINERS or owners file; release process mentions doc updates; no duplicate doc sources without sync strategy (CNCF single-source rule).

**Audit method:** Conformance checklist; maturity-model scoring.

**Scoring hook:** §6.1; §6.3.

**Gaming vector:** CONTRIBUTING.md boilerplate with no doc review; docs hosted only in wiki outside repo.

**Anti-gaming guard:** Require evidence of ≥1 doc update in last two release cycles (later git stage)—Stage 0 defines criterion only.

**Evidence grade:** B (CNCF content creation + single-source).

**Sources:** [CNCF criteria — content creation & single-source](https://github.com/cncf/techdocs/blob/main/docs/analysis/criteria.md); [arc42 Req-7, Req-9, Req-11](https://arc42.org/principles-of-technical-documentation).

---

### Doc-completeness matrix (audit artifact template)

Use this matrix during the later audit. Rows = doc categories; columns = delivery channel.

| Category | Human tutorial | Human how-to | Human reference | Human explanation | README | Root AGENTS.md | Package CLAUDE.md | Status |
|---|---|---|---|---|---|---|---|---|
| Install / environment | | | | | | | | |
| Primary CLI/workflow | | | | | | | | |
| Deterministic gate contract | | | | | | | | |
| Advisory LLM lane (opt-in) | | | | | | | | |
| Invariants & named constants | | | | | | | | |
| Failure modes & exit codes | | | | | | | | |
| Trace / debug artifacts | | | | | | | | |
| Calibration status & thresholds | | | | | | | | |
| Known gaps / roadmap | | | | | | | | |
| Architecture map & boundaries | | | | | | | | |
| Greppable conventions | | | | | | | | |
| Metrics / eval interpretation | | | | | | | | |
| Security / untrusted input | | | | | | | | |

**Scoring:** cell = **F** (filled & correct type), **P** (partial), **A** (absent). Dimension score = %F weighted 2× over P.

---

## 3. External benchmark / exemplar bar

### Tier 1 frameworks (normative structure)

| Framework | Bar | Application to whisker audit |
|---|---|---|
| **Diátaxis** | Four documentation modes with distinct user needs; compass prevents quadrant blur; functional quality (accuracy, completeness, consistency) is prerequisite to excellence | Human docs must be typed and IA-separated; mis-typed content fails even if prose is polished |
| **CNCF TechDocs criteria** | IA completeness, persona/use-case coverage, getting-started paths, API/CLI reference completeness, maintenance process | Sets "incubating-grade OSS" doc bar; happy path + escalation |
| **arc42 documentation principles** | Correct, current, understandable, relevant, referenceable, maintainable, version-controlled, continuously updated | Contract/invariant docs must stay current with releases |

### Tier 2 agent-guidance exemplars (observed practice, not worship)

| Exemplar | Transferable practice | Would be wrong to cargo-cult |
|---|---|---|
| **agents.md (AAIF)** | Open Markdown, nested monorepo files, living doc, complements README | No schema enforcement—still need package-specific contracts |
| **Docling `AGENTS.md`** | Typed-model standards, explicit finish gate (`make validate`), project structure map, scoped change discipline | Their MkDocs stack / make targets are not universal |
| **firecrawl `AGENTS.md`** | E2E-first workflow, environment-gated tests, explicit win conditions | Their `pnpm harness` monorepo ops ≠ Python uv/pytest layout |
| **OpenAI Codex guide** | Directory-walk merge, byte limits, override files | 32 KiB default cap forces concise root + nested splits |
| **Anthropic Claude Code memory** | ≤200 lines, path-scoped `.claude/rules/`, CLAUDE.md as facts-not-procedures | Tool-specific; pair with AGENTS.md for cross-agent baseline |

### Professional bar summary (synthesis)

A **professional** documentation + agent-guidance posture means:

1. **Human docs** pass Diátaxis typing + CNCF IA/new-user/reference checks with runnable examples.
2. **Contract docs** make deterministic/advisory boundaries, failure semantics, calibration honesty, and gaps **explicit and greppable**.
3. **Agent docs** ship root `AGENTS.md` (cross-tool) + package `CLAUDE.md` (Claude-specific), ≤200 lines each at a given scope, nested overrides in monorepos, finish gates as commands, no encyclopedic duplication.
4. **Operator test:** docs-alone reproduction of install → run → interpret → diagnose succeeds.

---

## 4. Recommended weight & gate rationale

### Weight recommendation (feeds §6.1 documentation/operator-UX dimension)

| Sub-criterion | Suggested relative weight within doc dimension | Rationale |
|---|---|---|
| P20-C01 Diátaxis coverage | 15% | Structural foundation; prevents uncorrectable IA debt |
| P20-C02 Functional quality | 15% | Accuracy failures are worse than omissions (arc42 Req-1) |
| P20-C03 Contract & invariants | 20% | Highest leverage for hybrid QA trust model |
| P20-C04 Architecture & conventions | 10% | Enables agents/operators to navigate safely |
| P20-C05 Runnable examples | 10% | Grounds truth; reduces spec drift |
| P20-C06 AGENTS.md | 10% | Cross-tool agent baseline (industry direction) |
| P20-C07 CLAUDE.md / scoped rules | 10% | Claude Code ergonomics; prevents context bloat |
| P20-C08 Agent workflows | 5% | Maturity differentiator |
| P20-C09 Operator docs-alone path | 5% | Integrative check |
| P20-C10 Maintenance process | 5% | Sustainability |

**Suggested doc dimension weight in overall audit composite:** **8–12%** of total (mid-tier; below security/determinism gates, above branding). Exact number deferred to Opus synthesis with other personas—documentation enables but does not substitute for correct gates.

### Hard gate candidates (feeds §6.2)

| Gate | Condition | Rationale |
|---|---|---|
| **G-DOC-1** | Missing documented **failure modes + exit-code contract** for primary operator command | Operators cannot trust QA results they cannot interpret; pairs with fidelity doctrine |
| **G-DOC-2** | **Deterministic vs advisory boundary** absent or ambiguous in contract docs | Hybrid architecture unauditable; risks LLM gating by documentation drift |
| **G-DOC-3** | P20-C09 **Fail** (cannot reproduce primary workflow from docs alone) | Direct §6.4 anti-Goodhart: "documented" must mean operable |

Non-gates but high weight: calibration status honesty (partial allowed if labeled **uncalibrated** with protocol pointer—aligns with P16 method).

---

## 5. Sources

| Tier | Source | URL | Date/version | Used for |
|---|---|---|---|---|
| **T1** | Diátaxis (official) | https://diataxis.fr/start-here/ | Site active 2026 | Quadrant IA, compass |
| **T1** | Diátaxis quality theory | https://diataxis.fr/quality/ | Site active 2026 | Functional vs deep quality |
| **T1** | CNCF TechDocs assessment criteria | https://github.com/cncf/techdocs/blob/main/docs/analysis/criteria.md | LF/CNCF repo, ongoing | IA, new-user, CLI/API reference, maintenance |
| **T1** | arc42 documentation principles | https://arc42.org/principles-of-technical-documentation | 2026 site | Correct/current/maintainable docs |
| **T1** | Anthropic Claude Code memory docs | https://code.claude.com/docs/en/memory | 2026 | CLAUDE.md size, rules, hierarchy |
| **T1** | agents.md (AAIF/Linux Foundation) | https://agents.md/ | 2026 | AGENTS.md open standard |
| **T2** | OpenAI Codex AGENTS.md guide | https://developers.openai.com/codex/guides/agents-md | 2026 | Discovery, merge order, byte limits |
| **T2** | Docling AGENTS.md | https://github.com/docling-project/docling/blob/main/AGENTS.md | 2026-03+ main | Exemplar structure, finish gates, standards |
| **T2** | firecrawl AGENTS.md | https://github.com/firecrawl/firecrawl/blob/main/AGENTS.md | 2026 main | Workflow + win-condition pattern |
| **T2** | Claude Help Center — CLAUDE.md | https://support.claude.com/en/articles/14553240-give-claude-context-claude-md-and-better-prompts | Anthropic, 2026 | Operator-facing CLAUDE.md guidance |

**Distinct Tier 1–2 primaries used:** 10 (floor ≥3 satisfied).

**Contradictions surfaced:** Diátaxis explicitly states it **cannot** alone deliver functional quality (measurement discipline still required)—CNCF/arc42 supply that. AGENTS.md advocates **no required schema** while Anthropic pushes **≤200 lines** and path-scoped rules—reconciliation: AGENTS.md for shared orientation, CLAUDE.md/rules for depth without truncating cross-tool baseline. Codex **concatenates** nested files (later overrides); Claude loads nested CLAUDE.md on demand—audit should require **non-conflicting** commands across layers.

---

## 6. Overlap statement

**Confirmed boundaries held:**

- Did **not** open, inspect, or score whisker production code. No whisker `file:line` citations. No whisker documentation quality verdict.
- Did **not** duplicate the `persona/` swarm's code-level **documentation-claims** finding—that swarm scored whisker docs against an internal baseline; this persona researched **external doc/agent-guidance standards only**.
- Used `CLAUDE.md` **category list** only as already captured in `00-FRAME.md` §3 (lanes, gate, advisory overlay, thresholds, exit codes, trace/debug, calibration, golden roadmap)—not to judge whisker's implementation.
- Did **not** overlap **P21** (operator CLI UX): P20 owns **documentation presence/completeness**; P21 owns exit-code semantics, stderr/stdout, JSON output quality as CLI design.
- Did **not** clone, fork, or copy code from exemplar repos; read public docs and maintainer-authored agent files only.
- Did **not** re-litigate `redteam/`, `langextract/`, or case-study adoption verdicts.

**Prior folder avoided:** `persona/` (documentation-claims code audit).

---

*End of P20 report.*
