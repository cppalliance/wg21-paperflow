# wg21-paperflow - Architecture and Pipeline Design

_Internal design reference. Describes how the system is architected and how the pipeline works._

_Last updated April 26, 2026._

---

## 1. Overview

paperflow is the data-acquisition and transformation layer at the front of the WG21 paper pipeline. It scrapes open-std.org mailing metadata, downloads papers, and converts them to markdown. In production, after paperflow populates Postgres, additional apps read from Postgres. None of those apps ingest the mailing directly.

**Single public repo principle:** The repo must be self-contained. A user who clones it and nothing else must be able to replicate the scrape and conversion steps end to end. No file that is required for the result may live elsewhere.

Two modes of operation:

- **Local mode:** SQLite database + files in a workspace directory, no Postgres required. Any user can clone `cppalliance/wg21-paperflow`, run the CLI, and replicate the scrape and conversion steps.
- **Production mode:** Celery task in the Django app (`wg21-website`), Postgres + S3 backend.

---

## 2. Pipeline Ordering

```
open-std.org mailing
        |
        v
 paperflow mailing        (scrape index, idempotent)
        |
        v
 paperflow convert        (download + tomd conversion, parallel)
        |
        v
 paperflow eval           (LLM pipeline per paper)
        |
        v
     Postgres
        |
   additional apps
```

- Scrape is the serial bottleneck: one HTTP stream to open-std.org.
- After scrape, tomd conversion is embarrassingly parallel (minutes for a full mailing). tomd is lightweight - no ML, no OCR.
- Additional apps read from Postgres; they do not re-scrape the mailing.

---

## 3. Paper Data Model

Two active data structures:

**`PaperMeta`** is the write-side model for `<pid>.meta.json`. It is populated during `paperflow convert` and read back by the eval pipeline. It holds what the system knows about a paper at convert time: title, authors, audience (subgroup), intent, and the path to the staged source file.

**`Evaluation`** is the deliverable written to `<pid>.eval.json` at the end of the LLM pipeline. It contains all `PaperMeta` fields plus findings, references, counts, and the pipeline status.

The `Paper` dataclass in `models.py` is a forward-declared canonical model that is not yet wired through the pipeline. It exists as a design target; `PaperMeta` remains the active write-side contract.

**`intent`** is a field on `PaperMeta` with values `"ask"`, `"info"`, or `""` (unknown). It comes from two sources in order:
1. The mailing scraper: `"Info:"` at the start of the title -> `"info"`, `"Ask:"` -> `"ask"`.
2. tomd: if the converted markdown's YAML front matter carries an `intent` field, it patches meta. If it conflicts with the scraper value, tomd wins and a warning is emitted to stderr.

**Metadata authority rule:** The mailing index is the source of truth for identity fields (title, authors, date). What open-std.org publishes is what the website displays. tomd receives the mailing metadata at invocation time and uses it to fill in YAML front-matter fields that are absent from the source file; it never overrides fields the mailing index already provides.

---

## 4. CLI Contracts

Five commands, each independently runnable. Workspace dir defaults to `$PAPERFLOW_WORKSPACE` or `./data`; pass `--workspace-dir` to override.

```bash
paperflow 2026                    # full pipeline for year (no-verb alias)
paperflow mailing 2026            # scrape mailing indexes only
paperflow mailing all             # scrape all years >= 2011
paperflow download 2026           # fetch source files
paperflow download P3642R4        # fetch a specific paper
paperflow download all            # fetch all not-yet-staged
paperflow convert 2026            # convert to markdown (no LLM)
paperflow convert all             # convert all staged but not converted
paperflow eval 2026               # LLM eval all papers in year
paperflow eval P3642R4            # eval one paper
paperflow eval all                # eval all converted but not evaled
paperflow full 2026               # mailing + download + convert + eval
paperflow full all                # everything not yet done
```

`paperflow` with no verb is an alias for `full`. All commands accept year, paper-id list, or `all`. Mixing years and paper-ids in one invocation is a hard error.

Flags: `--force` / `-f`, `--verify` (download/full), `--concurrency N`, `--discovery-passes N`.

Running `paperflow` with no arguments prints full usage including all flags.

---

## 5. Eval Pipeline Reference

### Pipeline Steps

```
paperflow convert (no LLM):
  download source -> tomd conversion -> meta.json

paperflow eval (LLM):
  Step 0: load paper.md + meta.json
  Step 1: DISCOVERY  (Opus 4.7, JSON + thinking, multi-pass)
  Step 1b: QUOTE VERIFICATION  (pure Python, substring match)
  Step 2: GATE  (Opus 4.7, JSON + thinking)
  Step 2c: KNOWN-FP SUPPRESSION  (pure Python, post-gate)
  Step 3: SUMMARY WRITER  (Sonnet 4.6, JSON)
  Step 4: ASSEMBLY  (pure Python)
  -> eval.json
```

### Models

| Step | Model | Provider | Mode |
|------|-------|----------|------|
| Discovery | Opus 4.7 | OpenRouter | JSON + thinking |
| Gate | Opus 4.7 | OpenRouter | JSON + thinking |
| Summary | Sonnet 4.6 | OpenRouter | JSON |

Slugs are pinned in `paperlint/llm.py` and overridable per process via `PAPERLINT_DISCOVERY_MODEL` (Discovery + Gate) and `PAPERLINT_SUMMARY_MODEL` (Summary).

### Output: `eval.json`

`pipeline_status` is always present: `complete` (end-to-end success), `failed` (pre-analysis failure, e.g. paper could not be fetched), or `partial` (analysis loaded metadata but raised before completing). `failed` and `partial` carry `failure_stage`, `failure_type`, `failure_message`; `PAPERLINT_ERROR_TRACEBACK=1` adds `failure_traceback`. All `failure_*` fields are omitted when unset.

### Intermediate Artifacts (debugging)

```
{workspace_dir}/
  {pid}.meta.json            # convert: metadata
  {pid}.md                   # convert: extracted text
  {pid}.prompts.json         # convert: tomd uncertain-region prompts (optional)
  {pid}.1-findings.json      # eval step 1: discovery findings
  {pid}.2-gate.json          # eval step 2: verdicts
  {pid}.2c-suppressed.json   # eval step 2c: suppressed findings (audit)
  {pid}.eval.json            # eval step 4: deliverable
```

### Versioning

Each evaluation carries:
- **`paperlint_sha`** - git commit hash of the code that produced it
- **`prompt_hash`** - SHA-256 (12 hex chars) of all `prompts/**/*.md` plus `rubric.md`

Rerun rule: `prompt_hash` changed -> full rerun. Unchanged -> skip.

---

## 6. Backend Abstraction

Two concrete backends behind the same `StorageBackend` ABC (`packages/paperstore/src/paperstore/backend.py`):

**SQLite backend** (default - no external dependencies):
- Workspace directory: `./data/` (or `$PAPERFLOW_WORKSPACE`)
- Metadata in `papers.db` (three tables: `papers`, `years`, `evals`)
- Source files, markdown, and eval JSON remain on disk; DB stores paths
- Used for local replication, testing, CI, debugging

**Postgres + S3 backend** (production):
- Structured metadata (paper_id, title, authors, intent, audience, findings, eval status) stored in Postgres
- Blobs (PDF source, converted markdown, eval JSON, intermediates) stored in S3
- `get_source_path` materializes from S3 to a local temp file before returning, per the `StorageBackend` ABC contract
- Implemented in `wg21-website` (private), not in this repo
- Django app calls paperflow functions directly as a Python library

The SQLite backend must work without Postgres installed, and the Postgres backend must never be a dependency of the public repo. Any user must be able to clone the repo, run the scraper, and get results into a local directory without configuring a database.

SQLite is preferred over flat JSON files for the local backend because metadata queries (idempotency checks, work-set selection) are SQL rather than file-glob-and-parse operations. Source files and markdown remain on disk because MuPDF and tomd need local paths.

S3 for blobs was chosen over all-in-Postgres for production because it decouples blob serving from the query path. PDFs and markdown can be served via direct S3 URLs without routing through the application tier. At archive scale (all mailings since 2011, roughly 10,000 papers), the database stays lean while blob storage scales independently.

---

## 7. tomd YAML Front-Matter Spec

Fields tomd emits and their canonical forms:

| Field | Correct form | Wrong form |
|---|---|---|
| `intent` | `intent: ask` or `intent: info` | `paper-type: informational` |
| `intent` position | after `date`, before `audience` | any other position |
| `title` | `title: "A Minimal Coroutine..."` (quoted) | `title: A Minimal Coroutine...` |
| Audience values | Short names, no hyphens: `LEWG`, `SG16` | Long names: `LEWG Library Evolution`, `SG-16` |

Canonical field order: `title`, `document`, `date`, `intent`, `audience`, `reply-to`.

Audience normalization: audience values from the mailing metadata must be normalized to short names without hyphens. "EWG Evolution" -> "EWG", "SG-16" -> "SG16". The exact normalization formula is not yet defined; this is tracked as an open item.

tomd's contract: extract what's in the source file; if a field is absent from the source, leave it absent and let the mailing metadata fill it in.

---

## 8. Repository Layout

uv workspace monorepo. Four packages, each independently installable:

```
cppalliance/wg21-paperflow/   (public - users clone this to replicate)
├── packages/
│   ├── mailing/              # scrape open-std.org, download paper sources
│   ├── tomd/                 # PDF/HTML -> Markdown converter
│   ├── paperstore/           # storage abstraction (JsonBackend today)
│   └── paperlint/            # LLM eval pipeline + paperflow CLI
├── tests/                    # cross-package integration tests
└── DESIGN.md                 # this file
```

`cppalliance/wg21-website` (private Django app) imports wg21-paperflow as a Git submodule. The Postgres + S3 backend lives in `wg21-website`, not here.

---

## 9. Django Integration

How `wg21-website` (private) calls into `cppalliance/wg21-paperflow` (public):

```python
# In wg21-website (private):
from paperlint.orchestrator import convert_one_paper
from mailing.scrape import fetch_papers_for_mailing

@app.task
def process_year(year: str):
    for paper in fetch_papers_for_year(year, ...):
        convert_one_paper(
            paper["paper_id"],
            source_url=paper["url"],
            mailing_meta=paper,
            storage=PostgresBackend(db),
        )
```

wg21-paperflow is installed as a Git submodule. Django imports it as a Python library, not via subprocess.

**Current state:** mailing detection (polling open-std.org for new mailings) lives in the Django app. The goal is to move it into paperflow so the full pipeline is runnable without Django. Not yet done.

---

## 10. Dependencies

```
openai             # OpenRouter API (all LLM calls)
python-dotenv      # .env loading
pymupdf            # PDF text extraction
beautifulsoup4     # HTML parsing (mailing page scraper + HTML conversion)
requests           # HTTP (paper fetching, mailing scraper)
```

---

## 11. Environment

```
OPENROUTER_API_KEY=sk-or-...
PAPERFLOW_WORKSPACE=/path/to/data   # optional; default ./data
```

---

## 12. Known Limitations

- **Context window:** Papers exceeding ~200K tokens cannot be processed in a single Discovery call.
- **PDF extraction:** pymupdf quality varies by WG21 PDF toolchain; uncertain regions are flagged in `<pid>.prompts.json` for human or LLM review.
- **Non-determinism:** Same paper run twice may produce different findings. The Gate provides precision consistency - what passes is reliably correct, but the candidate set varies.
- **Quote verification:** Substring matching with whitespace normalization; OCR PDFs may still mismatch visual text.

---

## 13. Open Questions

Decisions not yet finalized as of Apr 26, 2026:

- **Audience normalization formula:** Short names without hyphens are required (`LEWG`, `SG16`), but the exact normalization rules for all known subgroup name variants are not yet codified.
- **GitHub issues per paper:** Where does per-paper issue tracking live once eval ships? `wg21.link/PXXXX/github` works as a URL pattern; hosting and linking unresolved.
- **Mailing detection in paperflow vs. Django:** The goal is to move mailing detection into the paperflow repo so the full pipeline can run without Django. Currently lives in `wg21-website`. Not yet scheduled.
