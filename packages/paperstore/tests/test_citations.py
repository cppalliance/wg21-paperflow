#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

"""Tests for ``paperstore.citations.extract_citations``."""

from __future__ import annotations

from paperstore.citations import Citation, extract_citations


def test_extracts_p_and_n_ids():
    refs = extract_citations("See P1234R0 and N4567 for context.")
    assert {r.paper_id for r in refs} == {"P1234R0", "N4567"}


def test_extracts_d_drafts():
    refs = extract_citations("D9999R2 is a draft revision.")
    assert refs == [Citation(paper_id="D9999R2", count=1)]


def test_counts_are_summed_per_id():
    refs = extract_citations("P1234R0 ... P1234R0 ... P1234R0 ... P9999R0")
    counts = {r.paper_id: r.count for r in refs}
    assert counts == {"P1234R0": 3, "P9999R0": 1}


def test_case_insensitive_match_normalizes_to_upper():
    refs = extract_citations("see p1234r0 and P1234R0")
    assert refs == [Citation(paper_id="P1234R0", count=2)]


def test_link_url_target_stripped():
    """``[text](https://wg21.link/P1234R0)`` -- the URL part is not counted."""
    refs = extract_citations("[the proposal](https://wg21.link/P1234R0)")
    assert refs == []


def test_link_text_still_counts():
    """``[P1234R0](URL)`` counts once: text matches, URL is stripped."""
    refs = extract_citations("[P1234R0](https://wg21.link/P1234R0)")
    assert refs == [Citation(paper_id="P1234R0", count=1)]


def test_sorted_by_count_descending():
    refs = extract_citations("P1 P9999R0 P1 P9999R0 P1234R0 P1234R0 P1234R0")
    # P1234R0 has 3 hits, P9999R0 has 2, "P1" doesn't match the regex
    assert [r.paper_id for r in refs] == ["P1234R0", "P9999R0"]
    assert refs[0].count == 3
    assert refs[1].count == 2


def test_empty_input():
    assert extract_citations("") == []


def test_no_matches():
    assert extract_citations("Just prose, no WG21 IDs here.") == []
