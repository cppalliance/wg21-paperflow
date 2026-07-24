#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the in-memory virtual filesystem."""

from __future__ import annotations

import pytest

from promptforge.vfs import MemVFS


def test_create_and_read() -> None:
    vfs = MemVFS()
    vfs.create("a.md", "hello")
    assert vfs.exists("a.md")
    assert vfs.read("a.md") == "hello"


def test_create_overwrites() -> None:
    vfs = MemVFS()
    vfs.create("a.md", "one")
    vfs.create("a.md", "two")
    assert vfs.read("a.md") == "two"


def test_append_creates_then_appends() -> None:
    vfs = MemVFS()
    vfs.append("log.md", "a")
    vfs.append("log.md", "b")
    assert vfs.read("log.md") == "ab"


def test_read_missing_raises() -> None:
    with pytest.raises(FileNotFoundError):
        MemVFS().read("nope.md")


def test_delete_removes_and_missing_raises() -> None:
    vfs = MemVFS()
    vfs.create("a.md", "x")
    vfs.delete("a.md")
    assert not vfs.exists("a.md")
    with pytest.raises(FileNotFoundError):
        vfs.delete("a.md")


def test_glob_matches_and_is_sorted() -> None:
    vfs = MemVFS()
    vfs.create("section-2.md", "2")
    vfs.create("section-1.md", "1")
    vfs.create("other.md", "x")
    assert vfs.glob("section-*.md") == ["section-1.md", "section-2.md"]


def test_paths_lists_all() -> None:
    vfs = MemVFS()
    vfs.create("a.md", "1")
    vfs.create("b.md", "2")
    assert sorted(vfs.paths()) == ["a.md", "b.md"]
