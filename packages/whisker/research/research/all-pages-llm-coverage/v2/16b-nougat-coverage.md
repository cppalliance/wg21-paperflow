# 16b - nougat per-page failure surfacing (predict CLI)

**Claims tested:** C4 adjacent (foreign per-page failure-surfacing prior art). C1/C2/C3 not primary scope.

**Exhaustive:** yes

**Repo SHA:** 5a92920 (matches baseline pin in `research/all-pages-llm-coverage/00-baseline.md`)

## Method

Search commands:

```text
rg -n "MISSING_PAGE|repeats|repetition|Truncated|WARNING|ERROR: No output" packages/whisker/research/repos/nougat --glob "*.py"
rg -n "def main|if __name__|console_scripts" packages/whisker/research/repos/nougat --glob "*.py"
git -C packages/whisker/research/repos/nougat rev-parse HEAD  # attempted; clone present at pinned path
```

Files read in full (prediction / CLI flow and callees):

- `predict.py` (CLI entry `nougat = predict:main`, `setup.py:80-81`)
- `app.py` (API entry `nougat_api = app:main`, `setup.py:82`)
- `setup.py` (entry points only)
- `nougat/model.py` (`StoppingCriteriaScores`, `NougatModel.inference`)
- `nougat/postprocessing.py` (`postprocess`, `postprocess_single`, marker emission)
- `nougat/utils/dataset.py` (`LazyDataset`, `ImageDataset`, collate)
- `nougat/dataset/rasterize.py`
- `nougat/metrics.py` (eval harness; no marker emission)
- `test.py` (eval harness; no marker emission)

Not read in full: `train.py`, `lightning_module.py`, `docker/`, `config/`, `nougat/dataset/*` (training/index tooling). None matched `MISSING_PAGE` or predict-path markers in repo-wide `rg`.

## Architecture (CLI page loop)

`predict.py:main` builds one `LazyDataset` per PDF (`145-149`), concatenates via `ConcatDataset` (`156-157`), iterates `DataLoader` batches (`166-207`). Each batch item calls `NougatModel.inference(..., early_stopping=args.skipping)` (`167-168`). Post-decode string cleanup runs inside `inference` via `postprocess(..., markdown_fix=False)` (`model.py:655-659`). CLI optionally applies `markdown_compatible` per page (`predict.py:193-194`). Per-PDF output is `"".join(predictions)` written to `.mmd` (`197-202`). Default: `args.skipping=True` (`predict.py:74-77`, `store_false` on `--no-skipping`).

## Inventory — marker emission sites (every match)

| ID | Marker | File:line | Condition | Role |
|----|--------|-----------|-----------|------|
| M01 | `[MISSING_PAGE_POST]` | `nougat/postprocessing.py:323` | `remove_hallucinated_references`: duplicate/near-duplicate reference slice `to_delete` replaced in `text` | Intermediate postprocess sentinel; not written to `.mmd` unless CLI branch M02 fires |
| M02 | `[MISSING_PAGE_EMPTY:{page_num}]` | `predict.py:180` | `output.strip() == "[MISSING_PAGE_POST]"` (entire page text is only the post sentinel after inference postprocess) | CLI: post-only failure → numbered empty marker |
| M03 | `[MISSING_PAGE_FAIL:{page_num}]` | `predict.py:185` | `args.skipping` and `model_output["repeats"][j] is not None` and `model_output["repeats"][j] > 0` | CLI: logit-variance repetition detected (`model.py:636-645`); page replaced by fail marker |
| M04 | `[MISSING_PAGE_EMPTY:{i*args.batchsize+j+1}]` | `predict.py:190` | `args.skipping` and `model_output["repeats"][j] is not None` and `model_output["repeats"][j] == 0` (out-of-domain / early-stop branch per comment `187-188`) | CLI: OOD marker; **page index uses batch formula, not `page_num`** (inconsistency vs M02/M03) |
| M05 | `+++ ==WARNING: Truncated because of repetitions==` … `+++` | `app.py:134,139-141` | API path: `model_output["repeats"][j] is not None` and `repeats[j] > 0`; template filled with `close_envs(repetitions[j])` if non-empty | API equivalent of repetition fail; keeps partial text + disclaimer, **not** `[MISSING_PAGE_FAIL]` |
| M06 | `+++ ==ERROR: No output for this page==` … `+++` | `app.py:137,139-141` | API path: `repeats[j] is not None` and `repeats[j] == 0` | API OOD / empty branch; **not** `[MISSING_PAGE_EMPTY]` |
| M07 | (regex normalize only) | `postprocessing.py:325-326` | Rewrites `## References\n+[MISSING_PAGE_POST(:\d+)?]` → `[MISSING_PAGE_POST\1]` | Reformats existing M01 markers; does not create markers from clean text |

Logging-only (not written to artifact): `predict.py:184` (skip warning), `model.py:644` (`Found repetitions in sample`).

## Inventory — repetition detection (sets `repeats`, no direct marker)

| ID | File:line | Condition | Effect |
|----|-----------|-----------|--------|
| R01 | `model.py:606-608` | `early_stopping=True` (default CLI/API) | Attaches `StoppingCriteriaScores` to `generate` |
| R02 | `model.py:464-474` | During generation: `varvar[b] < 0.015` after window ≥200 (`459-460`) | Schedules early stop index per batch item; influences decode length before post-decode check |
| R03 | `model.py:624-626` | `len(var) < 10` after stacking scores | `repeats.append(None)` — no fail marker path |
| R04 | `model.py:631-633` | EOS present and `N + 1 < indices.shape[1]` | `repeats.append(None)` — treated as clean completion |
| R05 | `model.py:636-645` | `early_stopping` and ≥2 consecutive `varvar < 0.045` windows (`635-637`) | Sets `idx`; if `idx/N > 0.9` → `repeats=None` (`639-640`); elif `small_var[0] < 30` → `idx=0` (`642-643`); else `repeats.append(idx)` |
| R06 | `model.py:648-651` | Non-consecutive `small_var` or `early_stopping=False` | `repeats.append(None)` |
| R07 | `postprocessing.py:361` | Always in `postprocess_single` | `truncate_repetitions(generation)` — tail repeat removal, **no marker** |
| R08 | `postprocessing.py:213` | Slice detector guard | Skips lines starting with `[MISSING_PAGE` when finding duplicate reference blocks |

## Inventory — CLI paths with neither marker nor content (silent holes)

| ID | File:line | Condition | Outcome |
|----|-----------|-----------|---------|
| S01 | `predict.py:135-136` | `not pdf.exists()` | Entire PDF skipped; no `.mmd` for that input |
| S02 | `predict.py:139-143` | `out_path.exists()` and not `--recompute` | Entire PDF skipped; stale or absent update |
| S03 | `predict.py:150-152` | `pypdf.errors.PdfStreamError` on `LazyDataset` | Entire PDF skipped |
| S04 | `predict.py:154-155` | `len(datasets) == 0` | No output at all |
| S05 | `predict.py:181-195` | `args.skipping=False` (`--no-skipping`) | All M02–M04 branches bypassed; degenerate/empty/repeated pages emit raw `output` or `""` with **no marker** |
| S06 | `predict.py:192-195` | `repeats[j] is None` (R03–R06, including R05 `idx/N > 0.9`) | Normal append path: may be truncated repetition, empty string, or partial garbage — **no marker** |
| S07 | `predict.py:178-195` | `output.strip() != "[MISSING_PAGE_POST]"` but page is empty/whitespace after postprocess | Appends empty or whitespace-only chunk — **no marker** |
| S08 | `postprocessing.py:361` | `truncate_repetitions` shortens tail | Content removed inline; page may become empty without M01 if no hallucinated-ref slice |
| S09 | `postprocessing.py:451-457` | Absurd table line (`\\begin{tabular}` >15, etc.) | Line deleted from generation; no marker |
| S10 | `nougat/utils/dataset.py:110-111` | `LazyDataset.ignore_none_collate`: `image is None` | Page dropped from batch — **never reaches predict loop** |
| S11 | `nougat/utils/dataset.py:64-65` | `ImageDataset.__getitem__` open/prepare exception | Returns implicit `None` → collate drop (S10) |
| S12 | `nougat/dataset/rasterize.py:58-59` | Rasterize exception | Partial `pils` list possible; downstream index errors or missing pages |
| S13 | `predict.py:166-207` | Dropped batch pages (S10–S12) | `page_num` increments per emitted output only → **physical page can be missing from `.mmd` with no marker** and subsequent markers misnumbered |
| S14 | `app.py:128-129` | `sample is None` | `continue` — affected pages stay `predictions[i]==""` (`96`) |
| S15 | `app.py:147-149` | `repeats[j] is None` | Output is `markdown_compatible(output)` only; empty OK with no marker |
| S16 | `app.py:144-145` | `repeats[j] is not None` but `len(rest)==0` | `disclaimer=""` — repetition/OOD detected but **no WARNING/ERROR block** appended |

## Verdict on silent page loss vs in-band markers

**In-band `[MISSING_PAGE_*]` markers do NOT make silent page loss impossible.**

Confirmed holes (representative citations):

- **Heuristic bypass:** `--no-skipping` disables marker branches entirely (`predict.py:74-77`, `181-195`; `model.py:650-651`).
- **Undetected degeneration:** `repeats[j] is None` when repetition starts in last 10% of tokens (`model.py:639-640`) or other R03–R06 paths → truncated/empty content without marker (`predict.py:192-195`).
- **String-level truncation:** `truncate_repetitions` (`postprocessing.py:361`) removes tail repeats without marker.
- **Partial post failure:** M01 replaces duplicate-reference *slices* only (`postprocessing.py:319-323`); page with mixed valid/degenerate content keeps text unless entire page equals `[MISSING_PAGE_POST]` (M02).
- **Load/collate drop:** failed rasterize/open drops page from batch (`dataset.py:64-65`, `110-111`; `rasterize.py:58-59`) with no placeholder in `.mmd` (S13).
- **Document-level skip:** entire PDF omitted (S01–S04).
- **API path:** uses M05/M06 disclaimers, not `[MISSING_PAGE_*]`; allows empty strings (S14–S16).

Markers are **best-effort surfacing when `--skipping` (default) and logit heuristics fire**, not a fail-closed per-page guarantee.

## Coverage gaps

None for predict/CLI marker semantics. Training scripts (`train.py`, `lightning_module.py`) and dataset builders not read; repo-wide `rg MISSING_PAGE` returned no additional production emission sites outside inventory.

## What could still hide a counterexample

A wrapper script or fork outside this clone that calls `NougatModel.inference` directly without `predict.py` marker logic would bypass M02–M04. Not found in this pinned tree.
