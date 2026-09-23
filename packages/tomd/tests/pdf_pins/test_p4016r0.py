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

# Family pins for P4016R0 (#369): §7 Property comparison (tomd page 27,
# printed 28, Pass 1 with the wrapped `canonical_reduce` header tail
# merged), D.3 Sequential vs. Parallel (page 34, printed 35) and N.6
# Partition Strategy (page 51, printed 52). The last two are bordered
# grids whose uneven rows fail Pass 3's asymmetry gate; Pass 3 completes
# its run with the rows the find_tables() grid still holds
# (_grid_rows_left_behind). Pass 3 sections carry no table_source.
# N.14 Summary (page 54, printed 55) is a Property | Guarantee grid whose
# "Determinism" row arrives as a col-0 label block plus a separate
# multi-line cell block (Pass 1 branch 4d, _try_split_row) and whose
# "Practicality" cell wraps onto a line that starts slightly above the
# row bottom (_is_trailing_continuation tolerates the negative y gap).
_P4016R0_TABLE_PINS = {
    (27, 7, 5, "clean_matrix", "horizontal_rows"),
    (30, 3, 3, "clean_matrix", None),
    (34, 5, 3, "clean_matrix", None),
    (38, 5, 4, "prose_table", "horizontal_rows"),
    (44, 9, 5, "prose_table", None),
    (51, 5, 4, "clean_matrix", None),
    (54, 5, 2, "key_value", "horizontal_rows"),
}

def test_p4016r0_table_family_pins():
    """Focused guard for the P4016R0 tables on tomd pages 27, 30, 34, 38,
    44, 51 and 54. Independent of the full golden so a re-bless can never
    silently hand D.3 or N.6 back to Pass 3 with their header or last row
    missing, let N.14 explode into headings again, lose B.1 (drawn grid
    under a find_tables() phantom, 39pt tall), leave K.1 at Pass 1's two
    rows with the other seven leaking as prose, or let F.1 fall to Pass 2
    as a two-row column-aligned table (its shape only is pinned here;
    the Rationale cell contents are the golden's job).
    """
    pdf_path = _GOLDEN / "p4016r0.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")
    sections = run_pipeline(pdf_path).sections
    got = {
        (s.page_num, len(s.columns), len(s.columns[0]),
         s.table_kind, s.table_source)
        for s in sections
        if s.kind == SectionKind.TABLE
        and s.page_num in (27, 30, 34, 38, 44, 51, 54)
    }
    assert got == _P4016R0_TABLE_PINS
