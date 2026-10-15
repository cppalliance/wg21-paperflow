"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

import logging
import re
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
    audience: list[str] | str = field(default_factory=list)
    reply_to: list[str] | str = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PaperMetadata":
        """Construct PaperMetadata from a dictionary of front matter keys."""
        if not data:
            return cls()
        return cls(
            title=str(data.get("title") or ""),
            document=str(data.get("document") or ""),
            date=str(data.get("date") or ""),
            intent=str(data.get("intent") or ""),
            audience=_list_or_str(data.get("audience")),
            reply_to=_list_or_str(data.get("reply-to", data.get("reply_to"))),
            extra={k: v for k, v in data.items() if k not in _KNOWN_KEYS},
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict in ``FRONT_MATTER_ORDER``, extras last; blank values are omitted."""
        d = {key: getattr(self, key.replace("-", "_")) for key in FRONT_MATTER_ORDER}
        d.update((k, v) for k, v in self.extra.items() if k not in d)
        return {k: v for k, v in d.items() if not is_blank_value(v)}

    def with_mailing_fallback(self, mailing: MailingRecord) -> "PaperMetadata":
        """Return a copy completed from ``mailing``.

        Mailing values fill only blank fields (``is_blank_value``), except
        ``document``: SD-7 forbids D-numbers in published mailings, so the mailing
        ``paper_id`` replaces whatever document number the source has. A ``reply_to``
        of bare names (no email address) counts as blank. Blank mailing values never
        fill anything.
        """
        date = _present_or(self.date, mailing.document_date)
        if date != self.date:
            logger.debug("Date fallback from mailing (document_date=%r): source had no date", date)

        reply_to = self.reply_to
        entries = [reply_to] if isinstance(reply_to, str) else reply_to
        if not any(EMAIL_RE.search(entry) for entry in entries) and not is_blank_value(mailing.authors):
            reply_to = list(mailing.authors)

        return replace(
            self,
            title=_present_or(self.title, mailing.title),
            document=_present_or(mailing.paper_id, self.document),
            date=date,
            audience=_present_or(self.audience, mailing.audience),
            reply_to=reply_to,
        )


def _present_or[T](value: T, fallback: T) -> T:
    return fallback if is_blank_value(value) and not is_blank_value(fallback) else value


def _list_or_str(value: Any) -> list[str] | str:
    if value is None:
        return []
    return value if isinstance(value, (list, str)) else str(value)
