"""Tests for the deterministic structural golden comparator."""

import pytest

from tomd.lib.golden_compare import compare, normalize


def test_normalize_heading_levels_and_text():
    doc = normalize("## Abstract\n\nSome prose here.\n")
    kinds = [(b.kind, b.level, b.text) for b in doc.blocks]
    assert kinds == [("heading", 2, "Abstract"), ("paragraph", 0, "Some prose here.")]


def test_normalize_ignores_blank_lines():
    doc = normalize("# A\n\n\n\nbody\n")
    assert [b.kind for b in doc.blocks] == ["heading", "paragraph"]


def test_normalize_nested_list_depths_and_markers():
    md = "- top\n  - child a\n  - child b\n"
    doc = normalize(md)
    lists = [b for b in doc.blocks if b.kind == "list"]
    assert len(lists) == 1
    depths = [(e.depth, e.marker, e.text) for e in lists[0].items]
    assert depths == [
        (0, "-", "top"),
        (1, "-", "child a"),
        (1, "-", "child b"),
    ]


def test_normalize_ordered_list_marker():
    doc = normalize("1. one\n2. two\n")
    items = [b for b in doc.blocks if b.kind == "list"][0].items
    assert all(e.ordered for e in items)
    assert [e.text for e in items] == ["one", "two"]


def test_normalize_code_block_lang_and_lines():
    md = "```cpp\nint main() {\n  return 0;\n}\n```\n"
    code = [b for b in normalize(md).blocks if b.kind == "code"][0]
    assert code.code_lang == "cpp"
    assert code.code_lines == 3


def test_normalize_table_dims():
    md = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n"
    table = [b for b in normalize(md).blocks if b.kind == "table"][0]
    assert table.table_cols == 2
    assert table.table_rows == 3  # 1 header row + 2 body rows


def test_normalize_front_matter_keys_in_contract_order():
    md = (
        "---\n"
        'title: "X"\n'
        "document: P1R0\n"
        "date: 2024-01-01\n"
        "---\n\n"
        "## Body\n"
    )
    doc = normalize(md)
    assert doc.front_matter_keys == ("title", "document", "date")


def test_compare_identical_headings_score_one():
    md = "## Intro\n\ntext\n"
    s = compare(md, md)
    assert s.axes["heading"].score == 1.0
    assert s.axes["frontmatter"].score == 1.0


def test_compare_h1_vs_h2_drops_only_heading_axis():
    golden = "## Introduction\n\nbody text here\n"
    tomd = "# Introduction\n\nbody text here\n"   # wrong level (issue #155)
    s = compare(tomd, golden)
    assert s.axes["heading"].score < 1.0
    assert s.axes["text"].score == 1.0
    assert s.axes["frontmatter"].score == 1.0


def test_list_axis_drops_when_nested_items_lost():
    golden = "- parent\n  - child one\n  - child two\n"
    # tomd failed to detect the nested bullets; they became prose:
    tomd = "- parent\n\nchild one\nchild two\n"
    s = compare(tomd, golden)
    assert s.axes["list"].score < 1.0


def test_list_axis_one_when_equal():
    md = "- a\n  - b\n"
    assert compare(md, md).axes["list"].score == 1.0


def test_code_axis_drops_on_fence_split():
    golden = "```cpp\nstruct S {\n  int x;\n};\n```\n"
    tomd = "```cpp\nstruct S {\n```\n\n```cpp\n  int x;\n};\n```\n"  # split in two
    s = compare(tomd, golden)
    assert s.axes["code"].score < 1.0


def test_code_axis_one_when_equal():
    md = "```cpp\nint x;\n```\n"
    assert compare(md, md).axes["code"].score == 1.0


def test_table_axis_drops_on_missplit():
    golden = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n| 5 | 6 |\n"
    tomd = "| A | B |\n|---|---|\n| 1 | 2 |\n"  # rows lost / table split
    s = compare(tomd, golden)
    assert s.axes["table"].score < 1.0


def test_table_axis_one_when_equal():
    md = "| A | B |\n|---|---|\n| 1 | 2 |\n"
    assert compare(md, md).axes["table"].score == 1.0


def test_text_axis_one_when_identical():
    md = "## H\n\nthe quick brown fox\n"
    assert compare(md, md).axes["text"].score == 1.0


def test_text_axis_drops_on_paraphrase():
    golden = "para one words here\n\npara two more words\n"
    tomd = "completely different content\n\nunrelated tokens entirely\n"
    s = compare(tomd, golden)
    assert s.axes["text"].score < 0.5


def test_text_axis_survives_pure_structural_shift():
    # Same words, only heading LEVEL differs -> text axis stays 1.0
    golden = "## Introduction\n\nshared body sentence\n"
    tomd = "# Introduction\n\nshared body sentence\n"
    s = compare(tomd, golden)
    assert s.axes["text"].score == 1.0


_RICH_MD = (
    "---\n"
    'title: "T"\n'
    "document: P1R0\n"
    "---\n\n"
    "## Abstract\n\nIntro prose here.\n\n"
    "### Details\n\n"
    "- one\n  - nested\n- two\n\n"
    "```cpp\nint main() { return 0; }\n```\n\n"
    "| A | B |\n|---|---|\n| 1 | 2 |\n"
)


@pytest.mark.parametrize("axis", ["frontmatter", "heading", "list", "code", "table", "text"])
def test_identical_document_scores_one_on_every_axis(axis):
    s = compare(_RICH_MD, _RICH_MD)
    assert s.axes[axis].score == 1.0


def test_identical_document_composite_is_one():
    assert compare(_RICH_MD, _RICH_MD).composite == 1.0


def test_heading_uniform_shift_is_graded_not_zero():
    # All headings present, correct order, correct nesting shape, but every
    # body heading is one level too shallow (issue #155).
    ideal = "## A\n\ntext\n\n### B\n\nmore\n\n### C\n\nend\n"
    tomd = "# A\n\ntext\n\n## B\n\nmore\n\n## C\n\nend\n"
    h = compare(tomd, ideal).axes["heading"]
    assert h.sub["text"] == 1.0          # all heading text present, in order
    assert h.sub["nesting"] == 1.0       # deltas (+1, 0) preserved
    assert h.sub["level"] == 0.0         # every absolute level wrong
    assert 0.5 < h.score < 1.0           # graded, not 0.0 and not 1.0


def test_heading_identical_is_one_on_all_subsignals():
    md = "## A\n\nx\n\n### B\n\ny\n"
    h = compare(md, md).axes["heading"]
    assert h.score == 1.0
    assert h.sub == {"text": 1.0, "level": 1.0, "nesting": 1.0}


def test_heading_missing_heading_drops_text_subsignal():
    ideal = "## A\n\nx\n\n### B\n\ny\n\n### C\n\nz\n"
    tomd = "## A\n\nx\n\n### B\n\ny\n"     # dropped C entirely
    h = compare(tomd, ideal).axes["heading"]
    assert h.sub["text"] < 1.0


def test_composite_ignores_absent_structural_axes():
    # Prose only: list/code/table are vacuously 1.0 and must not pad composite.
    ideal = "## A\n\nshared body words here\n"
    tomd = "# A\n\nshared body words here\n"   # heading level wrong only
    s = compare(tomd, ideal)
    assert s.axes["list"].score == 1.0          # still individually reported
    # composite is the mean of present axes (frontmatter, heading, text), so the
    # heading miss is not diluted by three vacuous 1.0s.
    assert s.composite < (sum(a.score for a in s.axes.values()) / len(s.axes))
    assert s.worst_present_axis == "heading"
