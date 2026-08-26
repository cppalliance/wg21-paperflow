"""Tests for lib.pdf.wording."""

from unittest.mock import MagicMock

import pytest

from conftest import make_block
from tomd.lib.pdf.types import Span, Line, Block
from tomd.lib.pdf.wording import (
    _is_wording_color,
    classify_wording,
    collect_line_drawings,
    is_green_ins,
    is_red_del,
    is_wording_rgb,
)


def _color(r, g, b):
    """Convert 0-255 RGB to MuPDF integer color."""
    return (r << 16) | (g << 8) | b


_GREEN = _color(0, 133, 71)
_RED = _color(204, 0, 0)
_BLUE = _color(5, 85, 193)
_PURPLE = _color(128, 0, 128)


def _green_block(n=6, text="added text", bbox=(10, 50, 200, 60)):
    """Block of n lines, each a single green span with explicit bbox."""
    spans = [Span(text=f"{text} {i}", color=_GREEN, bbox=bbox) for i in range(n)]
    lines = [Line(spans=[s]) for s in spans]
    return Block(lines=lines, page_num=0)


def _red_block(n=6, text="removed text", bbox=(10, 50, 200, 60)):
    """Block of n lines, each a single red span with explicit bbox."""
    spans = [Span(text=f"{text} {i}", color=_RED, bbox=bbox) for i in range(n)]
    lines = [Line(spans=[s]) for s in spans]
    return Block(lines=lines, page_num=0)


def _strikethrough_at(y, x0=10, x1=200):
    """Drawings dict with a single strikethrough line."""
    return {0: [(y, x0, x1, (0.8, 0, 0))]}


class TestMatchStrikethrough:
    def test_del_classified_with_matching_drawing(self):
        block = _red_block()
        # Strikethrough at span vertical center: (50+60)/2 = 55
        problems = classify_wording([block], _strikethrough_at(55))
        assert block.lines[0].spans[0].wording_role == "del"
        assert len(problems) == 0

    def test_del_not_classified_without_drawing(self):
        block = _red_block()
        problems = classify_wording([block], {})
        assert all(s.wording_role is None for ln in block.lines for s in ln.spans)

    def test_del_not_classified_when_drawing_out_of_range(self):
        block = _red_block()
        # y=48, center=55, distance=7 > _STRIKETHROUGH_Y_TOLERANCE=2.0
        problems = classify_wording([block], _strikethrough_at(48))
        assert all(s.wording_role is None for ln in block.lines for s in ln.spans)

    def test_del_not_classified_when_drawing_too_narrow(self):
        # Drawing width=5, span width=190 -> overlap fraction 5/190 < 0.3
        block = _red_block(bbox=(10, 50, 200, 60))
        narrow_drawings = {0: [(55, 10, 15, (0.8, 0, 0))]}
        problems = classify_wording([block], narrow_drawings)
        assert all(s.wording_role is None for ln in block.lines for s in ln.spans)

    def test_del_classified_with_fragmented_strikethrough(self):
        """A strike drawn as several short collinear segments still confirms del.

        WG21 renderers often emit one strike segment per sub-word, so no
        single segment reaches the 30% coverage bar; merged coverage does.
        """
        span = Span(text="removed", color=_RED, bbox=(10, 50, 210, 60))
        block = Block(lines=[Line(spans=[span])], page_num=0)
        # Four 40px segments at the span center (y=55). Each is 40/200=0.2
        # of the span width (< 0.3), but merged they cover 80%.
        segs = [(55, 10, 50, (0.8, 0, 0)), (55, 50, 90, (0.8, 0, 0)),
                (55, 90, 130, (0.8, 0, 0)), (55, 130, 170, (0.8, 0, 0))]
        classify_wording([block], {0: segs})
        assert span.wording_role == "del"


class TestInsClassification:
    def test_ins_classified_without_drawing(self):
        # Green spans are classified as ins even without underline drawing
        block = _green_block()
        problems = classify_wording([block], {})
        assert block.lines[0].spans[0].wording_role == "ins"
        assert len(problems) == 0

    def test_ins_classified_with_drawing(self):
        block = _green_block()
        underline = {0: [(60.5, 10, 200, (0, 0.5, 0))]}
        problems = classify_wording([block], underline)
        assert block.lines[0].spans[0].wording_role == "ins"
        assert len(problems) == 0

    def test_ins_high_confidence_no_problems(self):
        block = _green_block(n=10)
        problems = classify_wording([block], {})
        assert len(problems) == 0


class TestMajorityFilter:
    def test_minority_red_not_classified(self):
        """A few red words on an otherwise black line are not del."""
        black = Span(text="normal text normal text normal text", color=0,
                     bbox=(0, 50, 350, 60))
        red_link = Span(text="link", color=_RED, bbox=(350, 50, 390, 60))
        line = Line(spans=[black, red_link])
        block = Block(lines=[line] * 6, page_num=0)
        classify_wording([block], _strikethrough_at(55))
        assert all(s.wording_role is None for ln in block.lines for s in ln.spans)

    def test_minority_green_on_black_classified(self):
        """Green span on an otherwise-black line is wording (partial-line pattern)."""
        black = Span(text="the function returns the value", color=0,
                     bbox=(0, 50, 300, 60))
        green_code = Span(text="T", color=_GREEN, bbox=(300, 50, 315, 60))
        line = Line(spans=[black, green_code])
        block = Block(lines=[line] * 6, page_num=0)
        classify_wording([block], {})
        assert any(s.wording_role == "ins" for ln in block.lines for s in ln.spans)

    def test_majority_green_line_classified(self):
        """When most of a line is green, it's wording ins."""
        green = Span(text="void f(int x) { return x; }", color=_GREEN,
                     bbox=(10, 50, 250, 60))
        black = Span(text=" //", color=0, bbox=(250, 50, 280, 60))
        line = Line(spans=[green, black])
        block = Block(lines=[line] * 6, page_num=0)
        classify_wording([block], {})
        assert green.wording_role == "ins"


class TestForeignColorFilter:
    def test_purple_span_disqualifies_block(self):
        """Block with purple text (syntax highlighting) is skipped."""
        green = Span(text="added text", color=_GREEN, bbox=(10, 50, 200, 60))
        purple = Span(text="keyword", color=_PURPLE, bbox=(200, 50, 270, 60))
        line = Line(spans=[green, purple])
        block = Block(lines=[line] * 6, page_num=0)
        classify_wording([block], {})
        assert all(s.wording_role is None for ln in block.lines for s in ln.spans)

    def test_blue_link_does_not_disqualify_block(self):
        """Blue hyperlinks (link_url set) do not contaminate the block check."""
        green = Span(text="added text added text", color=_GREEN, bbox=(10, 50, 200, 60))
        blue_link = Span(text="[dcl.type]", color=_BLUE, bbox=(200, 50, 270, 60),
                         link_url="https://eel.is/c++draft/dcl.type")
        line = Line(spans=[green, blue_link])
        block = Block(lines=[line] * 6, page_num=0)
        classify_wording([block], {})
        assert green.wording_role == "ins"

    def test_blue_non_link_does_not_disqualify(self):
        """Blue non-link text is allowed (cross-references without link annotation)."""
        green = Span(text="added text added text", color=_GREEN, bbox=(10, 50, 200, 60))
        blue = Span(text="[dcl.type]", color=_BLUE, bbox=(200, 50, 270, 60))
        line = Line(spans=[green, blue])
        block = Block(lines=[line] * 6, page_num=0)
        classify_wording([block], {})
        assert green.wording_role == "ins"

    def test_green_comment_not_counted_as_ins(self):
        """A green comment span is syntax highlighting and must not become ins."""
        code = Span(text="int x = 42;", color=0, bbox=(10, 50, 100, 60))
        green_comment = Span(text="// some comment", color=_GREEN, bbox=(110, 50, 200, 60))
        line = Line(spans=[code, green_comment])
        block = Block(lines=[line] * 6, page_num=0)
        classify_wording([block], {})
        assert green_comment.wording_role is None
        assert all(s.wording_role is None for ln in block.lines for s in ln.spans)

    def test_confirmed_strikethrough_overrides_foreign_filter(self):
        """A struck deletion inside syntax-highlighted code is still detected.

        The block carries a foreign (olive) syntax color, which would
        normally skip it, but a red span with a confirmed strikethrough is
        an unambiguous deletion: detect it (and the paired insertion) even
        though there are only two wording spans, below _MIN_WORDING_SPANS.
        """
        olive = Span(text="using", color=_color(130, 123, 0), bbox=(10, 50, 50, 60))
        red = Span(text="native_simd", color=_RED, bbox=(60, 50, 160, 60))
        green = Span(text="simd::vec", color=_GREEN, bbox=(160, 50, 240, 60))
        line = Line(spans=[olive, red, green])
        block = Block(lines=[line], page_num=0)
        strike = {0: [(55, 60, 160, (0.8, 0, 0))]}
        classify_wording([block], strike)
        assert red.wording_role == "del"
        assert green.wording_role == "ins"
        assert olive.wording_role is None

    def test_lone_struck_token_on_highlighted_line_classified(self):
        """A single struck token amid syntax-highlighted code is detected.

        The line is a minority edit (one red `2` struck, one green
        insertion) sitting in olive/black code, so it fails both the
        majority and partial-line gates; the confirmed strikethrough
        qualifies the line on its own.
        """
        floatv = Span(text="floatv f(floatv x) { return x * ", color=0,
                      bbox=(10, 50, 200, 60))
        olive = Span(text="keyword", color=_color(130, 123, 0), bbox=(200, 50, 230, 60))
        struck = Span(text="2", color=_RED, bbox=(230, 50, 234, 60))
        green = Span(text="std::cw<2>", color=_GREEN, bbox=(234, 50, 320, 60))
        tail = Span(text="; }", color=0, bbox=(320, 50, 340, 60))
        line = Line(spans=[floatv, olive, struck, green, tail])
        block = Block(lines=[line], page_num=0)
        # 3px strike centered on the narrow `2` span (width 4).
        strike = {0: [(55, 230.5, 233.5, (0.8, 0, 0))]}
        classify_wording([block], strike)
        assert struck.wording_role == "del"
        assert green.wording_role == "ins"
        assert olive.wording_role is None

    def test_foreign_block_without_strikethrough_still_skipped(self):
        """Foreign-color code with a red token but no strike stays unclassified.

        Guards the exemption: only a confirmed strikethrough overrides the
        filter. A red syntax token (no rule drawn through it) must not be
        misread as a deletion.
        """
        olive = Span(text="using", color=_color(130, 123, 0), bbox=(10, 50, 50, 60))
        red = Span(text="native_simd", color=_RED, bbox=(60, 50, 160, 60))
        green = Span(text="simd::vec", color=_GREEN, bbox=(160, 50, 240, 60))
        line = Line(spans=[olive, red, green])
        block = Block(lines=[line], page_num=0)
        classify_wording([block], {})
        assert all(s.wording_role is None for ln in block.lines for s in ln.spans)


class TestThreshold:
    def test_below_min_spans_no_classification(self):
        """Fewer than _MIN_WORDING_SPANS ins/del spans → nothing classified."""
        block = _green_block(n=3)
        classify_wording([block], {})
        assert all(s.wording_role is None for ln in block.lines for s in ln.spans)

    def test_black_spans_not_classified(self):
        blocks = [make_block(["normal text"] * 10, page_num=0)]
        classify_wording(blocks, {})
        assert all(s.wording_role is None
                   for ln in blocks[0].lines for s in ln.spans)

    def test_blue_spans_not_classified(self):
        block = Block(
            lines=[Line(spans=[Span(text="link text", color=_BLUE,
                                   bbox=(10, 50, 200, 60))]) for _ in range(10)],
            page_num=0,
        )
        classify_wording([block], {})
        assert all(s.wording_role is None for ln in block.lines for s in ln.spans)


class TestCollectLineDrawings:
    def _make_page(self, drawings):
        page = MagicMock()
        page.get_drawings.return_value = drawings
        return page

    def _make_drawing(self, x0, y0, x1, y1, color=(0.0, 0.5, 0.0)):
        """Build a minimal drawing dict with a single 'l' (line) item."""
        p1 = MagicMock()
        p1.x, p1.y = x0, y0
        p2 = MagicMock()
        p2.x, p2.y = x1, y1
        return {"items": [("l", p1, p2)], "color": color}

    def test_horizontal_line_collected(self):
        drawing = self._make_drawing(10, 50, 200, 50)
        page = self._make_page([drawing])
        result = collect_line_drawings(page)
        assert len(result) == 1
        y, x0, x1, color = result[0]
        assert abs(y - 50) < 0.1
        assert x0 == 10
        assert x1 == 200

    def test_short_line_filtered_out(self):
        """Lines <= 3 px wide are discarded as noise."""
        drawing = self._make_drawing(10, 50, 12, 50)
        page = self._make_page([drawing])
        assert collect_line_drawings(page) == []

    def test_single_glyph_strike_collected(self):
        """A ~4px rule (a strikethrough over one narrow glyph) is kept."""
        drawing = self._make_drawing(10, 50, 14.9, 50)
        page = self._make_page([drawing])
        assert len(collect_line_drawings(page)) == 1

    def test_diagonal_line_filtered_out(self):
        """Lines with |dy| >= 1 are not horizontal and are discarded."""
        drawing = self._make_drawing(10, 50, 200, 52)
        page = self._make_page([drawing])
        assert collect_line_drawings(page) == []

    def test_get_drawings_exception_returns_empty(self):
        """If get_drawings() raises, degrade gracefully and return []."""
        page = MagicMock()
        page.get_drawings.side_effect = RuntimeError("MuPDF internal error")
        assert collect_line_drawings(page) == []

    def test_no_color_drawing_skipped(self):
        """Drawings without a color tuple are skipped."""
        p1 = MagicMock()
        p1.x, p1.y = 10, 50
        p2 = MagicMock()
        p2.x, p2.y = 200, 50
        drawing = {"items": [("l", p1, p2)], "color": None}
        page = self._make_page([drawing])
        assert collect_line_drawings(page) == []


class TestTwoPassDeletion:
    """Two-pass del classification: red without strikethrough promoted when ins present."""

    def test_del_classified_without_strikethrough_when_ins_present(self):
        """Red spans without strikethrough are promoted to del when enough green ins exist."""
        green_spans = [Span(text=f"added {i}", color=_GREEN, bbox=(10, 50, 200, 60))
                       for i in range(6)]
        red_spans = [Span(text=f"removed {i}", color=_RED, bbox=(10, 70, 200, 80))
                     for i in range(3)]
        green_lines = [Line(spans=[s]) for s in green_spans]
        red_lines = [Line(spans=[s]) for s in red_spans]
        block = Block(lines=green_lines + red_lines, page_num=0)

        classify_wording([block], {})

        for s in green_spans:
            assert s.wording_role == "ins"
        for s in red_spans:
            assert s.wording_role == "del", (
                "red without strikethrough should be promoted to del "
                "when sufficient ins context exists"
            )

    def test_del_not_classified_without_strikethrough_when_no_ins(self):
        """Red spans without strikethrough are dropped when no green ins exist."""
        red_spans = [Span(text=f"removed {i}", color=_RED, bbox=(10, 50, 200, 60))
                     for i in range(6)]
        lines = [Line(spans=[s]) for s in red_spans]
        block = Block(lines=lines, page_num=0)

        classify_wording([block], {})

        for s in red_spans:
            assert s.wording_role is None, (
                "red without strikethrough should NOT be classified "
                "when no ins context exists"
            )


class TestRedCommentNotDeletion:
    """A red `//` code comment is syntax highlighting, never a deletion.

    Reproduces P0876R22: a single red `// hypothetical API` comment in
    an otherwise-black monospace listing was promoted to <del> once the
    document carried enough green insertions (two-pass promotion),
    flipping the whole code block into a wording diff.
    """

    def _ins_context_block(self):
        green = [Span(text=f"added {i}", color=_GREEN, bbox=(10, 50, 200, 60))
                 for i in range(6)]
        return Block(lines=[Line(spans=[s]) for s in green], page_num=0)

    def test_red_comment_line_not_promoted_to_deletion(self):
        comment_spans = [
            Span(text="// ", color=_RED, monospace=True, bbox=(10, 70, 30, 80)),
            Span(text="hypothetical API", color=_RED, monospace=True,
                 bbox=(30, 70, 200, 80)),
        ]
        code_block = Block(
            lines=[
                Line(spans=comment_spans),
                Line(spans=[Span(text="fiber_context f4{[]{", color=0,
                                 monospace=True, bbox=(10, 90, 200, 100))]),
            ],
            page_num=0,
        )
        classify_wording([self._ins_context_block(), code_block], {})
        for s in comment_spans:
            assert s.wording_role is None, (
                "a red // comment must not be classified as a deletion"
            )

    def test_red_token_in_code_is_still_deletion(self):
        # A red identifier amid black code (not a comment) is a genuine
        # deletion and must still be promoted (p1068r11 / p2040r0).
        line = Line(spans=[
            Span(text="const size_t ", color=0, monospace=True,
                 bbox=(10, 70, 90, 80)),
            Span(text="__j", color=_RED, monospace=True, bbox=(90, 70, 110, 80)),
            Span(text=" = i;", color=0, monospace=True, bbox=(110, 70, 160, 80)),
        ])
        block = Block(lines=[line], page_num=0)
        classify_wording([self._ins_context_block(), block], {})
        assert line.spans[1].wording_role == "del"

    def test_struck_red_comment_is_still_deletion(self):
        # A comment that is actually struck through is a real deletion;
        # the comment guard only applies in the absence of a strike.
        comment = Span(text="// old note", color=_RED, monospace=True,
                       bbox=(10, 50, 200, 60))
        block = Block(lines=[Line(spans=[comment])], page_num=0)
        classify_wording([block], {0: [(55, 10, 200, (0.8, 0, 0))]})
        assert comment.wording_role == "del"


def _hsv_grid(step: int = 4):
    """Yield packed-int colors sampling the HSV cube at the requested grid resolution."""
    samples = []
    levels = [int(255 * i / (step - 1)) for i in range(step)]
    for r in levels:
        for g in levels:
            for b in levels:
                samples.append((r << 16) | (g << 8) | b)
    return samples


class TestWordingPredicateEquivalence:
    """is_wording_color (packed int) and is_wording_rgb (float tuple) agree
    everywhere, and both equal the disjunction of is_green_ins / is_red_del.

    Pins the shared-helper refactor: the band logic lives in
    _in_green_band / _in_red_band, and all four predicates delegate to
    them. A drift between the packed-int and float-tuple paths would
    silently break vector_images.py's pre-clustering exclusion (which
    consumes pymupdf's float-tuple color output).
    """

    @pytest.mark.parametrize("packed", [
        0x000000,  # black
        0x006e28,  # mpark/wg21 ins green
        0xbf0303,  # mpark/wg21 del red
        0x008019,  # tcbrindle ins green
        0xff0000,  # tcbrindle del / cplusplus draft del
        0x009999,  # cplusplus draft ins (teal at H=180)
        0x17752d,  # schultke ins
        0xbe1621,  # schultke del (H=355, red-wrap)
        0x808080,  # achromatic gray
        0x800080,  # purple (code-syntax)
        0x00ff00,  # pure green
        0xff8000,  # orange
        0x0000ff,  # pure blue (link)
        *_hsv_grid(step=4),
    ])
    def test_predicates_agree_across_int_and_rgb_paths(self, packed: int):
        r = ((packed >> 16) & 0xFF) / 255.0
        g = ((packed >> 8) & 0xFF) / 255.0
        b = (packed & 0xFF) / 255.0
        int_result = _is_wording_color(packed)
        rgb_result = is_wording_rgb(r, g, b)
        component_result = is_green_ins(packed) or is_red_del(packed)
        assert int_result == rgb_result == component_result


class TestIsWordingRgb:
    """Direct float-tuple coverage so the float path is exercised even
    if a future refactor changes how the packed-int path computes HSV."""

    def test_mpark_ins_green_is_wording(self):
        # #006e28 -> (0.0, 0.43, 0.16) (rounded to two decimals)
        assert is_wording_rgb(0.0, 110.0 / 255.0, 40.0 / 255.0) is True

    def test_mpark_del_red_is_wording(self):
        # #bf0303 -> (0.75, 0.01, 0.01)
        assert is_wording_rgb(191.0 / 255.0, 3.0 / 255.0, 3.0 / 255.0) is True

    def test_code_syntax_purple_is_not_wording(self):
        # (0.5, 0.0, 0.5) - outside both hue bands
        assert is_wording_rgb(0.5, 0.0, 0.5) is False

    def test_black_is_not_wording(self):
        assert is_wording_rgb(0.0, 0.0, 0.0) is False

    def test_pure_blue_link_is_not_wording(self):
        assert is_wording_rgb(0.0, 0.0, 1.0) is False
