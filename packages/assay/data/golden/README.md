# Golden paper category labels

Curated WG21 paper labels for assay routing classifier evaluation (Issue #239).
Taxonomy and routing rules are defined in
[`paper-routing-classifier.md`](../../../../paper-routing-classifier.md) at the
repo root.

## Files

| File | Role |
|------|------|
| `paper_categories_train.jsonl` | Training golden (245 papers). Straight rename of the original Issue #239 set; labels unchanged. |
| `paper_categories_test.jsonl` | Held-out test golden (88 papers). Disjoint paper IDs from train; same schema and labeling rules. |

## Label taxonomy

| Category | Meaning |
|----------|---------|
| `library-design` | Library feature design (LEWG) |
| `library-wording` | Library standard wording (LWG) |
| `language-evolution` | Language feature design (EWG) |
| `language-wording` | Core language wording (CWG) |
| `informational` | Skip: agendas, minutes, editor reports, procedural |

## Labeling rules

Each entry has a `target_group` (primary routing group from the mailing index)
and one or more `categories` from the taxonomy above. Determine which categories
apply from title heuristics, index routing, and paper content.

`categories[0]` must be the category paired with `target_group` in the taxonomy
table (for example, LEWG -> `library-design`). Single-label papers have one
category. Multi-label papers list every applicable category; put that primary
category first and any others after it in alphabetical order. Do not sort the
full list alphabetically.

`confidence` reflects labeling certainty (`high` or `medium`). Values are
frozen at initial labeling time and are not auto-promoted.

## Validate

```bash
uv run python packages/assay/study/golden/validate_categories.py
uv run python packages/assay/study/golden/validate_categories.py --train
uv run python packages/assay/study/golden/validate_categories.py --test
```

With no flags, the script validates both golden files and checks that train and
test `paper_id` sets are disjoint. Use `--train` or `--test` to validate one
file only.

The script checks schema, prints label and primary-category distribution, and
exits non-zero on schema errors or acceptance gate failures.

**Training gates** (`paper_categories_train.jsonl`):

- at least 200 entries
- at least 30 papers containing each primary category (any label position)
- NOTE (non-failing) when any primary category has fewer than 30 `high`
  confidence labels

**Test gates** (`paper_categories_test.jsonl`):

- at least 80 entries
- primary (`categories[0]`) counts at least:

| Primary category | Minimum |
|------------------|--------:|
| `library-design` | 28 |
| `language-evolution` | 18 |
| `language-wording` | 12 |
| `informational` | 13 |
| `library-wording` | 8 |

When validating the test golden (`--test` or the default all-files run), the
script also prints NOTE lines for primary proportions that differ from the
training file by more than 5 percentage points.

## Bias note

Among non-`informational` papers, LEWG routing dominates the sample.
Full committee rebalancing is out of scope for the initial golden set.

## Sentence-level hypothesis labels

Curated sentence labels for the fine-tuned multi-label routing tagger and
regression checks. Hypothesis IDs (`D1`..`D15`, `M1`..`M13`, `W1`..`W5`,
`S1`..`S5`) match the catalog in `assay.paper_routing.hypotheses`.

| File | Role |
|------|------|
| `sentence_hypo_train.jsonl` | Training split |
| `sentence_hypo_test.jsonl` | Held-out evaluation split |

Each line is a JSON object:

```json
{"text": "...", "labels": ["D3", "M1"]}
```

`labels` may be empty. `paper_id` is optional provenance when known; omit it
when sentences were exported without document identity.

Exact duplicate `text` strings can appear in both splits for short boilerplate;
the validator prints a warning but does not fail on overlap.

### Validate sentence_hypo

```bash
uv run python packages/assay/study/golden/validate_sentence_hypo.py
uv run python packages/assay/study/golden/validate_sentence_hypo.py \
  packages/assay/data/golden/sentence_hypo_train.jsonl \
  packages/assay/data/golden/sentence_hypo_test.jsonl
```

Exits non-zero on schema errors or unknown hypothesis labels.
