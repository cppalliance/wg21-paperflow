# 02 - License-Compliance

**Verdict:** usable-with-conditions — Apache-2.0 is permissive and BSL-compatible for both pip dependency and selective code ports; no copyleft or proprietary license blocks adoption, but verbatim ports must retain Google Apache notices and a pip install pulls mandatory Google Cloud SDK deps into the closure.
**Confidence:** high

## Findings

- [HIGH] **Target license is Apache-2.0 with a standard permissive grant, compatible with our BSL-1.0 stack.** Evidence: `LICENSE:67-72` (copyright grant), `LICENSE:74-88` (patent grant with retaliation-only termination), `pyproject.toml:26` (`license = "Apache-2.0"`), baseline §1 (`00-baseline.md:6`). Impact: **no license forbids** importing langextract as a PyPI dependency or copying algorithms into BSL-1.0 modules; copyleft contamination is absent at the project root.

- [HIGH] **Verbatim ports into our BSL-1.0 files require retained Apache attribution, not BSL headers alone.** Evidence: `LICENSE:101-105` (§4(c): retain copyright/attribution notices in derivative Source form); root `CLAUDE.md:119` (new `.py` files carry BSL-1.0 headers); baseline §2 notes `resolver.py` at **1213 LOC** (`00-baseline.md:24`) as the primary adoptable alignment module. Our monorepo already documents the same gap for Apache upstream ports: `packages/whisker/research/persona/12-license-compliance.md:10-11` (OmniDocBench ports without package-level NOTICE). Impact: copying resolver/chunking logic under a Boost-only header **passes tests but fails redistribution compliance**; dual-header or a `THIRD_PARTY_NOTICES` entry for Google LangExtract is mandatory before shipping ported code.

- [HIGH] **Mandatory runtime deps force Google Cloud SDK packages into any pip-install adoption path.** Evidence: `pyproject.toml:35-36` (`google-genai>=1.39.0`, `google-cloud-storage>=2.14.0` in `[project].dependencies`, not optional); baseline §2 (`00-baseline.md:27`) reproduces the same list; our whisker manifest has **zero** Google SDK entries (`packages/whisker/pyproject.toml:8-19`). Impact: license-wise both are **Apache-2.0 OSS** (permissive, BSL-compatible); product-wise this expands the transitive closure toward proprietary cloud APIs, but it is **not a license contamination failure** unless we treat "no proprietary dependencies" (`CLAUDE.md` Invariants) as blocking cloud SDKs (they are open-source packages).

- [MED] **All 45 shipped library modules carry consistent Google Apache-2.0 file headers.** Evidence: `pyproject.toml:81-87` (wheel packages: `langextract`, `langextract.core`, `langextract.providers`, etc.); every production module opens with the standard block, e.g. `langextract/resolver.py:1-13`, `langextract/__init__.py:1-13`, `langextract/providers/gemini.py:1-13`; shebang-prefixed scripts also carry headers on line 2, e.g. `benchmarks/benchmark.py:2-13`, `scripts/create_provider_plugin.py:2-13`. Impact: **copied-code provenance is traceable**; no unmarked orphan modules in the installable tree.

- [MED] **All 17 direct runtime dependencies declared in the manifest are permissive licenses; no GPL/LGPL/AGPL among them.** Evidence: `pyproject.toml:30-47` — `absl-py`, `aiohttp`, `google-genai`, `google-cloud-storage`, `ml-collections`, `regex`, `requests` (Apache-2.0 family); `pydantic`, `PyYAML`, `more-itertools`, `python-dotenv` (MIT); `numpy`, `pandas` (BSD); `tqdm` (MPL-2.0, file-level weak copyleft on modified tqdm files only); `typing-extensions` (PSF). Optional `openai` extra at `pyproject.toml:58-59` is likewise permissive. Impact: **dependency license set does not forbid** BSL-1.0 redistribution of our combined work; no copyleft trigger from direct deps.

- [MED] **Alignment code is original Google work atop stdlib, not unattributed third-party ports.** Evidence: `langextract/resolver.py:27` imports stdlib `difflib` only; grep over `langextract/` finds no "adapted from", "copied from", or "ported from" provenance strings; baseline §3 (`00-baseline.md:36`) describes the LCS DP and difflib tiers as in-repo implementations. Impact: adopting alignment logic means **one upstream licensor (Google LLC, Apache-2.0)**, not a hidden multi-license mashup.

- [LOW] **No NOTICE file in the target repo; our monorepo likewise lacks a consolidated third-party NOTICE.** Evidence: glob over `packages/whisker/research/repos/langextract/` returns zero `NOTICE*` files; workspace has `LICENSE_1_0.txt` (BSL) only, no `THIRD_PARTY_NOTICES`. Apache §4(d) (`LICENSE:107-122`) applies when a NOTICE file ships with the Work (none here). Impact: **not a blocker for reading/adopting**, but any wheel/sdist we publish after porting or bundling langextract-derived code should add attribution documentation; mirrors the open item already flagged for whisker's own Apache ports (`12-license-compliance.md:10`).

- [LOW] **Google Contributor License Agreement binds contributors, not downstream adopters.** Evidence: `CONTRIBUTING.md:7-12` (CLA required to submit patches; contributor retains copyright); `README.md:429-430` (same). Impact: **false-fail risk** if CLA is mistaken for an additional downstream obligation; Apache-2.0 release terms govern adopters.

## False-pass hypothesis

We port `_apply_monotonic_exact_matches` / LCS fuzzy alignment from `resolver.py` into a new `packages/whisker/src/whisker/grounding_spans.py` with only the BSL-1.0 six-line Boost header (`CLAUDE.md:119`), run `uv run pytest packages/whisker/`, all tests pass, and we declare the adoption license-clean because no GPL entered the tree — while **Apache §4(c) attribution for "Copyright 2025 Google LLC" is missing**, matching the same false-pass pattern already identified for OmniDocBench ports (`12-license-compliance.md:26-27`).

## False-fail hypothesis

A reviewer rejects langextract because `README.md:429-430` requires a Google CLA for **contributors**, treating CLA signatory status as a prerequisite to **use or copy** the released Apache-2.0 code — CLA governs inbound contributions only (`CONTRIBUTING.md:11-12`: Google gets redistribution permission for patches; downstream users inherit the Apache-2.0 grant in `LICENSE:67-72` without signing anything).

## What would change my mind

A resolved `uv.lock` closure (after adding `langextract` to a package manifest) or a vendored subtree under `langextract/langextract/` containing **GPL-/AGPL-licensed source without headers**, or evidence that `google-genai`/`google-cloud-storage` pin a copyleft transitive dependency — any of these would flip the verdict to **garbage** for BSL distribution.
