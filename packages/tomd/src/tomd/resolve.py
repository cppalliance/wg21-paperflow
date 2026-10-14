#
# Copyright (c) 2026 Sean Parsons (seanpatrick2013@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Resolve a paper's parsed metadata against its mailing-index row.

Whatever the converter could not extract from the source is filled in from the
mailing row; fields the source already carries win. ``document`` is the
exception: ``PaperDocument.paper_id`` is the mailing id, and it always becomes
``PaperMetadata.document``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from tomd.domain.metadata import PaperMetadata
from tomd.lib.metadata_yaml.format import is_blank_value, sanitize_metadata
from tomd.lib.shared import EMAIL_RE

__all__ = ["MailingRecord", "resolve_metadata"]

logger = logging.getLogger(__name__)

# MailingRecord field -> front-matter key. When two fields feed one key, the first
# non-empty one wins: `subgroup` is the mailing-row name, `target_group` the
# SqliteBackend row name.
_FALLBACK_KEY_MAP = {
    "title": "title",
    "paper_id": "document",
    "document_date": "date",
    "subgroup": "audience",
    "target_group": "audience",
    "authors": "reply-to",
}

# SD-7 forbids D-numbers (draft circulation) in published mailings, so the
# mailing paper_id (P/N-number) replaces whatever document number the source has.
_OVERRIDE_KEYS = frozenset({"document"})


@dataclass(frozen=True)
class MailingRecord:
    """Mailing-index row fields that feed front-matter fallback."""

    paper_id: str = ""
    title: str = ""
    authors: tuple[str, ...] = ()
    target_group: str = ""
    subgroup: str = ""
    document_date: str = ""

    @classmethod
    def from_meta(cls, meta: Mapping[str, Any] | None) -> MailingRecord | None:
        """Build a record from the ``convert_paper_full`` ``meta`` dict, or ``None`` if it is empty.

        Keys other than the record's fields (``intent``, ``url``) are ignored.
        ``None`` values read as empty; a bare ``authors`` string is one name.
        """
        if not meta:
            return None
        return cls(
            paper_id=_text(meta.get("paper_id")),
            title=_text(meta.get("title")),
            authors=_names(meta.get("authors")),
            target_group=_text(meta.get("target_group")),
            subgroup=_text(meta.get("subgroup")),
            document_date=_text(meta.get("document_date")),
        )


def _text(value: Any) -> str:
    return str(value) if value else ""


def _names(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    return tuple(str(name) for name in value)


def resolve_metadata(parsed: PaperMetadata, mailing: MailingRecord | None) -> PaperMetadata:
    """Return ``parsed`` sanitized and completed from ``mailing``.

    Mailing values only fill fields the source lacks, except ``document``, which
    the mailing ``paper_id`` overrides. A blank field (``is_blank_value``) counts as
    missing, as does a ``reply-to`` of bare names (no email address), so mailing data
    replaces it. Blank mailing values never fill anything.
    """
    resolved = sanitize_metadata(parsed.to_dict())
    if mailing is not None:
        _fill_from_mailing(resolved, mailing)
    return PaperMetadata.from_dict(resolved)


def _fill_from_mailing(metadata: dict[str, Any], mailing: MailingRecord) -> None:
    present = {key for key, value in metadata.items() if not is_blank_value(value)}
    reply_to = metadata.get("reply-to")
    if reply_to and not any(EMAIL_RE.search(entry) for entry in reply_to):
        present.discard("reply-to")

    filled: set[str] = set()
    for field_name, key in _FALLBACK_KEY_MAP.items():
        if key in filled or (key in present and key not in _OVERRIDE_KEYS):
            continue
        value = getattr(mailing, field_name)
        if is_blank_value(value):
            continue
        if key == "date":
            logger.debug(
                "Date fallback from mailing (%s=%r): source had no date",
                field_name,
                value,
            )
        metadata[key] = list(value) if isinstance(value, tuple) else value
        filled.add(key)
