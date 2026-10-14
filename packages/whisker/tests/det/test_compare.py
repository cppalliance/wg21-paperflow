#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for whisker.det.compare block parsing and alignment."""

from whisker.det.compare.align import (
    PairStatus,
    align_documents,
    word_diff,
)
from whisker.det.compare.blocks import Block, BlockType, parse_blocks


class TestBlockParsing:
    """Verify that parse_blocks correctly identifies structural types."""

    def test_empty_document(self):
        assert parse_blocks("") == []

    def test_single_heading(self):
        blocks = parse_blocks("## Hello World")
        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.HEADING
        assert blocks[0].level == 2
        assert blocks[0].text == "## Hello World"

    def test_paragraph(self):
        blocks = parse_blocks("This is a paragraph.\nWith two lines.")
        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.PARAGRAPH

    def test_fenced_code_block(self):
        md = "```cpp\nint main() {\n  return 0;\n}\n```"
        blocks = parse_blocks(md)
        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.CODE
        assert "int main()" in blocks[0].text

    def test_pipe_table(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        blocks = parse_blocks(md)
        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.TABLE

    def test_unordered_list(self):
        md = "- item one\n- item two\n- item three"
        blocks = parse_blocks(md)
        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.LIST

    def test_ordered_list(self):
        md = "1. first\n2. second\n3. third"
        blocks = parse_blocks(md)
        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.LIST

    def test_blockquote(self):
        md = "> This is a quote\n> spanning two lines"
        blocks = parse_blocks(md)
        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.QUOTE

    def test_thematic_break(self):
        blocks = parse_blocks("---")
        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.THEMATIC_BREAK

    def test_mixed_document(self):
        md = """## Title

Some paragraph text.

```python
print("hello")
```

| Col1 | Col2 |
|------|------|
| a    | b    |

- list item"""
        blocks = parse_blocks(md)
        types = [b.block_type for b in blocks]
        assert types == [
            BlockType.HEADING,
            BlockType.PARAGRAPH,
            BlockType.CODE,
            BlockType.TABLE,
            BlockType.LIST,
        ]

    def test_line_numbers_are_correct(self):
        md = "## Heading\n\nParagraph\n\n```\ncode\n```"
        blocks = parse_blocks(md)
        assert blocks[0].start_line == 0
        assert blocks[0].end_line == 0
        assert blocks[1].start_line == 2
        assert blocks[2].block_type == BlockType.CODE
        assert blocks[2].start_line == 4

    def test_normalized_property(self):
        block = Block(BlockType.PARAGRAPH, "  Hello   World  ", 0, 0)
        assert block.normalized == "hello world"


class TestWordDiff:
    """Verify word-level diffing."""

    def test_identical_texts(self):
        left, right = word_diff("hello world", "hello world")
        assert len(left) == 1
        assert left[0].tag == "equal"
        assert left[0].text == "hello world"

    def test_deletion(self):
        left, right = word_diff("a b c", "a c")
        tags_l = [s.tag for s in left]
        assert "delete" in tags_l

    def test_insertion(self):
        left, right = word_diff("a c", "a b c")
        tags_r = [s.tag for s in right]
        assert "insert" in tags_r

    def test_empty_inputs(self):
        left, right = word_diff("", "")
        assert left == []
        assert right == []


class TestBlockAlignment:
    """Verify structural block alignment."""

    def test_identical_documents(self):
        md = "## Title\n\nParagraph text."
        doc = align_documents(md, md, left_label="a", right_label="b")
        assert doc.equal_pairs == doc.total_pairs
        assert doc.changed_pairs == 0

    def test_heading_change(self):
        left = "## Original Title\n\nContent."
        right = "## Modified Title\n\nContent."
        doc = align_documents(left, right)
        statuses = [p.status for p in doc.pairs]
        assert PairStatus.CHANGED in statuses or PairStatus.LEFT_ONLY in statuses

    def test_added_block(self):
        left = "## Title\n\nParagraph."
        right = "## Title\n\nParagraph.\n\n## New Section\n\nNew content."
        doc = align_documents(left, right)
        assert doc.total_pairs > 2
        statuses = [p.status for p in doc.pairs]
        assert PairStatus.RIGHT_ONLY in statuses

    def test_removed_block(self):
        left = "## Title\n\nParagraph.\n\n## Removed\n\nOld content."
        right = "## Title\n\nParagraph."
        doc = align_documents(left, right)
        statuses = [p.status for p in doc.pairs]
        assert PairStatus.LEFT_ONLY in statuses

    def test_labels_propagate(self):
        doc = align_documents("# A", "# A", left_label="tomd", right_label="marker")
        assert doc.left_label == "tomd"
        assert doc.right_label == "marker"

    def test_type_preserving_alignment(self):
        left = "## H1\n\n```\ncode\n```\n\nParagraph."
        right = "## H1\n\n```\nmodified code\n```\n\nParagraph."
        doc = align_documents(left, right)
        for pair in doc.pairs:
            if pair.left and pair.right:
                assert pair.left.block_type == pair.right.block_type

    def test_similarity_score_range(self):
        left = "## Title\n\nSome text here."
        right = "## Title\n\nCompletely different content that shares nothing."
        doc = align_documents(left, right)
        for pair in doc.pairs:
            assert 0.0 <= pair.similarity <= 1.0
