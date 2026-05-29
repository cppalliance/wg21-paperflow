# tomd Bug: `Dates:` fuzzy-matches `date` and overwrites correct document date

**Severity:** Medium
**Component:** `packages/tomd/src/tomd/lib/pdf/wg21.py`
**Discovered by:** wg21-validator Step 4 evaluation (May 4, 2026)
**Affected papers:** n5035 (and likely other admin/telecon N-papers)

## Symptom

tomd produces `date: 2026-03-09` for N5035, but the PDF clearly states:
```
Date: 2026-01-22
```

The incorrect date `2026-03-09` comes from a later line:
```
Dates: Monday 2026-03-09
```

## Root Cause

1. `_LABEL_RE` matches `Date` (exact), setting `metadata["date"] = "2026-01-22"` correctly.
2. Later, the line `Dates: Monday 2026-03-09` is processed:
   - `Dates` does NOT match `_LABEL_RE` (exact regex has `Date`, not `Dates`).
   - But `dates` fuzzy-matches against `_FUZZY_LABEL_TARGETS` which contains `"date"` (SequenceMatcher score > 0.82 threshold).
   - `DATE_RE.search("Monday 2026-03-09")` finds `2026-03-09`.
   - `metadata["date"]` is **overwritten** with the wrong value.

## Fix Options

**Option A (minimal):** Add `"dates"` to a blocklist in the fuzzy label path, or skip fuzzy matching if the key already has a value from an exact match.

**Option B (better):** In `wg21.py`, when `metadata["date"]` was already set by an exact `Date:` label match, do not allow fuzzy matches to overwrite it. "First exact match wins" semantics.

**Option C (most robust):** Track provenance (exact vs fuzzy) for each metadata field. Exact matches should never be overwritten by fuzzy matches.

## Reproduction

```powershell
uv run paperflow convert n5035
# Inspect output: date field will be 2026-03-09 instead of 2026-01-22
```

Manual verification: open `data/n5035.pdf` page 0. The header says `Date: 2026-01-22`.
The telecon info says `Dates: Monday 2026-03-09`. tomd picks up the latter.

## Related

- `PDF_ARCH.md` describes fuzzy label recovery (threshold 0.82)
- `_FUZZY_LABEL_TARGETS` in `wg21.py` line 24-28
- `structure.py` line 336-341 also has a `startswith("date")` check that would match `Dates:`
