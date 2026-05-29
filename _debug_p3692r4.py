"""Debug: trace why P3692R4 abstract body is missing."""
import sys, os, logging
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.environ.setdefault("WG21_DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
logging.basicConfig(level=logging.DEBUG, format="%(name)s %(message)s")

from pathlib import Path
from tomd.lib.pdf.pipeline import _run_pipeline
from tomd.lib.pdf.types import SectionKind
from tomd.lib.toc import find_toc_indices, has_dot_leader

PDF = Path(__file__).parent / "data" / "paperstore" / "p3692r4.pdf"

# Monkey-patch _run_pipeline to intercept at key points.
# We'll patch find_toc_indices and the structure_sections call.
import tomd.lib.pdf.pipeline as pipe

_orig_find_toc = pipe.find_toc_indices

def _traced_find_toc(texts, heading_texts, hints=None, **kw):
    result = _orig_find_toc(texts, heading_texts, hints, **kw)
    if result:
        print(f"\n=== TOC INDICES ({len(result)} entries): {sorted(result)} ===")
        for idx in sorted(result)[:20]:
            print(f"  TOC[{idx:3d}]: {texts[idx][:80]!r}")
    else:
        print("\n=== NO TOC INDICES FOUND ===")
    return result

pipe.find_toc_indices = _traced_find_toc

# Run pipeline
result = _run_pipeline(PDF)

pipe.find_toc_indices = _orig_find_toc

print(f"\n=== FINAL SECTIONS (first 15 of {len(result.sections)}) ===")
for i, sec in enumerate(result.sections[:15]):
    tag = " **ABSTRACT**" if "abstract" in sec.text.lower()[:60] else ""
    print(f"  [{i:3d}] {sec.kind.name:12s} h={sec.heading_level} pg={sec.page_num} "
          f"fs={sec.font_size:.1f} conf={sec.confidence.name:8s} | {sec.text.split(chr(10))[0][:100]!r}{tag}")

print("\n=== ABSTRACT HEADING AND NEIGHBORS ===")
for i, sec in enumerate(result.sections):
    if sec.kind == SectionKind.HEADING and "abstract" in sec.text.lower():
        print(f"  Abstract heading at [{i}]: {sec.text!r}")
        for j in range(i+1, min(i+3, len(result.sections))):
            nxt = result.sections[j]
            tag = " **ABSTRACT**" if "abstract" in nxt.text.lower()[:60] else ""
            print(f"  [{j}] {nxt.kind.name} h={nxt.heading_level} pg={nxt.page_num} | "
                  f"{nxt.text.split(chr(10))[0][:120]!r}{tag}")
        break

print("\n=== FIRST 20 LINES OF MARKDOWN ===")
for i, line in enumerate(result.md.split("\n")[:20]):
    print(f"  {i:3d}| {line}")
