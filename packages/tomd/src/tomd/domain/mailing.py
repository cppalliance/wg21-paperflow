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

        ``audience`` is ``subgroup`` unless that is blank, then ``target_group``.
        """
        if not meta:
            return cls()
        subgroup = meta.get("subgroup", "")
        return cls(
            paper_id=meta.get("paper_id", ""),
            title=meta.get("title", ""),
            authors=tuple(meta.get("authors", ())),
            audience=meta.get("target_group", "") if is_blank_value(subgroup) else subgroup,
            document_date=meta.get("document_date", ""),
        )
