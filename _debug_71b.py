import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "packages" / "tomd" / "src"))
import fitz

pdf_path = str(pathlib.Path(__file__).resolve().parent / "data" / "paperstore" / "p4088r0.pdf")
doc = fitz.open(pdf_path)

for pg_num in range(doc.page_count):
    page = doc[pg_num]
    blocks = page.get_text("dict")["blocks"]
    found = False
    for b in blocks:
        if b["type"] != 0:
            continue
        for line in b.get("lines", []):
            for sp in line.get("spans", []):
                if "Bold" in sp.get("font", "") and "7.1" in sp["text"] and "Caller" in sp["text"]:
                    found = True
                    break
            if found:
                break
        if found:
            break
    if found:
        print(f"=== Page {pg_num}: Block column analysis ===")
        for bi, b in enumerate(blocks):
            if b["type"] != 0:
                continue
            lines = b.get("lines", [])
            if not lines:
                continue
            y0 = b["bbox"][1]
            # Check if block looks columnar
            cols = set()
            for L in lines:
                cols.add(round(L["bbox"][0], 0))
            is_columnar = len(cols) >= 2 and (max(cols) - min(cols)) > 50
            first_text = "".join(s["text"] for s in lines[0]["spans"])[:60]
            print(f"B{bi}: cols={sorted(cols)} columnar={is_columnar} [{first_text}]")
        break

doc.close()
