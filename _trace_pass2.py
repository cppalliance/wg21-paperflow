"""Trace Pass 2 execution for Tony Table blocks."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "packages/tomd/src")
from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf.table import (
    _block_column_positions, _detect_header_block,
    _classify_and_annotate, _render_table_text,
)
from tomd.lib.pdf.types import Span
from pathlib import Path
import fitz

pdf = Path("data/paperstore/p2034r6.pdf")
doc = fitz.open(str(pdf))
blocks = extract_mupdf(doc[4], 4)
doc.close()

# Simulate what detect_tables Pass 2 does
# Find groups of blocks with aligned columns
from collections import defaultdict

# Group by left-x positions
for b in blocks:
    cols = _block_column_positions(b)
    text = "".join(sp.text for ln in b.lines for sp in ln.spans)[:40]
    if cols and ("move_only" in text or "vocabulary" in text or "loss of" in text or "Before" in text):
        print(f"Block x={b.bbox[0]:.0f},y={b.bbox[1]:.0f} cols={[f'{c:.0f}' for c in cols]} "
              f"lines={len(b.lines)} text={repr(text)}")
        for li, ln in enumerate(b.lines):
            lt = "".join(sp.text for sp in ln.spans)[:60]
            print(f"    L{li} x={ln.bbox[0]:.0f},y={ln.bbox[1]:.0f}: {lt}")
        print()
