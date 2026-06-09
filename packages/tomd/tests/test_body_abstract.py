# Copyright (c) 2026 C++ Alliance, Inc. (https://cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Unit tests for body/abstract.py functions."""

from conftest import make_section
from tomd.lib.pdf.types import SectionKind
from tomd.lib.body.abstract import (
    dedup_abstract,
    promote_abstract_from_uncertain,
    reorder_abstract_in_uncertain,
    strip_metadata_from_uncertain,
)


class TestDedupAbstract:
    """Tests for dedup_abstract: removes duplicate Abstract headings."""

    def test_single_abstract_unchanged(self):
        sections = [
            make_section("Abstract", kind=SectionKind.HEADING),
            make_section("This is the abstract body."),
        ]
        dedup_abstract(sections)
        assert len(sections) == 2

    def test_no_abstract_unchanged(self):
        sections = [
            make_section("Introduction", kind=SectionKind.HEADING),
            make_section("Some text."),
        ]
        dedup_abstract(sections)
        assert len(sections) == 2

    def test_duplicate_keeps_one_with_body(self):
        sections = [
            make_section("Abstract", kind=SectionKind.HEADING),
            make_section("Introduction", kind=SectionKind.HEADING),
            make_section("Abstract", kind=SectionKind.HEADING),
            make_section("Real abstract body text here."),
        ]
        dedup_abstract(sections)
        abstract_count = sum(
            1 for s in sections
            if s.kind == SectionKind.HEADING
            and s.text.strip().lower() == "abstract"
        )
        assert abstract_count == 1
        assert any("Real abstract" in s.text for s in sections)

    def test_two_empty_abstracts_keeps_first(self):
        sections = [
            make_section("Abstract", kind=SectionKind.HEADING),
            make_section("Abstract", kind=SectionKind.HEADING),
            make_section("Introduction", kind=SectionKind.HEADING),
        ]
        dedup_abstract(sections)
        abstract_count = sum(
            1 for s in sections
            if s.kind == SectionKind.HEADING
            and s.text.strip().lower() == "abstract"
        )
        assert abstract_count == 1

    def test_empty_sections_list(self):
        sections = []
        dedup_abstract(sections)
        assert sections == []


class TestPromoteAbstractFromUncertain:
    """Tests for promote_abstract_from_uncertain."""

    def test_promotes_abstract_from_uncertain_section(self):
        sections = [
            make_section(
                "Abstract\nThis is a long enough abstract body with more than "
                "ten words to pass the minimum word count threshold.",
                kind=SectionKind.UNCERTAIN, page_num=0,
            ),
        ]
        promote_abstract_from_uncertain(sections)
        kinds = [s.kind for s in sections]
        assert SectionKind.HEADING in kinds

    def test_skips_when_content_heading_exists_on_page0(self):
        sections = [
            make_section("1. Introduction", kind=SectionKind.HEADING, page_num=0),
            make_section(
                "Abstract\nThis is a long enough abstract body with more than "
                "ten words to pass the minimum word count.",
                kind=SectionKind.UNCERTAIN, page_num=0,
            ),
        ]
        original_len = len(sections)
        promote_abstract_from_uncertain(sections)
        assert len(sections) == original_len

    def test_skips_short_abstract_body(self):
        sections = [
            make_section(
                "Abstract\nToo short.",
                kind=SectionKind.UNCERTAIN, page_num=0,
            ),
        ]
        promote_abstract_from_uncertain(sections)
        assert all(s.kind != SectionKind.HEADING for s in sections)

    def test_skips_non_page0(self):
        sections = [
            make_section(
                "Abstract\nThis is a long enough abstract body with more than "
                "ten words to pass the minimum word count threshold.",
                kind=SectionKind.UNCERTAIN, page_num=1,
            ),
        ]
        promote_abstract_from_uncertain(sections)
        assert all(s.kind == SectionKind.UNCERTAIN for s in sections)


class TestStripMetadataFromUncertain:
    """Tests for strip_metadata_from_uncertain."""

    def test_removes_metadata_echo_lines(self):
        metadata = {
            "title": "My Paper",
            "document": "P1234R0",
            "reply-to": ["Author Name"],
        }
        sections = [
            make_section(
                "Document: P1234R0\nDate: 2026-01-01\nActual content here.",
                kind=SectionKind.UNCERTAIN, page_num=0,
            ),
        ]
        strip_metadata_from_uncertain(sections, metadata)
        remaining_text = " ".join(s.text for s in sections)
        assert "Actual content" in remaining_text

    def test_skips_non_uncertain(self):
        metadata = {"title": "Test", "document": "P0001R0"}
        sections = [
            make_section("Document: P0001R0", kind=SectionKind.PARAGRAPH),
        ]
        original_text = sections[0].text
        strip_metadata_from_uncertain(sections, metadata)
        assert sections[0].text == original_text


class TestReorderAbstractInUncertain:
    """Tests for reorder_abstract_in_uncertain."""

    def test_empty_sections(self):
        sections = []
        reorder_abstract_in_uncertain(sections)
        assert sections == []

    def test_no_uncertain_unchanged(self):
        sections = [
            make_section("Introduction", kind=SectionKind.HEADING),
            make_section("Some text."),
        ]
        original = list(sections)
        reorder_abstract_in_uncertain(sections)
        assert len(sections) == len(original)
