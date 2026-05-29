# Copyright (c) 2026 Sergio DuBois -- temporary debug script, delete after use
"""Simulate the cross-page spec-table absorption fix for Table 2."""
import sys, os, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "packages", "tomd", "src"))
logging.basicConfig(level=logging.WARNING)

from pathlib import Path
import fitz
from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf.cleanup import cleanup_text
from tomd.lib.pdf.spans import normalize_spans
from tomd.lib.pdf.table import detect_tables, _classify_and_annotate
from tomd.lib.pdf.docling_backend import (
    extract_docling_tables, enrich_tables_with_docling,
    _flat_spans_from_section, _collect_spans_for_cell,
)
from tomd.lib.pdf.types import Span

pdf = Path("data/paperstore/p4003r1.pdf")

# ---- Full pipeline reproduction ----
doc = fitz.open(str(pdf))
all_blocks = []
for i, page in enumerate(doc):
    all_blocks.extend(extract_mupdf(page, i))

page_mupdf_tables = {}
for pg_idx in range(doc.page_count):
    page = doc[pg_idx]
    try:
        tabs = page.find_tables()
        if tabs and tabs.tables:
            pg_tbls = []
            for tab in tabs.tables:
                cells_list = [c if c else None for c in tab.cells]
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
doc.close()

all_blocks = cleanup_text(all_blocks)
all_blocks = normalize_spans(all_blocks)

table_sections, remaining = detect_tables(
    all_blocks, page_mupdf_tables=page_mupdf_tables, two_column_pages=set())

# ---- Docling enrichment ----
docling_tables = extract_docling_tables(pdf)
n = enrich_tables_with_docling(table_sections, docling_tables, remaining)
print(f"Docling enriched {n} table(s)")

# ---- Find the SPEC_TABLE on page 54 ----
spec_sec = None
for sec in table_sections:
    if sec.page_num == 54 and sec.table_kind == "spec_table":
        spec_sec = sec
        break

if not spec_sec:
    print("ERROR: No spec_table found on page 54!")
    print("Tables found:")
    for sec in table_sections:
        if sec.page_num in (52, 53, 54, 55):
            print(f"  Page {sec.page_num}: kind={sec.table_kind}")
    sys.exit(1)

print(f"\n=== BEFORE FIX: spec_table on page 54 ===")
print(f"  Grid: {len(spec_sec.columns)} rows x {len(spec_sec.columns[0])} cols")
for ri, row in enumerate(spec_sec.columns):
    cells_txt = " | ".join("".join(s.text for s in c).strip()[:30] for c in row)
    print(f"  Row {ri}: {cells_txt}")

# ---- SIMULATE THE FIX ----
# Get Docling cell info for column boundaries
dtbl = docling_tables[54][0]
cells = dtbl["cells"]
num_cols = dtbl["num_cols"]

col_x_min = {}
col_x_max = {}
for c in cells:
    ci = c["col"]
    x0, _, x1, _ = c["bbox"]
    col_x_min[ci] = min(col_x_min.get(ci, x0), x0)
    col_x_max[ci] = max(col_x_max.get(ci, x1), x1)

bounds = []
for i in range(num_cols - 1):
    bounds.append((col_x_max[i] + col_x_min[i + 1]) / 2)
print(f"\nColumn boundaries: {[f'{b:.1f}' for b in bounds]}")

# Get header text from grid
hdr_c0 = "".join(s.text for s in spec_sec.columns[0][0]).strip().lower()
print(f"Looking for header anchor: '{hdr_c0}'")

# Find header on page 53
prev_page = 53
prev_blocks = [(i, b) for i, b in enumerate(remaining) if b.page_num == prev_page]
print(f"Remaining blocks on page {prev_page}: {len(prev_blocks)}")

header_y = None
for idx, blk in prev_blocks:
    for ln in blk.lines:
        txt = " ".join(s.text for s in ln.spans).strip().lower()
        if hdr_c0 in txt:
            header_y = ln.bbox[1]
            break
    if header_y is not None:
        break

if header_y is None:
    print("ERROR: Header not found on prev page!")
    sys.exit(1)

print(f"Header found at y={header_y:.1f}")

def col_for_x(x):
    for i, b in enumerate(bounds):
        if x < b:
            return i
    return num_cols - 1

# Collect all lines at/below header on prev page
_PAGE_BOTTOM_CUTOFF = 790.0
col_lines = {i: [] for i in range(num_cols)}
consumed_block_indices = set()

for idx, blk in prev_blocks:
    for ln in blk.lines:
        y_mid = (ln.bbox[1] + ln.bbox[3]) / 2
        if y_mid < header_y - 5 or y_mid > _PAGE_BOTTOM_CUTOFF:
            continue
        x = ln.bbox[0]
        ci = col_for_x(x)
        col_lines[ci].append((y_mid, ln, idx))
        consumed_block_indices.add(idx)

for ci in col_lines:
    col_lines[ci].sort(key=lambda t: t[0])

print(f"\nLines collected by column:")
for ci in range(num_cols):
    print(f"  Col {ci}: {len(col_lines[ci])} lines")
    for y, ln, _ in col_lines[ci]:
        txt = " ".join(s.text for s in ln.spans).strip()[:50]
        print(f"    y={y:.1f} '{txt}'")

# Determine rows: use col 0 and col 1 as anchors (shorter columns)
anchor_ys = []
for y, ln, _ in col_lines[0]:
    anchor_ys.append(y)
for y, ln, _ in col_lines[1]:
    if not any(abs(y - ay) < 10 for ay in anchor_ys):
        anchor_ys.append(y)
anchor_ys.sort()

# Cluster anchors into rows
row_centers = []
if anchor_ys:
    cluster = [anchor_ys[0]]
    for ay in anchor_ys[1:]:
        if ay - cluster[-1] > 25:
            row_centers.append(sum(cluster) / len(cluster))
            cluster = [ay]
        else:
            cluster.append(ay)
    row_centers.append(sum(cluster) / len(cluster))

print(f"\nRow anchor y-centers: {[f'{y:.1f}' for y in row_centers]}")

# First row center should be the header, skip it
# Remaining centers are data rows
if len(row_centers) < 2:
    print("Only header found on prev page, no data rows to absorb")
    sys.exit(0)

data_row_centers = row_centers[1:]
header_center = row_centers[0]

# Build data rows using row boundaries
# Row boundary: midpoint between consecutive row centers
row_boundaries = []
for i, drc in enumerate(data_row_centers):
    if i == 0:
        y_start = (header_center + drc) / 2
    else:
        y_start = (data_row_centers[i - 1] + drc) / 2
    if i == len(data_row_centers) - 1:
        y_end = _PAGE_BOTTOM_CUTOFF
    else:
        y_end = (drc + data_row_centers[i + 1]) / 2
    row_boundaries.append((y_start, y_end))

print(f"Data row boundaries: {[(f'{s:.1f}', f'{e:.1f}') for s, e in row_boundaries]}")

new_rows = []
for (y_start, y_end) in row_boundaries:
    row = [[] for _ in range(num_cols)]
    for ci in range(num_cols):
        cell_lines = [(y, ln) for y, ln, _ in col_lines[ci]
                      if y_start <= y <= y_end]
        cell_lines.sort(key=lambda t: t[0])
        for y, ln in cell_lines:
            if row[ci]:
                row[ci].append(Span(text="\n"))
            row[ci].extend(ln.spans)
    
    if any(cell for cell in row):
        new_rows.append(row)

print(f"\n=== SIMULATED FIX: {len(new_rows)} new data row(s) ===")
for ri, row in enumerate(new_rows):
    cells_txt = " | ".join("".join(s.text for s in c).strip()[:35] for c in row)
    print(f"  New Row {ri}: {cells_txt}")

# Insert into grid after header
for i, row in enumerate(new_rows):
    spec_sec.columns.insert(1 + i, row)

print(f"\n=== AFTER FIX: spec_table on page 54 ===")
print(f"  Grid: {len(spec_sec.columns)} rows x {len(spec_sec.columns[0])} cols")
for ri, row in enumerate(spec_sec.columns):
    cells_txt = " | ".join("".join(s.text for s in c).strip()[:35] for c in row)
    print(f"  Row {ri}: {cells_txt}")

# Check consumed blocks
print(f"\n=== Consumed {len(consumed_block_indices)} block indices from remaining ===")
print(f"Remaining blocks on page 53 before: {len(prev_blocks)}")
print(f"Would remove: {len(consumed_block_indices)}")
remaining_after = [b for i, b in enumerate(remaining) if i not in consumed_block_indices]
rem53_after = [b for b in remaining_after if b.page_num == 53]
print(f"Remaining on page 53 after: {len(rem53_after)}")
for b in rem53_after:
    for ln in b.lines:
        txt = " ".join(s.text for s in ln.spans).strip()[:80]
        print(f"  y={ln.bbox[1]:.1f} '{txt}'")
