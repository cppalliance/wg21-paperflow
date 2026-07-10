#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from __future__ import annotations

from pathlib import Path

import pytest

from assay.paper_routing.split import RawSentence, split_sentences

_P1122R3_LINE = (
    Path(__file__).resolve().parents[2]
    / "tomd"
    / "tests"
    / "fixtures"
    / "golden"
    / "snapshots"
    / "p1122r3.md"
).read_text(encoding="utf-8").splitlines()[308].strip()


@pytest.mark.parametrize(
    ("markdown", "expected_texts"),
    [
        ("1. First point. 2. Second point.", ["1. First point.", "2. Second point."]),
        ("See e.g. std::vector for details.", ["See e.g. std::vector for details."]),
        (
            "Dr. Smith proposed P1234R0. The committee agreed.",
            ["Dr. Smith proposed P1234R0.", "The committee agreed."],
        ),
        (
            "Effects: Returns true. Throws: nothing.",
            ["Effects: Returns true.", "Throws: nothing."],
        ),
        (
            "expression: assignment-expression",
            ["expression: assignment-expression"],
        ),
        (
            "*Effects:* Equivalent to: return foo;",
            ["*Effects:* Equivalent to: return foo;"],
        ),
        (
            "In 20.10.2 [meta.type.synop], add: Effects: returns is_same_v.",
            [
                "In 20.10.2 [meta.type.synop], add:",
                "Effects: returns is_same_v.",
            ],
        ),
    ],
)
def test_split_sentences_cases(markdown: str, expected_texts: list[str]) -> None:
    units = split_sentences(markdown)
    assert [u.text for u in units] == expected_texts


def test_split_p1122r3_numbered_standardese() -> None:
    units = split_sentences(_P1122R3_LINE)
    assert len(units) == 3
    assert units[0].text.startswith("1. Effects:")
    assert units[1].text.startswith("2. Synchronization:")
    assert units[2].text.startswith("3. Remarks:")


def test_code_block_is_single_sentence() -> None:
    md = "Prose before.\n\n```cpp\nint x = 1;\nint y = 2;\n```\n\nProse after."
    units = split_sentences(md)
    assert len(units) == 3
    assert units[0].text == "Prose before."
    assert "```" in units[1].text
    assert units[2].text == "Prose after."


def test_split_start_line_tracks_source() -> None:
    md = (
        "First sentence here.\n"
        "Second sentence on next line.\n"
        "Third sentence too."
    )
    units = split_sentences(md)
    assert len(units) == 3
    assert units[0].start_line == 0
    assert units[1].start_line == 1
    assert units[2].start_line == 2


def test_standardese_line_not_treated_as_bnf() -> None:
    md = "Effects: Returns true if valid."
    units = split_sentences(md)
    assert len(units) == 1
    assert units[0].text == "Effects: Returns true if valid."


def test_raw_sentence_is_frozen() -> None:
    unit = RawSentence("text", 0)
    with pytest.raises(AttributeError):
        unit.text = "other"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("markdown", "expected_texts"),
    [
        ("- Effects: returns void.", ["- Effects: returns void."]),
        (
            "(a) Effects: foo. (b) Returns: bar.",
            ["(a) Effects: foo.", "(b) Returns: bar."],
        ),
        ("1.2.3 Effects: foo.", ["1.2.3 Effects: foo."]),
        ("Release Notes: see appendix.", ["Release Notes: see appendix."]),
        (
            "add: Effects: foo. modify: Returns: bar.",
            ["add:", "Effects: foo.", "modify:", "Returns: bar."],
        ),
        ("- item two with Effects: foo.", ["- item two with Effects: foo."]),
        (
            "- We propose to add std::widget.\n- Effects: returns void.",
            ["- We propose to add std::widget.", "- Effects: returns void."],
        ),
    ],
)
def test_split_edge_cases_no_junk_fragments(
    markdown: str, expected_texts: list[str]
) -> None:
    units = split_sentences(markdown)
    assert [u.text for u in units] == expected_texts
    for text in expected_texts:
        assert text not in {"-", "(a)", "(b)", "1.2.3", "Release", "1.", "2.", "3."}
