"""Trace the emit flow for p2034r6 to see why code_blocks tables render as pipes."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "packages/tomd/src")
from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf.table import detect_tables
from tomd.lib.pdf.emit import _render_table, _render_code_comparison
from pathlib import Path
import fitz

pdf = Path("data/paperstore/p2034r6.pdf")
doc = fitz.open(str(pdf))
blocks = []
for i in range(len(doc)):
    blocks.extend(extract_mupdf(doc[i], i))
doc.close()

secs, _ = detect_tables(blocks)

for i, s in enumerate(secs):
    if s.table_kind == "code_comparison":
        print(f"=== Table {i}: page {s.page_num}, kind={s.table_kind}, strategy={s.table_strategy} ===")
        print(f"  Rows: {len(s.columns)}, Cols: {max(len(r) for r in s.columns)}")
        # Show first cell
        if s.columns and s.columns[0]:
            cell = s.columns[0][0]
            print(f"  First cell spans ({len(cell)}):")
            for sp in cell[:10]:
                print(f"    text={repr(sp.text[:40])}")
            if len(cell) > 10:
                print(f"    ... ({len(cell)} total spans)")
        
        # Now render
        rendered = _render_table(s)
        print(f"\n  Rendered output (first 300 chars):")
        print(f"  {repr(rendered[:300])}")
        print()
