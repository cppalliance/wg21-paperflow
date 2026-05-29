"""Debug: How does the geometric detector handle Before/After block."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "packages/tomd/src")
from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf.table import detect_tables
from pathlib import Path
import fitz

pdf = Path("data/paperstore/p2034r6.pdf")
doc = fitz.open(str(pdf))
blocks = extract_mupdf(doc[4], 4)
doc.close()

secs, used = detect_tables(blocks)

# Check: is the Before/After block (block 7) included in the table?
print(f"Used block count: {len(used)}")
print()

# Show block 7 details
for idx, b in enumerate(blocks):
    text = "".join(sp.text for ln in b.lines for sp in ln.spans)
    if "Before" in text and "After" in text:
        print(f"Before/After block index: {idx}")
        print(f"  In used set: {idx in used}")
        print(f"  bbox: {b.bbox}")
        print(f"  lines: {len(b.lines)}")
        for li, ln in enumerate(b.lines):
            lt = "".join(sp.text for sp in ln.spans)
            print(f"    L{li}: x={ln.bbox[0]:.0f} text={repr(lt)}")
        break

# Show the code_comparison table details
for s in secs:
    if s.table_kind == "code_comparison" and s.page_num == 4:
        print(f"\nTable: {len(s.columns)} rows, kind={s.table_kind}")
        # Show first cell of each row
        for ri, row in enumerate(s.columns):
            if row[0]:
                first = "".join(sp.text for sp in row[0] if sp.text != "\n")[:40]
                print(f"  Row {ri} col0: {repr(first)}")
