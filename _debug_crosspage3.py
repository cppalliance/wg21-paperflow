# Copyright (c) 2026 Sergio DuBois -- temporary debug script, delete after use
"""Trace Table 2 (io_runnable) cross-page issue on pages 53-54."""
import sys, os, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "packages", "tomd", "src"))
logging.basicConfig(level=logging.WARNING)

from pathlib import Path
import fitz
from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf.cleanup import cleanup_text
from tomd.lib.pdf.spans import normalize_spans
from tomd.lib.pdf.table import detect_tables
from tomd.lib.pdf.docling_backend import (
    extract_docling_tables, _blocks_in_bbox, _collect_spans_for_cell,
    _flat_spans_from_section,
)

pdf = Path("data/paperstore/p4003r1.pdf")

# 1. Extract blocks exactly like pipeline
doc = fitz.open(str(pdf))
all_blocks = []
for i, page in enumerate(doc):
    all_blocks.extend(extract_mupdf(page, i))
doc.close()
all_blocks = cleanup_text(all_blocks)
all_blocks = normalize_spans(all_blocks)

# 2a. Collect MuPDF native tables (like pipeline does)
doc2 = fitz.open(str(pdf))
page_mupdf_tables = {}
for pg_idx in range(doc2.page_count):
    page = doc2[pg_idx]
    try:
        tabs = page.find_tables()
        if tabs and tabs.tables:
            pg_tbls = []
            for tab in tabs.tables:
                cells_list = []
                for cell in tab.cells:
                    if cell:
                        cells_list.append(cell)
                    else:
                        cells_list.append(None)
                pg_tbls.append({
                    "bbox": tab.bbox,
                    "row_count": tab.row_count,
                    "col_count": tab.col_count,
                    "cells": cells_list,
                })
            if pg_tbls:
                page_mupdf_tables[pg_idx] = pg_tbls
    except Exception:
        pass
doc2.close()

print(f"=== MuPDF find_tables() on pages 53-54 ===")
for pg in (53, 54):
    tbls = page_mupdf_tables.get(pg, [])
    for t in tbls:
        print(f"  Page {pg}: bbox={tuple(round(x,1) for x in t['bbox'])}, {t['row_count']}x{t['col_count']}")

# 2b. detect_tables with MuPDF native tables
table_sections, remaining = detect_tables(all_blocks, page_mupdf_tables=page_mupdf_tables, two_column_pages=set())

# 3. What tables on pages 53 and 54?
print("=== ALL TABLE SECTIONS near pages 52-55 ===")
for sec in table_sections:
    if sec.page_num in (52, 53, 54, 55):
        y0 = sec.lines[0].bbox[1] if sec.lines else 0
        y1 = sec.lines[-1].bbox[3] if sec.lines else 0
        ncols = len(sec.columns[0]) if sec.columns else 0
        nrows = len(sec.columns) if sec.columns else 0
        hdr = ""
        if sec.columns:
            hdr = " | ".join("".join(s.text for s in c).strip()[:20] for c in sec.columns[0])
        cont = getattr(sec, 'table_continuation', False)
        print(f"  Page {sec.page_num}: {nrows}x{ncols}, y={y0:.1f}-{y1:.1f}, "
              f"kind={sec.table_kind}, cont={cont}")
        print(f"    Header: [{hdr}]")

# 4. Remaining blocks on pages 53-54
print("\n=== REMAINING BLOCKS on page 53 ===")
rem53 = [b for b in remaining if b.page_num == 53]
for b in rem53:
    for ln in b.lines:
        txt = " ".join(s.text for s in ln.spans).strip()[:90]
        print(f"  y={ln.bbox[1]:.1f}-{ln.bbox[3]:.1f} x={ln.bbox[0]:.1f} '{txt}'")

print("\n=== REMAINING BLOCKS on page 54 (first 15) ===")
rem54 = [b for b in remaining if b.page_num == 54]
for b in rem54[:15]:
    for ln in b.lines:
        txt = " ".join(s.text for s in ln.spans).strip()[:90]
        print(f"  y={ln.bbox[1]:.1f}-{ln.bbox[3]:.1f} x={ln.bbox[0]:.1f} '{txt}'")

# 5. Docling tables on pages 52-55
docling_tables = extract_docling_tables(pdf)
print("\n=== DOCLING TABLES on pages 52-55 ===")
for pg in (52, 53, 54, 55):
    for t in docling_tables.get(pg, []):
        print(f"  Page {pg}: bbox={tuple(round(x,1) for x in t['bbox'])}, {t['num_rows']}x{t['num_cols']}")

print("\n=== DOCLING TABLE DETAIL on page 54 ===")
dtbl54 = docling_tables.get(54, [])
for t in dtbl54:
    print(f"  bbox={t['bbox']}, {t['num_rows']}x{t['num_cols']}")
    # Header cells
    for c in t["cells"]:
        if c["row"] == 0:
            print(f"    Header r0c{c['col']}: bbox={c['bbox']}, text='{c.get('text','')[:50]}'")

# 6. _blocks_in_bbox for page 54
if dtbl54:
    tbl = dtbl54[0]
    matched, indices = _blocks_in_bbox(remaining, 54, tbl["bbox"])
    print(f"\n=== _blocks_in_bbox(remaining, page=54, docling_bbox) -> {len(matched)} blocks ===")
    for b in matched:
        for ln in b.lines:
            txt = " ".join(s.text for s in ln.spans).strip()[:90]
            print(f"  y={ln.bbox[1]:.1f}-{ln.bbox[3]:.1f} '{txt}'")

    # 6b. Check what's in the section's own page_spans
    sec54 = [s for s in table_sections if s.page_num == 54]
    if sec54:
        sec = sec54[0]
        sec_spans = _flat_spans_from_section(sec)
        print(f"\n=== Section on page 54: {len(sec.lines)} lines, {len(sec_spans)} spans ===")
        header_texts = {"expression", "return type", "assertion/note"}
        for sp in sec_spans:
            if any(k in sp.text.lower() for k in header_texts):
                print(f"  FOUND in section: '{sp.text.strip()[:50]}' origin=({sp.origin[0]:.1f}, {sp.origin[1]:.1f})")
        
        # Now try matching with section spans
        print(f"\n=== Docling header cell matching using SECTION spans only ===")
        for c in tbl["cells"]:
            if c["row"] == 0:
                cbbox = c["bbox"]
                hits = _collect_spans_for_cell(cbbox, sec_spans)
                txt = "".join(s.text for s in hits).strip()[:60]
                print(f"  Header r0c{c['col']}: '{txt}'")
    else:
        print("\n=== NO table section on page 54 ===")

    # 6c. Simulate FULL Docling enrichment on the section
    from tomd.lib.pdf.table import _classify_and_annotate
    
    num_rows_d = tbl["num_rows"]
    num_cols_d = tbl["num_cols"]
    cells_d = tbl["cells"]
    
    grid = [[[] for _ in range(num_cols_d)] for _ in range(num_rows_d)]
    for cell_d in cells_d:
        r, c = cell_d["row"], cell_d["col"]
        cbbox = cell_d["bbox"]
        if r < num_rows_d and c < num_cols_d:
            spans = _collect_spans_for_cell(cbbox, sec_spans)
            grid[r][c] = spans
    
    print(f"\n=== SIMULATED DOCLING ENRICHMENT: {num_rows_d}x{num_cols_d} grid ===")
    for ri, row in enumerate(grid):
        cells_txt = []
        for ci, cell_spans in enumerate(row):
            txt = "".join(s.text for s in cell_spans).strip()[:30]
            cells_txt.append(txt)
        print(f"  Row {ri}: {' | '.join(cells_txt)}")
    
    kind_val, strategy_val, grid = _classify_and_annotate(grid)
    print(f"\n  -> kind={kind_val}, strategy={strategy_val}")
    print(f"  -> Grid after classify: {len(grid)} rows x {len(grid[0]) if grid else 0} cols")
    if grid:
        print(f"  -> Header: {' | '.join(''.join(s.text for s in c).strip()[:25] for c in grid[0])}")
    
    # 7. Try matching header cells using ALL remaining page 54 spans
    page_spans = []
    for blk in matched:
        for line in blk.lines:
            page_spans.extend(line.spans)
    print(f"\n=== Total page_spans from remaining blocks: {len(page_spans)} ===")
    
    # Check header spans exist
    for sp in page_spans:
        if sp.text.strip() in ("expression", "return type"):
            print(f"  FOUND span '{sp.text.strip()}' origin=({sp.origin[0]:.1f}, {sp.origin[1]:.1f})")
    
    for c in tbl["cells"]:
        if c["row"] == 0:
            cbbox = c["bbox"]
            hits = _collect_spans_for_cell(cbbox, page_spans)
            txt = "".join(s.text for s in hits).strip()[:60]
            print(f"  Header r0c{c['col']}: bbox=({cbbox[0]:.1f},{cbbox[1]:.1f},{cbbox[2]:.1f},{cbbox[3]:.1f}) -> '{txt}'")
