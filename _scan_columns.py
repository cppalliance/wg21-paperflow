"""Scan all PDFs in data/paperstore/ for two-column layouts on page 0."""
import fitz
import os
import sys
from pathlib import Path

STORE = Path("data/paperstore")

def analyze_pdf(pdf_path):
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        return None, str(e)
    if len(doc) == 0:
        doc.close()
        return None, "empty PDF"
    page = doc[0]
    width = page.rect.width
    mid = width / 2
    blocks = page.get_text("blocks")
    doc.close()

    left, right, span = [], [], []
    for b in blocks:
        x0, y0, x1, y1, text, block_no, block_type = b[0], b[1], b[2], b[3], b[4], b[5], b[6]
        if block_type != 0:
            continue
        if x1 < mid + 20 and x0 < mid:
            left.append((x0, y0, x1, y1, text.strip()[:60]))
        elif x0 > mid - 20:
            right.append((x0, y0, x1, y1, text.strip()[:60]))
        else:
            span.append((x0, y0, x1, y1, text.strip()[:60]))

    is_twocol = len(left) >= 3 and len(right) >= 3
    return {
        "left": left,
        "right": right,
        "span": span,
        "is_twocol": is_twocol,
        "width": width,
        "mid": mid,
    }, None


def main():
    pdfs = sorted(STORE.glob("*.pdf"))
    print(f"Scanning {len(pdfs)} PDFs in {STORE}/\n")

    twocol_results = []
    errors = []

    for pdf_path in pdfs:
        pid = pdf_path.stem
        result, err = analyze_pdf(pdf_path)
        if err:
            errors.append((pid, err))
            continue
        if result["is_twocol"]:
            twocol_results.append((pid, result))

    print("=" * 70)
    print(f"TOTAL PDFs scanned: {len(pdfs)}")
    print(f"Two-column detected: {len(twocol_results)}")
    if errors:
        print(f"Errors: {len(errors)}")
        for pid, err in errors:
            print(f"  {pid}: {err}")
    print("=" * 70)

    if not twocol_results:
        print("\nNo two-column PDFs found.")
        return

    print(f"\n{'PID':<20} {'Left':>5} {'Right':>5} {'Span':>5}  Right-before-Left?")
    print("-" * 65)

    affected = []
    for pid, r in twocol_results:
        nl, nr, ns = len(r["left"]), len(r["right"]), len(r["span"])
        min_left_y = min(b[1] for b in r["left"]) if r["left"] else 9999
        min_right_y = min(b[1] for b in r["right"]) if r["right"] else 9999
        right_before = min_right_y < min_left_y
        flag = "YES  <-- affected" if right_before else "no"
        print(f"{pid:<20} {nl:>5} {nr:>5} {ns:>5}  {flag}")
        if right_before:
            affected.append((pid, r, min_left_y, min_right_y))

    print(f"\n{'=' * 70}")
    print(f"AFFECTED by sort fix: {len(affected)} / {len(twocol_results)} two-column PDFs")
    print("=" * 70)

    for pid, r, min_left_y, min_right_y in affected:
        print(f"\n--- {pid} ---")
        print(f"  Page width: {r['width']:.1f}, midpoint: {r['mid']:.1f}")
        print(f"  First LEFT  block y={min_left_y:.1f}")
        print(f"  First RIGHT block y={min_right_y:.1f}")
        print(f"  Delta: right starts {min_left_y - min_right_y:.1f}pt above left")
        right_early = [b for b in r["right"] if b[1] < min_left_y]
        print(f"  Right blocks before first left block ({len(right_early)}):")
        for b in right_early:
            safe = b[4].encode("ascii", errors="replace").decode("ascii")
            print(f"    y={b[1]:.1f} x=[{b[0]:.1f}-{b[2]:.1f}] \"{safe}\"")


if __name__ == "__main__":
    main()
