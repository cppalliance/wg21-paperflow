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

# Tables II-V on the genuine two-column pages (tomd pages 3 and 4).
# Each is one same-baseline header block plus one body block of many
# rows. Pass 1 unpacks that body. Page 4's right-column table stays
# after the left column.
_P0533R9_TABLE_PINS = {
    (3, 8, 3, "clean_matrix", "multirow_body"),
    (3, 3, 2, "clean_matrix", "multirow_body"),
    (4, 21, 3, "clean_matrix", "multirow_body"),
    (4, 13, 3, "clean_matrix", "multirow_body"),
}


def _row_text(row: list) -> list[str]:
    return ["".join(sp.text for sp in cell).strip() for cell in row]


def test_p0533r9_table_family_pins():
    """Tables II-V keep their rows, headers, and column assignment.

    A re-bless must not flatten them back into prose, move Yes into the
    function cell, or swap the page-4 columns.
    """
    pdf_path = _GOLDEN / "sources" / "p0533r9.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")
    sections = run_pipeline(pdf_path).sections
    tables = [
        s for s in sections
        if s.kind == SectionKind.TABLE and s.page_num in (3, 4)
    ]
    got = {
        (s.page_num, len(s.columns), len(s.columns[0]),
         s.table_kind, s.table_source)
        for s in tables
    }
    assert got == _P0533R9_TABLE_PINS
    by_shape = {
        (s.page_num, len(s.columns), len(s.columns[0])): s for s in tables
    }
    frexp = by_shape[(3, 8, 3)]
    assert _row_text(frexp.columns[0]) == ["Function", "Pass", "Comment"]
    assert _row_text(frexp.columns[1]) == [
        "float frexp(float value, int* exp)", "Yes", "w"]
    modf = _row_text(frexp.columns[5])
    assert modf[0] == "float modf(float value, float* iptr)"
    assert modf[1] == "Yes"
    assert "Yes" not in modf[0]
    abs_table = by_shape[(3, 3, 2)]
    assert _row_text(abs_table.columns[0]) == ["Function", "Pass"]
    assert _row_text(abs_table.columns[1])[0] == "int abs(int j)"
    ceil = by_shape[(4, 21, 3)]
    assert _row_text(ceil.columns[1])[0] == "float ceil(float x)"
    assert _row_text(ceil.columns[-1])[0] == "float fma(float x, float y, float z)"
    classify = by_shape[(4, 13, 3)]
    assert _row_text(classify.columns[1])[0] == "int fpclassify(float x);"
    assert _row_text(classify.columns[-1])[0] == "int isunordered(float x, float y)"
    for section in sections:
        if section.kind != SectionKind.TABLE or not section.columns:
            continue
        assert "Revision History" not in _row_text(section.columns[0])[0]
    order = []
    for section in sections:
        if section.page_num != 4:
            continue
        if (section.kind == SectionKind.TABLE
                and section.table_source == "multirow_body"):
            order.append(_row_text(section.columns[1])[0])
            continue
        head = " ".join(section.text.split())
        if (head.startswith("TABLE IV") or head.startswith("TABLE V")
                or head.startswith("VIII.")):
            order.append(head)
    assert order[0].startswith("float ceil")
    assert order[1].startswith("TABLE IV")
    assert order[2].startswith("int fpclassify")
    assert order[3].startswith("TABLE V")
    assert "PROPOSED WORDING" in order[4]
