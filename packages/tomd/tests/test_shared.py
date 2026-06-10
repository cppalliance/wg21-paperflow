#
# Copyright (c) 2026 Greg Kaleka (greg@gregkaleka.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Tests for lib.shared helpers (issue04)."""

from __future__ import annotations

from pathlib import Path

from tomd.lib.shared import apply_strip_leading_h1, override_revision_from_filename


class TestApplyStripLeadingH1:
    def test_strips_matching_h1_after_front_matter(self):
        md = (
            "---\n"
            'title: "My Paper"\n'
            "---\n"
            "# My Paper\n"
            "\n"
            "Body text.\n"
        )
        result = apply_strip_leading_h1(md, "My Paper")
        assert "# My Paper" not in result
        assert "Body text." in result

    def test_no_front_matter_is_noop(self):
        md = "# Title\n\nBody.\n"
        assert apply_strip_leading_h1(md, "Title") == md

    def test_mismatched_title_h1_not_stripped(self):
        md = (
            "---\n"
            'title: "Real Title"\n'
            "---\n"
            "# Different Heading\n"
            "\n"
            "Body.\n"
        )
        result = apply_strip_leading_h1(md, "Real Title")
        assert "# Different Heading" in result

    def test_embedded_dashes_in_front_matter_value(self):
        md = (
            "---\n"
            'title: "Before --- After"\n'
            "document: P1234R1\n"
            "---\n"
            "# Before --- After\n"
            "\n"
            "Body.\n"
        )
        result = apply_strip_leading_h1(md, "Before --- After")
        assert "# Before --- After" not in result
        assert "Body." in result


class TestOverrideRevisionFromFilename:
    def test_revision_mismatch_updates_document(self):
        metadata = {"document": "P1234R0"}
        path = Path("p1234r3.pdf")
        override_revision_from_filename(metadata, path)
        assert metadata["document"] == "P1234R3"

    def test_d_prefix_left_alone(self):
        metadata = {"document": "D1234R0"}
        path = Path("p1234r3.pdf")
        override_revision_from_filename(metadata, path)
        assert metadata["document"] == "D1234R0"

    def test_base_number_mismatch_left_alone(self):
        metadata = {"document": "P1234R0"}
        path = Path("p5678r3.pdf")
        override_revision_from_filename(metadata, path)
        assert metadata["document"] == "P1234R0"
