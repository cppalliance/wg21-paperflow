"""Debug: check which pages have blocks for the Compiler schema table."""
import sys
from pathlib import Path
import fitz

sys.path.insert(0, str(Path(__file__).parent / "packages" / "tomd" / "src"))
from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf.table import (
    _block_column_positions, _cluster_x_positions, _nearest_column,
    detect_tables,
)

doc = fitz.open("data/paperstore/p4182r0.pdf")
all_blocks = []
for pn in range(len(doc)):
    all_blocks.extend(extract_mupdf(doc[pn], pn))
doc.close()

# Check pages 11 and 12 for table-related blocks
for page in [11, 12]:
    print(f"\n=== PAGE {page} ===")
    page_blocks = [b for b in all_blocks if b.page_num == page]
    for bi, blk in enumerate(page_blocks):
        blk_text = " | ".join(ln.text.strip() for ln in blk.lines)
        cols = _block_column_positions(blk)
        x0 = blk.bbox[0]
        if any(kw in blk_text for kw in [
            "Toolchain", "GCC", "Clang", "MSVC", "Arm", "NVIDIA", "EDG",
            "Yes", "No", "Platform", "Freestanding", "Hosted", "Follows",
            "Depends", "Coro", "TLS", "Host", "Exc", "PMR",
        ]):
            col_str = f"cols={[round(c,1) for c in cols]}" if cols else "single"
            print(f"  B[{bi}] x0={x0:.1f} y0={blk.bbox[1]:.1f} lines={len(blk.lines)} {col_str}")
            for li, ln in enumerate(blk.lines):
                print(f"    L[{li}] x0={ln.bbox[0]:.1f} '{ln.text.strip()[:50]}'")

# Also check what detect_tables returns for pages 11-12
print("\n\n=== DETECTED TABLES pages 11-12 ===")
secs, _ = detect_tables(all_blocks)
for sec in secs:
    if sec.page_num in [11, 12]:
        rows = sec.columns or []
        nc = max((len(r) for r in rows), default=0)
        print(f"\nTable page={sec.page_num} kind={sec.table_kind} strat={sec.table_strategy} {len(rows)}x{nc}")
        for ri, row in enumerate(rows):
            cells = []
            for ci, cell in enumerate(row):
                t = "".join(s.text for s in cell).strip().replace("\n", "\\n")
                cells.append(f"c{ci}=[{t[:35]}]")
            print(f"  row {ri}: {'  '.join(cells)}")
