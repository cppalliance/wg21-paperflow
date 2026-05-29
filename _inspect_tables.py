"""Manual inspection of key PDFs to verify table classifications.

Checks: structure around detected tables, visual format type confirmation.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import fitz
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "packages" / "tomd" / "src"))
from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf.table import detect_tables

DATA = Path(__file__).parent / "data" / "paperstore"

PAPERS_TO_CHECK = [
    # PROSE_TABLE (highest word counts)
    "p3427r3", "p3844r3", "p1000r8", "p3978r0",
    # CODE_COMPARISON
    "p2034r6", "p3605r1", "p4088r0", "p4091r0",
    # FALSE_POSITIVE
    "p3839r0", "p3977r0", "p4014r0",
    # High table count
    "p3596r1", "p4016r0", "p4182r0", "p4098r0",
    # Additional random sampling
    "p3856r7", "p4007r0", "n5036", "p3846r1",
]


def inspect_paper(paper_id: str):
    pdf_path = DATA / f"{paper_id}.pdf"
    if not pdf_path.exists():
        print(f"\n{'='*60}\n  {paper_id}: NOT FOUND\n")
        return

    doc = fitz.open(str(pdf_path))
    page_count = len(doc)
    all_blocks = []
    for page_num in range(page_count):
        page = doc[page_num]
        blocks = extract_mupdf(page, page_num)
        all_blocks.extend(blocks)
    doc.close()

    table_sections, _ = detect_tables(all_blocks)

    print(f"\n{'='*60}")
    print(f"  {paper_id}: {page_count} pages, {len(table_sections)} tables detected")
    print(f"{'='*60}")

    for idx, sec in enumerate(table_sections):
        rows = sec.columns
        if not rows:
            print(f"  Table {idx}: EMPTY")
            continue

        num_rows = len(rows)
        num_cols = max(len(row) for row in rows) if rows else 0

        # Show first 3 rows content
        print(f"\n  Table {idx}: {num_rows} rows x {num_cols} cols")
        for row_idx, row in enumerate(rows[:3]):
            cells = []
            for cell_spans in row:
                cell_text = "".join(s.text for s in cell_spans).strip()
                if len(cell_text) > 50:
                    cell_text = cell_text[:47] + "..."
                cells.append(cell_text)
            print(f"    Row {row_idx}: {cells}")
        if num_rows > 3:
            print(f"    ... ({num_rows - 3} more rows)")


def main():
    for paper_id in PAPERS_TO_CHECK:
        inspect_paper(paper_id)


if __name__ == "__main__":
    main()
