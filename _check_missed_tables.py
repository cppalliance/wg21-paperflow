"""Identify PDFs with NO tables detected, then manually inspect their text for missed tables."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import fitz
from pathlib import Path

DATA = Path(__file__).parent / "data" / "paperstore"

sys.path.insert(0, str(Path(__file__).parent / "packages" / "tomd" / "src"))
from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf.table import detect_tables


def get_all_pdfs():
    return sorted(DATA.glob("*.pdf"))


def get_pdfs_with_tables():
    """Return set of paper_ids that had tables detected."""
    import csv
    ids = set()
    with open("_scan_tables_inventory.csv", "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ids.add(row["paper_id"])
    return ids


def check_pdf_for_table_indicators(pdf_path: Path) -> dict:
    """Open PDF and look for visual table indicators in raw text."""
    doc = fitz.open(str(pdf_path))
    page_count = len(doc)
    
    findings = {
        "paper_id": pdf_path.stem,
        "pages": page_count,
        "has_table_like_content": False,
        "indicators": [],
    }
    
    for page_num in range(min(page_count, 30)):  # cap at 30 pages
        page = doc[page_num]
        text = page.get_text("text")
        lines = text.split("\n")
        
        # Look for table indicators
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Indicator 1: Lines with multiple pipe characters
            if line_stripped.count("|") >= 2:
                findings["has_table_like_content"] = True
                findings["indicators"].append(f"p{page_num}: PIPES: {line_stripped[:80]}")
            
            # Indicator 2: Lines that look like column headers followed by separator
            if "---" in line_stripped and "|" in line_stripped:
                findings["has_table_like_content"] = True
                findings["indicators"].append(f"p{page_num}: SEPARATOR: {line_stripped[:80]}")
            
            # Indicator 3: "Table N" or "Table:" references
            if line_stripped.lower().startswith("table ") and any(c.isdigit() for c in line_stripped):
                findings["indicators"].append(f"p{page_num}: TABLE_REF: {line_stripped[:80]}")
            
            # Indicator 4: Aligned columns (multiple whitespace gaps in data lines)
            parts = line_stripped.split("   ")  # triple-space as column separator
            if len(parts) >= 3 and all(len(p.strip()) > 0 for p in parts[:3]):
                if len(line_stripped) > 20:  # not too short
                    findings["has_table_like_content"] = True
                    findings["indicators"].append(f"p{page_num}: ALIGNED_COLS: {line_stripped[:80]}")

    doc.close()
    
    # Deduplicate and limit indicators
    seen = set()
    unique = []
    for ind in findings["indicators"]:
        key = ind[:40]
        if key not in seen:
            seen.add(key)
            unique.append(ind)
    findings["indicators"] = unique[:10]  # max 10 per paper
    
    return findings


def main():
    all_pdfs = get_all_pdfs()
    detected_ids = get_pdfs_with_tables()
    
    no_table_pdfs = [p for p in all_pdfs if p.stem not in detected_ids]
    print(f"PDFs without detected tables: {len(no_table_pdfs)}")
    print(f"PDFs with detected tables: {len(detected_ids)}")
    print()
    
    missed_tables = []
    
    for pdf_path in no_table_pdfs:
        result = check_pdf_for_table_indicators(pdf_path)
        if result["has_table_like_content"]:
            missed_tables.append(result)
            print(f"  POTENTIAL MISS: {result['paper_id']} ({result['pages']} pages)")
            for ind in result["indicators"][:5]:
                print(f"    {ind}")
            print()
        else:
            print(f"  OK (no tables): {result['paper_id']} ({result['pages']} pages)")
    
    print(f"\n{'='*60}")
    print(f"SUMMARY:")
    print(f"  PDFs checked: {len(no_table_pdfs)}")
    print(f"  Potential missed tables: {len(missed_tables)}")
    for m in missed_tables:
        print(f"    {m['paper_id']}: {len(m['indicators'])} indicators")


if __name__ == "__main__":
    main()
