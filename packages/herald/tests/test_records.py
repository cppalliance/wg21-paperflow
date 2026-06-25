#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Record-type tests: the Cursor/Window codecs and the framework data types."""

from __future__ import annotations

import dataclasses
import json

import pytest

from herald.collection import records as r
from herald.collection.enums import ContentType, GroupKind, SourceKind, SourceRole, SourceState

# -- Cursor ---------------------------------------------------------------


@pytest.mark.parametrize(
    "cursor",
    [
        r.Timestamp("2026-06-22T00:00:00Z"),
        r.MonotonicId(987654321),
        r.ByteOffset(4096),
        r.OpaqueToken("page=3&after=abc"),
    ],
)
def test_simple_cursor_round_trip(cursor: r.Cursor) -> None:
    blob = json.loads(json.dumps(r.cursor_to_json(cursor)))  # prove JSON-safe
    assert r.cursor_from_json(blob) == cursor


def test_nested_composite_cursor_round_trip() -> None:
    cursor = r.Composite(
        {
            "issues": r.Timestamp("2026-01-01T00:00:00Z"),
            "commits": r.MonotonicId(42),
            "archive": r.Composite({"mbox": r.ByteOffset(10)}),
        }
    )
    assert r.cursor_from_json(json.loads(json.dumps(r.cursor_to_json(cursor)))) == cursor


def test_unknown_cursor_kind_raises() -> None:
    with pytest.raises(ValueError, match="unknown cursor kind"):
        r.cursor_from_json({"kind": "made-up"})


# -- Window ---------------------------------------------------------------


def test_temporal_window_round_trip_with_backfill() -> None:
    window = r.CollectionWindow(
        range=r.TemporalWindow(since="-90d", until="2026-06-01"),
        throttle=r.ThrottleCeilings(max_items=100, max_pages=10, max_age_seconds=86400),
        backfill=r.BackfillState(
            target_since="2018-01-01", progress=r.ByteOffset(2048), completed=False
        ),
    )
    assert r.window_from_json(json.loads(json.dumps(r.window_to_json(window)))) == window


def test_byte_range_window_round_trip() -> None:
    window = r.CollectionWindow(range=r.ByteRangeWindow(max_bytes_per_sweep=10_485_760))
    assert r.window_from_json(r.window_to_json(window)) == window


def test_current_only_window_round_trip() -> None:
    window = r.CollectionWindow(range=r.CurrentOnlyWindow())
    assert r.window_from_json(r.window_to_json(window)) == window


def test_unbounded_temporal_window_round_trip() -> None:
    window = r.CollectionWindow(range=r.TemporalWindow(since=None, until=None))
    rebuilt = r.window_from_json(r.window_to_json(window))
    assert rebuilt == window
    assert isinstance(rebuilt.range, r.TemporalWindow)
    assert rebuilt.range.since is None and rebuilt.range.until is None


def test_completed_backfill_round_trip_without_progress() -> None:
    window = r.CollectionWindow(
        range=r.TemporalWindow(since="-30d"),
        backfill=r.BackfillState(target_since="2010-01-01", progress=None, completed=True),
    )
    rebuilt = r.window_from_json(r.window_to_json(window))
    assert rebuilt == window
    assert rebuilt.backfill is not None and rebuilt.backfill.completed is True


def test_unknown_window_kind_raises() -> None:
    with pytest.raises(ValueError, match="unknown window kind"):
        r.window_from_json({"range": {"kind": "made-up"}})


# -- default windows ------------------------------------------------------


def test_default_windows_are_kind_appropriate() -> None:
    assert isinstance(r.default_window_for_kind(SourceKind.GITHUB).range, r.TemporalWindow)
    assert isinstance(r.default_window_for_kind(SourceKind.REFLECTOR).range, r.ByteRangeWindow)
    assert isinstance(r.default_window_for_kind(SourceKind.MBOX).range, r.ByteRangeWindow)
    assert isinstance(r.default_window_for_kind(SourceKind.RSS).range, r.CurrentOnlyWindow)
    assert isinstance(r.default_window_for_kind(SourceKind.SITEMAP).range, r.CurrentOnlyWindow)
    # every default survives a round-trip
    for kind in SourceKind:
        w = r.default_window_for_kind(kind)
        assert r.window_from_json(r.window_to_json(w)) == w


# -- Candidate ------------------------------------------------------------


def test_candidate_types_are_frozen() -> None:
    d = r.Discovered(url="https://example.org/post")
    f = r.Fetched(url="https://example.org/post", text="hi")
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.url = "x"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.text = "y"  # type: ignore[misc]


def test_candidate_union_membership() -> None:
    items: list[r.Candidate] = [r.Discovered(url="u"), r.Fetched(url="u")]
    assert all(isinstance(i, (r.Discovered, r.Fetched)) for i in items)


def test_discovered_candidate_round_trip() -> None:
    cand = r.Discovered(
        url="https://example.org/post",
        hint={"title": "Hello", "etag": "abc"},
        canonical_id="url:https://example.org/post",
    )
    assert r.candidate_from_json(json.loads(json.dumps(r.candidate_to_json(cand)))) == cand


def test_fetched_candidate_round_trip_with_raw_bytes() -> None:
    # raw bytes must survive a JSON round-trip (base64-encoded in the tagged form).
    cand = r.Fetched(
        url="reflector://wg21/msg-1",
        raw=b"\x00\x01\x02 binary \xff body",
        text="From: a@b\n\nhello",
        content_type=ContentType.EMAIL,
        metadata={"message_id": "<m1@host>"},
        canonical_id="email:<m1@host>",
        fetched_at="2026-06-25T00:00:00Z",
    )
    rebuilt = r.candidate_from_json(json.loads(json.dumps(r.candidate_to_json(cand))))
    assert rebuilt == cand
    assert isinstance(rebuilt, r.Fetched) and rebuilt.raw == cand.raw


def test_unknown_candidate_kind_raises() -> None:
    with pytest.raises(ValueError, match="unknown candidate kind"):
        r.candidate_from_json({"kind": "made-up", "url": "u"})


# -- compute_source_uid ---------------------------------------------------


def test_source_uid_is_deterministic_and_key_order_independent() -> None:
    a = r.compute_source_uid(
        role=SourceRole.SOURCE, kind=SourceKind.GITHUB, identity={"owner": "boostorg", "repo": "beast"}
    )
    b = r.compute_source_uid(
        role=SourceRole.SOURCE, kind=SourceKind.GITHUB, identity={"repo": "beast", "owner": "boostorg"}
    )
    assert a == b
    assert a.startswith("source:github:")


def test_source_uid_differs_for_different_sources() -> None:
    a = r.compute_source_uid(
        role=SourceRole.SOURCE, kind=SourceKind.GITHUB, identity={"owner": "boostorg", "repo": "beast"}
    )
    c = r.compute_source_uid(
        role=SourceRole.SOURCE, kind=SourceKind.GITHUB, identity={"owner": "boostorg", "repo": "asio"}
    )
    assert a != c


def test_source_uid_for_group_uses_group_kind() -> None:
    g = r.compute_source_uid(
        role=SourceRole.GROUP, group_kind=GroupKind.GITHUB_ORG, identity={"org": "boostorg"}
    )
    assert g.startswith("group:github_org:")


# -- SourceRow defaults ---------------------------------------------------


def test_source_row_defaults() -> None:
    row = r.SourceRow(source_uid="source:github:abc", name="boostorg/beast", kind=SourceKind.GITHUB)
    assert row.role == SourceRole.SOURCE
    assert row.group_kind is None
    assert row.parent_id is None
    assert row.window_inherited is False
    assert row.enabled is True
    assert row.state == SourceState.PENDING
    assert row.id is None


def test_group_row_is_expressible() -> None:
    group = r.SourceRow(
        source_uid="group:github_org:xyz",
        name="boostorg",
        role=SourceRole.GROUP,
        group_kind=GroupKind.GITHUB_ORG,
    )
    child = r.SourceRow(
        source_uid="source:github:abc",
        name="boostorg/beast",
        kind=SourceKind.GITHUB,
        parent_id=7,
        window_inherited=True,
    )
    assert group.role == SourceRole.GROUP and group.kind is None
    assert child.parent_id == 7 and child.window_inherited is True


# -- result seam types ----------------------------------------------------


def test_result_types_construct() -> None:
    fr = r.FetchResult(outcome=r.FetchOutcome.OK, status_code=200, raw=b"<html>")
    er = r.ExtractResult(text="body", title="t")
    idn = r.Identity(content_hash_text="a" * 64, content_hash_raw="b" * 64, canonical_id="gh:x/y#1")
    assert fr.outcome == "ok"
    assert er.text == "body"
    assert idn.canonical_id == "gh:x/y#1"
