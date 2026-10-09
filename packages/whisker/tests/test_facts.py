#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

import pytest
from whisker.det.corpus_tools import classify_paper, draft_facts_scaffold
from whisker.facts import (
    Fact,
    auto_baseline_checks,
    check_facts,
    facts_from_records,
    parse_facts_jsonl,
)

_MD = """## Overview

The allocator model uses polymorphic storage for the container.

The energy is $E = mc^2$ in the relativistic limit.

| Feature    | Status | Owner |
|------------|--------|-------|
| coroutines | done   | SG1   |
| executors  | wip    | LEWG  |

First we discuss motivation, then design, finally wording.
"""


def _verified(**kw) -> Fact:
    kw.setdefault("checked", True)
    return Fact(**kw)


# -- present / absent --------------------------------------------------------


def test_present_exact_pass():
    rep = check_facts(_MD, [_verified(id="p", type="present", text="polymorphic storage")])
    assert rep.passed


def test_present_missing_fails():
    rep = check_facts(_MD, [_verified(id="p", type="present", text="quantum entanglement")])
    assert rep.failed
    assert "absent" in rep.failures()[0].detail


def test_present_fuzzy_within_budget_passes():
    # "polymorfic" is 2 edits from "polymorphic" (f->p sub + h insert).
    rep = check_facts(
        _MD, [_verified(id="p", type="present", text="polymorfic storage", max_diffs=2)]
    )
    assert rep.passed


def test_present_fuzzy_beyond_budget_fails():
    rep = check_facts(
        _MD, [_verified(id="p", type="present", text="polymorfic storage", max_diffs=1)]
    )
    assert rep.failed


def test_absent_pass_and_fail():
    ok = check_facts(_MD, [_verified(id="a", type="absent", text="deprecated junk")])
    assert ok.passed
    bad = check_facts(_MD, [_verified(id="a", type="absent", text="polymorphic storage")])
    assert bad.failed
    assert "present" in bad.failures()[0].detail


# -- math --------------------------------------------------------------------


def test_math_structural_pass():
    rep = check_facts(_MD, [_verified(id="m", type="math", text="E = mc^2")])
    assert rep.passed


def test_math_missing_exponent_fails():
    rep = check_facts(_MD, [_verified(id="m", type="math", text="E = mc^3")])
    assert rep.failed


def test_math_ignores_dollar_delimiters():
    # The surface folds LaTeX; the bare formula matches the $-wrapped source.
    rep = check_facts(_MD, [_verified(id="m", type="math", text="$E = mc^2$")])
    assert rep.passed


# -- order -------------------------------------------------------------------


def test_order_monotonic_pass():
    rep = check_facts(
        _MD, [_verified(id="o", type="order", sequence=("motivation", "design", "wording"))]
    )
    assert rep.passed


def test_order_reversed_fails():
    rep = check_facts(
        _MD, [_verified(id="o", type="order", sequence=("wording", "design", "motivation"))]
    )
    assert rep.failed


def test_order_missing_item_fails():
    rep = check_facts(
        _MD, [_verified(id="o", type="order", sequence=("motivation", "absent-section"))]
    )
    assert rep.failed
    assert "absent" in rep.failures()[0].detail


# -- table neighbor graph ----------------------------------------------------


def test_table_neighbors_pass():
    fact = _verified(
        id="t", type="table", cell="executors",
        neighbors=(("right", "wip"), ("up", "coroutines"), ("heading", "Feature")),
    )
    assert check_facts(_MD, [fact]).passed


def test_table_left_and_down_neighbors():
    fact = _verified(
        id="t", type="table", cell="done",
        neighbors=(("left", "coroutines"), ("down", "wip")),
    )
    assert check_facts(_MD, [fact]).passed


def test_table_wrong_neighbor_fails():
    fact = _verified(
        id="t", type="table", cell="executors", neighbors=(("right", "done"),),
    )
    rep = check_facts(_MD, [fact])
    assert rep.failed
    assert "right" in rep.failures()[0].detail


def test_table_missing_cell_fails():
    fact = _verified(
        id="t", type="table", cell="nonexistent", neighbors=(("right", "x"),),
    )
    rep = check_facts(_MD, [fact])
    assert rep.failed
    assert "not found" in rep.failures()[0].detail


def test_table_out_of_bounds_neighbor_fails():
    # "coroutines" is first-column; it has no left neighbor.
    fact = _verified(
        id="t", type="table", cell="coroutines", neighbors=(("left", "anything"),),
    )
    rep = check_facts(_MD, [fact])
    assert rep.failed
    assert "out of bounds" in rep.failures()[0].detail


def test_table_heading_neighbor_is_column_header():
    # "up" of a body cell in row 1 is the header row, same as "heading".
    fact = _verified(
        id="t", type="table", cell="coroutines",
        neighbors=(("up", "Feature"), ("heading", "Feature")),
    )
    assert check_facts(_MD, [fact]).passed


def test_table_neighbor_fuzzy_within_budget():
    fact = _verified(
        id="t", type="table", cell="executors",
        neighbors=(("right", "wpi"),), max_diffs=2,  # transposed
    )
    assert check_facts(_MD, [fact]).passed


# -- verified gate -----------------------------------------------------------


def test_unverified_failing_fact_does_not_gate():
    draft = Fact(id="d", type="present", text="quantum entanglement", checked=False)
    rep = check_facts(_MD, [draft])
    # The check is recorded and failing, but the report passes (draft not gated).
    assert rep.checks[0].passed is False
    assert rep.checks[0].verified is False
    assert rep.passed
    assert "not gated" in rep.checks[0].detail


def test_verified_failing_fact_gates():
    rep = check_facts(_MD, [_verified(id="v", type="present", text="quantum entanglement")])
    assert rep.failed


def test_no_verified_facts_passes():
    draft = Fact(id="d", type="present", text="anything", checked=False)
    assert check_facts(_MD, [draft]).passed


# -- reporting ---------------------------------------------------------------


def test_by_type_macro_average_over_verified_only():
    facts = [
        _verified(id="p1", type="present", text="polymorphic storage"),
        _verified(id="p2", type="present", text="quantum entanglement"),
        Fact(id="p3", type="present", text="ignored draft", checked=False),
        _verified(id="a1", type="absent", text="missing junk"),
    ]
    rep = check_facts(_MD, facts, "P1")
    by_type = rep.by_type()
    assert by_type["present"] == {"passed": 1, "total": 2, "pass_rate": 0.5}
    assert by_type["absent"]["pass_rate"] == 1.0
    d = rep.to_dict()
    assert d["pid"] == "P1"
    assert d["verified_count"] == 3
    assert d["total_count"] == 4


# -- loader / validation -----------------------------------------------------


def test_parse_jsonl_roundtrip_and_blank_lines():
    text = (
        '{"id":"f1","type":"present","text":"alpha","checked":"verified"}\n'
        "\n"
        '   \n'
        '{"id":"f2","type":"absent","text":"beta"}\n'
    )
    facts = parse_facts_jsonl(text, "P1")
    assert len(facts) == 2
    assert facts[0].checked is True
    assert facts[1].checked is False  # no checked field -> draft
    assert facts[0].question == ""
    assert facts[1].question == ""


def test_parse_jsonl_loads_authored_question():
    text = (
        '{"id":"f1","type":"present","text":"alpha","checked":"verified",'
        '"question":"What term is used? Quote it."}\n'
    )
    facts = parse_facts_jsonl(text, "P1")
    assert facts[0].question == "What term is used? Quote it."


def test_question_must_be_a_string():
    with pytest.raises(ValueError, match="question"):
        facts_from_records([
            {"id": "x", "type": "present", "text": "a", "question": 1},
        ])


def test_checked_only_verified_promotes():
    facts = parse_facts_jsonl(
        '{"id":"x","type":"present","text":"a","checked":"draft"}\n', "P1"
    )
    assert facts[0].checked is False


def test_invalid_json_reports_line_number():
    with pytest.raises(ValueError, match="line 2"):
        parse_facts_jsonl('{"id":"ok","type":"absent","text":"a"}\n{bad json}\n', "P1")


def test_unknown_type_raises():
    with pytest.raises(ValueError, match="type"):
        facts_from_records([{"id": "x", "type": "nonsense", "text": "a"}])


def test_present_requires_text():
    with pytest.raises(ValueError, match="text"):
        facts_from_records([{"id": "x", "type": "present"}])


def test_order_requires_two_items():
    with pytest.raises(ValueError, match="sequence"):
        facts_from_records([{"id": "x", "type": "order", "sequence": ["only one"]}])


def test_table_requires_cell_and_neighbors():
    with pytest.raises(ValueError, match="cell"):
        facts_from_records([{"id": "x", "type": "table", "neighbors": {"up": "a"}}])
    with pytest.raises(ValueError, match="neighbors"):
        facts_from_records([{"id": "x", "type": "table", "cell": "c"}])


def test_verified_table_fact_requires_table_heading():
    with pytest.raises(ValueError, match="table_heading"):
        facts_from_records([{
            "id": "x",
            "type": "table",
            "cell": "alpha",
            "neighbors": {"right": "42"},
            "checked": "verified",
        }])


def test_draft_table_fact_may_omit_table_heading():
    facts = facts_from_records([{
        "id": "x",
        "type": "table",
        "cell": "alpha",
        "neighbors": {"right": "42"},
        "checked": "draft",
    }])
    assert facts[0].table_heading == ""
    assert facts[0].checked is False


def test_bad_neighbor_direction_raises():
    with pytest.raises(ValueError, match="direction"):
        facts_from_records(
            [{"id": "x", "type": "table", "cell": "c", "neighbors": {"northwest": "a"}}]
        )


def test_negative_max_diffs_raises():
    with pytest.raises(ValueError, match="max_diffs"):
        facts_from_records([{"id": "x", "type": "present", "text": "a", "max_diffs": -1}])


def test_bool_max_diffs_raises():
    # bool is an int subclass; reject it explicitly so True/False is not a budget.
    with pytest.raises(ValueError, match="max_diffs"):
        facts_from_records([{"id": "x", "type": "present", "text": "a", "max_diffs": True}])


def test_duplicate_id_raises():
    with pytest.raises(ValueError, match="duplicate"):
        facts_from_records([
            {"id": "dup", "type": "present", "text": "a"},
            {"id": "dup", "type": "absent", "text": "b"},
        ])


def test_neighbors_sorted_by_direction_order():
    facts = facts_from_records([{
        "id": "t", "type": "table", "cell": "c",
        "neighbors": {"heading": "h", "up": "u", "right": "r"},
    }])
    # Stable ordering: up, right, heading (per the fixed direction tuple).
    assert [d for d, _ in facts[0].neighbors] == ["up", "right", "heading"]


def test_id_defaults_to_type_index():
    facts = facts_from_records([{"type": "present", "text": "a"}])
    assert facts[0].id == "present[0]"


# -- surface: raw mode -------------------------------------------------------


def test_raw_surface_present_preserves_operators():
    md = "The expression x != y is always checked."
    ok = check_facts(md, [_verified(id="r", type="present", text="x != y", surface="raw")])
    assert ok.passed
    bad = check_facts(md, [_verified(id="r", type="present", text="x == y", surface="raw")])
    assert bad.failed


def test_raw_surface_preserves_case():
    md = "Use the C++ standard library."
    ok = check_facts(md, [_verified(id="r", type="present", text="C++", surface="raw")])
    assert ok.passed
    bad = check_facts(md, [_verified(id="r", type="present", text="c++", surface="raw")])
    assert bad.failed


def test_raw_surface_absent():
    md = "The result is x == y."
    ok = check_facts(md, [_verified(id="r", type="absent", text="x != y", surface="raw")])
    assert ok.passed
    bad = check_facts(md, [_verified(id="r", type="absent", text="x == y", surface="raw")])
    assert bad.failed


def test_raw_surface_order():
    md = "First x != y, then x == y appears."
    ok = check_facts(
        md, [_verified(id="o", type="order", sequence=("x != y", "x == y"), surface="raw")]
    )
    assert ok.passed
    bad = check_facts(
        md, [_verified(id="o", type="order", sequence=("x == y", "x != y"), surface="raw")]
    )
    assert bad.failed


def test_invalid_surface_raises():
    with pytest.raises(ValueError, match="surface"):
        facts_from_records([{"id": "x", "type": "present", "text": "a", "surface": "bogus"}])


# -- code / xref / image_ref types -------------------------------------------


def test_code_fact_pass():
    md = "Some text.\n```cpp\nint main() { return 0; }\n```\n"
    ok = check_facts(md, [_verified(id="c", type="code", text="int main()")])
    assert ok.passed


def test_code_fact_missing():
    md = "No code here."
    rep = check_facts(md, [_verified(id="c", type="code", text="int main()")])
    assert rep.failed
    assert "code snippet" in rep.failures()[0].detail


def test_xref_fact_pass():
    md = "See [P1234R5] for details."
    ok = check_facts(md, [_verified(id="x", type="xref", text="[P1234R5]")])
    assert ok.passed


def test_xref_fact_wrong_revision():
    md = "See [P1234R4] for details."
    rep = check_facts(md, [_verified(id="x", type="xref", text="[P1234R5]")])
    assert rep.failed


def test_image_ref_fact_pass():
    md = "Figure: ![diagram](images/fig1.png)\n"
    ok = check_facts(md, [_verified(id="i", type="image_ref", text="")])
    assert ok.passed


def test_image_ref_fact_with_text():
    md = "Figure: ![diagram](images/fig1.png)\n"
    ok = check_facts(md, [_verified(id="i", type="image_ref", text="fig1.png")])
    assert ok.passed
    bad = check_facts(md, [_verified(id="i", type="image_ref", text="fig2.png")])
    assert bad.failed


def test_image_ref_fact_no_image():
    md = "No images in this paper."
    rep = check_facts(md, [_verified(id="i", type="image_ref", text="")])
    assert rep.failed
    assert "image reference" in rep.failures()[0].detail


def test_code_and_xref_always_raw_surface():
    facts = facts_from_records([
        {"id": "c", "type": "code", "text": "x != y"},
        {"id": "x", "type": "xref", "text": "[P1234R5]"},
    ])
    assert facts[0].surface == "raw"
    assert facts[1].surface == "raw"


# -- auto-baseline checks ---------------------------------------------------


def test_auto_baseline_nonempty_passes():
    md = "a" * 100
    checks = auto_baseline_checks(md)
    nonempty = next(c for c in checks if c.id == "baseline-nonempty")
    assert nonempty.passed


def test_auto_baseline_nonempty_fails_on_empty():
    checks = auto_baseline_checks("")
    nonempty = next(c for c in checks if c.id == "baseline-nonempty")
    assert not nonempty.passed


def test_auto_baseline_repeated_ngrams_passes_clean():
    md = (
        "This is a document about C++ allocators. "
        "Section 2 describes the memory model in detail. "
        "The proposal targets LEWG review at the next meeting. "
        "Table 1 shows benchmark results across platforms. "
        "We conclude that the approach is sound and ready for wording. "
    )
    checks = auto_baseline_checks(md)
    ngram = next(c for c in checks if c.id == "baseline-no-repeated-ngrams")
    assert ngram.passed


def test_auto_baseline_repeated_ngrams_fails_mojibake():
    md = "abcabc" * 200
    checks = auto_baseline_checks(md)
    ngram = next(c for c in checks if c.id == "baseline-no-repeated-ngrams")
    assert not ngram.passed


def test_auto_baseline_all_verified():
    checks = auto_baseline_checks("Normal document content " * 50)
    assert all(c.verified for c in checks)


# -- CI canaries (one per verified exploit class) ----------------------------


_DECOY_TABLE_MD = """\
## Real results

| Feature | Score |
|---------|-------|
| alpha   | 42    |

## Decoy

| Feature | Score |
|---------|-------|
| alpha   | 99    |
"""


def test_canary_decoy_table_all_occurrences():
    """With table_heading set, EVERY occurrence must satisfy the neighbors.

    The decoy table shares the heading and contradicts the real row, so the
    fact must fail closed instead of passing via the genuine occurrence
    (first-match-wins decoy exploit, red-team finding Jul 2026).
    """
    fact_heading = _verified(
        id="d", type="table", cell="alpha",
        neighbors=(("right", "42"),), table_heading="Feature",
    )
    rep = check_facts(_DECOY_TABLE_MD, [fact_heading])
    assert rep.failed, "conflicting decoy occurrence under same heading must fail closed"

    fact_no_heading = _verified(
        id="d2", type="table", cell="alpha",
        neighbors=(("right", "42"),),
    )
    assert check_facts(_DECOY_TABLE_MD, [fact_no_heading]).passed, (
        "without heading filter, at least one occurrence of alpha->42 must pass"
    )


_CLEAN_HEADING_MD = """\
## Results

| Feature | Score |
|---------|-------|
| alpha   | 42    |

## Unrelated table (no Feature heading)

| Name  | Score |
|-------|-------|
| alpha | 99    |
"""


def test_table_heading_all_semantics_pass_when_consistent():
    """Heading filter scopes ALL-semantics: tables without the heading are ignored."""
    fact = _verified(
        id="c", type="table", cell="alpha",
        neighbors=(("right", "42"),), table_heading="Feature",
    )
    assert check_facts(_CLEAN_HEADING_MD, [fact]).passed


def test_canary_decoy_table_wrong_heading_fails():
    """table_heading mismatch must not silently pass via a different table."""
    fact = _verified(
        id="d", type="table", cell="alpha",
        neighbors=(("right", "42"),), table_heading="NonexistentHeader",
    )
    rep = check_facts(_DECOY_TABLE_MD, [fact])
    assert rep.failed


_HTML_TABLE_MD = """\
Some text.

<table>
<tr><th>Name</th><th>Value</th></tr>
<tr><td>widget</td><td>100</td></tr>
<tr><td>gadget</td><td>200</td></tr>
</table>
"""


def test_canary_html_table_cell_check():
    """HTML-emitted tables must be visible to fact checks."""
    ok = check_facts(
        _HTML_TABLE_MD,
        [_verified(id="h", type="table", cell="widget", neighbors=(("right", "100"),))],
    )
    assert ok.passed


def test_canary_html_table_scramble_detected():
    """A scrambled HTML table neighbor must fail."""
    bad = check_facts(
        _HTML_TABLE_MD,
        [_verified(id="h", type="table", cell="widget", neighbors=(("right", "200"),))],
    )
    assert bad.failed


def test_canary_operator_flip():
    """raw surface must distinguish >= from <= (operator-flip exploit)."""
    md = "The threshold is x >= 42."
    ok = check_facts(md, [_verified(id="op", type="present", text="x >= 42", surface="raw")])
    assert ok.passed
    bad = check_facts(md, [_verified(id="op", type="present", text="x <= 42", surface="raw")])
    assert bad.failed


def test_canary_pipe_split_in_code():
    """Pipes inside fenced code must not be parsed as table rows."""
    md = "```\nif (a | b) { return c | d; }\n```\n"
    fact = _verified(id="p", type="table", cell="a", neighbors=(("right", "b"),))
    rep = check_facts(md, [fact])
    assert rep.failed, "pipes inside code fences must not be parsed as tables"


def test_classify_paper_detects_strata():
    md = (
        "## Title\n\n"
        "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
        "$$E = mc^2$$\n\n"
        "```cpp\nint main() {}\n```\n"
        "```python\nprint('hi')\n```\n"
        "```rust\nfn main() {}\n```\n"
        "See [^1] for details.\n"
        "![fig](img.png)\n"
        "[^1]: footnote\n"
    )
    info = classify_paper("P9999R0", md)
    assert "table" in info.strata
    assert "display_math" in info.strata
    assert "code_heavy" in info.strata
    assert "footnotes" in info.strata
    assert "images" in info.strata


def test_classify_paper_ignores_cpp_negated_character_class():
    info = classify_paper("P1040R10", "Match `[^*path-separators*]` here.\n")
    assert info.footnote_count == 0
    assert "footnotes" not in info.strata


def test_classify_paper_ignores_unpaired_canonical_marker():
    info = classify_paper("P0001R0", "See [^1] for details.\n")
    assert info.footnote_count == 0
    assert "footnotes" not in info.strata


def test_classify_paper_ignores_ordinal_superscript():
    info = classify_paper("P0001R0", "The 5<sup>th</sup> revision.\n")
    assert info.footnote_count == 0
    assert "footnotes" not in info.strata


def test_classify_paper_detects_paired_canonical_footnote():
    md = "See [^1] for details.\n\n[^1]: Canonical footnote.\n"
    info = classify_paper("P0001R0", md)
    assert info.footnote_count == 1
    assert "footnotes" in info.strata


def test_classify_paper_detects_paired_html_footnote():
    md = "A claim.<sup>1</sup>\n\n1. Numbered terminal note. ↩︎\n"
    info = classify_paper("P0001R0", md)
    assert info.footnote_count == 1
    assert "footnotes" in info.strata


def test_classify_paper_ignores_dollars_inside_code_fences():
    """$$ inside fenced code (e.g. $-prefixed identifiers, P4234R0) is not math."""
    md = (
        "## Title\n\n"
        "```cpp\n"
        "auto $$counter = 0;\n"
        "auto $$other = $$counter + 1;\n"
        "```\n\n"
        "Plain prose without any math.\n"
    )
    info = classify_paper("P4234R0", md)
    assert info.display_math_count == 0
    assert "display_math" not in info.strata

    md_real_math = md + "\n$$E = mc^2$$\n"
    info2 = classify_paper("P4234R0", md_real_math)
    assert info2.display_math_count == 1
    assert "display_math" in info2.strata


def test_draft_facts_scaffold_generates_records():
    md = (
        "# Paper Title\n\n"
        "## Section A\n\n"
        "Some text.\n\n"
        "| Feature | Score |\n|---------|-------|\n| alpha | 42 |\n\n"
        "$$x^2 + y^2 = z^2$$\n\n"
        "See [P1234R5] for details.\n"
    )
    records = draft_facts_scaffold("P0001R0", md)
    assert len(records) >= 3
    assert all(r["checked"] == "draft" for r in records)
    types = {r["type"] for r in records}
    assert "order" in types or "present" in types
    assert "table" in types
    table_recs = [r for r in records if r["type"] == "table"]
    assert table_recs
    assert all(r.get("table_heading") for r in table_recs)


def test_canary_math_scope_case_and_relation():
    """Math surface preserves case and relational operators."""
    md = "If $X >= Y$ then the bound holds."
    ok = check_facts(md, [_verified(id="m", type="math", text="X >= Y")])
    assert ok.passed
    bad_case = check_facts(md, [_verified(id="m", type="math", text="x >= y")])
    assert bad_case.failed, "math surface must be case-sensitive"
    bad_op = check_facts(md, [_verified(id="m", type="math", text="X <= Y")])
    assert bad_op.failed, "math surface must distinguish >= from <="


def test_canary_math_scope_display_delimiters():
    """Math surface treats \\[...\\] display math the same as \\(...\\) inline.

    Regression for a live whisker-readback finding (2026-07-08): the
    alliance-pod correctly reproduced a formula from the corpus but wrapped it
    in a multi-line display-math block (``\\[\\n x^{2k} \\geq 0 \\n\\]``)
    instead of the source's single-line inline delimiters. The formula
    content was identical; only the wrapper and internal newlines differed. A
    math fact written against inline-delimited source text must still match
    display-delimited prose expressing the same formula, including when the
    block spans multiple lines.
    """
    md = "The relation \\[\nx^{2k} \\geq 0\n\\] holds for all real x."
    ok = check_facts(
        md, [_verified(id="m", type="math", text=r"\(x^{2k} \geq 0\)")]
    )
    assert ok.passed, "math surface must fold multi-line \\[...\\] like \\(...\\)"


def test_canary_math_scope_doubled_backslashes():
    """Math surface undoubles \\\\command backslashes before folding.

    Regression for a live whisker-readback finding (2026-07-08): the
    alliance-pod returned a formula with every LaTeX command backslash
    doubled (``\\\\text{rms}``, ``\\\\cdot``, ``\\\\sin``, ``\\\\varphi``).
    pylatexenc parses ``\\\\`` as a line-break command, leaving the command
    name as literal text and silently breaking the fold. A math fact must
    still match a doubled-backslash paraphrase of the same formula.
    """
    md = (
        r"The exact formula is: \\(Q = U_\\text{rms} \\cdot I_\\text{rms} "
        r"\\cdot \\sin\\varphi\\)"
    )
    ok = check_facts(
        md,
        [_verified(
            id="m", type="math",
            text=r"\(Q = U_\text{rms} \cdot I_\text{rms} \cdot \sin\varphi\)",
        )],
    )
    assert ok.passed, "math surface must undouble \\\\command before folding"
