#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Pure tests for the Tesseract survey adapter. No OCR binary required."""

from whisker.survey.adapters.tesseract import (
    MODES,
    _parse_version,
    render_markdown,
    tsv_to_paragraphs,
)

_SAMPLE_TSV = """\
level	page_num	block_num	par_num	line_num	word_num	left	top	width	height	conf	text
1	1	0	0	0	0	0	0	100	40	-1	
5	1	1	1	1	1	10	10	20	10	96	Hello
5	1	1	1	1	2	32	10	28	10	95	world
5	1	1	2	1	1	10	30	18	10	90	Next
5	1	1	2	1	2	30	30	40	10	91	paragraph
"""


class TestTsvToParagraphs:
    """TSV grouping is the only structure Tesseract markdown is allowed."""

    def test_groups_words_into_paragraphs(self):
        paras = tsv_to_paragraphs(_SAMPLE_TSV)
        assert paras == ["Hello world", "Next paragraph"]

    def test_skips_header_and_empty_words(self):
        tsv = (
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num"
            "\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t0\t0\t1\t1\t10\t\n"
            "5\t1\t1\t1\t1\t2\t0\t0\t1\t1\t10\tKeep\n"
        )
        assert tsv_to_paragraphs(tsv) == ["Keep"]

    def test_empty_tsv(self):
        assert tsv_to_paragraphs("") == []
        assert tsv_to_paragraphs("level\tpage_num\n") == []


class TestRenderMarkdown:
    """Provenance YAML only. No invented ATX headings."""

    def test_front_matter_and_body(self):
        md = render_markdown(
            version="5.5.0",
            oem=1,
            psm=3,
            dpi=300,
            lang="eng",
            pages=["Hello world", "Next paragraph"],
        )
        assert md.startswith("---\n")
        assert 'tesseract_version: "5.5.0"' in md
        assert "generator: tesseract" in md
        assert "## " not in md
        assert "Hello world" in md
        assert "Next paragraph" in md

    def test_empty_pages_still_write_yaml(self):
        md = render_markdown(
            version="5.5.0", oem=1, psm=3, dpi=300, lang="eng", pages=["", "  "]
        )
        assert md.startswith("---\n")
        assert "Hello" not in md


class TestVersionParse:
    def test_stderr_banner(self):
        banner = "tesseract 5.5.0\n leptonica-1.84.1\n"
        assert _parse_version(banner) == "5.5.0"

    def test_windows_build_banner(self):
        banner = "tesseract v5.5.0.20241111\n leptonica-1.85.0\n"
        assert _parse_version(banner) == "5.5.0"

    def test_missing(self):
        assert _parse_version("no version here") is None


class TestModes:
    def test_lstm_is_the_measured_mode(self):
        assert "lstm" in MODES
        assert MODES["lstm"]["oem"] == 1
        assert MODES["lstm"]["psm"] == 3
