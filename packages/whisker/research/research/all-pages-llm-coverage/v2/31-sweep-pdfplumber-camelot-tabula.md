# 31 - pdfplumber, camelot, tabula-java, tabula-java-tmp
**Claims tested:** C1
**Exhaustive:** yes

Pinned SHAs verified: pdfplumber `4c64b92`, camelot `39ba78c`, tabula-java `2cdf3b4`, tabula-java-tmp `2cdf3b4` (duplicate checkout of tabula-java).

## Method

Search-floor combined regex (case-insensitive), run from repo root over entire tree with `rg -i -n --no-heading`:

```
openai|anthropic|claude|gemini|google\.genai|genai|litellm|vllm|ollama|chat\.completions|completions\.create|messages\.create|generate_content|GenerativeModel|transformers|AutoModel|\.generate\(|pipeline\(|predict|invoke|prompt|system_prompt|LLM|VLM|gpt-|llama|qwen
```

Additional Java HTTP / AI-API scan for tabula-java and tabula-java-tmp (case-insensitive):

```
openai|anthropic|claude|gemini|generativeai|api\.openai\.com|generativelanguage|cohere|mistral|huggingface|HttpClient|OkHttp|RestTemplate|HttpURLConnection|URLConnection|WebClient|RestClient
```

Production code read in full for C1 adjudication: `camelot/camelot/parsers/ml.py` (725 lines). No other production `.py`/`.java` files contained real LLM/VLM invocation APIs.

## Inventory

### pdfplumber (SHA 4c64b92) — 0 hits

**0 LLM invocation sites.** Patterns run (combined regex above); zero matches across entire repo tree.

---

### tabula-java (SHA 2cdf3b4) — 16 hits (all false positives)

Java HTTP/AI-API supplemental scan: **0 hits**.

| file:line | classification |
|---|---|
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-002-str.xml:1080` | test fixture; substring `llm` inside "enrollment" (not LLM) |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-002-str.xml:2580` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:203` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:247` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:291` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:467` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:515` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:559` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:603` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:695` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:1207` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:1231` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-018-str.xml:7221` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-018-str.xml:7232` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-018-str.xml:7242` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-027-str.xml:13` | test fixture; substring `llm` inside "enrollment" |

**0 LLM invocation sites** in production or test Java code.

---

### tabula-java-tmp (SHA 2cdf3b4) — 16 hits (all false positives)

Java HTTP/AI-API supplemental scan: **0 hits**. Identical hit set to tabula-java (duplicate checkout).

| file:line | classification |
|---|---|
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-002-str.xml:1080` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-002-str.xml:2580` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:203` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:247` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:291` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:467` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:515` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:559` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:603` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:695` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:1207` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:1231` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-018-str.xml:7221` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-018-str.xml:7232` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-018-str.xml:7242` | test fixture; substring `llm` inside "enrollment" |
| `src/test/resources/technology/tabula/icdar2013-dataset/competition-dataset-us/us-027-str.xml:13` | test fixture; substring `llm` inside "enrollment" |

**0 LLM invocation sites** in production or test Java code.

---

### camelot (SHA 39ba78c) — 113 hits

| file:line | classification |
|---|---|
| `CODE_OF_CONDUCT.md:68` | docs; English "promptly" (prompt substring) |
| `pyproject.toml:54` | packaging; comment mentioning HuggingFace transformers optional extra |
| `pyproject.toml:59` | packaging; comment on transformers version pin |
| `pyproject.toml:62` | packaging; optional `[ml]` dependency `transformers>=4.40,<5` |
| `pyproject.toml:90` | packaging; dev doc dep `sphinx-prompt` |
| `noxfile.py:44` | CI; English "invoked" (invoke substring) |
| `noxfile.py:258` | CI; dev dep `sphinx-prompt` |
| `noxfile.py:282` | CI; dev dep `sphinx-prompt` |
| `uv.lock:210` | lockfile; sphinx-prompt package entry |
| `uv.lock:211` | lockfile; sphinx-prompt package entry |
| `uv.lock:223` | lockfile; transformers package entry |
| `uv.lock:264` | lockfile; sphinx-prompt specifier |
| `uv.lock:268` | lockfile; transformers `[ml]` extra specifier |
| `uv.lock:3689` | lockfile; sphinx-prompt metadata |
| `uv.lock:3705` | lockfile; sphinx-prompt sdist URL |
| `uv.lock:3707` | lockfile; sphinx-prompt wheel URL |
| `uv.lock:3711` | lockfile; sphinx-prompt metadata |
| `uv.lock:3732` | lockfile; sphinx-prompt sdist URL |
| `uv.lock:3734` | lockfile; sphinx-prompt wheel URL |
| `uv.lock:4045` | lockfile; transformers metadata |
| `uv.lock:4061` | lockfile; transformers sdist URL |
| `uv.lock:4063` | lockfile; transformers wheel URL |
| `docs/requirements.txt:10` | docs; sphinx-prompt pin |
| `docs/_themes/flask_theme_support.py:89` | docs theme; Pygments `Generic.Prompt` color |
| `docs/conf.py:132` | docs; copybutton_prompt_text config |
| `docs/conf.py:133` | docs; copybutton_prompt_is_regexp config |
| `docs/user/comparison.rst:268` | docs; English "predictable" (predict substring) |
| `docs/user/comparison.rst:285` | docs; prose comparing to "LLM ingestion pipeline" (competitor mention, not invocation) |
| `docs/user/faq.rst:130` | docs; prose mentioning "table-transformers" tool name |
| `docs/benchmark/lattice/row_span/row_span-data-tabula.csv:11` | benchmark fixture; "Enrollment" cell text (`llm` substring) |
| `docs/benchmark/lattice/row_span/row_span-data-tabula.csv:34` | benchmark fixture; "Enrollment" cell text |
| `docs/benchmark/lattice/row_span/row_span-data-tabula.csv:38` | benchmark fixture; "Enrollment" cell text |
| `docs/benchmark/lattice/row_span/row_span-data-tabula.csv:39` | benchmark fixture; "Enrollments" cell text |
| `docs/benchmark/lattice/row_span/row_span-data-camelot-page-1-table-1.csv:11` | benchmark fixture; "Enrollment" cell text |
| `docs/benchmark/lattice/row_span/row_span-data-camelot-page-1-table-1.csv:34` | benchmark fixture; "Enrollment" cell text |
| `docs/benchmark/lattice/row_span/row_span-data-camelot-page-1-table-1.csv:38` | benchmark fixture; "Enrollment" cell text |
| `docs/benchmark/lattice/row_span/row_span-data-camelot-page-1-table-1.csv:39` | benchmark fixture; "Enrollments" cell text |
| `camelot/core.py:597` | production; docstring "invoke" (English verb, not LLM API) |
| `camelot/parsers/stream.py:107` | production; `textedges.generate(textlines)` heuristic edge detector |
| `camelot/parsers/network.py:925` | production; `text_network.generate(textlines)` heuristic network builder |
| `camelot/parsers/ml.py:15` | production; module docstring naming torch/transformers optional deps |
| `camelot/parsers/ml.py:68` | production; docstring on transformers object-detection coords |
| `camelot/parsers/ml.py:424` | production; docstring "Import torch/transformers" |
| `camelot/parsers/ml.py:441` | **production extraction**; lazy import `AutoImageProcessor` from transformers |
| `camelot/parsers/ml.py:442` | **production extraction**; lazy import `AutoModelForObjectDetection` |
| `camelot/parsers/ml.py:451` | **production extraction**; load TATR detection checkpoint via `from_pretrained` |
| `camelot/parsers/ml.py:457` | **production extraction**; load TATR structure checkpoint via `from_pretrained` |
| `camelot/parsers/ml.py:471` | production; docstring on transformers image processor config |
| `camelot/parsers/ml.py:474` | production; docstring on transformers DETR processor |
| `tests/data.py:4447` | test fixture; "Enrollment" expected cell value |
| `tests/data.py:4470` | test fixture; "Enrollment" expected cell value |
| `tests/data.py:4474` | test fixture; "Enrollment" expected cell value |
| `tests/data.py:4475` | test fixture; "Enrollments" expected cell value |
| `tests/data.py:5412` | test fixture; "Enrollment" expected cell value |
| `tests/data.py:5435` | test fixture; "Enrollment" expected cell value |
| `tests/data.py:5439` | test fixture; "Enrollment" expected cell value |
| `tests/data.py:5440` | test fixture; "Enrollments" expected cell value |
| `tests/test_ml_backend.py:6` | test; comment on missing torch/transformers ImportError path |
| `tests/test_main_module.py:6` | test; function name `test_main_invokes_cli` |
| `tests/test_main_module.py:17` | test; function name `test_run_as_module_invokes_cli` |
| `tests/test_cli.py:18` | test; Click `runner.invoke(cli, ...)` |
| `tests/test_cli.py:37` | test; Click `runner.invoke` |
| `tests/test_cli.py:43` | test; Click `runner.invoke` |
| `tests/test_cli.py:50` | test; Click `runner.invoke` |
| `tests/test_cli.py:56` | test; Click `runner.invoke` |
| `tests/test_cli.py:65` | test; Click `runner.invoke` |
| `tests/test_cli.py:71` | test; Click `runner.invoke` |
| `tests/test_cli.py:76` | test; Click `runner.invoke` |
| `tests/test_cli.py:80` | test; Click `runner.invoke` |
| `tests/test_cli.py:98` | test; Click `runner.invoke` |
| `tests/test_cli.py:122` | test; Click `runner.invoke` |
| `tests/test_cli.py:145` | test; Click `runner.invoke` |
| `tests/test_cli.py:151` | test; Click `runner.invoke` |
| `tests/test_cli.py:156` | test; Click `runner.invoke` |
| `tests/test_cli.py:166` | test; Click `runner.invoke` |
| `tests/test_cli.py:171` | test; Click `runner.invoke` |
| `tests/test_cli.py:175` | test; Click `runner.invoke` |
| `tests/test_cli.py:185` | test; Click `runner.invoke` |
| `tests/test_cli.py:203` | test; Click `runner.invoke` |
| `tests/test_cli.py:209` | test; Click `runner.invoke` |
| `tests/test_cli.py:233` | test; Click `runner.invoke` |
| `tests/test_cli.py:241` | test; Click `runner.invoke` |
| `tests/test_cli.py:249` | test; Click `runner.invoke` |
| `tests/test_cli.py:257` | test; Click `runner.invoke` |
| `tests/test_cli.py:265` | test; Click `runner.invoke` |
| `tests/test_cli.py:289` | test; Click `runner.invoke` |
| `tests/test_cli.py:310` | test; Click `runner.invoke` |
| `tests/test_cli.py:354` | test; Click `runner.invoke` |
| `tests/test_cli.py:373` | test; function name `test_cli_group_help_invokes_config` |
| `tests/test_cli.py:380` | test; comment "Invoke a real subcommand" |
| `tests/test_cli.py:382` | test; Click `runner.invoke` |
| `tests/files/assam.pdf:614` | binary test PDF; random `Vlm`/`llm` bytes in compressed stream |
| `tests/files/assam.pdf:1748` | binary test PDF; random `Vlm` bytes |
| `tests/files/assam.pdf:1834` | binary test PDF; random `VlM` bytes |
| `tests/files/assam.pdf:2176` | binary test PDF; random `VLmi` bytes |
| `tests/files/assam.pdf:2424` | binary test PDF; random `VlM` bytes |
| `tests/files/assam.pdf:3729` | binary test PDF; random `nlLM` bytes |
| `tests/files/tabula/icdar2013-dataset/competition-dataset-us/us-002-str.xml:1080` | test fixture; "enrollment" (`llm` substring) |
| `tests/files/tabula/icdar2013-dataset/competition-dataset-us/us-002-str.xml:2580` | test fixture; "enrollment" |
| `tests/files/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:203` | test fixture; "enrollment" |
| `tests/files/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:247` | test fixture; "enrollment" |
| `tests/files/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:291` | test fixture; "enrollment" |
| `tests/files/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:467` | test fixture; "enrollment" |
| `tests/files/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:515` | test fixture; "enrollment" |
| `tests/files/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:559` | test fixture; "enrollment" |
| `tests/files/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:603` | test fixture; "enrollment" |
| `tests/files/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:695` | test fixture; "enrollment" |
| `tests/files/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:1207` | test fixture; "enrollment" |
| `tests/files/tabula/icdar2013-dataset/competition-dataset-us/us-019-str.xml:1231` | test fixture; "enrollment" |
| `tests/files/tabula/icdar2013-dataset/competition-dataset-us/us-018-str.xml:7221` | test fixture; "enrollment" |
| `tests/files/tabula/icdar2013-dataset/competition-dataset-us/us-018-str.xml:7232` | test fixture; "enrollment" |
| `tests/files/tabula/icdar2013-dataset/competition-dataset-us/us-018-str.xml:7242` | test fixture; "enrollment" |
| `tests/files/tabula/icdar2013-dataset/competition-dataset-us/us-027-str.xml:13` | test fixture; "Enrollment" |

**Production ML note (extraction only, not C1 counterexample):** `camelot/parsers/ml.py` optional `flavor='ml'` runs Microsoft Table Transformer object-detection models (`AutoModelForObjectDetection`, `_infer` at lines 593–614) to detect table row/column boxes on a rendered page image, then fills cell text from the PDF text layer (`_text_source`, lines 489–502). The model supplies structure during extraction; it never receives an already-produced conversion output for judging. No generative LLM APIs (`chat.completions`, `generate_content`, `GenerativeModel`, prompts) appear anywhere in the repo.

**0 LLM/VLM verification-of-output sites.**

---

## Verdict on the claim(s)

**C1 CONFIRMED** for all four repos at pinned SHAs.

- **pdfplumber:** Pure deterministic PDF text/geometry extraction; zero search-floor hits; no ML/LLM code path.
- **tabula-java / tabula-java-tmp:** Pure deterministic table extraction (Java); zero real LLM hits; zero HTTP AI-API clients.
- **camelot:** Default flavors (lattice/stream/network/hybrid) are heuristic/deterministic. Optional `ml` flavor uses vision object-detection for table *structure extraction* only; no path compares existing converter output to source via LLM/VLM.

No refuting file:line for a per-page/per-chunk verification judge of already-produced conversion output.

## Coverage gaps

None. Full repo trees scanned with search-floor regex; tabula repos additionally scanned for HTTP/AI clients; camelot `ml.py` read in full for C1 path analysis.

## What could still hide a counterexample

- Dynamically loaded model code not referenced by search-floor strings (none observed; camelot ML imports are explicit lazy imports of named HuggingFace checkpoints).
- External subprocess calling an LLM CLI (no subprocess-to-LLM patterns in search floor for these repos; pdfplumber/tabula have zero ML deps).
- Verification logic implemented under non-obvious naming outside search-floor tokens (no secondary evidence in dependency manifests for pdfplumber/tabula; camelot ML path audited and is extraction-only).
