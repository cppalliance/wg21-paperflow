# Copyright (c) 2026 Sergio DuBois -- temporary debug script, delete after use
import sys, os, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "packages", "tomd", "src"))
logging.basicConfig(level=logging.DEBUG, format="%(name)s: %(message)s")

from pathlib import Path
import fitz
from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf.table import detect_tables
from tomd.lib.pdf.docling_backend import (
    extract_docling_tables, enrich_tables_with_docling, _blocks_in_bbox
)
from tomd.lib.pdf.cleanup import cleanup_text
from tomd.lib.pdf.spans import normalize_spans

doc = fitz.open("data/paperstore/p4003r1.pdf")
all_blocks = []
for i, page in enumerate(doc):
    all_blocks.extend(extract_mupdf(page, i))
doc.close()
all_blocks = cleanup_text(all_blocks)
all_blocks = normalize_spans(all_blocks)

# detect_tables
table_sections, remaining = detect_tables(all_blocks, page_mupdf_tables={}, two_column_pages=set())

# Find table section on page 54 (0-indexed)
tgt = [s for s in table_sections if s.page_num == 54]
print(f"\n=== Table sections on page 54: {len(tgt)} ===")
if tgt:
    sec = tgt[0]
    print(f"  Lines: {len(sec.lines)}")
    if sec.lines:
        print(f"  First line y: {sec.lines[0].bbox[1]:.1f}")
        print(f"  Last line y: {sec.lines[-1].bbox[3]:.1f}")

# Check remaining blocks on page 54
rem_p54 = [b for b in remaining if b.page_num == 54]
print(f"\n=== Remaining blocks on page 54: {len(rem_p54)} ===")
for b in rem_p54[:10]:
    for ln in b.lines:
        txt = " ".join(s.text for s in ln.spans).strip()[:80]
        print(f"  y={ln.bbox[1]:.1f}-{ln.bbox[3]:.1f} x={ln.bbox[0]:.1f} '{txt}'")

# Now run docling
docling_tables = extract_docling_tables(Path("data/paperstore/p4003r1.pdf"))
tbl54 = [t for t in docling_tables if t["page_num"] == 54]
print(f"\n=== Docling tables on page 54: {len(tbl54)} ===")
if tbl54:
    t = tbl54[0]
    print(f"  bbox: {t['bbox']}")
    print(f"  grid: {t['num_rows']}x{t['num_cols']}")
    # Check what _blocks_in_bbox finds
    matched, indices = _blocks_in_bbox(remaining, 54, t['bbox'])
    print(f"  _blocks_in_bbox matched {len(matched)} blocks from remaining")
    for b in matched:
        for ln in b.lines:
            txt = " ".join(s.text for s in ln.spans).strip()[:80]
            print(f"    y={ln.bbox[1]:.1f}-{ln.bbox[3]:.1f} '{txt}'")
    
    # Check header row cells
    for c, cell in enumerate(t["cells"]):
        if cell["row"] == 0:
            print(f"\n  Header cell r0c{c}: bbox={cell['bbox']}, text='{cell.get('text','')}'")
