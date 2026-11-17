# Copyright (c) 2026 Rob Beeston (rob@cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""The rule-band reader places a word by where it starts (ruled._rule_band_tables)."""
from tomd.lib.pdf.ruled import _rule_band_tables

CW = 5.0     # character width
H = 9.0      # line height


def _word(text, x, y, font="LMMono10-Regular"):
    chars = [(ch, (x + i * CW, y, x + (i + 1) * CW, y + H), font, 9.0, 0, 0) for i, ch in enumerate(text)]
    return (x, y, x + CW * len(text), y + H, text, chars, True)


def _line(text, x, y):
    out, cx = [], x
    for part in text.split():
        out.append(_word(part, cx, y))
        cx += CW * (len(part) + 1)
    return out


# rules from x=60 to x=300 at the header's top, under it, and at the table's bottom
GROUP = [(100.0, 60.0, 300.0), (115.0, 60.0, 300.0), (200.0, 60.0, 300.0)]


def _texts(t):
    return [[" ".join(ln.text for ln in c) for c in r] for r in t.rows]


def test_word_running_past_the_right_rule_stays_in_its_cell():
    words = (_line("Before", 64, 103) + _line("After", 190, 103)
             + _line("int f();", 64, 120) + _line("void g() = delete;", 190, 120)
             + _line("int h();", 64, 132) + _line("int k();", 190, 132))
    # "delete;" starts at x=275 and ends at x=310, past the rule's end
    (t,) = _rule_band_tables(1, words, GROUP, header_above=False)
    assert "void g() = delete;" in _texts(t)[1][1]


def test_word_starting_right_of_the_rules_is_not_the_table():
    words = (_line("Before", 64, 103) + _line("After", 190, 103)
             + _line("int f();", 64, 120) + _line("int g();", 190, 120)
             + _line("margin", 320, 120))
    (t,) = _rule_band_tables(1, words, GROUP, header_above=False)
    assert "margin" not in " ".join(c for r in _texts(t) for c in r)
