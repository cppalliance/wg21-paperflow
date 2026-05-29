"""Regenerate markdowns by calling convert_pdf directly, bypassing postcondition."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "packages/tomd/src")
from pathlib import Path
from tomd.lib.pdf.pipeline import convert_pdf

data = Path("data/paperstore")

# All PDFs we want to test
ticket_pdfs = [
    "p2034r6", "p3977r0", "p4014r0", "p3688r6", "p3985r0",
    "p4006r0", "p3856r8", "p3978r3", "p3844r4", "p0876r22",
    "p3596r1", "p4016r0",
]

for paper in ticket_pdfs:
    pdf = data / f"{paper}.pdf"
    if not pdf.exists():
        print(f"  {paper}: PDF NOT FOUND, skipping")
        continue
    try:
        md, prompts = convert_pdf(pdf)
        out = data / f"{paper}.md"
        out.write_text(md, encoding="utf-8")
        print(f"  {paper}: OK ({len(md)} chars)")
    except Exception as e:
        print(f"  {paper}: ERROR - {e}")

print("\nDone.")
