"""Regenerate all markdowns by calling convert_pdf directly."""
import sys
sys.path.insert(0, "packages/tomd/src")
sys.path.insert(0, "packages/paperstore/src")
import sqlite3
from pathlib import Path
from tomd.lib.pdf.pipeline import convert_pdf
from paperstore import SqliteBackend

db_path = Path("data/paperstore/paperstore.db")
backend = SqliteBackend(Path("data/paperstore"))

con = sqlite3.connect(str(db_path))
rows = con.execute(
    "SELECT paper_id, source_file FROM papers "
    "WHERE source_file IS NOT NULL ORDER BY paper_id"
).fetchall()
con.close()

total = len(rows)
success = 0
errors = []
for i, (pid, src) in enumerate(rows):
    pdf_path = Path("data/paperstore") / src
    if not pdf_path.exists():
        print(f"[{i+1}/{total}] {pid}: SKIP (no PDF)")
        continue
    try:
        md, prompts = convert_pdf(pdf_path)
        out_path = Path("data/paperstore/paperstore") / f"{pid.lower()}.md"
        out_path.write_text(md, encoding="utf-8")
        con2 = sqlite3.connect(str(db_path))
        con2.execute(
            "UPDATE papers SET markdown_path = ? WHERE paper_id = ?",
            (str(out_path.resolve()), pid))
        con2.commit()
        con2.close()
        success += 1
        if (i + 1) % 20 == 0:
            print(f"[{i+1}/{total}] {pid}: OK ({success} done)")
    except Exception as e:
        errors.append((pid, str(e)))
        print(f"[{i+1}/{total}] {pid}: ERROR {e}")

print(f"\nDone: {success}/{total} converted, {len(errors)} errors")
if errors:
    for pid, err in errors:
        print(f"  {pid}: {err}")
