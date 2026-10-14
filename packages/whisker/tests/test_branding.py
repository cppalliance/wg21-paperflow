#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the shared report theme.

The point of these is that a generated PDF silently losing its logo or its brand
colours is exactly the kind of regression nobody notices until a report is
already in front of the team.
"""

from __future__ import annotations

from whisker.branding import (
    CSS_PATH,
    LOGO_PATH,
    REFERENCE_PDF,
    ReportMeta,
    logo_data_uri,
    render_branded_html,
    split_front_block,
    stylesheet,
    wrap_document,
)

BRAND_RED = "#a81c21"
CODE_RED = "#aa3344"


class TestAssets:
    def test_assets_exist(self):
        assert CSS_PATH.is_file()
        assert LOGO_PATH.is_file()

    def test_layout_reference_is_preserved(self):
        """The design contract must ship with the theme it defines."""
        assert REFERENCE_PDF.is_file()
        assert REFERENCE_PDF.read_bytes()[:5] == b"%PDF-"

    def test_logo_is_a_png(self):
        assert LOGO_PATH.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    def test_stylesheet_declares_brand_palette(self):
        css = stylesheet()
        assert BRAND_RED in css
        assert CODE_RED in css

    def test_logo_data_uri_is_self_contained(self):
        uri = logo_data_uri()
        assert uri.startswith("data:image/png;base64,")
        assert len(uri) > 1000


class TestFrontBlock:
    def test_extracts_title_and_fields(self):
        title, body, fields = split_front_block(
            "# My Report\n"
            "**Date:** 2 August 2026\n"
            "**Corpus:** v2\n"
            "\n"
            "## Section\n"
            "Body text.\n"
        )
        assert title == "My Report"
        assert fields == (("Date", "2 August 2026"), ("Corpus", "v2"))
        assert body.lstrip().startswith("## Section")

    def test_body_without_metadata_is_untouched(self):
        title, body, fields = split_front_block("# Title\n\nJust prose.\n")
        assert title == "Title"
        assert fields == ()
        assert "Just prose." in body

    def test_missing_title_is_tolerated(self):
        title, body, fields = split_front_block("Some prose with no heading.\n")
        assert title == ""
        assert fields == ()
        assert "Some prose" in body


class TestDocumentShell:
    def test_document_embeds_logo_and_title(self):
        html = wrap_document("<p>x</p>", ReportMeta(title="Benchmark"))
        assert "data:image/png;base64," in html
        assert "Benchmark" in html
        assert "report-masthead" in html

    def test_title_is_escaped(self):
        html = wrap_document("<p>x</p>", ReportMeta(title="a <script> & b"))
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_landscape_sets_page_orientation(self):
        portrait = wrap_document("<p>x</p>", ReportMeta(title="t"))
        landscape = wrap_document("<p>x</p>", ReportMeta(title="t"), landscape=True)
        assert "A4 landscape" not in portrait
        assert "A4 landscape" in landscape

    def test_metadata_values_render_inline_code(self):
        html = wrap_document(
            "<p>x</p>",
            ReportMeta(title="t", fields=(("tomd", "commit `0d18a65b`"),)),
        )
        assert "<code>0d18a65b</code>" in html
        assert "`" not in html.split("report-meta")[1][:200]


class TestMarkdownRendering:
    def test_tables_are_rendered(self):
        html = render_branded_html(
            "# T\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"
        )
        assert "<table>" in html
        assert "<th>" in html

    def test_title_is_not_duplicated_in_body(self):
        html = render_branded_html("# Unique Title\n\nProse.\n")
        assert html.count("Unique Title") == 2  # <title> and masthead h1

    def test_document_is_self_contained(self):
        html = render_branded_html("# T\n\nProse with `code`.\n")
        assert "<style>" in html
        assert 'link rel="stylesheet"' not in html
        assert "<code>code</code>" in html
