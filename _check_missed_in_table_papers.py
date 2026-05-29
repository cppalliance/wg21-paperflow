"""Check PDFs WITH detected tables for additional missed tables.

Strategy: Look at raw page text for tabular patterns that exist on pages
where NO table was detected (comparing page coverage).
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import csv
import fitz
from pathlib import Path
from collections import defaultdict

DATA = Path(__file__).parent / "data" / "paperstore"
sys.path.insert(0, str(Path(__file__).parent / "packages" / "tomd" / "src"))
from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf.table import detect_tables


def get_table_pages():
    """Get pages that already have detected tables."""
    paper_pages = defaultdict(set)
    with open("_scan_tables_inventory.csv", "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = row["paper_id"]
            # page_num from scan might be -1 if not available
            # We'll recompute below
            paper_pages[pid].add(int(row.get("page_num", -1)))
    return paper_pages


def check_page_for_tabular_content(text: str) -> list[str]:
    """Check raw page text for tabular indicators NOT involving code pipes."""
    indicators = []
    lines = text.split("\n")
    
    # Look for "Table N:" captions that suggest a formal table
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower().startswith("table") and ":" in stripped[:20]:
            indicators.append(f"TABLE_CAPTION: {stripped[:60]}")
    
    # Look for lines with consistent multi-space column alignment
    # (3+ consecutive lines with similar gap patterns)
    aligned_groups = 0
    prev_gaps = None
    for line in lines:
        if len(line) < 10:
            prev_gaps = None
            continue
        # Find gap positions (runs of 3+ spaces)
        gaps = []
        in_gap = False
        gap_start = 0
        for j, ch in enumerate(line):
            if ch == ' ':
                if not in_gap:
                    in_gap = True
                    gap_start = j
            else:
                if in_gap and (j - gap_start) >= 3:
                    gaps.append(gap_start)
                in_gap = False
        
        if len(gaps) >= 2:
            if prev_gaps and len(gaps) == len(prev_gaps):
                # Check if gaps are roughly aligned (within 5 chars)
                if all(abs(a - b) <= 5 for a, b in zip(gaps, prev_gaps)):
                    aligned_groups += 1
            prev_gaps = gaps
        else:
            prev_gaps = None
    
    if aligned_groups >= 3:
        indicators.append(f"ALIGNED_COLUMNS: {aligned_groups} consecutive aligned rows")
    
    return indicators


def main():
    # Focus on a sample of papers with many pages where tables might be missed
    # These are papers where the detector found tables but might miss some
    sample_papers = [
        "p3839r0",  # 423 pages, 35 tables - might miss some
        "p4142r0",  # 59 pages, 0 tables! - wait this should have been checked already
        "p4135r0",  # 28 pages, 0 tables
        "p3955r0",  # 21 pages, 0 tables
        "p4158r0",  # 20 pages, 0 tables
        "p2000r5",  # 27 pages, 0 tables
        "p3874r1",  # 13 pages, 0 tables
        "p4016r0",  # 57 pages, 23 tables - might miss some
        "p3596r1",  # 100 pages, 129 tables
        "p4014r0",  # 25 pages, 11 tables
        "p4091r0",  # 16 pages, 7 tables
        "p3977r0",  # 13 pages, 6 tables
    ]
    
    for paper_id in sample_papers:
        pdf_path = DATA / f"{paper_id}.pdf"
        if not pdf_path.exists():
            continue
        
        doc = fitz.open(str(pdf_path))
        page_count = len(doc)
        
        # Run detect_tables to know which blocks are tables
        all_blocks = []
        page_block_counts = {}
        for page_num in range(page_count):
            page = doc[page_num]
            blocks = extract_mupdf(page, page_num)
            page_block_counts[page_num] = len(blocks)
            all_blocks.extend(blocks)
        
        table_sections, remaining = detect_tables(all_blocks)
        
        # Get pages with detected tables
        table_pages = set()
        for sec in table_sections:
            if sec.columns:
                for row in sec.columns:
                    for cell in row:
                        for span in cell:
                            if hasattr(span, 'page_num'):
                                table_pages.add(span.page_num)
                                break
                        if table_pages:
                            break
                    if table_pages:
                        break
        
        # Check pages WITHOUT detected tables for tabular content
        missed_on_pages = []
        for page_num in range(min(page_count, 30)):
            page = doc[page_num]
            text = page.get_text("text")
            indicators = check_page_for_tabular_content(text)
            if indicators:
                missed_on_pages.append((page_num, indicators))
        
        doc.close()
        
        if missed_on_pages:
            print(f"\n{paper_id} ({page_count} pages, {len(table_sections)} tables detected):")
            for page_num, indicators in missed_on_pages[:5]:
                for ind in indicators:
                    print(f"  Page {page_num}: {ind}")
        else:
            print(f"{paper_id} ({page_count} pages, {len(table_sections)} tables): no missed indicators")


if __name__ == "__main__":
    main()
