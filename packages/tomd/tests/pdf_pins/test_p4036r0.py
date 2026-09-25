# Copyright (c) 2026 C++ Alliance, Inc. (https://cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Family pins for the P4036R0 capability page."""

from pathlib import Path

import pytest

from tomd.lib.pdf import run_pipeline
from tomd.lib.pdf.types import SectionKind

_GOLDEN = Path(__file__).resolve().parent.parent / "fixtures" / "golden"

# Page 5 of P4036R0 only. Four capability labels stay on their own rows.
_P4036R0_TABLE_PINS = {
    (0, 5, 3, "clean_matrix", "horizontal_rows"),
}


def test_p4036r0_table_family_pins():
    """The Boost.Asio capability table stays 5x3 with one label per row."""
    pdf_path = _GOLDEN / "p4036r0.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")
    sections = run_pipeline(pdf_path).sections
    tables = [s for s in sections if s.kind == SectionKind.TABLE]
    got = {
        (s.page_num, len(s.columns), len(s.columns[0]),
         s.table_kind, s.table_source)
        for s in tables
    }
    assert got == _P4036R0_TABLE_PINS
