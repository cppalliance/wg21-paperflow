# 02 - License-Compliance

**Verdict:** usable-with-conditions — every audited whisker dependency is permissive (MIT/BSD) and GPL `levenshtein` is gone, but Apache-2.0 verbatim OmniDocBench/PubTabNet TEDS and text-normalizer ports ship without a consolidated third-party NOTICE, leaving a redistribution attribution gap on an otherwise clone-and-replicate-safe stack.
**Confidence:** high

## Findings

- [HIGH] **Apache-2.0 verbatim OmniDocBench/PubTabNet code is ported into `metrics.py` and `match.py` without upstream copyright reproduction in a NOTICE file.** Evidence: `metrics.py:394-399` documents a "verbatim port" of TEDS (`Apache-2.0, IBM peter.zhong`); `metrics.py:88-96` and `129-133` port the text-axis normalizer verbatim; `match.py:23-24` ports `match_quick` from the same upstream tree. Workspace glob finds no `NOTICE` or `THIRD_PARTY_NOTICES` (only root `LICENSE_1_0.txt`). OmniDocBench upstream is Apache-2.0 (https://github.com/opendatalab/OmniDocBench). Impact: BSL-1.0 + Apache-2.0 **combine legally**, but public redistribution of the monorepo without reproducing upstream copyright + license text fails Apache §4(c); this is attribution hygiene, not copyleft infection.

- [HIGH] **All six mandated PyPI dependencies are permissive and do not forbid BSL-1.0 public shipping.** Evidence: `pyproject.toml:9-17` declares apted, grits-metric, mistune, pylatexenc, rapidfuzz; runtime metadata (2026-07-06): apted MIT, rapidfuzz MIT, pylatexenc MIT, mistune BSD-3-Clause, grits-metric MIT; `bench.py:47` imports grits as an advisory axis only. Impact: no dependency license in the audit set blocks "anyone can clone and replicate"; the failure class is missing attribution for copied upstream code, not forbidden deps.

- [HIGH] **GPL `levenshtein` was replaced by MIT `rapidfuzz` with an enforced import ban.** Evidence: `pyproject.toml:17` pins `rapidfuzz>=3.14.5,<4` (no `levenshtein` entry); `metrics.py:41`, `match.py:37`, `facts.py:42` import `rapidfuzz.distance.Levenshtein`; `uv.lock` resolves rapidfuzz 3.14.5 and has no `levenshtein` package; `test_edit_distance_parity.py:56-70` lint-bans `import Levenshtein` under `src/whisker`. `CLAUDE.md:152-153` documents the swap as score-identical. Impact: the documented GPL escape hatch is **verified in the runtime path**; BSL distribution is not blocked by the former GPL-2.0 C extension.

- [MED] **Lane 3 `facts.py` adopts the olmOCR assertion *model* but does not copy olmOCR source; no separate Apache notice is required for the design.** Evidence: `facts.py:17-21` cites olmOCR as the conceptual precedent and states whisker "adopts that model verbatim" (schema/semantics, not code); all logic is original BSL-1.0 code (`facts.py:1-6`, `_check_table` at `facts.py:309-335`, pipe-table parser at `facts.py:261-295`); olmOCR upstream is Apache-2.0 (https://github.com/allenai/olmocr). 05-web.md Q1 card (https://github.com/allenai/olmocr/tree/main/olmocr/bench) lists six olmOCR assertion classes including Baseline checks; whisker implements five types (`facts.py:59-64`, baseline 00 §Size) with a different math surface (`pylatexenc` folding per `facts.py:173-181` vs olmOCR KaTeX render per 05-web.md Q1). Impact: design adoption is license-safe; only literal code ports need Apache attribution.

- [MED] **BSL-1.0 header hygiene is complete on every whisker production module under `src/whisker/`.** Evidence: all 24 `.py` modules (e.g. `__init__.py:1-6`, `metrics.py:1-6`, `facts.py:1-6`, `bench.py:1-6`) open with "Distributed under the Boost Software License, Version 1.0"; matches `CLAUDE.md:286` invariant. Impact: **our own code** meets the stated header rule; no orphan modules in the audited target.

- [MED] **`pylatexenc` and `mistune` are used as libraries, not copied; their permissive licenses propagate only via dependency metadata.** Evidence: `metrics.py:40-41` imports `LatexNodes2Text` from pylatexenc; `metrics.py:558` creates a mistune AST renderer for MHS; both are runtime library calls with no upstream source pasted into whisker. pylatexenc MIT, mistune BSD-3-Clause (runtime metadata). Impact: standard permissive-deps case; no additional in-tree attribution beyond normal PyPI dependency notices.

- [LOW] **GPL guard in CI covers import lines only, not the dependency manifest.** Evidence: `test_edit_distance_parity.py:58-66` scans `src/whisker/*.py` for `import Levenshtein` only; it does not inspect `pyproject.toml` or `uv.lock`. Stale research at `research/buildvsbuy/text-edit-distance.md:25` still claims `levenshtein>=0.25.1` in pyproject. Impact: re-adding GPL via manifest would pass tests while violating the license policy; compliance trust in CI is partial.

## False-pass hypothesis

A maintainer runs `uv run pytest packages/whisker/tests`, sees green, and declares license-clean because every `.py` has a BSL header and `grep` finds no GPL imports — while `metrics.py:394-399` still embeds Apache-2.0 verbatim TEDS/normalizer code with no IBM/OmniDocBench copyright block or `THIRD_PARTY_NOTICES` entry, satisfying runtime use but not redistribution attribution for a public BSL repo.

## False-fail hypothesis

A reviewer rejects whisker because `facts.py:17-21` "copies olmOCR" and olmOCR is Apache-2.0 — but the file contains only original BSL implementation of a published benchmark pattern (deterministic fact assertions, 05-web.md Q1); olmOCR's Apache license governs its **code**, not the idea of JSONL present/absent/order/table/math checks, and whisker does not import or paste olmOCR modules.

## What would change my mind

A committed `THIRD_PARTY_NOTICES` (or equivalent) reproducing Apache-2.0 copyright + license text for the OmniDocBench/PubTabNet ports cited at `metrics.py:394-399`, `metrics.py:88-96`, and `match.py:23-24`, **plus** an SPDX SBOM from `uv lock` scoped to `packages/whisker` showing zero GPL/AGPL packages among direct deps, would flip the verdict to **usable** with no conditions.
