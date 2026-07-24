#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

from __future__ import annotations

from chatsmith.interview.models import ROLE_ASSISTANT, ROLE_SUBJECT, InterviewSession


def test_transcript_pairs_question_with_answer() -> None:
    session = InterviewSession(session_id="s1", subject="Ada")
    session.add_turn(ROLE_ASSISTANT, "What are you working on?")
    session.add_turn(ROLE_SUBJECT, "Analytical engines.")

    md = session.transcript_markdown()
    assert "### Turn 1" in md
    assert "- **Q**: What are you working on?" in md
    assert "- **A**: Analytical engines." in md


def test_transcript_keeps_trailing_unanswered_question() -> None:
    # Interviews usually end on the interviewer's question with the subject not
    # replying; that final question must survive into the durable transcript
    # instead of being dropped with the unflushed pending question.
    session = InterviewSession(session_id="s1", subject="Ada")
    session.add_turn(ROLE_ASSISTANT, "Opening question?")
    session.add_turn(ROLE_SUBJECT, "An answer.")
    session.add_turn(ROLE_ASSISTANT, "The final unanswered question?")

    md = session.transcript_markdown()
    assert "The final unanswered question?" in md
    # It renders as its own Q-only turn -- no fabricated answer.
    assert md.count("- **Q**:") == 2
    assert md.count("- **A**:") == 1
    assert "### Turn 2" in md


def test_session_round_trips_through_dict() -> None:
    # The core "any store shares the same bytes" invariant: to_dict -> from_dict
    # must reproduce the session, including nested turns and resume state.
    session = InterviewSession(session_id="s1", subject="Ada", owner="user-42")
    session.add_turn(ROLE_ASSISTANT, "Q?")
    session.add_turn(ROLE_SUBJECT, "A.")
    session.state.phase = "walk"
    session.state.turn_count = 2
    session.state.interests = ["engines"]
    session.touch_written()

    restored = InterviewSession.from_dict(session.to_dict())

    assert restored.session_id == "s1"
    assert restored.subject == "Ada"
    assert restored.owner == "user-42"
    assert [(t.role, t.text) for t in restored.turns] == [
        (ROLE_ASSISTANT, "Q?"),
        (ROLE_SUBJECT, "A."),
    ]
    assert restored.state.phase == "walk"
    assert restored.state.turn_count == 2
    assert restored.state.interests == ["engines"]
    assert restored.sessions == session.sessions


def test_from_dict_tolerates_missing_keys_and_absent_version() -> None:
    # A minimal, versionless payload (e.g. from an older store) must load with
    # safe defaults instead of raising.
    restored = InterviewSession.from_dict({"session_id": "only-id"})
    assert restored.session_id == "only-id"
    assert restored.subject == ""
    assert restored.owner is None
    assert restored.turns == []
    assert restored.state.phase == "greeting"
    assert restored.sessions == []
