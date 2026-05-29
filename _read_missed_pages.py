"""Deep-read specific pages that have potential missed tables."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import fitz
from pathlib import Path

DATA = Path(__file__).parent / "data" / "paperstore"


def read_page(paper_id: str, page_num: int, context_lines: int = 40):
    """Read and print raw text from a specific page."""
    pdf_path = DATA / f"{paper_id}.pdf"
    doc = fitz.open(str(pdf_path))
    page = doc[page_num]
    text = page.get_text("text")
    doc.close()
    
    lines = text.split("\n")
    print(f"\n{'='*70}")
    print(f"  {paper_id} - Page {page_num} ({len(lines)} lines)")
    print(f"{'='*70}")
    for i, line in enumerate(lines[:context_lines]):
        print(f"  {i:3d}| {line}")
    if len(lines) > context_lines:
        print(f"  ... ({len(lines) - context_lines} more lines)")


# Check the specific flagged pages
pages_to_check = [
    ("p4142r0", 9),   # 3 aligned rows
    ("p4016r0", 16),  # 8 aligned rows
    ("p4016r0", 19),  # 19 aligned rows!
    ("p4016r0", 27),  # TABLE_CAPTION
    ("p4014r0", 8),   # 4 aligned rows
    ("p4014r0", 15),  # 4 aligned rows
]

for paper_id, page_num in pages_to_check:
    read_page(paper_id, page_num)
