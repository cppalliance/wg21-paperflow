#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Herald collection layer.

The pure-Python, no-LLM ingestion layer: it discovers sources, polls them on a
per-source cadence, fetches politely, normalizes/extracts/dedups content, observes
people mechanically, and records everything through a transactional outbox
(`collection_events`) for downstream layers to consume.

Public vocabulary (enums, frozen row/result types, the Candidate/Cursor/Window unions)
is re-exported here. Heavier machinery (backends, adapters, the orchestrator) lives in
subpackages and is imported explicitly to keep `import herald.collection` cheap.
"""

from __future__ import annotations

from herald.collection.enums import (
    AccessState,
    CadenceKind,
    CandidateKind,
    ChangeKind,
    ContentType,
    CursorKind,
    EventKind,
    EventOrigin,
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
from herald.collection.errors import HeraldError
from herald.collection.records import (
    BackfillState,
    ByteOffset,
    ByteRangeWindow,
    Candidate,
    CandidateSourceRow,
    CollectionWindow,
    Composite,
    ConsumerCursorRow,
    ContentRow,
    Cursor,
    CurrentOnlyWindow,
    Discovered,
    EventRow,
    ExtractResult,
    Fetched,
    FetchOutcome,
    FetchResult,
    Identity,
    MetricSnapshotRow,
    MonotonicId,
    OpaqueToken,
    OrganizationRow,
    PersonAffiliationRow,
    PersonCommitteeRoleRow,
    PersonEmailDomainRow,
    PersonEventRow,
    PersonHandleRow,
    PersonNameVariantRow,
    PersonPendingCandidateRow,
    PersonRow,
    RangeBound,
    SourceRow,
    TemporalWindow,
    ThrottleCeilings,
    Timestamp,
    UrlContentVersionRow,
    UrlRow,
    WatchRow,
    WatchSnapshotRow,
    candidate_from_json,
    candidate_to_json,
    compute_source_uid,
    cursor_from_json,
    cursor_to_json,
    default_window_for_kind,
    window_from_json,
    window_to_json,
)

__all__ = [
    "HeraldError",
    # records: framework unions + codecs
    "Timestamp",
    "MonotonicId",
    "ByteOffset",
    "OpaqueToken",
    "Composite",
    "Cursor",
    "cursor_to_json",
    "cursor_from_json",
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
    "Discovered",
    "Fetched",
    "Candidate",
    "candidate_to_json",
    "candidate_from_json",
    "FetchOutcome",
    "FetchResult",
    "ExtractResult",
    "Identity",
    "compute_source_uid",
    # records: common rows
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
    "PersonEmailDomainRow",
    "PersonPendingCandidateRow",
    "PersonEventRow",
    "OrganizationRow",
    "PersonAffiliationRow",
    "PersonCommitteeRoleRow",
    "WatchRow",
    "WatchSnapshotRow",
    "AccessState",
    "CadenceKind",
    "CandidateKind",
    "ChangeKind",
    "ContentType",
    "CursorKind",
    "EventKind",
    "EventOrigin",
    "GroupKind",
    "HandlePlatform",
    "PersonStatus",
    "SourceKind",
    "SourceRole",
    "SourceState",
    "VariantKind",
    "Visibility",
    "WindowKind",
]
