#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Metric invariants (identity, symmetry, bounds, monotonicity).

The guard and bench paths trust the metric engine implicitly: if a refactor of
teds/mhs/text_nid silently breaks identity or bounds, every downstream verdict
is corrupted. These are the cheap, structural property checks the surveyed
projects rely on (pandoc QuickCheck round-trips, pdfplumber domain invariants),
adapted to whisker's deterministic metrics with a fixed, varied input table so
no extra dependency is needed.
"""

import pytest

from whisker.metrics import mhs, normalized_edit_distance, teds, text_nid

_TEXTS = [
    "",
    "a",
    "the quick brown fox jumps over the lazy dog",
    "P2300R7 std::execution sender receiver model",
    "unicode: \u00e9\u00e8\u00ea CJK \u4e2d\u6587 digits 12345",
    "Multi\nline\ntext\nwith breaks",
]

_TABLES = [
    "<table><tr><td>a</td><td>b</td></tr><tr><td>1</td><td>2</td></tr></table>",
    "<table><tr><td>x</td></tr></table>",
    "<table><tr><td>h1</td><td>h2</td><td>h3</td></tr>"
    "<tr><td>1</td><td>2</td><td>3</td></tr></table>",
]

_DOCS = [
    "",
    "# Title\n\nbody",
    "## A\n\ntext\n\n## B\n\nmore",
    "## A\n\n### A1\n\nx\n\n### A2\n\ny\n\n## B\n\nz",
]


@pytest.mark.parametrize("a", _TEXTS)
def test_text_nid_identity(a):
    assert text_nid(a, a) == 1.0


@pytest.mark.parametrize("a", _TEXTS)
@pytest.mark.parametrize("b", _TEXTS)
def test_text_nid_symmetry_and_bounds(a, b):
    v = text_nid(a, b)
    assert 0.0 <= v <= 1.0
    assert text_nid(a, b) == text_nid(b, a)


@pytest.mark.parametrize("a", _TEXTS)
@pytest.mark.parametrize("b", _TEXTS)
def test_ned_identity_symmetry_bounds(a, b):
    assert normalized_edit_distance(a, a) == 0.0
    v = normalized_edit_distance(a, b)
    assert 0.0 <= v <= 1.0
    assert v == normalized_edit_distance(b, a)


def test_ned_and_text_nid_are_complementary():
    a, b = "allocator", "allocater"
    assert text_nid(a, b) == pytest.approx(1.0 - normalized_edit_distance(a, b))


@pytest.mark.parametrize("t", _TABLES)
def test_teds_identity(t):
    assert teds(t, t) == pytest.approx(1.0)


@pytest.mark.parametrize("a", _TABLES)
@pytest.mark.parametrize("b", _TABLES)
def test_teds_bounds(a, b):
    assert 0.0 <= teds(a, b) <= 1.0


def test_teds_no_table_is_zero():
    assert teds("no table here", "<table><tr><td>x</td></tr></table>") == 0.0


def test_teds_cell_change_lowers_score():
    a = "<table><tr><td>1</td><td>2</td></tr></table>"
    b = "<table><tr><td>1</td><td>9</td></tr></table>"
    assert teds(a, b) < 1.0


@pytest.mark.parametrize("d", _DOCS)
def test_mhs_identity(d):
    assert mhs(d, d) == pytest.approx(1.0)


@pytest.mark.parametrize("a", _DOCS)
@pytest.mark.parametrize("b", _DOCS)
def test_mhs_symmetry_and_bounds(a, b):
    v = mhs(a, b)
    assert 0.0 <= v <= 1.0
    assert mhs(a, b) == pytest.approx(mhs(b, a))


def test_mhs_no_headings_is_one():
    assert mhs("just prose", "different prose") == pytest.approx(1.0)


def test_mhs_missing_section_lowers_score():
    full = "## A\n\nx\n\n## B\n\ny"
    partial = "## A\n\nx"
    assert mhs(partial, full) < 1.0
