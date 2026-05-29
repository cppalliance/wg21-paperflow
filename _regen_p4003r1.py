"""Regenerate P4003R1 markdown and write to the correct paperstore path."""
import sys, logging
from pathlib import Path
sys.path.insert(0, str(Path("packages/tomd/src")))
sys.path.insert(0, str(Path("packages/paperstore/src")))
sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format="%(name)s: %(message)s")

from tomd.lib.pdf import convert_pdf
from paperstore import SqliteBackend

backend = SqliteBackend(Path("data/paperstore"))
pid = "p4003r1"
pdf_path = Path("data/paperstore/p4003r1.pdf")
print(f"PDF: {pdf_path}")
md, _warnings = convert_pdf(pdf_path)
out = backend.get_paper_md_path(pid)
out.write_text(md, encoding="utf-8")
print(f"Wrote {len(md)} chars to {out}")
