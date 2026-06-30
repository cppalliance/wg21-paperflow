#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

"""Non-prose blanking for paper markdown.

Blanks YAML frontmatter, revision history, references, and
acknowledgments with empty lines in one pass through the document.
Line numbers are preserved (lines are blanked, not removed) so
downstream references stay valid.

Package-private. Called by the pipeline before analytical processing.
"""

from __future__ import annotations

import re

from pipeline.heading_classifiers import (
    HeadingKind,
    is_acknowledgment_heading,
    is_reference_heading,
    is_revision_heading,
)
from pipeline.markdown import front_matter_end_index

_PAPER_OVERRIDES: dict[str, set[str]] = {
    "P0260": {"old revision history"},
}

_STEM_RE = re.compile(r"[PN]\d+", re.IGNORECASE)


def _get_overrides(paper_id: str | None) -> set[str]:
    if not paper_id:
        return set()
    m = _STEM_RE.match(paper_id)
    if not m:
        return set()
    return _PAPER_OVERRIDES.get(m.group(0).upper(), set())


def _blank_section(
    lines: list[str],
    classifier,
) -> None:
    """Blank all lines belonging to sections identified by *classifier*.

    Multi-pass: after exiting a block on a NO heading, scanning continues
    from PRE back to IN, so split or interrupted sections are all caught.
    """
    in_section = False
    for i in range(len(lines)):
        kind = classifier(lines[i])
        if in_section:
            if kind is HeadingKind.NO:
                in_section = False
            else:
                lines[i] = "\n"
        elif kind is HeadingKind.YES:
            lines[i] = "\n"
            in_section = True


def blank_paper(source: str, paper_id: str | None = None) -> str:
    """Blank frontmatter, revision history, references, and acknowledgments.

    YAML frontmatter is always blanked. Non-prose sections (revision
    history, references, acknowledgments) are detected via tri-bool
    heading classifiers and blanked in independent passes so ordering
    within the document does not matter.
    """
    lines = source.splitlines(keepends=True)
    overrides = _get_overrides(paper_id)

    # Pass 1: blank YAML frontmatter
    fm_end = front_matter_end_index(lines)
    for i in range(fm_end):
        lines[i] = "\n"

    # Pass 2: blank revision history (with paper-specific overrides)
    _blank_section(lines, lambda line: is_revision_heading(line, overrides))

    # Pass 3: blank references
    _blank_section(lines, is_reference_heading)

    # Pass 4: blank acknowledgments
    _blank_section(lines, is_acknowledgment_heading)

    return "".join(lines)
