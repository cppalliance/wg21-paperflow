#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Mutation corpus tests: verify that deterministic corruptions are detected.

Uses mutation_fixtures to create known-defective markdown variants and verifies
that each mutation class produces measurable, detectable changes.
"""

from __future__ import annotations

import pytest
from mutation_fixtures import (
    mutate_code_garble,
    mutate_heading_level,
    mutate_list_item_drop,
    mutate_secno_inject,
    mutate_table_cell_truncate,
)
from whisker.llm.table_compare import parse_markdown_tables

# A minimal well-formed golden markdown for mutation
_GOOD_GOLDEN = """\
---
title: "Test Paper"
document: P9999R0
date: 2026-01-01
---

## Abstract

This paper proposes improvements to the C++ standard library.

## Motivation

The motivation for this change is clear and well-documented.

## Design

### Overview

The design follows established patterns.

### Details

Implementation details are straightforward.

## Wording

Changes to the standard text.

## References

[1] ISO/IEC 14882:2020
"""

_TABLE_MD = """\
| SF | F | N | A | SA |
|---|---|---|---|---|
| Yes | No | Yes | No | Yes |
| Agree | Disagree | Neutral | Agree | Disagree |
"""

_LIST_MD = """\
## Steps

1. First item in the list
2. Second item in the list
3. Third item in the list
4. Fourth item in the list
5. Fifth item in the list
6. Sixth item in the list

Done.
"""

_CODE_MD = """\
## Example

Use `std::vector` for dynamic arrays and `std::map` for associative containers.

The function `calculate_total` returns an `int` value.
"""


class TestTableCellTruncate:
    """Table cell truncation must produce detectable grid changes."""

    def test_truncates_cells(self):
        result = mutate_table_cell_truncate(_TABLE_MD)
        assert result.affected_count > 0
        assert result.mutated != result.original

    def test_detectable_by_table_parser(self):
        result = mutate_table_cell_truncate(_TABLE_MD)
        original_tables = parse_markdown_tables(_TABLE_MD)
        mutated_tables = parse_markdown_tables(result.mutated)
        assert original_tables != mutated_tables

    def test_respects_max_mutations(self):
        result = mutate_table_cell_truncate(_TABLE_MD, max_mutations=2)
        assert result.affected_count <= 2

    def test_skips_separator_rows(self):
        result = mutate_table_cell_truncate(_TABLE_MD)
        # Separator line must remain intact
        assert "---|" in result.mutated


class TestSecnoInject:
    """Section-number injection must alter heading text."""

    def test_injects_numbers(self):
        result = mutate_secno_inject(_GOOD_GOLDEN)
        assert result.affected_count > 0
        assert result.mutated != result.original

    def test_numbered_headings_present(self):
        result = mutate_secno_inject(_GOOD_GOLDEN)
        # At least the first heading gets "1. " prefix
        assert "## 1. Abstract" in result.mutated

    def test_respects_max_mutations(self):
        result = mutate_secno_inject(_GOOD_GOLDEN, max_mutations=2)
        assert result.affected_count <= 2

    def test_skips_already_numbered(self):
        md = "## 1. Already numbered\n## Another heading\n"
        result = mutate_secno_inject(md)
        # "1. Already numbered" should not get double-numbered
        assert "## 1. 1. Already numbered" not in result.mutated


class TestListItemDrop:
    """List item dropping must reduce item count."""

    def test_drops_items(self):
        result = mutate_list_item_drop(_LIST_MD)
        assert result.affected_count > 0
        assert result.mutated != result.original

    def test_reduces_line_count(self):
        result = mutate_list_item_drop(_LIST_MD)
        original_items = [
            l for l in _LIST_MD.splitlines() if l.strip().startswith(("1", "2", "3", "4", "5", "6"))
        ]
        mutated_items = [
            l for l in result.mutated.splitlines() if l.strip() and l.strip()[0].isdigit()
        ]
        assert len(mutated_items) < len(original_items)

    def test_drop_every_controls_frequency(self):
        result_2 = mutate_list_item_drop(_LIST_MD, drop_every=2)
        result_3 = mutate_list_item_drop(_LIST_MD, drop_every=3)
        assert result_2.affected_count > result_3.affected_count


class TestHeadingLevel:
    """Heading level drift must shift ATX heading markers."""

    def test_shifts_levels(self):
        result = mutate_heading_level(_GOOD_GOLDEN, shift=1)
        assert result.affected_count > 0
        assert result.mutated != result.original

    def test_h2_becomes_h3(self):
        result = mutate_heading_level(_GOOD_GOLDEN, shift=1)
        assert "### Abstract" in result.mutated

    def test_negative_shift(self):
        md = "### Sub heading\n#### Deep heading\n"
        result = mutate_heading_level(md, shift=-1)
        assert "## Sub heading" in result.mutated
        assert "### Deep heading" in result.mutated

    def test_clamps_at_h6(self):
        md = "###### Already h6\n"
        result = mutate_heading_level(md, shift=1)
        # Should not go beyond h6
        assert result.affected_count == 0


class TestCodeGarble:
    """Code garbling must corrupt inline code delimiters."""

    def test_garbles_code(self):
        result = mutate_code_garble(_CODE_MD)
        assert result.affected_count > 0
        assert result.mutated != result.original

    def test_adds_backtick_debris(self):
        result = mutate_code_garble(_CODE_MD)
        # Double backticks should appear
        assert "``" in result.mutated

    def test_respects_max_mutations(self):
        result = mutate_code_garble(_CODE_MD, max_mutations=1)
        assert result.affected_count == 1


class TestMutationResultContract:
    """All mutation results must satisfy the dataclass contract."""

    @pytest.mark.parametrize(
        "mutator,input_md",
        [
            (mutate_table_cell_truncate, _TABLE_MD),
            (mutate_secno_inject, _GOOD_GOLDEN),
            (mutate_list_item_drop, _LIST_MD),
            (mutate_heading_level, _GOOD_GOLDEN),
            (mutate_code_garble, _CODE_MD),
        ],
        ids=[
            "table_cell_truncate",
            "secno_inject",
            "list_item_drop",
            "heading_level",
            "code_garble",
        ],
    )
    def test_result_fields_populated(self, mutator, input_md):
        result = mutator(input_md)
        assert result.original == input_md
        assert isinstance(result.mutated, str)
        assert isinstance(result.mutation_type, str)
        assert result.affected_count >= 0
        assert isinstance(result.locations, list)

    @pytest.mark.parametrize(
        "mutator,input_md",
        [
            (mutate_table_cell_truncate, _TABLE_MD),
            (mutate_secno_inject, _GOOD_GOLDEN),
            (mutate_list_item_drop, _LIST_MD),
            (mutate_heading_level, _GOOD_GOLDEN),
            (mutate_code_garble, _CODE_MD),
        ],
        ids=[
            "table_cell_truncate",
            "secno_inject",
            "list_item_drop",
            "heading_level",
            "code_garble",
        ],
    )
    def test_locations_match_count(self, mutator, input_md):
        result = mutator(input_md)
        assert len(result.locations) == result.affected_count
