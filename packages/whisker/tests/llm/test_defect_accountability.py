#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Accountability tests: one test per defect contract class.

Each test plants a known defect and asserts it produces the correct signal
through the deterministic pipeline. Breaks the green-CI-at-recall-0 loop.
"""

from __future__ import annotations

from whisker.llm.html_outline import (
    extract_heading_outline,
    extract_heading_outline_normalized,
    extract_section_units,
    normalize_heading_text,
)
from whisker.llm.source_router import (
    normalize_heading_text as router_normalize,
)
from whisker.llm.source_router import (
    route_html_units,
    route_pdf_units,
)
from whisker.llm.table_compare import parse_markdown_tables
from whisker.llm.textlayer import PageUnit


class TestHeadingLabelRetained:
    """Contract: structural heading labels (secno) must be stripped."""

    def test_normalize_strips_decimal_label(self):
        assert normalize_heading_text("1. Introduction") == "Introduction"

    def test_normalize_strips_multi_level_label(self):
        assert normalize_heading_text("1.2.3 Details") == "Details"

    def test_normalize_strips_roman_label(self):
        assert normalize_heading_text("IV. Results") == "Results"
        assert router_normalize("IV. Results") == "Results"

    def test_normalize_strips_alpha_label(self):
        assert normalize_heading_text("A. Appendix") == "Appendix"
        assert router_normalize("A. Appendix") == "Appendix"

    def test_normalize_preserves_semantic_number(self):
        assert normalize_heading_text("C++ 26") == "C++ 26"

    def test_secno_stripped_from_html_outline(self):
        """extract_heading_outline_normalized strips span.secno text."""
        html = '<h2><span class="secno">1. </span>Abstract</h2>'
        raw = extract_heading_outline(html)
        normalized = extract_heading_outline_normalized(html)
        assert raw[0][1] == "1. Abstract"
        assert normalized[0][1] == "Abstract"

    def test_secno_heading_no_false_drift(self):
        """After normalization, source secno headings match candidate headings."""
        html = (
            '<h2><span class="secno">1. </span>Scope</h2>'
            '<h2><span class="secno">2. </span>Design</h2>'
            '<p>body text here for recall</p>'
        )
        sections = extract_section_units(html)
        outline = extract_heading_outline(html)
        candidate_md = "## Scope\n\ntext\n\n## Design\n\ntext\n"
        signals = route_html_units(sections, candidate_md, outline)
        heading_drift = [s for s in signals if s.signal_type == "heading_drift"]
        assert len(heading_drift) == 0, (
            f"Expected no heading_drift after normalization, got {heading_drift}"
        )


class TestTableCorruption:
    """Contract: table cell content mismatches must be detected."""

    def test_sf_truncation_detectable_in_markdown(self):
        """SF -> S truncation is detectable via markdown table parsing."""
        source_header = ["SF", "F", "N", "A", "SA"]
        candidate_md = "| S | F | N | A | SA |\n|---|---|---|---|---|\n"
        tables = parse_markdown_tables(candidate_md)
        assert len(tables) >= 1
        assert tables[0][0][0].strip() == "S"
        assert source_header[0] == "SF"
        assert tables[0][0][0].strip() != source_header[0]

    def test_table_presence_produces_signal(self):
        """Pages with tables get a table_presence risk signal."""
        page = PageUnit(
            page=8,
            text="Poll: SF F N A SA content here",
            heading_candidates=[],
            has_images=False,
            has_tables=True,
            caption_lines=[],
            code_token_count=0,
            content_tokens=10,
        )
        signals = route_pdf_units([page], "# Paper\n\nOther text.\n")
        table_signals = [s for s in signals if s.signal_type == "table_presence"]
        assert len(table_signals) == 1
        assert table_signals[0].severity == "high"
        assert table_signals[0].unit_id == "page:8"


class TestTokenDelta:
    """Contract: significant keyword count deltas must be detected."""

    def test_constexpr_omission_detected(self):
        source_text = " ".join(["constexpr"] * 20 + ["int", "foo"])
        page = PageUnit(
            page=1,
            text=source_text,
            heading_candidates=[],
            has_images=False,
            has_tables=False,
            caption_lines=[],
            code_token_count=20,
            content_tokens=22,
        )
        candidate_md = "# Paper\n\nconstexpr int foo\n"
        signals = route_pdf_units([page], candidate_md)
        token_signals = [s for s in signals if s.signal_type == "token_delta"]
        assert len(token_signals) >= 1
        assert "constexpr" in token_signals[0].detail


class TestLowRecall:
    """Contract: missing page content must produce a low_recall signal."""

    def test_missing_page_flagged(self):
        page = PageUnit(
            page=13,
            text=(
                "This page has completely unique content that does not "
                "appear anywhere else in the document at all whatsoever "
                "none of these words match the candidate"
            ),
            heading_candidates=[],
            has_images=False,
            has_tables=False,
            caption_lines=[],
            code_token_count=0,
            content_tokens=50,
        )
        candidate_md = "# Paper\n\nCompletely different unrelated text.\n"
        signals = route_pdf_units([page], candidate_md)
        recall_signals = [s for s in signals if s.signal_type == "low_recall"]
        assert len(recall_signals) >= 1
        assert recall_signals[0].severity == "high"
        assert recall_signals[0].unit_id == "page:13"


class TestScriptExclusion:
    """Contract: script/style content must not enter section text."""

    def test_script_excluded(self):
        html = (
            "<h2>Title</h2>"
            "<p>Real content here.</p>"
            '<script>var x = "malicious";</script>'
            "<p>More real content.</p>"
        )
        sections = extract_section_units(html)
        assert len(sections) >= 1
        assert "malicious" not in sections[0].text
        assert "Real content" in sections[0].text

    def test_style_excluded(self):
        html = (
            "<h2>Title</h2>"
            "<p>Good text.</p>"
            "<style>.hidden { display: none; }</style>"
        )
        sections = extract_section_units(html)
        assert len(sections) >= 1
        assert "hidden" not in sections[0].text
        assert "Good text" in sections[0].text


class TestNumericSort:
    """Contract: unit IDs sort numerically, not lexically."""

    def test_page_13_before_page_2_fixed(self):
        """Numeric sort prevents page:13 from sorting before page:2."""
        from whisker.llm.unit_judge import _unit_id_sort_key

        ids = ["page:1", "page:13", "page:2", "page:3", "page:9"]
        sorted_ids = sorted(ids, key=_unit_id_sort_key)
        assert sorted_ids == [
            "page:1", "page:2", "page:3", "page:9", "page:13"
        ]
