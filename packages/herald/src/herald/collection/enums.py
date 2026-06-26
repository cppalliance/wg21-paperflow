#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Contract vocabularies for the collection layer.

Every value here is part of a wire/storage contract, so they are :class:`enum.StrEnum`
members whose *value* is the stored string (e.g. ``AccessState.BLOCKED_BY_ROBOTS ==
"blocked-by-robots"``). The event/source/content/state vocabularies mirror
``docs/foundation/1-collection.md`` verbatim; the additions (``SourceRole``, ``GroupKind``,
``WindowKind``, ``CursorKind``, ``SourceState.CANDIDATE``, ``EventOrigin``) are recorded as
deviations in ``docs/decisions``.
"""

from __future__ import annotations

from enum import StrEnum


class EventKind(StrEnum):
    """The seven canonical collection events (1-collection.md). Fixed; new semantics are
    payload annotations, never new kinds."""

    CONTENT_FIRST_SEEN = "content_first_seen"
    CONTENT_CHANGED = "content_changed"
    URL_DISAPPEARED = "url_disappeared"
    URL_RESURRECTED = "url_resurrected"
    CANDIDATE_OBSERVED = "candidate_observed"
    CONTENT_RE_EXTRACTED = "content_re_extracted"
    PERSON_CANDIDATE_OBSERVED = "person_candidate_observed"


class EventOrigin(StrEnum):
    """Provenance annotation carried in the event payload (not a new EventKind).

    ``LIVE`` is steady-state forward collection; ``BACKFILL`` is historical content pulled
    by a backfill pass. Generation consumers ignore ``BACKFILL``; archival/enhancement
    consumers process all origins.
    """

    LIVE = "live"
    BACKFILL = "backfill"


class ChangeKind(StrEnum):
    """The outcome of a change-detection strategy for one polled item."""

    NEW = "new"
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    REMOVED = "removed"


class SourceKind(StrEnum):
    """Pollable source adapter kinds (the clean adapter vocabulary).

    ``web``/``rss``/``sitemap``/``mbox``/``mcp``/``reflector``/``slack`` are the spec set;
    the API adapters (``github``/``discourse``/``discord``/``reddit``) extend it for the
    sources the principal collects (recorded as a deviation). Group container kinds are NOT
    here - see :class:`GroupKind`.
    """

    WEB = "web"
    RSS = "rss"
    SITEMAP = "sitemap"
    MBOX = "mbox"
    REFLECTOR = "reflector"
    MCP = "mcp"
    SLACK = "slack"
    GITHUB = "github"
    DISCOURSE = "discourse"
    DISCORD = "discord"
    REDDIT = "reddit"


class SourceRole(StrEnum):
    """Whether a registry row is a pollable source or a non-pollable group container."""

    SOURCE = "source"
    GROUP = "group"


class GroupKind(StrEnum):
    """Group container kinds - expand into child ``role=source`` rows (kept out of
    :class:`SourceKind` so the adapter vocabulary stays clean)."""

    GITHUB_ORG = "github_org"
    REFLECTOR_HOST = "reflector_host"
    DISCORD_GUILD = "discord_guild"


class SourceState(StrEnum):
    """The source curation lifecycle (residue.md)."""

    CANDIDATE = "candidate"
    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"
    DEMOTED = "demoted"


class AccessState(StrEnum):
    """How reachable a source is, recorded after fetch attempts (1-collection.md)."""

    OPEN = "open"
    PARTIAL = "partial"
    BLOCKED_BY_EDGE = "blocked-by-edge"
    BLOCKED_BY_ROBOTS = "blocked-by-robots"
    REQUIRES_SIGNED_REQUESTS = "requires-signed-requests"


class CadenceKind(StrEnum):
    """How a source's next poll time is computed."""

    FIXED = "fixed"
    ADAPTIVE = "adaptive"
    MANUAL = "manual"


class ContentType(StrEnum):
    """The nature of a piece of content (1-collection.md)."""

    POST = "post"
    EMAIL = "email"
    ANNOUNCEMENT = "announcement"
    DISCUSSION = "discussion"
    TRANSCRIPT = "transcript"
    PAPER = "paper"
    RELEASE = "release"


class Visibility(StrEnum):
    """Content visibility, load-bearing for downstream publish/train gating (1-collection.md)."""

    PUBLIC = "public"
    PRIVATE = "private"
    RESTRICTED = "restricted"


class WindowKind(StrEnum):
    """Tag for the typed Window range union (serialized as the ``kind`` field)."""

    TEMPORAL = "temporal"
    BYTE_RANGE = "byte-range"
    CURRENT_ONLY = "current-only"


class CursorKind(StrEnum):
    """Tag for the typed Cursor union (serialized as the ``kind`` field)."""

    TIMESTAMP = "timestamp"
    MONOTONIC_ID = "monotonic-id"
    BYTE_OFFSET = "byte-offset"
    OPAQUE_TOKEN = "opaque-token"
    COMPOSITE = "composite"


class CandidateKind(StrEnum):
    """Tag for the typed Candidate union (serialized as the ``kind`` field)."""

    DISCOVERED = "discovered"
    FETCHED = "fetched"


class PersonStatus(StrEnum):
    """Lifecycle status of a tracked person (1-collection.md person table)."""

    ACTIVE = "active"
    LAPSED = "lapsed"
    EMERITUS = "emeritus"
    DECEASED = "deceased"
    UNKNOWN = "unknown"


class VariantKind(StrEnum):
    """Kind of a person name variant (1-collection.md)."""

    LEGAL = "legal"
    NICKNAME = "nickname"
    BYLINE = "byline"
    TRANSLITERATION = "transliteration"
    FORMER = "former"


class HandlePlatform(StrEnum):
    """Platform a person handle belongs to (1-collection.md)."""

    GITHUB = "github"
    MASTODON = "mastodon"
    BLUESKY = "bluesky"
    X = "x"
    LINKEDIN = "linkedin"
    ORCID = "orcid"
    WEBSITE = "website"


__all__ = [
    "EventKind",
    "EventOrigin",
    "ChangeKind",
    "SourceKind",
    "SourceRole",
    "GroupKind",
    "SourceState",
    "AccessState",
    "CadenceKind",
    "ContentType",
    "Visibility",
    "WindowKind",
    "CursorKind",
    "CandidateKind",
    "PersonStatus",
    "VariantKind",
    "HandlePlatform",
]
