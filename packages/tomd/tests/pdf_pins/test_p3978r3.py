# Copyright (c) 2026 C++ Alliance, Inc. (https://cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Family pins for P3978R3.

The five suggested polls on tomd page 1 stay separate 2x5 grids. The
page-2 expectations table stays 8x4. A 2-column grid whose header cell
is the document id is page furniture (#438): pages 3 and 9 emit no table,
and the document id is not a heading.
"""

from pathlib import Path

import pytest

from tomd.lib.pdf import run_pipeline
from tomd.lib.pdf.types import SectionKind

_GOLDEN = Path(__file__).resolve().parent.parent / "fixtures" / "golden"

_P3978R3_TABLE_PINS = (
    # A numbered section heading is not a packed table (4.1, 4.3).
    # A later document id in column 0 is not furniture either.
    (1, 2, 5, "clean_matrix", None),
    (1, 2, 5, "clean_matrix", None),
    (1, 2, 5, "clean_matrix", None),
    (1, 2, 5, "clean_matrix", None),
    (1, 2, 5, "clean_matrix", None),
    (2, 8, 4, "clean_matrix", "horizontal_rows"),
)


def test_p3978r3_table_family_pins():
    """Polls and the expectations table stay; running headers are not tables."""
    pdf_path = _GOLDEN / "p3978r3.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")
    result = run_pipeline(pdf_path)
    tables = [s for s in result.sections if s.kind == SectionKind.TABLE]
    got = [
        (s.page_num, len(s.columns), len(s.columns[0]),
         s.table_kind, s.table_source)
        for s in tables
    ]
    assert sorted(got) == sorted(_P3978R3_TABLE_PINS)
    assert not [s for s in tables if s.page_num in (3, 9)]
    leaked = [
        s.text for s in result.sections
        if s.kind == SectionKind.HEADING and s.text.startswith("P3978R3")
    ]
    assert leaked == []
    assert not any(s.text.startswith("4.1") or s.text.startswith("4.3")
                   for s in tables)
