import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "packages" / "tomd" / "src"))
import fitz

pdf_path = str(pathlib.Path(__file__).resolve().parent / "data" / "paperstore" / "p4088r0.pdf")
doc = fitz.open(pdf_path)

# Find page with a BOLD heading containing "7.1" and "Caller Is Erased"
target_page = None
for pg_num in range(doc.page_count):
    page = doc[pg_num]
    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        if b["type"] != 0:
            continue
        for line in b.get("lines", []):
            for sp in line.get("spans", []):
                if "Bold" in sp.get("font", "") and "7.1" in sp["text"] and "Caller" in sp["text"]:
                    target_page = pg_num
                    break
            if target_page is not None:
                break
        if target_page is not None:
            break
    if target_page is not None:
        break

if target_page is None:
    print("ERROR: Could not find bold heading 7.1 Caller Is Erased")
    print("Searching for any page with bold 7.1...")
    for pg_num in range(doc.page_count):
        page = doc[pg_num]
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if b["type"] != 0:
                continue
            for line in b.get("lines", []):
                for sp in line.get("spans", []):
                    if "Bold" in sp.get("font", "") and "7.1" in sp["text"]:
                        print(f"  Page {pg_num}: bold span: {sp['text'][:80]}")
    sys.exit(1)

print(f"=== Found section 7.1 heading on page {target_page} ===")

for pg in [target_page, target_page + 1]:
    if pg >= doc.page_count:
        break
    page = doc[pg]
    print(f"\n{'='*60}")
    print(f"PAGE {pg}")
    print(f"{'='*60}")
    blocks = page.get_text("dict")["blocks"]
    for bi, b in enumerate(blocks):
        if b["type"] != 0:
            continue
        lines = b.get("lines", [])
        if not lines:
            continue
        bbox = b["bbox"]
        print(f"\nBlock {bi}: {len(lines)} lines, bbox=({bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f})")
        for li, line in enumerate(lines):
            spans = line.get("spans", [])
            if not spans:
                continue
            font = spans[0].get("font", "?")[:20]
            x0 = line["bbox"][0]
            text = "".join(s["text"] for s in spans)[:100]
            print(f"  L{li}: x0={x0:.1f} font={font:<20s} {text}")

doc.close()
