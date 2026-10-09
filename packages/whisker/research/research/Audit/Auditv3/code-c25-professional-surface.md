# C25 Professional Surface

**Role**: Audit the CLI surface as an operator sees it: documented commands vs
code, code without an operator path, and the fidelity of the docs to the
actual argparse tree.
**Audited state**: whisker 0.5.0, working tree, manifest
b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771
**Gates**: D7 (Professional surface), D8 (Platform compatibility), both
PROPOSED (Auditv2 naming, re-applied here; see section 6).

## 1. Scope

Three console scripts, their full `--help` trees, the interactive menu
(`menu.py`), and every module reachable (or not) from those three entry
points. Cross-check the documented command set (`CLAUDE.md`, `tapetum_llm.md`,
benchmark READMEs) against the live argparse surface. Verify the exit-code
contract (E9) is discoverable by an operator without reading source.

## 2. Commands and Exits

```
uv run --package whisker -- whisker --help
uv run --package whisker -- whisker <sub> --help   (all 19 subcommand paths)
uv run --package whisker whisker-tapetum-llm --help
uv run --package whisker whisker-readback --help
```

All `--help` invocations exit 0 (E4, `raw/w2-cli-surface.md` SS2-3). Full
capture in `raw/w2-cli-surface.md`.

## 3. Current Evidence

### 3.1 Surface inventory (E4)

3 console scripts (`whisker`, `whisker-tapetum-llm`, `whisker-readback`), 19
subcommand paths, 55 unique flags (`raw/w2-cli-surface.md` SS3.21). `whisker`
alone covers 17 of the 19 paths (default score, `bench`, `guard`, `golden`,
`facts`, `calibrate`, `score-file`, `check-facts`, `corpus stratify`, `corpus
draft`, and six `survey` subcommands).

### 3.2 Documented-but-missing (docs claim a flag the CLI does not have)

Only one whisker-operator-relevant hit: `--enable-prefix-caching`
(`packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md:309`). It is quoted
inline as if it were a `whisker-tapetum-llm` argument; it is a **vLLM server**
setting, not a lane flag (`raw/w2-cli-surface.md` SS4.1). Five further
backticked-but-missing tokens (`--append`, `--headless`, `--config`,
`--smoke`, `--pdf`) belong to benchmark tooling (`render_report.py`,
`run_campaign_v2.py`) documented in `packages/whisker/benchmark/README.md` and
`benchmark/tools/README.md`, not to any whisker console script.

### 3.3 In CLI but not documented

`whisker compare` exists as a module (`compare/cli.py`, `prog="whisker-compare"`)
but has no `[project.scripts]` entry and no routing from `whisker.__main__`
(`raw/w2-cli-surface.md` SS1, SS4.1, SS6.1). It is invoked only by benchmark
tooling (`gen_compare_pdf.py`, `gen_appendix.py`), never by an operator through
`whisker` or `whisker-compare`. Eight flags used by real subcommands
(`--anchors`, `--facts`, `--labels`, `--md`, `--ref`, `--slack`, `--source`,
`--target-fpr`) are not backticked anywhere in `CLAUDE.md`, `tapetum_llm.md`,
`corpus/README.md`, or `benchmark/README.md` (`raw/w2-cli-surface.md` SS4.2);
they are discoverable only via `--help` or argparse's own generated text, not
via prose documentation.

### 3.4 Menu-only actions

Bare `whisker` in a TTY opens `menu.py` (`__main__.py:1315-1317`). Two menu
actions have no CLI equivalent (`raw/w2-cli-surface.md` SS5):

| Menu action | Dispatches to | CLI equivalent |
|---|---|---|
| "Last Report" | `_show_last_report` (reads `whisker/det/report.md`, renders via Rich) | none |
| Ideals lane (Corpus Lanes submenu) | `_run_ideals_lane` (auto-discovers `packages/tomd/tests/fixtures/golden/ideals/`, scores only those PIDs) | none (`whisker ideals` does not exist) |

An operator scripting a pipeline cannot reach either action without
reimplementing the menu's internal logic.

### 3.5 No operator path at all

Reachability was traced from all four entry surfaces (`__main__`,
`tapetum_llm.cli`, `readback_cli`, `menu.run_menu`). Zero production importer
reaches (`raw/w2-cli-surface.md` SS6.1):

| Module / tree | Only reachable from |
|---|---|
| `compare/` (7 modules incl. `cli.py`) | benchmark tooling only |
| `branding/` (4 modules) | benchmark `render_report.py` / compare render paths |
| `tapetum_llm/vision.py`, `vision_task.py`, `transcribe.py`, `vlm_diff.py`, `vlm_pipeline.py` | each other; no entry-point importer |
| `tapetum_llm/payload_scope.py` | `tests/test_payload_scope.py` only |

### 3.6 Exit-code contract, documented and re-verified live

The typed contract (`0` ok, `1` error, `3` review, `5` fail) is stated
verbatim inside the `whisker --help` text itself (`raw/w2-cli-surface.md`
SS2.1, "Typed exit codes (CI contract)"), not only in `CLAUDE.md:476-479`. The
`--gate {pass,review,fail}` flag and its effect ("lowest verdict considered
acceptable for exit 0") are documented per-subcommand in argparse help
(`raw/w2-cli-surface.md` SS3.2). Live re-verification against three real
papers with distinct verdicts (E9) reproduced the documented matrix exactly:
0/0/0 for a `pass` paper, 3/0/0 for a `review` paper, 5/5/0 for a `fail`
paper, with no deviation. `whisker-tapetum-llm`'s separate, simpler contract
(advisory always exits 0, operational error exits 1) is documented in
`CLAUDE.md:481-484` and confirmed live: 9 of 10 E13 scenarios exited 0
(advisory verdicts, including two `fail` fusions), one (S6, nonexistent
service slot) exited 1 with no verdict emitted.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---|---|---|
| F1 | `whisker compare` (`compare/cli.py`, `prog="whisker-compare"`) is a declared but unregistered console script; no operator path exists | Medium | HIGH |
| F2 | Two menu-only actions ("Last Report", ideals lane) have no CLI equivalent; unscriptable | Low | HIGH |
| F3 | Four module trees (`compare/`, `branding/`, the VLM chain, `payload_scope.py`) ship in the wheel (E6) with zero operator reachability | Medium | HIGH |
| F4 | One load-bearing doc/code mismatch: `--enable-prefix-caching` documented as if it were a `whisker-tapetum-llm` flag; it is a vLLM server setting | Low | HIGH |
| F5 | Eight working CLI flags are undocumented in prose (discoverable only via `--help`) | Low | HIGH |
| F6 | Exit-code contract is documented in both `--help` output and `CLAUDE.md`, and reproduces exactly under live re-verification (E9) | Informational | HIGH |
| F7 | `whisker-tapetum-llm`'s separate exit contract is documented and confirmed live across 10 scenarios (E13) | Informational | HIGH |

## 5. False-Pass Hypothesis

**Could the dormant surface (F1, F3) be intentionally staged, i.e. code the
project plans to wire up, making "no operator path" a non-finding?**
`CLAUDE.md`'s own "Known gaps" section (lines 883-887) explicitly calls the
VLM chain unwired with an open delete-vs-quarantine decision, which confirms
F3 is a known, named gap for that tree. It says nothing about `compare/`,
`branding/`, or `payload_scope.py`. Those three are undocumented as dormant;
the project's own gap-tracking mechanism does not currently cover them, so F1
and part of F3 are not merely known-and-accepted, they are unacknowledged in
the authoritative doc.

**Could the undocumented flags (F5) be deliberately internal-only?** All
eight are on subcommands (`check-facts`, `calibrate`, `score-file`, `guard`)
that are themselves documented and intended for operator use; there is no
"internal" marker distinguishing these flags from the documented ones on the
same subcommands. No evidence supports deliberate omission.

## 6. Gate/Dimension Mapping (PROPOSED)

- **D7 (Professional surface): PROPOSED PASS-PROVISIONAL.** Exit codes,
  stderr/stdout separation, and JSON output remain clean (unchanged from
  Auditv2). The new CLI-completeness lens surfaces genuine surface debt (F1,
  F2, F3) that a "professional surface" gate should probably weigh, since an
  operator following the docs literally cannot discover `whisker compare` or
  reach the menu-only actions from a script.
- **D8 (Platform compatibility): PROPOSED PASS.** No Windows-specific
  regression found in this pass; unchanged from Auditv2 (code inspection
  only, not independently re-verified here).

## 7. Limitations

- This report inventories the CLI as it exists; it does not establish whether
  `compare/`, `branding/`, or `payload_scope.py` were reachable at any prior
  commit. The dormant status could be new or long-standing; no git-blame
  analysis was performed.
- `--help` exit-code verification is static (argparse behavior); the
  operator-facing README/quickstart prose was not independently tested for
  copy-paste correctness (commands were read, not all re-executed verbatim).
- Rich's own terminal-detection behavior (flagged in Auditv2 C25/C28 as
  unaudited) was not re-examined in this pass.

## 8. Conclusion

The exit-code contract is sound, documented in two independent places, and
reproduces exactly under live re-verification, an improvement in evidence
class over Auditv2 (code inspection only). But the CLI-completeness lens this
report applies, which Auditv2 never used, surfaces real operator-facing
debt: one unregistered console script, two CLI-unreachable menu actions, and
four module trees with zero path from any entry point, one of which
(`--enable-prefix-caching`) is an active documentation error rather than a
mere omission. None of this is a correctness defect in the deterministic
gate; all of it is discoverability and ergonomics debt.

## 9. Delta vs Auditv2

Auditv2's `code-c25-professional-surface.md` scoped narrowly to packaging,
exit codes, stderr/stdout separation, JSON serialization, error messages, and
Windows ANSI gating. It found zero violations, all seven findings
Informational, and explicitly stated "Cannot verify `whisker --help` output
rendering (requires running the CLI...)". This report closes exactly that
gap: `raw/w2-cli-surface.md` is a full, executed capture of every `--help`
tree, the menu, and a documentation cross-reference the prior audit never
attempted.

The new lens changes the shape of the findings entirely. Where Auditv2
reported "no violations found" (its section 4, F1-F7 all Informational),
this report reports two Medium findings (F1, F3) and confirms the exit-code
contract with live runtime evidence (E9) rather than code inspection alone,
upgrading F6/F7 from Auditv2's static claim to a runtime-verified one.
Whether the dormant surface (`compare/`, `branding/`, `payload_scope.py`)
existed at Auditv2's audited commit is not established here; Auditv2 did not
inventory the CLI surface at all, so no prior baseline exists to diff
against. This is the first audit cycle in which the full CLI/docs
cross-reference was performed.
