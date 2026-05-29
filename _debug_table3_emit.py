"""Check remaining blocks after spec-label pass."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "packages", "tomd", "src"))

from pathlib import Path
import fitz

PDF_PATH = Path(os.path.join(os.path.dirname(__file__), "data", "paperstore", "p4003r1.pdf"))

from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf.table import _detect_spec_tables_by_label, detect_tables

doc = fitz.open(str(PDF_PATH))
all_blocks = []
for page_idx in range(doc.page_count):
    page = doc[page_idx]
    page_blocks = extract_mupdf(page, page_idx)
    all_blocks.extend(page_blocks)
doc.close()

spec_tables, spec_used = _detect_spec_tables_by_label(all_blocks)
remaining = [b for i, b in enumerate(all_blocks) if i not in spec_used]

# Show remaining blocks on pages 55-58
print("=== Remaining blocks on pages 55-58 after spec-label ===")
for b in remaining:
    if 55 <= b.page_num <= 58:
        t = b.text.strip()[:80].replace("\n", "\\n")
        print(f"  page={b.page_num} y={b.bbox[1]:6.1f} w={b.bbox[2]-b.bbox[0]:5.1f} "
              f"text='{t}'")

print(f"\nSpec-used: {len(spec_used)} block indices")
print(f"Remaining on pages 55-58: "
      f"{sum(1 for b in remaining if 55 <= b.page_num <= 58)}")

# Now run full detect_tables
table_sections, det_remaining = detect_tables(
    list(all_blocks), page_mupdf_tables={}, two_column_pages=set())
print(f"\ndetect_tables: {len(table_sections)} tables")
for i, ts in enumerate(table_sections):
    if ts.page_num >= 52:
        rows = ts.columns or []
        r0 = "".join(s.text for s in rows[0][0]).strip()[:40] if rows else ""
        print(f"  {i}: page={ts.page_num} rows={len(rows)} "
              f"src={ts.table_source} r0='{r0}'")

print(f"Total <table> in md: {r.md.count('<table ')}")

# Check spec table 3 specifically
spec3 = [s for s in r.sections if s.kind == SectionKind.TABLE 
         and s.table_source == "spec_label" and s.page_num == 55]
print(f"\nSpec Table 3 in sections: {len(spec3)}")
if not spec3:
    # Check if page 55 has ANY section
    p55 = [s for s in r.sections if s.page_num == 55]
    print(f"  Total sections on page 55: {len(p55)}")
    for s in p55[:5]:
        print(f"    kind={s.kind} text={s.text[:60]!r}")

print(f"\nAll TABLE sections:")
for i, sec in enumerate(r.sections):
    if sec.kind == SectionKind.TABLE:
        rows = sec.columns or []
        cont = getattr(sec, "table_continuation", False)
        r0 = ""
        if rows:
            r0 = "".join(s.text for s in rows[0][0]).strip()[:40]
        print(f"  [{i}] page={sec.page_num} rows={len(rows)} "
              f"cont={cont} src={sec.table_source} strat={sec.table_strategy} "
              f"r0='{r0}'")

# Check for Table 4 label and content
t4_label = r.md.find("Table 4 - ExecutionContext")
if t4_label >= 0:
    chunk = r.md[t4_label:t4_label+500]
    print(f"\nTable 4 label found at char {t4_label}")
    print(f"  Next 200 chars: {chunk[:200]!r}")
    t4_table = r.md.find("<table", t4_label)
    if t4_table >= 0 and t4_table < t4_label + 2000:
        print(f"  <table> found at char {t4_table} (offset +{t4_table - t4_label})")
    else:
        print(f"  NO <table> within 2000 chars after label!")
