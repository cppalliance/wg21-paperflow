"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

import logging
from dataclasses import dataclass, field, replace
from typing import Any

from tomd.domain.mailing import MailingRecord
from tomd.lib.metadata_yaml.format import FRONT_MATTER_ORDER as FRONT_MATTER_ORDER, is_blank_value
from tomd.lib.shared import EMAIL_RE

logger = logging.getLogger(__name__)


@dataclass
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

        known = {"title", "document", "date", "intent", "audience", "reply-to", "reply_to"}
        extra = {k: v for k, v in data.items() if k not in known}

        audience_val = data.get("audience")
        if audience_val is None:
            audience: list[str] | str = []
        elif isinstance(audience_val, (list, str)):
            audience = audience_val
        else:
            audience = str(audience_val)

        reply_to_val = data.get("reply-to", data.get("reply_to"))
        if reply_to_val is None:
            reply_to: list[str] | str = []
        elif isinstance(reply_to_val, (list, str)):
            reply_to = reply_to_val
        else:
            reply_to = str(reply_to_val)

        return cls(
            title=str(data.get("title") or ""),
            document=str(data.get("document") or ""),
            date=str(data.get("date") or ""),
            intent=str(data.get("intent") or ""),
            audience=audience,
            reply_to=reply_to,
            extra=extra,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize metadata into a dict ordered by canonical FRONT_MATTER_ORDER."""
        d: dict[str, Any] = {}
        for key in FRONT_MATTER_ORDER:
            if key == "title" and self.title:
                d["title"] = self.title
            elif key == "document" and self.document:
                d["document"] = self.document
            elif key == "date" and self.date:
                d["date"] = self.date
            elif key == "intent" and self.intent:
                d["intent"] = self.intent
            elif key == "audience" and self.audience:
                d["audience"] = self.audience
            elif key == "reply-to" and self.reply_to:
                d["reply-to"] = self.reply_to

        for k, v in self.extra.items():
            if k not in d:
                d[k] = v

        return d

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
