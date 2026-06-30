"""Tests for the deterministic gap locator and issue drafter."""

from tomd.lib.golden_gaps import Gap, draft_issues, locate_gaps


def test_locate_gaps_uniform_heading_shift_reports_wrong_level():
    ideal = "## A\n\nx\n\n### B\n\ny\n"
    tomd = "# A\n\nx\n\n## B\n\ny\n"
    gaps = locate_gaps(tomd, ideal)
    hgaps = [g for g in gaps if g.axis == "heading"]
    assert hgaps
    assert all(g.kind == "wrong-level" for g in hgaps)
    assert "H1" in hgaps[0].tomd and "H2" in hgaps[0].ideal
    assert hgaps[0].rule  # a cited contract rule


def test_locate_gaps_identical_has_none():
    md = "## A\n\nx\n\n- one\n  - two\n"
    assert locate_gaps(md, md) == []


def test_locate_gaps_missing_heading():
    ideal = "## A\n\nx\n\n## B\n\ny\n"
    tomd = "## A\n\nx\n"
    gaps = locate_gaps(tomd, ideal)
    assert any(g.axis == "heading" and g.kind == "missing" and "B" in g.ideal
               for g in gaps)


def test_locate_gaps_list_count_mismatch():
    ideal = "- parent\n  - child one\n  - child two\n"
    tomd = "- parent\n\nchild one child two\n"
    gaps = locate_gaps(tomd, ideal)
    assert any(g.axis == "list" for g in gaps)


def test_draft_issues_one_per_axis_with_objective_triple():
    gaps = [Gap("heading", "wrong-level", "H1 'A'", "H2 'A'",
                "Body headings start at H2.")]
    drafts = draft_issues("p4228r0", gaps, {"heading": 0.667})
    assert len(drafts) == 1
    draft = drafts[0]
    assert "tomd:" in draft                      # title convention
    assert "heading" in draft.lower()
    assert "H1 'A'" in draft and "H2 'A'" in draft   # located divergence
    assert "Body headings start at H2." in draft     # cited rule
    assert "0.667" in draft                          # the score
    assert "tomd score p4228r0" in draft             # repro command
