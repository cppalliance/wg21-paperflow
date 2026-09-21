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

# #380 family pins for P4096R0: (page_num, rows incl. header, cols,
# table_kind, table_source) for the four tables of §5.1, §5.2 (x2), §5.4.
_P4096R0_TABLE_PINS = {
    (9, 5, 4, "prose_table", "side_by_side_prepass"),
    (10, 4, 3, "prose_table", "horizontal_rows"),
    (10, 4, 3, "clean_matrix", "horizontal_rows"),
    (11, 5, 4, "clean_matrix", "side_by_side_prepass"),
}

def test_p4096r0_table_family_pins():
    """#380 focused guard: each of the four shattered tables is routed to
    the intended family with the intended shape. Independent of the full
    golden so a re-bless can never silently move a table to another pass.
    """
    pdf_path = _GOLDEN / "p4096r0.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")
    sections = run_pipeline(pdf_path).sections
    got = {
        (s.page_num, len(s.columns), len(s.columns[0]),
         s.table_kind, s.table_source)
        for s in sections
        if s.kind == SectionKind.TABLE and s.page_num in (9, 10, 11)
    }
    assert got == _P4096R0_TABLE_PINS
