"""Scan all PDFs in paperstore for tables and compute classification signals.

Outputs a CSV inventory of every detected table with signals that will
drive table_analyzer.py classification logic.

Usage: uv run python _scan_tables.py
"""

import csv
import json
import sys
from pathlib import Path

import fitz  # pymupdf

# Add tomd to path
sys.path.insert(0, str(Path(__file__).parent / "packages" / "tomd" / "src"))

from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf.table import detect_tables
from tomd.lib.pdf.types import Section, SectionKind

DATA_DIR = Path(__file__).parent / "data" / "paperstore"
OUTPUT_CSV = Path(__file__).parent / "_scan_tables_inventory.csv"
OUTPUT_JSON = Path(__file__).parent / "_scan_tables_summary.json"


def compute_table_signals(sec: Section) -> dict:
    """Compute classification signals for a detected table section."""
    rows = sec.columns  # list of rows, each row = list of cells, each cell = list of Spans
    if not rows:
        return {"num_rows": 0, "num_cols": 0, "error": "empty"}

    num_rows = len(rows)
    num_cols = max(len(row) for row in rows) if rows else 0

    total_cells = 0
    empty_cells = 0
    monospace_cells = 0
    max_word_count = 0
    total_word_count = 0
    has_links = False
    col_counts = []

    for row in rows:
        col_counts.append(len(row))
        for cell_spans in row:
            total_cells += 1
            cell_text = "".join(s.text for s in cell_spans).strip()
            if not cell_text:
                empty_cells += 1
                continue

            words = cell_text.split()
            word_count = len(words)
            total_word_count += word_count
            if word_count > max_word_count:
                max_word_count = word_count

            if all(s.monospace for s in cell_spans if s.text.strip()):
                monospace_cells += 1

            if any(s.link_url for s in cell_spans):
                has_links = True

    non_empty_cells = total_cells - empty_cells
    empty_ratio = empty_cells / total_cells if total_cells > 0 else 0
    mono_ratio = monospace_cells / non_empty_cells if non_empty_cells > 0 else 0
    col_count_consistent = len(set(col_counts)) <= 2  # allow 1 variance

    return {
        "num_rows": num_rows,
        "num_cols": num_cols,
        "total_cells": total_cells,
        "empty_cells": empty_cells,
        "empty_ratio": round(empty_ratio, 2),
        "monospace_cells": monospace_cells,
        "mono_ratio": round(mono_ratio, 2),
        "max_word_count": max_word_count,
        "avg_word_count": round(total_word_count / non_empty_cells, 1) if non_empty_cells else 0,
        "has_links": has_links,
        "col_count_consistent": col_count_consistent,
        "col_counts_unique": sorted(set(col_counts)),
    }


def classify_from_signals(signals: dict) -> str:
    """Preliminary classification based on signals."""
    if signals.get("error"):
        return "ERROR"
    if signals["mono_ratio"] >= 0.8:
        return "CODE_COMPARISON"
    if signals["empty_ratio"] > 0.5:
        return "FALSE_POSITIVE"
    if not signals["col_count_consistent"]:
        return "FALSE_POSITIVE"
    if signals["max_word_count"] > 40:
        return "PROSE_TABLE"
    if signals["max_word_count"] > 15:
        return "PROSE_TABLE"
    return "CLEAN_MATRIX"


def scan_pdf(pdf_path: Path) -> list[dict]:
    """Scan one PDF for tables, return list of table signal dicts."""
    results = []
    paper_id = pdf_path.stem

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        return [{"paper_id": paper_id, "error": str(e)}]

    try:
        all_blocks = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = extract_mupdf(page, page_num)
            all_blocks.extend(blocks)

        table_sections, _ = detect_tables(all_blocks)

        for idx, sec in enumerate(table_sections):
            signals = compute_table_signals(sec)
            classification = classify_from_signals(signals)
            results.append({
                "paper_id": paper_id,
                "table_index": idx,
                "page_num": sec.page_num if hasattr(sec, "page_num") else -1,
                "classification": classification,
                **signals,
            })
    except Exception as e:
        results.append({"paper_id": paper_id, "error": str(e)})
    finally:
        doc.close()

    return results


def main():
    pdf_files = sorted(DATA_DIR.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDFs in {DATA_DIR}")

    all_results = []
    papers_with_tables = 0
    total_tables = 0

    for i, pdf_path in enumerate(pdf_files):
        results = scan_pdf(pdf_path)
        if results and not results[0].get("error"):
            if any(r.get("num_rows", 0) > 0 for r in results):
                papers_with_tables += 1
            total_tables += len([r for r in results if r.get("num_rows", 0) > 0])
        all_results.extend(results)

        if (i + 1) % 20 == 0:
            print(f"  Scanned {i + 1}/{len(pdf_files)} PDFs...")

    # Filter to only tables (exclude errors and empty)
    table_results = [r for r in all_results if r.get("num_rows", 0) > 0]
    error_results = [r for r in all_results if r.get("error")]

    # Write CSV
    if table_results:
        fieldnames = [
            "paper_id", "table_index", "page_num", "classification",
            "num_rows", "num_cols", "total_cells", "empty_cells", "empty_ratio",
            "monospace_cells", "mono_ratio", "max_word_count", "avg_word_count",
            "has_links", "col_count_consistent", "col_counts_unique",
        ]
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(table_results)
        print(f"\nWrote {len(table_results)} table rows to {OUTPUT_CSV}")

    # Write summary JSON
    classification_dist = {}
    for r in table_results:
        cls = r.get("classification", "UNKNOWN")
        classification_dist[cls] = classification_dist.get(cls, 0) + 1

    summary = {
        "total_pdfs_scanned": len(pdf_files),
        "papers_with_tables": papers_with_tables,
        "total_tables_detected": total_tables,
        "classification_distribution": classification_dist,
        "errors": len(error_results),
        "error_papers": [r["paper_id"] for r in error_results],
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote summary to {OUTPUT_JSON}")

    # Print summary
    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"  PDFs scanned: {len(pdf_files)}")
    print(f"  Papers with tables: {papers_with_tables}")
    print(f"  Total tables detected: {total_tables}")
    print(f"  Errors: {len(error_results)}")
    print(f"\nClassification distribution:")
    for cls, count in sorted(classification_dist.items()):
        print(f"  {cls}: {count}")


if __name__ == "__main__":
    main()
