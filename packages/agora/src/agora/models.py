#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Pydantic models for the agora pipeline.

One schema, fields filled progressively. The analysis-phase steps in
this package populate every structural and analytical field of
``Thread`` / ``Reply`` / ``EncounterPlan``. Generation-phase fields
(``content``, ``character_username``, ``score``, furniture flags,
``votes``) stay ``None`` until a future generation phase fills
them in.

``SourceLoc`` is imported from ``paperstore`` (the canonical home for
the loc type at the storage layer). Each ``TechnicalAnchor`` carries
a ``claim_uid`` (the paperstore integer key) and an optional
``SourceLoc`` for display.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Literal, Optional

from paperstore import SourceLoc
from pydantic import BaseModel, Field, model_validator

# -- Enumerations ------------------------------------------------------------

PaperType = Literal["wording", "proposal", "directional"]
HeatTier = Literal["cold", "warm", "hot", "thermonuclear"]
InterestTier = Literal["niche", "relevant", "magnetic", "gravitational"]
Subreddit = Literal["r/wg21"]
"""Every thread lands in the single r/wg21 community. The artifact
carries this as producer vocabulary; the website maps it to its
``wg21`` community row. The schema stays a Literal so more
communities can be added later without a shape change."""
Committee = Literal["ewg", "lewg", "cwg", "lwg"]
"""Committee group derived from the paper's first target audience.
Drives audience badges on the website; does not change where the
thread lands."""
AnchorKind = Literal["load_bearing", "conflicted", "critical_gap"]
ReplyRole = Literal[
    "signal",
    "noise",
    "encounter",
    "tangent",
    "teaser",
    "mod",
    "deleted",
]
EncounterResolution = Literal["concession", "narrowing", "stalemate"]
NoiseStance = Literal[
    "didn't-read",
    "skimmed-abstract",
    "Rust-evangelist",
    "C-purist",
    "it's-fine-actually",
    "doomsayer",
    "recruiter-brain",
    "process-cynic",
    "old-guard",
    "student",
    "misconception",
]
"""the-mod.md section 6 stance palette plus the ``misconception``
marker agora.md Step 5 puts on a misconception-trap question slot.
Closed vocabulary: casting keys trap handling on the exact
``misconception`` string, so a free-form stance would let a typo
silently demote a trap to ordinary noise."""
RevisionCase = Literal["A", "B", "C"]
"""``A``: new paper, no prior thread. ``B``: re-run of an existing
revision (regenerate same thread). ``C``: new revision; the prior
thread is referenced and the submission body calls out the delta."""


# -- Domain models -----------------------------------------------------------


class TechnicalAnchor(BaseModel, frozen=True):
    """A load-bearing claim, an internally-contested claim, or a critical gap.

    Derived from paperstore extract tables in Step 1 (Smell Test).
    Every signal slot must address at least one anchor; every anchor
    must be addressed by at least one slot. The ``loc`` ties the
    anchor back to the exact line of the paper that prompted it.
    """

    id: str = Field(description="Stable id within the thread, e.g. ``a01``.")
    kind: AnchorKind
    summary: str = Field(
        description="One-line description of the anchor (what makes it load-bearing,"
        " contested, or gap-shaped).",
    )
    claim_text: str = Field(
        description="Exact quote from the paper that the anchor crystallises.",
    )
    claim_uid: int
    claim_loc: SourceLoc | None = Field(
        default=None,
        description="Source location for display. Not used for identity.",
    )
    supports: list[str] = Field(
        default_factory=list,
        description="Optional list of evidence ids or external references"
        " supporting / contradicting this anchor.",
    )


class ResearchAgentReport(BaseModel, frozen=True):
    """Return from one Step 2 research sub-agent.

    Three sub-agents run in parallel: public reception, committee
    history, author + ecosystem. Each returns ``findings`` capped at
    roughly 200 words plus a coarse heat / interest signal that
    Step 3 will calibrate against.
    """

    agent: Literal["public_reception", "committee_history", "author_ecosystem"]
    findings: str = Field(description="Compressed research summary (~200 words max).")
    sources: list[str] = Field(
        default_factory=list,
        description="URLs the agent considered most relevant.",
    )
    heat_signal: HeatTier = Field(
        description="Coarse heat suggestion from this agent's slice of the record.",
    )
    interest_signal: InterestTier = Field(
        description="Coarse interest suggestion from this agent's slice of the record.",
    )


class ResearchSummary(BaseModel, frozen=True):
    """The three research sub-agent reports collected for Step 3 to read."""

    public_reception: ResearchAgentReport
    committee_history: ResearchAgentReport
    author_ecosystem: ResearchAgentReport


class DesignTension(BaseModel, frozen=True):
    """A genuine disagreement seeded by stored rhetorical markers.

    Each design tension is a candidate for an Encounter in Step 6.
    Step 3 decides how many encounters this thread will run; Step 5
    pre-allocates encounter slots; Step 6 fills the position pair and
    resolution path.
    """

    id: str = Field(description="Stable id within the thread, e.g. ``t01``.")
    description: str = Field(description="One-line description of the tension.")
    anchor_id: Optional[str] = Field(
        default=None,
        description="Anchor this tension grows from, if any.",
    )


class Vote(BaseModel, frozen=True):
    """One persona's vote on one target (the submission or a comment).

    Votes are always individual — never aggregated into a score. The
    website derives scores from the votes that have revealed, so the
    artifact carries who voted and how, nothing else.
    """

    persona: str = Field(description="Roster username of the voter.")
    direction: Literal[1, -1]


class EncounterPlan(BaseModel, frozen=True):
    """A planned multi-turn back-and-forth between two named positions.

    Step 6 emits one ``EncounterPlan`` per allocated encounter and
    links its ``slot_ids`` to the encounter-role replies that Step 5
    pre-allocated.
    """

    encounter_id: str
    design_tension_id: str
    design_tension: str = Field(description="One-line tension description.")
    position_a: str = Field(description="First substantive position.")
    position_b: str = Field(description="Second substantive position.")
    resolution: EncounterResolution
    slot_ids: list[str] = Field(
        description="Ordered ``Reply.slot_id`` values for this encounter's turns.",
    )


class Reply(BaseModel):
    """A single planned reply in the thread.

    Analysis-phase fields are required and describe what the reply
    must accomplish; generation-phase fields (``content``,
    ``character_username``, ``score``, furniture flags) are
    ``Optional`` and stay ``None`` until a future generation phase
    runs. ``brief`` is permanent - the audit trail for why this reply
    was planned.

    Not frozen: the generation phase mutates these in place.
    """

    # -- Analysis phase (required) -------------------------------------------

    slot_id: str = Field(description="Unique within the thread, e.g. ``s01``.")
    parent_slot_id: Optional[str] = Field(
        default=None,
        description="``None`` for top-level slots; otherwise a sibling's ``slot_id``.",
    )
    depth: int = Field(ge=0, le=6, description="Reply depth (0 = top-level).")
    role: ReplyRole
    brief: str = Field(
        description="1-3 sentences. What this reply must accomplish."
        " Permanent audit trail; survives generation.",
    )

    anchor_id: Optional[str] = Field(
        default=None,
        description="``TechnicalAnchor.id`` this reply addresses (signal / encounter).",
    )
    domain_lens: Optional[int] = Field(
        default=None, ge=1, le=13,
        description="Table C domain index (1-13) for signal / encounter roles.",
    )
    encounter_id: Optional[str] = Field(
        default=None,
        description="``EncounterPlan.encounter_id`` for encounter turns.",
    )
    noise_tone: Optional[str] = Field(
        default=None,
        description="Tone label for noise slots (e.g. ``snark``, ``earnest``).",
    )
    noise_stance: Optional[NoiseStance] = Field(
        default=None,
        description="Stance label for noise slots, drawn from the-mod.md"
        " section 6 palette; ``misconception`` marks a trap question slot.",
    )

    carries_quote: bool = False
    carries_code: bool = False
    carries_link: bool = False

    # -- Generation phase (Optional / None for now) --------------------------

    content: Optional[str] = None
    character_username: Optional[str] = None
    score: Optional[int] = None
    ordering: Optional[int] = None
    time_label: Optional[str] = None
    controversial: bool = False
    edited: bool = False
    collapsed: bool = False
    deleted: bool = False
    removed: bool = False
    is_mod: bool = False
    is_op: bool = False
    flair: Optional[str] = None
    votes: list[Vote] = Field(
        default_factory=list,
        description="Per-persona votes on this comment. At most one vote"
        " per persona; filled by the reactor pass.",
    )


class Thread(BaseModel):
    """A planned r/wg21 thread for one WG21 paper.

    Analysis-phase fields are populated by Steps 0-7 in this package.
    Generation-phase fields (``submission_poster_id``,
    ``submission_votes``, ``generated_at``) stay ``None`` until a
    future generation phase runs.

    Not frozen: the generation phase mutates these in place.
    """

    # -- Step 0: paper identity (required) -----------------------------------

    document: str = Field(description="Full revisioned paper id, e.g. ``P2900R14``.")
    paper: str = Field(description="Paper id without revision, e.g. ``P2900``.")
    revision: int = Field(ge=0, description="Numeric revision (``0`` for ``R0``).")
    mailing_id: str = Field(
        default="",
        description="Mailing the paper arrived in (paperstore ``mailing_date``,"
        " e.g. ``2026-05``).",
    )
    title: str
    authors: list[str] = Field(
        default_factory=list,
        description="Author names as stored in paperstore.",
    )
    audience: str = Field(description="Comma-joined target groups from paperstore.")
    date: str = Field(description="Document date as stored in paperstore.")
    subreddit: Subreddit = "r/wg21"
    committee: Committee = Field(
        default="ewg",
        description="Group derived from the first target audience; drives"
        " audience badges.",
    )
    prior_revision: Optional[str] = Field(
        default=None,
        description="``Pnnnnn.Rk-1`` document if this is a re-revision (Case C).",
    )
    revision_case: RevisionCase = Field(
        default="A",
        description="``A`` new paper, ``B`` re-run of same revision, ``C`` new revision.",
    )

    # -- Step 1 (Smell Test) + Step 2 (Research) -----------------------------

    paper_type: PaperType
    technical_anchors: list[TechnicalAnchor] = Field(default_factory=list)
    tangent_magnets: list[str] = Field(
        default_factory=list,
        description="Topics likely to attract off-topic but plausible reply chains.",
    )
    hot_takes: list[str] = Field(
        default_factory=list,
        description="Inflammatory but plausible takes seeded from rhetorical markers.",
    )
    misconception_traps: list[str] = Field(
        default_factory=list,
        description="Predictable misreadings the thread should anticipate and dismantle.",
    )
    design_tensions: list[DesignTension] = Field(default_factory=list)
    research_summary: ResearchSummary

    # -- Step 3 (Calibrate) --------------------------------------------------

    heat: HeatTier
    interest: InterestTier
    target_comment_count: int = Field(
        ge=0, description="Planned total reply count (heat baseline * interest mult)."
    )
    encounter_count: int = Field(ge=0, description="How many encounters Step 6 runs.")
    signal_count: int = Field(ge=0, description="Planned signal reply count.")
    noise_count: int = Field(ge=0, description="Planned noise reply count.")

    # -- Step 4 (Submission) -------------------------------------------------

    submission_title: str
    submission_body: str
    submission_link: str = Field(description="Best canonical paper link.")
    submission_flair: str = Field(default="")

    # -- Steps 5-6 (Structure) -----------------------------------------------

    replies: list[Reply] = Field(default_factory=list)
    encounters: list[EncounterPlan] = Field(default_factory=list)

    # -- Generation phase (Optional / None for now) --------------------------

    submission_poster_id: Optional[str] = None
    submission_votes: Optional[list[Vote]] = Field(
        default=None,
        description="Per-persona votes on the submission itself."
        " ``None`` until the reactor pass runs.",
    )
    generated_at: Optional[datetime] = None


# -- Per-step LLM output classes ---------------------------------------------


class SmellTestOutput(BaseModel, frozen=True):
    """Step 1 (Smell Test) output."""

    paper_type: PaperType
    technical_anchors: list[TechnicalAnchor] = Field(default_factory=list)
    hot_takes: list[str] = Field(default_factory=list)
    tangent_magnets: list[str] = Field(default_factory=list)
    misconception_traps: list[str] = Field(default_factory=list)
    design_tensions: list[DesignTension] = Field(default_factory=list)


# Calibration arithmetic (the-mod.md 2.3/2.4/5b, mirrored by agora.md
# Step 3). The Step 3 validator holds the model's output to these
# tables; the backend's retry loop feeds violations back to the model.

HEAT_BASELINE: dict[str, tuple[int, int]] = {
    "cold": (5, 10),
    "warm": (15, 30),
    "hot": (30, 60),
    "thermonuclear": (60, 150),
}
INTEREST_MULTIPLIER: dict[str, float] = {
    "niche": 1.0,
    "relevant": 1.5,
    "magnetic": 2.0,
    "gravitational": 3.0,
}
TARGET_COMMENT_CAP = 90
"""One thread's generation ceiling; the scaled baseline clamps here."""
SIGNAL_RATIO_FLOOR: dict[str, float] = {
    "niche": 0.25,
    "relevant": 0.35,
    "magnetic": 0.45,
    "gravitational": 0.55,
}
MOD_ACTION_RESERVE: dict[str, tuple[int, int]] = {
    "cold": (0, 0),
    "warm": (0, 1),
    "hot": (1, 2),
    "thermonuclear": (3, 5),
}
ENCOUNTER_TURNS = (3, 5)
"""Turns per encounter chain (the-mod.md section 11: never more than 5)."""
ENCOUNTER_COUNT_MAX = 3


class CalibrationOutput(BaseModel, frozen=True):
    """Step 3 (Calibrate) output."""

    heat: HeatTier
    interest: InterestTier
    target_comment_count: int = Field(ge=0)
    encounter_count: int = Field(ge=0)
    signal_count: int = Field(ge=0)
    noise_count: int = Field(ge=0)
    rationale: str = Field(
        description="One paragraph: why this heat/interest combination, citing "
        "the paper-type floors and any author-gravity adjustments.",
    )

    @model_validator(mode="after")
    def _check_plan(self) -> "CalibrationOutput":
        """Report every table violation at once.

        The retry budget is 3; a draft that breaks several rules must
        see all of them in one round trip, not one per retry.
        """
        problems: list[str] = []

        base_low, base_high = HEAT_BASELINE[self.heat]
        multiplier = INTEREST_MULTIPLIER[self.interest]
        target_low = min(round(base_low * multiplier), TARGET_COMMENT_CAP)
        target_high = min(round(base_high * multiplier), TARGET_COMMENT_CAP)
        if not target_low <= self.target_comment_count <= target_high:
            problems.append(
                f"target_comment_count={self.target_comment_count} is outside "
                f"[{target_low}, {target_high}] for heat={self.heat} x "
                f"interest={self.interest} (baseline {base_low}-{base_high} x "
                f"{multiplier}, capped at {TARGET_COMMENT_CAP})"
            )

        if self.encounter_count > ENCOUNTER_COUNT_MAX:
            problems.append(
                f"encounter_count={self.encounter_count} exceeds the maximum "
                f"of {ENCOUNTER_COUNT_MAX}"
            )
        if self.heat == "cold" and self.encounter_count != 0:
            problems.append("cold threads have no encounters")
        if self.heat == "warm" and self.encounter_count > 1:
            problems.append("warm threads carry at most 1 encounter")
        if self.heat in ("hot", "thermonuclear") and self.encounter_count < 1:
            problems.append(f"{self.heat} threads need at least 1 encounter")

        # The signal/noise pool plus the encounter/mod reserve is the target.
        turns_low, turns_high = ENCOUNTER_TURNS
        mods_low, mods_high = MOD_ACTION_RESERVE[self.heat]
        reserve = self.target_comment_count - self.signal_count - self.noise_count
        reserve_low = self.encounter_count * turns_low + mods_low
        reserve_high = self.encounter_count * turns_high + mods_high
        if not reserve_low <= reserve <= reserve_high:
            problems.append(
                f"signal_count + noise_count leaves {reserve} of "
                f"target_comment_count={self.target_comment_count} for "
                f"encounters and mod actions, but {self.encounter_count} "
                f"encounter(s) at {turns_low}-{turns_high} turns plus "
                f"{mods_low}-{mods_high} mod action(s) for heat={self.heat} "
                f"needs {reserve_low}-{reserve_high}"
            )

        pool = self.signal_count + self.noise_count
        floor = math.ceil(SIGNAL_RATIO_FLOOR[self.interest] * pool)
        if pool and self.signal_count < floor:
            problems.append(
                f"signal_count={self.signal_count} is below the "
                f"interest={self.interest} minimum signal share "
                f"({SIGNAL_RATIO_FLOOR[self.interest]:.0%} of the "
                f"{pool}-slot signal+noise pool = {floor})"
            )

        if problems:
            raise ValueError("; ".join(problems))
        return self


class SubmissionOutput(BaseModel, frozen=True):
    """Step 4 (Submission) output."""

    submission_title: str
    submission_body: str
    submission_link: str
    submission_flair: str = ""
    revision_case: RevisionCase = "A"


class SkeletonReply(BaseModel, frozen=True):
    """A planned reply slot as emitted by Step 5 (Skeleton).

    Only the analysis-phase fields of :class:`Reply` — the generation
    phase fills the rest, so asking the model to echo them as nulls
    just burns output tokens (a 90-slot thread overflows the output
    budget). ``_extract_skeleton`` widens these into full ``Reply``
    objects.
    """

    slot_id: str = Field(description="Unique within the thread, e.g. ``s01``.")
    parent_slot_id: Optional[str] = Field(
        default=None,
        description="``None`` for top-level slots; otherwise a sibling's ``slot_id``.",
    )
    depth: int = Field(ge=0, le=6, description="Reply depth (0 = top-level).")
    role: ReplyRole
    brief: str = Field(
        description="1-3 sentences. What this reply must accomplish."
        " Permanent audit trail; survives generation.",
    )

    anchor_id: Optional[str] = Field(
        default=None,
        description="``TechnicalAnchor.id`` this reply addresses (signal / encounter).",
    )
    domain_lens: Optional[int] = Field(
        default=None, ge=1, le=13,
        description="Table C domain index (1-13) for signal / encounter roles.",
    )
    encounter_id: Optional[str] = Field(
        default=None,
        description="``EncounterPlan.encounter_id`` for encounter turns.",
    )
    noise_tone: Optional[str] = Field(
        default=None,
        description="Tone label for noise slots (e.g. ``snark``, ``earnest``).",
    )
    noise_stance: Optional[NoiseStance] = Field(
        default=None,
        description="Stance label for noise slots, drawn from the-mod.md"
        " section 6 palette; ``misconception`` marks a trap question slot.",
    )

    carries_quote: bool = False
    carries_code: bool = False
    carries_link: bool = False


class SkeletonOutput(BaseModel, frozen=True):
    """Step 5 (Skeleton) output.

    Carries the planned replies plus pre-allocated encounter slot
    pointers for Step 6 to fill in.
    """

    replies: list[SkeletonReply] = Field(default_factory=list)
    encounter_slot_groups: list[list[str]] = Field(
        default_factory=list,
        description="One list of ``slot_id`` strings per allocated encounter, "
        "in turn order. Length must equal ``encounter_count`` from Step 3.",
    )


class EncountersOutput(BaseModel, frozen=True):
    """Step 6 (Encounters) output."""

    encounters: list[EncounterPlan] = Field(default_factory=list)


class CommentOutput(BaseModel, frozen=True):
    """Step 9 (Voice) per-slot output: one comment body."""

    content: str = Field(
        min_length=1,
        description="The comment body in Reddit-flavored markdown,"
        " written in the assigned persona's voice.",
    )


# -- Pipeline state ----------------------------------------------------------


class PipelineState(BaseModel):
    """Mutable accumulator threaded through every agora pipeline step.

    Steps read by attribute name (matching their ``Reads:`` metadata in
    ``agora.md``) and write by attribute name (matching ``Writes:``).
    The runner enforces nothing about field types here; Pydantic
    validates per-step LLM outputs separately.
    """

    # -- Step 0 (Load): paper identity + paperstore extract data --------------

    paper_id: str = ""
    paper_source: Optional[str] = None
    paper_title: str = ""
    paper_authors: list[str] = Field(default_factory=list)
    paper_audience: str = ""
    paper_date: str = ""
    paper_url: str = ""
    paper_number: str = ""
    paper_revision: int = 0
    mailing_id: str = ""
    subreddit: Optional[Subreddit] = None
    committee: Optional[Committee] = None
    prior_revision: Optional[str] = None
    revision_case: RevisionCase = "A"

    # Field names retain "dissect_" prefix for backward compatibility with
    # pipeline.py and serialized state; data comes from paperstore extract tables.
    dissect_claims: Optional[list[dict]] = None
    dissect_evidence: Optional[list[dict]] = None
    dissect_markers: Optional[list[dict]] = None
    dissect_caput_causae: Optional[str] = None
    dissect_citation_audit: Optional[list[dict]] = None
    dissect_external_citations: Optional[list[dict]] = None

    # -- Step 1 (Smell Test) -------------------------------------------------

    paper_type: Optional[PaperType] = None
    technical_anchors: Optional[list[TechnicalAnchor]] = None
    hot_takes: Optional[list[str]] = None
    tangent_magnets: Optional[list[str]] = None
    misconception_traps: Optional[list[str]] = None
    design_tensions: Optional[list[DesignTension]] = None

    # -- Step 2 (Research) ---------------------------------------------------

    research_summary: Optional[ResearchSummary] = None

    # -- Step 3 (Calibrate) --------------------------------------------------

    heat: Optional[HeatTier] = None
    interest: Optional[InterestTier] = None
    target_comment_count: Optional[int] = None
    encounter_count: Optional[int] = None
    signal_count: Optional[int] = None
    noise_count: Optional[int] = None

    # -- Step 4 (Submission) -------------------------------------------------

    submission_title: Optional[str] = None
    submission_body: Optional[str] = None
    submission_link: Optional[str] = None
    submission_flair: Optional[str] = None

    # -- Step 5 (Skeleton) ---------------------------------------------------

    replies: Optional[list[Reply]] = None
    encounter_slot_groups: Optional[list[list[str]]] = None

    # -- Step 6 (Encounters) -------------------------------------------------

    encounters: Optional[list[EncounterPlan]] = None

    # -- Step 7 (Serialize) --------------------------------------------------

    thread: Optional[Thread] = None

    # Steps 8-10 (Cast, Voice, Reactor) add no state fields: they
    # mutate ``thread`` in place, filling the generation-phase fields
    # on ``Thread`` and ``Reply``.

    # -- Step 11 (Emit) --------------------------------------------------------

    artifact_path: Optional[str] = None
    qa_findings: Optional[list[str]] = None
