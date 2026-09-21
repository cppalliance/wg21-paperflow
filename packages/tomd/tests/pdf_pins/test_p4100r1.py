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

# Family pins for P4100R1: the p.3 (printed 4) Capy/Corosio table, a
# header-grid seed like P4047R0's (`Library | Role | Status` on one
# baseline over a shattered two-row body; before, a `####` heading plus
# prose), and the p.10 (printed 11) protocol table that Pass 3 completes
# from the find_tables() grid (no table_source), locked since #380. The
# test filters by page, so the other tables of those pages are pinned as
# they are today: p.3 the second `Library | Role | Status` table (5x3)
# and the `Library | Author | Status` table (4x3), both Pass 1; p.10 the
# Stage Two `# | Paper | Abstraction` table (8x3, Pass 3).
_P4100R1_TABLE_PINS = {
    (3, 3, 3, "clean_matrix", "side_by_side_prepass"),
    (3, 5, 3, "clean_matrix", "horizontal_rows"),
    (3, 4, 3, "prose_table", "horizontal_rows"),
    (10, 7, 3, "clean_matrix", None),
    (10, 8, 3, "clean_matrix", None),
}


def _header_cells(section) -> list[str]:
    """Header row cell texts, runs of whitespace collapsed."""
    return [" ".join("".join(sp.text for sp in cell).split())
            for cell in section.columns[0]]


def test_p4100r1_table_family_pins():
    """Focused guard for the P4100R1 tables on tomd pages 3 and 10: the
    Capy/Corosio table stays a 3x3 pre-scanner table with its header
    row, and the protocol table stays at Pass 3's seven rows.
    """
    pdf_path = _GOLDEN / "p4100r1.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")
    sections = run_pipeline(pdf_path).sections
    tables = [s for s in sections
              if s.kind == SectionKind.TABLE and s.page_num in (3, 10)]
    got = {
        (s.page_num, len(s.columns), len(s.columns[0]),
         s.table_kind, s.table_source)
        for s in tables
    }
    assert got == _P4100R1_TABLE_PINS
    capy = [s for s in tables if s.table_source == "side_by_side_prepass"]
    assert len(capy) == 1
    assert _header_cells(capy[0]) == ["Library", "Role", "Status"]
