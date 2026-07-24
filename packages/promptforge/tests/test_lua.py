#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the sandboxed Lua configuration layer."""

from __future__ import annotations

import pytest

from promptforge.errors import PreconditionError, PostconditionError
from promptforge.lua import configure_section
from promptforge.parser import Document
from promptforge.store import MemStore


def _cfg(code, store=None, params=None, document=None):
    return configure_section(
        code,
        store=store if store is not None else MemStore(),
        params=params or {},
        document=document,
    )


def test_model_selection() -> None:
    assert _cfg('model("gemma-27b")').model_slot == "gemma-27b"


def test_no_lua_returns_defaults() -> None:
    c = configure_section(None, store=MemStore(), params={}, document=None)
    assert c.model_slot is None
    assert c.tools == []
    assert c.injected == []
    c.run_check()  # no-op, must not raise


def test_tools_add_remove_dedup_and_order() -> None:
    c = _cfg('tools.add("a", "b", "c"); tools.remove("b"); tools.add("a", "d")')
    assert c.tools == ["a", "c", "d"]


def test_context_inject_preserves_order() -> None:
    c = _cfg('context.inject("first"); context.inject("second")')
    assert c.injected == ["first", "second"]


def test_precondition_passes_when_true() -> None:
    store = MemStore({"chunks_total": 3})
    _cfg('assert(state.chunks_total > 0, "no chunks")', store=store)


def test_precondition_raises_with_message() -> None:
    store = MemStore({"chunks_total": 0})
    with pytest.raises(PreconditionError) as excinfo:
        _cfg('assert(state.chunks_total > 0, "no chunks to extract")', store=store)
    assert "no chunks to extract" in str(excinfo.value)


def test_state_nested_access() -> None:
    store = MemStore({"classification": {"type": "library"}})
    _cfg('assert(state.classification.type == "library", "wrong")', store=store)


def test_params_access() -> None:
    _cfg('assert(params.chunk_id == 3, "bad param")', params={"chunk_id": 3})


def test_store_view_count_and_exists() -> None:
    store = MemStore()
    store.add("items", {"chunk": 0})
    _cfg('assert(store.count("items") == 1, "count")', store=store)
    _cfg('assert(store.exists("items"), "exists")', store=store)


def test_store_count_with_where_clause() -> None:
    store = MemStore()
    store.add("items", {"chunk": 0})
    store.add("items", {"chunk": 1})
    store.add("items", {"chunk": 0})
    _cfg('assert(store.count("items", {chunk = 0}) == 2, "filtered count")', store=store)


def test_postcondition_check_fails_then_passes() -> None:
    store = MemStore()
    c = _cfg(
        'function check() assert(store.count("items") >= 1, "no items filed") end',
        store=store,
    )
    with pytest.raises(PostconditionError):
        c.run_check()
    store.add("items", {"chunk": 0})
    c.run_check()  # now satisfied


def test_sandbox_blocks_os() -> None:
    with pytest.raises(PreconditionError):
        _cfg("local t = os.time()")


def test_sections_block_from_lua() -> None:
    doc = Document("## Main\n\n<digest-task>\nDo the thing.\n</digest-task>\n")
    c = _cfg('context.inject(sections.block("digest-task"))', document=doc)
    assert c.injected == ["Do the thing."]


def test_sections_children_from_lua() -> None:
    doc = Document(
        "## Battery\n\n### Test 1\n\nbody\n\n### Test 2\n\nbody\n"
    )
    c = _cfg(
        'local n = 0\n'
        'for _ in pairs(sections.children("## Battery")) do n = n + 1 end\n'
        'context.inject(tostring(n))',
        document=doc,
    )
    assert c.injected == ["2"]


def test_fanout_is_recorded() -> None:
    c = _cfg('fanout({{section = "## Extract", params = {chunk_id = 1}}}, {tag = "x"})')
    assert c.fanout is not None
    assert c.fanout.tasks[0]["section"] == "## Extract"
    assert c.fanout.tasks[0]["params"]["chunk_id"] == 1
    assert c.fanout.shared == {"tag": "x"}
