# 02 - License-Compliance

**Verdict:** usable-with-conditions — every mandated LLM-stack dependency is permissive (MIT/BSD/Apache-2.0) and all 25 production `.py` modules under `pipeline/` and `tapetum_llm/` carry BSL-1.0 headers, but tapetum grounding pulls Apache-2.0 verbatim OmniDocBench normalizers without a consolidated attribution NOTICE, which gaps the "public and reproducible" redistribution bar until fixed.
**Confidence:** high

## Findings

- [HIGH] **Apache-2.0 verbatim OmniDocBench code sits on the tapetum grounding path without upstream copyright reproduction.** Evidence: `grounding.py:19` imports `normalized_text` from `whisker.metrics`; `metrics.py:88-91` and `129-133` document verbatim OmniDocBench text normalizers; `metrics.py:394-399` documents a verbatim PubTabNet/OmniDocBench TEDS port (`Apache-2.0, IBM peter.zhong`). No IBM/OmniDocBench copyright block appears in the ported sections; glob over the repo finds no `NOTICE` or `THIRD_PARTY_NOTICES` (only `LICENSE_1_0.txt` at root). Impact: BSL + Apache-2.0 **can** be combined, but public wheels/sdists that ship tapetum grounding without reproducing upstream Apache notices fail §4(c) attribution — a redistribution compliance gap, not copyleft infection.

- [HIGH] **All five persona-mandated dependencies are permissive and BSL-compatible; none forbids public redistribution.** Evidence: runtime metadata (reproduced 2026-07-03): `rapidfuzz` MIT (`grounding.py:17`, `whisker/pyproject.toml:17`); `openai` Apache-2.0 (`pipeline/pyproject.toml:10`, used at `model_backends.py:318`, `:341`); `pydantic-ai` MIT (`whisker/pyproject.toml:28` optional extra); `httpx` BSD-3-Clause (`pipeline/pyproject.toml:9`); `python-dotenv` BSD-3-Clause (`whisker/pyproject.toml:30`, loaded at `cli.py:348`). Impact: **no dependency license blocks** the public-reproducible mandate for the LLM stack itself; the failure class is attribution hygiene, not forbidden deps.

- [MED] **No consolidated third-party NOTICE exists despite multiple Apache-2.0 packages in the pipeline closure.** Evidence: root `pyproject.toml:6` declares BSL-1.0; `LICENSE_1_0.txt:1` is Boost only; `pipeline/pyproject.toml:8-14` also pulls `trafilatura` (Apache 2.0, runtime metadata) and `openai` (Apache-2.0); zero `NOTICE*` files in the workspace. Impact: cloning and running is fine; **publishing** a combined artifact without an SBOM/NOTICE under-documents Apache-2.0 obligations for openai, trafilatura, and the in-tree OmniDocBench ports tapetum inherits.

- [MED] **BSL-1.0 header hygiene is complete on every LLM-stack production module.** Evidence: all 17 files under `packages/pipeline/src/pipeline/` (including `backends/brave.py:1-6`, `model_backends.py:1-6`, `validate.py:1-6`) and all 8 files under `packages/whisker/src/whisker/tapetum_llm/` (e.g. `adjudicate.py:1-6`, `cli.py:1-6`) open with "Distributed under the Boost Software License, Version 1.0"; matches root `CLAUDE.md:119`. Impact: **our own code** meets the stated header invariant; no orphan modules in the audited target.

- [MED] **`pydantic-ai-slim` (pipeline) vs full `pydantic-ai` (tapetum extra) creates a dual install surface with identical MIT license but divergent transitive trees.** Evidence: `pipeline/pyproject.toml:11` pins `pydantic-ai-slim`; `whisker/pyproject.toml:26-31` optional `tapetum-llm` extra adds `pydantic-ai` (full); `agora/pyproject.toml:11` also uses full `pydantic-ai`. Both resolve MIT at runtime. Impact: not a license blocker, but a **provenance/audit surface**: two pydantic-ai variants in one workspace complicate SPDX closure for "what ships with tapetum_llm" unless lockfile scope is explicit.

- [LOW] **`tokens.py` carries an abbreviated BSL header missing the standard LICENSE_1_0.txt pointer.** Evidence: `tokens.py:4` reads "Distributed under the Boost Software License, Version 1.0." with no "(See accompanying file LICENSE_1_0.txt...)" line; peer modules use the full six-line block (e.g. `runner.py:4-5`). Impact: cosmetic header inconsistency only; license terms are unchanged.

- [LOW] **Pipeline direct deps are unpinned, allowing silent license-metadata drift on reinstall.** Evidence: `pipeline/pyproject.toml:8-14` lists `httpx`, `openai`, `pydantic-ai-slim`, `trafilatura`, `sentence-transformers` without version bounds (contrast `whisker/pyproject.toml:17` `rapidfuzz>=3.14.5,<4`). Impact: current resolved licenses are permissive; unpinned manifests cannot guarantee future minor releases stay that way without lockfile discipline.

## False-pass hypothesis

We ship `whisker[tapetum-llm]`, run `uv run pytest packages/pipeline/ packages/whisker/tests/test_tapetum_llm.py`, all green, and declare the LLM stack license-clean because `grep` finds no GPL in `pyproject.toml` and every `.py` has a BSL header — while `grounding.py:19` silently depends on Apache-2.0 verbatim OmniDocBench normalizers at `metrics.py:88-119` with no IBM/OmniDocBench copyright block or `THIRD_PARTY_NOTICES` entry, matching the false-pass pattern already flagged for whisker (`packages/whisker/research/persona/12-license-compliance.md:10-11`).

## False-fail hypothesis

A reviewer rejects the stack because `openai` (`pipeline/pyproject.toml:10`) and `pydantic-ai` (`whisker/pyproject.toml:28`) are "cloud SDKs" and therefore proprietary — both packages are **Apache-2.0 / MIT OSS** (runtime metadata reproduced 2026-07-03) and are explicitly sanctioned behind the `ModelBackend` boundary (`00-baseline.md:55`, `model_backends.py:318`); using them does not violate the "no proprietary dependencies" invariant in `CLAUDE.md:121`, which targets closed-source runtime requirements, not open-source client libraries.

## What would change my mind

A committed `THIRD_PARTY_NOTICES` (or equivalent) reproducing Apache-2.0 copyright + license text for the OmniDocBench/PubTabNet ports cited at `metrics.py:394-399` and `match.py:23-24`, **plus** an SPDX SBOM from `uv lock` scoped to `pipeline` + `whisker[tapetum-llm]` showing zero GPL/AGPL/LGPL packages, would flip the verdict to **usable** with no conditions.
