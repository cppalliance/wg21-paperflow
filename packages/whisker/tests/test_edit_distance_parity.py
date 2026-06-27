#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Frozen parity vectors for the GPL-levenshtein -> MIT-rapidfuzz migration.

The values below were captured from the original ``levenshtein`` C-extension
before it was swapped for ``rapidfuzz.distance.Levenshtein``. They are baked in
as literals (not recomputed from either library) so the test stays a genuine
regression oracle: it fails if rapidfuzz ever diverges from the historical
edit-distance semantics, independent of whichever package is installed. The
license-ban test guards that the GPL import never creeps back in.
"""

import pathlib

import pytest
from rapidfuzz.distance import Levenshtein as _Lev

from whisker.metrics import normalized_edit_distance

# (a, b, raw_distance, normalized_edit_distance)
_PARITY = [
    ("abc", "abc", 0, 0.0),
    ("abc", "abd", 1, 1 / 3),
    ("kitten", "sitting", 3, 3 / 7),
    ("allocator", "allocater", 1, 1 / 9),
    ("", "x", 1, 1.0),
    ("flaw", "lawn", 2, 0.5),
    ("hello world", "hello there", 5, 5 / 11),
    ("template<class T>", "template <class T>", 1, 1 / 18),
]

# Integer-sequence parity (reading_order_ned compares lists of block ids).
_SEQ_PARITY = [
    ((0, 1, 2, 3), (0, 2, 1, 3), 2),
    ((1, 2, 3), (3, 2, 1), 2),
    ((5, 1, 9, 2), (1, 5, 2, 9), 3),
]


@pytest.mark.parametrize("a,b,raw,nid", _PARITY)
def test_string_distance_parity(a, b, raw, nid):
    assert _Lev.distance(a, b) == raw
    assert normalized_edit_distance(a, b) == pytest.approx(nid)


@pytest.mark.parametrize("a,b,raw", _SEQ_PARITY)
def test_int_sequence_distance_parity(a, b, raw):
    assert _Lev.distance(list(a), list(b)) == raw


def test_no_gpl_levenshtein_import():
    """Lint-ban: the GPL ``levenshtein`` package must never be imported again."""
    src = pathlib.Path(__file__).resolve().parent.parent / "src" / "whisker"
    offenders = []
    for path in src.rglob("*.py"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("import Levenshtein") or stripped.startswith(
                "from Levenshtein"
            ):
                offenders.append(f"{path.name}:{lineno}")
    assert not offenders, (
        "GPL 'levenshtein' import found (use rapidfuzz.distance.Levenshtein): "
        + ", ".join(offenders)
    )
