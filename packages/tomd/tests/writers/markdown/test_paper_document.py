"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from typing import Callable

import pytest

from fixtures.sample_documents import ALL_SAMPLE_DOCUMENT_BUILDERS
from tomd.domain.document import PaperDocument
from tomd.writers import MarkdownWriter


def test_paper_document_abstract_prose_and_anchors(
    sample_abstract_doc: PaperDocument,
    sample_markdown: Callable[[str], str],
) -> None:
    actual = MarkdownWriter().write(sample_abstract_doc)
    assert actual == sample_markdown("abstract_prose")


def test_paper_document_tony_table_comparison(
    sample_tony_table_doc: PaperDocument,
    sample_markdown: Callable[[str], str],
) -> None:
    actual = MarkdownWriter().write(sample_tony_table_doc)
    assert actual == sample_markdown("tony_table")


def test_paper_document_wording_diff_markup(
    sample_wording_diff_doc: PaperDocument,
    sample_markdown: Callable[[str], str],
) -> None:
    actual = MarkdownWriter().write(sample_wording_diff_doc)
    assert actual == sample_markdown("wording_diff")


def test_paper_document_wording_diff_without_wording_tags(
    sample_wording_diff_doc: PaperDocument,
) -> None:
    actual = MarkdownWriter().write(sample_wording_diff_doc, wording_tags=False)
    assert "~~shall allocate elements using `std::allocator` exclusively.~~" in actual
    assert "<u>may allocate memory using an allocator satisfying the `Allocator` requirements [allocator.requirements].</u>" in actual
    assert "<del>" not in actual
    assert "</del>" not in actual


def test_paper_document_straw_poll_and_macro_tables(
    sample_poll_table_doc: PaperDocument,
    sample_markdown: Callable[[str], str],
) -> None:
    actual = MarkdownWriter().write(sample_poll_table_doc)
    assert actual == sample_markdown("straw_polls")


def test_paper_document_rich_blocks_and_nested_lists(
    sample_rich_blocks_doc: PaperDocument,
    sample_markdown: Callable[[str], str],
) -> None:
    actual = MarkdownWriter().write(sample_rich_blocks_doc)
    assert actual == sample_markdown("rich_blocks")


def test_paper_document_full_proposal_assembly(
    sample_full_proposal_doc: PaperDocument,
    sample_markdown: Callable[[str], str],
) -> None:
    actual = MarkdownWriter().write(sample_full_proposal_doc)
    assert actual == sample_markdown("full_proposal")


@pytest.mark.parametrize("builder", ALL_SAMPLE_DOCUMENT_BUILDERS)
def test_paper_document_pure_markdown_table_invariant(
    builder: Callable[[], PaperDocument],
) -> None:
    actual = MarkdownWriter().write(builder())
    assert "<table" not in actual
    assert "<tr" not in actual
    assert "<td" not in actual
    assert "<th" not in actual
    assert "<style" not in actual


@pytest.mark.parametrize("builder", ALL_SAMPLE_DOCUMENT_BUILDERS)
def test_paper_document_front_matter_invariant(
    builder: Callable[[], PaperDocument],
) -> None:
    actual = MarkdownWriter().write(builder())
    assert actual.startswith("---\n")
    assert "\n---\n" in actual
