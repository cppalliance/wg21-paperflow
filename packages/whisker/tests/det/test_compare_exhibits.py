#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the defect detectors behind the report's evidence appendix.

These detectors decide which block pairs a report prints as proof of its claims,
so a detector that silently stops matching turns a substantiated claim into an
unsubstantiated one without any error. Two properties matter most and each has a
dedicated test: a defect that spans two unmatched pairs is still found, and the
match total survives truncation so the appendix cannot imply that a sample is
the whole finding.
"""

from __future__ import annotations

from whisker.det.compare import align_documents, find_exhibits
from whisker.det.compare.blocks import BlockType, parse_blocks
from whisker.det.compare.exhibits import (
    code_leaked_into_prose,
    dropped_code_block,
    emphasis_promoted_to_heading,
    escaped_identifier,
    inflated_table,
    table_row_count,
)


def _doc(candidate: str, reference: str):
    return align_documents(
        candidate, reference, left_label="candidate", right_label="reference"
    )


def _count(candidate: str, reference: str, detector) -> int:
    _, total = find_exhibits(_doc(candidate, reference), detector)
    return total


class TestTableRowCount:
    def test_separator_row_is_not_data(self):
        table = "| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
        block = parse_blocks(table)[0]
        assert block.block_type is BlockType.TABLE
        assert table_row_count(block) == 3  # header plus two data rows

    def test_alignment_colons_are_still_a_separator(self):
        table = "| a | b |\n|:--|--:|\n| 1 | 2 |"
        assert table_row_count(parse_blocks(table)[0]) == 2


class TestDroppedCodeBlock:
    def test_reference_code_without_counterpart_is_found(self):
        """The defining case: a fenced block the candidate turned into prose.

        Alignment cannot pair these as one changed row because it only pairs
        blocks of equal type, so the detector has to match the unmatched
        reference block.
        """
        candidate = "## Title\n\nint x = 1; is the declaration.\n"
        reference = "## Title\n\n```cpp\nint x = 1;\n```\n"
        assert _count(candidate, reference, dropped_code_block) == 1

    def test_reproduced_code_is_not_a_defect(self):
        both = "## Title\n\n```cpp\nint x = 1;\n```\n"
        assert _count(both, both, dropped_code_block) == 0

    def test_candidate_only_code_is_not_counted_as_dropped(self):
        """A spurious candidate block is a different bug and must not net out."""
        candidate = "## Title\n\n```cpp\nint x;\n```\n"
        reference = "## Title\n\nplain prose here\n"
        assert _count(candidate, reference, dropped_code_block) == 0


class TestEscapedIdentifier:
    def test_escaped_underscores_in_candidate_are_found(self):
        candidate = "## T\n\nThe macro \\_\\_cpp\\_lib\\_ranges is set.\n"
        reference = "## T\n\nThe macro __cpp_lib_ranges is set.\n"
        assert _count(candidate, reference, escaped_identifier) == 1

    def test_reference_escaping_too_means_the_source_is_to_blame(self):
        both = "## T\n\nThe macro \\_\\_cpp is set.\n"
        assert _count(both, both, escaped_identifier) == 0

    def test_plain_underscores_are_clean(self):
        both = "## T\n\nThe macro __cpp_lib_ranges is set.\n"
        assert _count(both, both, escaped_identifier) == 0


class TestInflatedTable:
    def test_more_rows_than_reference_is_found(self):
        candidate = "| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n| 5 | 6 |\n"
        reference = "| a | b |\n|---|---|\n| 1 | 2 |\n"
        assert _count(candidate, reference, inflated_table) == 1

    def test_table_the_reference_lacks_entirely_is_found(self):
        candidate = "## T\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"
        reference = "## T\n\nprose instead of a table\n"
        assert _count(candidate, reference, inflated_table) == 1

    def test_row_parity_is_clean(self):
        both = "| a | b |\n|---|---|\n| 1 | 2 |\n"
        assert _count(both, both, inflated_table) == 0

    def test_fewer_rows_is_not_inflation(self):
        candidate = "| a | b |\n|---|---|\n| 1 | 2 |\n"
        reference = "| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n"
        assert _count(candidate, reference, inflated_table) == 0


class TestCodeLeakedIntoProse:
    def test_orphan_closing_brace_is_found(self):
        candidate = "## T\n\n`}` This sentence follows the block.\n"
        reference = "## T\n\nThis sentence follows the block.\n"
        assert _count(candidate, reference, code_leaked_into_prose) == 1

    def test_bare_brace_without_code_span_is_found(self):
        candidate = "## T\n\n} This sentence follows the block.\n"
        reference = "## T\n\nThis sentence follows the block.\n"
        assert _count(candidate, reference, code_leaked_into_prose) == 1

    def test_prose_that_merely_mentions_a_brace_is_clean(self):
        both = "## T\n\nThe closing brace } ends the scope.\n"
        assert _count(both, both, code_leaked_into_prose) == 0


class TestEmphasisPromotedToHeading:
    def test_heading_against_neighbouring_emphasis_is_found(self):
        candidate = "## Real\n\n#### Clearing up some core vocabulary\n\ntail\n"
        reference = "## Real\n\n*Clearing up some core vocabulary*\n\ntail\n"
        assert _count(candidate, reference, emphasis_promoted_to_heading) == 1

    def test_matching_headings_are_clean(self):
        both = "## Real\n\n#### Clearing up some core vocabulary\n\ntail\n"
        assert _count(both, both, emphasis_promoted_to_heading) == 0

    def test_unrelated_extra_heading_is_not_attributed_to_emphasis(self):
        candidate = "## Real\n\n#### Something entirely different\n\ntail\n"
        reference = "## Real\n\n*Clearing up some core vocabulary*\n\ntail\n"
        assert _count(candidate, reference, emphasis_promoted_to_heading) == 0


class TestFindExhibits:
    def _five_dropped_blocks(self):
        reference = "## T\n\n" + "\n\n".join(
            f"```cpp\nint x{n} = {n};\n```" for n in range(5)
        )
        return "## T\n\nno code at all here\n", reference

    def test_total_counts_every_match_even_when_truncated(self):
        """Truncating the sample must not truncate the count.

        The appendix prints "N of M shown", so a limit that also caps M would
        present a sample as if it were the whole finding.
        """
        candidate, reference = self._five_dropped_blocks()
        doc = _doc(candidate, reference)

        exhibits, total = find_exhibits(doc, dropped_code_block, limit=2)
        assert len(exhibits) == 2
        assert total == 5

    def test_unlimited_returns_everything(self):
        candidate, reference = self._five_dropped_blocks()
        exhibits, total = find_exhibits(_doc(candidate, reference), dropped_code_block)
        assert len(exhibits) == total == 5

    def test_exhibits_keep_document_order_and_neighbours(self):
        candidate, reference = self._five_dropped_blocks()
        exhibits, _ = find_exhibits(_doc(candidate, reference), dropped_code_block)

        assert [e.index for e in exhibits] == sorted(e.index for e in exhibits)
        # Interior exhibits carry context on both sides for the renderer.
        assert exhibits[-1].before is not None
