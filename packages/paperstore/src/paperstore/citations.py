#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Pure-Python WG21 paper-id citation extractor.

Deterministic, no LLM, no network. The regex pair matches the two paper-id
shapes WG21 uses:

* ``P####R#`` and ``D####R#`` (proposals; D is a draft revision)
* ``N####``   (committee documents; unrevisioned)

Markdown ``[text](URL)`` link targets are stripped before matching so a
paper-id that appears only inside a URL doesn't double-count.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from itertools import chain


@dataclass(frozen=True)
class Citation:
    """A WG21 paper-id cited in a source document, with occurrence count."""

    paper_id: str
    count: int


_CITATION_PD_RE = re.compile(r"\b([PD]\d{4,5}R\d{1,2})\b", re.IGNORECASE)
_CITATION_N_RE = re.compile(r"\b(N\d{4,5})\b", re.IGNORECASE)
_LINK_URL_RE = re.compile(r"\]\([^)]*\)")


def extract_citations(paper_md: str) -> list[Citation]:
    """Return citations found in ``paper_md`` sorted by count (desc).

    Counts are case-insensitive but paper IDs are normalized to upper-case
    in the returned :class:`Citation` rows.
    """
    stripped = _LINK_URL_RE.sub("]", paper_md)
    counts = Counter(
        m.group(1).upper()
        for m in chain(
            _CITATION_PD_RE.finditer(stripped),
            _CITATION_N_RE.finditer(stripped),
        )
    )
    refs = [Citation(paper_id=pid, count=c) for pid, c in counts.items()]
    refs.sort(key=lambda r: r.count, reverse=True)
    return refs
