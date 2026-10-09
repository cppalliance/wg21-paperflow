#
# Copyright (c) 2026 Sean Parsons
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from whisker.det.structural import MARKER_PATTERNS, count_markers


def test_all_classes_present():
    counts = count_markers("")
    assert set(counts.keys()) == set(MARKER_PATTERNS.keys())
    assert all(v == 0 for v in counts.values())


def test_code_fences():
    text = "```cpp\nint x;\n```\n"
    assert count_markers(text)["code_fence"] == 2


def test_inline_code():
    text = "Use `foo` and `bar`.\n"
    assert count_markers(text)["inline_code"] == 2


def test_headings():
    text = "# H1\n## H2\n### H3\n"
    assert count_markers(text)["heading"] == 3


def test_table_rows():
    text = "| A | B |\n|---|---|\n| 1 | 2 |\n"
    assert count_markers(text)["table_row"] == 3


def test_empty_table_rows():
    text = "| A | B |\n|   |   |\n| 1 | 2 |\n"
    assert count_markers(text)["empty_table_row"] == 1


def test_images():
    text = "![alt](img.png)\n"
    assert count_markers(text)["image"] == 1


def test_escaped_underscores():
    text = "std::uniform\\_real\\_distribution\n"
    assert count_markers(text)["escaped_underscore"] == 2


def test_list_items():
    text = "- item 1\n* item 2\n+ item 3\n"
    assert count_markers(text)["list_item"] == 3


def test_indented_code():
    text = "    int x = 1;\n    return x;\n"
    assert count_markers(text)["indented_code"] == 2


def test_mixed_document():
    text = (
        "## Heading\n\n"
        "Some prose with `inline` code.\n\n"
        "```cpp\nint x;\n```\n\n"
        "| A |\n|---|\n| 1 |\n\n"
        "- item\n"
    )
    c = count_markers(text)
    assert c["heading"] == 1
    assert c["inline_code"] == 1
    assert c["code_fence"] == 2
    assert c["table_row"] == 3
    assert c["list_item"] == 1
