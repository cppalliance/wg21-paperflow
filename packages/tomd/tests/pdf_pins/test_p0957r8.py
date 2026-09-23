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

# Family pins for P0957R8: the §5.4.2.1 Name/Value comparison (printed
# p.27-28, tomd page 26). The two rows that start the next page join
# this table when both fragments sit on the same ruled grid, so page 27
# has no table of its own.
_P0957R8_TABLE_PINS = {
    (26, 18, 2, "code_comparison", "side_by_side_prepass"),
}

def test_p0957r8_table_family_pins():
    """Focused guard for the P0957R8 Name/Value table on tomd page 26.
    The printed-page-28 continuation is part of that table. A re-bless
    must not put those two rows back into their own table on page 27
    or drop the type-trait rows into a code fence.
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
