# 13 - Dependency-Supply-Chain

**Verdict:** garbage — a bare `pip install langextract` hard-requires the Google Cloud SDK stack and several unused scientific-Python deps, which violates our no-proprietary-deps invariant and makes Ollama/self-hosted adoption carry cloud baggage we never invoke.
**Confidence:** high

## Findings
- [CRITICAL] `google-genai` and `google-cloud-storage` are **core** dependencies, not optional extras; an Ollama-only user still resolves the full `google-cloud-*` transitive chain at install time. Evidence: `pyproject.toml:35-36`; dry-run `uv pip install --dry-run -e .` resolved 57 packages including `google-api-core`, `google-cloud-core`, `google-cloud-storage`, `google-crc32c`, `google-resumable-media`, `proto-plus`. Impact: direct breach of root `CLAUDE.md:121` ("No proprietary dependencies") and our model-sovereignty mandate; supply-chain surface includes Google auth/credential plumbing even when inference stays local.

- [HIGH] OpenAI is correctly isolated behind an optional extra, but Google is not — install-time asymmetry locks the default footprint to Google. Evidence: `openai>=1.50.0` only under `[project.optional-dependencies] openai/all` (`pyproject.toml:58-60`); `google-genai`/`google-cloud-storage` under unconditional `dependencies` (`pyproject.toml:35-36`). Impact: `pip install langextract[openai]` still pulls Google SDK; cloud-first packaging contradicts our `pipeline` anchor (`packages/pipeline/pyproject.toml:8-14`: httpx, openai, pydantic-ai-slim only).

- [HIGH] Six declared runtime deps have **zero imports** in library code — dead weight on the supply chain. Evidence: `numpy>=1.20.0`, `ml-collections>=0.1.0`, `aiohttp>=3.8.0`, `async_timeout>=4.0.0`, `exceptiongroup>=1.1.0`, `python-dotenv>=0.19.0` (`pyproject.toml:31-44`); grep over `langextract/` returns no matches (numpy appears only in `tests/data_lib_test.py:19` and `benchmarks/plotting.py:28`, outside the wheel). Impact: enlarged attack surface and resolver churn for packages the library never calls; pin-hygiene signal is poor (deps declared but not owned).

- [HIGH] `pandas` is eagerly imported on `import langextract`, not gated behind the notebook extra. Evidence: `__init__.py:27-28` imports `extraction` and `visualization`; `extraction.py:26` imports `io`; `io.py:27` `import pandas as pd`; `[notebook]` extra is separate (`pyproject.toml:75-78`). Impact: ~50MB+ scientific stack loads for every consumer including CSV-free Ollama paths; contrasts with our lean `pipeline` import graph.

- [MED] Entry-point plugin discovery executes third-party provider code via `entry_point.load()` during `load_plugins_once()`, with failures downgraded to warnings. Evidence: `providers/__init__.py:111-134` iterates `langextract.providers` entry points and calls `entry_point.load()`; exceptions caught and logged at warning level (`providers/__init__.py:131-134`); opt-out only via `LANGEXTRACT_DISABLE_PLUGINS` env var (`providers/__init__.py:81-88`); registry declared at `pyproject.toml:94-97`. Impact: any installed malicious/conflicting plugin runs import-time code in our process; fragile for integrators who cannot control the host environment.

- [MED] Pin hygiene is floor-only across all runtime deps — no upper bounds, no lockfile, wide pydantic span. Evidence: every runtime dep uses `>=` (`pyproject.toml:30-47`); `pydantic>=1.8.0` permits v1 or v2; only dev tools are exact-pinned (`pyink==24.3.0`, `isort==5.13.2` at `pyproject.toml:62-63`). Impact: non-reproducible installs across time; pydantic major-version drift can break schema handling silently between CI runs.

- [MED] Loading the Gemini provider unconditionally imports `gemini_batch`, which top-level-imports `google.cloud.storage` even for synchronous (non-batch) inference. Evidence: `providers/gemini.py:36` `from langextract.providers import gemini_batch`; `providers/gemini_batch.py:42-44` `from google import genai` and `from google.cloud import storage` at module scope (contrast: `google.genai` in `gemini.py:212-214` is lazy inside `__init__`). Impact: first Gemini resolution pulls GCS client code and credentials machinery unrelated to simple chat completion; tight coupling increases runtime import failures in air-gapped/self-hosted environments.

## False-pass hypothesis
An integrator sees `openai` behind `[project.optional-dependencies]` and `ollama` documented as a first-class provider (`providers/ollama.py:17-80`) and assumes `pip install langextract` is provider-neutral at install time — it is not, because the Google SDK chain is unconditional (`pyproject.toml:35-36`).

## False-fail hypothesis
A reviewer rejects langextract believing `google-genai` executes on every `import langextract` — the top-level import chain stops at `pandas`/`requests` via `extraction.py:26` → `io.py:27`; Google modules load only when the Gemini provider path is resolved. The real failure is **install-time** mandatory Google deps, not import-time for Ollama-only extract calls.

## What would change my mind
A tagged release (or upstream PR merged) that moves `google-genai` and `google-cloud-storage` into a `[gemini]` extra, drops unused deps (`numpy`, `ml-collections`, `aiohttp`, `async_timeout`, `exceptiongroup`, `python-dotenv`), and lazy-imports `pandas` — verified by `uv pip install langextract` (no extras) resolving ≤15 packages with zero `google-*` entries.
