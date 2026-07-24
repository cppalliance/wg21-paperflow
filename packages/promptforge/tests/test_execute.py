#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the single-section execution loop."""

from __future__ import annotations

import pytest

from promptforge.errors import IncompleteError, PostconditionError
from promptforge.execute import SectionResult, ToolResult, run_section
from promptforge.inference import ScriptedModel, tool_call, turn


def _dispatch_table(table, recorder=None):
    def dispatch(name, args):
        if recorder is not None:
            recorder.append((name, dict(args)))
        return table.get(name, ToolResult(f"ok:{name}"))

    return dispatch


def test_success_runs_tools_then_done() -> None:
    model = ScriptedModel([
        turn(tool_call("add_claim", quote="x", line=1)),
        turn(tool_call("done")),
    ])
    recorder: list = []
    dispatch = _dispatch_table(
        {"done": ToolResult("", done=True)},
        recorder,
    )
    result = run_section(
        prose="Extract claims.",
        model=model,
        tool_schemas=[],
        dispatch=dispatch,
    )
    assert isinstance(result, SectionResult)
    assert result.status == "done"
    assert result.tool_counts == {"add_claim": 1, "done": 1}
    assert recorder[0][0] == "add_claim"


def test_goto_stops_with_transition() -> None:
    model = ScriptedModel([turn(tool_call("goto", section="## Classify"))])
    dispatch = _dispatch_table(
        {"goto": ToolResult("going to ## Classify", transition="## Classify")}
    )
    result = run_section(prose="Route.", model=model, tool_schemas=[], dispatch=dispatch)
    assert result.status == "goto"
    assert result.transition == "## Classify"


def test_incomplete_when_done_never_called() -> None:
    # Every turn calls a regular tool, never done; budget runs out.
    model = ScriptedModel([turn(tool_call("noop")) for _ in range(3)])
    with pytest.raises(IncompleteError):
        run_section(
            prose="x",
            model=model,
            tool_schemas=[],
            dispatch=_dispatch_table({}),
            max_turns=3,
        )


def test_postcondition_failure_propagates() -> None:
    model = ScriptedModel([turn(tool_call("done"))])

    def failing_check():
        raise PostconditionError("no items filed")

    with pytest.raises(PostconditionError):
        run_section(
            prose="x",
            model=model,
            tool_schemas=[],
            dispatch=_dispatch_table({"done": ToolResult("", done=True)}),
            run_check=failing_check,
        )


def test_task_call_and_continue() -> None:
    model = ScriptedModel([
        turn(tool_call("task", section="## Digest")),
        turn(tool_call("done")),
    ])
    recorder: list = []
    dispatch = _dispatch_table(
        {
            "task": ToolResult("digest returned metadata"),
            "done": ToolResult("", done=True),
        },
        recorder,
    )
    result = run_section(prose="Orchestrate.", model=model, tool_schemas=[], dispatch=dispatch)
    assert result.status == "done"
    assert [c[0] for c in recorder] == ["task", "done"]


def test_no_tool_call_turn_gets_nudged() -> None:
    model = ScriptedModel([
        turn(text="Let me think about this."),
        turn(tool_call("done")),
    ])
    result = run_section(
        prose="x",
        model=model,
        tool_schemas=[],
        dispatch=_dispatch_table({"done": ToolResult("", done=True)}),
    )
    assert result.status == "done"
    # Two model calls: the thinking turn plus the done turn after the nudge.
    assert len(model.calls) == 2


def test_multiple_tool_calls_in_one_turn() -> None:
    model = ScriptedModel([
        turn(
            tool_call("file_section", criterion="A"),
            tool_call("file_missing", criterion="B"),
            tool_call("done"),
        ),
    ])
    result = run_section(
        prose="x",
        model=model,
        tool_schemas=[],
        dispatch=_dispatch_table({"done": ToolResult("", done=True)}),
    )
    assert result.status == "done"
    assert result.tool_counts["file_section"] == 1
    assert result.tool_counts["file_missing"] == 1
