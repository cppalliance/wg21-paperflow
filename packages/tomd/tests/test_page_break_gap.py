# Copyright (c) 2026 Rob Beeston (rob@cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Text between two pieces of a table at a page break (select._text_outside)."""
from tomd.lib.pdf.select import _text_outside
from tomd.lib.pdf.types import Block, Line, Span


def _block(page, *rows):
    """rows: (y, text, size)."""
    lines = []
    for y, text, size in rows:
        bb = (72.0, y, 72.0 + 5 * len(text), y + size)
        lines.append(Line(spans=[Span(text=text, font_size=size, bbox=bb)], bbox=bb, page_num=page))
    return Block(lines=lines, bbox=(72.0, rows[0][0], 500.0, rows[-1][0] + rows[-1][2]), page_num=page)


BODY = _block(1, *[(100 + 14 * i, "body text of the page", 11.0) for i in range(20)])


def test_footnote_below_the_first_piece_is_not_text_between():
    note = _block(1, (700, "1 https://example.com/proposal", 9.0))
    assert not _text_outside([BODY, note], 1, below=650)


def test_paragraph_below_the_first_piece_is_text_between():
    para = _block(1, (700, "A new section starts here", 11.0))
    assert _text_outside([BODY, para], 1, below=650)


def test_small_text_without_a_note_marker_is_text_between():
    small = _block(1, (700, "Source: survey results", 9.0))
    assert _text_outside([BODY, small], 1, below=650)


def test_continued_caption_above_the_second_piece_is_not_text_between():
    cap = _block(2, (73, "Table 1: Sequence container requirements (in addition to", 11.0),
                 (87, "container) (continued)", 11.0))
    assert not _text_outside([cap], 2, above=105)


def test_caption_without_continued_is_text_between():
    cap = _block(2, (73, "Table 2: Associative container requirements", 11.0))
    assert _text_outside([cap], 2, above=105)


def test_long_text_mentioning_continued_is_text_between():
    para = _block(2, *[(20 + 12 * i, "the discussion continued at length", 11.0) for i in range(5)])
    assert _text_outside([para], 2, above=105)


def _cell(text, page):
    bb = (72.0, 100.0, 300.0, 110.0)
    return [Line(spans=[Span(text=text, font_size=10.0, bbox=bb)], bbox=bb, page_num=page)]


def test_half_open_range_is_not_split_code():
    from tomd.lib.pdf.select import _split_code_cell
    assert not _split_code_cell("Effects: erases the elements in [q1, q2).")
    assert _split_code_cell("distance(begin(),")


def test_split_code_is_counted_page_by_page():
    from tomd.lib.pdf.select import table_flags
    from tomd.lib.pdf.types import TableCandidate
    # one cut code cell on each of two pages: each piece alone passes, so the join does too
    rows = [[_cell("Expression", 1), _cell("Notes", 1)]]
    rows += [[_cell(f"f{i}()", 1), _cell("returns a value of the type", 1)] for i in range(6)]
    rows += [[_cell("g(a,", 1), _cell("cut here", 1)]]
    rows += [[_cell(f"h{i}()", 2), _cell("returns a value of the type", 2)] for i in range(6)]
    rows += [[_cell("k(b,", 2), _cell("cut here", 2)]]
    joined = TableCandidate("rules", rows, {1: (0, 0, 300, 700), 2: (0, 0, 300, 700)})
    assert "split-code" not in table_flags(joined)
    one_page = TableCandidate("rules", [[_cell(t, 1) for t in (r[0][0].text, r[1][0].text)] for r in rows],
                              {1: (0, 0, 300, 700)})
    assert "split-code" in table_flags(one_page)
