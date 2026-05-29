"""Trace the full pipeline for p2034r6 to find where code_blocks gets lost."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "packages/tomd/src")
from tomd.lib.pdf.pipeline import convert_pdf
from tomd.lib.pdf.emit import emit_markdown, _render_section_md
from tomd.lib.pdf.types import SectionKind
from pathlib import Path
import fitz

pdf = Path("data/paperstore/p2034r6.pdf")
doc = fitz.open(str(pdf))

# Run pipeline up to sections
from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf.table import detect_tables

blocks = []
for i in range(len(doc)):
    blocks.extend(extract_mupdf(doc[i], i))
doc.close()

table_secs, remaining = detect_tables(blocks)
print(f"detect_tables returned {len(table_secs)} table sections")
for ts in table_secs:
    if ts.table_kind == "code_comparison":
        print(f"  CODE_COMPARISON: page={ts.page_num}, strategy={ts.table_strategy}")
        rendered = _render_section_md(ts)
        print(f"  Rendered starts with: {repr(rendered[:80])}")
        print()

# Now run the actual full pipeline convert_pdf to see what it produces
from tomd.lib.pdf import pipeline as _pl
import inspect
print("\nChecking convert_pdf pipeline...")
src = inspect.getsource(_pl.convert_pdf)
# Check if there's table handling in between
print(f"  'detect_tables' mentioned: {'detect_tables' in src}")
print(f"  'table_strategy' mentioned: {'table_strategy' in src}")
print(f"  'table_kind' mentioned: {'table_kind' in src}")
