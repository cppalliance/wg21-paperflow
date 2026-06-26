#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Stage 2: section detection from markdown headings."""

from __future__ import annotations

from pipeline.heading_classifiers import classify_routing_section
from pipeline.markdown import front_matter_end_index
from pipeline.markdown_patterns import HEADING_RE
from pipeline.paper_routing.split import RawSentence
from pipeline.paper_routing.types import SectionType


def line_section_map(paper_md: str) -> list[SectionType]:
    """Return one section type per source line (carry-forward from headings)."""
    lines = paper_md.splitlines()
    if not lines:
        return []

    fm_end = front_matter_end_index(lines)
    result: list[SectionType] = []
    current = SectionType.PREAMBLE

    for i, line in enumerate(lines):
        if i < fm_end:
            result.append(SectionType.PREAMBLE)
            continue

        m = HEADING_RE.match(line)
        if m:
            current = classify_routing_section(m.group(2).strip())
        result.append(current)

    return result


def section_for_sentence(
    raw: RawSentence,
    line_sections: list[SectionType],
) -> SectionType:
    """Look up section type for a sentence by its start line."""
    if not line_sections:
        return SectionType.PREAMBLE
    idx = min(raw.start_line, len(line_sections) - 1)
    return line_sections[idx]
