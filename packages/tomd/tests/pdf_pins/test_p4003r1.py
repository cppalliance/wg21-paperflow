# Copyright (c) 2026 C++ Alliance, Inc. (https://cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Family pins for the P4003R1 Prediction Registry pages."""

from pathlib import Path

import pytest

from tomd.lib.pdf import run_pipeline
from tomd.lib.pdf.types import SectionKind

_GOLDEN = Path(__file__).resolve().parent.parent / "fixtures" / "golden"

# PDF pages 49-50 only. The registry is a 5x4 then a 3x4 continuation.
# The 2x5 table on the second page is the other table on that page.
_P4003R1_TABLE_PINS = {
    (0, 5, 4, "clean_matrix", "side_by_side_prepass"),
    (1, 3, 4, "clean_matrix", "side_by_side_prepass"),
    (1, 2, 5, "clean_matrix", "horizontal_rows"),
}


def test_p4003r1_table_family_pins():
    """The Prediction Registry stays two side-by-side tables, not one merged row."""
    pdf_path = _GOLDEN / "p4003r1.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")
    sections = run_pipeline(pdf_path).sections
    tables = [s for s in sections if s.kind == SectionKind.TABLE]
    got = {
        (s.page_num, len(s.columns), len(s.columns[0]),
         s.table_kind, s.table_source)
        for s in tables
    }
    assert got == _P4003R1_TABLE_PINS
