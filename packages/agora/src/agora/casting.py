"""Deterministic persona casting for blueprint slots.

Pure selection logic over the :mod:`agora.roster` data; no LLM calls.
The generation phase asks :func:`cast_thread` for a full-thread
casting, or :func:`select_persona_for_slot` for a single slot. The
rules (master-plan §4.2, the-mod.md):

- ``signal`` / ``teaser`` slot → a signal-tier persona whose domain
  lens matches the slot's; when no persona covers the domain, the
  hand-authored :data:`NEAREST_DOMAIN` fallback picks the closest
  covered lens.
- ``noise`` slot → a jokester — except the misconception-trap
  question (``noise_stance == "misconception"``), which goes to a
  novice; the teaching correction is the trap slot's signal child,
  and :func:`cast_thread` surfaces the pairing.
- ``tangent`` slot → a jokester or a novice (learners wander into
  tangents too).
- ``mod`` slot → a human mod. ``AutoModerator`` is never cast by
  selection; generation places it explicitly for pinned metadata
  comments (the-mod.md §5b).
- ``deleted`` slot → a jokester (the body ends up ``[deleted]``;
  someone plausible has to have written it).
- ``encounter`` slots → two distinct signal personas alternating
  turns within each encounter chain.

Every choice is greedy and deterministic: ties break on a stable
SHA-256 hash of ``(document, slot_id, username)``, so re-running the
same blueprint yields the identical casting. Two or three personas
are chosen as the thread's "regulars" (seeded by the document alone)
and preferred while under a recurrence cap, so each thread has
familiar voices without one persona swallowing it.
"""

from __future__ import annotations

import hashlib
from typing import Iterable, Mapping, Optional, Sequence

from pydantic import BaseModel, Field

from agora.models import Reply, Thread
from agora.roster import MODS, ROSTER, Persona

MISCONCEPTION_STANCE = "misconception"
"""``Reply.noise_stance`` marker for a misconception-trap question
slot (see agora.md Step 5). Selection casts a novice on it."""

NEAREST_DOMAIN: dict[int, int] = {
    1: 9,    # networking / async I/O -> concurrency (same problem space)
    3: 2,    # game engines -> embedded (frame budgets ~ deterministic timing)
    5: 4,    # database / storage -> finance (throughput measurement culture)
    6: 10,   # application developer -> library design / API ergonomics
    7: 8,    # compiler implementation -> template metaprogramming
}
"""Hand-authored fallback for Table C domains no signal persona
covers. Values must be lenses the roster does cover."""

_SIGNAL = tuple(p for p in ROSTER if p.tier == "signal")
_NOVICES = tuple(p for p in ROSTER if p.tier == "learner")
_JOKESTERS = tuple(p for p in ROSTER if p.tier == "noise")
_HUMAN_MODS = tuple(p for p in MODS if p.username != "AutoModerator")

_REGULAR_COUNT_SIGNAL = 2
_REGULAR_COUNT_NOISE = 1
_REGULAR_RECURRENCE_CAP = 3
"""A regular is preferred over eligible peers only while it has
fewer than this many slots, so regulars recur without monopolizing."""


class ThreadCasting(BaseModel, frozen=True):
    """The full casting for one thread: slot -> persona username."""

    document: str
    submission_poster: str = Field(
        description="Signal-tier regular who posts the submission.",
    )
    regulars: tuple[str, ...] = Field(
        description="The 2-3 personas cast to recur in this thread.",
    )
    assignments: dict[str, str] = Field(
        description="``slot_id`` -> persona username for every reply slot.",
    )
    trap_pairs: tuple[tuple[str, str], ...] = Field(
        default=(),
        description="(question ``slot_id``, teaching ``slot_id``) per"
        " misconception trap: the novice's confused question and the"
        " signal child that corrects it.",
    )


def _stable_key(*parts: str) -> int:
    """Deterministic tie-break key (unlike ``hash()``, stable across runs)."""
    digest = hashlib.sha256(":".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _signal_pool(domain_lens: Optional[int]) -> tuple[Persona, ...]:
    """Signal personas for a domain, walking the fallback map as needed."""
    if domain_lens is None:
        return _SIGNAL
    lens = domain_lens
    seen: set[int] = set()
    while lens not in seen:
        seen.add(lens)
        pool = tuple(p for p in _SIGNAL if p.domain_lens == lens)
        if pool:
            return pool
        if lens not in NEAREST_DOMAIN:
            break
        lens = NEAREST_DOMAIN[lens]
    return _SIGNAL


def _pool_for_slot(slot: Reply) -> tuple[Persona, ...]:
    if slot.role in ("signal", "teaser", "encounter"):
        return _signal_pool(slot.domain_lens)
    if slot.role == "noise":
        if slot.noise_stance == MISCONCEPTION_STANCE:
            return _NOVICES
        return _JOKESTERS
    if slot.role == "tangent":
        return _JOKESTERS + _NOVICES
    if slot.role == "mod":
        return _HUMAN_MODS
    if slot.role == "deleted":
        return _JOKESTERS
    raise ValueError(f"Slot {slot.slot_id!r} has uncastable role {slot.role!r}.")


def _pick(
    pool: Sequence[Persona],
    *,
    document: str,
    slot_id: str,
    regulars: Iterable[str],
    usage: Mapping[str, int],
    exclude: frozenset[str] = frozenset(),
) -> Persona:
    candidates = [p for p in pool if p.username not in exclude] or list(pool)
    regular_set = set(regulars)

    def sort_key(persona: Persona) -> tuple:
        used = usage.get(persona.username, 0)
        preferred = (
            persona.username in regular_set and used < _REGULAR_RECURRENCE_CAP
        )
        # Regulars stick (most-used first, so the familiar voice keeps
        # the mic until the cap); everyone else spreads (least-used
        # first, so casting doesn't concentrate by accident).
        return (
            not preferred,
            -used if preferred else used,
            _stable_key(document, slot_id, persona.username),
        )

    return min(candidates, key=sort_key)


def select_persona_for_slot(
    slot: Reply,
    *,
    document: str,
    regulars: Iterable[str] = (),
    usage: Mapping[str, int] | None = None,
) -> Persona:
    """Cast one blueprint slot. Pure; ``usage`` is read, never written.

    ``regulars`` are preferred while under the recurrence cap;
    ``usage`` maps username -> slots already assigned in this thread
    (pass the running counts for balanced casting, or omit for a
    context-free selection).
    """
    return _pick(
        _pool_for_slot(slot),
        document=document,
        slot_id=slot.slot_id,
        regulars=regulars,
        usage=usage or {},
    )


def select_regulars(
    document: str,
    *,
    eligible_signal: Iterable[str] | None = None,
) -> tuple[str, ...]:
    """The thread's recurring personas: two signal, one jokester.

    ``eligible_signal`` restricts the signal picks to personas the
    thread's slots can actually cast (pass the usernames eligible for
    its signal-role slots); regulars only recur if the blueprint's
    domains can reach them. Choice order is a stable hash of the
    document, so the same paper gets the same regulars.
    """
    signal_names = (
        sorted(set(eligible_signal)) if eligible_signal
        else [p.username for p in _SIGNAL]
    )

    def order(names: Iterable[str]) -> list[str]:
        return sorted(
            names, key=lambda name: _stable_key(document, "regular", name),
        )

    return tuple(
        order(signal_names)[:_REGULAR_COUNT_SIGNAL]
        + order(p.username for p in _JOKESTERS)[:_REGULAR_COUNT_NOISE]
    )


def select_submission_poster(
    document: str,
    *,
    eligible_signal: Iterable[str] | None = None,
) -> str:
    """The OP: the thread's first signal regular (a power user)."""
    return select_regulars(document, eligible_signal=eligible_signal)[0]


def cast_thread(thread: Thread) -> ThreadCasting:
    """Cast every reply slot of a planned thread, deterministically.

    Slots are cast in the-mod.md priority order — teaser, encounter
    chains, signal, then everything else — in blueprint order within
    each class, so the marquee content gets first pick of the cast.
    """
    # Signal regulars come from personas whose lens covers MORE than
    # one slot — a regular that can only appear once can't recur.
    slot_coverage: dict[str, int] = {}
    for reply in thread.replies:
        if reply.role in ("signal", "teaser", "encounter"):
            for persona in _signal_pool(reply.domain_lens):
                slot_coverage[persona.username] = (
                    slot_coverage.get(persona.username, 0) + 1
                )
    recurrable = {name for name, count in slot_coverage.items() if count >= 2}
    regulars = select_regulars(
        thread.document,
        eligible_signal=recurrable or slot_coverage or None,
    )
    usage: dict[str, int] = {}
    assignments: dict[str, str] = {}

    def assign(slot: Reply, persona: Persona) -> None:
        assignments[slot.slot_id] = persona.username
        usage[persona.username] = usage.get(persona.username, 0) + 1

    def cast(slot: Reply) -> Persona:
        return _pick(
            _pool_for_slot(slot),
            document=thread.document,
            slot_id=slot.slot_id,
            regulars=regulars,
            usage=usage,
        )

    by_slot = {reply.slot_id: reply for reply in thread.replies}
    encounter_slot_ids = {
        slot_id for plan in thread.encounters for slot_id in plan.slot_ids
    }

    for reply in thread.replies:
        if reply.role == "teaser" and reply.slot_id not in encounter_slot_ids:
            assign(reply, cast(reply))

    for plan in thread.encounters:
        turns = [by_slot[sid] for sid in plan.slot_ids if sid in by_slot]
        if not turns:
            continue
        side_a = cast(turns[0])
        side_b = None
        if len(turns) > 1:
            # The two sides must be distinct people; widen past the
            # slot's domain when it has only one eligible persona.
            pool = _pool_for_slot(turns[1])
            if {p.username for p in pool} <= {side_a.username}:
                pool = _SIGNAL
            side_b = _pick(
                pool,
                document=thread.document,
                slot_id=turns[1].slot_id,
                regulars=regulars,
                usage=usage,
                exclude=frozenset({side_a.username}),
            )
        for index, turn in enumerate(turns):
            assign(turn, side_a if index % 2 == 0 or side_b is None else side_b)

    for reply in thread.replies:
        if reply.slot_id in assignments or reply.slot_id in encounter_slot_ids:
            continue
        if reply.role == "signal":
            assign(reply, cast(reply))

    for reply in thread.replies:
        if reply.slot_id not in assignments:
            assign(reply, cast(reply))

    trap_pairs = []
    for reply in thread.replies:
        if reply.role == "noise" and reply.noise_stance == MISCONCEPTION_STANCE:
            teaching = next(
                (
                    child for child in thread.replies
                    if child.parent_slot_id == reply.slot_id
                    and child.role in ("signal", "teaser")
                ),
                None,
            )
            if teaching is not None:
                trap_pairs.append((reply.slot_id, teaching.slot_id))

    return ThreadCasting(
        document=thread.document,
        submission_poster=regulars[0],
        regulars=regulars,
        assignments=assignments,
        trap_pairs=tuple(trap_pairs),
    )
