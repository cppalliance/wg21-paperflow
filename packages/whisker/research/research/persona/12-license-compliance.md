# 12 - The License / Compliance Auditor

**Verdict:** usable-with-conditions — the GPL `levenshtein` dependency is gone from code and lockfile, all nine declared PyPI deps are permissive-license-compatible with BSL-1.0, and every production/test `.py` carries the BSL header; distribution still needs a consolidated third-party NOTICE for Apache-2.0 verbatim ports and a manifest-level GPL guard beyond the current import lint.
**Confidence:** high

## Findings

- [CRITICAL] **No GPL `levenshtein` import or lock entry survives in production code.** Evidence: `grep` over `packages/whisker/src` finds zero `import Levenshtein` / `from Levenshtein` / `import levenshtein`; edit distance uses `from rapidfuzz.distance import Levenshtein as _Lev` at `metrics.py:41`, `match.py:37`, `facts.py:42`; `uv.lock` has no `levenshtein` package; `pyproject.toml:17` pins `rapidfuzz>=3.14.5,<4` only. `CHANGELOG.md:96-101` documents the 0.5.0 swap; `test_edit_distance_parity.py:56-70` lint-bans GPL reintroduction in `src/whisker`. Impact: the documented license fix is **verified in the runtime path**; BSL distribution is not blocked by the former GPL-2.0 C extension.

- [HIGH] **Apache-2.0 verbatim ports lack package-level attribution required for redistribution.** Evidence: `metrics.py:394-399` states TEDS is a "verbatim port" of OmniDocBench/PubTabNet (`Apache-2.0, IBM peter.zhong`) with only privatized names and a zero-denominator guard changed; `match.py:8-24` ports `match_quick` from the same upstream with path citations but **no license line**; `metrics.py:88-91` and `129-133` port OmniDocBench text normalizers verbatim. No `NOTICE`, `THIRD_PARTY_NOTICES`, or `LICENSE` file exists under `packages/whisker/` (glob returns zero). Impact: BSL + Apache-2.0 **can** be combined, but shipping whisker wheels/sdists without reproducing upstream copyright + Apache-2.0 license text is an **attribution compliance gap**, not a copyleft infection; legal review would flag before public release.

- [HIGH] **GPL lint covers import lines in `src/whisker` only, not the dependency manifest.** Evidence: `test_edit_distance_parity.py:58-66` scans `src/whisker/*.py` for `import Levenshtein` / `from Levenshtein` only; it does not inspect `pyproject.toml`, `uv.lock`, or transitive wheels. Stale research still documents the old dep: `research/buildvsbuy/text-edit-distance.md:25` claims `levenshtein>=0.25.1` in `pyproject.toml:10` (line 10 is now `grits-metric`). Impact: a future re-add of `levenshtein` to `pyproject.toml` would **pass 353 tests** while reintroducing GPL at install time; compliance trust in CI is partial.

- [MED] **All nine declared direct dependencies are permissive and BSL-compatible.** Evidence: `pyproject.toml:8-19` — apted (MIT), grits-metric (MIT, `CHANGELOG.md:104-105`), lxml (BSD-style), markitdown[pdf] (MIT; pdf extra pulls `pdfminer-six` + `pdfplumber` per `uv.lock:1840-1843`, both MIT), mistune~=3.2 (BSD-3), numpy (BSD), pylatexenc (MIT), rapidfuzz (MIT), scipy (BSD). Resolved pins: `uv.lock:227` apted 1.0.3, `:1157` grits-metric 0.6.0, `:1666` lxml 6.1.0, `:1823` markitdown 0.1.6, `:1962` mistune 3.2.0, `:2118` numpy 2.4.6, `:3138` pylatexenc 2.10, `:3355` rapidfuzz 3.14.5, `:3758` scipy 1.17.1. Impact: **no copyleft among the audited direct deps**; BSL-1.0 distribution of whisker itself is not contradicted by this dependency set.

- [MED] **Transitive tree via `grits-metric` and `markitdown` adds only permissive licenses among audited packages.** Evidence: `uv.lock:1160-1163` grits-metric → `pylcs` + `scipy`; `:3144-3148` pylcs → `pybind11` (BSD); markitdown base deps include `magika` (`:1763`, Apache-2.0, compatible with BSL). Impact: advisory `grits_con` axis does not inject GPL; Apache-2.0 magika is another attribution item for a full SBOM, not a blocking incompatibility.

- [MED] **Every production and test `.py` under `src/` and `tests/` has the BSL-1.0 header.** Evidence: 15 unique modules in `packages/whisker/src/whisker/` (e.g. `metrics.py:1-6`, `calibrate.py:1-6`, `score.py:1-6`) and 14 test files (e.g. `test_edit_distance_parity.py:1-6`, `test_golden.py:1-6`) each open with "Distributed under the Boost Software License, Version 1.0"; `CLAUDE.md:285` invariant matches practice. Impact: **header hygiene is complete** on shipped code; no orphan modules break the stated invariant.

- [LOW] **`tomd` (whisker dep, not in the nine-name audit list) pulls AGPL PyMuPDF transitively.** Evidence: `pyproject.toml:19` depends on `tomd`; `packages/tomd/pyproject.toml:10` pins `pymupdf~=1.27.0`; `uv.lock:4074` resolves pymupdf 1.27.2.3 into whisker's lock closure. Whisker imports tomd read-only (`CLAUDE.md:56-57`). Impact: **outside the nine direct deps** but present in a full `uv sync` install; AGPL is a workspace-level copyleft concern for paperflow, not introduced by whisker's own PyPI declarations; `--no-reference` avoids markitdown but not tomd QA imports.

- [LOW] **Stale build-vs-buy research contradicts live licensing facts.** Evidence: `research/buildvsbuy/text-edit-distance.md:25,98-99,105` still prescribe `levenshtein>=0.25.1` and `import Levenshtein`; `research/buildvsbuy/teds-tables.md:28` lists `levenshtein>=0.25.1` in pyproject. Live `pyproject.toml` has no such entry. Impact: misleads future contributors into reintroducing GPL; does not affect runtime.

## False-pass hypothesis

A maintainer adds `"levenshtein>=0.25.1"` back to `pyproject.toml` (following stale `research/buildvsbuy/text-edit-distance.md:105`) while keeping `rapidfuzz` in source: `test_no_gpl_levenshtein_import` (`test_edit_distance_parity.py:56-70`) still passes because it never reads the manifest, `uv run pytest packages/whisker/tests -q` stays green (`00-EVIDENCE-BASELINE.md` §2: 353 passed), and CI would ship a GPL transitive dependency while the CHANGELOG claim at `CHANGELOG.md:96-101` remains nominally true in source-only terms.

## False-fail hypothesis

none found — no license-incompatible direct dependency or missing header currently blocks BSL distribution of whisker's own code; the open items are attribution/documentation gaps, not hard copyleft blockers among the nine named deps.

## What would change my mind

A machine-generated SPDX SBOM from `uv lock` / `uv pip compile` showing **zero GPL/AGPL packages** in whisker's isolated dependency closure **plus** a committed `THIRD_PARTY_NOTICES` (or equivalent) reproducing Apache-2.0 copyright + license text for the OmniDocBench/PubTabNet TEDS, `match_quick`, and text-normalizer ports cited at `metrics.py:394-399` and `match.py:23-24` would flip the verdict to **usable** with no conditions.
