"""Shared test fixtures for tomd."""

import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

import pytest

from fixtures.sample_documents import (
    sample_abstract_prose_document,
    sample_full_proposal_document,
    sample_poll_table_document,
    sample_rich_blocks_document,
    sample_tony_table_document,
    sample_wording_diff_document,
)
from tomd.lib.pdf.types import Block, Confidence, Line, Section, SectionKind, Span


def make_span(text, font_size=10.0, bold=False, italic=False,
              monospace=False, font_name="TestFont", **kwargs):
    return Span(text=text, font_name=font_name, font_size=font_size,
                bold=bold, italic=italic, monospace=monospace, **kwargs)


def make_line(texts, page_num=0, **span_kwargs):
    spans = [make_span(t, **span_kwargs) for t in texts]
    return Line(spans=spans, page_num=page_num)


def make_block(line_texts, page_num=0, **span_kwargs):
    lines = [make_line(t if isinstance(t, list) else [t],
                       page_num=page_num, **span_kwargs)
             for t in line_texts]
    return Block(lines=lines, page_num=page_num)


def make_section(text, kind=SectionKind.PARAGRAPH, page_num=0,
                 font_size=10.0, confidence=Confidence.HIGH,
                 heading_level=0, lines=None, **kwargs):
    if lines is None:
        lines = [make_line([text], font_size=font_size)]
    return Section(kind=kind, text=text, confidence=confidence,
                   heading_level=heading_level, lines=lines,
                   page_num=page_num, font_size=font_size, **kwargs)


@pytest.fixture
def sample_abstract_doc():
    return sample_abstract_prose_document()


@pytest.fixture
def sample_tony_table_doc():
    return sample_tony_table_document()


@pytest.fixture
def sample_wording_diff_doc():
    return sample_wording_diff_document()


@pytest.fixture
def sample_poll_table_doc():
    return sample_poll_table_document()


@pytest.fixture
def sample_rich_blocks_doc():
    return sample_rich_blocks_document()


@pytest.fixture
def sample_full_proposal_doc():
    return sample_full_proposal_document()
