"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from tomd.domain.table import (
    CellAlign,
    CodeCell,
    Table,
    TableKind,
    TableRow,
    TableStrategy,
    TextCell,
)
from tomd.writers.markdown.tables import write_table


def test_write_pipe_table_basic():
    table = Table(
        headers=[TextCell.from_text("Option"), TextCell.from_text("Description")],
        rows=[
            TableRow(cells=[TextCell.from_text("-a"), TextCell.from_text("all")]),
            TableRow(cells=[TextCell.from_text("-b"), TextCell.from_text("batch")]),
        ],
    )
    expected = (
        "| Option | Description |\n"
        "| --- | --- |\n"
        "| -a | all |\n"
        "| -b | batch |"
    )
    assert write_table(table) == expected


def test_write_pipe_table_alignment_and_escaped_pipes():
    table = Table(
        headers=[
            TextCell.from_text("Left", align=CellAlign.LEFT),
            TextCell.from_text("Center", align=CellAlign.CENTER),
            TextCell.from_text("Right", align=CellAlign.RIGHT),
        ],
        rows=[
            TableRow(cells=[
                TextCell.from_text("a | b"),
                TextCell.from_text("multi\nline"),
                TextCell.from_text("100"),
            ]),
        ],
    )
    expected = (
        "| Left | Center | Right |\n"
        "| :--- | :---: | ---: |\n"
        "| a \\| b | multi<br>line | 100 |"
    )
    assert write_table(table) == expected


def test_write_table_with_code_cells():
    table = Table(
        headers=[TextCell.from_text("Before"), TextCell.from_text("After")],
        rows=[
            TableRow(cells=[
                CodeCell(code="void foo();", language="cpp"),
                CodeCell(code="void foo() noexcept;", language="cpp"),
            ]),
        ],
        strategy=TableStrategy.MIXED_HTML,
        kind=TableKind.TONY_TABLE,
    )
    rendered = write_table(table)
    expected = (
        "| Before | After |\n"
        "| --- | --- |\n"
        "| `void foo();` | `void foo() noexcept;` |"
    )
    assert rendered == expected
    assert "<table" not in rendered
    assert "<!-- tomd:mixed-table -->" not in rendered


def test_write_table_with_multiline_code_cells():
    table = Table(
        headers=[TextCell.from_text("Code")],
        rows=[
            TableRow(cells=[
                CodeCell(code="template <typename T>\nvoid bar();"),
            ]),
        ],
    )
    rendered = write_table(table)
    expected = (
        "| Code |\n"
        "| --- |\n"
        "| `template <typename T>`<br>`void bar();` |"
    )
    assert rendered == expected
    assert "<table" not in rendered


def test_write_table_never_emits_html_even_for_tony_table_strategy():
    table = Table(
        headers=[TextCell.from_text("Col 1"), TextCell.from_text("Col 2")],
        rows=[
            TableRow(cells=[
                TextCell.from_text("A"),
                TextCell.from_text("B"),
            ]),
        ],
        strategy=TableStrategy.MIXED_HTML,
        kind=TableKind.TONY_TABLE,
    )
    rendered = write_table(table)
    assert rendered.startswith("| Col 1 | Col 2 |")
    assert "<table" not in rendered
    assert "<tr" not in rendered
    assert "<td" not in rendered
    assert "<th" not in rendered


def test_write_table_empty():
    assert write_table(Table()) == ""
