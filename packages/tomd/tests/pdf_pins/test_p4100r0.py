# Copyright (c) 2026 C++ Alliance, Inc. (https://cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Family pins for P4100R0 section 7.

tomd page 8 carries the Property table and the stage-one protocol table.
The protocol header is `# | Paper | Abstraction` (#438); the numbered
row is a body row. Page 9 stage two was already that header.
"""

from pathlib import Path

import pytest

from tomd.lib.pdf import run_pipeline
from tomd.lib.pdf.types import SectionKind

_GOLDEN = Path(__file__).resolve().parent.parent / "fixtures" / "golden"

_P4100R0_TABLE_PINS = (
    (8, 6, 4, "clean_matrix", "horizontal_rows"),
    (8, 7, 3, "clean_matrix", None),
    (9, 8, 3, "clean_matrix", None),
)


def _header_cells(section) -> list[str]:
    """Header row cell texts, runs of whitespace collapsed."""
    return [" ".join("".join(sp.text for sp in cell).split())
            for cell in section.columns[0]]


def test_p4100r0_table_family_pins():
    """Stage one keeps the protocol header above the numbered body row."""
    pdf_path = _GOLDEN / "p4100r0.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")
    sections = run_pipeline(pdf_path).sections
    tables = [s for s in sections
              if s.kind == SectionKind.TABLE and s.page_num in (8, 9)]
    got = [
        (s.page_num, len(s.columns), len(s.columns[0]),
         s.table_kind, s.table_source)
        for s in tables
    ]
    assert sorted(got) == sorted(_P4100R0_TABLE_PINS)
    protocol = [s for s in tables if len(s.columns[0]) == 3 and s.page_num in (8, 9)
                and _header_cells(s)[0] == "#"]
    assert len(protocol) == 2
    assert all(_header_cells(s) == ["#", "Paper", "Abstraction"] for s in protocol)
