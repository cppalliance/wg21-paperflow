#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for source-vs-candidate paragraph-boundary comparison."""

from __future__ import annotations

import pymupdf
import pytest
from whisker.det.paragraph_align import (
    CONVENTION_INDENT,
    CONVENTION_SKIP,
    STATUS_ABSTAINED,
    STATUS_CHECKED,
    STATUS_UNSUPPORTED,
    compare_paragraph_boundaries,
)
from whisker.det.pdf_geometry import load_pdf_lines

_BODY_SIZE = 11.0
_MARGIN_X = 72.0
_INDENT_X = 84.0
_LEADING = 12.0
_SKIP = 20.0
_PARAGRAPHS = 12
_LINES_PER_PARAGRAPH = 4
# A footnote marker small enough and raised far enough that its ascender clears
# the prose ascender, which is what inflates the line bbox on real papers.
_MARKER_SIZE = 7.0
# Measured ceiling: above a 5pt rise MuPDF stops grouping the marker into the
# prose line, and a marker on its own line exercises nothing.
_MARKER_RISE = 5.0


def _paragraph_lines(index: int) -> list[str]:
    """Four distinct four-word lines, so every paragraph anchors uniquely."""
    stems = ("alpha", "beta", "gamma", "delta")
    return [
        " ".join(f"{stem}{index}{slot}" for slot in range(4))
        for stem in stems
    ]


def _all_paragraphs() -> list[list[str]]:
    return [_paragraph_lines(index) for index in range(_PARAGRAPHS)]


def _write_pdf(path, paragraphs, *, indent: bool) -> None:
    """Lay out paragraphs with exactly one of the two typographic conventions.

    ``indent``: first line pushed right, uniform leading throughout.
    Otherwise: everything flush left, extra leading between paragraphs.
    """
    document = pymupdf.open()
    page = document.new_page()
    y = 72.0
    for paragraph in paragraphs:
        for line_index, line in enumerate(paragraph):
            if line_index == 0 and not indent and y > 72.0:
                y += _SKIP - _LEADING
            x = _INDENT_X if (indent and line_index == 0) else _MARGIN_X
            page.insert_text((x, y), line, fontsize=_BODY_SIZE)
            y += _LEADING
    document.save(path)
    document.close()


def _candidate(paragraphs, *, merge_at: int | None = None) -> str:
    """Markdown with one block per source paragraph, optionally merging a pair."""
    blocks = [" ".join(lines) for lines in paragraphs]
    if merge_at is not None:
        blocks[merge_at:merge_at + 2] = [
            blocks[merge_at] + " " + blocks[merge_at + 1]
        ]
    return "\n\n".join(blocks) + "\n"


def test_indent_convention_faithful_candidate_is_clean(tmp_path):
    pdf = tmp_path / "indent.pdf"
    paragraphs = _all_paragraphs()
    _write_pdf(pdf, paragraphs, indent=True)

    result = compare_paragraph_boundaries(pdf, _candidate(paragraphs))

    assert result.status == STATUS_CHECKED
    assert result.convention == CONVENTION_INDENT
    assert result.analysed == _PARAGRAPHS
    assert result.merged == ()


def test_indent_convention_detects_swallowed_break(tmp_path):
    """The positive control: two source paragraphs fused into one block."""
    pdf = tmp_path / "indent.pdf"
    paragraphs = _all_paragraphs()
    _write_pdf(pdf, paragraphs, indent=True)

    result = compare_paragraph_boundaries(
        pdf, _candidate(paragraphs, merge_at=5),
    )

    assert result.status == STATUS_CHECKED
    assert result.convention == CONVENTION_INDENT
    assert result.merged_count == 1
    # The evidence must locate the join: paragraph 5's tail, paragraph 6's head.
    before, after = result.merged[0].split(" | ")
    assert "delta53" in before
    assert after.startswith("alpha60")


def test_indent_beats_a_more_frequent_block_indent(tmp_path):
    """Frequency picks the wrong cluster; isolation must pick the right one.

    A sustained block indent with MORE lines than the paragraph indent is the
    exact shape that fooled the first detector on P0957R8.
    """
    pdf = tmp_path / "decoy.pdf"
    paragraphs = _all_paragraphs()
    document = pymupdf.open()
    page = document.new_page()
    y = 72.0
    for paragraph in paragraphs:
        for line_index, line in enumerate(paragraph):
            x = _INDENT_X if line_index == 0 else _MARGIN_X
            page.insert_text((x, y), line, fontsize=_BODY_SIZE)
            y += _LEADING
    # A wholly-indented block at x0=110: more lines than the 12 paragraph
    # openers, but every one of them is followed by another indented line.
    for block_index in range(20):
        page.insert_text((110.0, y), f"quote{block_index} text here now",
                         fontsize=_BODY_SIZE)
        y += _LEADING
    document.save(pdf)
    document.close()

    result = compare_paragraph_boundaries(pdf, _candidate(paragraphs))

    assert result.convention == CONVENTION_INDENT
    assert "84.0" in result.detail
    assert result.merged == ()


def test_skip_convention_detects_swallowed_break(tmp_path):
    pdf = tmp_path / "skip.pdf"
    paragraphs = _all_paragraphs()
    _write_pdf(pdf, paragraphs, indent=False)

    clean = compare_paragraph_boundaries(pdf, _candidate(paragraphs))
    fused = compare_paragraph_boundaries(pdf, _candidate(paragraphs, merge_at=3))

    assert clean.convention == CONVENTION_SKIP
    assert clean.merged == ()
    assert fused.merged_count == 1


def test_superscript_does_not_fake_a_paragraph_break(tmp_path):
    """Mixed-size lines do not disturb the skip convention end to end.

    Not the regression guard for the P3556R0 false positives: measured against
    a bbox-top build of the module, this test still passes, because a synthetic
    marker cannot reproduce that paper's exact inflation. The guard with teeth
    is test_line_baseline_ignores_a_superscript_in_the_same_line below.
    """
    pdf = tmp_path / "footnote.pdf"
    paragraphs = _all_paragraphs()
    document = pymupdf.open()
    page = document.new_page()
    y = 72.0
    for paragraph in paragraphs:
        for line_index, line in enumerate(paragraph):
            if line_index == 0 and y > 72.0:
                y += _SKIP - _LEADING
            page.insert_text((_MARGIN_X, y), line, fontsize=_BODY_SIZE)
            # Raised 7pt marker on the second line of every paragraph, the
            # shape that inflated bbox-top gaps on the real paper. It must sit
            # flush against the prose so MuPDF groups it into the SAME line;
            # a distant marker becomes its own line and tests nothing.
            if line_index == 1:
                width = pymupdf.get_text_length(line, fontsize=_BODY_SIZE)
                page.insert_text(
                    (_MARGIN_X + width + 1.0, y - _MARKER_RISE), "7",
                    fontsize=_MARKER_SIZE,
                )
            y += _LEADING
    document.save(pdf)
    document.close()

    result = compare_paragraph_boundaries(pdf, _candidate(paragraphs))

    assert result.status == STATUS_CHECKED
    assert result.merged == ()


def test_line_baseline_ignores_a_superscript_in_the_same_line(tmp_path):
    """The primitive the skip detector rests on: baseline, never bbox top."""
    pdf = tmp_path / "marker.pdf"
    document = pymupdf.open()
    page = document.new_page()
    prose = "alpha beta gamma delta"
    width = pymupdf.get_text_length(prose, fontsize=_BODY_SIZE)
    page.insert_text((_MARGIN_X, 200.0), prose, fontsize=_BODY_SIZE)
    page.insert_text(
        (_MARGIN_X + width + 1.0, 200.0 - _MARKER_RISE), "7",
        fontsize=_MARKER_SIZE,
    )
    document.save(pdf)
    document.close()

    lines = load_pdf_lines(pdf)

    assert len(lines) == 1, "marker must group into the prose line to be a test"
    assert _MARKER_SIZE in lines[0].sizes
    assert _BODY_SIZE in lines[0].sizes
    assert lines[0].baseline == pytest.approx(200.0, abs=0.05)


def test_no_detectable_convention_abstains(tmp_path):
    """Too little geometry to establish a convention must not guess."""
    pdf = tmp_path / "sparse.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((_MARGIN_X, 72.0), "one two three four", fontsize=_BODY_SIZE)
    page.insert_text((_MARGIN_X, 86.0), "five six seven eight", fontsize=_BODY_SIZE)
    document.save(pdf)
    document.close()

    result = compare_paragraph_boundaries(pdf, "one two three four five six\n")

    assert result.status == STATUS_ABSTAINED
    assert result.merged == ()


def test_html_source_is_unsupported(tmp_path):
    html = tmp_path / "paper.html"
    html.write_text("<p>alpha beta gamma</p>", encoding="utf-8")

    result = compare_paragraph_boundaries(html, "alpha beta gamma\n")

    assert result.status == STATUS_UNSUPPORTED
    assert result.merged == ()


def test_unreadable_source_abstains(tmp_path):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not a pdf at all")

    result = compare_paragraph_boundaries(broken, "alpha beta gamma\n")

    assert result.status == STATUS_ABSTAINED


def test_code_and_headings_are_not_prose_paragraphs(tmp_path):
    pdf = tmp_path / "indent.pdf"
    paragraphs = _all_paragraphs()
    _write_pdf(pdf, paragraphs, indent=True)
    candidate = (
        "---\ntitle: \"T\"\n---\n\n"
        "## A heading\n\n"
        "```cpp\nint main() { return 0; }\n```\n\n"
        "- a list item that is long enough to pass the word floor easily\n\n"
        + _candidate(paragraphs)
    )

    result = compare_paragraph_boundaries(pdf, candidate)

    assert result.analysed == _PARAGRAPHS
    assert result.merged == ()
