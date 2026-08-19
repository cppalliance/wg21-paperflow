# Copyright (c) 2026 C++ Alliance, Inc. (https://cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Unit tests for metadata_yaml strip and format modules."""

from conftest import make_section
from tomd.lib.pdf.types import SectionKind
from tomd.lib.metadata_yaml.strip import (
    _matches_author_name,
    _is_content_heading,
    strip_metadata_headings,
    strip_pre_heading_fragments,
    strip_pre_content_paragraphs,
)
from tomd.lib.metadata_yaml.extract import extract_metadata
from tomd.lib.metadata_yaml.format import (
    format_front_matter,
    sanitize_metadata,
)


class TestMatchesAuthorName:

    def test_single_matching_name(self):
        assert _matches_author_name("John Smith", {"john", "smith"})

    def test_no_match(self):
        assert not _matches_author_name("Jane Doe", {"john", "smith"})

    def test_comma_rejects(self):
        assert not _matches_author_name("Smith, John", {"john", "smith"})

    def test_email_in_text_stripped(self):
        assert _matches_author_name(
            "John Smith john@example.com", {"john", "smith"})

    def test_short_tokens_ignored(self):
        assert not _matches_author_name("Jo", {"jo"})

    def test_partial_match_sufficient(self):
        assert _matches_author_name("John W Smith", {"john", "smith"})


class TestIsContentHeading:

    def test_numbered_heading(self):
        sec = make_section("1. Introduction", kind=SectionKind.HEADING)
        assert _is_content_heading(sec)

    def test_known_section_name(self):
        sec = make_section("Abstract", kind=SectionKind.HEADING)
        assert _is_content_heading(sec)

    def test_unknown_heading(self):
        sec = make_section("Random Title", kind=SectionKind.HEADING)
        assert not _is_content_heading(sec)

    def test_paragraph_rejected(self):
        sec = make_section("1. Introduction", kind=SectionKind.PARAGRAPH)
        assert not _is_content_heading(sec)

    def test_empty_text(self):
        sec = make_section("", kind=SectionKind.HEADING)
        assert not _is_content_heading(sec)

    def test_deep_numbered_heading(self):
        sec = make_section("1.2.3 Details", kind=SectionKind.HEADING)
        assert _is_content_heading(sec)


class TestStripMetadataHeadings:

    def test_removes_doc_number_heading(self):
        metadata = {"document": "P1234R0", "title": "Test Paper"}
        sections = [
            make_section("Doc. No.: P1234R0", kind=SectionKind.HEADING,
                         page_num=0),
            make_section("1. Introduction", kind=SectionKind.HEADING,
                         page_num=0),
            make_section("Body text."),
        ]
        n = strip_metadata_headings(sections, metadata)
        assert n >= 1
        assert not any("Doc. No." in s.text for s in sections)

    def test_preserves_content_headings(self):
        metadata = {"document": "P1234R0", "title": "Test"}
        sections = [
            make_section("1. Introduction", kind=SectionKind.HEADING,
                         page_num=0),
            make_section("Body text."),
        ]
        strip_metadata_headings(sections, metadata)
        assert any("Introduction" in s.text for s in sections)

    def test_empty_metadata(self):
        sections = [
            make_section("Something", kind=SectionKind.HEADING, page_num=0),
        ]
        n = strip_metadata_headings(sections, {})
        assert n == 0


class TestStripPreHeadingFragments:

    def test_strips_pre_heading_paragraphs(self):
        sections = [
            make_section("P1234R0", page_num=0),
            make_section("Author Name", page_num=0),
            make_section("1. Introduction", kind=SectionKind.HEADING,
                         page_num=0),
            make_section("Body text."),
        ]
        n = strip_pre_heading_fragments(sections)
        assert n == 2
        assert sections[0].kind == SectionKind.HEADING

    def test_no_heading_no_strip(self):
        sections = [
            make_section("Just text.", page_num=0),
        ]
        n = strip_pre_heading_fragments(sections)
        assert n == 0

    def test_heading_first_no_strip(self):
        sections = [
            make_section("Title", kind=SectionKind.HEADING, page_num=0),
            make_section("Body."),
        ]
        n = strip_pre_heading_fragments(sections)
        assert n == 0


class TestStripPreContentParagraphs:

    def test_strips_metadata_paragraphs_before_content(self):
        sections = [
            make_section("P1234R0", page_num=0),
            make_section("2026-01-15", page_num=0),
            make_section("1. Introduction", kind=SectionKind.HEADING,
                         page_num=0),
            make_section("Body text."),
        ]
        n = strip_pre_content_paragraphs(sections)
        assert n == 2

    def test_no_content_heading_no_strip(self):
        sections = [
            make_section("Random text", page_num=0),
            make_section("More text", page_num=0),
        ]
        n = strip_pre_content_paragraphs(sections)
        assert n == 0

    def test_unlabeled_abstract_not_stripped_when_content_heading_far(self):
        """Body prose before a distant content heading must survive (p3889r0).

        The only KNOWN_SECTIONS heading ("Summary") sits at the document end,
        so the metadata/body boundary cannot be "everything before it": the
        leading short metadata is stripped, but the abstract prose is kept.
        """
        abstract = ("P2900 claims to be a minimum viable product, but is that "
                    "true? This does not sound like one at all.")
        sections = [
            make_section("Harald Achitz harald@swedencpp.se", page_num=0),
            make_section("2026-01-15", page_num=0),
            make_section(abstract, page_num=0),
            make_section("More abstract prose continuing the argument here.",
                         page_num=0),
            make_section("Summary", kind=SectionKind.HEADING, page_num=2),
            make_section("Closing body."),
        ]
        n = strip_pre_content_paragraphs(sections)
        assert n == 2  # author + date only
        assert any(abstract in s.text for s in sections)

    def test_long_multi_author_replyto_is_stripped(self):
        """A long Reply-to line (multi-author + emails) is metadata, not body.

        Word count alone would misread it as prose; the email/field-label shape
        keeps it in the metadata run so it does not leak into the body.
        """
        replyto = ("Reply-to: Vinnie Falco vinnie@x.org Steve Gerbino "
                   "steve@x.org Michael Vandeberg michael@x.org Proposal Team")
        sections = [
            make_section("P1234R0", page_num=0),
            make_section(replyto, page_num=0),
            make_section("Abstract", kind=SectionKind.HEADING, page_num=0),
            make_section("Real body."),
        ]
        n = strip_pre_content_paragraphs(sections)
        assert n == 2
        assert not any("Reply-to" in s.text for s in sections)

    def test_body_paragraph_with_single_email_is_kept(self):
        """A long body paragraph mentioning ONE email must not be over-stripped.

        Guards against citation-collateral: a single incidental email does not
        make a sentence metadata, so the abstract survives even though a
        distant "Summary" heading is the only content heading.
        """
        body = ("This proposal was discussed on the reflector at "
                "std-proposals@lists.isocpp.org and we summarize the outcome "
                "of that long thread in the following paragraphs here.")
        sections = [
            make_section("P1234R0", page_num=0),
            make_section(body, page_num=0),
            make_section("Summary", kind=SectionKind.HEADING, page_num=2),
            make_section("Closing body."),
        ]
        n = strip_pre_content_paragraphs(sections)
        assert n == 1  # only the bare doc number
        assert any(body in s.text for s in sections)

    def test_merged_metadata_block_stripped_via_label_count(self):
        """A long merged single-line metadata block is stripped via label count.

        Exercises the >= 2 metadata-labels-anywhere path specifically: the block
        is long (so the short-paragraph path does not fire), has only ONE email
        (so the >= 2 email path does not fire), and starts with "Document #:"
        (not matched by the anchored first-line label checks). Only the
        label-count rule classifies it as metadata. Without that rule the sweep
        would break at this paragraph and leak it (n == 0).
        """
        merged = ("Document #: P9999R0 Date: 2026-01-01 Project: Programming "
                  "Language C++ Audience: LEWG Reply-to: Solo Author "
                  "<solo@example.org>")
        assert len(merged.split()) >= 12  # long: short-path must not fire
        sections = [
            make_section(merged, page_num=0),
            make_section("Summary", kind=SectionKind.HEADING, page_num=3),
            make_section("Closing body."),
        ]
        n = strip_pre_content_paragraphs(sections)
        assert n == 1
        assert not any("Reply-to" in s.text for s in sections)


class TestFormatFrontMatter:

    def test_basic_format(self):
        metadata = {
            "title": "Test Paper",
            "document": "P1234R0",
            "date": "2026-01-15",
        }
        result = format_front_matter(metadata)
        assert result.startswith("---\n")
        assert "---" in result
        assert "title:" in result
        assert "P1234R0" in result

    def test_empty_metadata_returns_empty(self):
        result = format_front_matter({})
        assert result == ""

    def test_field_order_matches_front_matter_order(self):
        metadata = {
            "date": "2026-01-15",
            "title": "Test Paper",
            "document": "P1234R0",
        }
        result = format_front_matter(metadata)
        title_pos = result.find("title:")
        doc_pos = result.find("document:")
        date_pos = result.find("date:")
        assert title_pos < doc_pos < date_pos


class TestSanitizeMetadata:

    def test_cleans_title_whitespace(self):
        metadata = {"title": "Test  Paper\n  Title"}
        result = sanitize_metadata(metadata)
        assert "\n" not in result["title"]
        assert "  " not in result["title"]

    def test_preserves_valid_fields(self):
        metadata = {"title": "Test Paper", "document": "P1234R0"}
        result = sanitize_metadata(metadata)
        assert result["title"] == "Test Paper"
        assert result["document"] == "P1234R0"


class TestMetadataZoneClose:
    """The metadata zone must close once body content starts (issue #368).

    While the zone is open, extract_metadata silently consumes all-caps
    sections of three words or fewer as category labels. P3290R4's zone was
    only ever closed by a malformed poll table whose text happened to read
    "8 | 3 | 1 | 0 | 0" and so matched SECTION_NUM_RE. Repairing the table
    removed that accident and the extractor then ate a macro name from the
    body twelve pages later.
    """

    def _sections(self, heading_text):
        return [
            make_section("Document Number: P3290R4"),
            make_section(heading_text, page_num=1),
            make_section("ASSERT_USES_CONTRACT_VIOLATION_HANDLER.", page_num=12),
        ]

    def test_numbered_heading_split_across_lines_closes_the_zone(self):
        """PDF headings arrive as "1\\nIntroduction": number on its own line."""
        _, remaining = extract_metadata(self._sections("1\nIntroduction"))
        kept = [s.text for s in remaining]
        assert "ASSERT_USES_CONTRACT_VIOLATION_HANDLER." in kept

    def test_numbered_heading_on_one_line_still_closes_the_zone(self):
        _, remaining = extract_metadata(self._sections("1 Introduction"))
        kept = [s.text for s in remaining]
        assert "ASSERT_USES_CONTRACT_VIOLATION_HANDLER." in kept

    def test_document_field_is_still_extracted(self):
        meta, _ = extract_metadata(self._sections("1\nIntroduction"))
        assert meta["document"] == "P3290R4"
