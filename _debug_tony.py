"""Debug: Trace exactly what detect_tables produces for the Tony Table on page 4."""
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

for s in secs:
    if s.table_kind == "code_comparison":
        print(f"=== Page {s.page_num}, {s.table_kind}/{s.table_strategy} ===")
        print(f"  Rows: {len(s.columns)}, Cols: {max(len(r) for r in s.columns)}")
        
        for row_idx, row in enumerate(s.columns):
            print(f"\n  ROW {row_idx}:")
            for col_idx, cell in enumerate(row):
                spans_text = []
                for sp in cell:
                    if sp.text == "\n":
                        spans_text.append("[NL]")
                    else:
                        spans_text.append(repr(sp.text[:30]))
                print(f"    COL {col_idx} ({len(cell)} spans): {' '.join(spans_text[:15])}")
                if len(spans_text) > 15:
                    print(f"      ... +{len(spans_text)-15} more spans")
        print()
        break  # Just first table
