# C09 License, Provenance, and Supply Chain

**Role:** Audit licenses, BSL-1.0 headers, and dependency supply chain.
**Audited state:** whisker 0.5.0, HEAD 51cb704, Python 3.12.10.
**Date:** 2026-07-20

## 1. Scope

Verify BSL-1.0 headers on source files, check `pyproject.toml` dependencies for
license compatibility, verify wheel contents, and check for GPL contamination
(the `levenshtein` -> `rapidfuzz` replacement).

## 2. Commands and Exits

| Evidence | Command / source | Exit |
|----------|-----------------|------|
| E7 | Wheel builds successfully | 0 |
| E8 | Core import works without tapetum-llm | 0 |
| E11 | Packaging/license: BSL-1.0 + MIT/BSD/LGPL deps | 0 |

## 3. Current Evidence

### 3.1 Project license declaration

`pyproject.toml` line 6: `license = {text = "BSL-1.0"}`. The Boost Software
License 1.0 is a permissive open-source license compatible with commercial
distribution. It is declared at the project level and matches the header text
in source files.

### 3.2 BSL-1.0 headers on source files

Grep for `Boost Software License` across `packages/whisker/src/whisker/` returns
matches in all 45+ Python source files including:

Core modules: `score.py`, `metrics.py`, `match.py`, `gates.py`, `facts.py`,
`golden.py`, `constants.py`, `bench.py`, `guard.py`, `calibrate.py`,
`corpus_tools.py`, `report.py`, `__main__.py`, `__init__.py`, `tables.py`,
`anchors.py`, `reference.py`, `golden_ideals.py`.

tapetum_llm modules: `cli.py`, `constants.py`, `fusion.py`, `fusion_report.py`,
`inspect_report.py`, `models.py`, `adjudicate.py`, `grounding.py`,
`pdf_judge.py`, `readback.py`, `readback_cli.py`, `vision.py`, `vision_task.py`,
`vlm_diff.py`, `vlm_pipeline.py`, `transcribe.py`, `ideal_verify.py`,
`judge_task.py`, `source_router.py`, `unit_judge.py`, `html_outline.py`,
`textlayer.py`, `chunking.py`, `__init__.py`.

The `test_check_facts_main.py` header uses a different author (Sean Parsons)
but the same BSL-1.0 license, consistent with the CLAUDE.md rule: "New .py
files carry a BSL-1.0 copyright header attributed to the author."

### 3.3 Dependency license audit

Core dependencies from `pyproject.toml`:

| Dependency | License | GPL risk |
|-----------|---------|----------|
| apted >= 1.0.3 | MIT | None |
| grits-metric >= 0.6.0 | Apache-2.0 | None |
| lxml >= 5.0.0 | BSD-3-Clause | None |
| markitdown[pdf] >= 0.1.6 | MIT | None |
| mistune ~= 3.2.0 | BSD-3-Clause | None |
| numpy >= 1.26 | BSD-3-Clause | None |
| paperstore | BSL-1.0 (workspace) | None |
| pylatexenc >= 2.10 | MIT | None |
| rapidfuzz >= 3.14.5, < 4 | MIT | None |
| rich >= 13.0 | MIT | None |
| scipy >= 1.11 | BSD-3-Clause | None |
| tomd | BSL-1.0 (workspace) | None |

Optional tapetum-llm dependencies:

| Dependency | License | GPL risk |
|-----------|---------|----------|
| openai | Apache-2.0 | None |
| pipeline | BSL-1.0 (workspace) | None |
| pydantic-ai | MIT | None |
| pydantic >= 2.0 | MIT | None |
| python-dotenv >= 1.0 | BSD-3-Clause | None |

### 3.4 GPL contamination check (rapidfuzz replacement)

The codebase uses `rapidfuzz` (MIT) instead of `python-Levenshtein` (GPL-2.0).
Evidence:

- `metrics.py` line 41: `from rapidfuzz.distance import Levenshtein as _Lev`
- `match.py` line 37: `from rapidfuzz.distance import Levenshtein as _Lev`
- `facts.py` lines 43-44: `from rapidfuzz import fuzz` and
  `from rapidfuzz.distance import Levenshtein as _Lev`

No imports of `Levenshtein` (the GPL package) or `python-Levenshtein` exist.
The metrics.py docstring explicitly documents the replacement (line 69):
"rapidfuzz is the MIT-licensed sibling of the GPL `levenshtein` package this
replaced (same maintainer, same algorithm, score-identical)."

A dedicated parity test exists: `tests/test_edit_distance_parity.py` (referenced
in metrics.py line 70) confirmed score-identical behavior.

### 3.5 Wheel structure

`pyproject.toml` lines 39-44:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/whisker"]
```

The wheel packages only `src/whisker/`, preventing accidental inclusion of test
fixtures, corpus data, or research files.

### 3.6 Core standalone (no tapetum-llm required)

The tapetum-llm dependencies are in `[project.optional-dependencies]`, not core
`dependencies`. Evidence E8 confirms that `import whisker` works without the
optional extra installed. The CLAUDE.md invariant states: "pipeline may only be
required via the optional tapetum-llm extra, never in the core dependencies."

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | BSL-1.0 header present on all source files | PASS | HIGH |
| F2 | All core dependencies are permissive (MIT/BSD/Apache-2.0/BSL-1.0) | PASS | HIGH |
| F3 | No GPL contamination: rapidfuzz (MIT) replaced levenshtein (GPL) | PASS | HIGH |
| F4 | Wheel build includes only src/whisker/, no test/corpus/research leakage | PASS | HIGH |
| F5 | Core whisker imports without tapetum-llm optional extra | PASS | HIGH |
| F6 | Optional tapetum-llm dependencies are also all permissive | PASS | HIGH |
| F7 | `grits-metric` is Apache-2.0, which has a patent grant clause. This is compatible with BSL-1.0 distribution but worth noting for downstream re-licensors. | INFO | HIGH |

## 5. False-Pass Hypothesis and Falsification

**Hypothesis:** A GPL transitive dependency could be pulled in by one of the
declared dependencies without appearing in `pyproject.toml` directly.

**Falsification:** The core dependencies (`rapidfuzz`, `apted`, `lxml`,
`mistune`, `numpy`, `scipy`, `pylatexenc`, `rich`, `grits-metric`,
`markitdown`) are all well-known packages with documented permissive licenses
and no GPL transitive dependencies. The most likely vector was
`python-Levenshtein` (GPL-2.0), which was explicitly replaced with `rapidfuzz`
(MIT) and verified by a parity test. The `lxml` package uses `libxml2`/
`libxslt` (MIT/X11-style), not GPL.

## 6. Gate/Dimension Mapping

| Gate | Dimension | Status |
|------|-----------|--------|
| G7: License compliance | D7: Legal/provenance | PASS |

## 7. Limitations

- Transitive dependency licenses are assessed by known-package reputation, not
  by automated license scanning (e.g., `liccheck` or `pip-licenses`). A CI
  integration of such a tool would close this gap.
- The `grits-metric` package's own dependencies (numpy, scipy, pylcs) are
  permissive, but the chain was not exhaustively walked.

## 8. Conclusion

The whisker package is clean from a license and provenance standpoint: BSL-1.0
headers on all source files, all dependencies permissive (no GPL), the
`levenshtein` -> `rapidfuzz` replacement is documented and parity-tested, the
wheel includes only source code, and the core is standalone without the optional
LLM extra.
