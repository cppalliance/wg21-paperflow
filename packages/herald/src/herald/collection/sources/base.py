#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""The source adapter seam.

An adapter is the only component that understands a source's wire format. It is a pure
producer: it turns ``(cursor, window)`` into a stream of :class:`PolledItem`, and never
touches storage, emits events, or advances cursors itself - the orchestrator does that
when it commits each item.

This module defines the contract only; concrete adapters land in later milestones.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from herald.collection.enums import SourceKind
from herald.collection.records import Candidate, CollectionWindow, Cursor


@dataclass(frozen=True)
class PolledItem:
    """One unit yielded by :meth:`SourceAdapter.poll`.

    ``candidate`` is the discovered/fetched item. ``cursor`` is the forward resume
    position *after* this item, so the orchestrator can advance the source cursor atomically
    when it commits. ``cursor`` may be ``None`` for sources whose resume position is only
    known at end-of-sweep (the adapter then sets it on the final item).
    """

    candidate: Candidate
    cursor: Cursor | None = None


@runtime_checkable
class SourceAdapter(Protocol):
    """Protocol every source adapter implements.

    ``kind`` ties the adapter to its :class:`SourceKind`. ``poll`` is an async generator;
    ``window`` is keyword-only so a caller cannot transpose it with ``cursor``, and the
    adapter must respect the window's range floor/ceiling and :class:`ThrottleCeilings`
    so a fresh or backfilling source stays bounded.
    """

    kind: SourceKind

    def poll(
        self,
        cursor: Cursor | None,
        *,
        window: CollectionWindow | None = None,
    ) -> AsyncIterator[PolledItem]:
        """Yield items newer than ``cursor``, bounded by ``window``.

        ``window=None`` means "use the source's stored window" (ADR-0005).
        """
        ...


__all__ = ["PolledItem", "SourceAdapter"]
