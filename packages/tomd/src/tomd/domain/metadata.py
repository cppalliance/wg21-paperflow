"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from tomd.domain.front_matter import FRONT_MATTER_ORDER, is_blank_value
from tomd.domain.mailing import MailingRecord

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")

_KNOWN_KEYS = frozenset({*FRONT_MATTER_ORDER, "reply_to"})

# A title that opens with one of these labels states the paper's intent.
_INTENT_TITLE_PREFIXES = (("Info:", "info"), ("Ask:", "ask"))


def normalize_title(title: str) -> str:
    """Return ``title`` on one line: ``A :: B`` becomes ``A::B`` and whitespace runs collapse."""
    title = title.replace("\r", " ").replace("\n", " ")
    title = re.sub(r"\s*::\s*", "::", title)
    return re.sub(r"\s{2,}", " ", title).strip()


def intent_from_title(title: str) -> str:
    """Return the intent an ``Info:`` or ``Ask:`` title prefix states, or ``""``."""
    stripped = title.strip()
    for prefix, intent in _INTENT_TITLE_PREFIXES:
        if stripped.startswith(prefix):
            return intent
    return ""


@dataclass(frozen=True)
class PaperMetadata:
    """Structured metadata for a WG21 paper."""

    title: str = ""
    document: str = ""
    date: str = ""
    intent: str = ""
    audience: list[str] | str = ""
    reply_to: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "PaperMetadata":
        """Construct PaperMetadata from front-matter keys; a scalar ``reply-to`` becomes a one-item list."""
        if not data:
            return cls()
        reply_to = data.get("reply-to", data.get("reply_to", []))
        return cls(
            title=data.get("title", ""),
            document=data.get("document", ""),
            date=data.get("date", ""),
            intent=data.get("intent", ""),
            audience=data.get("audience", ""),
            reply_to=[reply_to] if isinstance(reply_to, str) else reply_to,
            extra={k: v for k, v in data.items() if k not in _KNOWN_KEYS},
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict in ``FRONT_MATTER_ORDER``, extras last; blank values are omitted."""
        d = {
            "title": self.title,
            "document": self.document,
            "date": self.date,
            "intent": self.intent,
            "audience": self.audience,
            "reply-to": self.reply_to,
        }
        d.update((k, v) for k, v in self.extra.items() if k not in d)
        return {k: v for k, v in d.items() if not is_blank_value(v)}

    def fill_from_mailing(self, mailing: MailingRecord) -> "PaperMetadata":
        """Return a copy with blank fields filled from ``mailing``.

        ``document`` is the exception: a non-blank mailing ``paper_id`` always replaces
        it, because SD-7 forbids D-numbers in published mailings. A ``reply_to`` with no
        email address counts as blank, because the mailing authors may carry emails.
        """
        if is_blank_value(self.date) and not is_blank_value(mailing.document_date):
            logger.debug(
                "Date fallback from mailing (document_date=%r): source had no date",
                mailing.document_date,
            )
        keep_reply_to = is_blank_value(mailing.authors) or any(EMAIL_RE.search(e) for e in self.reply_to)
        return replace(
            self,
            title=mailing.title if is_blank_value(self.title) else self.title,
            document=self.document if is_blank_value(mailing.paper_id) else mailing.paper_id,
            date=mailing.document_date if is_blank_value(self.date) else self.date,
            audience=mailing.audience if is_blank_value(self.audience) else self.audience,
            reply_to=self.reply_to if keep_reply_to else list(mailing.authors),
        )
