#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

import pytest

from whisker.facts import (
    Fact,
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
