"""Trace the full convert_pdf pipeline to see table strategies at emit time."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "packages/tomd/src")

# Monkey-patch _render_section_md to log TABLE sections
from tomd.lib.pdf import emit as _emit_mod
from tomd.lib.pdf.types import SectionKind

_orig = _emit_mod._render_section_md

def _patched(sec):
    if sec.kind == SectionKind.TABLE:
        first_text = ""
        if sec.columns and sec.columns[0]:
            first_text = "".join(s.text for s in sec.columns[0][0]).strip()[:50]
        print(f"[RENDER TABLE] page={sec.page_num} kind={sec.table_kind} "
              f"strategy={sec.table_strategy} first_cell=\"{first_text}\"")
        result = _orig(sec)
        print(f"  -> starts with: {repr(result[:60])}")
    return _orig(sec)

_emit_mod._render_section_md = _patched

# Now run convert_pdf
from tomd.lib.pdf.pipeline import convert_pdf
from pathlib import Path

pdf = Path("data/paperstore/p2034r6.pdf")
md, _, _ = convert_pdf(pdf)
