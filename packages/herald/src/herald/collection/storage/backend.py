#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""The storage seam: an ORM-agnostic abstract base class.

`StorageBackend` is the single boundary between the collection pipeline and persistence.
Its signatures speak only in the frozen `records.py` dataclasses - no SQL, no Django, no
engine objects leak through - so the same contract serves the SQLite dev/test backend and
a Postgres/Django backend in production ("depend on less", 1-collection.md).

The defining method is :meth:`record_item`: the **only** place an item (and its events and
advanced cursor) becomes durable, in one transaction, after the blob has been written. Its
commit inputs are keyword-only so they cannot be transposed positionally.

This PR ships the ABC only; concrete backends land in a later milestone.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any

from herald.collection.enums import AccessState, HandlePlatform, SourceKind, SourceRole, SourceState
from herald.collection.records import (
    CandidateSourceRow,
    ConsumerCursorRow,
    ContentRow,
    Cursor,
    EventRow,
    MetricSnapshotRow,
    PersonHandleRow,
    PersonNameVariantRow,
    PersonPendingCandidateRow,
    SourceRow,
    UrlContentVersionRow,
    UrlRow,
)


class _Unset:
    """Sentinel so ``list_sources(parent_id=None)`` can mean "only top-level rows"
    distinctly from "do not filter on parent_id"."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "UNSET"


UNSET = _Unset()


class StorageBackend(ABC):
    """Abstract persistence contract for the collection layer."""

    # -- source registry ---------------------------------------------------

    @abstractmethod
    def add_source(self, source: SourceRow) -> SourceRow:
        """Insert a source/group row (upsert by ``source_uid``); return it with its id."""

    @abstractmethod
    def get_source(self, source_id: int) -> SourceRow:
        """Return the source by surrogate id, or raise ``UnknownSourceError``."""

    @abstractmethod
    def get_source_by_uid(self, source_uid: str) -> SourceRow | None:
        """Return the source by its natural key, or ``None``."""

    @abstractmethod
    def list_sources(
        self,
        *,
        enabled: bool | None = None,
        role: SourceRole | None = None,
        kind: SourceKind | None = None,
        state: SourceState | None = None,
        parent_id: int | None | _Unset = UNSET,
    ) -> list[SourceRow]:
        """List sources filtered by any combination of fields. ``parent_id=None`` selects
        top-level rows; the default (``UNSET``) does not filter on parent."""

    @abstractmethod
    def update_source(self, source: SourceRow) -> None:
        """Persist all mutable fields of an existing source (matched by id)."""

    @abstractmethod
    def remove_source(self, source_id: int) -> None:
        """Delete a source by id."""

    @abstractmethod
    def set_enabled(self, source_id: int, enabled: bool) -> None:
        """Toggle a source's ``enabled`` flag."""

    @abstractmethod
    def set_source_state(self, source_id: int, state: SourceState) -> None:
        """Advance a source through the curation lifecycle."""

    # -- scheduling --------------------------------------------------------

    @abstractmethod
    def due_sources(self, *, now: str, limit: int | None = None) -> list[SourceRow]:
        """Return enabled, active sources whose ``next_run_at`` is due at ``now``."""

    @abstractmethod
    def set_next_run_at(self, source_id: int, next_run_at: str | None) -> None:
        """Set a source's next scheduled poll time."""

    @abstractmethod
    def record_sweep(
        self,
        source_id: int,
        *,
        swept_at: str,
        access_state: AccessState | None = None,
        error: str | None = None,
    ) -> None:
        """Record the outcome of a sweep (timestamp, optional access_state / error)."""

    # -- cursors -----------------------------------------------------------

    @abstractmethod
    def get_cursor(self, source_id: int) -> Cursor | None:
        """Return a source's forward resume cursor, or ``None`` if never swept."""

    @abstractmethod
    def set_cursor(self, source_id: int, cursor: Cursor | None) -> None:
        """Set a source's forward resume cursor (outside an item commit)."""

    # -- reads -------------------------------------------------------------

    @abstractmethod
    def get_url(self, url_syntactic: str) -> UrlRow | None:
        """Return the URL row for a syntactic URL, or ``None``."""

    @abstractmethod
    def get_content(self, content_hash_text: str) -> ContentRow | None:
        """Return the content row for an extracted-text hash, or ``None``."""

    # -- the atomic commit (transactional outbox) --------------------------

    @abstractmethod
    def record_item(
        self,
        *,
        source_id: int,
        url: UrlRow,
        content: ContentRow,
        version: UrlContentVersionRow,
        events: Sequence[EventRow] = (),
        cursor: Cursor | None = None,
        candidate_sources: Sequence[CandidateSourceRow] = (),
        person_candidates: Sequence[PersonPendingCandidateRow] = (),
    ) -> None:
        """Durably commit one collected item in a single transaction.

        Precondition: the content blobs are already written (content-addressed, idempotent).
        This upserts the ``url`` and ``content`` rows, appends the ``version`` row and the
        ``events`` (the outbox), records any ``candidate_sources`` / ``person_candidates``,
        and advances the source ``cursor`` - all atomically. Inputs are keyword-only.
        """

    # -- events + consumer cursors -----------------------------------------

    @abstractmethod
    def emit_events(self, events: Sequence[EventRow]) -> list[int]:
        """Append events to the outbox outside an item commit (e.g. ``source_added``);
        return the assigned ids."""

    @abstractmethod
    def read_events(self, *, after_id: int = 0, limit: int = 1000) -> list[EventRow]:
        """Read up to ``limit`` events with id greater than ``after_id``, in id order."""

    @abstractmethod
    def get_consumer_cursor(self, consumer_name: str) -> ConsumerCursorRow:
        """Return a consumer's cursor, creating a zero cursor if it does not exist."""

    @abstractmethod
    def set_consumer_cursor(
        self,
        consumer_name: str,
        *,
        last_processed_event_id: int,
        last_processed_at: str | None = None,
    ) -> None:
        """Advance a consumer's cursor after it has processed events."""

    @abstractmethod
    def consumer_lag(self, consumer_name: str) -> int:
        """Return how many events remain unprocessed for a consumer."""

    # -- metric snapshots (snapshot policy) --------------------------------

    @abstractmethod
    def record_metric_snapshot(self, snapshot: MetricSnapshotRow) -> None:
        """Persist one periodic snapshot of a cumulative engagement metric."""

    @abstractmethod
    def latest_metric(self, content_hash_text: str, metric_kind: str) -> MetricSnapshotRow | None:
        """Return the most recent snapshot of a metric for a content item, or ``None``."""

    # -- person observation ------------------------------------------------

    @abstractmethod
    def add_person_candidate(self, candidate: PersonPendingCandidateRow) -> int:
        """Insert a pending person candidate; return its id."""

    @abstractmethod
    def find_person_handle(self, platform: HandlePlatform, handle: str) -> PersonHandleRow | None:
        """Look up a person handle by ``(platform, handle)``, or ``None``."""

    @abstractmethod
    def find_name_variants(self, variant_text_normalized: str) -> list[PersonNameVariantRow]:
        """Return person name variants whose normalized text matches."""

    # -- cross-instance interchange seam (implemented in the migration PR) --

    @abstractmethod
    def export_table(self, name: str) -> Iterator[Mapping[str, Any]]:
        """Yield a table's rows as JSON-safe dicts for logical (cross-engine) export."""

    @abstractmethod
    def import_rows(
        self,
        name: str,
        rows: Iterable[Mapping[str, Any]],
        *,
        on_conflict: str = "natural_key",
    ) -> int:
        """Upsert exported rows into a table (by natural key), remapping surrogate FKs;
        return the number of rows written."""

    # -- lifecycle ---------------------------------------------------------

    @abstractmethod
    def close(self) -> None:
        """Release any resources held by the backend."""


__all__ = ["StorageBackend", "UNSET"]
