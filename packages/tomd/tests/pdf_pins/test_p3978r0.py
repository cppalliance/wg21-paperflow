# Copyright (c) 2026 C++ Alliance, Inc. (https://cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Family pins for one PDF golden.

One module per paper. A new golden adds a module here and a stem file.
It does not edit test_pdf_golden.py.
"""

from pathlib import Path

import pytest

from tomd.lib.pdf import run_pipeline
from tomd.lib.pdf.types import SectionKind

_GOLDEN = Path(__file__).resolve().parent.parent / "fixtures" / "golden"

# Family pins for P3978R0 (#422): three identical empty poll grids on tomd
# page 1 (Pass 3, header-only, synthesized empty body row; Pass 3 sections
# carry no table_source) and the §3.1 rewrite mapping on page 2 (Pass 1).
# A list, not a set: three tables share one shape and must all be present.
_P3978R0_TABLE_PINS = [
    (1, 2, 5, "clean_matrix", None),
    (1, 2, 5, "clean_matrix", None),
    (1, 2, 5, "clean_matrix", None),
    (2, 8, 4, "clean_matrix", "horizontal_rows"),
]

def test_p3978r0_table_family_pins():
    """#422 focused guard: each suggested poll is its own 2x5 table with
    the SF/F/N/A/SA header and an empty body row, and the page-2 rewrite
    mapping keeps its 8x4 shape. Independent of the full golden so a
    re-bless can never silently fuse the polls again.
    """
    pdf_path = _GOLDEN / "sources" / "p3978r0.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")
    sections = run_pipeline(pdf_path).sections
    tables = [s for s in sections
              if s.kind == SectionKind.TABLE and s.page_num in (1, 2)]
    got = sorted(
        (s.page_num, len(s.columns), len(s.columns[0]),
         s.table_kind, s.table_source or "")
        for s in tables
    )
    assert got == sorted(
        (p, r, c, k, src or "") for p, r, c, k, src in _P3978R0_TABLE_PINS)
    polls = [s for s in tables if s.page_num == 1]
    for s in polls:
        assert ["".join(sp.text for sp in c).strip() for c in s.columns[0]] == [
            "SF", "F", "N", "A", "SA"]
        assert all(not "".join(sp.text for sp in c).strip()
                   for c in s.columns[1])
