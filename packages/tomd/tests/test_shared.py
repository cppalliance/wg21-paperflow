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

import pytest

from tomd.lib.shared import (
    _strip_metadata_table,
    apply_strip_leading_h1,
    override_revision_from_filename,
    strip_heading_section_number,
    strip_leading_h1,
    strip_redundant_body_meta,
)


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

    def test_apply_strip_leading_h1_max_level_2_strips_h2(self):
        md = '---\ntitle: "My Paper"\n---\n## My Paper\n\nBody.\n'
        result = apply_strip_leading_h1(md, "My Paper", 2)
        assert "## My Paper" not in result
        assert "Body." in result


class TestEmitCleanup:
    _H1_THEN_METADATA_TABLE = (
        "---\n"
        'title: "T"\n'
        "---\n"
        "# T\n"
        "\n"
        "| Document | P1 |\n"
        "| Date | x |\n"
        "---\n"
        "Body.\n"
    )

    def test_h1_then_metadata_table_stripped_by_emit_sequence(self):
        md = self._H1_THEN_METADATA_TABLE
        md = strip_redundant_body_meta(md)
        md = apply_strip_leading_h1(md, "T")
        assert "| Document |" not in md
        assert "# T" not in md
        assert "Body." in md

    def test_h2_then_metadata_table_stripped_when_title_matches(self):
        md = (
            '---\ntitle: "My Paper"\n---\n'
            "## My Paper\n\n"
            "| Document | P0000 |\n|----------|-------|\n\n"
            "Body.\n"
        )
        out = _strip_metadata_table(md)
        assert "| Document |" not in out
        assert "## My Paper" not in out
        assert "Body." in out


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

    def test_revision_match_is_noop(self):
        metadata = {"document": "P1234R3"}
        override_revision_from_filename(metadata, Path("p1234r3.pdf"))
        assert metadata["document"] == "P1234R3"

    def test_stem_without_revision_left_alone(self):
        metadata = {"document": "P1234R0"}
        override_revision_from_filename(metadata, Path("p1234.pdf"))
        assert metadata["document"] == "P1234R0"

    def test_missing_document_key_is_noop(self):
        metadata: dict = {}
        override_revision_from_filename(metadata, Path("p1234r3.pdf"))
        assert metadata == {}


class TestStripLeadingH1:
    def test_strips_h1_title_duplicate(self):
        out = strip_leading_h1("# My Paper\n\nBody.", "My Paper")
        assert not out.lstrip().startswith("#")
        assert "Body." in out

    def test_strips_h1_first_content_when_no_title(self):
        out = strip_leading_h1("# Anything\n\nBody.", "")
        assert not out.lstrip().startswith("#")

    def test_leaves_non_matching_h1(self):
        out = strip_leading_h1("# Other\n\nBody.", "My Paper")
        assert out.lstrip().startswith("# Other")

    def test_default_does_not_strip_h2(self):
        # PDF path keeps H1-only behavior: an H2 title-dup is left alone.
        out = strip_leading_h1("## My Paper\n\nBody.", "My Paper")
        assert out.lstrip().startswith("## My Paper")

    def test_max_level_2_strips_h2_title_duplicate(self):
        # HTML path: body headings start at H2, so the title-dup arrives as H2.
        out = strip_leading_h1("## My Paper\n\nBody.", "My Paper", max_level=2)
        assert not out.lstrip().startswith("#")
        assert "Body." in out

    def test_max_level_2_leaves_deeper_heading(self):
        out = strip_leading_h1("### My Paper\n\nBody.", "My Paper", max_level=2)
        assert out.lstrip().startswith("### My Paper")


class TestStripHeadingSectionNumber:
    """Issue #301: the outline label is document structure, not the title."""

    def test_strips_plain_arabic_number(self):
        assert strip_heading_section_number("2 Revision History") == "Revision History"

    def test_strips_dotted_decimal_number(self):
        assert strip_heading_section_number("2.1.3 Details") == "Details"

    def test_strips_number_with_trailing_dot(self):
        assert strip_heading_section_number("1. Disclosure") == "Disclosure"

    def test_strips_dotted_roman_numeral(self):
        assert strip_heading_section_number("IV. Scope") == "Scope"

    def test_no_number_is_noop(self):
        assert strip_heading_section_number("Abstract") == "Abstract"

    def test_bare_number_with_no_title_is_left_alone(self):
        # No trailing content to distinguish "the number" from "the title",
        # so there is nothing safe to strip.
        assert strip_heading_section_number("3.2") == "3.2"

    @pytest.mark.parametrize("text", [
        "C compatibility",
        "LLVM codegen impact",
        "I Have a Dream",
        "D compatibility notes",
    ])
    def test_undotted_roman_letters_are_ordinary_words(self, text):
        # An outline label is only recognised as Roman/alphabetic when it
        # carries its dot. Without that, every heading whose first word is
        # built from Roman-numeral letters loses it.
        assert strip_heading_section_number(text) == text

    @pytest.mark.parametrize("text,expected", [
        ("A. Global Flags", "Global Flags"),
        ("B. Rounding Mode", "Rounding Mode"),
        ("C. Arguments with External Visibility",
         "Arguments with External Visibility"),
        ("D. Conditions for `constexpr`", "Conditions for `constexpr`"),
    ])
    def test_strips_whole_alphabetic_series(self, text, expected):
        # An A/B/C/D sub-series is stripped uniformly, however Roman-numeral
        # letters fall across it: `ideals/p0533r9.md` blesses exactly these
        # four headings label-free. Stripping only the C/D half (which are
        # Roman-numeral characters) would cut the series in two.
        assert strip_heading_section_number(text) == expected

    def test_keeps_standard_clause_reference(self):
        # A number immediately followed by a stable name is a WG21 standard
        # clause reference (which clause is being modified), not the paper's
        # own redundant outline number, and must survive into the heading text.
        text = "5.1 [lex.separate] Separate translation"
        assert strip_heading_section_number(text) == text

    def test_keeps_multi_part_clause_reference(self):
        text = "15.6.5 [[cpp.rescan]](https://wg21.link/cpp.rescan) Rescanning"
        assert strip_heading_section_number(text) == text

    def test_ordinary_markdown_link_does_not_shield_the_number(self):
        # The clause-reference exception needs a *stable name* next to the
        # number, not any bracket: a link label carries capitals and spaces.
        assert (strip_heading_section_number("2 [Some Title](url)")
                == "[Some Title](url)")

    def test_strips_number_when_stable_name_is_not_adjacent(self):
        # Adjacency is load-bearing. `10.3 modify [simd.expos.defn]` (p4012r0)
        # and `4.1 Canonical tree shape [canonical.reduce.tree]` (p4016r0)
        # number the paper's own sections, so a trailing stable name cannot
        # decide the question on text alone.
        assert (strip_heading_section_number("10.3 modify [simd.expos.defn]")
                == "modify [simd.expos.defn]")

    def test_letter_label_is_stripped_beside_a_stable_name(self):
        # Clause numbers are always decimal, so the exception is decimal-only:
        # this `C.` is p0533r9's own sub-series label, and its ideal drops it.
        text = "C. Modification to “The C standard library” [library.c]"
        assert (strip_heading_section_number(text)
                == "Modification to “The C standard library” [library.c]")

    def test_leading_date_is_not_an_outline_label(self):
        # p1122r3's revision headings; the `2020` is not followed by a space.
        text = "2020-08-28 [D1122R3] after virtual LWG meeting"
        assert strip_heading_section_number(text) == text
