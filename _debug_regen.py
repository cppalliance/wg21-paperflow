# Copyright (c) 2026 Sergio DuBois -- temporary debug script, delete after use
import sys, os, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "packages", "tomd", "src"))
logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")

from pathlib import Path
from tomd.lib.pdf.pipeline import convert_pdf

md, _, _ = convert_pdf(Path("data/paperstore/p4003r1.pdf"), ml_tables=True)
Path("data/paperstore/p4003r1.md").write_text(md, encoding="utf-8")
print(f"Wrote {len(md)} chars")
