"""Tests for lib.pdf.extract."""

import pytest
from unittest.mock import MagicMock
from tomd.lib.pdf.extract import extract_spatial, attach_links
from tomd.lib.pdf.types import Span, Line, Block, compute_bbox


def _make_page(chars_by_span):
    """Build a mock page whose rawdict returns chars grouped by span.

    chars_by_span: list of (font, size, [(char, x0, y0, x1, y1), ...])
    """
    spans = []
    for font, size, char_list in chars_by_span:
        chars = []
        for c, x0, y0, x1, y1 in char_list:
            chars.append({
                "c": c,
                "bbox": (x0, y0, x1, y1),
                "origin": (x0, y0),
            })
        spans.append({
            "font": font,
            "size": size,
            "flags": 0,
            "color": 0,
            "chars": chars,
        })
    page = MagicMock()
    page.get_text.return_value = {
        "blocks": [{
            "type": 0,
            "lines": [{"spans": spans}],
        }],
    }
    return page


def _make_page_with_blocks(block_char_order):
    """Mock a fitz page whose rawdict iterates blocks in the given order.

    block_char_order is a list of lists of (c, x, y) tuples. Each outer
    list element becomes one block, iterated in that order.
    """
    blocks = []
    for chars in block_char_order:
        block_chars = [
            {"c": c, "bbox": (x, y, x + 5, y + 10), "origin": (x, y + 10)}
            for c, x, y in chars
        ]
        blocks.append({
            "type": 0,
            "lines": [{
                "spans": [{
                    "font": "TestFont",
                    "size": 10.0,
                    "flags": 0,
                    "color": 0,
                    "chars": block_chars,
                }],
            }],
        })
    page = MagicMock()
    page.get_text.return_value = {"blocks": blocks}
    return page


def test_spatial_sorts_by_x_within_same_y():
    """Chars at the same y but reversed x-order should come out left-to-right."""
    page = _make_page([
        ("Font", 12.0, [
            ("B", 100.0, 10.0, 112.0, 22.0),
            ("A", 10.0, 10.0, 22.0, 22.0),
        ]),
    ])
    blocks = extract_spatial(page, 0)
    full_text = " ".join(ln.text for b in blocks for ln in b.lines)
    assert full_text.index("A") < full_text.index("B")


def test_extract_spatial_sorts_across_blocks_in_y_band():
    """Two blocks at the same y with reversed x ranges must be merged
    in left-to-right reading order regardless of rawdict iteration order.
    """
    # Block B is iterated first but sits to the right of block A.
    page = _make_page_with_blocks([
        [("R", 300, 100), ("I", 310, 100), ("G", 320, 100), ("H", 330, 100), ("T", 340, 100)],
        [("L", 50, 100), ("E", 60, 100), ("F", 70, 100), ("T", 80, 100)],
    ])
    blocks = extract_spatial(page, page_num=0)
    text = "".join(
        span.text for block in blocks for line in block.lines for span in line.spans
    )
    # The left block's characters must come first in the output.
    assert text.index("L") < text.index("R"), f"got text={text!r}"


def test_spatial_sorts_by_baseline_for_mixed_font_sizes():
    """Inline run in a smaller font shares baseline but has lower bbox top;
    must still sort in reading order before text on the next line."""
    # Line 1: Prose "a" at 14pt (origin y=100, bbox top y=87, x=10)
    # followed by inline code "x" at 8pt (origin y=100, bbox top y=94, x=30).
    # Line 2: Prose "b" at 14pt (origin y=113, bbox top y=99, x=10).
    #
    # With bbox-top sorting, "x" (bbox top 94) and "b" (bbox top 99) fall into
    # the same sort band (band 15), where "b" (x=10) sorts before "x" (x=30),
    # corrupting reading order to ["a", "b", "x"].
    # With baseline (origin y) sorting, "a" and "x" share baseline y=100 (band 15)
    # and sort before "b" (baseline y=113, band 17).
    spans = [
        {
            "font": "ProseFont",
            "size": 14.0,
            "flags": 0,
            "color": 0,
            "chars": [
                {"c": "a", "bbox": (10, 87, 18, 102), "origin": (10, 100)},
            ],
        },
        {
            "font": "CodeFont",
            "size": 8.0,
            "flags": 0,
            "color": 0,
            "chars": [
                {"c": "x", "bbox": (30, 94, 36, 102), "origin": (30, 100)},
            ],
        },
        {
            "font": "ProseFont",
            "size": 14.0,
            "flags": 0,
            "color": 0,
            "chars": [
                {"c": "b", "bbox": (10, 99, 18, 115), "origin": (10, 113)},
            ],
        },
    ]
    page = MagicMock()
    page.get_text.return_value = {
        "blocks": [{"type": 0, "lines": [{"spans": spans}]}],
    }
    blocks = extract_spatial(page, 0)
    words = [w for b in blocks for ln in b.lines for w in ln.text.split()]
    assert words == ["a", "x", "b"]






class TestComputeBbox:
    def test_single_box(self):
        assert compute_bbox([(1.0, 2.0, 3.0, 4.0)]) == (1.0, 2.0, 3.0, 4.0)

    def test_multiple_boxes(self):
        result = compute_bbox([(10, 20, 30, 40), (5, 25, 35, 38)])
        assert result == (5, 20, 35, 40)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            compute_bbox([])


def _make_block_with_span(text, bbox):
    span = Span(text=text, bbox=bbox)
    line = Line(spans=[span])
    return Block(lines=[line]), span


class TestAttachLinks:
    def test_best_overlap_wins(self):
        """Link is assigned to the span with the greatest overlap area."""
        block_a, span_a = _make_block_with_span("hello", (10, 10, 100, 20))
        block_b, span_b = _make_block_with_span("world", (200, 10, 300, 20))
        link = {"uri": "https://example.com", "bbox": (5, 8, 110, 22)}
        attach_links([block_a, block_b], [link])
        assert span_a.link_url == "https://example.com"
        assert span_b.link_url is None

    def test_multiple_links_each_win_their_best_span(self):
        """Each link independently assigns to its own best-overlap span."""
        block_a, span_a = _make_block_with_span("hello", (10, 10, 100, 20))
        block_b, span_b = _make_block_with_span("world", (200, 10, 300, 20))
        link_a = {"uri": "https://a.com", "bbox": (5, 8, 110, 22)}
        link_b = {"uri": "https://b.com", "bbox": (195, 8, 305, 22)}
        attach_links([block_a, block_b], [link_a, link_b])
        assert span_a.link_url == "https://a.com"
        assert span_b.link_url == "https://b.com"

    def test_later_link_overwrites_if_better_overlap(self):
        """A later link with larger overlap replaces an earlier assignment."""
        block, span = _make_block_with_span("text", (10, 10, 100, 20))
        small_link = {"uri": "https://small.com", "bbox": (10, 10, 50, 20)}
        big_link = {"uri": "https://big.com", "bbox": (5, 8, 110, 22)}
        attach_links([block], [small_link, big_link])
        assert span.link_url == "https://big.com"

    def test_no_overlap_no_assignment(self):
        """A link entirely outside all spans leaves link_url unchanged."""
        block, span = _make_block_with_span("text", (10, 10, 100, 20))
        link = {"uri": "https://far.com", "bbox": (500, 500, 600, 510)}
        attach_links([block], [link])
        assert span.link_url is None
