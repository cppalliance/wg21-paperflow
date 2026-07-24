#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""The persistent state store.

State is built incrementally through flat tool calls rather than emitted as
one large structured object: a tool that files a claim also writes it here.
The store survives a ``goto`` context wipe (the conversation history does
not), and a subagent's store is serialized and merged back into its caller.

Two shapes of data live here:

- Keyed values (``put`` / ``get`` / ``exists``): scalars, dicts, or lists
  addressed by a single key (``classification``, ``metadata``, ``report_path``).
- Collections: keyed values that are lists of dicts, appended to with ``add``
  and counted with ``count`` (``items``, ``findings``, ``verdicts``).

There is no locking. Fan-out runs subagents serially at the inference layer,
so the store is only ever touched from one coroutine at a time.
"""

from __future__ import annotations

import copy
from typing import Any


class MemStore:
    """An in-memory state store."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        # Deep-copy so the store owns its data and the caller's dict is
        # never mutated by later ``add``/``put`` calls (and vice versa).
        self._data: dict[str, Any] = copy.deepcopy(dict(data)) if data else {}

    def put(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def exists(self, key: str) -> bool:
        return key in self._data

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def add(self, collection: str, item: dict[str, Any]) -> None:
        """Append ``item`` to a list collection, creating it if absent."""
        existing = self._data.setdefault(collection, [])
        if not isinstance(existing, list):
            raise TypeError(
                f"'{collection}' holds a {type(existing).__name__}, not a "
                f"collection; use put() for scalar values."
            )
        existing.append(item)

    def count(self, collection: str, where: dict[str, Any] | None = None) -> int:
        """Count items in a collection, optionally filtered by field equality."""
        items = self._data.get(collection, [])
        if not isinstance(items, list):
            raise TypeError(f"'{collection}' is not a collection")
        if not where:
            return len(items)
        return sum(1 for it in items if _matches(it, where))

    def keys(self) -> list[str]:
        return list(self._data)

    def serialize(self) -> dict[str, Any]:
        """Return a deep copy of all state, for subagent return or merging."""
        return copy.deepcopy(self._data)

    def reset(self, data: dict[str, Any] | None = None) -> None:
        """Replace all state, used to roll back a failed section attempt."""
        self._data = copy.deepcopy(dict(data)) if data else {}

    def merge(self, other: "MemStore | dict[str, Any]") -> None:
        """Fold another store's state in: extend list collections, overwrite
        scalars, add new keys. Used to merge a subagent's store back."""
        incoming = other.serialize() if isinstance(other, MemStore) else copy.deepcopy(dict(other))
        for key, value in incoming.items():
            current = self._data.get(key)
            if isinstance(value, list) and isinstance(current, list):
                current.extend(value)
            else:
                self._data[key] = value


def _matches(item: Any, where: dict[str, Any]) -> bool:
    """True when ``item`` is a dict matching every key/value in ``where``."""
    if not isinstance(item, dict):
        return False
    return all(item.get(k) == v for k, v in where.items())
