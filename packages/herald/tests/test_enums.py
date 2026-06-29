#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Vocabulary tests - the enums are storage/wire contracts, so their values are pinned."""

from __future__ import annotations

from herald.collection import enums


def test_seven_event_kinds() -> None:
    assert len(list(enums.EventKind)) == 7
    assert {k.value for k in enums.EventKind} == {
        "content_first_seen",
        "content_changed",
        "url_disappeared",
        "url_resurrected",
        "candidate_observed",
        "content_re_extracted",
        "person_candidate_observed",
    }


def test_four_change_kinds() -> None:
    assert {k.value for k in enums.ChangeKind} == {"new", "changed", "unchanged", "removed"}


def test_event_origin_values() -> None:
    assert enums.EventOrigin.LIVE == "live"
    assert enums.EventOrigin.BACKFILL == "backfill"


def test_source_role_and_group_kind() -> None:
    assert {r.value for r in enums.SourceRole} == {"source", "group"}
    assert {g.value for g in enums.GroupKind} == {
        "github_org",
        "reflector_host",
        "discord_guild",
    }


def test_source_state_includes_candidate() -> None:
    assert enums.SourceState.CANDIDATE == "candidate"
    assert {s.value for s in enums.SourceState} == {
        "candidate",
        "pending",
        "active",
        "rejected",
        "demoted",
    }


def test_access_state_hyphenated_values() -> None:
    assert enums.AccessState.BLOCKED_BY_ROBOTS == "blocked-by-robots"
    assert enums.AccessState.BLOCKED_BY_EDGE == "blocked-by-edge"
    assert enums.AccessState.REQUIRES_SIGNED_REQUESTS == "requires-signed-requests"


def test_strenum_equals_string() -> None:
    # StrEnum members compare equal to their str value and JSON-serialize as the string.
    import json

    assert enums.Visibility.PRIVATE == "private"
    assert json.dumps({"v": enums.ContentType.EMAIL}) == '{"v": "email"}'


def test_source_kind_is_clean_pollable_set() -> None:
    # Group container kinds must NOT leak into the pollable adapter vocabulary.
    values = {k.value for k in enums.SourceKind}
    assert "github" in values
    assert "reflector" in values
    assert "github_org" not in values
    assert "reflector_host" not in values


def test_window_cursor_candidate_kind_tags() -> None:
    assert {w.value for w in enums.WindowKind} == {"temporal", "byte-range", "current-only"}
    assert {c.value for c in enums.CursorKind} == {
        "timestamp",
        "monotonic-id",
        "byte-offset",
        "opaque-token",
        "composite",
    }
    assert {c.value for c in enums.CandidateKind} == {"discovered", "fetched"}


def test_full_member_sets_are_pinned() -> None:
    # These are storage/wire vocabularies; their full value sets are part of the contract.
    assert {v.value for v in enums.SourceKind} == {
        "web",
        "rss",
        "sitemap",
        "mbox",
        "reflector",
        "mcp",
        "slack",
        "github",
        "discourse",
        "discord",
        "reddit",
    }
    assert {v.value for v in enums.AccessState} == {
        "open",
        "partial",
        "blocked-by-edge",
        "blocked-by-robots",
        "requires-signed-requests",
    }
    assert {v.value for v in enums.ContentType} == {
        "post",
        "email",
        "announcement",
        "discussion",
        "transcript",
        "paper",
        "release",
    }
    assert {v.value for v in enums.Visibility} == {"public", "private", "restricted"}
    assert {v.value for v in enums.CadenceKind} == {"fixed", "adaptive", "manual"}


def test_person_vocabularies_are_pinned() -> None:
    assert {v.value for v in enums.PersonStatus} == {
        "active",
        "lapsed",
        "emeritus",
        "deceased",
        "unknown",
    }
    assert {v.value for v in enums.VariantKind} == {
        "legal",
        "nickname",
        "byline",
        "transliteration",
        "former",
    }
    assert {v.value for v in enums.HandlePlatform} == {
        "github",
        "mastodon",
        "bluesky",
        "x",
        "linkedin",
        "orcid",
        "website",
    }


def test_fetch_outcome_is_pinned() -> None:
    assert {v.value for v in enums.FetchOutcome} == {
        "ok",
        "not-modified",
        "not-found",
        "blocked",
        "error",
    }


def test_person_event_kind_pinned() -> None:
    assert {v.value for v in enums.PersonEventKind} == {
        "role_change",
        "affiliation_change",
        "publication",
        "mention",
    }


def test_resolution_status_pinned() -> None:
    assert {v.value for v in enums.ResolutionStatus} == {
        "pending",
        "resolved",
        "rejected",
    }


def test_metric_kind_pinned() -> None:
    assert {v.value for v in enums.MetricKind} == {
        "reactions",
        "upvotes",
        "stars",
        "views",
    }
