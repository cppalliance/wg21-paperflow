---
name: paper-mcp on Qdrant
overview: Add paper-mcp, a Rust MCP server that gives prompts full access to WG21 papers (metadata, complete text as lines, sections, and an outline, citations, and full-text, vector, and hybrid search) from two Qdrant collections that an operator-run ingest command fills from the paperstore. The crate is its own Cargo workspace so its container image builds from the crate directory alone.
todos:
  - id: ids-dates
    content: "Step 1: scaffold crates/paper-mcp as its own workspace, excluded from the root one; PaperId and RevisionTarget parsing; strict ISO dates and mailing months"
    status: pending
  - id: text-model
    content: "Step 2: text model: lines, code fences, headings and heading cleanup, the section rules with their fallback, Lua-style range resolution, and the outline"
    status: pending
  - id: chunks
    content: "Step 3: blocks and retrieval chunks with overlap, size-limited splitting, and the context header; proptest invariants; insta golden snapshots of six real papers"
    status: pending
  - id: config
    content: "Step 4: typed configuration from an optional TOML file and PAPER_MCP_* environment overrides, validated at load"
    status: pending
  - id: bm25
    content: "Step 5: shared BM25 options, case and accent folding, the Qdrant-compatible tokenizer, and match_lines"
    status: pending
  - id: ingest
    content: "Step 6: BGE-M3 embedding worker, Qdrant collections, payloads, writes and queries, and the ingest command over the read-only paperstore"
    status: pending
  - id: cursor
    content: "Step 7: opaque paging cursors bound to the arguments that produced them"
    status: pending
  - id: auth
    content: "Step 8: bearer-token auth from a keys file with SIGHUP reload and constant-time comparison"
    status: pending
  - id: tools
    content: "Step 9: the eight MCP tools, tool error codes, and the stateless Streamable HTTP router; end-to-end test over a fixture paperstore"
    status: pending
  - id: ops
    content: "Step 10: clap CLI with ingest and serve, Dockerfile, compose-paper-mcp-rust.yaml, CI jobs, cargo-deny config, and the README section"
    status: pending
isProject: false
---

# paper-mcp: a Rust MCP Server for WG21 Papers on Qdrant

<product-contract>

## Product Requirements

Prompts run by the runvil harness need to read whole WG21 papers, not signed download URLs. Today the only way for a prompt to follow a paper URL is a web fetch that cuts text at 40,000 characters, has no offset, and cannot render PDFs. This plan adds `paper-mcp`, a Rust MCP (Model Context Protocol) server that returns paper metadata, the complete text of any paper in one call in several shapes, the paper's citations, and search over paper text and metadata. All data comes from the paperstore that paperflow already fills; an operator-run ingest command copies it into Qdrant, and the server answers every call from Qdrant alone.

- Problem and users:
  - Prompt authors (Agora author advocacy, Papergate, paperweight-style classifiers) whose Lua reads a paper through `tools.call`, stores it in the run's file system, and works on it whatever its size.
  - The operator, who runs paperflow, then ingest, then the server.
- Goals:
  - Full text, never cut: any paper's complete text in one call. No tool truncates, shortens, or windows paper text.
  - Four views of one paper: an outline of every heading, the whole text or a line range, the whole text as markdown sections, and the text as retrieval chunks inside Qdrant. Every word of the paper appears in the text, section, and chunk views.
  - One splitter: every consumer sees the same sections for a paper, because one module defines lines, headings, sections, and chunks.
  - Search: full-text (BM25), vector, and hybrid search over paper text, ranked search over paper metadata, and MCP-standard paging.
  - Facts only: metadata, text, and mechanically extracted citations from the paperstore; nothing produced by an LLM.
- Non-goals:
  - Replacing or changing the Python `paper_mcp` in `wg21-website` or its three tools.
  - Any data store besides Qdrant; Qdrant Cloud.
  - Re-conversion handling; conversions are assumed done and stable.
  - The paperstore's analysis tables (`claims`, `evidence`, `assay_*`, `findings`, `caput_causae`, `rhetoric`, `signals`, `candidates`).
  - Reranking with a model, MCP resources, and MCP prompts.
  - Automatic ingest. Ingest runs only when an operator runs it.
  - Changes to the prompts that consume the server.
- Success criteria:
  - Over a fixture paperstore ingested into a real Qdrant 1.19, every tool in the Functional Specification returns schema-valid structured content over Streamable HTTP, every documented error code is reachable, and every search hit's `text` equals `get_lines` over its range.
  - The text invariants (sections tile the paper; chunks cover each section, never cross a section boundary, and fit the size limit; the same input always produces the same sections and chunks) hold under property tests.
  - The outline, sections, and chunk boundaries of six real papers chosen for their shape are pinned by golden snapshots.
- Constraints:
  - Paper text and metadata come only from the paperstore under `$WG21_DATA_DIR`: `paperstore.db` (tables `papers` and `paper_citations`) and the markdown files its `markdown_path` column names. Nothing fetches paper data from the web; the only permitted download is the embedding model weights.
  - Ingest opens `paperstore.db` read-only with its own queries (`rusqlite`, `SQLITE_OPEN_READ_ONLY`). It does not use `paperstore-sqlite`, whose open path runs schema migrations.
  - Rust edition 2024, `rust-version = "1.89"`, BSL-1.0, toolchain 1.98.0 from the root `rust-toolchain.toml`. The crate's lints mirror the root workspace's: `unsafe_code` forbidden, `clippy::all`, `unwrap_used`, and `expect_used` denied, `pedantic` and `missing_docs` warned.
  - Qdrant 1.19 or later (local BM25, weighted RRF, and the explicit stemmer switch).
- Open questions:
  - None

## Functional Specification

One binary has two commands. `paper-mcp ingest` reads the paperstore and writes two Qdrant collections; `paper-mcp serve` answers MCP tool calls over stateless Streamable HTTP from those collections, behind bearer-token auth. A paper is visible to the tools only after ingest has indexed it.

- Actors and workflows:
  - The operator runs paperflow to fill `$WG21_DATA_DIR`, then `paper-mcp ingest <targets> [--force]`, then `paper-mcp serve`. In Docker, `docker compose -f compose-paper-mcp-rust.yaml up --build` starts Qdrant and the server, and `docker compose -f compose-paper-mcp-rust.yaml exec paper-mcp paper-mcp ingest <targets>` ingests.
  - An MCP client connects to `http://<bind>/papers/mcp` with `Authorization: Bearer <token>`, lists the tools, and calls them.
- Inputs and outputs:
  - Paper ids: `P<n>R<r>`, `D<n>R<r>`, `N<n>`, or `SD-<n>`, accepted in any letter case, stored and returned in lower case. A bare `P<n>` or `D<n>` is accepted only by `list_revisions`. Anything else, including surrounding whitespace, brackets, file suffixes, or URLs, fails with `invalid_paper_id`.
  - Lines: the text between `\n` characters, numbered from 1. A trailing newline does not add an empty last line, and `\r` is an ordinary character.
  - Headings: lines outside code fences that are markdown headings (`#` to `######` and text) or bold-numbered lines (`2. **Motivation and Scope**`). Heading text is cleaned: hashes, hackmd anchor links, link targets, emphasis, and code marks removed, whitespace collapsed. A fence opens at three or more backticks or tildes after optional indentation and closes at the same character repeated at least as often; an unclosed fence runs to the end.
  - Sections: primary boundaries are H2 and bold-numbered headings. When they yield fewer than four sections, the first of H3, H1, or plain numbered lines (`3. Title`) that yields at least four is used, else the primary. Non-blank lines before the first boundary are section 1 (front matter); blank ones join the first boundary's section. Sections tile the paper and are never split.
  - Chunks: built per section from blocks (code block, table including HTML tables, list item, heading, paragraph; blank lines belong to the block before them). A chunk is a run of whole blocks packed to a target size, never crossing a section; each chunk after the first repeats the previous chunk's last block as overlap when that block fits the overlap limit. A block whose embedded text would exceed the size limit is split at the most meaningful boundary that fits: blank-line groups of a code block or rows of an HTML table, then lines, then points inside a line (sentence ends, tag ends, whitespace, and as a last resort any character), with a code block's opening fence or a table's opening line repeated on each part's embedded text. The embedded text starts with a context header (`Paper:`, `Title:`, and `Section N: <heading path>` lines) and a blank line; a chunk's stored `text` is exactly its lines.
  - Tools (names, argument names, and result fields are the contract; every tool declares an output schema and returns structured content):
    - `get_metadata(paper)`: `paper_id`, `title`, `authors`, `document_date` (`YYYY-MM-DD` or empty), `mailing_date` (`YYYY-MM`), `year`, `group`, `intent`, `url`, `disposition`, `previous_version`, `has_markdown`, and, when markdown exists, `total_lines` and `total_sections`.
    - `search_metadata(query?, papers?, start?, end?, date_field?, author?, limit?, cursor?)`: results with `get_metadata`'s fields. With `query`, ranked by weighted RRF over the `title` (weight 3), `authors`, and `other` BM25 vectors, each with a `score`. Without `query`, at least one filter is required and results are newest first by `document_date`, falling back to the first of the mailing month, ties by `paper_id`.
    - `list_revisions(paper)`: the revision chain oldest first, each entry with `paper_id`, `document_date`, `mailing_date`, and `indexed`. Built from same-number records, a backward walk along `previous_version` (renumbered papers), and records whose `previous_version` points into the chain.
    - `get_outline(paper)`: `total_lines`, `total_sections`, and every heading with `line`, `level`, `text`, `section_index`, and `starts_section`.
    - `get_lines(paper, first?, last?)`: Lua `string.sub` semantics (defaults 1 and -1, inclusive, negatives from the end, clamping, empty after clamping returns empty `text`); returns `paper_id`, `text`, resolved `first` and `last`, and `total_lines`.
    - `get_sections(paper, first?, last?)`: sections indexed like `get_lines`; each with `section_index`, `heading`, `first_line`, `last_line`, and full `text`; plus `paper_id` and `total_sections`.
    - `get_citations(paper, direction)`: `direction` is `cites`, `cited_by`, or `both`, with mention counts; when extraction has not run, `citations_extracted` is false and a message replaces the `cites` list.
    - `search(query, type, papers?, start?, end?, date_field?, author?, limit?, cursor?)`: `type` is `fulltext`, `vector`, or `hybrid`. Each hit has `paper_id`, `title`, `url`, `heading_path`, `section_index`, `first_line`, `last_line`, `match_lines`, `text`, and `score`. Requested papers without markdown are listed in `no_markdown`.
  - Filters: `start` and `end` are inclusive ISO dates and apply only when given; `date_field` is `document_date` (default; papers without one are excluded) or `mailing_date` (compared as the first of the month); `author` is a substring match after case and accent folding on both sides.
  - Paging: `limit` defaults to 10 and is capped by configuration; `nextCursor` is present only when more results exist; the cursor is opaque and bound to the arguments that produced it. Fused queries cut every page from one candidate list of a fixed size, so pages never repeat or skip.
- States and validation:
  - Ingest targets are `all`, one or more four-digit years, or one or more paper ids; years and ids cannot be mixed.
  - For each selected paper, ingest replaces its `paper_metadata` record whether or not it has markdown. A paper with markdown is chunked when its record has no markdown, its `chunker_version` differs, or `--force` is given. Chunking deletes the paper's chunk points, then writes the new ones under UUIDv5 ids of (paper id, section index, chunk number), and only then writes the metadata record with `markdown` and `chunker_version`, so a record holding markdown always has complete chunks.
  - `document_date` is stored only when it is a real `YYYY-MM-DD` date; any other value is logged as a warning and treated as absent.
  - Configuration comes from an optional TOML file (`--config` or `PAPER_MCP_CONFIG`) with environment overrides (`PAPER_MCP_QDRANT_URL`, `PAPER_MCP_QDRANT_API_KEY`, `PAPER_MCP_COLLECTION_PREFIX`, `PAPER_MCP_MODEL_CACHE_DIR`, `PAPER_MCP_BIND`, `PAPER_MCP_KEYS_FILE`, `PAPER_MCP_ALLOWED_HOSTS`, `WG21_DATA_DIR`). Unknown keys and invalid values stop startup with an error naming the setting.
- Errors and recovery:
  - Tool errors carry a `code` and a message: `invalid_paper_id`, `paper_not_indexed`, `markdown_not_converted`, `invalid_argument` (missing `query` or `type`, a `search_metadata` call with neither query nor filter, a malformed date, a cursor reused with other arguments), and `internal_error` (details logged once with a request id, never returned).
  - In ingest, a failure confined to one paper is logged with the paper id and cause, counted, and does not stop the run; failing to reach Qdrant or load the model stops it with a nonzero exit.
- Security and privacy behavior:
  - Bearer tokens come from a keys file, one per line, blank lines and `#` comments ignored, compared in constant time. A missing or invalid token gets HTTP 401 before the MCP layer. SIGHUP reloads the file; a reload that yields no tokens is rejected and the previous tokens stay in force.
  - The server reads only Qdrant; only ingest reads the paperstore, and it never writes to it.
  - Paper text is untrusted third-party content returned as data.
- Acceptance criteria:
  - The end-to-end test ingests the fixture paperstore into Qdrant, calls every tool over Streamable HTTP, and checks results, error codes, paging, and that each hit's `text` equals `get_lines` over its range and each `fulltext` hit has a non-empty `match_lines`.
  - A request without a valid bearer token is rejected with 401.
  - `get_lines` and `get_sections` follow every row of the `string.sub` table: whole paper, `first` only, `first` and `last`, negative `first`, and `11, -11`.

</product-contract>
<implementation-contract>

## Technical Design

One new crate, `crates/paper-mcp`, is a library plus a thin binary. It is its own Cargo workspace (an empty `[workspace]` table and its own `Cargo.lock`), excluded from the root workspace, so `docker build crates/paper-mcp` needs nothing else from the repository. Its package values and lints are written out to mirror the root workspace's.

- Architecture:
  - Ingest: paperstore (read-only SQLite and markdown files) to the text model to the BGE-M3 embedder to Qdrant. Serve: rmcp tool router to Qdrant queries, with the embedder for query vectors.
  - Two Qdrant collections, named `<prefix>paper_chunks` and `<prefix>paper_metadata`. `paper_chunks` holds one point per chunk with a 1,024-dimension cosine `dense` vector and a Qdrant-generated `bm25` sparse vector (IDF modifier). `paper_metadata` holds one point per paper with three BM25 vectors (`title`, `authors`, `other`) and the full markdown in its payload. Both are created with `on_disk_payload`, with keyword, integer, and datetime payload indexes created before any point is written.
  - BM25 vectors are generated by Qdrant from documents sent with the `qdrant/bm25` model and options built in one place: `word` tokenizer, lowercase, ASCII folding, stemmer `none`, empty custom stopwords, and a configured `avg_len` per vector (300 for chunks, 6 for titles, 4 for authors, 12 for other).
- Modules and interfaces:
  - `paper_id`: `PaperId` newtype built only by parsing, with `Series` (`p`, `d`, `n`, `sd`), `number`, and `revision`; `RevisionTarget` for `list_revisions`. Pure.
  - `dates`: `Date`, `parse_date` (strict real `YYYY-MM-DD`), `parse_month` (`YYYY-MM` to its first day). Pure.
  - `text`: 1-based `LineNo`, `SectionIndex`, and `ChunkNo` newtypes; `Document` (lines, fences, headings); `Section`; `InclusiveRange` and `resolve_range`; `outline`; `Block` and `BlockKind`; `TokenCounter`, `ChunkSettings`, `Chunk`, `PaperLabel`, `chunk_section`, `chunk_document`, and `context_header`. Pure.
  - `bm25`: `options(avg_len)`, `fold`, `fold_to_ascii`, `tokens`, and `match_lines`. Pure.
  - `cursor`: `fingerprint`, `encode`, and `decode` (URL-safe base64 of the offset and a SHA-256 fingerprint of the arguments). Pure.
  - `config`: `Config` with `qdrant`, `model`, `chunks`, `bm25`, `search`, `serve`, and `ingest` sections, `Config::load`, and accessors that fail with the missing setting's name.
  - `embed`: `Embedder` (fastembed `BGEM3`, `with_max_length(8192)`, one worker thread owning the model behind a bounded channel with oneshot replies, batches capped by token count) and `ModelTokens`, the BGE-M3 tokenizer with truncation and padding off, as the chunker's `TokenCounter`.
  - `qdrant`: `Store` (connect with the configured URL, API key, and timeout, health check, `ensure_collections`, chunk and metadata writes and deletes, scroll, point lookups, and the search queries), `MetadataPayload`, `ChunkPayload`, `Citation`, `chunk_point_id`, and `StoreError`.
  - `ingest`: `Targets` and `parse_targets`, `chunker_version` (a hash of the chunker code version, chunk settings, header format version, and model name), `Ingest::run`, `Report`, and `IngestError`.
  - `serve`: `auth` (`parse_keys`, `Keys` with `load`, `reload`, and constant-time `verify`, and the `require_bearer` axum middleware), `error` (`ToolError` with one variant per code and its `IntoCallToolResult`), `tools` (`PaperServer`, the rmcp tool router with typed argument and result structs), `router`, and `run` (SIGHUP reload, graceful shutdown on SIGTERM and SIGINT).
  - `src/main.rs`: clap `ingest <targets> [--force]` and `serve`, a global `--config`, `anyhow` errors, `tracing-subscriber` logging to stderr.
- File and public API changes:
  - New: `crates/paper-mcp/` (`Cargo.toml`, `Cargo.lock`, `src/`, `tests/it/`, `proptest-regressions/`, `Dockerfile`, `.dockerignore`).
  - Root `Cargo.toml`: add `crates/paper-mcp` to `exclude`. Root `.gitignore`: ignore `/crates/paper-mcp/target`.
  - New root `compose-paper-mcp-rust.yaml` (paper-mcp and a pinned `qdrant/qdrant:v1.19.2`), new root `deny.toml`, two new jobs in `.github/workflows/tests.yml`, and a README section.
- Data, persistence, failure, security, and privacy constraints:
  - Qdrant is the server's only data source; the `paper_metadata` payload carries `markdown`, so outlines, sections, and lines are computed at call time by the same `text` code ingest uses.
  - Query embedding never runs on the async executor; a full embed queue makes callers wait.
  - The keys set sits behind a `std::sync::RwLock`, replaced whole on reload, never held across an `.await`.
  - The container serves on `0.0.0.0:8003` inside its network namespace; compose publishes it on `127.0.0.1` only and reads the bearer token from the `PAPER_MCP_TOKEN` environment variable as a Compose secret.

</implementation-contract>
<verification-contract>

## Testing Plan

Most verification is pure: unit tests beside the code in the pure modules, property tests over generated markdown, and golden snapshots of real papers. One end-to-end test needs Qdrant and the model cache and is ignored by default; CI runs it in a separate job that provides both.

- Unit:
  - `paper_id`: every id form in any case, malformed ids, bare numbers only as revision targets.
  - `dates`: real dates only (rejects `2023-02-29`, `2013-4-25`, `20130825`, Unicode hyphens, and author names), months to their first day.
  - `text`: trailing newline and stray `\r`; indented, unclosed, and mismatched fences; markdown and bold-numbered headings; heading cleanup; headings inside fences ignored; each step of the section fallback and the blank front-matter rule; every row of the `get_lines` table; outline section starts; block kinds including HTML tables and list markers; chunk packing with overlap; oversized code, table, paragraph, and line splitting; heading paths and the context header.
  - `config`: defaults, partial TOML files, unknown keys, and invalid values and chunk size limits naming the setting.
  - `bm25`: tokenization and folding matching Qdrant's options, author folding, `match_lines`.
  - `ingest`: target parsing and `chunker_version` tracking every setting.
  - `cursor`: round trips; rejects other arguments and garbage.
  - `serve::auth`: keys parsing, bearer extraction, verify, and a reload of an empty file keeping the previous keys.
  - `serve::tools`: revision chain ordering, an output schema on every tool, and unknown enum arguments reaching the handler.
- Integration and end-to-end:
  - Property tests (`proptest`): sections tile the paper; chunks cover each section and stay inside it; every chunk fits the size limit; analysis is deterministic; every heading lies in its section.
  - Golden snapshots (`insta`, ignored, reading `$WG21_DATA_DIR`): p3045r9 (H2 headings), p4021r2 (mixed H2 and bold-numbered), p3248r5 (hackmd export), n3768 (stray `\r`), n4485 (largest file, counts and first sections only), and p2079r10 (indented fences).
  - End-to-end (`ingest_and_call_every_tool`, ignored, needs Qdrant 1.19+ and the BGE-M3 cache): writes a five-paper fixture paperstore to a temporary directory (a renumbered revision chain, a paper without markdown, an N paper, and citations), ingests it into uniquely prefixed collections, serves on a free port, and calls every tool through an rmcp client over Streamable HTTP, checking metadata, text, revisions, citations, search, search_metadata, paging, error codes, and the 401 for a bad token.
- Regression, security, and performance:
  - Tool handlers never panic on any input; every expected failure is a `Result` mapped to a code.
- Operational limits:
  - Target hardware: the development VM, CPU only.
  - Downloads: the BGE-M3 model (about 2.3 GB) only for the ignored end-to-end test, run by the operator or CI; no build step downloads it.
  - Data: the golden tests read six real papers; nothing processes the full corpus.
- Exit criteria:
  - In `crates/paper-mcp`: `cargo fmt --check`, `cargo clippy --locked --all-targets --all-features -- -D warnings`, and `cargo test --locked` pass; the golden tests pass against the local paperstore.

</verification-contract>
<decision-record>

## Decision Record

- Decisions:
  - Qdrant is the only store: two collections, BM25 generated server-side, fusion by Qdrant's RRF, filters on payload indexes. The server reads nothing else.
  - BGE-M3 through `fastembed` on CPU, 1,024 dimensions, 8,192-token input, computed locally at ingest and query time so vectors stay portable.
  - Sections are made only by the `text` module, and outlines, lines, and sections are computed at call time from the markdown stored in `paper_metadata`.
  - Every chunk's embedded text fits `max_tokens` (default 1,024, at most the model's 8,192): blocks are split at the most meaningful boundary that fits rather than truncated by the model.
  - Contextual embeddings use a deterministic header of paper id, title, and section heading path; no LLM-generated context.
  - `get_lines` and `get_sections` use Lua `string.sub` range semantics, because the consumers are Lua prompts.
  - Bearer tokens come from a keys file named by `PAPER_MCP_KEYS_FILE` or `serve.keys_file`, in the Python `paper_mcp` format, reloaded on SIGHUP.
  - paper-mcp is its own Cargo workspace excluded from the root, so its Docker image builds from the crate directory alone; it pins its own dependency versions and lockfile.
  - Ingest uses its own read-only `rusqlite` queries instead of `paperstore-sqlite`, whose open path runs migrations.
  - The MCP surface is tools only, over stateless Streamable HTTP with JSON responses, using `rmcp` with structured output.
- Rejected alternatives:
  - An embedded store (LanceDB): it needs an exact pin plus a `remote` feature just to compile and adds Arrow and DataFusion to the build; Qdrant's server-side BM25 and fusion cover the need.
  - Qdrant Cloud and Cloud Inference: Cloud Inference would tie vectors to the provider.
  - Splitting only code blocks and tables over the model limit: a long paragraph or a single-line table could still exceed the model's input and be truncated.
  - Reusing `paperstore-sqlite` for ingest: its open path migrates the schema.
- Assumptions, risks, and notes:
  - The 400-token target and 200-token overlap limit are starting values, tunable in configuration once real results can be judged.
  - The first full ingest embeds several hundred thousand chunks on CPU and takes hours; it is an operator follow-up, not build work.
  - About 270 paperstore rows have malformed `document_date` values; ingest treats them as absent rather than repairing them.

### Deferred and Out of Scope

- Deferred: deploying paper-mcp beside the Python `paper_mcp` in `wg21-website`'s compose file; this plan ships a standalone `compose-paper-mcp-rust.yaml`.
- Deferred: tuning the chunk target, overlap, and BM25 `avg_len` values against judged search results.
- Out of scope: answer generation, scraping, conversion, MCP resources and prompts, and changes to consuming prompts.

</decision-record>
<project-survey>

## Project Survey

- Status: complete
- Build command: `cargo build --locked --manifest-path crates/paper-mcp/Cargo.toml` for paper-mcp, which is its own workspace; the root workspace builds with `cargo build --workspace --locked` (needs the `vendor/runvil` submodule). Python side: `uv sync --all-packages --group dev`.
- Focused test command pattern: `cargo test --locked --manifest-path crates/paper-mcp/Cargo.toml <test_name_filter>`; ignored tests add `-- --ignored`.
- Component test command pattern: `cargo test --locked --manifest-path crates/paper-mcp/Cargo.toml`.
- Full-suite test command: `cargo test --locked --manifest-path crates/paper-mcp/Cargo.toml`, plus `cargo test --workspace --locked` and `uv run pytest` for the rest of the repository.
- Linter command: `cargo clippy --locked --manifest-path crates/paper-mcp/Cargo.toml --all-targets --all-features -- -D warnings`.
- Formatter check command: `cargo fmt --manifest-path crates/paper-mcp/Cargo.toml --check` (`rustfmt.toml`: `style_edition = "2024"`).
- Docs command: `cargo doc --no-deps --manifest-path crates/paper-mcp/Cargo.toml` (rustdoc lints deny broken and private intra-doc links).
- Test placement and naming conventions: Rust unit tests inline as `#[cfg(test)] mod tests { use super::*; ... }` at the bottom of each source file; integration tests in one `tests/it/main.rs` target with a `//!` header and submodules beside it; tests that need external services or data are `#[ignore = "<reason>"]`. Python tests in `packages/<pkg>/tests/test_<topic>.py`.
- Directory map:
  - `Cargo.toml`, `Cargo.lock`, `rust-toolchain.toml`, `rustfmt.toml`: the root Rust workspace (`members = ["crates/*"]`, excludes `vendor/runvil`).
  - `crates/paperstore`, `crates/paperstore-sqlite`: Rust storage API and its SQLite backend.
  - `crates/paperweight`: CLI running a runvil prompt against a paper, plus a `runvil-cli` binary.
  - `vendor/runvil`: git submodule, its own Cargo workspace.
  - `packages/`: uv workspace Python packages (`paperstore`, `mailing`, `tomd`, `pipeline`, `agora`, `assay`, `cli`, `preview`, `cpp-mcp`, `whisker`).
  - `tests/`: Python cross-package integration tests. `data/`: local workspace data (`paperstore.db`, `paperstore/`).
  - `docs/`, `study/`, `herald/`, `html/`: plans, experiments, and notes. `justfile`: command hub.
  - `.github/workflows/tests.yml`: ruff, pyright, per-package pytest, the paperweight cargo job, and integration tests.
- Component boundaries:
  - Rust: `paperstore` <- `paperstore-sqlite` <- `paperweight`, which also depends on `vendor/runvil`. paper-mcp depends on none of them; it reads `paperstore.db` and the markdown files directly.
  - Python: `paperstore` is the base package the others build on; `cpp-mcp` depends only on `fastmcp`.
  - Rust and Python share the on-disk paperstore under `$WG21_DATA_DIR`, with Python owning the schema.
- Conventions summary: Rust edition 2024; crates pin their own dependency versions; `//!` module docs and `///` on public items; `thiserror` errors in libraries and `anyhow` in binaries; no `unwrap`, `expect`, or `unsafe`; `#[must_use]` on pure accessors. Python 3.12 with storage only through `StorageBackend`. No em dashes; spellings `paperflow`, `tomd`, `WG21`.

</project-survey>
<execution-plan>

## Execution Instructions

Components, in dependency order:

1. `paper-mcp-text`: the crate scaffold and the pure paper model (ids, dates, lines, headings, sections, ranges, outline, blocks, chunks). It comes first because ingest and serve both build every view of a paper from it, and it is useful on its own to any consumer that needs the same sections. Pieces are sequential: ids and dates, then the line and section model, then chunks, which consume sections.
2. `paper-mcp-ingest`: configuration, BM25 options, the embedder, the Qdrant store, and the ingest command. It depends on the text model and produces the collections serve reads. Configuration and BM25 are independent pure pieces built first; the embedder, store, and ingest are built jointly because the store's vector size and the ingest pipeline only make sense together.
3. `paper-mcp-serve`: paging cursors, bearer auth, and the MCP tools and router. It depends on the store, config, and BM25. Cursors and auth are independent and built first; the tools compose everything and come last, with the end-to-end test.
4. `paper-mcp-ops`: the CLI binary, container image, compose file, CI, cargo-deny, and README. It depends on a complete library.

Each step's tests pass before the next step starts, and each step leaves `cargo fmt --check` and `cargo clippy --locked --all-targets --all-features -- -D warnings` clean in `crates/paper-mcp`. No em dashes anywhere.

<step-1>

### Step 1: Scaffold paper-mcp with paper ids and dates [completed]

- Component: paper-mcp-text
- Tests: `cargo test --locked --manifest-path crates/paper-mcp/Cargo.toml`
- Create `crates/paper-mcp/Cargo.toml` (`publish = false`, an empty `[workspace]` table, package values and `[lints.*]` tables mirroring the root workspace, `serde` with `derive`, and `thiserror`) and its `Cargo.lock`. Add `crates/paper-mcp` to the root `Cargo.toml` `exclude` with a comment saying why, and `/crates/paper-mcp/target` to `.gitignore`.
- `src/lib.rs` with `//!` crate docs declaring `paper_id` and `dates`.
- `src/paper_id.rs`: `Series` (`as_str`, `has_revisions`), `InvalidPaperId`, `PaperId` (`FromStr`, `TryFrom<String>`, `Display`, serde as a string; `as_str`, `series`, `number`, `revision`; always lower case), and `RevisionTarget` (`Exact(PaperId)` or a bare `P<n>`/`D<n>` number).
- `src/dates.rs`: `Date` with `iso()`, `parse_date` accepting only real `YYYY-MM-DD` dates, `parse_month` mapping `YYYY-MM` to its first day.
- Unit tests: every id form in any case; malformed ids (surrounding whitespace, brackets, a `.md` suffix, a URL, a bare `p3045` or `d3045`, `sd-` without digits, full-width digits); bare numbers only as revision targets; real dates only, including leap years; months become their first day.

</step-1>

<step-2>

### Step 2: Lines, headings, sections, and outline [completed]

- Component: paper-mcp-text
- Tests: `cargo test --locked --manifest-path crates/paper-mcp/Cargo.toml text::`
- Add `schemars` and `src/text/` with `mod.rs`, `headings.rs`, `sections.rs`, and `range.rs`.
- `text/mod.rs`: the `one_based!` macro defining `LineNo` and `SectionIndex` (`FIRST`, `new`, `from_zero_based`, `get`, `zero_based`, serde-transparent, `JsonSchema`); `Document` (`parse`, `line_count`, `lines`, `line`, `text`, `headings`, `sections`); `split_lines`; `OutlineEntry` and `outline`.
- `text/headings.rs`: `scan_fences` (indented fences, same character and at least as many marks to close, unclosed runs to the end), `markdown_heading`, `is_bold_numbered`, `is_plain_numbered`, `find_headings`, `Heading`, and `clean_heading_text` (hashes, hackmd anchors, links, emphasis, code marks, whitespace).
- `text/sections.rs`: `Section` (`index`, `first`, `last`, `boundary`) and the rules of the Functional Specification, ignoring fenced lines.
- `text/range.rs`: `InclusiveRange` (`bounds`, `is_empty`) and `resolve_range(first, last, len)` with `string.sub` semantics.
- Unit tests: trailing newline; `\r` as an ordinary character; `text` clamping; outline section starts; indented, mismatched, unclosed, and two-backtick fences; heading recognition and cleanup; fenced headings ignored; blank front matter joining the first section; primary kept when no fallback reaches four; front matter counting toward four; no boundaries is one section; every row of the `get_lines` table and `string.sub` clamping.

</step-2>

<step-3>

### Step 3: Blocks and retrieval chunks [completed]

- Component: paper-mcp-text
- Tests: `cargo test --locked --manifest-path crates/paper-mcp/Cargo.toml text::`, then `cargo test --locked --manifest-path crates/paper-mcp/Cargo.toml --test it -- --ignored golden` with `WG21_DATA_DIR` set to the local paperstore workspace
- Add `ChunkNo` and the fence-end tracking `Document` needs to `text/mod.rs`, plus `text/blocks.rs`, `text/chunks.rs`, and `text/proptests.rs`, with `proptest` and `insta` as dev dependencies.
- `text/blocks.rs`: `BlockKind` (code, table, list item, heading, paragraph) and `Block`, splitting a section so blocks cover every line with blank lines attached to the block before them; HTML tables are tables; list markers need trailing whitespace.
- `text/chunks.rs`: `TokenCounter`, `SPECIAL_TOKENS`, `MIN_MAX_TOKENS`, `ChunkSettings` (`target_tokens`, `overlap_max_tokens`, `max_tokens`), `Chunk` (`heading_path_text`, `text`, `embed_text`), `PaperLabel`, `context_header`, `chunk_section`, and `chunk_document`, with the packing, overlap, and splitting rules of the Functional Specification; the heading path is shortened in the header when long.
- `text/proptests.rs` and its `proptest-regressions/text/proptests.txt` seed file: the five invariants of the Testing Plan.
- `tests/it/main.rs` (one integration target, `[[test]] name = "it"`) with `tests/it/golden.rs` and its six `insta` snapshots under `tests/it/snapshots/`, ignored with the reason that they need the paperstore markdown under `$WG21_DATA_DIR`. Snapshots use a whitespace word counter so they do not depend on the model tokenizer.
- Unit tests: block kinds; a paragraph stopping at another block; HTML tables; list markers; packing up to the target with overlap; large overlap blocks not repeated; a block larger than the target running long while it fits; chunks never crossing sections; oversized code split with the fence repeated and at blank lines first; oversized paragraphs split at lines; over-long lines split at sentence ends and cut anywhere as a last resort; HTML tables split at rows with the opening line repeated; long heading paths shortened; nested heading paths; the context header format.

</step-3>

<step-4>

### Step 4: Typed configuration [completed]

- Component: paper-mcp-ingest
- Tests: `cargo test --locked --manifest-path crates/paper-mcp/Cargo.toml config::`
- Add `toml` and `src/config.rs`: `CONFIG_ENV`, `MODEL_MAX_TOKENS` (8,192), `ConfigError` (`Read`, `Parse`, `Missing`, and `Invalid`, each naming the file or setting), and `Config` with `QdrantConfig` (url `http://localhost:6334`, api_key, collection_prefix, timeout_secs 120), `ModelConfig` (cache_dir, max_length 8,192, batch_tokens 8,192, queue_depth 64), `ChunkConfig` (target 400, overlap 200, max 1,024), `Bm25Config` (300, 6, 4, 12), `SearchConfig` (fused_candidates 1,000, default_limit 10, max_limit 100, weights 3, 1, 1), `ServeConfig` (bind `127.0.0.1:8003`, path `/papers/mcp`, keys_file, allowed_hosts `localhost` and `127.0.0.1`), and `IngestConfig` (data_dir, embed_batch 64). Every section denies unknown fields.
- `Config::load(path)` reads `--config`, else `PAPER_MCP_CONFIG`, else defaults, applies the environment overrides of the Functional Specification, and runs `validate`, which rejects the first bad setting by name: an empty Qdrant URL, a model max length outside 1 to 8,192 or above the batch size, a zero queue depth, `chunks.max_tokens` outside `MIN_MAX_TOKENS` to the model max length, a target above half the maximum, an overlap not below the target, non-positive BM25 lengths or weights, inconsistent search limits, a zero embed batch, and a serve path not starting with `/`. Accessors `chunk_settings`, `model_cache_dir`, `data_dir`, `keys_file`, `bind_addr`, `chunks_collection`, and `metadata_collection` fail with the missing or invalid setting's name.
- Unit tests: defaults are valid; a partial file keeps the other defaults; unknown settings and bad values are rejected with the setting named; chunk size limits are checked against the model limit, `MIN_MAX_TOKENS`, and the target.

</step-4>

<step-5>

### Step 5: BM25 options and query-term matching [completed]

- Component: paper-mcp-ingest
- Tests: `cargo test --locked --manifest-path crates/paper-mcp/Cargo.toml bm25::`
- Add `serde_json` and `unicode-normalization`, and `src/bm25.rs`: `BM25_MODEL` (`qdrant/bm25`), `options(avg_len)` building the shared option object (`word` tokenizer, lowercase, ASCII folding, stemmer `none`, empty custom stopwords, `avg_len`), `fold_to_ascii`, `fold` (lower case after accent folding, for the author filter), `tokens` (split on non-alphanumerics, fold, lower-case), and `match_lines(text, first, query)` returning every line of a chunk that contains a query token.
- Unit tests: tokens split on non-alphanumerics and fold; author names fold (`Çağrı` to `cagri`); `match_lines` reports lines with any query token and numbers them from the chunk's first line.

</step-5>

<step-6>

### Step 6: Embed and ingest papers into Qdrant [completed]

- Component: paper-mcp-ingest
- Tests: `cargo test --locked --manifest-path crates/paper-mcp/Cargo.toml ingest::`
- Add `fastembed` (rustls download features, no defaults), `tokenizers` (`onig`), `tokio`, `qdrant-client` (`serde`, `uuid`), `uuid` (`v4`, `v5`), `rusqlite` (`bundled`), `sha2`, and `tracing`.
- `src/embed.rs`: `MODEL_NAME` (`BAAI/bge-m3`), `DIMENSIONS` (1,024), `EmbedError`, `Embedder` (`start` loading BGE-M3 into a cache directory with the configured max length and starting the worker thread; `token_counter`; `embed` in token-capped batches; `embed_one`), and `ModelTokens` implementing `TokenCounter`.
- `src/qdrant.rs`: `field` names, `StoreError`, `Citation`, `MetadataPayload`, `ChunkPayload`, `chunk_point_id` (UUIDv5 in a fixed namespace), and `Store` (`connect` with the configured URL, API key, and timeout, `health`, `ensure_collections` with vectors, `on_disk_payload`, and payload indexes, chunk deletes and batched upserts, metadata upserts, scrolls that exclude `markdown`, point lookups, and the fulltext, vector, hybrid, and metadata queries with filters and fused candidate limits).
- `src/ingest.rs`: `Targets`, `TargetError`, `parse_targets`, `chunker_version`, `IngestError`, `Report`, and `Ingest::run`, reading `papers` and `paper_citations` read-only, writing every id in lower case, storing `document_date` only when valid (warning otherwise), deriving `series`, `number`, `revision`, `authors_folded`, `cites`, `cited_ids`, `mailing_date_filter`, `total_lines`, and `total_sections`, and following the chunk-then-metadata write order and the per-paper failure rule.
- Unit tests: target parsing (`all`, years, ids, mixed rejected, bad values named); `chunker_version` changing with every chunk setting. Embedding and Qdrant are covered by the end-to-end test of Step 9, because they need the model download and a running Qdrant.

</step-6>

<step-7>

### Step 7: Paging cursors [completed]

- Component: paper-mcp-serve
- Tests: `cargo test --locked --manifest-path crates/paper-mcp/Cargo.toml cursor::`
- Add `base64` and `src/cursor.rs`: `CursorError`, `fingerprint(&arguments)` (SHA-256 of the serialized arguments, truncated), `encode(fingerprint, offset)`, and `decode(cursor, fingerprint)` rejecting a cursor from other arguments or one that does not decode.
- Unit tests: round trips; other arguments and garbage rejected.

</step-7>

<step-8>

### Step 8: Bearer-token auth [completed]

- Component: paper-mcp-serve
- Tests: `cargo test --locked --manifest-path crates/paper-mcp/Cargo.toml serve::auth::`
- Add `axum` and `subtle`, `src/serve/mod.rs` (`//!` docs, `pub mod auth`, `pub use auth::Keys`), and `src/serve/auth.rs`: `KeysError`, `parse_keys` (one token per line, blank lines and `#` comments ignored), `Keys` (`load` failing on a file with no tokens, `reload` keeping the previous tokens when the new file has none, `verify` in constant time), and `require_bearer`, an axum middleware answering 401 with `WWW-Authenticate: Bearer` before the MCP layer when the case-insensitive `Bearer` token is missing or unknown.
- Unit tests: tokens parsed with comments skipped; bearer extraction; verify, and a reload of an empty file keeping the old keys.

</step-8>

<step-9>

### Step 9: MCP tools over Streamable HTTP

- Component: paper-mcp-serve
- Tests: `cargo test --locked --manifest-path crates/paper-mcp/Cargo.toml`
- Add `rmcp` (`server`, `macros`, `transport-streamable-http-server`), `tokio-util`, and dev dependencies `tempfile`, `reqwest`, and `rmcp` (`client`, `transport-streamable-http-client-reqwest`).
- `src/serve/error.rs`: `ToolError` with `InvalidPaperId`, `PaperNotIndexed`, `MarkdownNotConverted`, `InvalidArgument`, and `Internal`, `code()`, conversions from `InvalidPaperId`, `StoreError`, and `EmbedError`, and `IntoCallToolResult` returning `{code, message}` with a request id logged and returned for internal errors.
- `src/serve/tools.rs`: `PaperServer` and the eight tools of the Functional Specification with typed argument and result structs, output schemas, one `tracing` span per call (tool, paper ids, result code, duration), and server instructions describing ids, lines, and sections.
- `src/serve/mod.rs`: `ServeError`, `router` (stateless Streamable HTTP with JSON responses and allowed hosts, nested at the configured path behind `require_bearer`), and `run` (SIGHUP key reload, graceful shutdown on SIGTERM or SIGINT).
- Unit tests: revision chains ordered by date with a missing `previous_version` placed by its successor; every tool declares an output schema; unknown `type`, `date_field`, and `direction` values deserialize so the handler can answer `invalid_argument`.
- `tests/it/fixture.rs` (a five-paper paperstore written to a temporary directory) and `ingest_and_call_every_tool` in `tests/it/main.rs`, ignored with the reason that it needs Qdrant 1.19+ and the BGE-M3 model cache, covering every check listed in the Testing Plan.

</step-9>

<step-10>

### Step 10: CLI, container deployment, and CI

- Component: paper-mcp-ops
- Tests: `cargo build --locked --manifest-path crates/paper-mcp/Cargo.toml`
- Add `clap` (`derive`, `env`), `anyhow`, and `tracing-subscriber` (`env-filter`), and `src/main.rs`: a global `--config`, `ingest <targets> [--force]` (connect, health check, load the model, run, log the report, exit nonzero when any paper failed), and `serve` (load keys, bind, connect, load the model, `serve::run`), logging to stderr with `info,rmcp=warn` as the default filter.
- `crates/paper-mcp/Dockerfile` (multi-stage build of the crate alone, a slim runtime serving on `0.0.0.0:8003` with `/models` as the model cache and `/run/secrets/paper-mcp-keys` as the keys file) and `.dockerignore`.
- Root `compose-paper-mcp-rust.yaml`: `qdrant` (`qdrant/qdrant:v1.19.2`, a storage volume, a bash TCP health check) and `paper-mcp` (built from the crate, waiting for a healthy Qdrant, `127.0.0.1:8003`, a model volume, the paperstore mounted read-only at the absolute path `paperstore.db` records, and the `paper-mcp-keys` secret from the `PAPER_MCP_TOKEN` environment variable).
- `.github/workflows/tests.yml`: a `paper-mcp` job (format, clippy with warnings denied, tests, cargo-deny) and a `paper-mcp-integration` job with a Qdrant service and a cached model directory running the ignored end-to-end test. Root `deny.toml` with the permissive license allow-list and crates.io as the only source.
- `README.md`: a "Run paper-mcp locally" section covering compose, direct runs, settings, SIGHUP, and the ignored tests.

</step-10>

</execution-plan>
