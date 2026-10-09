# Repo scan: html-to-markdown-go

**Does it verify LLM-readability?** **no**

Scanned: local shallow clone at `packages/whisker/research/repos/html-to-markdown-go` (JohannesKaufmann/html-to-markdown v2, read-only).

Neither comprehension tests, fact assertions, LLM-as-judge, blind read-back, nor downstream field-QA benchmarks appear anywhere in this repo. QA is **conversion fidelity**: byte-exact golden markdown, optional HTML→MD→HTML→MD idempotence, per-construct escape unit tests, and DOM-collapse representation checks.

## Findings

### Golden-file gate (primary QA contract)

- **14** paired fixtures: `*.in.html` + committed `*.out.md` across three plugin suites (8 commonmark, 5 table, 1 strikethrough; counted at scan time).
- Harness: `internal/tester/goldenfiles.go:44-78` reads each `.in.html`, converts, then `goldie.Assert(t, run, []byte(output))` — **zero slack**, any byte change fails.
- Refresh ritual documented in `README.md:387-393` (`go test -update`); CI runs tests **without** `-update` (`.github/workflows/go.yml:31`: `go test ./... -v -race`).
- Fixture hygiene: rejects subdirectories and orphan filenames (`goldenfiles.go:27-34`); only `.in.html` / `.out.md` allowed.
- Cross-platform stability: `plugin/commonmark/testdata/.gitattributes:4` sets `* -text`; CRLF input normalization tested in `convert_test.go:59-101`.

### Round-trip idempotence (optional, not default CI)

- `internal/tester/round_trip.go:87-120`: HTML→MD→goldmark HTML→MD; passes when `bytes.Equal(FirstMarkdown, SecondMarkdown)` (`round_trip.go:115-120`).
- Gated behind `-round` flag (`goldenfiles.go:14`, `goldenfiles.go:81-95`); **not** enabled in `.github/workflows/go.yml:31`.
- Uses goldmark MD→HTML renderer (`round_trip.go:17-22`, `round_trip.go:101-106`) — checks **converter idempotence through an HTML hop**, not CommonMark spec compliance or LLM fact recovery.

### Plugin-isolated suites + option permutation matrix

- Separate golden dirs per plugin: `plugin/commonmark/commonmark_test.go:14-41`, `plugin/table/table_test.go:14-27`, `plugin/strikethrough/strikethrough_test.go:88-100`.
- `TestOptionFunc` in `plugin/commonmark/commonmark_test.go:44-223`: **27** inline cases (counted `desc:` lines) covering delimiter/heading/HR/list options — each asserts exact expected string, independent of golden files.

### Per-construct escape and collapse tests (format-sensitive micro-anchors)

- Eight escape test files under `internal/escape/*_test.go` (e.g. fenced-code detection `elem_code_test.go:8-49`).
- DOM intermediate representation goldens via `tester.ExpectRepresentation` (`internal/tester/dom_representation.go:11-18`, `collapse/collapse_test.go:22-27`).
- Config validation contract: `plugin/commonmark/validation.go:41-100`, `validation_test.go:8-30`.

### Fuzzing (limited; not markdown-output validity)

- **One** native Go fuzz target: `FuzzReplaceAnyWhitespaceWithSpace` in `collapse/whitespace_test.go:156-168` — asserts regex vs hand-rolled whitespace helper agree on arbitrary strings.
- **No** go-fuzz corpus, **no** fuzz of converter output, **no** markdown-parser validity check on emitted bytes in this clone (searched all `*.go` for `Fuzz` / `go-fuzz`).

### Concurrency / robustness (not readability)

- `convert_test.go:104-163`: 500 goroutines stress converter registration + convert (race detector in CI via `-race` at `go.yml:31`).

### CI matrix (structural regression only)

- `.github/workflows/go.yml:40-58`: Go **1.25** and **1.26** × ubuntu/macos/windows; `go test ./... -v -race -cover`.

### Explicit absences (LLM-readability axes from `00-baseline.md` / Q1–Q3)

| Axis | html-to-markdown-go |
|------|---------------------|
| Comprehension / fact assertions | None |
| LLM-as-judge or blind read-back | None |
| Downstream LLM consumability (ParseBench / RealDocBench / olmOCR downstream pretrain) | None |
| Table neighbor / math layout semantic checks | Only if encoded in a golden string |
| Threshold calibration / ROC | None — implicit operating point is **100% exact match** on goldens |
| Markdown-invalid-construct fuzz gate | None (whitespace-helper fuzz only) |

No source references to LLM readability, comprehension benchmarks, or downstream QA (grep `LLM`, `comprehension`, `readability` in `*.go` / `README.md`: no hits).

## Portable to whisker (ranked)

1. **Golden micro-corpus tier beneath metric guard**: paired HTML snippet → committed expected `.md`, slack **0**, human `-update` / CI never updates — closes formatting regressions NID/TEDS/MHS miss. Evidence: `goldenfiles.go:69-78`, `README.md:387-393`, `.github/workflows/go.yml:31`.
2. **`.gitattributes * -text` + CRLF corpus case** on committed whisker goldens and baselines. Evidence: `plugin/commonmark/testdata/.gitattributes:4`, `convert_test.go:59-101`.
3. **Optional round-trip idempotence axis** for tomd HTML path (HTML→MD→HTML→MD byte-equal). Evidence: `round_trip.go:87-120`; adopt as opt-in bench/guard profile, not default CI cost.
4. **Plugin-/construct-isolated golden subsets** (tables, escapes, strikethrough separate from body goldens). Evidence: `plugin/table/table_test.go:14-27`, `internal/escape/elem_code_test.go:8-49`.
5. **Option-matrix baselines** keyed by converter flags (mirror `TestOptionFunc`). Evidence: `commonmark_test.go:44-223`.
6. **Fixture directory hygiene** (fail on orphan/unpaired files). Evidence: `goldenfiles.go:27-34`.
7. **Whitespace/regression fuzz pattern** — extend whisker with **output-level** fuzz: parse emitted markdown (or pipe-table grid invariants) after conversion; go only fuzzes an internal helper (`whitespace_test.go:156-168`), but the *pattern* (property test over random inputs) is the portable idea whisker lacks.

Not portable for Lane 3: goldens encode **author-chosen expected strings**, not human-verified paper facts, table neighbor geometry, or math surface checks (olmOCR / whisker `facts.py` pattern in Q1).

## Cross-check vs redteam report

Reference: `packages/whisker/research/redteam/html-to-markdown-go.md`.

| Redteam claim | Scan verdict |
|---------------|--------------|
| 14 `.in.html`/`.out.md` goldie pairs | **Confirms** (14 `.in.html` files counted). |
| 43 `*_test.go` files | **Confirms** (43 counted). |
| CI matrix Go 1.25–1.26 × ubuntu/macos/windows | **Confirms** (`.github/workflows/go.yml:40-58`). |
| `goldie.Assert` byte-exact, zero tolerance | **Confirms** (`goldenfiles.go:78`). |
| Round-trip MD→HTML→MD idempotence via `-round` | **Confirms** (`round_trip.go:115-120`, `goldenfiles.go:14`, `goldenfiles.go:81-95`); not default CI. |
| goldie `-update` refresh + CI never `-update` | **Confirms** (`README.md:387-393`, `go.yml:31`). |
| `.gitattributes * -text` for golden stability | **Confirms** (`plugin/commonmark/testdata/.gitattributes:4`). |
| Plugin-isolated golden suites | **Confirms** (commonmark/table/strikethrough test files). |
| Per-element escaping regression files | **Confirms** (8 files under `internal/escape/`). |
| `TestOptionFunc` option permutation matrix | **Confirms** (`commonmark_test.go:44-223`; 27 cases counted). |
| No ROC/threshold calibration | **Confirms**. |
| Missing `.in.html` silently drops coverage | **Confirms** (`goldenfiles.go:30-31` skips `.out.md`-only; no inventory fail on removal). |
| guard missing-pid hard-fail is whisker-only strength | **N/A** — go has no baseline JSON concept. |
| **go-fuzz targets on markdown output** | **Contradicts** — only `FuzzReplaceAnyWhitespaceWithSpace` on whitespace helper (`whitespace_test.go:156-168`); no output-validity fuzz. |
| Verifies LLM-readability | **Not claimed by redteam** — redteam compares regression gates to whisker guard; scan confirms **no** LLM-readability layer. |
