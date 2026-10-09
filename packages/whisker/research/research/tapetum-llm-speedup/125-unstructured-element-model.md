# 125 - unstructured-Element-Model

**Verdict:** usable-with-conditions — Rich element metadata (coordinates, hierarchy, provenance) is a solid design reference for per-unit incremental judging, but the default hash-id scheme explicitly keys on `page_number` and within-page ordinal, so it does NOT stabilize identities when page numbers shift or elements reorder on a page.
**Confidence:** high

## Findings

- [CRITICAL] Default element IDs are deterministic SHA-256 hashes, not UUIDs, when `unique_element_ids=False` (partition default). Formula: `sha256(f"{filename}{text}{page_number}{sequence_number}")[:32]`. Evidence: `unstructured/documents/elements.py:789-802` (`id_to_hash`), applied by `_assign_hash_ids` at `unstructured/partition/common/metadata.py:284-305`. Impact: Adopting this verbatim for tapetum per-unit fingerprints would **break skip-cache on any page renumbering** (common in tomd re-converts). Quality risk: low if used only as a starting point; high if copied without dropping `page_number`. Expected wall saving: 0 on cold run; incremental lever could approach warm-run skip rates (~98% papers skipped, 64.8 s vs 3003 s per 00-baseline) only with a page-invariant key.

- [CRITICAL] Hash inputs deliberately exclude coordinates and category; only filename, text, page_number, and 0-based sequence index on that page. Evidence: `elements.py:800` (concat fields), `metadata.py:287-289` (comment: deterministic across parallel fragments). Impact: Coordinates can drift without ID change (good for layout-only edits), but two identical text blobs on the same page get distinct IDs via sequence_number (good). Insert/delete/reorder on a page renumbers all downstream sequence counters (bad for ordinal-based fingerprints). Quality risk: stale skip if ordinal shifts but semantic unit unchanged.

- [HIGH] Post-partition pipeline order: unique-ify instances → apply filename/filetype/lang metadata → hash IDs → **then** assign `parent_id` via heading hierarchy. Evidence: `metadata.py:210-275` (`apply_metadata` wrapper), `metadata.py:99-147` (`set_element_hierarchy`). Parent IDs reference hashed element IDs, not pre-hash UUIDs. Impact: Portable pattern for tapetum: compute stable unit keys first, then attach hierarchical context. Quality risk: none if order preserved.

- [HIGH] Element data model carries coordinates separately from identity. `CoordinatesMetadata` pairs bounding-box `points` with a `CoordinateSystem` (`PixelSpace`, `PointSpace`, `RelativeCoordinateSystem`); elements expose `convert_coordinates_to_new_system()`. Evidence: `elements.py:56-127`, `elements.py:760-787`, `coordinates.py:20-113`. `parent_id` lives in `ElementMetadata` (`elements.py:202`, `323`). Impact: A tapetum unit fingerprint could anchor on normalized relative coordinates + text hash (page-shift tolerant) instead of page_number. Expected saving: enables per-page unit skip on re-convert; potential 4-5× call reduction on partially changed papers (rough: skip unchanged units of 5 MAX_UNIT_CHECKS). Quality risk: coordinate noise from PDF extraction could cause false re-judge (false-fail) or false skip (false-pass).

- [MED] `assign_and_map_hash_ids` (legacy `process_metadata` decorator) and `_assign_hash_ids` (`apply_metadata`) both remap `parent_id` from old UUID to new hash via an `id_mapping` dict. Evidence: `elements.py:585-617`, `metadata.py:307-309`. Duplicate text on same page gets unique IDs via distinct sequence_number; test proves determinism: `test_unstructured/documents/test_elements.py:723-744`. Impact: Confirms hash scheme is intentional and tested, not accidental. Quality risk: none for design borrowing.

- [MED] Chunking preserves provenance via `metadata.orig_elements` (optional, default on): chunks record the source elements they were formed from. Evidence: `chunking/base.py:191-196`, `856-857`, `938-954`; consolidation drops `coordinates` and `parent_id` on chunks (`elements.py:530`, `558`). Impact: Incremental invalidation pattern: judge the chunk/unit, invalidate when any `orig_elements` fingerprint changes. Expected saving: scoped re-judge instead of full 6-call cascade (00-baseline lever #6). Quality risk: missing an changed orig element → false-pass.

- [LOW] HTML ontology intermediate layer uses random UUIDs (`ontology.py:76-78`), not content hashes; converted to unstructured elements with `parent_id=None`, then hierarchy applied downstream. Evidence: `ontology.py:47-78`, `partition/html/transformations.py:66`, `163`, `test_unstructured/documents/test_ontology_to_unstructured_parsing.py:207-235`. Impact: Unstructured treats deterministic IDs as a post-partition concern, not a parse-time concern. Quality risk: none.

- [LOW] No element-level cross-run cache or incremental re-partition store in unstructured. "Incremental" in chunking refers to `PreChunkBuilder` accumulating elements (`chunking/base.py:504-516`), not skip-on-unchanged. NLP `lru_cache` is tokenizer-only (`nlp/tokenize.py:145-190`). Impact: Unstructured supplies identity infrastructure, not a judge-speedup mechanism. Expected wall saving on 3003 s cold run: **0 s directly**; value is schema/hashing design for tapetum lever #6.

## False-pass hypothesis

A tapetum port copies unstructured's hash key including `page_number` and within-page `sequence_number`. A tomd fix inserts one paragraph early on page 3; all downstream units on that page get new sequence indices and new hashes, but their text is unchanged. The incremental layer skips re-judging them (stale fingerprints), missing a real defect in the inserted paragraph's neighbors or in cross-page context that the monolith would catch.

## False-fail hypothesis

A tapetum port keys unit fingerprints on normalized `(text, relative_bbox)` and drops page_number. Two distinct tables with identical boilerplate header text and overlapping layout on different pages collide to the same fingerprint; one page's unit is skipped after the other was judged, causing a missed table-structure defect on the skipped page.

## What would change my mind

Evidence that unstructured (or a downstream consumer) keys element IDs on coordinate-normalized content without `page_number`, with tests showing stable IDs across simulated page renumbering and element insertion — no such scheme exists in the cloned repo as of 2026-07-23.
