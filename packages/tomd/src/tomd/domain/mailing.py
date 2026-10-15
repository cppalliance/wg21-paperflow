"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from tomd.domain.front_matter import is_blank_value


@dataclass(frozen=True)
class MailingRecord:
    """Mailing-index row fields that feed front-matter fallback."""

    paper_id: str = ""
    title: str = ""
    authors: tuple[str, ...] = ()
    audience: str = ""
    document_date: str = ""

    @classmethod
    def from_meta(cls, meta: Mapping[str, Any] | None) -> "MailingRecord":
        """Build a record from the ``convert_paper_full`` ``meta`` dict.

        ``None`` values read as empty and a bare ``authors`` string is one name.
        ``audience`` is the first non-blank of ``subgroup`` (mailing-row name) and
        ``target_group`` (SqliteBackend row name). Other keys (``intent``, ``url``)
        are ignored.
        """
        meta = meta or {}
        authors = meta.get("authors") or ()
        subgroup = meta.get("subgroup")
        audience = meta.get("target_group") if is_blank_value(subgroup) else subgroup
        return cls(
            paper_id=str(meta.get("paper_id") or ""),
            title=str(meta.get("title") or ""),
            authors=(authors,) if isinstance(authors, str) else tuple(str(name) for name in authors),
            audience=str(audience or ""),
            document_date=str(meta.get("document_date") or ""),
        )
