# Whisker Auditv3 — Dependencies, Packaging, License (raw evidence)

Audit target: current working tree. No modifications made during collection.

---

## Task 1 — `packages/whisker/pyproject.toml` (verbatim fields)

### version

```
0.5.0
```

### license field

```
license = {text = "BSL-1.0"}
```

### requires-python

```
requires-python = ">=3.12"
```

### dependencies (core)

```toml
dependencies = [
    "apted>=1.0.3",
    "grits-metric>=0.6.0",
    "lxml>=5.0.0",
    "markitdown[pdf]>=0.1.6",
    "mistune~=3.2.0",
    "numpy>=1.26",
    "paperstore",
    "pylatexenc>=2.10",
    "rapidfuzz>=3.14.5,<4",
    "rich>=13.0",
    "scipy>=1.11",
    "tomd",
]
```

### `[project.optional-dependencies]` (all groups)

Only one group is declared:

```toml
[project.optional-dependencies]
# Opt-in advisory LLM lane. Keeps the whisker core install LLM-free and
# standalone: `pip install whisker[tapetum-llm]` pulls the pipeline framework.
tapetum-llm = [
    "openai",
    "pipeline",
    "pydantic-ai",
    "pydantic>=2.0",
    "python-dotenv>=1.0",
]
```

### `[tool.uv.sources]`

**Not present in `packages/whisker/pyproject.toml`.** The whisker package pyproject ends at line 54 (hatch force-include entries).

Workspace `[tool.uv.sources]` lives in repo-root `pyproject.toml`:

```toml
[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
paperstore   = {workspace = true}
mailing      = {workspace = true}
tomd         = {workspace = true}
pipeline     = {workspace = true}
agora        = {workspace = true}
assay        = {workspace = true}
cli          = {workspace = true}
preview      = {workspace = true}
cpp-mcp      = {workspace = true}
scrivener  = {git = "https://github.com/gregjkal/wg21-scrivener.git"}
```

Whisker core dependencies that resolve via workspace sources: `paperstore`, `tomd`. `pipeline` is workspace-sourced but only via the `tapetum-llm` extra, not core deps.

---

## Task 2 — Core/extra isolation (LLM stack imports)

### Command: `rg -n "^\s*(import|from)\s+(pipeline|openai|pydantic_ai|httpx|dotenv)" packages/whisker/src/whisker --glob "!tapetum_llm/**"`

Exit code: **0**

```
packages/whisker/src/whisker\tapetum_llm\cli.py:35:import httpx
packages/whisker/src/whisker\tapetum_llm\cli.py:37:from dotenv import find_dotenv, load_dotenv
packages/whisker/src/whisker\tapetum_llm\cli.py:39:from pipeline import AgentBackend, PipelinePrompt, write_debug_file
packages/whisker/src/whisker\tapetum_llm\cli.py:40:from pipeline.services import load_services
packages/whisker/src/whisker\tapetum_llm\adjudicate.py:28:from pipeline import (
packages/whisker/src/whisker\tapetum_llm\adjudicate.py:38:from pipeline.services import load_services
packages/whisker/src/whisker\tapetum_llm\readback.py:35:import httpx
packages/whisker/src/whisker\tapetum_llm\pdf_judge.py:44:from pipeline import AgentBackend
packages/whisker/src/whisker\tapetum_llm\pdf_judge.py:45:from pipeline.tools import guard_instruction, inject_untrusted
packages/whisker/src/whisker\tapetum_llm\vision_task.py:41:import openai
packages/whisker/src/whisker\tapetum_llm\vision_task.py:42:from openai import AsyncOpenAI
packages/whisker/src/whisker\tapetum_llm\judge_task.py:43:from pipeline import AgentBackend
packages/whisker/src/whisker\tapetum_llm\readback_cli.py:26:from dotenv import find_dotenv, load_dotenv
packages/whisker/src/whisker\tapetum_llm\ideal_verify.py:15:from pipeline import AgentBackend
packages/whisker/src/whisker\tapetum_llm\ideal_verify.py:16:from pipeline.tasks import run_task
packages/whisker/src/whisker\tapetum_llm\ideal_verify.py:17:from pipeline.tools import guard_instruction, inject_untrusted
packages/whisker/src/whisker\tapetum_llm\unit_judge.py:30:from pipeline import AgentBackend
packages/whisker/src/whisker\tapetum_llm\unit_judge.py:31:from pipeline.tools import guard_instruction, inject_untrusted
```

**Note:** On this Windows shell, `--glob "!tapetum_llm/**"` did **not** exclude `tapetum_llm/` paths; all hits are under `tapetum_llm/`.

### Supplemental core-only scan (Python, excludes any path containing `tapetum_llm`)

Command:

```
uv run python -c "..."  # regex ^\s*(import|from)\s+(pipeline|openai|pydantic_ai|httpx|dotenv)\b, skip tapetum_llm paths
```

Exit code: **0**

```
HITS_OUTSIDE_TAPETUM_LLM: 0
```

### Command: `rg -n "import (pipeline|openai|pydantic_ai)" packages/whisker/src/whisker`

Exit code: **0**

```
packages/whisker/src/whisker\tapetum_llm\vision_task.py:41:import openai
```

### Related deferred import in core (not matching the regex above)

`packages/whisker/src/whisker/menu.py:38`:

```python
        importlib.import_module(_TAPETUM_LLM_PKG)
```

where `_TAPETUM_LLM_PKG = "whisker.tapetum_llm.cli"` (lines 32–38). This is a runtime probe for optional extra availability, not a direct `import pipeline` / `import openai` / `import pydantic_ai`.

### Empirical import test

Command:

```
uv run --package whisker python -c "import whisker; print(sorted(n for n in dir(whisker) if not n.startswith('_')))"
```

Exit code: **0**

```
['AnchorCheck', 'AnchorReport', 'AnchorSpec', 'BenchRow', 'CalibrationResult', 'Fact', 'FactCheck', 'FactReport', 'GateResult', 'GoldenFinding', 'GoldenItem', 'GoldenReport', 'GuardFinding', 'GuardReport', 'IdealPanel', 'OperatingPoint', 'REFERENCE_ENGINES', 'VERDICT_FAIL', 'VERDICT_PASS', 'VERDICT_REVIEW', 'WhiskerResult', 'aggregate', 'anchor_spec_from_dict', 'anchors', 'baseline_from_rows', 'bench', 'block_text_nid', 'build_report', 'calibrate', 'calibrate_threshold', 'check_anchors', 'check_facts', 'collect_tool_versions', 'constants', 'diff_goldens', 'diff_rows', 'facts', 'facts_from_records', 'find_ideals_dir', 'gates', 'golden', 'golden_ideals', 'guard', 'ideal_path', 'list_ideal_stems', 'match', 'metrics', 'mhs', 'normalize_for_exact_lane', 'normalized_edit_distance', 'parse_facts_jsonl', 'reading_order_ned', 'reference', 'reference_markdown', 'render_report_md', 'render_summary', 'report', 'run_bench', 'run_gates', 'score', 'score_against_ideal', 'score_markdown', 'score_paper', 'sidecar_path', 'tables', 'teds', 'text_nid', 'whisker_output_dir']
```

---

## Task 3 — Wheel build and contents

### Command: `uv build --package whisker --wheel`

Exit code: **0**

```
Building wheel...
Successfully built dist\whisker-0.5.0-py3-none-any.whl
```

Produced filename: **`dist\whisker-0.5.0-py3-none-any.whl`**

### Command: wheel contents listing

```
uv run python -c "import zipfile,glob; wh=sorted(glob.glob('dist/whisker-*.whl'))[-1]; z=zipfile.ZipFile(wh); names=sorted(z.namelist()); print('WHEEL:', wh); print('TOTAL:', len(names)); print('\n'.join(names))"
```

Exit code: **0**

```
WHEEL: dist\whisker-0.5.0-py3-none-any.whl
TOTAL: 80
whisker-0.5.0.dist-info/METADATA
whisker-0.5.0.dist-info/RECORD
whisker-0.5.0.dist-info/WHEEL
whisker-0.5.0.dist-info/entry_points.txt
whisker/CLAUDE.md
whisker/__init__.py
whisker/__main__.py
whisker/anchors.py
whisker/bench.py
whisker/branding/__init__.py
whisker/branding/assets/LAYOUT-PATTERN.md
whisker/branding/assets/LAYOUT-REFERENCE.pdf
whisker/branding/assets/alliance.css
whisker/branding/assets/cppalliance-logo.png
whisker/branding/markdown.py
whisker/branding/pdf.py
whisker/branding/theme.py
whisker/calibrate.py
whisker/compare/__init__.py
whisker/compare/align.py
whisker/compare/blocks.py
whisker/compare/cli.py
whisker/compare/exhibits.py
whisker/compare/render_appendix.py
whisker/compare/render_html.py
whisker/compare/render_pdf.py
whisker/constants.py
whisker/corpus_tools.py
whisker/facts.py
whisker/gates.py
whisker/golden.py
whisker/golden_ideals.py
whisker/guard.py
whisker/match.py
whisker/menu.py
whisker/metrics.py
whisker/reference.py
whisker/report.py
whisker/score.py
whisker/survey/__init__.py
whisker/survey/adapters/__init__.py
whisker/survey/adapters/contract.py
whisker/survey/adapters/marker.py
whisker/survey/cli.py
whisker/survey/history.py
whisker/survey/locks/__init__.py
whisker/survey/locks/marker.lock.json
whisker/survey/registry.py
whisker/survey/report.py
whisker/survey/runner.py
whisker/survey/runtime.py
whisker/tables.py
whisker/tapetum_llm/__init__.py
whisker/tapetum_llm/adjudicate.py
whisker/tapetum_llm/chunking.py
whisker/tapetum_llm/cli.py
whisker/tapetum_llm/constants.py
whisker/tapetum_llm/fusion.py
whisker/tapetum_llm/fusion_report.py
whisker/tapetum_llm/grounding.py
whisker/tapetum_llm/html_outline.py
whisker/tapetum_llm/ideal_verify.py
whisker/tapetum_llm/inspect_report.py
whisker/tapetum_llm/judge_task.py
whisker/tapetum_llm/metadata_compare.py
whisker/tapetum_llm/models.py
whisker/tapetum_llm/payload_scope.py
whisker/tapetum_llm/pdf_judge.py
whisker/tapetum_llm/readback.py
whisker/tapetum_llm/readback_cli.py
whisker/tapetum_llm/source_router.py
whisker/tapetum_llm/table_compare.py
whisker/tapetum_llm/tapetum_llm.md
whisker/tapetum_llm/textlayer.py
whisker/tapetum_llm/transcribe.py
whisker/tapetum_llm/unit_judge.py
whisker/tapetum_llm/vision.py
whisker/tapetum_llm/vision_task.py
whisker/tapetum_llm/vlm_diff.py
whisker/tapetum_llm/vlm_pipeline.py
```

**Total file count in wheel:** 80

**Flagged entries (should-not-ship categories):**

| Category | Present in wheel? | Paths |
|---|---|---|
| Test files | **No** | (none) |
| `research/repos/` clones | **No** | (none) |
| Research `.md` docs (non-package) | **Partial** | `whisker/CLAUDE.md`, `whisker/tapetum_llm/tapetum_llm.md` ship as package-internal docs |
| Caches / notebooks | **No** | (none) |
| Intentionally force-included asset doc | **Yes** | `whisker/branding/assets/LAYOUT-PATTERN.md` (declared in `[tool.hatch.build.targets.wheel.force-include]`) |

**Additional packaging fact:** entire `whisker/tapetum_llm/` subtree (27 Python modules + `tapetum_llm.md`) ships in the core wheel despite LLM runtime deps being optional extra only.

---

## Task 4 — Lock honesty

### `uv.lock` at repo root

Command:

```
if (Test-Path uv.lock) { Write-Output "uv.lock exists: YES" ; (Get-Item uv.lock).Length }
```

Exit code: **0**

```
uv.lock exists: YES
806829
```

### Command: `uv lock --check`

Exit code: **0**

```
Resolved 249 packages in 7ms
```

No drift reported.

---

## Task 5 — Dependency licenses (machine metadata)

Command:

```
uv run --package whisker python -c "import importlib.metadata as m; ..."
```

Exit code: **0**

### CORE

```
apted	MIT
grits-metric	MIT
lxml	BSD-3-Clause
markitdown	MIT
mistune	BSD-3-Clause
numpy	BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0
paperstore	BSL-1.0
pylatexenc	MIT
rapidfuzz	MIT
rich	MIT
scipy	Copyright (c) 2001-2002 Enthought, Inc. 2003, SciPy Developers. ... [truncated; full text in wheel metadata]
tomd	BSL-1.0
```

(`scipy` `License` metadata field is multi-kilobyte BSD-3-Clause text plus bundled third-party notices; truncated in script output at 120 chars of first line.)

### EXTRA (`tapetum-llm`)

```
openai	Apache-2.0
pipeline	BSL-1.0
pydantic-ai	MIT
pydantic	MIT
python-dotenv	BSD-3-Clause
```

### GPL-family flag (core dependency set)

No core dependency reports `License` or `License-Expression` starting with a GPL-family SPDX identifier as its primary package license in the fields above.

**Note on `scipy`:** installed metadata `License` field embeds bundled-binary notices that mention `GPL-3.0-or-later WITH GCC-exception-3.1` for bundled GCC runtime library components inside SciPy wheels; the SciPy project license text itself is BSD-3-Clause (Enthought/SciPy Developers header).

---

## Task 6 — BSL-1.0 headers in core Python sources

Scope: `packages/whisker/src/whisker/**/*.py`

Command:

```
uv run python -c "from pathlib import Path; ... BSL-1.0 or Boost Software License in first 15 lines ..."
```

Exit code: **0**

```
TOTAL_PY: 69
WITH_BSL_HEADER: 69
MISSING_BSL_HEADER: 0
--- MISSING FILES ---
```

**Files missing BSL header:** (none)

---

## Task 7 — `packages/whisker/THIRD_PARTY_NOTICES.md`

### Exists?

**Yes** — `packages/whisker/THIRD_PARTY_NOTICES.md`

### Full file contents (verbatim)

```markdown
# Third-party notices

## langextract (Apache-2.0)

`src/whisker/tapetum_llm/grounding.py` contains a Python re-implementation of
the monotonic exact-occurrence alignment DP from Google's langextract project
(`langextract/resolver.py`, `_select_monotonic_matches` and its application),
Copyright Google LLC, licensed under the Apache License, Version 2.0
(<https://www.apache.org/licenses/LICENSE-2.0>).

The port is algorithm-only: no langextract code is imported at runtime, no
dependency was added. langextract's LCS fuzzy-alignment tier was deliberately
not ported.

Source: <https://github.com/google/langextract> @ 0dff5479 (v1.6.0).
```

### Named ported metric implementations (audit checklist)

| Implementation | Named in THIRD_PARTY_NOTICES? |
|---|---|
| TEDS | **No** (documented in `metrics.py` comments as OmniDocBench/PubTabNet port) |
| GriTS | **No** (core dep `grits-metric`, not a port notice) |
| APTED | **No** (core dep `apted`, used by TEDS/MHS; not a port notice) |
| OmniDocBench | **No** (referenced in `metrics.py` comments only) |
| langextract | **Yes** |
| markitdown | **No** (core runtime dependency, not a port notice) |

### pyproject dependencies absent from THIRD_PARTY_NOTICES

**Core dependencies (all absent):**

- apted
- grits-metric
- lxml
- markitdown (with `[pdf]` extra)
- mistune
- numpy
- paperstore
- pylatexenc
- rapidfuzz
- rich
- scipy
- tomd

**Extra `tapetum-llm` dependencies (all absent):**

- openai
- pipeline
- pydantic-ai
- pydantic
- python-dotenv
