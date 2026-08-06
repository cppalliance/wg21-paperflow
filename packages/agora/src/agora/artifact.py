#
# Copyright (c) 2026 Glenn Siegman (glenn@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""The ``.agora.json`` artifact: serialization and producer validation.

The artifact is the interface between this package (producer) and the
website (consumer). :func:`thread_to_artifact` maps a fully generated
:class:`~agora.models.Thread` to the artifact dict, translating model
field names to the artifact vocabulary (``content`` -> ``body``,
``character_username`` -> ``persona``, ``flair`` -> ``tag``,
``submission_flair`` -> ``submission_tag``). :func:`validate_artifact`
enforces the invariants the producer guarantees, so a malformed
artifact fails here instead of at website ingest.

Design rules the artifact encodes:

- **Timing-agnostic.** No reveal times, no publish timestamps.
  ``generated_at`` is provenance (when generation ran), never pacing.
- **Votes are individual.** Each vote is ``{persona, direction}`` with
  direction exactly ``+1`` or ``-1``. No scores, no tallies — the
  website derives scores from revealed votes.
- **Personas by username only.** The roster owns the definitions;
  unknown usernames are a validation failure when a roster is given.
- **The blueprint travels for audit.** The analysis-phase plan is
  embedded verbatim so a thread can be explained or regenerated.
"""

from __future__ import annotations

from typing import Any

from agora.models import Reply, Thread

SCHEMA_VERSION = 1

_HEAT_TIERS = {"cold", "warm", "hot", "thermonuclear"}
_INTEREST_TIERS = {"niche", "relevant", "magnetic", "gravitational"}
_PAPER_TYPES = {"wording", "proposal", "directional"}
_COMMITTEES = {"ewg", "lewg", "cwg", "lwg"}
_REVISION_CASES = {"A", "B", "C"}
_COMMENT_ROLES = {
    "signal", "noise", "encounter", "tangent", "teaser", "mod", "deleted",
}

# Fields on Reply / Thread that the generation phases fill. The
# blueprint embedded in the artifact is the analysis-phase plan, so
# these are stripped from it (they appear at the artifact's top level
# and in the comment list instead).
_REPLY_GENERATION_FIELDS = frozenset({
    "content", "character_username", "score", "ordering", "time_label",
    "controversial", "edited", "collapsed", "deleted", "removed",
    "is_mod", "is_op", "flair", "votes",
})
_THREAD_GENERATION_FIELDS = frozenset({
    "submission_poster_id", "submission_votes", "generated_at",
})


class ArtifactError(ValueError):
    """A ``.agora.json`` artifact violates the contract invariants."""


# -- Serialization -----------------------------------------------------------


def thread_to_artifact(thread: Thread) -> dict[str, Any]:
    """Map a fully generated :class:`Thread` to the artifact dict.

    The caller is responsible for the thread being complete (comments
    written, personas assigned, votes filled); run the result through
    :func:`validate_artifact` before persisting.
    """
    dump = thread.model_dump(mode="json")
    return {
        "schema_version": SCHEMA_VERSION,
        "document": thread.document,
        "paper": thread.paper,
        "revision": thread.revision,
        "mailing_id": thread.mailing_id,
        "title": thread.title,
        "authors": list(thread.authors),
        "audience": thread.audience,
        "subreddit": thread.subreddit,
        "committee": thread.committee,
        "paper_type": thread.paper_type,
        "heat": thread.heat,
        "interest": thread.interest,
        "revision_case": thread.revision_case,
        "prior_revision": thread.prior_revision,
        "submission_title": thread.submission_title,
        "submission_body": thread.submission_body,
        "submission_link": thread.submission_link,
        "submission_tag": thread.submission_flair,
        "submission_poster_id": thread.submission_poster_id,
        "submission_votes": [
            vote.model_dump(mode="json")
            for vote in (thread.submission_votes or [])
        ],
        "technical_anchors": dump["technical_anchors"],
        "design_tensions": dump["design_tensions"],
        "blueprint": _blueprint_view(dump),
        "generated_at": dump["generated_at"],
        "comments": [_comment_view(reply) for reply in thread.replies],
    }


def _comment_view(reply: Reply) -> dict[str, Any]:
    """Map one :class:`Reply` to the artifact comment shape."""
    return {
        "slot_id": reply.slot_id,
        "parent_slot_id": reply.parent_slot_id,
        "depth": reply.depth,
        "role": reply.role,
        "persona": reply.character_username,
        "body": reply.content,
        "tag": reply.flair,
        "is_op": reply.is_op,
        "is_mod": reply.is_mod,
        "controversial": reply.controversial,
        "edited": reply.edited,
        "deleted": reply.deleted,
        "removed": reply.removed,
        "collapsed": reply.collapsed,
        "anchor_id": reply.anchor_id,
        "encounter_id": reply.encounter_id,
        "domain_lens": reply.domain_lens,
        "brief": reply.brief,
        "votes": [vote.model_dump(mode="json") for vote in reply.votes],
    }


def _blueprint_view(dump: dict[str, Any]) -> dict[str, Any]:
    """The analysis-phase plan: the thread dump minus generation fields.

    This is what the planner produced before any content was written —
    every slot with its brief, the calibration, anchors, tensions, and
    encounter plans. Embedded verbatim for audit and regeneration.

    The blueprint is audit data, not part of the consumer contract:
    consumers must treat it as opaque. The only pinned guarantee is
    that generation fields are omitted. Hand-authored test fixtures
    embed a condensed stub here rather than this full shape.
    """
    blueprint = {
        key: value for key, value in dump.items()
        if key not in _THREAD_GENERATION_FIELDS
    }
    blueprint["replies"] = [
        {
            key: value for key, value in reply.items()
            if key not in _REPLY_GENERATION_FIELDS
        }
        for reply in dump["replies"]
    ]
    return blueprint


# -- Producer validation -----------------------------------------------------


_REQUIRED_TOP_LEVEL = (
    "schema_version", "document", "paper", "revision", "mailing_id",
    "title", "authors", "audience", "subreddit", "committee",
    "paper_type", "heat", "interest", "revision_case", "prior_revision",
    "submission_title", "submission_body", "submission_link",
    "submission_tag", "submission_poster_id", "submission_votes",
    "technical_anchors", "design_tensions", "blueprint", "generated_at",
    "comments",
)


def validate_artifact(
    artifact: dict[str, Any],
    *,
    roster: set[str] | None = None,
) -> None:
    """Assert the contract invariants on an artifact dict.

    Raises :class:`ArtifactError` on the first violation. ``roster``
    is the set of valid persona usernames; when ``None`` the roster
    check is skipped (the roster module supplies it once it exists).
    Keys starting with ``_`` (fixture notes and the like) are ignored.
    """
    missing = [key for key in _REQUIRED_TOP_LEVEL if key not in artifact]
    if missing:
        raise ArtifactError(f"Artifact is missing top-level keys: {missing}.")

    if artifact["schema_version"] != SCHEMA_VERSION:
        raise ArtifactError(
            f"schema_version is {artifact['schema_version']!r};"
            f" this producer writes {SCHEMA_VERSION}."
        )
    if artifact["subreddit"] != "r/wg21":
        raise ArtifactError(
            f"subreddit is {artifact['subreddit']!r}; every thread lands"
            f" in 'r/wg21'."
        )
    _require_vocab(artifact, "committee", _COMMITTEES)
    _require_vocab(artifact, "paper_type", _PAPER_TYPES)
    _require_vocab(artifact, "heat", _HEAT_TIERS)
    _require_vocab(artifact, "interest", _INTEREST_TIERS)
    _require_vocab(artifact, "revision_case", _REVISION_CASES)

    if artifact["revision_case"] == "C" and not artifact["prior_revision"]:
        raise ArtifactError("revision_case is 'C' but prior_revision is unset.")

    for field_name in ("document", "paper", "title", "submission_title",
                       "submission_body", "submission_link",
                       "submission_poster_id", "generated_at"):
        if not artifact[field_name]:
            raise ArtifactError(f"{field_name} must be non-empty.")

    _validate_votes(artifact["submission_votes"], "submission", roster)
    _validate_comments(artifact, roster)

    if roster is not None and artifact["submission_poster_id"] not in roster:
        raise ArtifactError(
            f"submission_poster_id {artifact['submission_poster_id']!r}"
            f" is not in the roster."
        )


def _require_vocab(
    artifact: dict[str, Any], field_name: str, vocabulary: set[str],
) -> None:
    value = artifact[field_name]
    if value not in vocabulary:
        raise ArtifactError(
            f"{field_name} is {value!r}; expected one of {sorted(vocabulary)}."
        )


def _validate_comments(
    artifact: dict[str, Any], roster: set[str] | None,
) -> None:
    comments = artifact["comments"]
    if not isinstance(comments, list) or not comments:
        raise ArtifactError("comments must be a non-empty list.")

    by_slot: dict[str, dict[str, Any]] = {}
    for comment in comments:
        slot_id = comment.get("slot_id")
        if not slot_id:
            raise ArtifactError("Every comment needs a non-empty slot_id.")
        if slot_id in by_slot:
            raise ArtifactError(f"Duplicate comment slot_id {slot_id!r}.")
        by_slot[slot_id] = comment

    anchor_ids = {anchor["id"] for anchor in artifact["technical_anchors"]}
    addressed: set[str] = set()

    for comment in comments:
        slot_id = comment["slot_id"]
        parent_slot_id = comment.get("parent_slot_id")
        depth = comment.get("depth")

        if parent_slot_id is None:
            if depth != 0:
                raise ArtifactError(
                    f"Comment {slot_id!r} is top-level but has depth {depth}."
                )
        else:
            parent = by_slot.get(parent_slot_id)
            if parent is None:
                raise ArtifactError(
                    f"Comment {slot_id!r} has dangling parent_slot_id"
                    f" {parent_slot_id!r}."
                )
            if depth != parent["depth"] + 1:
                raise ArtifactError(
                    f"Comment {slot_id!r} has depth {depth}; its parent"
                    f" {parent_slot_id!r} has depth {parent['depth']}."
                )
        if not isinstance(depth, int) or depth < 0 or depth > 6:
            raise ArtifactError(
                f"Comment {slot_id!r} has out-of-range depth {depth!r}."
            )

        if comment.get("role") not in _COMMENT_ROLES:
            raise ArtifactError(
                f"Comment {slot_id!r} has unknown role {comment.get('role')!r}."
            )
        if not comment.get("persona"):
            raise ArtifactError(f"Comment {slot_id!r} has no persona.")
        if not comment.get("body"):
            raise ArtifactError(f"Comment {slot_id!r} has no body.")
        if roster is not None and comment["persona"] not in roster:
            raise ArtifactError(
                f"Comment {slot_id!r} persona {comment['persona']!r} is not"
                f" in the roster."
            )
        if comment.get("is_op") and (
            comment["persona"] != artifact["submission_poster_id"]
        ):
            raise ArtifactError(
                f"Comment {slot_id!r} is marked is_op but its persona"
                f" {comment['persona']!r} is not the submission poster."
            )

        comment_anchor = comment.get("anchor_id")
        if comment_anchor is not None:
            if comment_anchor not in anchor_ids:
                raise ArtifactError(
                    f"Comment {slot_id!r} references unknown anchor"
                    f" {comment_anchor!r}."
                )
            addressed.add(comment_anchor)

        _validate_votes(comment.get("votes"), slot_id, roster)

    unaddressed = sorted(anchor_ids - addressed)
    if unaddressed:
        raise ArtifactError(
            f"Technical anchors with no addressing comment: {unaddressed}."
        )


def _validate_votes(
    votes: Any, target: str, roster: set[str] | None,
) -> None:
    if not isinstance(votes, list):
        raise ArtifactError(f"Votes on {target!r} must be a list.")
    seen: set[str] = set()
    for vote in votes:
        persona = vote.get("persona") if isinstance(vote, dict) else None
        direction = vote.get("direction") if isinstance(vote, dict) else None
        if not persona:
            raise ArtifactError(
                f"A vote on {target!r} has no persona username."
            )
        if direction not in (1, -1):
            raise ArtifactError(
                f"Vote by {persona!r} on {target!r} has direction"
                f" {direction!r}; must be 1 or -1."
            )
        if persona in seen:
            raise ArtifactError(
                f"Persona {persona!r} votes more than once on {target!r}."
            )
        seen.add(persona)
        if roster is not None and persona not in roster:
            raise ArtifactError(
                f"Voter {persona!r} on {target!r} is not in the roster."
            )
