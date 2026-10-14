#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Select the block pairs that exhibit a named conversion defect.

A three-hundred-page side-by-side dump proves nothing to a reader who will not
read it. A claim like "this converter emits no fenced code blocks" is only
verifiable if the specific pairs behind it can be put in front of someone, so
they have to be selected mechanically. Hand-picking invites picking whatever
flatters the conclusion.

Detectors name a defect class, never a tool, so the same set applies to whatever
converter the next survey measures. Each takes the full pair sequence and one
index, because some defects are only visible across neighbouring pairs: a code
block rendered as prose appears as two unmatched pairs, not one changed pair,
since alignment only pairs blocks of equal type.

Left is the candidate under test, right is the reference. That orientation is
fixed and every detector assumes it.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from whisker.det.compare.align import AlignedDocument, AlignedPair, PairStatus
from whisker.det.compare.blocks import Block, BlockType

__all__ = [
    "DETECTORS",
    "Detector",
    "Exhibit",
    "code_leaked_into_prose",
    "dropped_code_block",
    "emphasis_promoted_to_heading",
    "escaped_identifier",
    "find_exhibits",
    "inflated_table",
    "table_row_count",
]

Detector = Callable[[Sequence[AlignedPair], int], bool]

# How far to look for the other half of a defect that spans two pairs.
NEIGHBOUR_WINDOW = 3

# A table separator row carries no data and must not count toward row totals.
_TABLE_ROW = re.compile(r"^\s*\|")
_TABLE_SEPARATOR = re.compile(r"^\s*\|[\s:|-]+\|?\s*$")

# Backslash-escaped underscore, as emitted by converters that escape Markdown
# metacharacters without excluding code spans. Turns __cpp_lib_x into \_\_cpp\_lib\_x.
_ESCAPED_UNDERSCORE = re.compile(r"\\_")

# A closing brace or bracket that escaped its fence and got glued to the prose
# that follows it, optionally still wearing a code span.
_ORPHAN_CLOSER = re.compile(r"^`?\s*[}\])]+\s*`?(?:\s|$)")

# Text whose entire content is wrapped in emphasis markers.
_EMPHASIS_ONLY = re.compile(r"^([*_]{1,3})(?P<inner>[^*_].*?)\1$", re.S)

MIN_EMPHASIS_OVERLAP_CHARS = 8


@dataclass(frozen=True)
class Exhibit:
    """One selected pair, with its position and the pairs around it."""

    index: int
    pair: AlignedPair
    before: AlignedPair | None = None
    after: AlignedPair | None = None


def table_row_count(block: Block) -> int:
    """Count data rows in a pipe table, excluding the separator."""
    rows = 0
    for line in block.text.splitlines():
        if not _TABLE_ROW.match(line):
            continue
        if _TABLE_SEPARATOR.match(line):
            continue
        rows += 1
    return rows


def _at(pairs: Sequence[AlignedPair], index: int) -> AlignedPair | None:
    return pairs[index] if 0 <= index < len(pairs) else None


def dropped_code_block(pairs: Sequence[AlignedPair], index: int) -> bool:
    """The reference has a fenced code block the candidate did not produce.

    Matches ``right_only`` pairs rather than type mismatches, because a code
    block re-emitted as a paragraph cannot align as one changed pair: the gap
    filler only pairs blocks of equal type, so it splits into an unmatched
    reference code block and an unmatched candidate paragraph.
    """
    pair = pairs[index]
    return (
        pair.status is PairStatus.RIGHT_ONLY
        and pair.right is not None
        and pair.right.block_type is BlockType.CODE
    )


def escaped_identifier(pairs: Sequence[AlignedPair], index: int) -> bool:
    """The candidate backslash-escaped underscores, breaking identifiers."""
    pair = pairs[index]
    if pair.left is None or not _ESCAPED_UNDERSCORE.search(pair.left.text):
        return False
    # Only a defect if the reference did not escape them too.
    if pair.right is not None and _ESCAPED_UNDERSCORE.search(pair.right.text):
        return False
    return True


def inflated_table(pairs: Sequence[AlignedPair], index: int) -> bool:
    """The candidate produced more table rows than the reference has, or a
    table where the reference has none."""
    pair = pairs[index]
    if pair.left is None or pair.left.block_type is not BlockType.TABLE:
        return False
    if pair.right is None or pair.right.block_type is not BlockType.TABLE:
        return True
    return table_row_count(pair.left) > table_row_count(pair.right)


def code_leaked_into_prose(pairs: Sequence[AlignedPair], index: int) -> bool:
    """A candidate paragraph opens with a closer that belongs inside a fence."""
    pair = pairs[index]
    if pair.left is None or pair.left.block_type is not BlockType.PARAGRAPH:
        return False
    if not _ORPHAN_CLOSER.match(pair.left.text.strip()):
        return False
    # If the reference paragraph starts the same way, the source is to blame.
    if pair.right is not None and _ORPHAN_CLOSER.match(pair.right.text.strip()):
        return False
    return True


def emphasis_promoted_to_heading(pairs: Sequence[AlignedPair], index: int) -> bool:
    """The candidate made a heading of a line the reference keeps as emphasis.

    Spans two pairs for the same reason ``dropped_code_block`` does, so this
    looks for the reference half in the surrounding window.
    """
    pair = pairs[index]
    if (
        pair.status is not PairStatus.LEFT_ONLY
        or pair.left is None
        or pair.left.block_type is not BlockType.HEADING
    ):
        return False

    title = pair.left.text.lstrip("#").strip().lower()
    if not title:
        return False

    for offset in range(-NEIGHBOUR_WINDOW, NEIGHBOUR_WINDOW + 1):
        if offset == 0:
            continue
        other = _at(pairs, index + offset)
        if other is None or other.status is not PairStatus.RIGHT_ONLY:
            continue
        if other.right is None or other.right.block_type is not BlockType.PARAGRAPH:
            continue
        match = _EMPHASIS_ONLY.match(other.right.text.strip())
        if not match:
            continue
        inner = match.group("inner").strip().lower()
        if len(inner) >= MIN_EMPHASIS_OVERLAP_CHARS and inner == title:
            return True
    return False


# Registry keyed by defect name, for callers that select by string.
DETECTORS: dict[str, Detector] = {
    "dropped_code_block": dropped_code_block,
    "escaped_identifier": escaped_identifier,
    "inflated_table": inflated_table,
    "code_leaked_into_prose": code_leaked_into_prose,
    "emphasis_promoted_to_heading": emphasis_promoted_to_heading,
}


def find_exhibits(
    doc: AlignedDocument,
    detector: Detector,
    *,
    limit: int | None = None,
) -> tuple[list[Exhibit], int]:
    """Return the pairs a detector matches, in document order, and the total.

    The total is the full match count even when ``limit`` truncates the returned
    list, so a caller can honestly say "3 of 17 shown" instead of implying that
    three is all there is. Scanning does not stop at the limit for that reason.
    """
    found: list[Exhibit] = []
    total = 0
    for index in range(len(doc.pairs)):
        if not detector(doc.pairs, index):
            continue
        total += 1
        if limit is not None and len(found) >= limit:
            continue
        found.append(
            Exhibit(
                index=index,
                pair=doc.pairs[index],
                before=_at(doc.pairs, index - 1),
                after=_at(doc.pairs, index + 1),
            )
        )
    return found, total
