"""Debug: What extract_mupdf produces for the Tony Table blocks."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "packages/tomd/src")
from tomd.lib.pdf.extract import extract_mupdf
from pathlib import Path
import fitz

pdf = Path("data/paperstore/p2034r6.pdf")
doc = fitz.open(str(pdf))
page = doc[4]  # 0-indexed page 4
blocks = extract_mupdf(page, 4)
doc.close()

print(f"Page 4: {len(blocks)} extracted blocks\n")

# Show blocks in the Tony Table area (y > 350, code-related)
for b in blocks:
    all_text = "".join(sp.text for ln in b.lines for sp in ln.spans)
    if any(kw in all_text for kw in ["Before", "After", "new vocabulary",
            "move_only", "loss of", "mutable b", "as_owned"]):
        print(f"Block bbox=({b.bbox[0]:.0f},{b.bbox[1]:.0f},{b.bbox[2]:.0f},{b.bbox[3]:.0f}) "
              f"lines={len(b.lines)}")
        for li, ln in enumerate(b.lines):
            line_text = "".join(sp.text for sp in ln.spans)
            print(f"  L{li} y={ln.bbox[1]:.1f}: {line_text[:80]}")
            for sp in ln.spans[:3]:
                print(f"      span: text={repr(sp.text[:40])}")
        print()
