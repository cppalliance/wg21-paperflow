# Evidence Holdout Corpus

Locked corpus for measuring LLM evidence precision and recall.
**No threshold tuning permitted against this set.**

## Rules

1. Labels are committed once and frozen.
2. New anchors may be added; existing anchors never edited.
3. Acceptance gates are measured here but never optimized here.
4. This set must cover: metadata, headings, prose/punctuation, code,
   tables, figures, and math/Unicode.
5. `manifest.json` is the only active-paper list. Files listed under
   `quarantined` remain on disk for audit history but are excluded from every
   holdout count and acceptance metric.
6. Each active paper has a `locked_candidates` entry that pins the source and
   candidate Markdown by repository-relative path and SHA-256. P1112R4 and
   P3714R0 use tomd's byte-exact PDF snapshots. P4182R0 uses its human-blessed
   tomd ideal because no byte-exact tomd snapshot exists for that source.
   Fingerprint drift fails the holdout instead of silently changing labels.
   `source_sha256` hashes the binary source's raw bytes. `candidate_sha256`
   hashes the candidate's UTF-8 text with line endings normalized to `\n`
   before encoding (`manifest.json`'s `fingerprint_method` field; see
   `test_dev_replay_schema.py`'s `_sha256_source_bytes` /
   `_sha256_candidate_text`), so the lock is identical on CRLF (Windows) and
   LF checkouts. It is NOT identical across content changes: any real edit to
   a candidate or source still fails
   `test_locked_candidate_dispositions` (`test_candidate_fingerprint_tripwire_detects_content_drift`
   proves this). A stale lock caused by an upstream fixture edit (see
   `manifest.json`'s `repinned` field for the 2026-08-05 precedent) must be
   re-pinned only after re-verifying every anchor's `expected_candidate_status`
   still holds against the new content; never hand-edit a pinned hash.

## Schema

Each `<pid>.anchors.jsonl` contains one JSON object per line:

```json
{
  "anchor_id": "p1112r4-heading-01",
  "stratum": "headings",
  "quote": "## References",
  "source_location": {"page": 1, "tag": "h2"},
  "expected_candidate_status": "present_in_candidate",
  "notes": "Standard top-level section"
}
```

Valid `stratum` values: metadata, headings, prose, punctuation, code,
tables, figures, math.

Valid `expected_candidate_status`: present_in_candidate,
candidate_not_found, ambiguous.

## Papers

Papers here are from the committed golden fixtures that are NOT in the
9-PR dev replay set. They are converted by tomd (not PR ideals).

The active 48 anchors were re-verified on 2026-07-17 against the exact source
page and a fresh local tomd conversion. `p0533r9` is quarantined because it is
PR #293 in the dev-replay set and therefore cannot be holdout evidence.

`tests/test_dev_replay_schema.py` exercises every active
`expected_candidate_status` through
`classify_candidate_evidence` against the locked candidate. A case-change
canary and a semantic-operator punctuation canary require either mutation to
become ambiguous. This gate does not rerun tomd: tomd's own golden test owns
conversion reproducibility for P1112R4 and P3714R0, while the manifest
fingerprints lock the exact inputs used here.
