#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

from __future__ import annotations

from assay.chunker import Section, _build_tree, _parse_headings, chunk_paper


SIMPLE_PAPER = """\
---
title: Test
---

## Section One

This is section one with some content that spans
multiple lines to give it enough characters.

## Section Two

Short.

## Section Three

This section has more text to work with so it will
be above the minimum character threshold we set. It
contains multiple sentences and paragraphs to make
it substantive enough for testing purposes.

More content here to pad it out a bit further for
the character count to be meaningful.
"""

BOLD_SUBSECTION_PAPER = """\
---
title: Test Bold Subsections
---

## Big Section

Some intro text.

**3.1** **First Subsection**

Content of first subsection that should be split out
into its own chunk when the parent is oversized.

**3.2** **Second Subsection**

Content of second subsection with enough text to be
meaningful and testable as an independent chunk.

**3.3** **Third Subsection**

Content of third subsection rounding out the test.
"""

ISSUE_LIST_PAPER = """\
---
title: Ready Issues
---

## Ready issues in C++26

#### Issue one
Content for issue one.

#### Issue two
Content for issue two.

#### Issue three
Content for issue three.
"""


def _legacy_direct_children(
    headings: list[tuple[int, int, str]],
    start: int,
    end: int,
    parent_level: int,
) -> list[tuple[int, int, str]]:
    """Pre-fix child selection: only headings at parent_level + 1."""
    return [
        (ln, lv, t)
        for ln, lv, t in headings
        if start < ln < end and lv == parent_level + 1
    ]


class TestChunkPaperBasic:
    def test_returns_sections(self):
        result = chunk_paper(SIMPLE_PAPER)
        assert all(isinstance(s, Section) for s in result)

    def test_sections_have_char_count(self):
        result = chunk_paper(SIMPLE_PAPER)
        assert all(s.char_count > 0 for s in result)

    def test_sections_cover_full_paper(self):
        result = chunk_paper(SIMPLE_PAPER)
        assert result[0].start_line >= 1
        lines = SIMPLE_PAPER.splitlines()
        assert result[-1].end_line <= len(lines)

    def test_no_gaps_between_sections(self):
        result = chunk_paper(SIMPLE_PAPER)
        for i in range(len(result) - 1):
            assert result[i].end_line == result[i + 1].start_line - 1 or \
                   result[i].end_line >= result[i + 1].start_line - 1

    def test_empty_source(self):
        result = chunk_paper("")
        assert len(result) == 1
        assert result[0].heading == "(untitled)"

    def test_no_headings(self):
        result = chunk_paper("Just plain text\nwith no headings.\n")
        assert len(result) == 1
        assert result[0].heading == "(untitled)"



class TestDefaultChunking:
    def test_all_sections_returned(self):
        result = chunk_paper(SIMPLE_PAPER, max_chars=50)
        headings = [s.heading for s in result]
        assert any("Section One" in h for h in headings)
        assert any("Section Three" in h for h in headings)

    def test_short_sections_merged(self):
        result = chunk_paper(SIMPLE_PAPER)
        assert len(result) >= 1
        assert all(s.char_count > 0 for s in result)



class TestMaxChars:
    def test_large_max_no_split(self):
        result = chunk_paper(SIMPLE_PAPER, max_chars=999999)
        all_under = all(s.char_count <= 999999 for s in result)
        assert all_under

    def test_small_max_more_chunks(self):
        big = chunk_paper(SIMPLE_PAPER, max_chars=999999)
        small = chunk_paper(SIMPLE_PAPER, max_chars=100)
        assert len(small) >= len(big)


class TestBoldSubsectionSplit:
    def test_splits_on_bold_pattern(self):
        result = chunk_paper(BOLD_SUBSECTION_PAPER, max_chars=50)
        headings = [s.heading for s in result]
        assert any("3.1" in h for h in headings)
        assert any("3.2" in h for h in headings)
        assert any("3.3" in h for h in headings)

    def test_no_split_when_under_max(self):
        result = chunk_paper(BOLD_SUBSECTION_PAPER, max_chars=999999)
        assert len(result) == 1

    def test_split_preserves_line_numbers(self):
        result = chunk_paper(BOLD_SUBSECTION_PAPER, max_chars=50)
        for s in result:
            assert s.start_line >= 1
            assert s.end_line >= s.start_line


class TestSkippedHeadingLevels:
    def test_splits_h4_under_h2_without_h3(self):
        result = chunk_paper(ISSUE_LIST_PAPER, max_chars=50)
        assert len(result) > 1

    def test_issue_chunks_under_cap(self):
        max_chars = 50
        result = chunk_paper(ISSUE_LIST_PAPER, max_chars=max_chars)
        assert all(s.char_count <= max_chars for s in result)

    def test_preserves_issue_headings(self):
        result = chunk_paper(ISSUE_LIST_PAPER, max_chars=50)
        headings = [s.heading for s in result]
        assert any("Issue one" in h for h in headings)
        assert any("Issue two" in h for h in headings)
        assert any("Issue three" in h for h in headings)

    def test_line_coverage(self):
        result = chunk_paper(ISSUE_LIST_PAPER, max_chars=50)
        lines = ISSUE_LIST_PAPER.splitlines()
        assert result[0].start_line >= 1
        assert result[-1].end_line <= len(lines)
        for i in range(len(result) - 1):
            assert result[i].end_line == result[i + 1].start_line - 1 or \
                   result[i].end_line >= result[i + 1].start_line - 1


class TestIncidentalIntermediateHeading:
    """Prefix span before a lone H3 must still use skipped-level fallback."""

    def test_prefix_h4_issues_split_when_later_h3_exists(
        self, survey_max_chars,
    ):
        prefix_issues = []
        for i in range(1, 11):
            body = "\n".join(
                f"Wording detail line {j} for issue {i}."
                for j in range(1, 26)
            )
            prefix_issues.append(f"#### Issue {i}\n{body}")
        suffix_issues = []
        for i in range(11, 16):
            body = "\n".join(
                f"Wording detail line {j} for issue {i}."
                for j in range(1, 26)
            )
            suffix_issues.append(f"#### Issue {i}\n{body}")
        paper = (
            "---\n"
            "title: Ready Issues\n"
            "---\n\n"
            "## Ready issues in C++26\n\n"
            + "\n\n".join(prefix_issues)
            + "\n\n### Editorial notes\n\n"
            "One incidental intermediate heading after many H4 issues.\n\n"
            + "\n\n".join(suffix_issues)
        )

        result = chunk_paper(paper, max_chars=survey_max_chars)
        headings = [s.heading for s in result]

        assert len(result) > 1
        assert any("Issue 1" in h for h in headings)
        assert any("Issue 5" in h for h in headings)
        assert any("Issue 10" in h for h in headings)
        assert max(s.char_count for s in result) < len(paper) // 2

    def test_prefix_tree_recurses_into_h4_before_incidental_h3(self):
        lines = [
            "---",
            "title: Ready Issues",
            "---",
            "",
            "## Ready issues in C++26",
            "",
            "#### Issue 1",
            "Content one.",
            "",
            "#### Issue 2",
            "Content two.",
            "",
            "### Editorial notes",
            "",
            "#### Issue 3",
            "Content three.",
        ]
        headings = _parse_headings(lines)
        h2_line = next(ln for ln, lv, _t in headings if lv == 2)
        h3_line = next(ln for ln, lv, _t in headings if lv == 3)

        tree = _build_tree(lines, headings, h2_line, len(lines), 2)
        prefix = next(s for s in tree if s.start_line <= h3_line + 1 and s.end_line == h3_line)
        prefix_children = [s for s in prefix.children if s.level == 4]

        assert len(prefix_children) == 2
        assert {s.heading for s in prefix_children} == {"Issue 1", "Issue 2"}


class TestP4160R0ChunkerRegression:
    """Regression tests for P4160R0: old chunker produced one monolithic chunk."""

    def test_legacy_tree_ignores_h4_when_h3_absent(self, large_issue_list_paper):
        lines = large_issue_list_paper.splitlines()
        headings = _parse_headings(lines)
        h2_line = next(ln for ln, lv, _t in headings if lv == 2)

        legacy_children = _legacy_direct_children(headings, h2_line, len(lines), 2)
        assert legacy_children == []

        fixed_children = _build_tree(lines, headings, h2_line, len(lines), 2)
        issue_children = [s for s in fixed_children if s.level == 4]
        assert len(issue_children) == 20

    def test_large_issue_list_not_monolithic_under_survey_budget(
        self, large_issue_list_paper, survey_max_chars,
    ):
        result = chunk_paper(large_issue_list_paper, max_chars=survey_max_chars)

        assert len(result) > 1
        assert len(result) >= 5
        assert max(s.char_count for s in result) < len(large_issue_list_paper) // 2

    def test_old_behavior_would_fail_single_chunk_assertion(
        self, large_issue_list_paper, survey_max_chars,
    ):
        """Documents the pre-fix failure: one chunk covered the whole paper."""
        result = chunk_paper(large_issue_list_paper, max_chars=survey_max_chars)
        lines = large_issue_list_paper.splitlines()

        old_style_single_chunk = len(result) == 1 and result[0].end_line >= len(lines) - 1
        assert not old_style_single_chunk

    def test_issue_headings_split_out_not_merged_into_h2_only(
        self, large_issue_list_paper, survey_max_chars,
    ):
        result = chunk_paper(large_issue_list_paper, max_chars=survey_max_chars)
        headings = [s.heading for s in result]

        assert any(h.startswith("Issue 1") or " + Issue 1" in h for h in headings)
        assert any("Issue 10" in h for h in headings)
        assert any("Issue 20" in h for h in headings)
