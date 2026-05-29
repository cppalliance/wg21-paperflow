"""Trace exact Pass 2 execution for Tony Table."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "packages/tomd/src")
from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf.table import _block_column_positions, _columns_match
from pathlib import Path
import fitz

pdf = Path("data/paperstore/p2034r6.pdf")
doc = fitz.open(str(pdf))
blocks = extract_mupdf(doc[4], 4)
doc.close()

# Show _block_column_positions for each relevant block
print("Block column positions for page 4:\n")
for idx, b in enumerate(blocks):
    cols = _block_column_positions(b)
    text = "".join(sp.text for ln in b.lines for sp in ln.spans)[:40]
    if b.bbox[1] > 350:  # Tony Table area
        print(f"  [{idx}] x={b.bbox[0]:.0f},y={b.bbox[1]:.0f} "
              f"lines={len(b.lines)} cols={cols} text={repr(text)}")

# Now simulate the table_blocks assembly
print("\n\nSimulating Pass 2 table detection:\n")
# Find the first block with 2+ columns
for i, b in enumerate(blocks):
    cols = _block_column_positions(b)
    if cols and len(cols) >= 2 and b.bbox[1] > 350:
        print(f"Seed block [{i}]: cols={cols}")
        ref_cols = cols
        table_blocks = [b]
        j = i + 1
        while j < len(blocks):
            nb = blocks[j]
            nc = _block_column_positions(nb)
            if nc is not None and _columns_match(ref_cols, nc):
                table_blocks.append(nb)
                print(f"  Added [{j}] (match): cols={nc}")
                j += 1
            else:
                # Check if it's a single-col block that could be orphan
                text = "".join(sp.text for ln in nb.lines for sp in ln.spans)[:30]
                print(f"  Stopped at [{j}]: cols={nc} text={repr(text)}")
                break
        
        print(f"\nTable blocks: {len(table_blocks)}")
        num_cols = len(ref_cols)
        print(f"num_cols: {num_cols}")
        
        # Now show how rows get built
        for bi, blk in enumerate(table_blocks):
            blk_cols = _block_column_positions(blk) or ref_cols
            print(f"\n  Processing block [{bi}] blk_cols={blk_cols}:")
            row = []
            for line in blk.lines[:num_cols]:
                row.append(list(line.spans))
                lt = "".join(sp.text for sp in line.spans)[:50]
                print(f"    Line→row[{len(row)-1}]: x={line.bbox[0]:.0f} {repr(lt)}")
            while len(row) < num_cols:
                row.append([])
            for line in blk.lines[num_cols:]:
                line_x = line.bbox[0]
                best_col = min(
                    range(num_cols),
                    key=lambda ci: abs(line_x - blk_cols[ci]),
                )
                lt = "".join(sp.text for sp in line.spans)[:50]
                print(f"    Line→merge row[{best_col}]: x={line_x:.0f} {repr(lt)}")
        break
