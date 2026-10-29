"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

import difflib
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from conftest import make_section, make_span
from parity.corpus import (
    GOLDEN_PDF_CORPUS,
    PDF_CONVERTER_CASES,
    PDF_CORPUS,
    SYNTH_PDF_CORPUS,
    cached_parse_pdf,
    cached_run_pipeline,
)
import tomd.api as tomd_api
from tomd.api import convert_paper_full
from tomd.domain.document import PaperDocument, SkipReason
from tomd.domain.elements import Confidence, UncertainElement
from tomd.lib.metadata_yaml.format import parse_front_matter
from tomd.lib.shared import apply_strip_leading_h1, strip_freeform_metadata_lines
from tomd.lib.pdf.emit import (
    assign_emdash_nesting,
    emit_markdown,
    emit_prompts,
    fold_table_continuations,
)
from tomd.lib.pdf.pipeline import PipelineResult, run_pipeline
from tomd.lib.pdf.types import Line, Section, SectionKind
from tomd.parsers import DocumentParser
from tomd.parsers.legacy_bridge import PDF_STRING_PASSES, render_pdf
from tomd.parsers.pdf import convert_pdf_dark, parse_pdf, sections_to_document
from tomd.writers.markdown.normalizers import (
    normalize_front_matter,
    strip_body_metadata_text,
    strip_toc,
)

_DIFF_CONTEXT_LINES = 3
_MAX_DIFF_LINES = 80


def _first_diff(expected: str, actual: str, label: str) -> str:
    diff = list(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=f"{label}:legacy",
            tofile=f"{label}:dark",
            n=_DIFF_CONTEXT_LINES,
        )
    )
    return "".join(diff[:_MAX_DIFF_LINES])


def _apply_api_normalizers(md: str, meta: dict[str, Any]) -> str:
    md = normalize_front_matter(md, meta)
    md = strip_body_metadata_text(md)
    md = strip_freeform_metadata_lines(md, metadata=meta)
    title = parse_front_matter(md).get("title")
    if isinstance(title, str) and title:
        md = apply_strip_leading_h1(md, title)
    return strip_toc(md)


def _case_id(case: tuple[Path, bool]) -> str:
    path, extract_vector = case
    suffix = "+vector" if extract_vector else ""
    return f"{path.stem}{suffix}"


def test_corpus_counts():
    assert len(GOLDEN_PDF_CORPUS) == 28
    assert len(SYNTH_PDF_CORPUS) == 4
    assert len(PDF_CORPUS) == 33
    assert len(PDF_CONVERTER_CASES) == 37


@pytest.mark.parametrize(
    ("path", "extract_vector"),
    PDF_CONVERTER_CASES,
    ids=[_case_id(c) for c in PDF_CONVERTER_CASES],
)
def test_pdf_converter_parity(path: Path, extract_vector: bool):
    legacy = cached_run_pipeline(path, extract_vector)
    doc = cached_parse_pdf(path, extract_vector)
    dark_md = render_pdf(doc)

    if dark_md != legacy.md:
        pytest.fail(
            f"Converter-level Markdown mismatch for {path.name} "
            f"(extract_vector={extract_vector}):\n"
            f"{_first_diff(legacy.md, dark_md, path.stem)}"
        )

    assert doc.reconcile_prompts() == legacy.prompts
    assert doc.images == legacy.images
    assert doc.is_skipped == legacy.skipped
    assert doc.skip_reason == legacy.skip_reason


@pytest.mark.parametrize(
    "path",
    PDF_CORPUS,
    ids=[p.stem for p in PDF_CORPUS],
)
def test_pdf_api_parity(path: Path):
    paper_id = path.stem.upper()
    meta: dict[str, Any] = {
        "paper_id": paper_id,
        "title": "Fallback Mailing Title",
        "document_date": "2025-01-15",
        "subgroup": "LEWG",
        "authors": ["Test Author <author@example.com>"],
    }

    with patch.object(tomd_api, "run_pipeline", side_effect=cached_run_pipeline):
        legacy = convert_paper_full(paper_id, path, meta)

    doc = cached_parse_pdf(path, False)
    dark_raw_md = render_pdf(doc)
    dark_api_md = _apply_api_normalizers(dark_raw_md, meta)

    if dark_api_md != legacy.markdown:
        pytest.fail(
            f"API-level Markdown mismatch for {path.name}:\n"
            f"{_first_diff(legacy.markdown, dark_api_md, path.stem)}"
        )

    assert doc.reconcile_prompts() == legacy.prompts
    assert doc.images == legacy.images


def test_unpatched_parse_pdf_and_convert_pdf_dark():
    sample_pdf = SYNTH_PDF_CORPUS[0]
    legacy = run_pipeline(sample_pdf)
    doc = parse_pdf(sample_pdf)
    assert render_pdf(doc) == legacy.md
    assert convert_pdf_dark(sample_pdf) == legacy.md


def test_pdf_string_passes_order():
    names = tuple(fn.__name__ for fn in PDF_STRING_PASSES)
    assert names == (
        "dedup_paragraphs",
        "strip_redundant_body_meta",
        "strip_orphan_toc_list",
        "_inject_table_css",
        "_strip_leading_h1",
    )


def test_assign_emdash_nesting_idempotent():
    line_outer = Line(
        spans=[make_span("\u2013 outer item")],
        bbox=(72.0, 100.0, 200.0, 112.0),
    )
    line_inner = Line(
        spans=[make_span("\u2013 inner item")],
        bbox=(90.0, 120.0, 200.0, 132.0),
    )
    line_deep = Line(
        spans=[make_span("\u2013 deep item")],
        bbox=(108.0, 140.0, 200.0, 152.0),
    )
    sections = [
        make_section(
            "\u2013 outer item",
            kind=SectionKind.PARAGRAPH,
            lines=[line_outer],
        ),
        make_section(
            "\u2013 inner item",
            kind=SectionKind.PARAGRAPH,
            lines=[line_inner],
        ),
        make_section(
            "\u2013 deep item",
            kind=SectionKind.PARAGRAPH,
            lines=[line_deep],
        ),
    ]

    assign_emdash_nesting(sections)
    levels_after_first = [s.indent_level for s in sections]
    assert levels_after_first == [0, 1, 2]
    md_first = emit_markdown({}, sections)

    assign_emdash_nesting(sections)
    levels_after_second = [s.indent_level for s in sections]
    assert levels_after_second == levels_after_first
    assert emit_markdown({}, sections) == md_first


def test_fold_table_continuations_idempotent():
    base_table = Section(
        kind=SectionKind.TABLE,
        text="H1 | H2\nA | B",
        confidence=Confidence.HIGH,
        columns=[
            [[make_span("H1")], [make_span("H2")]],
            [[make_span("A")], [make_span("B")]],
        ],
        table_strategy="pipe_table",
    )
    interleaved = make_section("Page 2", kind=SectionKind.PARAGRAPH)
    continuation_table = Section(
        kind=SectionKind.TABLE,
        text="C | D",
        confidence=Confidence.HIGH,
        columns=[
            [[make_span("C")], [make_span("D")]],
        ],
        table_strategy="pipe_table",
        table_continuation=True,
    )
    sections = [base_table, interleaved, continuation_table]

    returned = fold_table_continuations(sections)
    assert returned is sections
    assert len(sections) == 2
    assert len(sections[0].columns) == 3
    snapshot_text = sections[0].text
    snapshot_rows = len(sections[0].columns)

    returned_again = fold_table_continuations(sections)
    assert returned_again is sections
    assert len(sections) == 2
    assert len(sections[0].columns) == snapshot_rows
    assert sections[0].text == snapshot_text


def test_sections_to_document_skipped_and_extra_prompts():
    skip_prompt = "# tomd - Slide Deck Detected\n"
    skipped_res = PipelineResult.for_skip(
        SkipReason.SLIDE_DECK,
        page_count=5,
        prompts=[skip_prompt],
    )
    skipped_doc = sections_to_document(skipped_res, paper_id="P9999R0")
    assert skipped_doc.is_skipped is True
    assert skipped_doc.skip_reason == SkipReason.SLIDE_DECK
    assert skipped_doc.reconcile_prompts() == [skip_prompt]
    assert render_pdf(skipped_doc) == ""

    sec_before = make_section("Preceding context text", kind=SectionKind.PARAGRAPH)
    sec_uncertain = Section(
        kind=SectionKind.UNCERTAIN,
        text="uncertain text\n\n  ",
        mupdf_text="",
        spatial_text="spatial text",
        page_num=2,
        confidence=Confidence.UNCERTAIN,
    )
    sec_after = make_section("Following context text", kind=SectionKind.PARAGRAPH)
    wording_prompt = (
        "The PDF wording-detection pass flagged the following issue. "
        "Review and correct the affected region in the converted Markdown.\n\n"
        "page 2: unconfirmed deletion"
    )
    active_res = PipelineResult(
        md="",
        sections=[sec_before, sec_uncertain, sec_after],
        metadata={"title": "Test", "reply-to": []},
        prompts=["placeholder-uncertain-prompt", wording_prompt],
    )
    active_doc = sections_to_document(active_res, paper_id="P9998R0")
    uncertain_elems = [
        e for e in active_doc.elements if isinstance(e, UncertainElement)
    ]
    assert len(uncertain_elems) == 1
    assert uncertain_elems[0].context_before == "Preceding context text"
    assert uncertain_elems[0].context_after == "Following context text"
    assert active_doc.diagnostics.extra_prompts == (wording_prompt,)
    prompts = active_doc.reconcile_prompts()
    assert prompts is not None
    assert len(prompts) == 2
    assert prompts[:1] == emit_prompts(active_res.sections)
    assert prompts[1] == wording_prompt
    rendered = render_pdf(active_doc)
    expected = emit_markdown(active_res.metadata, active_res.sections)
    assert rendered == expected


def test_document_parser_protocol():
    class _DummyPdfParser:
        def parse(self, path: Path) -> PaperDocument:
            return PaperDocument(paper_id=path.stem)

    parser = _DummyPdfParser()
    assert isinstance(parser, DocumentParser)
    assert parser.parse(Path("p1234r0.pdf")).paper_id == "p1234r0"
