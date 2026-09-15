"""Wording section detection via multi-signal HSV color + drawing analysis.

Detects ins/del markup in WG21 PDF papers by combining three signals:
  1. Block-level color contamination filter - blocks containing non-wording
     chromatic colors (purple, orange, cyan) are syntax-highlighted code
     and are skipped entirely. So are blocks whose palette has two or
     more distinct shades inside one wording band (two greens: a Pygments
     keyword and a number), since a diff framework paints ins in exactly
     one color and del in exactly one color.
  2. Line-level wording detection - lines where the majority of non-link
     characters are green/red, or where green/red spans appear on an
     otherwise-black line (partial-line wording pattern).
  3. Span-level classification - green spans become ins; red spans with
     a confirmed strikethrough drawing become del.

Hyperlinks (span.link_url set) are excluded from all checks and fractions.
Insertions require no drawing decoration. Deletions require a strikethrough
drawing whose width overlaps at least 30% of the span to avoid matching
table borders and decorative rules.

Known WG21 framework diff colors (for reference):
  mpark/wg21:     add=#006e28 (H=142), rm=#bf0303 (H=1)
  tcbrindle:      add=#008019 (H=150), rm=#ff0000 (H=0)
  cplusplus/draft: add=#009999 (H=180, teal), rm=#ff0000 (H=0)
  schultke:       ins=#17752d (H=138), del=#be1621 (H=355)
All fall within our HSV ranges: green 90-180, red <=30 or >=330.
"""

import colorsys
import logging
from .types import Block

_log = logging.getLogger(__name__)

_HORIZ_LINE_Y_TOL = 1.0
# A strikethrough over a single narrow glyph (a struck ``2``, ``i``, or
# ``.``) is only ~4px wide, so the collection floor must sit below one
# character cell. Noise is rejected downstream: _match_strikethrough
# requires the rule to cover >=30% of a *red* span at its vertical
# center, which a stray tick or vector-art fragment will not.
_HORIZ_LINE_MIN_WIDTH = 3.0
_CONTEXT_LIGHTNESS_MIN = 0.25
_CONTEXT_LIGHTNESS_MAX = 0.65
_BLACK_LIGHTNESS_MAX = 0.15

_SATURATION_THRESHOLD = 0.15
_GREEN_HUE_MIN = 90
_GREEN_HUE_MAX = 180
_RED_HUE_WRAP = 30
_BLUE_HUE_MIN = 210
_BLUE_HUE_MAX = 270
_STRIKETHROUGH_Y_TOLERANCE = 2.0
_STRIKETHROUGH_OVERLAP_MIN = 0.3
_WORDING_LINE_MAJORITY = 0.5
_MIN_WORDING_SPANS = 5

# C/C++ comment introducers. A red run that begins a comment is syntax
# highlighting (a colored code comment), never WG21 deletion markup,
# which strikes out identifiers / strings / operators - never an
# entire `//` or `/* */` comment.
_LINE_COMMENT = "//"
_BLOCK_COMMENT_OPEN = "/*"


def _color_int_to_rgb(color_int: int) -> tuple[float, float, float]:
    """Convert MuPDF integer color to (r, g, b) in 0-1 range."""
    if color_int == 0:
        return (0.0, 0.0, 0.0)
    r = ((color_int >> 16) & 0xFF) / 255.0
    g = ((color_int >> 8) & 0xFF) / 255.0
    b = (color_int & 0xFF) / 255.0
    return (r, g, b)


def _hsv(color_int: int) -> tuple[float, float, float]:
    """Convert MuPDF integer color to (hue 0-360, saturation 0-1, value 0-1)."""
    r, g, b = _color_int_to_rgb(color_int)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360.0, s, v


def _in_green_band(h: float, s: float) -> bool:
    """True if (hue 0-360, saturation 0-1) sits in the ins green band."""
    return s >= _SATURATION_THRESHOLD and _GREEN_HUE_MIN <= h <= _GREEN_HUE_MAX


def _in_red_band(h: float, s: float) -> bool:
    """True if (hue 0-360, saturation 0-1) sits in the del red band."""
    return s >= _SATURATION_THRESHOLD and (h <= _RED_HUE_WRAP or h >= 360 - _RED_HUE_WRAP)


def is_green_ins(color_int: int) -> bool:
    """True if color is in the green hue range with sufficient saturation."""
    h, s, _ = _hsv(color_int)
    return _in_green_band(h, s)


def is_red_del(color_int: int) -> bool:
    """True if color is in the red hue range with sufficient saturation."""
    h, s, _ = _hsv(color_int)
    return _in_red_band(h, s)


def is_wording_rgb(r: float, g: float, b: float) -> bool:
    """True if (r, g, b) floats in [0, 1] sit in the ins (green) or del (red) hue band.

    Mirrors :func:`_is_wording_color` for callers that already have RGB
    floats, such as ``pymupdf.Page.get_drawings()``, which yields
    ``color`` and ``fill`` as float tuples rather than the packed-int
    format ``wording.py`` originally consumed. Both predicates delegate
    to :func:`_in_green_band` / :func:`_in_red_band`, so the hue-band
    rule lives in one place.
    """
    h, s, _v = colorsys.rgb_to_hsv(r, g, b)
    h *= 360.0
    return _in_green_band(h, s) or _in_red_band(h, s)


def _is_blue_link(color_int: int) -> bool:
    """True if color is in the blue hue range (hyperlink)."""
    h, s, _ = _hsv(color_int)
    return s >= _SATURATION_THRESHOLD and _BLUE_HUE_MIN <= h <= _BLUE_HUE_MAX


def _is_chromatic(color_int: int) -> bool:
    """True if color has enough saturation to be a chromatic signal."""
    _, s, _ = _hsv(color_int)
    return s >= _SATURATION_THRESHOLD


def _is_black(color_int: int) -> bool:
    """True if color is achromatic and dark (near-black)."""
    r, g, b = _color_int_to_rgb(color_int)
    lightness = (r + g + b) / 3.0
    return lightness <= _BLACK_LIGHTNESS_MAX


def _is_wording_color(color_int: int) -> bool:
    """True if color is green (ins) or red (del)."""
    h, s, _ = _hsv(color_int)
    return _in_green_band(h, s) or _in_red_band(h, s)


def is_foreign_chromatic(color_int: int) -> bool:
    """True if color is chromatic but not green, red, or blue.

    A foreign chromatic color is the signature of syntax-highlighted
    code (purple, orange, cyan, olive, ...). It is used both by the
    block-level wording filter here and by the section-level guard in
    :mod:`structure` that keeps a syntax-highlighted code listing from
    being reclassified as wording markup.
    """
    if not _is_chromatic(color_int):
        return False
    return not (_is_wording_color(color_int) or _is_blue_link(color_int))


def _match_strikethrough(span_bbox, drawings: list) -> bool:
    """True if horizontal rules cross the vertical center of the span.

    Aggregate coverage must reach _STRIKETHROUGH_OVERLAP_MIN of the span
    width. A single strikethrough is frequently emitted as several short
    collinear segments (one per sub-word, e.g. ``experimental::`` then
    ``native_simd``); summing their merged x-coverage at the span's
    vertical center recovers the strike that a per-segment test would
    miss. The y-tolerance gate still rejects full-page table borders and
    decorative rules, which never sit at a text span's vertical center.
    """
    if not drawings:
        return False
    sx0, sy0, sx1, sy1 = span_bbox
    y_center = (sy0 + sy1) / 2.0
    span_w = max(sx1 - sx0, 1.0)
    intervals: list[tuple[float, float]] = []
    for dy, dx0, dx1, _ in drawings:
        if abs(dy - y_center) > _STRIKETHROUGH_Y_TOLERANCE:
            continue
        lo = max(dx0, sx0)
        hi = min(dx1, sx1)
        if hi > lo:
            intervals.append((lo, hi))
    if not intervals:
        return False
    intervals.sort()
    covered = 0.0
    cur_lo, cur_hi = intervals[0]
    for lo, hi in intervals[1:]:
        if lo <= cur_hi:
            cur_hi = max(cur_hi, hi)
        else:
            covered += cur_hi - cur_lo
            cur_lo, cur_hi = lo, hi
    covered += cur_hi - cur_lo
    return covered / span_w >= _STRIKETHROUGH_OVERLAP_MIN


def _block_has_foreign_colors(block: Block) -> bool:
    """True if the block contains chromatic colors outside green/red/blue.

    Indicates syntax-highlighted code. Hyperlink spans are excluded.
    """
    for line in block.lines:
        for span in line.spans:
            if span.link_url or not span.text.strip():
                continue
            if is_foreign_chromatic(span.color):
                return True
    return False


def _block_has_highlighter_palette(block: Block) -> bool:
    """True if one wording band holds two or more distinct colors in the block.

    A WG21 diff framework paints insertions in exactly one green and
    deletions in exactly one red (see the module docstring). A syntax
    highlighter paints keywords, numbers and builtins in *different*
    greens (Pygments ``friendly``: ``#007020``, ``#40a070``, ``#008000``)
    and types in a red-brown (``#902000``), so a second shade inside the
    green band or the red band is the highlighter's signature, even when
    the block carries no foreign (purple/orange/cyan) color at all.

    Only monospace spans vote: a highlighter paints code, and a prose
    wording block whose cross-reference wraps into a second green span
    (``attach_links`` marks one span per annotation) must not lose its
    insertions to this check. Hyperlink spans are excluded.

    shortcut: a highlighter block whose palette is exactly one green and
    one red (a listing with keywords and a type but no literal) is not
    caught here and relies on the ``_MIN_WORDING_SPANS`` floor; the
    upgrade path is to propagate the palette detected here to every
    monospace block of the document that uses only those colors.
    """
    greens: set[int] = set()
    reds: set[int] = set()
    for line in block.lines:
        for span in line.spans:
            if span.link_url or not span.monospace or not span.text.strip():
                continue
            if is_green_ins(span.color):
                greens.add(span.color)
            elif is_red_del(span.color):
                reds.add(span.color)
    return len(greens) >= 2 or len(reds) >= 2


def _comment_start_offset(text: str) -> int | None:
    """Char offset of the first ``//`` or ``/*`` in a line, or None.

    Conservative: a ``//`` or ``/*`` inside a string literal would be
    misread as a comment start, but red string literals being deleted
    (``<del>"\\n"</del>``) do not themselves contain a comment
    introducer, so the wording cases this guard protects are unaffected.
    """
    offsets = [
        o for o in (text.find(_LINE_COMMENT), text.find(_BLOCK_COMMENT_OPEN))
        if o >= 0
    ]
    return min(offsets) if offsets else None


def _span_is_comment(line, span) -> bool:
    """True if ``span`` lies within a code comment on its line.

    Walks the line's spans in reading order to locate ``span``'s char
    offset, then compares it to the line's first comment introducer. A
    red span at or past the comment start is syntax-highlighted comment
    text, not a struck-out token, so it must not become a deletion.
    """
    offset = 0
    span_offset: int | None = None
    for s in line.spans:
        if s is span:
            span_offset = offset
        offset += len(s.text)
    if span_offset is None:
        return False
    comment_start = _comment_start_offset(line.text)
    return comment_start is not None and span_offset >= comment_start


def _line_has_confirmed_strikethrough(line, drawings: list) -> bool:
    """True if a red span on this line carries a confirmed strikethrough."""
    for span in line.spans:
        if span.link_url or not span.text.strip():
            continue
        if is_red_del(span.color) and _match_strikethrough(span.bbox, drawings):
            return True
    return False


def _block_has_confirmed_strikethrough(block: Block, drawings: list) -> bool:
    """True if a red span in the block carries a confirmed strikethrough.

    A struck-out token is the strongest wording signal there is, so its
    presence overrides the foreign-color filter: a genuine WG21 deletion
    can sit inside an otherwise syntax-highlighted code listing (a diff
    that swaps one type for another, ``native_simd`` -> ``simd::vec``).
    Syntax-highlighted code never has rules drawn through its glyphs, so
    this exemption does not readmit ordinary code listings.
    """
    return any(
        _line_has_confirmed_strikethrough(line, drawings)
        for line in block.lines
    )


def _line_wording_fraction(line) -> float:
    """Fraction of non-link non-whitespace characters that are green or red."""
    total = colored = 0
    for span in line.spans:
        if span.link_url:
            continue
        n = len(span.text.replace(" ", ""))
        if n == 0:
            continue
        total += n
        if _is_wording_color(span.color):
            colored += n
    return colored / total if total else 0.0


def _line_has_wording_on_black(line) -> bool:
    """True if a line has green/red spans with the rest being black.

    Catches partial-line wording where only the new keyword is colored
    (e.g. green `constexpr` prepended to a black function declaration).
    Returns False if any non-link span is a foreign chromatic color or
    a non-black achromatic color.
    """
    has_colored = False
    for span in line.spans:
        if span.link_url or not span.text.strip():
            continue
        if _is_wording_color(span.color):
            has_colored = True
        elif _is_blue_link(span.color):
            continue
        elif _is_chromatic(span.color):
            return False
        elif not _is_black(span.color):
            return False
    return has_colored


def collect_line_drawings(page) -> list[tuple[float, float, float, tuple]]:
    """Collect horizontal line drawings from a page for decoration detection.

    Returns list of (y, x0, x1, color_rgb) for horizontal lines.
    """
    lines = []
    try:
        for drawing in page.get_drawings():
            items = drawing.get("items", [])
            color = drawing.get("color")
            if not color or not isinstance(color, (tuple, list)):
                continue
            for item in items:
                if item[0] != "l":
                    continue
                p1 = item[1]
                p2 = item[2]
                if abs(p1.y - p2.y) < _HORIZ_LINE_Y_TOL:
                    y = (p1.y + p2.y) / 2.0
                    x0 = min(p1.x, p2.x)
                    x1 = max(p1.x, p2.x)
                    if x1 - x0 > _HORIZ_LINE_MIN_WIDTH:
                        lines.append((y, x0, x1, tuple(color)))
    except RuntimeError:
        _log.warning("get_drawings() failed", exc_info=True)
    return lines


def classify_wording(blocks: list[Block],
                     page_drawings: dict[int, list]) -> list[str]:
    """Classify spans as ins/del/context using multi-signal analysis.

    Three-layer filter:
      1. Blocks with foreign chromatic colors (not green/red/blue), or with
         two or more distinct shades inside one wording band, are skipped:
         they are syntax-highlighted code, not wording markup.
      2. Lines qualify if either the majority (>50%) of non-link characters
         are green/red, or if any green/red spans appear with the remaining
         text being black (partial-line wording pattern).
      3. Green spans on qualifying lines become ins (no drawing required).
         Red spans become del only with a confirmed strikethrough drawing.

    Sets span.wording_role on matching spans.
    Returns an empty list (reserved for future diagnostic messages).
    """
    # Candidates carry (span, role, page_num) for page-local promotion.
    candidates: list[tuple] = []

    for block in blocks:
        drawings = page_drawings.get(block.page_num, [])

        if ((_block_has_foreign_colors(block)
                or _block_has_highlighter_palette(block))
                and not _block_has_confirmed_strikethrough(block, drawings)):
            continue

        for line in block.lines:
            is_majority = _line_wording_fraction(line) > _WORDING_LINE_MAJORITY
            is_partial = not is_majority and _line_has_wording_on_black(line)
            # A confirmed strikethrough qualifies the line on its own, even
            # when it is a lone struck token amid syntax-highlighted code
            # (a `2` replaced by `std::cw<2>`): the rule through the glyph
            # is unambiguous, so neither a wording majority nor an
            # all-black remainder is required.
            is_struck = _line_has_confirmed_strikethrough(line, drawings)
            if not is_majority and not is_partial and not is_struck:
                continue

            for span in line.spans:
                if not span.text.strip() or span.link_url:
                    continue

                if is_green_ins(span.color):
                    if _span_is_comment(line, span):
                        # A green `//` or `/* */` comment is a syntax-highlighted
                        # code comment, not an insertion.
                        continue
                    candidates.append((span, "ins", block.page_num))
                elif is_red_del(span.color):
                    if _match_strikethrough(span.bbox, drawings):
                        candidates.append((span, "del", block.page_num))
                    elif _span_is_comment(line, span):
                        # A red `//` or `/* */` comment with no strike is a
                        # syntax-highlighted code comment, not a deletion.
                        continue
                    else:
                        candidates.append((span, "del_unconfirmed", block.page_num))
                elif not _is_chromatic(span.color) and span.color != 0:
                    r, g, b = _color_int_to_rgb(span.color)
                    lightness = (r + g + b) / 3.0
                    if _CONTEXT_LIGHTNESS_MIN < lightness < _CONTEXT_LIGHTNESS_MAX:
                        candidates.append((span, "context", block.page_num))

    ins_count = sum(1 for _, r, _ in candidates if r == "ins")
    confirmed_del = sum(1 for _, r, _ in candidates if r == "del")
    preamble_dropped = 0

    if ins_count >= _MIN_WORDING_SPANS:
        # Page-gated promotion: only promote del_unconfirmed on pages at
        # or after the first page containing an ins span. The preamble
        # (Abstract, TOC, Revision History) precedes wording sections and
        # often contains red code-styling that must not be promoted.
        # Ticket F: prevents 432 false wording-remove blocks in p2583r3.
        first_ins_page = min(pg for _, r, pg in candidates if r == "ins")
        candidates = [
            (s, "del" if r == "del_unconfirmed" and pg >= first_ins_page else r, pg)
            for s, r, pg in candidates
        ]
    # Drop remaining unconfirmed (preamble pages, or ins_count < threshold).
    pre_drop = len(candidates)
    candidates = [(s, r, pg) for s, r, pg in candidates if r != "del_unconfirmed"]
    preamble_dropped = pre_drop - len(candidates)

    ins_del = [c for c in candidates if c[1] in ("ins", "del")]
    # The span floor guards against a handful of stray syntax-highlight
    # tokens that happen to fall in the green/red bands. A confirmed
    # strikethrough is not noise: a single struck token is unambiguous
    # wording even when it is the only edit on the page, so it bypasses
    # the floor.
    if len(ins_del) < _MIN_WORDING_SPANS and confirmed_del == 0:
        _log.debug("Too few wording candidates (%d < %d), skipping",
                    len(ins_del), _MIN_WORDING_SPANS)
        return []

    for span, role, _ in candidates:
        span.wording_role = role

    del_count = sum(1 for _, r, _ in candidates if r == "del")
    ctx_count = sum(1 for _, r, _ in candidates if r == "context")
    promoted = del_count - confirmed_del if del_count > confirmed_del else 0
    _log.info("Wording detected: %d ins, %d del (%d promoted, %d preamble dropped), %d context",
               ins_count, del_count, promoted, preamble_dropped, ctx_count)

    return []
