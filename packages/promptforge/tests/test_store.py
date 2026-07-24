#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the persistent state store."""

from __future__ import annotations

import pytest

from promptforge.store import MemStore


def test_put_get_exists_delete() -> None:
    store = MemStore()
    assert not store.exists("k")
    store.put("k", {"type": "library"})
    assert store.exists("k")
    assert store.get("k")["type"] == "library"
    store.delete("k")
    assert not store.exists("k")


def test_get_default() -> None:
    store = MemStore()
    assert store.get("missing") is None
    assert store.get("missing", 42) == 42


def test_add_creates_collection_and_appends() -> None:
    store = MemStore()
    store.add("items", {"chunk": 0, "kind": "claim"})
    store.add("items", {"chunk": 1, "kind": "evidence"})
    assert store.count("items") == 2
    assert store.get("items")[0]["kind"] == "claim"


def test_count_with_filter() -> None:
    store = MemStore()
    store.add("items", {"chunk": 0})
    store.add("items", {"chunk": 0})
    store.add("items", {"chunk": 1})
    assert store.count("items", {"chunk": 0}) == 2
    assert store.count("items", {"chunk": 1}) == 1
    assert store.count("items", {"chunk": 9}) == 0


def test_count_missing_collection_is_zero() -> None:
    assert MemStore().count("nope") == 0


def test_count_int_float_equivalence() -> None:
    # Lua numbers may arrive as floats; a stored int must still match.
    store = MemStore()
    store.add("items", {"chunk": 3})
    assert store.count("items", {"chunk": 3.0}) == 1


def test_add_to_non_list_key_raises() -> None:
    store = MemStore()
    store.put("scalar", 1)
    with pytest.raises(TypeError):
        store.add("scalar", {"x": 1})


def test_serialize_is_a_deep_copy() -> None:
    store = MemStore()
    store.add("items", {"chunk": 0})
    snap = store.serialize()
    snap["items"][0]["chunk"] = 99
    snap["new"] = 1
    # Mutating the snapshot must not touch the live store.
    assert store.get("items")[0]["chunk"] == 0
    assert not store.exists("new")


def test_merge_extends_lists_and_overwrites_scalars() -> None:
    store = MemStore({"items": [{"chunk": 0}], "verdict": "old"})
    store.merge({"items": [{"chunk": 1}], "verdict": "new", "extra": 5})
    assert store.count("items") == 2
    assert store.get("verdict") == "new"
    assert store.get("extra") == 5


def test_merge_accepts_another_store() -> None:
    a = MemStore({"items": [{"chunk": 0}]})
    b = MemStore({"items": [{"chunk": 1}]})
    a.merge(b)
    assert a.count("items") == 2


def test_init_with_data_is_copied() -> None:
    seed = {"items": [{"chunk": 0}]}
    store = MemStore(seed)
    store.add("items", {"chunk": 1})
    # The caller's dict must not be mutated by store operations.
    assert len(seed["items"]) == 1
