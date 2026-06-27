#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

import pytest

from whisker.metrics import (
    _parse_headings,
    clean_string,
    content_recall,
    content_tokens,
    mhs,
    normalized_edit_distance,
    normalized_text,
    replace_textcircle,
    teds,
    text_nid,
    textblock2unicode,
)


def test_ned_identical_and_empty():
    assert normalized_edit_distance("abc", "abc") == 0.0
    assert normalized_edit_distance("", "") == 0.0
    assert normalized_edit_distance("abc", "abd") == pytest.approx(1 / 3)


def test_text_nid_whitespace_insensitive():
    assert text_nid("a  b\n c", "a b c") == 1.0
    assert text_nid("hello world", "hello world") == 1.0
    assert 0.0 < text_nid("hello world", "hello there") < 1.0


# Frozen MHS vectors captured from the retired hand-rolled Zhang-Shasha engine
# BEFORE the apted migration (A1). They pin that the apted backend produces
# identical scores so the swap is score-neutral (no baseline/guard drift).
_MHS_PARITY = [
    ("## Intro\n### Detail\n## Wording\n", "## Intro\n### Detail\n## Wording\n", 1.0, 1.0),
    ("## A\n### B\n", "## A\n## B\n", 1 / 3, 1 / 3),
    ("## A\n### B\n", "## A\n#### B\n", 1.0, 1.0),
    ("## A\n\n### A1\n\nx\n\n### A2\n\ny\n\n## B\n\nz", "## A\n\ntext\n\n## B\n\nmore", 0.6, 0.6),
    ("# Title\n## Section\n### Sub\n#### Deep", "# Title\n## Section\n### Sub", 0.8, 0.8),
    ("## Alpha beta\n### Gamma", "## Alpha beta gamma\n### Delta", 0.6083333333333333, 1.0),
    ("plain text", "other text", 1.0, 1.0),
    ("## A\n## B\n## C", "## A\n## B", 0.75, 0.75),
]


@pytest.mark.parametrize("a,b,expected,expected_struct", _MHS_PARITY)
def test_mhs_apted_parity_with_zhang_shasha(a, b, expected, expected_struct):
    assert mhs(a, b) == pytest.approx(expected)
    assert mhs(a, b, structure_only=True) == pytest.approx(expected_struct)


def test_teds_identical_table_is_one():
    t = "<table><tr><td>a</td><td>b</td></tr><tr><td>c</td><td>d</td></tr></table>"
    assert teds(t, t) == 1.0


def test_teds_text_change_reduces_score():
    a = "<table><tr><td>a</td><td>b</td></tr></table>"
    b = "<table><tr><td>a</td><td>x</td></tr></table>"
    score = teds(a, b)
    assert 0.0 < score < 1.0


def test_teds_missing_row_reduces_score():
    a = "<table><tr><td>a</td></tr><tr><td>b</td></tr></table>"
    b = "<table><tr><td>a</td></tr></table>"
    assert teds(a, b) < 1.0


def test_teds_empty_strings_score_zero():
    # PubTabNet/OmniDocBench convention: no parseable table on either side is a
    # non-comparison and scores 0.0 (the "no tables anywhere" case is handled one
    # level up in bench._table_score, which returns 1.0 before calling teds).
    assert teds("", "") == 0.0


def test_teds_structure_only_ignores_cell_text():
    # Same topology, different text -> TEDS-S is 1.0 while content TEDS is < 1.0.
    a = "<table><tr><td>a</td><td>b</td></tr></table>"
    b = "<table><tr><td>x</td><td>y</td></tr></table>"
    assert teds(a, b, structure_only=True) == 1.0
    assert teds(a, b) < 1.0


def test_teds_golden_matches_pubtabnet_definition():
    # Anchor against a hand-checkable PubTabNet case: a 2x1 GT vs a 1x1 pred.
    # GT table descendants (tbody,tr,td,tr,td) drive the xpath denominator; the
    # missing second row is one removed <tr> + one removed <td>. This pins the
    # exact OmniDocBench formula (1 - APTED_distance / max xpath('.//*')).
    gt = "<table><tbody><tr><td>a</td></tr><tr><td>b</td></tr></tbody></table>"
    pred = "<table><tbody><tr><td>a</td></tr></tbody></table>"
    score = teds(gt, pred)
    # GT has 5 descendant elements after tbody is unwrapped: tr,td,tr,td -> 4.
    # pred has tr,td -> 2. denom=4, distance=2 (remove tr+td). 1 - 2/4 = 0.5.
    assert score == pytest.approx(0.5)


def test_mhs_identical_is_one():
    md = "## Intro\n### Detail\n## Wording\n"
    assert mhs(md, md) == 1.0


def test_mhs_level_change_reduces_score():
    a = "## A\n### B\n"
    b = "## A\n## B\n"
    assert mhs(a, b) < 1.0


def test_mhs_no_headings_is_one():
    assert mhs("plain text", "other text") == 1.0


def test_parse_headings_atx():
    md = "# Title\n\n## Section\n\ntext\n\n### Sub\n"
    assert _parse_headings(md) == [(1, "Title"), (2, "Section"), (3, "Sub")]


def test_parse_headings_setext():
    # Setext headings (text over === / ---) were invisible to the old regex.
    md = "Title\n=====\n\nSection\n-------\n\nbody\n"
    assert _parse_headings(md) == [(1, "Title"), (2, "Section")]


def test_parse_headings_flattens_inline_markup():
    # Inline emphasis/link/code markup is flattened to plain prose.
    md = "## **Bold** [link](http://x) and `code`\n"
    assert _parse_headings(md) == [(2, "Bold link and code")]


def test_parse_headings_strips_front_matter():
    # The leading --- block must not be misread as a setext underline.
    md = "---\ntitle: X\ndocument: P1\n---\n\n# Real H1\n\n## Real H2\n"
    assert _parse_headings(md) == [(1, "Real H1"), (2, "Real H2")]


def test_parse_headings_suppresses_fenced_code():
    md = "# H1\n\n```\n# not a heading\n## also not\n```\n\n## H2\n"
    assert _parse_headings(md) == [(1, "H1"), (2, "H2")]


def test_parse_headings_skips_nested_headings():
    # Top-level only, matching tomd QA's documented limitation.
    md = "> ## Quoted\n\n# Top\n"
    assert _parse_headings(md) == [(1, "Top")]


def test_mhs_counts_setext_headings():
    # An ATX doc vs the same hierarchy written setext: identical heading trees.
    atx = "# Intro\n\n## Methods\n"
    setext = "Intro\n=====\n\nMethods\n-------\n"
    assert mhs(atx, setext) == 1.0


def test_content_tokens_splits_on_word_boundary():
    # Unlike normalized_text (which collapses to one token), content_tokens keeps
    # word granularity: punctuation and whitespace separate tokens, lowercased.
    assert content_tokens("Hello, World! Foo-bar") == ["hello", "world", "foo", "bar"]


def test_content_recall_identical_is_one():
    assert content_recall("alpha beta gamma", "alpha beta gamma") == 1.0


def test_content_recall_empty_reference_is_one():
    assert content_recall("anything", "") == 1.0


def test_content_recall_dropped_words():
    # Three of six reference word occurrences survive in the candidate.
    assert content_recall("alpha beta gamma", "alpha beta gamma delta epsilon zeta") == 0.5


def test_content_recall_is_order_invariant():
    # Reordering the candidate does not change recall (bag-of-words).
    ref = "alpha beta gamma delta"
    assert content_recall("delta gamma beta alpha", ref) == 1.0


def test_content_recall_ignores_extra_candidate_words():
    # Hallucinated/duplicated candidate words do not inflate or lower recall.
    assert content_recall("alpha beta gamma extra words", "alpha beta gamma") == 1.0


def test_content_recall_respects_multiplicity():
    # The candidate has one 'alpha'; the reference needs two -> 3 of 4 present.
    assert content_recall("alpha beta gamma", "alpha alpha beta gamma") == 0.75


def test_clean_string_strips_formatting_keeps_content():
    # Markdown syntax, punctuation and whitespace vanish; alnum content stays.
    assert clean_string("# Title\n\n**Hello**, world! | a | b |") == "TitleHelloworldab"
    # Same content, different formatting -> identical normalized strings.
    assert clean_string("## Intro\n\nFoo bar.") == clean_string("Intro\n\n*Foo* bar")


def test_replace_textcircle_folds_circled_glyphs():
    # Circled digits/letters collapse to their inner character so one converter
    # emitting "(1)" and another emitting the circled glyph still agree.
    assert replace_textcircle("\u2460\u2461\u2462") == "123"   # circled 1,2,3
    assert replace_textcircle("\u24d0\u24d1") == "ab"          # circled a,b
    assert replace_textcircle(r"\textcircled{x}") == "x"
    # clean_string runs it too, so the circled form normalizes like the plain.
    assert clean_string("step \u2460") == clean_string("step 1")


def test_textblock2unicode_folds_inline_latex():
    # An inline formula with sub/superscript markup is converted toward unicode;
    # the dollar delimiters are gone and the content survives in some form.
    out = textblock2unicode("energy $x^2$ here")
    assert "$" not in out
    assert "energy" in out and "here" in out


def test_normalized_text_is_clean_string_of_textblock2unicode():
    # The canonical text-axis normalizer composes the two: identical prose with
    # different inline-formula formatting normalizes to the same content string.
    a = "The value $x_1$ matters."
    b = "The value x_1 matters."
    assert normalized_text(a) == normalized_text(b)


def test_normalized_text_handles_malformed_latex_without_raising():
    # Unbalanced braces are rejected by the guards (no pylatexenc crash); the
    # function still returns a normalized content string.
    out = normalized_text("broken $x^{2 formula and more text here")
    assert isinstance(out, str) and out


def test_clean_string_makes_nid_formatting_insensitive():
    # Heading markup, emphasis, punctuation and whitespace are formatting and
    # vanish, so the same words score perfect text agreement. (YAML front-matter
    # keys are NOT stripped by clean_string; they normalize as content tokens.)
    rich = "## Heading\n\nThe **quick** brown fox.\n"
    plain = "Heading\n\nThe quick brown fox\n"
    assert text_nid(clean_string(rich), clean_string(plain)) == 1.0


def test_metrics_are_deterministic():
    a = "<table><tr><td>a</td><td>b</td></tr></table>"
    b = "<table><tr><td>a</td><td>c</td></tr></table>"
    assert teds(a, b) == teds(a, b)
    md_a, md_b = "## A\n### B\n", "## A\n#### B\n"
    assert mhs(md_a, md_b) == mhs(md_a, md_b)
