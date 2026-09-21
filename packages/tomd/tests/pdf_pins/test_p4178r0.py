# Copyright (c) 2026 C++ Alliance, Inc. (https://cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Family pins for P4178R0. One module per paper.

A new golden adds a module here and a stem file. It does not edit test_pdf_golden.py.
"""

import re
from pathlib import Path

import pytest

from tomd.lib.pdf import run_pipeline
from tomd.lib.pdf.types import SectionKind

_GOLDEN = Path(__file__).resolve().parent.parent / "fixtures" / "golden"

# Family pins for P4178R0 (#427): every TABLE section from
# sources/p4178r0.pdf, document order. A tuple, not a set: page 4
# repeats (4, 2, 2, "prose_table", "side_by_side_prepass") three times.
# T0 Pattern/Description and T1 conclusion/sole evidence stay Pass 1;
# the other 17 are citation-comparison boxes (pre-scanner).
_P4178R0_TABLE_PINS = (
    (1, 5, 2, "clean_matrix", "horizontal_rows"),
    (2, 4, 2, "key_value", "side_by_side_prepass"),
    (2, 4, 2, "key_value", "side_by_side_prepass"),
    (2, 4, 2, "clean_matrix", "side_by_side_prepass"),
    (3, 4, 2, "key_value", "side_by_side_prepass"),
    (3, 2, 2, "clean_matrix", "side_by_side_prepass"),
    (3, 2, 2, "key_value", "side_by_side_prepass"),
    (3, 2, 2, "prose_table", "side_by_side_prepass"),
    (4, 2, 2, "clean_matrix", "horizontal_rows"),
    (4, 2, 2, "clean_matrix", "side_by_side_prepass"),
    (4, 2, 2, "prose_table", "side_by_side_prepass"),
    (4, 2, 2, "prose_table", "side_by_side_prepass"),
    (4, 2, 2, "prose_table", "side_by_side_prepass"),
    (5, 2, 2, "prose_table", "side_by_side_prepass"),
    (5, 2, 2, "prose_table", "side_by_side_prepass"),
    (5, 2, 2, "clean_matrix", "side_by_side_prepass"),
    (5, 2, 2, "clean_matrix", "side_by_side_prepass"),
    (6, 2, 2, "key_value", "side_by_side_prepass"),
    (6, 2, 2, "clean_matrix", "side_by_side_prepass"),
)

_CITATION_SECTION_CELL = re.compile(r"P\d+R\d+\s+Section")


def test_p4178r0_table_family_pins():
    """#427 focused guard: all 19 tables stay with the intended family.

    Independent of a byte-exact golden so a re-bless can never silently
    hand a citation box back to headings, steal T0/T1 from Pass 1, or
    collapse the three identical page-4 2x2 prepass tuples.
    """
    pdf_path = _GOLDEN / "sources" / "p4178r0.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")
    sections = run_pipeline(pdf_path).sections
    tables = [s for s in sections if s.kind == SectionKind.TABLE]
    assert len(tables) == 19
    got = [
        (s.page_num, len(s.columns), len(s.columns[0]),
         s.table_kind, s.table_source)
        for s in tables
    ]
    assert got == list(_P4178R0_TABLE_PINS)

    def header(sec):
        return [" ".join("".join(sp.text for sp in c).split())
                for c in sec.columns[0]]

    t0 = tables[0]
    assert header(t0) == ["Pattern", "Description"]
    assert t0.table_source == "horizontal_rows"

    t1 = next(s for s in tables
              if "conclusion" in header(s)[0]
              and "sole evidence" in header(s)[1])
    assert t1.table_source == "horizontal_rows"

    others = [s for s in tables if s is not t0 and s is not t1]
    assert len(others) == 17
    assert all(s.table_source == "side_by_side_prepass" for s in others)

    yba = [s for s in tables
           if len(s.columns) == 4 and len(s.columns[0]) == 2]
    assert len(yba) == 4
    for s in yba:
        hdr = header(s)
        assert hdr[0] == ""
        assert _CITATION_SECTION_CELL.search(hdr[1]), hdr

    for s in tables:
        if (len(s.columns) == 2 and len(s.columns[0]) == 2
                and s.table_source == "side_by_side_prepass"):
            hdr = header(s)
            assert any(_CITATION_SECTION_CELL.search(c) for c in hdr), hdr

    assert header(tables[-1]) == [
        "P2300R10 Section 4.8", "P2300R10 Section 4.7"]
