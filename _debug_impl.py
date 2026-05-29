"""Check if MuPDF find_tables() detects Feature 3/5 tables."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import fitz

print(f"PyMuPDF version: {fitz.version}")
print(f"Has find_tables: {hasattr(fitz.Page, 'find_tables')}")

doc = fitz.open(r"data\paperstore\p2034r6.pdf")

for pg_idx in range(len(doc)):
    page = doc[pg_idx]
    try:
        tables = page.find_tables()
        if tables.tables:
            print(f"\nPage {pg_idx+1} (idx {pg_idx}): {len(tables.tables)} table(s)")
            for ti, t in enumerate(tables.tables):
                print(f"  Table {ti}: bbox={tuple(round(x) for x in t.bbox)} "
                      f"rows={t.row_count} cols={t.col_count}")
                # Show header
                if t.header:
                    print(f"    header: {t.header.names}")
                # Show first 2 rows
                extracted = t.extract()
                for ri, row in enumerate(extracted[:3]):
                    cells = [str(c)[:30] if c else "" for c in row]
                    print(f"    row[{ri}]: {cells}")
    except Exception as e:
        print(f"  Page {pg_idx+1}: find_tables() error: {e}")

doc.close()
