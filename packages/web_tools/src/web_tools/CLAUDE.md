# web_tools - Agent Rules

## What this is

Web search and content fetch for LLM pipelines. Brave Search API
as the sole backend. `WebResearcher` is the user-facing object.
`SearchBackend` ABC allows future backends.

## Public Surface

- `WebResearcher` - create, use, close. Borrows or owns a backend.
- `SearchResult` - frozen dataclass: title, url, snippet.
- `SearchResponse` - frozen dataclass: status_code, results.
- `FetchResponse` - frozen dataclass: status_code, content.
- `SearchBackend` - ABC for adding backends.

## How to Add a Backend

1. Create `backends/<name>.py`
2. Subclass `SearchBackend`
3. Implement `async def search(self, query, max_results) -> SearchResponse`
4. Declare `name` class attribute
5. Add `close()` if the backend owns resources
6. Register in `backends/__init__.py`

## Invariants

- **Status codes on everything.** `search()` returns `SearchResponse`
  with `status_code`. `fetch()` returns `FetchResponse` with
  `status_code`. No bare strings or lists.
- **Backends are self-contained.** Each backend owns its own HTTP
  client. No shared client coupling between session and backend.
- **Backends are long-lived.** `BraveBackend` holds a persistent
  connection pool and rate limiter. Create once, share across
  `WebResearcher` instances for parallel runs.
- **Researcher borrows or owns.** Pass a backend to share it. Omit
  to auto-create one. `_owns_backend` tracks who closes it.
- **Fail loud.** Missing `BRAVE_API_KEY` raises `ValueError` at
  construction time, not at first search call.
- **No global state.** The researcher is an explicit object. Create
  it, pass it around, close it.
- **`fetch` reads bodies via streaming with a hard cap.** Bodies are
  consumed through `client.stream(...)` + `aiter_bytes()`, and any
  response whose accumulated size exceeds `_MAX_FETCH_BYTES` (25 MB)
  is aborted mid-read. The cap is enforced before any extractor runs,
  so neither trafilatura nor any binary extractor ever sees an
  oversized body.
- **Binary content is routed through `binary_extractors`.** Passed at
  construction, keyed on the response's `Content-Type` (lowercased,
  charset stripped). If no extractor matches the content type, the
  body falls through to the trafilatura HTML path. Detection is
  Content-Type only: no URL-suffix fallback, no magic-byte sniffing.
- **`web_tools` ships no binary extractors.** The package keeps a
  permissive dep set (httpx + trafilatura). Consumers register
  extractors at the `WebResearcher` construction site; this keeps
  AGPL or other restrictively licensed libraries out of `web_tools`.
