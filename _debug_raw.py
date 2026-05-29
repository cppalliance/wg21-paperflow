"""Debug: Raw PDF blocks for p2034r6 page 4 Tony Table area."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "packages/tomd/src")
from tomd.lib.pdf.extract import extract_mupdf
from pathlib import Path
import fitz

pdf = Path("data/paperstore/p2034r6.pdf")
doc = fitz.open(str(pdf))
page = doc[4]  # page index 4 = page 5 in PDF (0-indexed)

# Get raw blocks from MuPDF
blocks_raw = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

print(f"Page 4 has {len(blocks_raw)} raw blocks\n")

# Show blocks in the table area (roughly middle of page)
# Let's look for code-like content with "Before"/"After"
for b_idx, block in enumerate(blocks_raw):
    if block["type"] != 0:  # text blocks only
        continue
    # Get all text in block
    all_text = ""
    for line in block["lines"]:
        for span in line["spans"]:
            all_text += span["text"]
    
    if any(kw in all_text for kw in ["Before", "After", "new vocabulary", "move_only", "loss of"]):
        bbox = block["bbox"]
        print(f"Block {b_idx} bbox=({bbox[0]:.0f},{bbox[1]:.0f},{bbox[2]:.0f},{bbox[3]:.0f}):")
        for li, line in enumerate(block["lines"]):
            line_text = "".join(sp["text"] for sp in line["spans"])
            y = line["bbox"][1]
            print(f"  Line {li} y={y:.1f}: {line_text[:80]}")
        print()

doc.close()
