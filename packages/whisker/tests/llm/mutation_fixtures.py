#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Deterministic mutation fixtures for recall testing.

Each mutation function takes well-formed markdown and introduces one specific
class of defect. The mutations are deterministic (seeded) so test results are
reproducible. Used by accountability tests to verify the detection pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class MutationResult:
    """Result of applying one mutation to markdown."""

    original: str
    mutated: str
    mutation_type: str
    affected_count: int
    locations: list[str] = field(default_factory=list)


def mutate_table_cell_truncate(
    markdown: str, *, max_mutations: int = 6
) -> MutationResult:
    """Truncate the first character of table cells containing 2+ chars.

    Models the PR #286 SF->S case where vertical text wrap dropped a character.
    Only affects data cells (skips header separators).
    """
    lines = markdown.splitlines(keepends=True)
    mutated_lines: list[str] = []
    count = 0
    locations: list[str] = []

    for i, line in enumerate(lines):
        if count >= max_mutations and max_mutations > 0:
            mutated_lines.append(line)
            continue
        # Match table rows (not separators)
        if re.match(r"^\|", line) and not re.match(
            r"^\|[\s:|\-]+\|$", line.strip()
        ):
            cells = line.split("|")
            new_cells: list[str] = []
            for j, cell in enumerate(cells):
                stripped = cell.strip()
                if len(stripped) >= 2 and count < max_mutations:
                    # Truncate: keep only first char (SF -> S)
                    new_cell = cell.replace(stripped, stripped[0], 1)
                    new_cells.append(new_cell)
                    count += 1
                    locations.append(f"line {i + 1}, cell {j}")
                else:
                    new_cells.append(cell)
            mutated_lines.append("|".join(new_cells))
        else:
            mutated_lines.append(line)

    return MutationResult(
        original=markdown,
        mutated="".join(mutated_lines),
        mutation_type="table_cell_truncate",
        affected_count=count,
        locations=locations,
    )


def mutate_secno_inject(
    markdown: str, *, max_mutations: int = 10
) -> MutationResult:
    """Inject section-number labels before heading text.

    Models the PR #295 case where span.secno labels were retained.
    Adds "N. " prefix to ## headings where N is the sequential count.
    """
    lines = markdown.splitlines(keepends=True)
    mutated_lines: list[str] = []
    count = 0
    locations: list[str] = []
    heading_counter = 0

    for i, line in enumerate(lines):
        match = re.match(r"^(#{2,3})\s+(.+)$", line.rstrip())
        if match and count < max_mutations:
            level_marker = match.group(1)
            heading_text = match.group(2).rstrip()
            # Don't inject if already has a number prefix
            if not re.match(r"^\d+\.?\s", heading_text):
                heading_counter += 1
                mutated_line = (
                    f"{level_marker} {heading_counter}. {heading_text}\n"
                )
                mutated_lines.append(mutated_line)
                count += 1
                locations.append(f"line {i + 1}: {heading_text}")
                continue
        mutated_lines.append(line)

    return MutationResult(
        original=markdown,
        mutated="".join(mutated_lines),
        mutation_type="secno_inject",
        affected_count=count,
        locations=locations,
    )


def mutate_list_item_drop(
    markdown: str, *, drop_every: int = 2
) -> MutationResult:
    """Drop every Nth list item from ordered lists.

    Models list cardinality collapse where items are merged or dropped.
    """
    lines = markdown.splitlines(keepends=True)
    mutated_lines: list[str] = []
    count = 0
    locations: list[str] = []
    list_item_index = 0
    in_list = False

    for i, line in enumerate(lines):
        is_list_item = bool(re.match(r"^\s*\d+\.\s", line))
        if is_list_item:
            in_list = True
            list_item_index += 1
            if list_item_index % drop_every == 0:
                count += 1
                locations.append(f"line {i + 1}")
                continue  # Drop this item
        elif in_list and not line.strip():
            in_list = False
            list_item_index = 0
        mutated_lines.append(line)

    return MutationResult(
        original=markdown,
        mutated="".join(mutated_lines),
        mutation_type="list_item_drop",
        affected_count=count,
        locations=locations,
    )


def mutate_heading_level(
    markdown: str, *, shift: int = 1
) -> MutationResult:
    """Shift heading levels (e.g. h2->h3).

    Models heading hierarchy corruption.
    """
    lines = markdown.splitlines(keepends=True)
    mutated_lines: list[str] = []
    count = 0
    locations: list[str] = []

    for i, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.+)$", line.rstrip())
        if match:
            level = len(match.group(1))
            new_level = min(6, max(1, level + shift))
            if new_level != level:
                mutated_line = f"{'#' * new_level} {match.group(2)}\n"
                mutated_lines.append(mutated_line)
                count += 1
                locations.append(f"line {i + 1}: h{level}->h{new_level}")
                continue
        mutated_lines.append(line)

    return MutationResult(
        original=markdown,
        mutated="".join(mutated_lines),
        mutation_type="heading_level_drift",
        affected_count=count,
        locations=locations,
    )


def mutate_code_garble(
    markdown: str, *, max_mutations: int = 5
) -> MutationResult:
    """Insert literal backtick debris around inline code spans.

    Models the PR #286 inline code delimiter corruption.
    """
    count = 0
    locations: list[str] = []
    result = markdown

    pattern = re.compile(r"`([^`]+)`")

    def garble(match: re.Match[str]) -> str:
        nonlocal count
        if count >= max_mutations:
            return match.group(0)
        count += 1
        locations.append(f"code: {match.group(1)[:30]}")
        # Add extra backtick debris
        return f"``{match.group(1)}``"

    result = pattern.sub(garble, result)

    return MutationResult(
        original=markdown,
        mutated=result,
        mutation_type="code_garble",
        affected_count=count,
        locations=locations,
    )
