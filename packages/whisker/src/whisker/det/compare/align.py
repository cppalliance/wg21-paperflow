#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Order-preserving block alignment with word-level diff.

Aligns two lists of blocks using SequenceMatcher for anchoring (on
normalized block hashes), then fills gaps with rapidfuzz NED pairing.
The result is a list of AlignedPair objects consumable by both the HTML
and PDF renderers.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from enum import Enum

from rapidfuzz.distance import Levenshtein as _Lev

from whisker.det.compare.blocks import Block, parse_blocks

__all__ = [
    "AlignedDocument",
    "AlignedPair",
    "PairStatus",
    "align_blocks",
    "align_documents",
    "word_diff",
]


class PairStatus(Enum):
    """Alignment status of a block pair."""
    EQUAL = "equal"
    CHANGED = "changed"
    LEFT_ONLY = "left_only"
    RIGHT_ONLY = "right_only"


@dataclass(frozen=True)
class WordSpan:
    """A contiguous run of words with a diff tag."""
    tag: str  # "equal", "insert", "delete", "replace"
    text: str


@dataclass(frozen=True)
class AlignedPair:
    """One row of the side-by-side view: a matched or unmatched block pair."""

    left: Block | None
    right: Block | None
    status: PairStatus
    similarity: float = 1.0  # 0..1, 1.0 = identical
    word_diff_left: list[WordSpan] = field(default_factory=list)
    word_diff_right: list[WordSpan] = field(default_factory=list)


@dataclass
class AlignedDocument:
    """Complete alignment result for two Markdown documents."""

    left_label: str
    right_label: str
    pairs: list[AlignedPair]
    left_blocks: list[Block]
    right_blocks: list[Block]

    @property
    def total_pairs(self) -> int:
        return len(self.pairs)

    @property
    def changed_pairs(self) -> int:
        return sum(1 for p in self.pairs if p.status != PairStatus.EQUAL)

    @property
    def equal_pairs(self) -> int:
        return sum(1 for p in self.pairs if p.status == PairStatus.EQUAL)


def _block_signature(block: Block) -> str:
    """Signature for SequenceMatcher anchoring: type + normalized text."""
    return f"{block.block_type.value}::{block.normalized}"


def _text_similarity(a: str, b: str) -> float:
    """Normalized text similarity in [0, 1] (1.0 = identical)."""
    if not a and not b:
        return 1.0
    longest = max(len(a), len(b))
    if longest == 0:
        return 1.0
    return 1.0 - (_Lev.distance(a, b) / longest)


def word_diff(left_text: str, right_text: str) -> tuple[list[WordSpan], list[WordSpan]]:
    """Compute word-level diff between two text blocks.

    Returns two lists of WordSpan: one for each side, with tags indicating
    which words are equal, deleted, inserted, or replaced.
    """
    left_words = left_text.split()
    right_words = right_text.split()

    sm = difflib.SequenceMatcher(None, left_words, right_words)
    left_spans: list[WordSpan] = []
    right_spans: list[WordSpan] = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            text = " ".join(left_words[i1:i2])
            left_spans.append(WordSpan("equal", text))
            right_spans.append(WordSpan("equal", text))
        elif tag == "delete":
            left_spans.append(WordSpan("delete", " ".join(left_words[i1:i2])))
        elif tag == "insert":
            right_spans.append(WordSpan("insert", " ".join(right_words[j1:j2])))
        elif tag == "replace":
            left_spans.append(WordSpan("delete", " ".join(left_words[i1:i2])))
            right_spans.append(WordSpan("insert", " ".join(right_words[j1:j2])))

    return left_spans, right_spans


def align_blocks(left_blocks: list[Block], right_blocks: list[Block]) -> list[AlignedPair]:
    """Align two block lists preserving reading order.

    Uses SequenceMatcher on block signatures as anchors, then pairs
    unmatched blocks in gaps using similarity if types match, otherwise
    emits them as left_only or right_only.
    """
    left_sigs = [_block_signature(b) for b in left_blocks]
    right_sigs = [_block_signature(b) for b in right_blocks]

    sm = difflib.SequenceMatcher(None, left_sigs, right_sigs, autojunk=False)
    pairs: list[AlignedPair] = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for li, ri in zip(range(i1, i2), range(j1, j2)):
                pairs.append(AlignedPair(
                    left=left_blocks[li],
                    right=right_blocks[ri],
                    status=PairStatus.EQUAL,
                    similarity=1.0,
                ))
        elif tag == "replace":
            _align_gap(left_blocks[i1:i2], right_blocks[j1:j2], pairs)
        elif tag == "delete":
            for li in range(i1, i2):
                pairs.append(AlignedPair(
                    left=left_blocks[li],
                    right=None,
                    status=PairStatus.LEFT_ONLY,
                    similarity=0.0,
                ))
        elif tag == "insert":
            for ri in range(j1, j2):
                pairs.append(AlignedPair(
                    left=None,
                    right=right_blocks[ri],
                    status=PairStatus.RIGHT_ONLY,
                    similarity=0.0,
                ))

    return pairs


def _align_gap(
    left_gap: list[Block],
    right_gap: list[Block],
    pairs: list[AlignedPair],
) -> None:
    """Align unmatched blocks within a gap using type + similarity."""
    li = 0
    ri = 0
    while li < len(left_gap) and ri < len(right_gap):
        lb = left_gap[li]
        rb = right_gap[ri]

        if lb.block_type == rb.block_type:
            sim = _text_similarity(lb.normalized, rb.normalized)
            if sim > 0.3:
                wd_left, wd_right = word_diff(lb.text, rb.text)
                pairs.append(AlignedPair(
                    left=lb, right=rb,
                    status=PairStatus.CHANGED,
                    similarity=sim,
                    word_diff_left=wd_left,
                    word_diff_right=wd_right,
                ))
                li += 1
                ri += 1
                continue

        # Type mismatch or low similarity: emit as separate
        if li <= ri:
            pairs.append(AlignedPair(left=lb, right=None, status=PairStatus.LEFT_ONLY))
            li += 1
        else:
            pairs.append(AlignedPair(left=None, right=rb, status=PairStatus.RIGHT_ONLY))
            ri += 1

    while li < len(left_gap):
        pairs.append(AlignedPair(left=left_gap[li], right=None, status=PairStatus.LEFT_ONLY))
        li += 1
    while ri < len(right_gap):
        pairs.append(AlignedPair(left=None, right=right_gap[ri], status=PairStatus.RIGHT_ONLY))
        ri += 1


def align_documents(
    left_md: str,
    right_md: str,
    *,
    left_label: str = "left",
    right_label: str = "right",
) -> AlignedDocument:
    """Parse and align two Markdown documents end-to-end.

    Returns an AlignedDocument whose pairs list is consumable by
    both the HTML and PDF renderers.
    """
    left_blocks = parse_blocks(left_md)
    right_blocks = parse_blocks(right_md)
    pairs = align_blocks(left_blocks, right_blocks)

    return AlignedDocument(
        left_label=left_label,
        right_label=right_label,
        pairs=pairs,
        left_blocks=left_blocks,
        right_blocks=right_blocks,
    )
