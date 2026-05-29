"""Deep inspection of specific papers."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "packages/tomd/src")
from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf.table import detect_tables
from pathlib import Path
import fitz

papers_to_check = {
    "p2034r6": "Tony Tables",
    "p3977r0": "FALSE_POSITIVE",
    "p4014r0": "FALSE_POSITIVE + pipe escape",
    "p3688r6": "pipe escape",
    "p4016r0": "space-aligned (deferred)",
}

for paper, desc in papers_to_check.items():
    pdf = Path(f"data/paperstore/{paper}.pdf")
    if not pdf.exists():
        print(f"{paper}: PDF NOT FOUND")
        continue
    doc = fitz.open(str(pdf))
    blocks = []
    for i in range(len(doc)):
        blocks.extend(extract_mupdf(doc[i], i))
    doc.close()
    secs, _ = detect_tables(blocks)
    
    print(f"=== {paper} ({desc}) ===")
    print(f"  Detected: {len(secs)} tables")
    kinds = {}
    for s in secs:
        k = s.table_kind
        kinds[k] = kinds.get(k, 0) + 1
    print(f"  Classification: {kinds}")
    for s in secs:
        if s.table_kind != "clean_matrix":
            rows = s.columns
            first_text = ""
            if rows and rows[0]:
                first_text = "".join(sp.text for sp in rows[0][0]).strip()[:50]
            print(f"    page {s.page_num}: {s.table_kind}/{s.table_strategy} "
                  f"({len(rows)} rows) first_cell=\"{first_text}\"")
    print()
