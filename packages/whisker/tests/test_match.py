#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from whisker.match import (
    block_text_nid,
    match_blocks,
    reading_order_ned,
    split_paragraph_blocks,
)

_P1 = "The first paragraph talks about allocators and lifetime bounds in detail."
_P2 = "A second paragraph covers coroutine promise types and their guarantees."
_P3 = "Finally the third paragraph discusses constexpr evaluation of the model."


def test_split_skips_fenced_code_and_blank_lines():
    md = f"{_P1}\n\n```cpp\nint x = 1;\n\nint y = 2;\n```\n\n{_P2}\n"
    blocks = split_paragraph_blocks(md)
    assert blocks == [_P1, _P2]


def test_split_groups_wrapped_lines_into_one_block():
    md = "line one\nline two\n\nseparate block\n"
    assert split_paragraph_blocks(md) == ["line one\nline two", "separate block"]


def test_block_nid_identical_is_one():
    md = f"{_P1}\n\n{_P2}\n\n{_P3}\n"
    assert block_text_nid(md, md) == 1.0


def test_block_nid_is_reorder_robust():
    # Same three paragraphs, different order. Block matching pairs each with its
    # twin regardless of position, so agreement stays perfect: this is the whole
    # reason for block matching over the order-sensitive full-document nid.
    a = f"{_P1}\n\n{_P2}\n\n{_P3}\n"
    b = f"{_P3}\n\n{_P1}\n\n{_P2}\n"
    assert block_text_nid(a, b) == 1.0


def test_block_nid_both_empty_is_one():
    assert block_text_nid("", "") == 1.0


def test_block_nid_no_alignment_is_zero():
    # Disjoint content: nothing matches within the accept threshold -> 0.0.
    a = "alpha beta gamma delta epsilon zeta eta theta content here.\n"
    b = "完全に違う日本語のテキストがここにあります全く異なる内容。\n"
    assert block_text_nid(a, b) == 0.0


def test_block_nid_partial_text_change_between_zero_and_one():
    a = f"{_P1}\n\n{_P2}\n"
    b = f"{_P1}\n\nA second paragraph covers something entirely unrelated now.\n"
    score = block_text_nid(a, b)
    assert 0.0 < score < 1.0


def test_fuzzy_rescue_matches_embedded_gt_block():
    # GT block is embedded verbatim inside a longer pred block: the Hungarian
    # pass may not pair them (high NED from the extra text), but the < 0.40 fuzzy
    # rescue should, so the pair is counted.
    gt = ["allocators and lifetime bounds matter here greatly indeed yes"]
    pred = [
        "PREAMBLE TEXT. allocators and lifetime bounds matter here greatly "
        "indeed yes. TRAILING UNRELATED COMMENTARY THAT MAKES THIS MUCH LONGER."
    ]
    matches = match_blocks(gt, pred, normalize=lambda s: s)
    assert len(matches) == 1
    assert matches[0].gt_index == 0


def test_reading_order_ned_same_order_is_zero():
    md = f"{_P1}\n\n{_P2}\n\n{_P3}\n"
    matches = match_blocks(
        split_paragraph_blocks(md), split_paragraph_blocks(md), normalize=lambda s: s
    )
    assert reading_order_ned(matches) == 0.0


def test_reading_order_ned_detects_reordering():
    a = f"{_P1}\n\n{_P2}\n\n{_P3}\n"
    b = f"{_P3}\n\n{_P2}\n\n{_P1}\n"
    matches = match_blocks(
        split_paragraph_blocks(a), split_paragraph_blocks(b), normalize=lambda s: s
    )
    # Same blocks, fully reversed order -> non-zero reading-order disagreement.
    assert reading_order_ned(matches) > 0.0


def test_match_blocks_is_deterministic():
    a = f"{_P1}\n\n{_P2}\n\n{_P3}\n"
    b = f"{_P2}\n\n{_P3}\n\n{_P1}\n"
    m1 = match_blocks(split_paragraph_blocks(a), split_paragraph_blocks(b))
    m2 = match_blocks(split_paragraph_blocks(a), split_paragraph_blocks(b))
    assert [(m.gt_index, m.pred_indices) for m in m1] == [(m.gt_index, m.pred_indices) for m in m2]
