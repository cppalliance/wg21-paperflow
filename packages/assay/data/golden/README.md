# Golden paper category labels

Curated WG21 paper labels for assay routing classifier evaluation (Issue #239).
Taxonomy and routing rules are defined in
[`paper-routing-classifier.md`](../../../../paper-routing-classifier.md) at the
repo root.

## Label taxonomy

| Category | Meaning |
|----------|---------|
| `library-design` | Library feature design (LEWG) |
| `library-wording` | Library standard wording (LWG) |
| `language-evolution` | Language feature design (EWG) |
| `language-wording` | Core language wording (CWG) |
| `informational` | Skip: agendas, minutes, editor reports, procedural |

## Labeling rules

**Single-label papers** (no `target_groups` field): category from title
heuristics plus `target_group` routing from the mailing index.

**Multi-label papers** (`target_groups` present): `categories` is the sorted
set derived from committee tags:

| `target_groups` | Category |
|-----------------|----------|
| `LEWG` | `library-design` |
| `LWG` | `library-wording` |
| `EWG` | `language-evolution` |
| `CWG` | `language-wording` |

`target_group` remains the primary routing group from the index;
`target_groups` is the full committee set when multiple subgroups are listed.

`confidence` reflects labeling certainty (`high` or `medium`). Values are
frozen at initial labeling time and are not auto-promoted.

## Validate

```bash
uv run python packages/assay/study/golden/validate_categories.py
uv run python packages/assay/study/golden/validate_categories.py \
  packages/assay/data/golden/paper_categories.jsonl
```

The script checks schema, prints label distribution and overlap matrix, and
exits non-zero on schema errors, fewer than 200 entries, or fewer than 30
papers per primary category. It also prints a NOTE when any primary category
has fewer than 30 `high` confidence labels (informational only; does not fail).

## Bias note

Among non-`informational` papers, LEWG routing dominates the sample.
Full committee rebalancing is out of scope for the initial golden set; see
validate output for the `target_group` histogram.
