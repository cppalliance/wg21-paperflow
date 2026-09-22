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

# Family pins for P0957R8: the §5.4.2.1 Name/Value comparison (p.27
# printed, tomd page 26, side-by-side pre-scanner) and the 2-column
# monospace type-trait table on the next page (tomd page 27, Pass 1).
# The latter regressed to a cpp fence when a 2-column monospace guard
# in _try_orphan_lookahead rejected its wrapped cell tail; the pin keeps
# it a table with the tail merged back into its cell (2 rows).
_P0957R8_TABLE_PINS = {
    (26, 16, 2, "code_comparison", "side_by_side_prepass"),
    (27, 2, 2, "clean_matrix", "horizontal_rows"),
}

def test_p0957r8_table_family_pins():
    """Focused guard for the two P0957R8 tables on tomd pages 26 and 27.
    Independent of the full golden so a re-bless can never silently drop
    the type-trait table back into a code fence.
    """
    pdf_path = _GOLDEN / "sources" / "p0957r8.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")
    sections = run_pipeline(pdf_path).sections
    got = {
        (s.page_num, len(s.columns), len(s.columns[0]),
         s.table_kind, s.table_source)
        for s in sections
        if s.kind == SectionKind.TABLE and s.page_num in (26, 27)
    }
    assert got == _P0957R8_TABLE_PINS
