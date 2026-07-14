#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for ``cli.paper_tools.make_read_paper_tool`` line clamping.

Focus: the ``num_lines`` clamp. A negative ``num_lines`` previously flowed
straight into ``lines[start : start + num_lines]``, so e.g. ``num_lines=-1``
produced ``lines[0:-1]`` - almost the entire document - and bypassed the
``max_lines`` cap entirely. The clamp floors it at 0.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paperstore import SqliteBackend
from cli.paper_tools import make_read_paper_tool

MARKDOWN = "\n".join(f"LINE{n:02d}" for n in range(1, 11))  # LINE01..LINE10


@pytest.fixture
def backend(tmp_path: Path) -> SqliteBackend:
    return SqliteBackend(tmp_path)


@pytest.fixture
def pid(backend: SqliteBackend) -> str:
    paper_id = "P1234R0"
    backend.upsert_year("2026", [
        {"paper_id": paper_id, "url": "https://example.com/p1234r0.html"},
    ])
    backend.write_paper_md(paper_id, MARKDOWN)
    return paper_id


def _lines_present(result: str) -> list[str]:
    return [f"LINE{n:02d}" for n in range(1, 11) if f"LINE{n:02d}" in result]


def test_negative_num_lines_reads_nothing(backend: SqliteBackend, pid: str):
    """The regression guard: -1 must NOT return lines[0:-1]."""
    read = make_read_paper_tool(pid, backend, guard_tag="TAG", max_lines=5)
    result = read(start_line=1, num_lines=-1)
    assert _lines_present(result) == []


def test_zero_num_lines_reads_nothing(backend: SqliteBackend, pid: str):
    read = make_read_paper_tool(pid, backend, guard_tag="TAG", max_lines=5)
    result = read(start_line=1, num_lines=0)
    assert _lines_present(result) == []


def test_num_lines_capped_at_max_lines(backend: SqliteBackend, pid: str):
    read = make_read_paper_tool(pid, backend, guard_tag="TAG", max_lines=5)
    result = read(start_line=1, num_lines=1000)
    assert _lines_present(result) == [f"LINE{n:02d}" for n in range(1, 6)]
    assert "LINE06" not in result


def test_num_lines_beyond_eof_clamps_to_document_end(
    backend: SqliteBackend, pid: str
):
    read = make_read_paper_tool(pid, backend, guard_tag="TAG")
    result = read(start_line=9, num_lines=100)
    assert _lines_present(result) == ["LINE09", "LINE10"]
    assert "of 10]" in result


def test_normal_window(backend: SqliteBackend, pid: str):
    read = make_read_paper_tool(pid, backend, guard_tag="TAG")
    result = read(start_line=3, num_lines=2)
    assert _lines_present(result) == ["LINE03", "LINE04"]
    assert "LINE02" not in result
    assert "LINE05" not in result
