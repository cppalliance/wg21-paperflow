"""Debug: Check what detect_tables returns now."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "packages/tomd/src")
from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf.table import detect_tables
from pathlib import Path
import fitz

pdf = Path("data/paperstore/p2034r6.pdf")
doc = fitz.open(str(pdf))
blocks = []
for i in range(len(doc)):
    blocks.extend(extract_mupdf(doc[i], i))
doc.close()

secs, _ = detect_tables(blocks)
print(f"Total tables: {len(secs)}")
for s in secs:
    print(f"  page={s.page_num} kind={s.table_kind} strategy={s.table_strategy} rows={len(s.columns)}")
    if s.page_num in (4, 5):
        for ri, row in enumerate(s.columns[:3]):
            for ci, cell in enumerate(row):
                text = "".join(sp.text for sp in cell if sp.text != "\n")[:40]
                if text:
                    print(f"    R{ri}C{ci}: {repr(text)}")
