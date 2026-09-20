#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for source-unit extraction and lane-local risk routing."""

from __future__ import annotations

import pymupdf
from whisker.llm.constants import (
    MAX_UNIT_CHECKS,
    PDF_MISSING_CODE_TOKEN_THRESHOLD,
)
from whisker.llm.html_outline import (
    extract_heading_outline,
    extract_section_units,
)
from whisker.llm.source_router import (
    route_html_units,
    route_pdf_units,
)
from whisker.llm.textlayer import PageUnit, extract_page_units

# Twelve distinct C++ keyword hits: above PDF_MISSING_CODE_TOKEN_THRESHOLD,
# one each so token_delta (deficit >= 5 of one token) stays quiet.
_FLAT_CODE_TOKENS = (
    "constexpr template struct class enum auto "
    "concept requires noexcept void int float"
)


def _long_text(prefix: str, count: int = 60) -> str:
    return " ".join(f"{prefix}{index}" for index in range(count))


def _flat_code_page(
    *,
    page: int = 4,
    code_token_count: int = 12,
) -> PageUnit:
    return PageUnit(
        page=page,
        text=_FLAT_CODE_TOKENS,
        heading_candidates=[],
        has_images=False,
        has_tables=False,
        caption_lines=[],
        code_token_count=code_token_count,
        content_tokens=12,
    )


def test_pdf_page_units_from_simple_pdf(tmp_path):
    pdf_path = tmp_path / "units.pdf"
    document = pymupdf.open()
    first = document.new_page()
    first.insert_text((72, 72), "Large Heading", fontsize=20)
    first.insert_textbox(
        pymupdf.Rect(72, 100, 540, 300),
        _long_text("alpha"),
        fontsize=11,
    )
    first.insert_text((72, 320), "Figure 1: Example layout", fontsize=11)
    second = document.new_page()
    second.insert_text((72, 72), "Second Heading", fontsize=20)
    second.insert_text((72, 110), "constexpr template struct class", fontsize=11)
    second.insert_text((72, 140), "Table 1: Results", fontsize=11)
    document.save(pdf_path)
    document.close()

    units = extract_page_units(pdf_path)

    assert [unit.page for unit in units] == [1, 2]
    assert "Large Heading" in units[0].text
    assert ("Large Heading", 20.0) in units[0].heading_candidates
    assert units[0].has_images is False
    assert units[0].has_tables is False
    assert units[0].caption_lines == ["Figure 1: Example layout"]
    assert units[0].content_tokens >= 60
    assert units[1].has_tables is True
    assert units[1].caption_lines == ["Table 1: Results"]
    assert units[1].code_token_count == 4


def test_html_section_units_from_fixture():
    html = """
    <h1>Paper title</h1><p>Opening sentence, with punctuation!</p>
    <h2>Design</h2><p>Detailed design.</p><pre>constexpr int value = 1;</pre>
    <h3>Results</h3><table><tr><td>Pass</td></tr></table><img src="plot.png">
    """

    units = extract_section_units(html)

    assert [(unit.section_id, unit.tag, unit.title) for unit in units] == [
        (0, "h1", "Paper title"),
        (1, "h2", "Design"),
        (2, "h3", "Results"),
    ]
    assert units[0].text == "Opening sentence, with punctuation!"
    assert units[1].code_blocks == 1
    assert units[2].has_tables is True
    assert units[2].has_images is True


def test_route_pdf_low_recall():
    unit = PageUnit(
        page=1,
        text=_long_text("missing"),
        heading_candidates=[],
        has_images=False,
        has_tables=False,
        caption_lines=[],
        code_token_count=0,
        content_tokens=60,
    )

    signals = route_pdf_units([unit], "# Unrelated\n\nNothing from the source.")

    assert any(signal.signal_type == "low_recall" for signal in signals)


def test_route_pdf_token_delta():
    source = " ".join(["constexpr"] * 10 + ["filler"] * 50)
    unit = PageUnit(
        page=3,
        text=source,
        heading_candidates=[],
        has_images=False,
        has_tables=False,
        caption_lines=[],
        code_token_count=10,
        content_tokens=60,
    )

    signals = route_pdf_units([unit], "constexpr constexpr " + _long_text("filler"))

    assert any(
        signal.signal_type == "token_delta"
        and "constexpr" in signal.detail
        and "source document has 10" in signal.detail
        for signal in signals
    )


def test_route_pdf_token_delta_is_document_wide():
    units = [
        PageUnit(
            page=index,
            text=" ".join(["constexpr"] * 4 + [f"page{index}word"] * 56),
            heading_candidates=[],
            has_images=False,
            has_tables=False,
            caption_lines=[],
            code_token_count=4,
            content_tokens=60,
        )
        for index in range(1, 4)
    ]
    candidate = " ".join(["constexpr"] * 3)

    signals = route_pdf_units(units, candidate)

    token_signal = next(
        signal for signal in signals
        if signal.signal_type == "token_delta" and "constexpr" in signal.detail
    )
    assert token_signal.unit_id == "page:1"
    assert "source document has 12" in token_signal.detail
    assert "candidate has 3, delta 9" in token_signal.detail


def test_route_pdf_missing_caption():
    text = _long_text("body") + "\nFigure 7: Important architecture"
    unit = PageUnit(
        page=2,
        text=text,
        heading_candidates=[],
        has_images=True,
        has_tables=False,
        caption_lines=["Figure 7: Important architecture"],
        code_token_count=0,
        content_tokens=64,
    )

    signals = route_pdf_units([unit], _long_text("body"))

    assert any(signal.signal_type == "missing_captions" for signal in signals)


def test_route_pdf_numbered_heading_is_not_drift():
    """A numbered source heading present in the candidate is not drift.

    Regression: source titles were secno-stripped before comparison but
    candidate keys were not, so "1 History" keyed as "history" on one side and
    "1history" on the other and every numbered heading reported as missing.
    """
    unit = PageUnit(
        page=1,
        text=_long_text("body"),
        heading_candidates=[("1 History", 14.0), ("1.1 Changes from P0000R0", 12.0)],
        has_images=False,
        has_tables=False,
        caption_lines=[],
        code_token_count=0,
        content_tokens=64,
    )

    signals = route_pdf_units(
        [unit],
        "## 1 History\n\n### 1.1 Changes from P0000R0\n\n" + _long_text("body"),
    )

    assert [s for s in signals if s.signal_type == "heading_drift"] == []


def test_route_pdf_absent_heading_still_drifts():
    """The fix must not blind the signal: a genuinely dropped heading flags."""
    unit = PageUnit(
        page=1,
        text=_long_text("body"),
        heading_candidates=[("2 Motivation", 14.0)],
        has_images=False,
        has_tables=False,
        caption_lines=[],
        code_token_count=0,
        content_tokens=64,
    )

    signals = route_pdf_units([unit], "## Something Else\n\n" + _long_text("body"))

    assert any(s.signal_type == "heading_drift" for s in signals)


def test_route_html_heading_drift():
    html = "<h2>Design</h2><p>" + _long_text("design") + "</p>"
    units = extract_section_units(html)

    signals = route_html_units(
        units,
        "### Design\n\n" + _long_text("design"),
        extract_heading_outline(html),
    )

    assert any(signal.signal_type == "heading_drift" for signal in signals)


def test_route_html_clean_passes():
    html = (
        "<h2>Design</h2><p>"
        + _long_text("design")
        + "</p><pre>constexpr int answer = 42;</pre>"
    )
    candidate = (
        "## Design\n\n"
        + _long_text("design")
        + "\n\n```cpp\nconstexpr int answer = 42;\n```\n"
    )

    assert route_html_units(
        extract_section_units(html),
        candidate,
        extract_heading_outline(html),
    ) == []


def test_route_html_ignores_stripped_source_toc_sections():
    for toc_title in ("Contents", "Table of Contents"):
        html = (
            f"<h2>{toc_title}</h2><ol><li>"
            + _long_text("toc")
            + "</li></ol><h2>Design</h2><p>"
            + _long_text("design")
            + "</p>"
        )
        candidate = "## Design\n\n" + _long_text("design")

        assert route_html_units(
            extract_section_units(html),
            candidate,
            extract_heading_outline(html),
        ) == []


def test_route_html_matches_duplicate_heading_occurrences_for_code():
    html = (
        "<h2>Example</h2><p>First occurrence.</p>"
        "<pre><code>constexpr int first = 1;</code></pre>"
        "<h2>Example</h2><p>Second occurrence.</p>"
        "<pre><code>constexpr int second = 2;</code></pre>"
    )
    candidate = (
        "## Example\n\nFirst occurrence.\n\n"
        "```cpp\nconstexpr int first = 1;\n```\n\n"
        "## Example\n\nSecond occurrence.\n"
    )

    signals = route_html_units(
        extract_section_units(html),
        candidate,
        extract_heading_outline(html),
    )

    assert [
        (signal.unit_id, signal.signal_type)
        for signal in signals
        if signal.signal_type == "missing_code"
    ] == [("section:1", "missing_code")]


def test_route_html_does_not_count_pre_text_inside_fence():
    html = (
        "<h2>Example</h2>"
        "<pre>constexpr int first = 1;</pre>"
        "<pre>constexpr int second = 2;</pre>"
    )
    candidate = (
        "## Example\n\n"
        "```html\n"
        "<pre>constexpr int first = 1;</pre>\n"
        "```\n"
    )

    signals = route_html_units(
        extract_section_units(html),
        candidate,
        extract_heading_outline(html),
    )

    assert [
        signal.signal_type for signal in signals
        if signal.signal_type == "missing_code"
    ] == ["missing_code"]
    assert "candidate section has 1" in signals[0].detail


def test_route_html_counts_pre_outside_fence():
    html = (
        "<h2>Example</h2>"
        "<pre>constexpr int first = 1;</pre>"
        "<pre>constexpr int second = 2;</pre>"
    )
    candidate = (
        "## Example\n\n"
        "```html\n"
        "<pre>literal example</pre>\n"
        "```\n\n"
        "<pre>constexpr int second = 2;</pre>\n"
    )

    assert route_html_units(
        extract_section_units(html),
        candidate,
        extract_heading_outline(html),
    ) == []


def test_route_pdf_clean_passes():
    text = "Architecture\n" + _long_text("body") + "\nFigure 1: Overview"
    unit = PageUnit(
        page=1,
        text=text,
        heading_candidates=[("Architecture", 20.0)],
        has_images=True,
        has_tables=False,
        caption_lines=["Figure 1: Overview"],
        code_token_count=0,
        content_tokens=64,
    )
    candidate = "## Architecture\n\n" + _long_text("body") + "\n\nFigure 1: Overview"

    assert route_pdf_units([unit], candidate) == []


def test_route_pdf_missing_code_no_fences():
    unit = _flat_code_page()

    signals = route_pdf_units([unit], "prose with no listings")

    missing = [s for s in signals if s.signal_type == "missing_code"]
    assert len(missing) == 1
    assert missing[0].severity == "high"
    assert missing[0].unit_id == "page:4"
    assert "page has 12 code-token hits" in missing[0].detail
    assert "candidate fences cover 0" in missing[0].detail


def test_route_pdf_missing_code_fences_cover_tokens():
    unit = _flat_code_page()
    candidate = f"```cpp\n{_FLAT_CODE_TOKENS}\n```\n"

    signals = route_pdf_units([unit], candidate)

    assert [s for s in signals if s.signal_type == "missing_code"] == []


def test_route_pdf_missing_code_below_threshold():
    unit = _flat_code_page(
        code_token_count=PDF_MISSING_CODE_TOKEN_THRESHOLD - 1,
    )

    signals = route_pdf_units([unit], "prose with no listings")

    assert [s for s in signals if s.signal_type == "missing_code"] == []


def test_route_pdf_missing_code_tokens_outside_fences():
    unit = _flat_code_page()

    signals = route_pdf_units([unit], _FLAT_CODE_TOKENS)

    missing = [s for s in signals if s.signal_type == "missing_code"]
    assert len(missing) == 1
    assert missing[0].severity == "high"
    assert missing[0].unit_id == "page:4"


def test_route_pdf_missing_code_other_page_fences_do_not_cover():
    """Keyword types in some other fence must not hide a flattened listing."""
    unit = _flat_code_page()
    candidate = (
        "```cpp\nint main() { return void_cast(0); }\n```\n\n"
        + _FLAT_CODE_TOKENS
    )

    signals = route_pdf_units([unit], candidate)

    missing = [s for s in signals if s.signal_type == "missing_code"]
    assert len(missing) == 1
    assert missing[0].unit_id == "page:4"


def test_router_preserves_signals_beyond_unit_check_capacity():
    units = [
        PageUnit(
            page=index,
            text=_long_text(f"page{index}-"),
            heading_candidates=[],
            has_images=False,
            has_tables=False,
            caption_lines=[],
            code_token_count=0,
            content_tokens=60,
        )
        for index in range(1, MAX_UNIT_CHECKS + 3)
    ]

    signals = route_pdf_units(units, "")

    assert len(signals) > MAX_UNIT_CHECKS
    assert [signal.unit_id for signal in signals] == [
        f"page:{index}" for index in range(1, MAX_UNIT_CHECKS + 3)
    ]
