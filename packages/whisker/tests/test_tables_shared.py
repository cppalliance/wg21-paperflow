#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Shared pipe/HTML table parser and table-readability integration tests."""

from __future__ import annotations

from pathlib import Path

from whisker.facts import Fact, check_facts
from whisker.llm.table_compare import parse_markdown_tables
from whisker.llm.unit_judge import (
    CONVERSION_CONTRACT,
    TABLE_CONTRACT_SENTINEL,
    UNIT_CHECK_SYSTEM_PROMPT,
    inject_table_rubric,
    resolve_runtime_table_contract,
)
from whisker.tables import parse_html_tables, parse_pipe_tables, split_pipe_cells


def _verified(**kw) -> Fact:
    kw.setdefault("checked", True)
    return Fact(**kw)


def test_escaped_pipe_is_one_cell_not_a_phantom_column():
    line = r"| `float ldexp(float x, int exp)` | Yes | G\|w |"
    cells = split_pipe_cells(line)
    assert cells == ["`float ldexp(float x, int exp)`", "Yes", "G|w"]


def test_unescape_preserves_cpp_and_path_backslashes():
    cells = split_pipe_cells(r"| C:\\tmp\\file | \\n | G\|w |")
    assert cells == [r"C:\tmp\file", r"\n", "G|w"]
    assert split_pipe_cells(r"| foo\nbar | \t | \d |") == [r"foo\nbar", r"\t", r"\d"]
    assert split_pipe_cells(r"| C:\tmp\file |") == [r"C:\tmp\file"]
    assert split_pipe_cells(r"| trail\ |") == ["trail\\"]


def test_odd_even_backslash_runs_before_pipe():
    assert split_pipe_cells(r"| a\|b | c |") == ["a|b", "c"]
    assert split_pipe_cells(r"| a\\|b | c |") == ["a\\", "b", "c"]
    assert split_pipe_cells(r"| a\\\|b | c |") == ["a\\|b", "c"]


def test_p0533r9_class_escaped_pipe_has_no_phantom_column():
    golden = (
        Path(__file__).resolve().parents[2]
        / "tomd"
        / "tests"
        / "fixtures"
        / "golden"
        / "ideals"
        / "p0533r9.md"
    )
    text = golden.read_text(encoding="utf-8")
    grids = parse_pipe_tables(text)
    matching = [
        row
        for grid in grids
        for row in grid
        if any("ldexp" in cell for cell in row)
    ]
    assert matching, "p0533r9 golden must contain the ldexp row"
    row = matching[0]
    assert "G|w" in row
    assert "G\\" not in row
    assert len(row) == 3


def test_fence_isolation_does_not_parse_code_pipes_as_tables():
    md = (
        "```\n"
        "| not | a | table |\n"
        "| --- | --- | --- |\n"
        "| x | y | z |\n"
        "```\n\n"
        "| Real | Col |\n"
        "| --- | --- |\n"
        "| a | b |\n"
    )
    grids = parse_pipe_tables(md)
    assert len(grids) == 1
    assert grids[0][0] == ["Real", "Col"]


def test_malformed_row_without_separator_is_not_a_table():
    md = "| a | b |\n| c | d |\n"
    assert parse_pipe_tables(md) == []
    from whisker.det.llm_readability.models import STATUS_FAIL, STATUS_PASS
    from whisker.det.llm_readability.profile import resolved_core_only
    from whisker.det.llm_readability.validate import evaluate, table_units_from_markdown

    report = evaluate(resolved_core_only(), table_units_from_markdown(md))
    assert report.result("R2").status == STATUS_FAIL
    valid = "| a | b |\n|---|---|\n| c | d |\n"
    report = evaluate(resolved_core_only(), table_units_from_markdown(valid))
    assert report.result("R2").status == STATUS_PASS
    assert parse_pipe_tables(valid)


def test_html_rowspan_denormalizes_and_flags_spans():
    from whisker.tables import _html_tables_with_spans

    md = (
        "<table><tr><th>A</th><th>B</th></tr>"
        "<tr><td rowspan=\"2\">span</td><td>one</td></tr>"
        "<tr><td>two</td></tr></table>"
    )
    detailed = _html_tables_with_spans(md)
    assert len(detailed) == 1
    grid, had_spans = detailed[0]
    assert had_spans is True
    assert grid[1][0] == "span"
    assert grid[2][0] == "span"
    public = parse_html_tables(md)
    assert public[0] == grid


def test_html_code_and_newlines_are_preserved_inside_pre():
    md = "<table><tr><td><pre>line1\nline2</pre></td></tr></table>"
    grid = parse_html_tables(md)[0]
    assert "line1" in grid[0][0]
    assert "line2" in grid[0][0]
    assert "\n" in grid[0][0]


def test_mixed_pipe_and_html_share_one_authority():
    md = (
        "| H | V |\n| --- | --- |\n| a | b |\n\n"
        "<table><tr><th>X</th><th>Y</th></tr>"
        "<tr><td>c</td><td>d</td></tr></table>\n"
    )
    pipes = parse_pipe_tables(md)
    html = parse_html_tables(md)
    combined = parse_markdown_tables(md)
    assert len(pipes) == 1
    assert len(html) == 1
    assert len(combined) == 2
    assert combined[0][0] == ["H", "V"]
    assert combined[1][0] == ["X", "Y"]


def test_source_compare_parser_delegates_to_shared_escape_rules():
    md = "| A | B |\n| --- | --- |\n| G\\|w | yes |\n"
    grids = parse_markdown_tables(md)
    assert grids[0][1] == ["G|w", "yes"]


def test_column_swap_fails_anchored_fact():
    md = (
        "| Feature | Score |\n"
        "| --- | --- |\n"
        "| alpha | 42 |\n"
    )
    swapped = (
        "| Score | Feature |\n"
        "| --- | --- |\n"
        "| 42 | alpha |\n"
    )
    fact = _verified(
        id="t",
        type="table",
        cell="alpha",
        neighbors=(("right", "42"),),
        table_heading="Feature",
    )
    assert check_facts(md, [fact]).passed
    assert check_facts(swapped, [fact]).failed


def test_row_swap_fails_anchored_neighbor():
    md = (
        "| Feature | Score |\n"
        "| --- | --- |\n"
        "| alpha | 42 |\n"
        "| beta | 7 |\n"
    )
    swapped = (
        "| Feature | Score |\n"
        "| --- | --- |\n"
        "| beta | 7 |\n"
        "| alpha | 99 |\n"
    )
    fact = _verified(
        id="t",
        type="table",
        cell="alpha",
        neighbors=(("right", "42"),),
        table_heading="Feature",
    )
    assert check_facts(md, [fact]).passed
    assert check_facts(swapped, [fact]).failed


def test_decoy_table_with_same_heading_fails_closed():
    md = (
        "| Feature | Score |\n| --- | --- |\n| alpha | 42 |\n\n"
        "| Feature | Score |\n| --- | --- |\n| alpha | 99 |\n"
    )
    fact = _verified(
        id="t",
        type="table",
        cell="alpha",
        neighbors=(("right", "42"),),
        table_heading="Feature",
    )
    assert check_facts(md, [fact]).failed


def test_table_capable_prompts_carry_rendered_contract():
    from whisker.det.llm_readability.contract import load_core_contract
    from whisker.llm.pdf_judge import JUDGE_SYSTEM_PROMPT, PAGE_JUDGE_SYSTEM_PROMPT
    from whisker.llm.vlm.transcribe import TRANSCRIPTION_SYSTEM_PROMPT

    resolved = resolve_runtime_table_contract()
    core = load_core_contract()
    for text in (
        UNIT_CHECK_SYSTEM_PROMPT,
        JUDGE_SYSTEM_PROMPT,
        PAGE_JUDGE_SYSTEM_PROMPT,
        TRANSCRIPTION_SYSTEM_PROMPT,
        CONVERSION_CONTRACT,
    ):
        hydrated = inject_table_rubric(text, resolved)
        assert core.id in hydrated
        assert core.hash in hydrated
        assert "R6" in hydrated
        assert TABLE_CONTRACT_SENTINEL not in hydrated
    assert "lossy-table" in CONVERSION_CONTRACT
    assert "Convert tables to Markdown pipe tables." not in TRANSCRIPTION_SYSTEM_PROMPT


def test_whisker_tables_cli_routes_from_main(capsys):
    from whisker.__main__ import main
    from whisker.det.llm_readability.contract import load_core_contract

    assert main(["llm-readability", "rules"]) == 0
    out = capsys.readouterr().out
    assert "R13" in out
    assert load_core_contract().hash in out


def test_whisker_tables_unknown_profile_is_fail_closed(capsys):
    from whisker.__main__ import main

    assert main(["llm-readability", "rules", "--profile", "ghost"]) == 1
    assert "profile_missing" in capsys.readouterr().err


def test_candidate_only_check_is_incomplete_not_certified(tmp_path, capsys):
    from whisker.__main__ import main

    path = tmp_path / "t.md"
    path.write_text(
        "| Option | Votes |\n|---|---|\n| SF | 4 |\n",
        encoding="utf-8",
    )
    code = main(["llm-readability", "check", str(path), "--json"])
    assert code in (3, 5)
    payload = __import__("json").loads(capsys.readouterr().out)
    assert payload["model_certified"] is False
    assert payload["certified"] is False
    assert payload["blocking_reasons"]


def test_hard_not_evaluated_blocks_certified():
    from whisker.det.llm_readability.models import STATUS_NOT_EVALUATED, STRENGTH_HARD
    from whisker.det.llm_readability.profile import resolved_core_only
    from whisker.det.llm_readability.validate import evaluate, table_units_from_markdown

    report = evaluate(
        resolved_core_only(),
        table_units_from_markdown("| A | B |\n|---|---|\n| 1 | 2 |\n"),
    )
    hard_uneval = [
        item
        for item in report.results
        if item.status == STATUS_NOT_EVALUATED and item.strength == STRENGTH_HARD
    ]
    assert hard_uneval
    assert report.model_certified is False
    assert any(
        reason.startswith("hard_rule_not_evaluated:")
        for reason in report.blocking_reasons
    )
