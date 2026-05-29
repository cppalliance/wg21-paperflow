"""Find WHERE in detect_tables the Tony Table gets detected."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "packages/tomd/src")
from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf import table as _tmod
from tomd.lib.pdf.types import Section, SectionKind, Span
from pathlib import Path
import fitz

# Monkey-patch Section creation to trace table detection
_orig_init = Section.__init__
_creation_log = []

def _traced_init(self, *args, **kwargs):
    _orig_init(self, *args, **kwargs)
    if self.kind == SectionKind.TABLE:
        import traceback
        stack = traceback.extract_stack()
        # Find the relevant frame in table.py
        for frame in reversed(stack):
            if "table.py" in frame.filename and frame.lineno > 100:
                _creation_log.append((frame.lineno, self.table_kind, self.page_num))
                break

Section.__init__ = _traced_init

pdf = Path("data/paperstore/p2034r6.pdf")
doc = fitz.open(str(pdf))
blocks = []
for i in range(len(doc)):
    blocks.extend(extract_mupdf(doc[i], i))
doc.close()

secs, _ = _tmod.detect_tables(blocks)

print("Table sections created:")
for lineno, kind, page in _creation_log:
    print(f"  table.py line {lineno}: kind={kind}, page={page}")
