#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the runtime: goto, Task, fanout, retry, and caps."""

from __future__ import annotations

import pytest

from promptforge.errors import (
    DepthLimitError,
    PreconditionError,
    TaskLimitError,
)
from promptforge.inference import ScriptedModel, tool_call, turn
from promptforge.runtime import Runtime
from promptforge.store import MemStore

# Each pipeline below is a small hand-written program. The single ScriptedModel
# serves every section, so its queue is the interleaved order of model calls.


def test_goto_transitions_between_sections() -> None:
    md = (
        "## Main\n\nRoute.\n\n```lua\ntools.add(\"goto\", \"done\")\n```\n\n"
        "## Classify\n\nClassify.\n\n```lua\ntools.add(\"set_result\", \"done\")\n```\n"
    )
    model = ScriptedModel([
        turn(tool_call("goto", section="## Classify")),
        turn(tool_call("set_result", value="library"), tool_call("done")),
    ])
    runtime = Runtime(md, model=model)

    def set_result(value: str) -> str:
        runtime.ctx.store.put("result", value)
        return "set"

    runtime.registry.register(set_result)

    result = runtime.execute()
    assert result.ok
    assert result.store.get("result") == "library"


def test_task_isolates_child_store_and_merges_back() -> None:
    md = (
        "## Main\n\nDelegate.\n\n```lua\ntools.add(\"task\", \"done\")\n```\n\n"
        "## Child\n\nWork.\n\n```lua\ntools.add(\"file_item\", \"done\")\n```\n"
    )
    model = ScriptedModel([
        turn(tool_call("task", section="## Child")),
        turn(tool_call("file_item", chunk=0), tool_call("done")),
        turn(tool_call("done")),
    ])
    runtime = Runtime(md, model=model)

    def file_item(chunk: int) -> str:
        runtime.ctx.store.add("items", {"chunk": chunk})
        return "filed"

    runtime.registry.register(file_item)

    result = runtime.execute()
    assert result.ok
    # The child filed into its isolated store, which merged back into Main's.
    assert result.store.count("items") == 1


def test_depth_limit_enforced() -> None:
    md = (
        "## Main\n\n```lua\ntools.add(\"task\", \"done\")\n```\n\n"
        "## Recur\n\n```lua\ntools.add(\"task\", \"done\")\n```\n"
    )
    model = ScriptedModel([
        turn(tool_call("task", section="## Recur")),
        turn(tool_call("task", section="## Recur")),
    ])
    runtime = Runtime(md, model=model, max_depth=1)
    with pytest.raises(DepthLimitError):
        runtime.execute()


def test_task_limit_enforced() -> None:
    md = (
        "## Main\n\n```lua\ntools.add(\"task\", \"done\")\n```\n\n"
        "## Leaf\n\n```lua\ntools.add(\"done\")\n```\n"
    )
    model = ScriptedModel([
        turn(tool_call("task", section="## Leaf")),
        turn(tool_call("done")),
        turn(tool_call("task", section="## Leaf")),
        turn(tool_call("done")),
        turn(tool_call("task", section="## Leaf")),
    ])
    runtime = Runtime(md, model=model, max_tasks=2)
    with pytest.raises(TaskLimitError):
        runtime.execute()


def test_retry_restores_store_and_counts_attempts() -> None:
    md = (
        "## Challenge\n\nJudge every finding.\n\n```lua\n"
        "tools.add(\"file_verdict\", \"done\")\n"
        "function check()\n"
        "  assert(store.count(\"verdicts\") == store.count(\"findings\"), \"incomplete\")\n"
        "end\n```\n"
    )
    model = ScriptedModel([
        # Attempt 1: judges only 3 of 5, then done -> postcondition fails.
        turn(
            tool_call("file_verdict", id=1),
            tool_call("file_verdict", id=2),
            tool_call("file_verdict", id=3),
            tool_call("done"),
        ),
        # Attempt 2 (fresh context, rolled-back store): judges all 5.
        turn(
            tool_call("file_verdict", id=1),
            tool_call("file_verdict", id=2),
            tool_call("file_verdict", id=3),
            tool_call("file_verdict", id=4),
            tool_call("file_verdict", id=5),
            tool_call("done"),
        ),
    ])
    store = MemStore({"findings": [{}, {}, {}, {}, {}]})
    runtime = Runtime(md, model=model, store=store, retries=1)

    def file_verdict(id: int) -> str:
        runtime.ctx.store.add("verdicts", {"id": id})
        return f"verdict {id}"

    runtime.registry.register(file_verdict)

    out = runtime.execute_section("## Challenge")
    assert out.ok
    assert out.attempts == 2
    # 5, not 8: attempt 1's three verdicts were rolled back before the retry.
    assert runtime.store.count("verdicts") == 5


def test_precondition_failure_is_not_retried() -> None:
    md = (
        "## Guard\n\n```lua\n"
        "assert(state.ready == true, \"not ready\")\n"
        "tools.add(\"done\")\n```\n"
    )
    model = ScriptedModel([turn(tool_call("done"))])
    runtime = Runtime(md, model=model, retries=1)
    with pytest.raises(PreconditionError):
        runtime.execute_section("## Guard")
    # The model was never called: the section failed before launch.
    assert model.calls == []


def test_lua_fanout_runs_each_task_and_merges() -> None:
    md = (
        "## Main\n\n```lua\ntools.add(\"goto\", \"done\")\n```\n\n"
        "## FanAll\n\n```lua\n"
        "fanout({{section = \"## Work\", params = {n = 1}}, "
        "{section = \"## Work\", params = {n = 2}}})\n```\n\n"
        "## Work\n\nRecord n.\n\n```lua\ntools.add(\"record\", \"done\")\n```\n"
    )
    model = ScriptedModel([
        turn(tool_call("goto", section="## FanAll")),
        turn(tool_call("record", n=1), tool_call("done")),
        turn(tool_call("record", n=2), tool_call("done")),
    ])
    runtime = Runtime(md, model=model)

    def record(n: int) -> str:
        runtime.ctx.store.add("done_work", {"n": n})
        return "recorded"

    runtime.registry.register(record)

    result = runtime.execute()
    assert result.ok
    assert result.store.count("done_work") == 2
    ns = sorted(item["n"] for item in result.store.get("done_work"))
    assert ns == [1, 2]
