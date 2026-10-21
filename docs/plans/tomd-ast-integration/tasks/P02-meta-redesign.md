# P02 Meta redesign: writer takes only the document

| Wave | Deps | Parallel with | Size | Risk |
|------|------|---------------|------|------|
| 0 | P01 | none | M | medium |

## Goal

Remove the `meta` argument from the writer. The writer renders exactly
`document.metadata`. Mailing fallback becomes a pure `resolve_metadata` step in a new
`tomd/resolve.py`, verified equal to the legacy `api._normalize_front_matter` on a
matrix of inputs. Delete the "hybrid body string" bridge in the writer. The public API
(`convert_paper_full(paper_id, path, meta: dict)`) and the CLI are untouched.

## Read first

- `api.py`: `_normalize_front_matter`, `_FALLBACK_KEY_MAP`, `_OVERRIDE_KEYS`
- `writers/markdown/writer.py`, `writers/markdown/normalizers.py` (the duplicate),
  `writers/base.py`
- `lib/metadata_yaml/format.py`: `parse_front_matter`, `sanitize_metadata`,
  `format_front_matter`
- `packages/cli/src/cli/orchestrator.py` (the `meta` dict shape: keys `paper_id`,
  `title`, `authors`, `target_group`, `subgroup`, `document_date`, `intent`, `url`)
- `design.md` section 3

## Change

1. `writers/base.py`: `DocumentWriter.write(self, document: PaperDocument) -> str`.
2. `MarkdownWriter.write(document)`: skipped -> `""`; otherwise front matter from
   `document.metadata` followed by rendered elements. Delete Branch 2 (the `body`
   string path), `PaperDocument.body`, and `writers/markdown/normalizers.py` with
   `tests/writers/markdown/test_normalizers.py` (dead duplicate of `api.py`).
3. `tomd/resolve.py` (new, BSL header):
   - `MailingRecord` frozen dataclass: `paper_id`, `title`, `authors`, `target_group`,
     `subgroup`, `document_date` (only the fields `_FALLBACK_KEY_MAP` reads), and
     `MailingRecord.from_meta(meta: dict | None) -> MailingRecord | None`.
   - `resolve_metadata(parsed: PaperMetadata, mailing: MailingRecord | None)
     -> PaperMetadata`: same rules as `_normalize_front_matter`: sanitize via
     `sanitize_metadata`; fill-only except `document` (mailing is authoritative, SD-7);
     first of `subgroup`/`target_group` wins for `audience`; a `reply-to` list with no
     email does not block the `authors` fallback; log the date fallback at debug.
     Name the key map as a module constant.
   - Intent inference stays in `format_front_matter` (single place); do not duplicate.
4. Do not change `api.py`. It keeps its own `_normalize_front_matter` until P26.

## Do not

- Change the `convert_paper_full` signature, `cli`, or any converter.
- Re-implement YAML formatting; reuse `format_front_matter`.

## Tests

- `tests/test_resolve.py`: a table-driven oracle test. For each case build front-matter
  Markdown and a `meta` dict, compute the legacy result with
  `api._normalize_front_matter(md, meta)` and the new result with
  `format_front_matter(resolve_metadata(PaperMetadata.from_dict(parse_front_matter(md)),
  MailingRecord.from_meta(meta)).to_dict())`, assert the front-matter blocks are equal.
  Cases: all fields present (nothing overridden except `document`); each field
  missing; `document` D-number overridden by `paper_id`; reply-to names only vs with
  emails; audience from `subgroup` vs `target_group`; empty mailing values; no
  mailing; no parsed front matter.
- Writer tests updated: no `meta` argument anywhere; a skipped document writes `""`.

## Acceptance

Checklist green. `grep -rn "meta=" packages/tomd/src/tomd/writers` is empty.
`git status` shows no change to `api.py`, `lib/`, `packages/cli`.

## Handoff (fill in at the end)

```
Status: done | blocked
Files changed:
Checklist output (tails):
Oracle cases covered / any case where new != legacy:
Known divergences found:
Open questions:
```
