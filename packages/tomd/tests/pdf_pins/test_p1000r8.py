# Copyright (c) 2026 C++ Alliance, Inc. (https://cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Family pins for the P1000R8 IS schedule page."""

from pathlib import Path

import pytest

from tomd.lib.pdf import run_pipeline
from tomd.lib.pdf.types import SectionKind

_GOLDEN = Path(__file__).resolve().parent.parent / "fixtures" / "golden"

# Page 1 of P1000R8 only. The IS schedule is 9 rows by 2 columns.
_P1000R8_TABLE_PINS = {
    (0, 9, 2, "key_value", None),
}


def test_p1000r8_table_family_pins():
    """The IS schedule stays 9x2. 2027.1 and 2027.2 stay empty continuation cells."""
    pdf_path = _GOLDEN / "p1000r8.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")
    sections = run_pipeline(pdf_path).sections
    tables = [s for s in sections if s.kind == SectionKind.TABLE]
    got = {
        (s.page_num, len(s.columns), len(s.columns[0]),
         s.table_kind, s.table_source)
        for s in tables
    }
    assert got == _P1000R8_TABLE_PINS
