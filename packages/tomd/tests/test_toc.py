"""Tests for lib.toc."""

import logging

from tomd.lib.toc import find_toc_indices, _bridgeable
from tomd.lib.pdf.types import Span, Line, Section, SectionKind


def test_find_toc_strips_dot_leaders():
    texts = ["Abstract ......... 5", "Introduction", "Motivation"]
    headings = {"abstract", "introduction", "motivation"}
    indices = find_toc_indices(texts, headings)
    assert 0 in indices


def test_find_toc_strips_trailing_page_number():
    texts = ["Abstract 42", "Introduction 15", "Motivation 22"]
    headings = {"abstract", "introduction", "motivation"}
    indices = find_toc_indices(texts, headings)
    assert 0 in indices


def test_find_toc_strips_section_prefix():
    texts = ["2.1 Introduction", "2.2 Motivation", "2.3 Design"]
    headings = {"introduction", "motivation", "design"}
    indices = find_toc_indices(texts, headings)
    assert 0 in indices


def test_find_toc_case_insensitive():
    texts = ["ABSTRACT", "INTRODUCTION", "MOTIVATION"]
    headings = {"abstract", "introduction", "motivation"}
    indices = find_toc_indices(texts, headings)
    assert 0 in indices


def test_find_toc_collapses_whitespace():
    texts = ["Some   Entry", "Another   Entry", "Third   Entry"]
    headings = {"some entry", "another entry", "third entry"}
    indices = find_toc_indices(texts, headings)
    assert 0 in indices


def test_find_toc_basic_run():
    texts = ["Abstract", "Introduction", "Motivation", "Body text here"]
    headings = {"Abstract", "Introduction", "Motivation"}
    indices = find_toc_indices(texts, headings)
    assert 0 in indices
    assert 1 in indices
    assert 2 in indices
    assert 3 not in indices


def test_find_toc_gap_bridging():
    texts = ["Abstract", "non-match", "Introduction", "Motivation"]
    headings = {"Abstract", "Introduction", "Motivation"}
    indices = find_toc_indices(texts, headings)
    assert 1 in indices


def test_find_toc_too_few_matches():
    texts = ["Abstract", "Introduction"]
    headings = {"Abstract", "Introduction"}
    indices = find_toc_indices(texts, headings)
    assert len(indices) == 0


def test_find_toc_duplicate_stops_scan():
    texts = ["Abstract", "Introduction", "Motivation",
             "Abstract"]
    headings = {"Abstract", "Introduction", "Motivation"}
    indices = find_toc_indices(texts, headings)
    assert 3 not in indices


def test_find_toc_label_included():
    texts = ["Table of Contents", "Abstract", "Introduction", "Motivation"]
    headings = {"Abstract", "Introduction", "Motivation"}
    indices = find_toc_indices(texts, headings)
    assert 0 in indices


def test_find_toc_empty_inputs():
    assert find_toc_indices([], set()) == set()
    assert find_toc_indices(["x"], set()) == set()
    assert find_toc_indices([], {"x"}) == set()


# ---------------------------------------------------------------------------
# Structural hints fallback (headingless wording papers)
# ---------------------------------------------------------------------------

def _make_toc_section(title: str, page: str, x: float = 400.0) -> "Section":
    """Build a Section whose text has a bare page number on the second line."""
    page_span = Span(text=page, bbox=(x, 0, x + 20, 10))
    page_line = Line(spans=[page_span])
    title_span = Span(text=title)
    title_line = Line(spans=[title_span])
    return Section(
        kind=SectionKind.WORDING_ADD,
        text=f"{title}\n{page}",
        lines=[title_line, page_line],
    )


def _hints(sections) -> "list[bool]":
    from tomd.lib.pdf.pipeline import _toc_structural_hints
    return _toc_structural_hints(sections)


class TestStructuralTocHints:
    def test_basic_run_detected(self):
        secs = [
            _make_toc_section("Introduction", "5"),
            _make_toc_section("Motivation", "8"),
            _make_toc_section("Design", "12"),
        ]
        hints = _hints(secs)
        indices = find_toc_indices(
            [s.text for s in secs], set(), hints)
        assert {0, 1, 2} == indices

    def test_too_few_entries_not_detected(self):
        secs = [_make_toc_section("A", "1"), _make_toc_section("B", "2")]
        hints = _hints(secs)
        indices = find_toc_indices([s.text for s in secs], set(), hints)
        assert len(indices) == 0

    def test_non_toc_section_excluded(self):
        body = Section(kind=SectionKind.PARAGRAPH,
                       text="This is body text with no page number.")
        secs = [
            _make_toc_section("Introduction", "5"),
            _make_toc_section("Motivation", "8"),
            _make_toc_section("Design", "12"),
            body,
        ]
        hints = _hints(secs)
        indices = find_toc_indices([s.text for s in secs], set(), hints)
        assert 3 not in indices

    def test_headings_present_ignores_structural_hints(self):
        """When headings are non-empty the structural fallback is not used."""
        secs = [_make_toc_section("X", "1"), _make_toc_section("Y", "2")]
        # Normally 2 entries would not form a TOC via structural hints.
        # With headings supplied they should also not form a TOC (too few).
        hints = _hints(secs)
        indices = find_toc_indices(
            [s.text for s in secs], {"X", "Y"}, hints)
        assert len(indices) == 0

    def test_outlier_x_position_excluded_from_hints(self):
        """A candidate whose x differs from the cluster is not marked as a hint."""
        from tomd.lib.pdf.pipeline import _TOC_X_TOLERANCE, _toc_structural_hints
        normal_x = 400.0
        outlier_x = normal_x + _TOC_X_TOLERANCE + 20.0
        secs = [
            _make_toc_section("A", "1", x=normal_x),
            _make_toc_section("B", "2", x=normal_x),
            _make_toc_section("C", "3", x=outlier_x),
        ]
        hints = _toc_structural_hints(secs)
        assert hints[0] is True
        assert hints[1] is True
        assert hints[2] is False


def test_exact_match_skips_fuzzy_on_large_heading_set():
    """When headings exceed _MAX_FUZZY_HEADINGS, only exact matches are used."""
    headings = {f"Section {i}" for i in range(300)}
    texts = ["Section 0", "Section 1", "Section 2", "Section 3",
             "Body paragraph", "Section 5"]
    result = find_toc_indices(texts, headings)
    assert 0 in result
    assert 1 in result
    assert 2 in result
    assert 3 in result


def test_large_toc_completes_quickly():
    """Performance guard: 1000 sections x 500 headings must finish in < 2s."""
    import time
    headings = {f"Heading {i}" for i in range(500)}
    texts = [f"Heading {i % 500}" for i in range(1000)]
    t0 = time.monotonic()
    find_toc_indices(texts, headings)
    elapsed = time.monotonic() - t0
    assert elapsed < 2.0, f"TOC detection took {elapsed:.1f}s, expected < 2s"


# ---------------------------------------------------------------------------
# Heading self-match exclusion (Change A) and gap-fill prose guard (Change B).
# A short paper of alternating HEADING/PARAGRAPH sections used to have its
# entire body deleted: every body heading matched itself in the heading set,
# and the gap-fill swallowed the prose between them. See #122.
# ---------------------------------------------------------------------------

def test_heading_sections_do_not_self_match():
    """Body headings excluded when is_heading is set; inert when it is not."""
    texts = ["Introduction", "x", "Motivation", "y", "Design"]
    headings = {"Introduction", "Motivation", "Design"}
    is_heading = [True, False, True, False, True]
    # With is_heading, the body headings are not eligible TOC matches.
    assert find_toc_indices(texts, headings, None, is_heading=is_heading) == set()
    # Without is_heading, the legacy self-match path is unchanged: the headings
    # match themselves and the trivial gaps bridge into a phantom TOC run.
    assert find_toc_indices(texts, headings) == {0, 1, 2, 3, 4}


def test_genuine_toc_paragraph_entries_detected():
    """Paragraph-kind TOC entries (is_heading all False) are still detected."""
    texts = ["Introduction", "Motivation", "Design"]
    headings = {"Introduction", "Motivation", "Design"}
    is_heading = [False, False, False]
    assert find_toc_indices(texts, headings, None, is_heading=is_heading) == {0, 1, 2}


def test_heading_kind_toc_with_dot_leader_pagenum_still_stripped():
    """A heading-kind TOC shaped like TOC lines (dot leader + page) is stripped."""
    texts = ["2.1 Foo .......... 7",
             "2.2 Bar .......... 8",
             "2.3 Baz .......... 9"]
    headings = {"Foo", "Bar", "Baz"}
    is_heading = [True, True, True]
    assert find_toc_indices(texts, headings, None, is_heading=is_heading) == {0, 1, 2}


def test_heading_kind_toc_pagenum_only_not_stripped():
    """Heading-kind entries with a bare page number but no dot leader leak.

    This is the deliberate scope at the `find_toc_indices` layer: a
    no-dot-leader heading-kind TOC is left in the body rather than risking the
    Step-1 deletion class. The leak is cleaned up downstream by
    `structure.drop_leaked_toc_headings`, but *only* when each entry recurs as
    a later heading. These synthetic entries have no later duplicate, so the
    post-pass also leaves them: this test pins the find_toc_indices behaviour
    in isolation, and the no-recurrence case the post-pass deliberately keeps.
    """
    texts = ["2.1 Foo 7", "2.2 Bar 8", "2.3 Baz 9"]
    headings = {"Foo", "Bar", "Baz"}
    is_heading = [True, True, True]
    assert find_toc_indices(texts, headings, None, is_heading=is_heading) == set()


def test_body_heading_step_run_not_matched():
    """`Step 1 / Step 2 / Step 3` headings are never TOC, separated or not."""
    headings = {"Step 1", "Step 2", "Step 3"}
    back_to_back = ["Step 1", "Step 2", "Step 3"]
    assert find_toc_indices(
        back_to_back, headings, None, is_heading=[True, True, True]) == set()
    prose_separated = ["Step 1", "do something here",
                       "Step 2", "do another thing", "Step 3"]
    assert find_toc_indices(
        prose_separated, headings, None,
        is_heading=[True, False, True, False, True]) == set()


def test_body_heading_without_structure_not_matched():
    """Plain body headings (no number, no dots) are not matched (core bug fix)."""
    texts = ["Introduction", "Motivation", "Design"]
    headings = {"Introduction", "Motivation", "Design"}
    is_heading = [True, True, True]
    assert find_toc_indices(texts, headings, None, is_heading=is_heading) == set()


def test_gap_fill_does_not_swallow_prose():
    """A long prose paragraph in a gap breaks the run instead of being included."""
    texts = ["Introduction", "Motivation", "Design",
             "This is a long prose paragraph with many words indeed.",
             "Conclusion"]
    headings = {"Introduction", "Motivation", "Design", "Conclusion"}
    is_heading = [False, False, False, False, False]
    indices = find_toc_indices(texts, headings, None, is_heading=is_heading)
    assert {0, 1, 2} <= indices
    assert 3 not in indices


def test_gap_fill_bridges_trivial_gap():
    """A short/blank/numeric gap is still bridged (mirrors gap-bridging test)."""
    texts = ["Introduction", "x", "Motivation", "Design"]
    headings = {"Introduction", "Motivation", "Design"}
    is_heading = [False, False, False, False]
    assert 1 in find_toc_indices(texts, headings, None, is_heading=is_heading)


def test_long_toc_entry_in_gap_breaks_run():
    """Deliberate trade-off: a long unmatched TOC title in a gap breaks the run.

    Change B under-strips a genuine TOC with a long unmatched entry rather than
    risk swallowing prose. Per the repo fidelity rule, leaking a TOC line is
    acceptable; deleting body is not.
    """
    texts = ["Introduction", "Motivation", "Design",
             "A Very Long Section Title That Exceeds The Word Limit",
             "Conclusion"]
    headings = {"Introduction", "Motivation", "Design", "Conclusion"}
    is_heading = [False, False, False, False, False]
    indices = find_toc_indices(texts, headings, None, is_heading=is_heading)
    assert {0, 1, 2} <= indices
    assert 3 not in indices


def test_bridgeable_predicate():
    """_bridgeable: blank/number/short label bridge; a prose sentence does not."""
    assert _bridgeable("") is True
    assert _bridgeable("42") is True
    assert _bridgeable("2.1") is True
    assert _bridgeable("Short label here") is True
    assert _bridgeable(
        "This sentence is quite definitely much too long to bridge.") is False


def test_is_heading_length_mismatch_safe():
    """An is_heading shorter than texts does not raise (defensive index guard)."""
    texts = ["Introduction", "Motivation", "Design"]
    headings = {"Introduction", "Motivation", "Design"}
    # Must not raise IndexError; indices past the list fall back to matching.
    find_toc_indices(texts, headings, None, is_heading=[True])


def test_missing_is_heading_logs_debug(caplog):
    """Omitting is_heading with non-empty headings leaves a debug signal."""
    caplog.set_level(logging.DEBUG)
    find_toc_indices(["Introduction", "Motivation", "Design"],
                     {"Introduction", "Motivation", "Design"})
    assert any("is_heading" in r.message and r.levelno == logging.DEBUG
               for r in caplog.records)
