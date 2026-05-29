"""Trace which detection path the Tony Table uses."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "packages/tomd/src")
from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf import table as _tmod
from pathlib import Path
import fitz

# Monkey-patch to trace section creation
_orig_section = _tmod.Section
_creation_count = [0]

class TracingSection(_tmod.Section):
    pass

# Instead, let's trace by looking at the table detection function internals
# Read the source to understand the paths

pdf = Path("data/paperstore/p2034r6.pdf")
doc = fitz.open(str(pdf))
blocks = []
for i in range(len(doc)):
    blocks.extend(extract_mupdf(doc[i], i))
doc.close()

# Filter to page 4 blocks
page4_blocks = [b for b in blocks if b.page_num == 4]
print(f"Page 4 blocks: {len(page4_blocks)}")
for b in page4_blocks:
    text = "".join(sp.text for ln in b.lines for sp in ln.spans)[:50]
    print(f"  bbox=({b.bbox[0]:.0f},{b.bbox[1]:.0f},{b.bbox[2]:.0f},{b.bbox[3]:.0f}) "
          f"lines={len(b.lines)} text={repr(text)}")

# Check if any block is a separator
import re
SEP_RE = re.compile(r"^[\s\-─━═┄┅┈┉╌╍]+$")
for b in page4_blocks:
    for ln in b.lines:
        line_text = "".join(sp.text for sp in ln.spans)
        if SEP_RE.match(line_text) and len(line_text.strip()) > 3:
            print(f"\n  SEPARATOR FOUND: bbox=({b.bbox[0]:.0f},{b.bbox[1]:.0f}) "
                  f"text={repr(line_text[:60])}")
