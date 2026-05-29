"""Debug script: inspect MuPDF blocks around Table 3 in P4003R1.

Prints all blocks from pages 52-58 with spatial info, then runs
_detect_spec_tables_by_label to show what it produces.
"""
import sys
import os
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "packages", "tomd", "src"))

import fitz  # pymupdf

PDF_PATH = os.path.join(
    os.path.dirname(__file__),
    "data", "paperstore", "p4003r1.pdf",
)

PAGES = range(0, 0)  # skip page dump

SPEC_TABLE_LABEL_RE = re.compile(
    r"^Table\s+(\d+)\s*[-\u2014\u2013]\s*", re.IGNORECASE
)


def main():
    doc = fitz.open(PDF_PATH)
    try:
        print(f"=== P4003R1: {doc.page_count} pages ===\n")

        for page_idx in PAGES:
            if page_idx >= doc.page_count:
                break
            page = doc[page_idx]
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

            print(f"\n{'='*80}")
            print(f"PAGE {page_idx} (PDF page {page_idx + 1})")
            print(f"{'='*80}")

            for bi, block in enumerate(blocks):
                if block["type"] != 0:  # skip image blocks
                    continue
                bbox = block["bbox"]
                lines = block.get("lines", [])
                all_text = ""
                first_font = ""
                first_size = 0.0
                first_bold = False

                for li, line in enumerate(lines):
                    spans = line.get("spans", [])
                    for si, span in enumerate(spans):
                        all_text += span["text"]
                        if li == 0 and si == 0:
                            first_font = span.get("font", "")
                            first_size = span.get("size", 0.0)
                            flags = span.get("flags", 0)
                            first_bold = bool(flags & (1 << 4))
                    if li < len(lines) - 1:
                        all_text += "\n"

                short_text = all_text.strip()[:120].replace("\n", "\\n")
                width = bbox[2] - bbox[0]

                # Identify special blocks
                markers = []
                if SPEC_TABLE_LABEL_RE.match(all_text.strip()):
                    markers.append("<<< TABLE LABEL >>>")
                if re.match(r"^\d+\.\d+", all_text.strip()) and first_size >= 10.0:
                    markers.append("<<< HEADING? >>>")
                if re.match(r"^\d+\s*\[", all_text.strip()):
                    markers.append("<<< NUMBERED NOTE >>>")
                if all_text.strip().lower() in ("expression", "return type",
                                                 "assertion/note pre/post-conditions"):
                    markers.append("<<< COLUMN HEADER >>>")

                marker_str = " ".join(markers)
                print(f"  [{bi:2d}] bbox=({bbox[0]:6.1f},{bbox[1]:6.1f},{bbox[2]:6.1f},{bbox[3]:6.1f}) "
                      f"w={width:5.1f} size={first_size:4.1f} bold={first_bold} "
                      f"lines={len(lines)}")
                print(f"       text: {short_text}")
                if marker_str:
                    print(f"       {marker_str}")

        # Now run the actual detection
        print(f"\n\n{'='*80}")
        print("RUNNING _detect_spec_tables_by_label ON FULL EXTRACTION")
        print(f"{'='*80}\n")

        from tomd.lib.pdf.extract import extract_mupdf
        from tomd.lib.pdf.table import _detect_spec_tables_by_label
        import logging
        logging.basicConfig(level=logging.DEBUG,
                            format="%(name)s %(levelname)s %(message)s")

        all_blocks = []
        for page_idx in range(doc.page_count):
            page = doc[page_idx]
            page_blocks = extract_mupdf(page, page_idx)
            all_blocks.extend(page_blocks)

        # Find all label blocks in extract_mupdf output
        print("\n--- Label blocks found in extract_mupdf output ---")
        for i, blk in enumerate(all_blocks):
            m = SPEC_TABLE_LABEL_RE.match(blk.text.strip())
            if m:
                print(f"  [{i}] page={blk.page_num} y={blk.bbox[1]:.1f} "
                      f"text='{blk.text.strip()[:80]}'")

        from tomd.lib.pdf.table import detect_tables
        page_mupdf_tables: dict = {}
        two_column_pages: set = set()
        table_sections, remaining = detect_tables(
            all_blocks,
            page_mupdf_tables=page_mupdf_tables,
            two_column_pages=two_column_pages,
        )

        print(f"\nDetected {len(table_sections)} total table sections")
        for ti, sec in enumerate(table_sections):
            rows = sec.columns or []
            cont = getattr(sec, "table_continuation", False)
            r0 = ""
            if rows:
                r0 = "".join(s.text for s in rows[0][0]).strip()[:50]
            print(f"  T{ti}: page={sec.page_num}, rows={len(rows)}, "
                  f"cont={cont}, source={sec.table_source}, "
                  f"strategy={sec.table_strategy}, "
                  f"r0='{r0}'")
        print()

        for ti, sec in enumerate(spec_tables):
            cols = sec.columns or []
            print(f"\n--- Spec Table {ti + 1}: page={sec.page_num}, "
                  f"rows={len(cols)}, kind={sec.table_kind}, "
                  f"source={sec.table_source} ---")

            for ri, row in enumerate(cols):
                row_texts = []
                for ci, cell in enumerate(row):
                    cell_text = "".join(s.text for s in cell).strip()
                    cell_text = cell_text[:60].replace("\n", "\\n")
                    row_texts.append(f"c{ci}='{cell_text}'")
                label = "HDR" if ri == 0 else f"R{ri:2d}"
                print(f"  [{label}] {' | '.join(row_texts)}")

            if cols:
                last_row = cols[-1]
                last_text = "".join(s.text for s in last_row[0]).strip()
                if any(kw in last_text.lower() for kw in
                       ["class ", "note", "[ note", "end note"]):
                    print(f"  *** OVERRUN WARNING: last row col-0 = '{last_text[:80]}'")

    finally:
        doc.close()


if __name__ == "__main__":
    main()
