# Whisker Auditv3 — W2 CLI Surface Map

Audit date: 2026-08-03. Target: current working tree (unmodified).  
Invocation note: with `uv run --package whisker`, pass `--` before whisker arguments so `uv` does not consume `--help` (e.g. `uv run --package whisker -- whisker survey list --help`).

---

## 1. Entry points (`pyproject.toml`)

**Package:** `whisker`  
**Version:** `0.5.0`

| Console script | Target function |
|---|---|
| `whisker` | `whisker.__main__:main` |
| `whisker-tapetum-llm` | `whisker.tapetum_llm.cli:main` |
| `whisker-readback` | `whisker.tapetum_llm.readback_cli:main` |

No other `[project.scripts]` entries. `whisker.compare.cli` defines `prog="whisker-compare"` but is **not** registered as a console script.

---

## 2. Top-level `--help` (each console script)

### 2.1 `whisker --help`

Command: `uv run --package whisker -- whisker --help`  
**Exit code:** 0

```
whisker command-line entry point.

Commands:

    whisker [PID ...] [--all] [--json] [--no-write] [--gate {pass,review,fail}]
            [--reference ENGINE | --no-reference]
    whisker bench       --corpus DIR [--baseline FILE] [--out FILE]
    whisker guard       --corpus DIR --baseline FILE [--update] [--slack F]
                        [--fail-on-new] [--out FILE]
    whisker golden      --corpus DIR [--update] [--fail-on-new] [--out FILE]
    whisker facts       --corpus DIR [--strict] [--out FILE]
    whisker calibrate   --labels FILE [--target-fpr F] [--out FILE]
    whisker score-file  --md FILE [--ref FILE] [--source FILE] [--json]
    whisker check-facts --md FILE [--facts FILE] [--anchors FILE] [--json]
    whisker corpus      {stratify --corpus DIR | draft PID... --out DIR}
    whisker survey      {list | status [NAME] | run NAME [--refresh-runtime] [--out DIR]}

The three lanes: ``golden`` is Lane 1 STABILITY (did the normalized markdown
change vs a committed ``<pid>.expected.md`` snapshot); ``bench``/``guard`` are
Lane 2 FIDELITY (how close is the output to a ``<pid>.gt.md`` reference, via
nid/teds/mhs); ``facts`` is Lane 3 COMPREHENSION (can an LLM still read it, via
deterministic source-verified ``<pid>.facts.jsonl`` assertions, no LLM in the
loop). ``guard`` additionally folds in anchors and facts conjunctively.

``bench`` reports corpus means; ``guard`` is the per-paper regression gate that
diffs each paper's each axis against a committed baseline (slack/floors read from
the baseline itself; refresh with ``--update``; ``--fail-on-new`` blocks papers
not yet in the baseline); ``golden`` is the Lane 1 stability gate that compares
each paper's normalized markdown against a committed ``<pid>.expected.md``
snapshot (refresh with ``--update``); ``facts`` is the Lane 3 comprehension gate
(only ``checked: verified`` facts gate; ``--strict`` also gates drafts);
``calibrate`` fits the coverage edges from labeled data and reports
TPR/FPR/precision. ``score-file`` and ``check-facts`` are file-based entry points
(no paperstore backend required) used by ``tomd score`` / ``tomd bless`` via
subprocess. Typed exit codes (CI contract): 0 ok, 1 error, 3 review, 5 fail.
```

### 2.2 `whisker-tapetum-llm --help`

Command: `uv run --package whisker whisker-tapetum-llm --help`  
**Exit code:** 0

```
usage: whisker-tapetum-llm [-h] [--review-all] [--debug] [--trace] [--inspect]
                           [--exhaustive-units] [--all-pages]
                           [--workspace WORKSPACE] [--service SLOT=NAME]
                           [--concurrency N] [--fuse-only] [--text-only]
                           [--incremental] [--force] [--retry-errors]
                           [pids ...]

Advisory LLM conversion-fidelity adjudication.

positional arguments:
  pids                  Paper IDs to adjudicate (case-insensitive). If omitted
                        (and --review-all is not set), all converted papers
                        are adjudicated with automatic fingerprint-based skip.

options:
  -h, --help            show this help message and exit
  --review-all          Auto-select risk candidates from existing whisker
                        sidecars instead of running all converted papers.
  --debug               Write debug transcript.
  --trace               Write trace transcript.
  --inspect             Also write a readable side-by-side report (whisker vs
                        advisory) to whisker/llm/tapetum-inspect.md.
  --exhaustive-units    Check ALL routed units instead of capping at
                        MAX_UNIT_CHECKS. Use for golden-PR review where wall-
                        clock cost is acceptable. Implied by --inspect.
  --all-pages           Forces a scoped LLM unit check for EVERY physical PDF
                        page; PDF papers only; review-mode tool, not for fleet
                        runs. It implies exhaustive unit semantics.
  --workspace WORKSPACE
                        Override WG21_DATA_DIR.
  --service SLOT=NAME   Override a service slot, e.g. --service deep=alliance-
                        pod. Repeatable.
  --concurrency N       Adjudicate up to N papers concurrently (default 32).
                        Advisory lane only; results are persisted in input
                        order. Use 1 for a strictly serial run.
  --fuse-only           Recompute fusion blocks from existing sidecar pairs on
                        disk. No LLM calls. Useful after a whisker --all re-
                        run.
  --text-only           Force all papers through the markdown text lane,
                        skipping the PDF-text-layer judge lane for PDF papers.
  --incremental         Skip papers whose existing sidecar fingerprint matches
                        (same source, same markdown, same prompt, same lane
                        version). For explicit PIDs and --review-all this is
                        opt-in (off by default). The bare full-run (no PIDs,
                        no --review-all) enables incremental automatically;
                        use --force to override.
  --force               Re-evaluate every paper even when a fingerprint match
                        exists. Only meaningful in the default full-run mode
                        where incremental is on by default; ignored when
                        explicit PIDs or --review-all are given.
  --retry-errors        Re-evaluate papers whose previous run ended in an
                        error tombstone, even when the fingerprint matches.
                        Without this flag, error tombstones with valid
                        fingerprints are skipped like successful runs.
```

### 2.3 `whisker-readback --help`

Command: `uv run --package whisker whisker-readback --help`  
**Exit code:** 0

```
usage: whisker-readback [-h] --corpus CORPUS [--workspace WORKSPACE]
                        [--service SERVICE] [--out OUT] [--corrupt]
                        [--pid PID] [-v]

Blind LLM readback validation: send fact-derived questions to the alliance-pod
and verify comprehension.

options:
  -h, --help            show this help message and exit
  --corpus CORPUS       directory of <pid>.facts.jsonl files
  --workspace WORKSPACE
                        override $WG21_DATA_DIR
  --service SERVICE     SERVICES.toml service name (default: alliance-pod)
  --out OUT             directory for <pid>.readback.md artifacts
  --corrupt             run in adversarial mode (corrupt markdown, expect
                        failures)
  --pid PID             only run this PID (repeatable; default: all in corpus)
  -v, --verbose         show full pod answers in terminal output
```

---

## 3. Subcommands and flags (full `--help` capture)

### 3.1 Subcommand inventory

| Console script | Subcommand path | Positional args |
|---|---|---|
| `whisker` | *(default score)* | `[pids ...]` or `--all` |
| `whisker` | `bench` | — |
| `whisker` | `guard` | — |
| `whisker` | `golden` | — |
| `whisker` | `facts` | — |
| `whisker` | `calibrate` | — |
| `whisker` | `score-file` | — |
| `whisker` | `check-facts` | — |
| `whisker` | `corpus stratify` | — |
| `whisker` | `corpus draft` | `pid [pid ...]` |
| `whisker` | `survey list` | — |
| `whisker` | `survey status` | `[name]` |
| `whisker` | `survey install` | `name` |
| `whisker` | `survey run` | `name` |
| `whisker` | `survey purge` | — |
| `whisker` | `survey clean` | — |
| `whisker` | `survey reports` | — |
| `whisker-tapetum-llm` | *(flat, no subcommands)* | `[pids ...]` |
| `whisker-readback` | *(flat, no subcommands)* | — |

**Counts:** 19 distinct subcommand paths (including default score); 3 console scripts.

### 3.2 `whisker` default score — flags

Command: `uv run --package whisker -- whisker DUMMY --help`  
**Exit code:** 0

```
usage: whisker [-h] [--all] [--json] [-v] [-q] [--stats]
               [--reference {markitdown}] [--no-reference] [--no-write]
               [--report-dir REPORT_DIR] [--gate {pass,review,fail}]
               [--workspace WORKSPACE]
               [pids ...]

QA verdict for tomd conversions

positional arguments:
  pids                  paper ids to score

options:
  -h, --help            show this help message and exit
  --all                 score every paper in the store
  --json                emit JSON to stdout
  -v, --verbose         show every paper (incl. pass) and lift the per-section
                        cap
  -q, --quiet           print only the one-line summary footer
  --stats               append a flag rollup (counts per hard/soft flag)
  --reference {markitdown}
                        reference oracle: score tomd vs an independent
                        converter (default: markitdown)
  --no-reference        skip the reference oracle; use structural/coverage
                        signals only
  --no-write            do not write sidecars or the run report (stdout only)
  --report-dir REPORT_DIR
                        directory for sidecars + report.md/report.json
                        (default: <data>/whisker/det)
  --gate {pass,review,fail}
                        lowest verdict considered acceptable for exit 0
                        (default: review)
  --workspace WORKSPACE
                        override $WG21_DATA_DIR
```

**Flags:** `-h`, `--help`, `--all`, `--json`, `-v`, `--verbose`, `-q`, `--quiet`, `--stats`, `--reference`, `--no-reference`, `--no-write`, `--report-dir`, `--gate`, `--workspace`

### 3.3 `whisker bench --help`

**Exit code:** 0

```
usage: whisker bench [-h] --corpus CORPUS [--baseline BASELINE] [--out OUT]
                     [--workspace WORKSPACE]

Benchmark vs ground truth

options:
  -h, --help            show this help message and exit
  --corpus CORPUS       dir of <pid>.gt.md reference files
  --baseline BASELINE   prior leaderboard JSON to check regressions against
  --out OUT             write leaderboard JSON to this path
  --workspace WORKSPACE
                        override $WG21_DATA_DIR
```

**Flags:** `-h`, `--help`, `--corpus`, `--baseline`, `--out`, `--workspace`

### 3.4 `whisker guard --help`

**Exit code:** 0

```
usage: whisker guard [-h] --corpus CORPUS --baseline BASELINE [--update]
                     [--slack SLACK] [--fail-on-new] [--out OUT] [--json]
                     [--workspace WORKSPACE]

Per-paper regression gate over a ground-truth corpus

options:
  -h, --help            show this help message and exit
  --corpus CORPUS       dir of <pid>.gt.md reference files
  --baseline BASELINE   committed per-paper baseline JSON (read to diff, or
                        written with --update)
  --update              rewrite the baseline from the current run and exit 0
                        (the refresh ritual)
  --slack SLACK         max per-axis drop tolerated before a paper counts as
                        regressed; overrides the slack stored in the baseline
                        (default: from baseline, else 0.02)
  --fail-on-new         fail papers absent from the baseline (force an
                        explicit --update to admit them)
  --out OUT             write the guard report JSON to this path
  --json                emit the guard report JSON to stdout
  --workspace WORKSPACE
                        override $WG21_DATA_DIR
```

**Flags:** `-h`, `--help`, `--corpus`, `--baseline`, `--update`, `--slack`, `--fail-on-new`, `--out`, `--json`, `--workspace`

### 3.5 `whisker golden --help`

**Exit code:** 0

```
usage: whisker golden [-h] --corpus CORPUS [--update] [--fail-on-new]
                      [--out OUT] [--json] [--workspace WORKSPACE]

Lane 1 stability gate: exact compare vs committed snapshots

options:
  -h, --help            show this help message and exit
  --corpus CORPUS       dir of <pid>.expected.md snapshots and optional
                        <pid>.gt.md markers
  --update              rewrite <pid>.expected.md from the current run and
                        exit 0 (the bless ritual)
  --fail-on-new         fail papers with no committed snapshot (force an
                        explicit --update)
  --out OUT             write the golden report JSON to this path
  --json                emit the golden report JSON to stdout
  --workspace WORKSPACE
                        override $WG21_DATA_DIR
```

**Flags:** `-h`, `--help`, `--corpus`, `--update`, `--fail-on-new`, `--out`, `--json`, `--workspace`

### 3.6 `whisker facts --help`

**Exit code:** 0

```
usage: whisker facts [-h] --corpus CORPUS [--out OUT] [--json] [--strict]
                     [--workspace WORKSPACE]

Lane 3 comprehension gate: deterministic source-verified fact assertions

options:
  -h, --help            show this help message and exit
  --corpus CORPUS       dir of <pid>.facts.jsonl files
  --out OUT             write the facts report JSON to this path
  --json                emit the facts report JSON to stdout
  --strict              also fail when an UNVERIFIED (draft) fact fails
                        (default: only verified facts gate)
  --workspace WORKSPACE
                        override $WG21_DATA_DIR
```

**Flags:** `-h`, `--help`, `--corpus`, `--out`, `--json`, `--strict`, `--workspace`

### 3.7 `whisker calibrate --help`

**Exit code:** 0

```
usage: whisker calibrate [-h] --labels LABELS [--target-fpr TARGET_FPR]
                         [--out OUT] [--workspace WORKSPACE]

Fit content-coverage edges from labeled data (TPR/FPR/precision)

options:
  -h, --help            show this help message and exit
  --labels LABELS       JSON labels file: list of
                        {pid,label[,unigram_coverage]} or {pid: label}
  --target-fpr TARGET_FPR
                        max false-positive rate while maximizing recall
                        (default: 0.05)
  --out OUT             write the fitted thresholds JSON to this path
  --workspace WORKSPACE
                        override $WG21_DATA_DIR
```

**Flags:** `-h`, `--help`, `--labels`, `--target-fpr`, `--out`, `--workspace`

### 3.8 `whisker score-file --help`

**Exit code:** 0

```
usage: whisker score-file [-h] --md FILE [--ref FILE] [--source FILE] [--json]

options:
  -h, --help     show this help message and exit
  --md FILE      Candidate markdown file to score
  --ref FILE     Reference/ideal markdown for NID/TEDS/MHS/content_recall
  --source FILE  Source PDF or HTML for content-coverage and region detail
  --json         Emit JSON to stdout
```

**Flags:** `-h`, `--help`, `--md`, `--ref`, `--source`, `--json`

### 3.9 `whisker check-facts --help`

**Exit code:** 0

```
usage: whisker check-facts [-h] --md FILE [--facts FILE] [--anchors FILE]
                           [--strict] [--json]

options:
  -h, --help      show this help message and exit
  --md FILE       Markdown file to validate assertions against
  --facts FILE    JSONL facts file (whisker-facts format)
  --anchors FILE  JSON anchors file (whisker-anchors format)
  --strict        Also gate on draft facts (default: verified only)
  --json
```

**Flags:** `-h`, `--help`, `--md`, `--facts`, `--anchors`, `--strict`, `--json`

### 3.10 `whisker corpus --help`

**Exit code:** 0

```
usage: whisker corpus [-h] {stratify,draft} ...

Comprehension corpus authoring tools

positional arguments:
  {stratify,draft}
    stratify        list zero-coverage papers by structural stratum
    draft           generate draft .facts.jsonl for a paper

options:
  -h, --help        show this help message and exit
```

### 3.11 `whisker corpus stratify --help`

**Exit code:** 0

```
usage: whisker corpus stratify [-h] --corpus CORPUS [--workspace WORKSPACE]
                               [--max MAX]

options:
  -h, --help            show this help message and exit
  --corpus CORPUS       dir of <pid>.facts.jsonl
  --workspace WORKSPACE
                        override $WG21_DATA_DIR
  --max MAX             max per stratum
```

**Flags:** `-h`, `--help`, `--corpus`, `--workspace`, `--max`

### 3.12 `whisker corpus draft --help`

**Exit code:** 0

```
usage: whisker corpus draft [-h] --out OUT [--workspace WORKSPACE]
                            pid [pid ...]

positional arguments:
  pid                   paper ID(s)

options:
  -h, --help            show this help message and exit
  --out OUT             output dir for .facts.jsonl
  --workspace WORKSPACE
                        override $WG21_DATA_DIR
```

**Flags:** `-h`, `--help`, `--out`, `--workspace`

### 3.13 `whisker survey --help`

**Exit code:** 0

```
usage: whisker survey [-h] {list,status,install,run,purge,clean,reports} ...

Repeatable monthly competitor monitor. Converts corpus PDFs with tomd and a
registered competitor, scores all Whisker lanes, and generates a report.

positional arguments:
  {list,status,install,run,purge,clean,reports}
    list                List registered competitors
    status              Show last run, due status, and runtime state
    install             Build and verify a competitor runtime without running
                        a survey
    run                 Execute a complete monthly survey run
    purge               Remove runtime caches (venvs, models, legacy dirs)
    clean               Remove benchmark run bundles (keeps corpus and
                        protocol)
    reports             List generated reports and show where they are stored

options:
  -h, --help            show this help message and exit

Exit codes: 0 = ok/not due, 1 = error, 2 = due (status: last run > 30 days or
newer upstream version detected).
```

### 3.14–3.20 Survey nested `--help`

**`whisker survey list --help`** (exit 0): flags `-h`, `--help` only.

**`whisker survey status --help`** (exit 0): positional `[name]`; flags `-h`, `--help`.

**`whisker survey install --help`** (exit 0): positional `name`; flags `-h`, `--help`, `--force`.

**`whisker survey run --help`** (exit 0): positional `name`; flags `-h`, `--help`, `--refresh-runtime`, `--out`, `--pid`, `--mode`.

**`whisker survey purge --help`** (exit 0): flags `-h`, `--help`, `--dry-run`, `--yes`.

**`whisker survey clean --help`** (exit 0): flags `-h`, `--help`, `--dry-run`.

**`whisker survey reports --help`** (exit 0): flags `-h`, `--help`, `--open`.

### 3.21 Flag rollup (unique across all console scripts)

**Total unique long/short flags (excluding duplicate `-h`/`--help` per command): 55**

`--all`, `--all-pages`, `--anchors`, `--baseline`, `--concurrency`, `--corpus`, `--corrupt`, `--debug`, `--dry-run`, `--exhaustive-units`, `--facts`, `--fail-on-new`, `--force`, `--fuse-only`, `--gate`, `--incremental`, `--inspect`, `--json`, `--labels`, `--max`, `--md`, `--mode`, `--no-reference`, `--no-write`, `--open`, `--out`, `--pid`, `--ref`, `--reference`, `--refresh-runtime`, `--retry-errors`, `--review-all`, `--service`, `--slack`, `--source`, `--stats`, `--strict`, `--target-fpr`, `--text-only`, `--trace`, `--update`, `--workspace`, `--yes`, `-q`, `-v`, `--verbose`, `--quiet`

---

## 4. Phantom-command check (documentation vs CLI)

**Method:** Grep listed documentation sources for backticked tokens matching `` `whisker[a-z-]*` `` or `` `--[a-z][a-z0-9-]+` ``; compare to CLI flag/subcommand set from §3.  
**Sources:** `packages/whisker/src/whisker/CLAUDE.md`, `packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md`, `packages/whisker/corpus/README.md`, `packages/whisker/benchmark/README.md`, all `packages/whisker/**/README.md` (191 files), repo-root `CLAUDE.md`.

**Note:** `packages/whisker/research/repos/**/README.md` files are vendored third-party READMEs; they contribute hundreds of unrelated backticked `--flags` (marker, olmocr, firecrawl, etc.). Those are **not whisker CLI flags**. Below lists only **whisker-operator-relevant** documented-but-missing items (excluding `research/repos/`).

### 4.1 Documented (backticked) but not in whisker CLI

| Token | Doc file | Line | Quoted context |
|---|---|---|---|
| `--enable-prefix-caching` | `packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md` | 309 | ``Enabling `--enable-prefix-caching` on the vLLM server caches KV blocks...`` |
| `--append` | `packages/whisker/benchmark/tools/README.md` | 73 | ``with `--append` to merge the appendix`` (refers to `render_report.py`, not whisker) |
| `--headless` | `packages/whisker/benchmark/tools/README.md` | 145 | ``so `--headless=new` is tried first`` (Chromium flag for benchmark tooling) |
| `--config` | `packages/whisker/benchmark/tools/README.md` | 30 | ``run_campaign_v2.py --config balanced`` |
| `--smoke` | `packages/whisker/benchmark/README.md` | 167 | ``python tools/run_campaign_v2.py --smoke`` |
| `--pdf` | `packages/whisker/benchmark/tools/README.md` | 116 | ``render_report.py ... --pdf`` |

**Load-bearing finding (whisker docs):** only `--enable-prefix-caching` appears in whisker lane documentation (`tapetum_llm.md`) as if it were an operator flag; it is a **vLLM server** setting, not a `whisker-tapetum-llm` argument.

**False positives from regex on `` `whisker...` `` tokens:** prose fragments like `` `whisker core` ``, `` `whisker is` ``, `` `whisker-golden` `` (JSON kind string) match the pattern but are not CLI commands.

**Undocumented CLI surface in code (not backticked in docs):** `whisker compare` appears in `compare/cli.py` module docstring (`prog="whisker-compare"`) but has **no** console script and **no** routing in `whisker.__main__`.

### 4.2 In CLI but not backticked in whisker operator documentation

These flags exist in `--help` but do not appear as backticked tokens in `CLAUDE.md`, `tapetum_llm.md`, `corpus/README.md`, or `benchmark/README.md` (they may appear unbackticked or only in argparse help):

| Flag | CLI location |
|---|---|
| `--anchors` | `whisker check-facts` |
| `--facts` | `whisker check-facts` |
| `--labels` | `whisker calibrate` |
| `--md` | `whisker score-file`, `whisker check-facts` |
| `--ref` | `whisker score-file` |
| `--slack` | `whisker guard` |
| `--source` | `whisker score-file` |
| `--target-fpr` | `whisker calibrate` |

Many other CLI flags (`--all`, `--json`, `-v`, etc.) are documented **without** backticks in `CLAUDE.md` prose and code blocks.

---

## 5. Menu-only surface (`menu.py`)

Launched when bare `whisker` runs in a TTY (`__main__.py` lines 1315–1317).

| Menu # | Label | Dispatches to |
|---|---|---|
| 1 | Deterministic | `_score_main` (same as CLI score) |
| 2 | Deterministic + AI | `_score_main` then `tapetum_llm.cli.main` |
| 3 | LLM only | `tapetum_llm.cli.main` |
| 4 | Corpus Lanes | Submenu → `_golden_main`, `_facts_main`, `_bench_main`, `_guard_main`, or `_run_ideals_lane` |
| 5 | Last Report | `_show_last_report` |
| q | Quit | exit 0 |

### Actions reachable ONLY from the menu (no equivalent CLI subcommand)

1. **Last Report (menu 5)** — `_show_last_report`: reads `$WG21_DATA_DIR/whisker/det/report.md` and renders via Rich Markdown. No `whisker report` or similar subcommand.

2. **Ideals lane (corpus submenu 5)** — `_run_ideals_lane`: auto-discovers `packages/tomd/tests/fixtures/golden/ideals/`, lists stems via `golden_ideals.list_ideal_stems`, runs `_score_main` on those PIDs only. No `whisker ideals` subcommand.

Menu options 1–4 synthesize argv for existing CLI functions (`_score_main`, tapetum CLI, corpus lane mains) via interactive prompts (`_prompt_pids`, `_prompt_reference`, `_prompt_tapetum_scope`, `_prompt_tapetum_flags`).

---

## 6. Code without CLI / menu operator path

Reachability traced from console-script entry modules: `whisker.__main__`, `whisker.tapetum_llm.cli`, `whisker.tapetum_llm.readback_cli`, and `whisker.menu.run_menu` (via bare TTY `whisker`).

### 6.1 No operator path

| Module / package | How determined |
|---|---|
| `compare/` (all modules incl. `compare/cli.py`) | Not imported by any entry-point module. `compare/cli.py` defines `main()` with `prog="whisker-compare"` but is not in `[project.scripts]` and not routed from `__main__`. Used only by benchmark tools (`gen_compare_pdf.py`, `gen_appendix.py`). |
| `branding/` | Not imported from entry points. Used by benchmark `render_report.py` and compare render paths. |
| `tapetum_llm/vision.py` | Only imported by `vlm_pipeline.py` (line 27). |
| `tapetum_llm/vision_task.py` | Imported by `transcribe.py` and `vlm_pipeline.py`; not reachable from `cli.py` / `adjudicate.py` / `pdf_judge.py` import chain. |
| `tapetum_llm/transcribe.py` | Only imported by `vlm_pipeline.py`. |
| `tapetum_llm/vlm_diff.py` | Only imported by `vlm_pipeline.py`. |
| `tapetum_llm/vlm_pipeline.py` | No production importer from entry points; library-only dormant VLM path. |
| `tapetum_llm/payload_scope.py` | No imports from production code; only `tests/test_payload_scope.py`. |

### 6.2 Reachable from operator paths (summary)

- **Core deterministic lane:** `score`, `bench`, `guard`, `golden`, `facts`, `calibrate`, `corpus_tools`, `gates`, `metrics`, `match`, `reference`, `report`, `anchors`, `tables`, `golden_ideals` ← `__main__` / `menu`.
- **Survey:** `survey/*` ← `__main__` → `survey.cli.survey_main`.
- **Tapetum LLM (active):** `adjudicate`, `pdf_judge`, `unit_judge`, `judge_task`, `fusion`, `fusion_report`, `inspect_report`, `ideal_verify`, `source_router`, `html_outline`, `textlayer`, `metadata_compare`, `table_compare`, `grounding`, `chunking`, `models`, `constants` ← `tapetum_llm.cli` import chain.
- **Readback:** `readback` ← `readback_cli`.

---

## Summary counts

| Metric | Value |
|---|---|
| Console scripts | 3 |
| Subcommand paths | 19 |
| Unique CLI flags | 55 |
| Documented-but-missing (whisker-operator docs, backticked) | 1 load-bearing (`--enable-prefix-caching`); 5 benchmark-tool flags in benchmark READMEs |
| CLI-but-not-backticked in operator docs | 8 flags (see §4.2) |
| Menu-only actions | 2 (`Last Report`, `Ideals lane`) |
| Module trees with no operator path | `compare/`, `branding/`, VLM chain (`vision*`, `vlm_*`, `transcribe`), `payload_scope.py` |
