# Corpus evidence: what the "base64 blob" actually is

Date: 2026-07-07. Measured directly against `$WG21_DATA_DIR/paperstore/` before
reading any external repo. This reframes the research question.

## Finding: the blobs are inline data-URI images, not garbage

The P2728R11/R12 failure class is NOT undecodable random garbage. It is
syntactically well-formed markdown image references whose URL is a `data:` URI
with a base64 PNG payload:

```
![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAADEUAAAf9CAIAAACqy4EvAAAA...)
```

- `p2728r11.md`: 2,540,150 chars total, only 1,135 lines. The largest single
  line is **1,135,356 chars** (a 1.1 MB base64 PNG inside one `![](data:...)`
  reference); the top 4 blob lines sum to ~2.39 MB, i.e. ~94% of the file.
- `p2728r12.md`: 2,554,175 chars, 7 data-URI images.
- The HTML source (`p2728r12.html`) itself carries 8 `data:image` URIs; tomd
  passed them through into the markdown instead of externalizing them.

## Affected corpus population (not just P2728)

Papers with `(data:image` in their converted `.md` (paperstore scan):

| paper | data-URI images | md size (chars) |
|---|---|---|
| p2728r11.md | 7 | 2,540,150 |
| p2728r12.md | 7 | 2,554,175 |
| n5044.md | 1 | 878,180 |
| p3045r8.md | 13 | 713,726 |
| p3045r7.md | 12 | 630,736 |
| p4215r0.md | 12 | 548,475 |
| p1040r10.md | 1 | 498,308 |
| p3981r0/r1/r2.md | 1 each | ~70,000 each |

Only the P2728 pair fails today because their blobs are large enough that,
after H2 chunking at `MAX_PAPER_MD_CHARS = 500_000`, entire chunks consist of
base64 payload; the triage LLM then burns its whole output budget describing
the noise and hits max_tokens truncation twice (the post-pod-upgrade rerun of
2026-07-07 confirms: 3 errors = P2728R11, P2728R12, P3948R1; zero CJK).
The other papers carry the same payload class but diluted below the choke
threshold - they cost tokens and attention silently on every adjudication.

## Consequence for the filter design

Because the payload is syntactically identifiable (`![alt](data:...)` /
`(data:image/...;base64,` inside an image reference), the chunk-level filter
does NOT need entropy or gibberish heuristics for this failure class. A
deterministic regex replacement of the data-URI payload with a sanctioned
placeholder (mirroring the existing `<!-- tomd:... -->` disclosure pattern,
e.g. `![alt](<!-- tapetum:data-uri-stripped image/png 1.1MB -->)` or an
equivalent marker) is exact, reversible in provenance terms, and cannot
false-positive on prose or code.

Open question for the swarm reports: whether other projects additionally keep
a generic garbage/entropy net for NON-data-URI blobs (raw base64 without the
image wrapper, corrupted streams), and at which layer they apply it
(conversion, chunking, prompt assembly).
