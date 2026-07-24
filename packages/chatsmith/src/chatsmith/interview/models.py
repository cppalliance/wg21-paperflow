#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Session data model.

``InterviewSession`` holds the verbatim transcript plus a lightweight
``InterviewState`` summary for resume, and an opaque ``owner`` for per-user
scoping (unset locally). Every type round-trips through plain dicts, so any store
(JSON, SQLite, or a Django JSONField) shares the same serialized bytes.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

ROLE_ASSISTANT = "assistant"
ROLE_SUBJECT = "subject"

# Bump when the persisted session shape changes; `from_dict` stays tolerant.
SCHEMA_VERSION = 2


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def slugify(name: str) -> str:
    """Kebab-case a subject name, e.g. 'Jane Doe' -> 'jane-doe'."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return cleaned or "subject"


@dataclass
class Turn:
    role: str  # ROLE_ASSISTANT | ROLE_SUBJECT
    text: str
    ts: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Turn:
        return cls(role=d["role"], text=d["text"], ts=d.get("ts") or _now_iso())


@dataclass
class InterviewState:
    """Lightweight, resumable summary. Not the fidelity-critical persona state."""

    phase: str = "greeting"  # greeting | elicit | walk | close
    turn_count: int = 0
    interests: list[str] = field(default_factory=list)
    last_thread: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> InterviewState:
        return cls(
            phase=d.get("phase", "greeting"),
            turn_count=int(d.get("turn_count", 0)),
            interests=list(d.get("interests", [])),
            last_thread=d.get("last_thread", "none"),
        )


@dataclass
class InterviewSession:
    session_id: str
    subject: str = ""
    slug: str = ""
    owner: str | None = None  # opaque principal; None = local single-user (unscoped)
    turns: list[Turn] = field(default_factory=list)
    state: InterviewState = field(default_factory=InterviewState)
    sessions: list[str] = field(default_factory=list)  # ISO dates the session was written
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def add_turn(self, role: str, text: str) -> Turn:
        turn = Turn(role=role, text=text)
        self.turns.append(turn)
        self.updated_at = turn.ts
        return turn

    def touch_written(self) -> None:
        """Record today's date once per calendar day the transcript is written."""
        today = datetime.now(UTC).date().isoformat()
        if today not in self.sessions:
            self.sessions.append(today)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "session_id": self.session_id,
            "subject": self.subject,
            "slug": self.slug,
            "owner": self.owner,
            "turns": [t.to_dict() for t in self.turns],
            "state": self.state.to_dict(),
            "sessions": list(self.sessions),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> InterviewSession:
        return cls(
            session_id=d["session_id"],
            subject=d.get("subject", ""),
            slug=d.get("slug", ""),
            owner=d.get("owner"),
            turns=[Turn.from_dict(t) for t in d.get("turns", [])],
            state=InterviewState.from_dict(d.get("state", {})),
            sessions=list(d.get("sessions", [])),
            created_at=d.get("created_at") or _now_iso(),
            updated_at=d.get("updated_at") or _now_iso(),
        )

    def transcript_markdown(self) -> str:
        """Render the durable transcript body: pure Q&A with timestamps."""
        interests = ", ".join(self.state.interests)
        header = [
            "---",
            f"subject: {self.subject or 'Unknown'}",
            f"slug: {self.slug or slugify(self.subject)}",
            f"interests: [{interests}]",
            f"last_thread: {self.state.last_thread}",
            f"sessions: [{', '.join(self.sessions)}]",
            "---",
            "",
            f"# Interview: {self.subject or 'Unknown'}",
            "",
        ]
        body: list[str] = []
        pair_index = 0
        pending_question: str | None = None
        pending_ts: str | None = None
        for turn in self.turns:
            if turn.role == ROLE_ASSISTANT:
                pending_question = turn.text
                pending_ts = turn.ts
                continue
            pair_index += 1
            body.append(f"### Turn {pair_index} ({turn.ts})")
            if pending_question is not None:
                body.append(f"- **Q**: {pending_question}")
                pending_question = None
                pending_ts = None
            body.append(f"- **A**: {turn.text}")
            body.append("")
        # Interviews usually end on the interviewer's question with no subject reply;
        # flush that trailing question (a Q with no A) so it is never dropped.
        if pending_question is not None:
            pair_index += 1
            body.append(f"### Turn {pair_index} ({pending_ts})")
            body.append(f"- **Q**: {pending_question}")
            body.append("")
        return "\n".join(header + body).rstrip() + "\n"
