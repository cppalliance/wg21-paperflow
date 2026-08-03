"""Step 10 - Reactor: per-persona votes on the generated thread.

The reactor pass decides **who voted how** — never when: reveal
timing, aggregate scores, and ordering are website-side, derived
from the votes this pass records. Each vote is an individual
``{persona, direction}`` pair; at most one per ``(persona, target)``.

The pass is a pure heuristic seeded by the roster's reactor floats
(``upvote_bias``, ``contrarianism``, ``snark_affinity``) — no LLM.
That was the open call in the design (heuristic vs. a cheap model
pass): the floats plus the slot's role and noise tone already carry
enough signal to reproduce the-mod.md section 4 vote dynamics
(snark outscores substance; a correct technical take can sit
buried), and a heuristic is free and exactly reproducible. A model
pass stays possible later behind the same ``react_thread`` seam.

Every roster persona and human mod is a potential voter on every
target (lurkers vote — Reddit's voters far outnumber its
commenters). AutoModerator never votes, and nobody votes on their
own comment or submission. Two stable-hash draws decide each
``(persona, target)`` pair: one against a participation rate (base
by heat tier, plus a bonus when the persona commented in the
thread, decaying with reply depth — deep subthreads have fewer
eyes), one against an upvote probability built from the floats:

- ``upvote_bias`` sets the base generosity;
- ``snark_affinity`` swings the vote on snarky noise — high rewards
  the quip, low punishes it;
- ``contrarianism`` counts against consensus targets (signal,
  teaser, encounter, and mod comments, and the submission itself);
- a ``deleted`` slot was presumably deleted for cause and votes
  accordingly.

Like the casting weights, the constants here are tunable data, not
law. Re-running the same thread yields the identical vote set.
"""

from __future__ import annotations

import logging

from pipeline import StepContext, StepSpec

from agora.casting import _stable_key
from agora.models import PipelineState, Reply, Thread, Vote
from agora.roster import MODS, ROSTER, Persona

logger = logging.getLogger(__name__)

_STEP_10_NUMBER = 10

SUBMISSION_TARGET = "submission"
"""Hash-salt target id for votes on the submission itself. Reply
slot ids are ``sNN``, so this can never collide with one."""

_VOTERS: tuple[Persona, ...] = ROSTER + tuple(
    mod for mod in MODS if mod.username != "AutoModerator"
)
"""Everyone who votes: the full persona roster plus the human mods.
Bots don't vote."""

_PARTICIPATION_BY_HEAT: dict[str, float] = {
    "cold": 0.25,
    "warm": 0.40,
    "hot": 0.55,
    "thermonuclear": 0.70,
}
"""Chance that a given voter votes on a given target. Hotter threads
draw more eyes, so more of the roster weighs in."""

_PARTICIPANT_BONUS = 0.20
"""Personas who commented in the thread are demonstrably present and
vote more often than lurkers."""

_PARTICIPATION_CAP = 0.90

_DEPTH_FALLOFF = 0.85
"""Multiplied into the participation rate once per level of reply
depth: a top-level quip is seen by everyone, a depth-5 encounter
turn by whoever expanded the subthread."""

_BASE_FLOOR = 0.35
_BASE_SPAN = 0.50
"""Upvote probability before target adjustments:
``floor + span * upvote_bias``. The floor sits above one half of the
range because most Reddit votes are upvotes; only genuinely
misanthropic floats downvote at rest."""

_SNARK_WEIGHT = 0.60
_SNARK_PIVOT = 0.35
"""On a snarky target, ``snark_affinity`` above the pivot pushes
toward the upvote, below it toward the downvote."""

_CONTRARIAN_WEIGHT = 0.45
_CONTRARIAN_PIVOT = 0.35
"""On a consensus target, ``contrarianism`` above the pivot pushes
toward the downvote — the mechanism that can bury a correct take.
Deliberately gentler than the snark swing: the-mod.md section 4 has
the best technical comment at 12 points under a quip with 340 —
substance usually stays above water, it just never wins."""

_DELETED_PENALTY = 0.30

_PROBABILITY_MIN = 0.05
_PROBABILITY_MAX = 0.95
"""No vote is ever a sure thing in either direction."""

_CONSENSUS_ROLES = frozenset({"signal", "teaser", "encounter", "mod"})
"""Roles whose comments read as the thread's respectable consensus:
the targets contrarians push against."""

_SNARK_MARKERS = ("snark", "sarcas", "quip", "joke", "meme", "mock")
"""``noise_tone`` substrings that mark a comment as a quip. The tone
labels are free text from the planner, so this matches families, not
exact values."""


# -- Heuristic core ------------------------------------------------------------


def _uniform(*parts: str) -> float:
    """Deterministic draw in ``[0, 1)`` from the stable hash."""
    return _stable_key(*parts) / 2**64


def _is_snarky(reply: Reply) -> bool:
    tone = (reply.noise_tone or "").lower()
    return any(marker in tone for marker in _SNARK_MARKERS)


def upvote_probability(
    persona: Persona,
    *,
    snarky: bool,
    consensus: bool,
    deleted: bool = False,
) -> float:
    """Chance this persona's vote on a target is the upvote."""
    probability = _BASE_FLOOR + _BASE_SPAN * persona.upvote_bias
    if snarky:
        probability += _SNARK_WEIGHT * (persona.snark_affinity - _SNARK_PIVOT)
    if consensus:
        probability -= _CONTRARIAN_WEIGHT * (
            persona.contrarianism - _CONTRARIAN_PIVOT
        )
    if deleted:
        probability -= _DELETED_PENALTY
    return min(max(probability, _PROBABILITY_MIN), _PROBABILITY_MAX)


def decide_vote(
    document: str,
    persona: Persona,
    target_id: str,
    *,
    participation: float,
    snarky: bool,
    consensus: bool,
    deleted: bool = False,
) -> Vote | None:
    """One persona's vote on one target, or ``None`` for an abstain.

    Two independent stable draws, both keyed on
    ``(document, target_id, persona)``: the first gates
    participation, the second picks the direction against
    :func:`upvote_probability`.
    """
    if _uniform(document, "reactor", "part", target_id, persona.username) >= (
        participation
    ):
        return None
    probability = upvote_probability(
        persona, snarky=snarky, consensus=consensus, deleted=deleted,
    )
    up = _uniform(document, "reactor", "dir", target_id, persona.username) < (
        probability
    )
    return Vote(persona=persona.username, direction=1 if up else -1)


# -- Thread pass ---------------------------------------------------------------


def react_thread(thread: Thread) -> None:
    """Fill ``Reply.votes`` and ``Thread.submission_votes`` in place.

    Deterministic: the same thread yields the identical vote set.
    Scores, orderings, and time labels are untouched — the website
    derives them from revealed votes.
    """
    participants = {
        reply.character_username
        for reply in thread.replies
        if reply.character_username
    }
    if thread.submission_poster_id:
        participants.add(thread.submission_poster_id)
    base = _PARTICIPATION_BY_HEAT[thread.heat]

    def rate_for(persona: Persona, depth: int = 0) -> float:
        rate = base
        if persona.username in participants:
            rate += _PARTICIPANT_BONUS
        return min(rate, _PARTICIPATION_CAP) * _DEPTH_FALLOFF**depth

    thread.submission_votes = [
        vote
        for persona in _VOTERS
        if persona.username != thread.submission_poster_id
        and (
            vote := decide_vote(
                thread.document, persona, SUBMISSION_TARGET,
                participation=rate_for(persona),
                snarky=False, consensus=True,
            )
        )
        is not None
    ]

    for reply in thread.replies:
        reply.votes = [
            vote
            for persona in _VOTERS
            if persona.username != reply.character_username
            and (
                vote := decide_vote(
                    thread.document, persona, reply.slot_id,
                    participation=rate_for(persona, reply.depth),
                    snarky=_is_snarky(reply),
                    consensus=reply.role in _CONSENSUS_ROLES,
                    deleted=reply.role == "deleted",
                )
            )
            is not None
        ]


# -- Step 10 - Reactor ---------------------------------------------------------


async def _pure_react(state: PipelineState, ctx: StepContext, spec: StepSpec) -> None:
    """Cast every persona's votes across the finished thread."""
    thread = state.thread
    assert thread is not None, "Step 10 requires the Thread from Step 7."

    react_thread(thread)

    comment_votes = sum(len(reply.votes) for reply in thread.replies)
    logger.info(
        "Step 10: %d submission votes, %d comment votes across %d comments",
        len(thread.submission_votes or []),
        comment_votes,
        len(thread.replies),
    )
