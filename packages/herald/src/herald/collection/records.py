#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Frozen row + framework types for the collection layer.

Three families live here:

* **Row dataclasses** - one frozen ``@dataclass`` per foundation table
  (``docs/foundation/1-collection.md``), kept ORM-agnostic so they travel across the
  SQLite and Postgres backends unchanged. ``id``/timestamp fields are optional because a
  row is constructed before insertion.
* **Framework unions** - the ``Candidate`` union an adapter yields, the typed ``Cursor``
  union for incremental resume, and the typed ``Window`` union for collection ranges, each
  with a tagged-JSON codec that rejects an unknown ``kind`` with ``ValueError``.
* **Injected-seam results** - ``FetchResult``/``ExtractResult``/``Identity`` returned by
  the fetcher/extractor/deduper seams (defined now; produced later).

Nothing here imports a backend, an adapter transport, or any heavy dependency.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from herald.collection.enums import (
    AccessState,
    CadenceKind,
    CandidateKind,
    ContentType,
    CursorKind,
    EventKind,
    GroupKind,
    HandlePlatform,
    PersonStatus,
    SourceKind,
    SourceRole,
    SourceState,
    VariantKind,
    Visibility,
    WindowKind,
)

# ---------------------------------------------------------------------------
# Cursor: typed union for the single forward resume position
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Timestamp:
    """Resume by an ISO-8601 instant (e.g. Discourse ``created_at``)."""

    value: str


@dataclass(frozen=True)
class MonotonicId:
    """Resume by a monotonically increasing integer id (e.g. a Discord snowflake)."""

    value: int


@dataclass(frozen=True)
class ByteOffset:
    """Resume by a byte offset into a cumulative dump (e.g. an mbox archive)."""

    offset: int


@dataclass(frozen=True)
class OpaqueToken:
    """Resume by a provider-defined token whose internals we do not interpret."""

    token: str


@dataclass(frozen=True)
class Composite:
    """A cursor with independent sub-axes (e.g. GitHub issues vs commits in one repo)."""

    parts: dict[str, "Cursor"]


Cursor = Timestamp | MonotonicId | ByteOffset | OpaqueToken | Composite


def cursor_to_json(cursor: Cursor) -> dict[str, Any]:
    """Serialize a :data:`Cursor` to a ``kind``-tagged JSON-safe dict."""
    match cursor:
        case Timestamp(value):
            return {"kind": CursorKind.TIMESTAMP.value, "value": value}
        case MonotonicId(value):
            return {"kind": CursorKind.MONOTONIC_ID.value, "value": value}
        case ByteOffset(offset):
            return {"kind": CursorKind.BYTE_OFFSET.value, "offset": offset}
        case OpaqueToken(token):
            return {"kind": CursorKind.OPAQUE_TOKEN.value, "token": token}
        case Composite(parts):
            return {
                "kind": CursorKind.COMPOSITE.value,
                "parts": {name: cursor_to_json(sub) for name, sub in parts.items()},
            }


def cursor_from_json(data: Mapping[str, Any]) -> Cursor:
    """Reconstruct a :data:`Cursor`; an unknown ``kind`` raises ``ValueError``."""
    kind = data["kind"]
    if kind == CursorKind.TIMESTAMP:
        return Timestamp(str(data["value"]))
    if kind == CursorKind.MONOTONIC_ID:
        return MonotonicId(int(data["value"]))
    if kind == CursorKind.BYTE_OFFSET:
        return ByteOffset(int(data["offset"]))
    if kind == CursorKind.OPAQUE_TOKEN:
        return OpaqueToken(str(data["token"]))
    if kind == CursorKind.COMPOSITE:
        return Composite({name: cursor_from_json(sub) for name, sub in data["parts"].items()})
    raise ValueError(f"unknown cursor kind: {kind!r}")


# ---------------------------------------------------------------------------
# Window: typed union for the collection range (operator intent)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TemporalWindow:
    """A time range. ``None`` bounds are unbounded. Bounds may be operator-intent tokens
    (``"-90d"``, ``"today"``) resolved at sweep time."""

    since: str | None = None
    until: str | None = None


@dataclass(frozen=True)
class ByteRangeWindow:
    """A byte budget per sweep, for cumulative-dump sources whose axis is bytes (mbox)."""

    max_bytes_per_sweep: int


@dataclass(frozen=True)
class CurrentOnlyWindow:
    """No range axis - the source only ever exposes "current" items (rss, sitemap)."""


RangeBound = TemporalWindow | ByteRangeWindow | CurrentOnlyWindow


@dataclass(frozen=True)
class ThrottleCeilings:
    """Universal per-sweep safety caps, independent of the range axis."""

    max_items: int | None = None
    max_pages: int | None = None
    max_age_seconds: int | None = None


@dataclass(frozen=True)
class BackfillState:
    """Backward-fill sidecar. ``progress`` is the backfill's own cursor so the forward
    ``cursor`` never rewinds; ``completed`` flips when ``target_since`` is reached."""

    target_since: str
    progress: Cursor | None = None
    completed: bool = False


@dataclass(frozen=True)
class CollectionWindow:
    """Operator intent for one source: a range axis + safety ceilings + optional backfill."""

    range: RangeBound
    throttle: ThrottleCeilings = field(default_factory=ThrottleCeilings)
    backfill: BackfillState | None = None


def _range_to_json(rng: RangeBound) -> dict[str, Any]:
    match rng:
        case TemporalWindow(since, until):
            return {"kind": WindowKind.TEMPORAL.value, "since": since, "until": until}
        case ByteRangeWindow(max_bytes):
            return {"kind": WindowKind.BYTE_RANGE.value, "max_bytes_per_sweep": max_bytes}
        case CurrentOnlyWindow():
            return {"kind": WindowKind.CURRENT_ONLY.value}


def _range_from_json(data: Mapping[str, Any]) -> RangeBound:
    kind = data["kind"]
    if kind == WindowKind.TEMPORAL:
        return TemporalWindow(data.get("since"), data.get("until"))
    if kind == WindowKind.BYTE_RANGE:
        return ByteRangeWindow(int(data["max_bytes_per_sweep"]))
    if kind == WindowKind.CURRENT_ONLY:
        return CurrentOnlyWindow()
    raise ValueError(f"unknown window kind: {kind!r}")


def window_to_json(window: CollectionWindow) -> dict[str, Any]:
    """Serialize a :class:`CollectionWindow` to a JSON-safe dict (range tagged by kind)."""
    out: dict[str, Any] = {
        "range": _range_to_json(window.range),
        "throttle": {
            "max_items": window.throttle.max_items,
            "max_pages": window.throttle.max_pages,
            "max_age_seconds": window.throttle.max_age_seconds,
        },
    }
    if window.backfill is not None:
        bf = window.backfill
        out["backfill"] = {
            "target_since": bf.target_since,
            "progress": cursor_to_json(bf.progress) if bf.progress is not None else None,
            "completed": bf.completed,
        }
    return out


def window_from_json(data: Mapping[str, Any]) -> CollectionWindow:
    """Reconstruct a :class:`CollectionWindow`; an unknown range ``kind`` raises ``ValueError``."""
    rng = _range_from_json(data["range"])
    raw_throttle = data.get("throttle") or {}
    throttle = ThrottleCeilings(
        max_items=raw_throttle.get("max_items"),
        max_pages=raw_throttle.get("max_pages"),
        max_age_seconds=raw_throttle.get("max_age_seconds"),
    )
    backfill: BackfillState | None = None
    raw_backfill = data.get("backfill")
    if raw_backfill:
        progress = (
            cursor_from_json(raw_backfill["progress"])
            if raw_backfill.get("progress") is not None
            else None
        )
        backfill = BackfillState(
            target_since=str(raw_backfill["target_since"]),
            progress=progress,
            completed=bool(raw_backfill.get("completed", False)),
        )
    return CollectionWindow(range=rng, throttle=throttle, backfill=backfill)


# Per-kind safe defaults: a fresh source is bounded by default and extended deliberately,
# which cures the "must-seed / slow first run" problem.
_TEMPORAL_API_KINDS = frozenset(
    {SourceKind.GITHUB, SourceKind.DISCOURSE, SourceKind.REDDIT, SourceKind.MCP}
)
_BYTE_DUMP_KINDS = frozenset({SourceKind.REFLECTOR, SourceKind.MBOX})


def default_window_for_kind(kind: SourceKind) -> CollectionWindow:
    """Return the safe default collection window for a source kind."""
    if kind in _BYTE_DUMP_KINDS:
        return CollectionWindow(
            range=ByteRangeWindow(max_bytes_per_sweep=10 * 1024 * 1024),
            throttle=ThrottleCeilings(max_age_seconds=None),
        )
    if kind == SourceKind.DISCORD:
        return CollectionWindow(
            range=TemporalWindow(since="today", until=None),
            throttle=ThrottleCeilings(max_items=5000),
        )
    if kind in _TEMPORAL_API_KINDS:
        return CollectionWindow(
            range=TemporalWindow(since="-90d", until=None),
            throttle=ThrottleCeilings(max_pages=10),
        )
    # rss, sitemap, web: no range axis
    return CollectionWindow(range=CurrentOnlyWindow(), throttle=ThrottleCeilings())


# ---------------------------------------------------------------------------
# Candidate: what an adapter yields
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Discovered:
    """A cheap listing entry - a URL (and a hint) to be fetched by the pipeline."""

    url: str
    hint: Mapping[str, Any] = field(default_factory=dict)
    canonical_id: str | None = None


@dataclass(frozen=True)
class Fetched:
    """An item whose bytes the poll already paid for (an mbox message, an API record)."""

    url: str
    raw: bytes | None = None
    text: str | None = None
    content_type: ContentType | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    canonical_id: str | None = None
    fetched_at: str | None = None


Candidate = Discovered | Fetched


def candidate_to_json(candidate: Candidate) -> dict[str, Any]:
    """Serialize a :data:`Candidate` to a ``kind``-tagged JSON-safe dict.

    ``Fetched.raw`` bytes are base64-encoded so the result is JSON-safe and lossless.
    """
    match candidate:
        case Discovered(url, hint, canonical_id):
            return {
                "kind": CandidateKind.DISCOVERED.value,
                "url": url,
                "hint": dict(hint),
                "canonical_id": canonical_id,
            }
        case Fetched(url, raw, text, content_type, metadata, canonical_id, fetched_at):
            return {
                "kind": CandidateKind.FETCHED.value,
                "url": url,
                "raw": base64.b64encode(raw).decode("ascii") if raw is not None else None,
                "text": text,
                "content_type": content_type.value if content_type is not None else None,
                "metadata": dict(metadata),
                "canonical_id": canonical_id,
                "fetched_at": fetched_at,
            }


def candidate_from_json(data: Mapping[str, Any]) -> Candidate:
    """Reconstruct a :data:`Candidate`; an unknown ``kind`` raises ``ValueError``."""
    kind = data["kind"]
    if kind == CandidateKind.DISCOVERED:
        return Discovered(
            url=str(data["url"]),
            hint=dict(data.get("hint") or {}),
            canonical_id=data.get("canonical_id"),
        )
    if kind == CandidateKind.FETCHED:
        raw_b64 = data.get("raw")
        content_type = data.get("content_type")
        return Fetched(
            url=str(data["url"]),
            raw=base64.b64decode(raw_b64) if raw_b64 is not None else None,
            text=data.get("text"),
            content_type=ContentType(content_type) if content_type is not None else None,
            metadata=dict(data.get("metadata") or {}),
            canonical_id=data.get("canonical_id"),
            fetched_at=data.get("fetched_at"),
        )
    raise ValueError(f"unknown candidate kind: {kind!r}")


# ---------------------------------------------------------------------------
# Injected-seam result types
# ---------------------------------------------------------------------------


class FetchOutcome(StrEnum):
    """Classification of a fetch attempt (drives change detection + access_state)."""

    OK = "ok"
    NOT_MODIFIED = "not-modified"
    NOT_FOUND = "not-found"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass(frozen=True)
class FetchResult:
    """The fetcher seam's output for one URL."""

    outcome: FetchOutcome
    status_code: int | None = None
    raw: bytes | None = None
    content_type: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    final_url: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class ExtractResult:
    """The extractor seam's output: clean text + structured metadata."""

    text: str
    title: str | None = None
    byline: str | None = None
    publish_date: str | None = None
    language: str | None = None
    content_type: ContentType | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Identity:
    """The deduper seam's output: cross-source identity + content hashes."""

    content_hash_text: str
    content_hash_raw: str
    canonical_id: str | None = None
    fingerprint: str | None = None


# ---------------------------------------------------------------------------
# source_uid: deterministic natural key for cross-instance interchange
# ---------------------------------------------------------------------------


def compute_source_uid(
    *,
    role: SourceRole,
    kind: SourceKind | None = None,
    group_kind: GroupKind | None = None,
    identity: Mapping[str, Any],
) -> str:
    """Derive a stable, collision-resistant natural key for a source/group row.

    Two rows with the same role + kind + identity-bearing config produce the same uid on
    any instance, so a cross-instance importer can upsert by natural key and remap
    surrogate foreign keys. ``identity`` should contain only the identity-defining config
    fields (e.g. ``{"owner": "boostorg", "repo": "beast"}``), not volatile settings.
    """
    if role == SourceRole.GROUP:
        if group_kind is None:
            raise ValueError("compute_source_uid with role=group requires group_kind")
        discriminator = group_kind.value
    else:
        if kind is None:
            raise ValueError("compute_source_uid with non-group role requires kind")
        discriminator = kind.value
    canonical = json.dumps(dict(identity), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{role.value}:{discriminator}:{digest}"


# ---------------------------------------------------------------------------
# Row dataclasses (one per foundation table)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceRow:
    """A registry row - a pollable source (``role=source``) or a group container
    (``role=group``). Extends the spec ``sources`` table with the role discriminator, the
    window/range model, the group hierarchy, scheduling fields, and the ``source_uid``
    natural key (all recorded as deviations)."""

    source_uid: str
    name: str
    role: SourceRole = SourceRole.SOURCE
    kind: SourceKind | None = None
    group_kind: GroupKind | None = None
    config_json: Mapping[str, Any] = field(default_factory=dict)
    enabled: bool = True
    state: SourceState = SourceState.PENDING
    access_state: AccessState = AccessState.OPEN
    cadence_kind: CadenceKind = CadenceKind.FIXED
    poll_interval_seconds: int | None = None
    parent_id: int | None = None
    window_json: Mapping[str, Any] | None = None
    window_inherited: bool = False
    last_swept_at: str | None = None
    next_run_at: str | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    id: int | None = None
    created_at: str | None = None

    def __post_init__(self) -> None:
        # Enforce the role/kind discriminator (ADR 0003): a pollable source carries a
        # SourceKind and no GroupKind; a group container carries a GroupKind and no SourceKind.
        if self.role is SourceRole.SOURCE:
            if self.kind is None:
                raise ValueError("SourceRow with role=source requires a kind")
            if self.group_kind is not None:
                raise ValueError("SourceRow with role=source must not set group_kind")
        elif self.role is SourceRole.GROUP:
            if self.group_kind is None:
                raise ValueError("SourceRow with role=group requires a group_kind")
            if self.kind is not None:
                raise ValueError("SourceRow with role=group must not set kind")


@dataclass(frozen=True)
class UrlRow:
    """A `urls` row - one per distinct syntactic URL (dedup-across-mirrors via contents)."""

    url_syntactic: str
    url_canonical: str
    source_id: int | None = None
    first_seen_at: str | None = None
    last_fetched_at: str | None = None
    last_checked_at: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    fetch_count: int = 0
    change_count: int = 0
    status_last: int | None = None
    revisit_after: str | None = None
    robots_allowed: bool | None = None
    id: int | None = None


@dataclass(frozen=True)
class ContentRow:
    """A `contents` row, keyed by the sha256 of the extracted text. Extended with the
    cross-source identity fields ``canonical_id`` and ``fingerprint``."""

    content_hash_text: str
    content_hash_raw: str
    title: str | None = None
    byline: str | None = None
    publish_date: str | None = None
    language: str | None = None
    content_type: ContentType | None = None
    extracted_text_blob_key: str | None = None
    raw_blob_key: str | None = None
    source_kind: SourceKind | None = None
    first_seen_at: str | None = None
    visibility: Visibility = Visibility.PUBLIC
    canonical_id: str | None = None
    fingerprint: str | None = None


@dataclass(frozen=True)
class UrlContentVersionRow:
    """A `url_content_versions` row - one per observed change at a URL."""

    url_id: int
    content_hash_text: str
    seen_at: str | None = None
    id: int | None = None


@dataclass(frozen=True)
class EventRow:
    """A `collection_events` row (the transactional outbox)."""

    kind: EventKind
    payload: Mapping[str, Any]
    created_at: str | None = None
    id: int | None = None


@dataclass(frozen=True)
class ConsumerCursorRow:
    """A `consumer_cursors` row - one per downstream consumer."""

    consumer_name: str
    last_processed_event_id: int = 0
    last_processed_at: str | None = None


@dataclass(frozen=True)
class MetricSnapshotRow:
    """A periodic snapshot of a cumulative engagement metric (snapshot policy: never one
    row per increment). Modeled here to pin the policy into the data model."""

    content_hash_text: str
    metric_kind: str
    value: int
    taken_at: str
    source_id: int | None = None
    id: int | None = None


@dataclass(frozen=True)
class CandidateSourceRow:
    """A `candidate_sources` row - an outbound link observed in extracted content."""

    candidate_url: str
    observed_in_content_hash: str
    first_observed_at: str | None = None
    observation_count: int = 1
    id: int | None = None


# --- person tables (collection writes; full schema in 2-people.md) ---


@dataclass(frozen=True)
class PersonRow:
    person_id: str
    canonical_name: str
    preferred_prose_name: str | None = None
    status: PersonStatus = PersonStatus.UNKNOWN
    deceased_on: str | None = None
    primary_domain: str | None = None
    one_line_summary: str | None = None


@dataclass(frozen=True)
class PersonNameVariantRow:
    person_id: str
    variant_text: str
    variant_kind: VariantKind
    variant_text_normalized: str | None = None
    id: int | None = None


@dataclass(frozen=True)
class PersonHandleRow:
    person_id: str
    platform: HandlePlatform
    handle: str
    id: int | None = None


@dataclass(frozen=True)
class PersonPendingCandidateRow:
    observed_name: str
    observed_context: str | None = None
    observed_handles: Mapping[str, Any] = field(default_factory=dict)
    observed_email_domain: str | None = None
    content_id: str | None = None
    first_seen: str | None = None
    last_seen: str | None = None
    resolution_status: str = "pending"
    candidate_id: int | None = None


@dataclass(frozen=True)
class PersonEventRow:
    person_id: str
    occurred_on: str
    event_kind: str
    headline: str | None = None
    body_md: str | None = None
    content_id: str | None = None
    article_id: int | None = None
    created_at: str | None = None
    event_id: int | None = None


@dataclass(frozen=True)
class PersonAffiliationRow:
    person_id: str
    organization_id: int
    role: str | None = None
    started_on: str | None = None
    ended_on: str | None = None
    content_id: str | None = None
    id: int | None = None


@dataclass(frozen=True)
class PersonCommitteeRoleRow:
    person_id: str
    group_code: str
    role: str | None = None
    started_on: str | None = None
    ended_on: str | None = None
    content_id: str | None = None
    id: int | None = None


@dataclass(frozen=True)
class WatchRow:
    person_id: str
    query_terms_json: Mapping[str, Any] = field(default_factory=dict)
    cadence: str | None = None
    last_run_at: str | None = None
    id: int | None = None


@dataclass(frozen=True)
class WatchSnapshotRow:
    watch_id: int
    taken_at: str
    content_hashes_json: Mapping[str, Any] = field(default_factory=dict)
    id: int | None = None


__all__ = [
    # cursor
    "Timestamp",
    "MonotonicId",
    "ByteOffset",
    "OpaqueToken",
    "Composite",
    "Cursor",
    "cursor_to_json",
    "cursor_from_json",
    # window
    "TemporalWindow",
    "ByteRangeWindow",
    "CurrentOnlyWindow",
    "RangeBound",
    "ThrottleCeilings",
    "BackfillState",
    "CollectionWindow",
    "window_to_json",
    "window_from_json",
    "default_window_for_kind",
    # candidate
    "Discovered",
    "Fetched",
    "Candidate",
    "candidate_to_json",
    "candidate_from_json",
    # results
    "FetchOutcome",
    "FetchResult",
    "ExtractResult",
    "Identity",
    # natural key
    "compute_source_uid",
    # rows
    "SourceRow",
    "UrlRow",
    "ContentRow",
    "UrlContentVersionRow",
    "EventRow",
    "ConsumerCursorRow",
    "MetricSnapshotRow",
    "CandidateSourceRow",
    "PersonRow",
    "PersonNameVariantRow",
    "PersonHandleRow",
    "PersonPendingCandidateRow",
    "PersonEventRow",
    "PersonAffiliationRow",
    "PersonCommitteeRoleRow",
    "WatchRow",
    "WatchSnapshotRow",
]
