#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for source-vs-candidate code-fence boundary comparison."""

from __future__ import annotations

import pymupdf
from whisker.det.code_fence_align import (
    STATUS_ABSTAINED,
    STATUS_CHECKED,
    STATUS_UNSUPPORTED,
    compare_code_fence_boundaries,
)
from whisker.det.pdf_geometry import is_monospace_line, load_pdf_lines

_BODY_SIZE = 11.0
_MONO_SIZE = 10.0
_MARGIN_X = 72.0
_LEADING = 14.0
_BODY_FONT = "Helvetica"
_MONO_FONT = "Courier"


def _write_mixed_pdf(path, prose_lines: list[str], code_lines: list[str]) -> None:
    """Write a PDF with prose lines in Helvetica and code lines in Courier."""
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72.0
    for line in prose_lines:
        page.insert_text((_MARGIN_X, y), line, fontname="helv",
                         fontsize=_BODY_SIZE)
        y += _LEADING
    y += _LEADING
    for line in code_lines:
        page.insert_text((_MARGIN_X, y), line, fontname="cour",
                         fontsize=_MONO_SIZE)
        y += _LEADING
    doc.save(path)
    doc.close()


def _write_prose_only_pdf(path, lines: list[str]) -> None:
    """Write a PDF with only proportional-font lines."""
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72.0
    for line in lines:
        page.insert_text((_MARGIN_X, y), line, fontname="helv",
                         fontsize=_BODY_SIZE)
        y += _LEADING
    doc.save(path)
    doc.close()


def test_clean_fences_produce_no_findings(tmp_path):
    """A candidate whose fences match the PDF's monospace regions exactly."""
    pdf = tmp_path / "clean.pdf"
    prose = ["This is a paragraph of text with several words in it.",
             "Another paragraph that continues the discussion here."]
    code = ["int main() {", "    return 0;", "}", "// end of main"]
    _write_mixed_pdf(pdf, prose, code)

    candidate = (
        "This is a paragraph of text with several words in it.\n\n"
        "Another paragraph that continues the discussion here.\n\n"
        "```cpp\n"
        "int main() {\n"
        "    return 0;\n"
        "}\n"
        "// end of main\n"
        "```\n"
    )

    result = compare_code_fence_boundaries(pdf, candidate)
    assert result.status == STATUS_CHECKED
    assert result.prose_in_fence == ()
    assert result.code_outside_fence == ()
    assert result.total_findings == 0


def test_prose_swallowed_into_fence(tmp_path):
    """Direction 1: a prose line inside a fence must be detected."""
    pdf = tmp_path / "prose_in_fence.pdf"
    prose = ["This is definitely prose text not code at all.",
             "More prose text that explains the algorithm."]
    code = ["int x = 42;", "return x;", "// done"]
    _write_mixed_pdf(pdf, prose, code)

    candidate = (
        "```cpp\n"
        "This is definitely prose text not code at all.\n"
        "int x = 42;\n"
        "return x;\n"
        "// done\n"
        "```\n\n"
        "More prose text that explains the algorithm.\n"
    )

    result = compare_code_fence_boundaries(pdf, candidate)
    assert result.status == STATUS_CHECKED
    assert result.prose_in_fence_count >= 1
    assert "this is definitely prose text not code at all" in result.prose_in_fence


def test_code_left_outside_fence(tmp_path):
    """Direction 2: a monospaced run outside a fence must be detected."""
    pdf = tmp_path / "code_outside.pdf"
    prose = ["Here is some explanation of the code below."]
    code = ["void foo() {", "    bar();", "    baz();", "}", "// end foo"]
    _write_mixed_pdf(pdf, prose, code)

    candidate = (
        "Here is some explanation of the code below.\n\n"
        "void foo() {\n"
        "    bar();\n"
        "    baz();\n"
        "}\n"
        "// end foo\n"
    )

    result = compare_code_fence_boundaries(pdf, candidate)
    assert result.status == STATUS_CHECKED
    assert result.code_outside_fence_count >= 1


def test_short_mono_run_does_not_fire(tmp_path):
    """Runs shorter than CODE_RUN_MIN_LINES must not trigger Direction 2."""
    pdf = tmp_path / "short.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72.0
    page.insert_text((_MARGIN_X, y), "Some prose context here.", fontname="helv",
                     fontsize=_BODY_SIZE)
    y += _LEADING
    # Only 2 mono lines (below the 3-line threshold)
    page.insert_text((_MARGIN_X, y), "int x = 1;", fontname="cour",
                     fontsize=_MONO_SIZE)
    y += _LEADING
    page.insert_text((_MARGIN_X, y), "int y = 2;", fontname="cour",
                     fontsize=_MONO_SIZE)
    y += _LEADING
    page.insert_text((_MARGIN_X, y), "More prose after code.", fontname="helv",
                     fontsize=_BODY_SIZE)
    doc.save(pdf)
    doc.close()

    candidate = (
        "Some prose context here.\n\n"
        "int x = 1;\n"
        "int y = 2;\n\n"
        "More prose after code.\n"
    )

    result = compare_code_fence_boundaries(pdf, candidate)
    assert result.status == STATUS_CHECKED
    assert result.code_outside_fence_count == 0


def test_cmtt_font_classified_as_monospace(tmp_path):
    """Regression: cmtt (Computer Modern Typewriter) must be classified mono.

    The original ``paragraph_align._is_body`` checked ``"Courier" in font``
    which missed cmtt/lmtt fonts used by LaTeX-generated WG21 PDFs.
    """
    pdf = tmp_path / "cmtt.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72.0
    # Simulate a cmtt-family font by using the name "CMTT10" as the fontname
    # PyMuPDF's insert_text with a non-builtin fontname will fall back, but
    # we can test the classification directly via load_pdf_lines.
    page.insert_text((_MARGIN_X, y), "int main() { return 0; }",
                     fontname="cour", fontsize=_MONO_SIZE)
    doc.save(pdf)
    doc.close()

    lines = load_pdf_lines(pdf)
    assert len(lines) >= 1
    assert is_monospace_line(lines[0])

    # Also verify the classify_monospace function directly for cmtt/lmtt:
    from tomd.lib.pdf.mono import classify_monospace
    assert classify_monospace("CMTT10") is True
    assert classify_monospace("LMTT10") is True
    assert classify_monospace("cmtt10-Regular") is True
    assert classify_monospace("CourierNewPSMT") is True
    assert classify_monospace("TimesNewRoman") is False
    assert classify_monospace("Helvetica") is False


def test_html_source_is_unsupported(tmp_path):
    html = tmp_path / "paper.html"
    html.write_text("<p>int main() {}</p>", encoding="utf-8")

    result = compare_code_fence_boundaries(html, "```\nint main() {}\n```\n")
    assert result.status == STATUS_UNSUPPORTED
    assert result.total_findings == 0


def test_unreadable_source_abstains(tmp_path):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not a pdf at all")

    result = compare_code_fence_boundaries(broken, "```\nint main() {}\n```\n")
    assert result.status == STATUS_ABSTAINED


def test_no_monospace_font_abstains(tmp_path):
    """PDF with only proportional fonts must abstain, not crash."""
    pdf = tmp_path / "nofont.pdf"
    _write_prose_only_pdf(pdf, [
        "This entire document uses proportional fonts.",
        "There is no code at all in this paper.",
        "Just regular text paragraphs everywhere.",
    ])

    result = compare_code_fence_boundaries(
        pdf, "```\nint main() {}\n```\n"
    )
    assert result.status == STATUS_ABSTAINED
    assert "no monospaced font" in result.detail


def test_front_matter_excluded_from_prose(tmp_path):
    """YAML front matter must not be parsed as prose or fenced content."""
    pdf = tmp_path / "fm.pdf"
    prose = ["The abstract of this paper discusses important things."]
    code = ["template<typename T>", "void swap(T& a, T& b) {", "    auto tmp = a;", "}"]
    _write_mixed_pdf(pdf, prose, code)

    candidate = (
        "---\n"
        "title: \"A Paper\"\n"
        "document: P1234R0\n"
        "---\n\n"
        "The abstract of this paper discusses important things.\n\n"
        "```cpp\n"
        "template<typename T>\n"
        "void swap(T& a, T& b) {\n"
        "    auto tmp = a;\n"
        "}\n"
        "```\n"
    )

    result = compare_code_fence_boundaries(pdf, candidate)
    assert result.status == STATUS_CHECKED
    assert result.total_findings == 0
