# tomd Code Cleanup -- Pre-PR Audit Findings

Branch: `sg/tomd-body-abstract-improvements`
Commit: `4a66db4`
Date: 2026-05-18
Scope: `packages/tomd/src/tomd/`, `packages/tomd/tests/`

Instructions: Verify each finding independently. Fix confirmed findings.
Do NOT update PDF_ARCH.md or HTML_ARCH.md in this pass (separate ticket).

---

## 1. Dead Code (4 confirmed, 3 borderline)

### 1.1 DELETE: `_block_aligns_with_column` in `lib/pdf/table.py` line 346
Function defined but never called anywhere. Displaced by `_block_column_positions`
and `_line_column` inside `_detect_geometric_tables`.

### 1.2 DELETE: unused `compute_bbox` import in `lib/pdf/cleanup.py` line 14
Imported from `.types` but never used inside cleanup.py. The function itself is
valid and used elsewhere -- only the import line in cleanup.py is dead.

### 1.3 DELETE: `SectionKind.METADATA` enum member in `lib/pdf/types.py` line 88
Never assigned or checked anywhere in the entire tomd package. No tests reference it.

### 1.4 DELETE: `_REDUNDANT_TABLE_RE` in `lib/shared.py` line 177
Compiled regex, never referenced. `strip_redundant_body_meta` uses
`_REDUNDANT_META_RE` and delegates table stripping to `_strip_metadata_table`.

### 1.5 BORDERLINE: `extract_revision` in `lib/metadata_yaml/format.py` line 33
Re-exported by `lib/__init__.py` but no callers inside tomd. If intended as
external API, keep but document. Otherwise delete.

### 1.6 BORDERLINE: `is_green_ins` / `is_red_del` in `lib/pdf/wording.py` lines 67-76
Public names (no underscore) but only called internally. Either prefix with `_`
or add explicit tests.

### 1.7 BORDERLINE: `_has_br_in_cells` in `lib/html/render.py`
Defined but zero callers. Likely intended to wire into `_needs_flat_reconstruction`.
Either connect it or delete it.

---

## 2. Mid-File Imports (8 findings)

### 2.1 `lib/body/abstract.py` line 276
`from tomd.lib.pdf.types import KNOWN_SECTIONS` inside function body.
Same module already imported at line 9. Move KNOWN_SECTIONS to existing import.

### 2.2 `lib/pdf/pipeline.py` line 256
`import fitz` inside `_run_pipeline()`. No lazy-import comment.
Move to top or add explicit comment explaining deferred load.

### 2.3 `lib/pdf/cleanup.py` line 333
`import fitz` inside `strip_hidden_blocks()`. No lazy-import comment.
Move to top or add explicit comment.

### 2.4 + 2.5 `lib/html/render.py` lines 38 and 100
`from collections import deque` duplicated inside two function bodies
(`_fix_misnested_blocks` and `_fix_misnested_list_items`).
Move to single module-level import at top of file.

### 2.6 `lib/html/convert.py` line 59
`from .. import DOC_NUM_RE` inside `convert_html()`.
Move to top alongside existing `from .. import` at line 9.

### 2.7 `lib/metadata_yaml/extract.py` line 19
`from pathlib import Path` appears after local imports. PEP 8 violation.
Move to stdlib block at top (with `import logging`, `import re`).

### 2.8 `lib/pdf/structure.py` line 399
`from ..metadata_yaml.extract import extract_metadata as _extract_metadata`
between function definitions. Move to top-of-file import block.

---

## 3. Duplicate / Redundant Code (10 findings)

### 3.1 HIGH: Exact function duplicate `override_revision_from_filename`
- `lib/metadata_yaml/extract.py` lines 209-230 (public)
- `lib/html/convert.py` lines 18-39 (private copy: `_override_revision_from_filename`)
Fix: delete the copy in convert.py, import from metadata_yaml/extract.py.

### 3.2 HIGH: `_PID_BASE_RE` regex duplicate (part of 3.1)
- `lib/metadata_yaml/extract.py` line 23
- `lib/html/convert.py` line 15
Fix: delete from convert.py when fixing 3.1.

### 3.3 HIGH: Author token extraction loop duplicated
- `lib/shared.py` lines 257-271 (inside `_strip_freeform_metadata_lines`)
- `lib/metadata_yaml/strip.py` lines 96-105 (inside `strip_metadata_headings`)
Fix: extract `_build_author_tokens(metadata: dict) -> set[str]` in shared.py,
call from both locations.

### 3.4 HIGH: Author name matching logic triplicated
- `lib/shared.py` lines 321-331
- `lib/metadata_yaml/strip.py` lines 208-218
- `lib/metadata_yaml/strip.py` lines 258-268
Fix: extract `_name_matches_author_tokens(text: str, tokens: set[str]) -> bool`
in shared.py, call from all three locations.

### 3.5 HIGH: Table row text rendering duplicated 4x in `lib/pdf/table.py`
- Lines 312-318 (`_detect_side_by_side_tables`)
- Lines 499-505 (`_detect_geometric_tables`)
- Lines 783-789 (`_detect_horizontal_row_tables`)
- Lines 908-914 (`detect_tables` Pass 1)
Fix: extract `_rows_to_text(rows) -> str` private helper, call from all four.

### 3.6 MEDIUM: `_BARE_HEADING_NUM_RE` diverged between table.py and emit.py
- `lib/pdf/table.py` line 64: includes `[IVXLCDM]+` Roman numeral branch
- `lib/pdf/emit.py` line 122: MISSING the Roman numeral branch
Fix: move canonical version to `lib/pdf/types.py`, import from both files.
Ensure emit.py gets the Roman numeral support.

### 3.7 MEDIUM: Bare date regex month lists duplicated across 4 files
- `lib/shared.py` line 221 (`_HEADING_BARE_DATE_RE`)
- `lib/metadata_yaml/strip.py` line 36 (`_BARE_DATE_HEADING_RE`)
- `lib/body/abstract.py` line 50 (`_BARE_DATE_RE`)
- `lib/pdf/wg21.py` line 58 (`_BARE_DATE_RE`)
Fix: single canonical month-list pattern in shared.py, import from others.

### 3.8 MEDIUM: Meta field label patterns triplicated with divergence
- `lib/shared.py` lines 184-191 (`_FREEFORM_META_LABEL_RE`) -- most complete
- `lib/metadata_yaml/strip.py` lines 26-31 (`_META_FIELD_LABEL_RE`) -- missing Date, Doc
- `lib/body/abstract.py` lines 41-44 (`_META_ECHO_RE`) -- missing Co-authors, Subgroup
Fix: `_FREEFORM_META_LABEL_RE` in shared.py is canonical. Others should import or
extend it. The divergence means real bugs: strip.py won't strip Date headings.

### 3.9 LOW: `_STRUCTURAL_CODE_RE` triplicated (intentional, documented)
- `lib/pdf/qa.py` (broadest), `lib/pdf/structure.py` (middle), `_COALESCE_CODE_RE` (narrowest)
Already documented as intentional divergence. No action unless consolidation desired.

### 3.10 LOW: Double `strip_leading_h1` call (second is always no-op)
- `lib/pdf/emit.py` lines 563 + 575
- `lib/html/convert.py` lines 101 + 113
Second call follows cleanup functions that cannot introduce a new leading H1.
Fix: remove the second call in both files.

---

## 4. ARCH Docs (SEPARATE TICKET -- DO NOT FIX HERE)

PDF_ARCH.md: 11 stale references, 13 missing descriptions.
HTML_ARCH.md: 2 stale (critical: wrong module paths), 3 missing descriptions.
These will be addressed in a dedicated arch-update pass after code cleanup.

---

## Priority Order

1. Dead code (1.1-1.4) -- trivial, removes noise
2. Mid-file imports (2.1-2.8) -- mechanical, improves readability
3. HIGH duplicates (3.1-3.5) -- real bugs and maintenance hazards
4. MEDIUM duplicates (3.6-3.8) -- divergence = latent bugs
5. LOW duplicates (3.9-3.10) -- optional cleanup
6. Borderline dead code (1.5-1.7) -- decision needed
