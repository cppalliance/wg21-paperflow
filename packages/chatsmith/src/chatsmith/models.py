#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Pydantic output schemas for the LLM steps.

These are the sole schema authority for LLM output, following the wg21-paperflow
convention: every ``agent.run`` call declares ``output_type=<PydanticModel>`` and
never ``output_type=str``. Frozen models; free-form prose is carried in a field.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class NormalizeOutput(BaseModel, frozen=True):
    """Post-STT normalization result for a single utterance."""

    text: str = Field(
        description="The corrected transcription of the latest utterance only, "
        "with recognition errors fixed and meaning preserved."
    )


class TurnReply(BaseModel, frozen=True):
    """One spoken interviewer reply plus advisory knowledge-capture signals."""

    text: str = Field(
        description="The interviewer's spoken reply: one short, warm turn, at most "
        "a reflection and a single open question."
    )
    topics: tuple[str, ...] = Field(
        default=(),
        description="Salient topics or interests the subject surfaced this turn "
        "(0-3 short phrases). Advisory; used for resume and knowledge capture.",
    )
