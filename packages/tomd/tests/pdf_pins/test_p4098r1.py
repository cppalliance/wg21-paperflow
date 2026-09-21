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

# Family pins for P4098R1 (#414): one Claim | Source | Year | Evidence
# table per page, rows incl. header. §2.1 to §2.5 (pages 2 to 6) have 4+
# data rows and go to the side-by-side pre-scanner; §2.6 (page 7) has 3
# data rows, below _ATOMIZED_PREPASS_MIN_ROWS_DENSE, and is claimed by
# Pass 2 (same detector, regular side-by-side) after Pass 1 rejects the
# page. Pinned so a re-bless can never hand pages 4 and 5 back to Pass 1
# (one row per wrapped line) or cut the tables to three columns again.
_P4098R1_TABLE_PINS = {
    (2, 7, 4, "prose_table", "side_by_side_prepass"),
    (3, 5, 4, "prose_table", "side_by_side_prepass"),
    (4, 5, 4, "prose_table", "side_by_side_prepass"),
    (5, 5, 4, "prose_table", "side_by_side_prepass"),
    (6, 6, 4, "prose_table", "side_by_side_prepass"),
    (7, 4, 4, "prose_table", "side_by_side"),
}

def test_p4098r1_table_family_pins():
    """#414 focused guard: the six Claim | Source | Year | Evidence tables
    keep four columns and one row per claim, and stay with the side-by-side
    detector (pre-scanner on pages 2 to 6, Pass 2 on page 7). The Year
    cell of every data row is a bare year, which is what the header-grid
    adoption buys: without it Year and Evidence share one cell.
    """
    pdf_path = _GOLDEN / "p4098r1.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")
    sections = run_pipeline(pdf_path).sections
    tables = [s for s in sections
              if s.kind == SectionKind.TABLE and s.page_num in range(2, 8)]
    got = {
        (s.page_num, len(s.columns), len(s.columns[0]),
         s.table_kind, s.table_source)
        for s in tables
    }
    assert got == _P4098R1_TABLE_PINS
    for s in tables:
        assert ["".join(sp.text for sp in c).strip() for c in s.columns[0]] == [
            "Claim", "Source", "Year", "Evidence"]
        for row in s.columns[1:]:
            year = "".join(sp.text for sp in row[2]).strip()
            assert year.isdigit() and len(year) == 4, (s.page_num, year)
