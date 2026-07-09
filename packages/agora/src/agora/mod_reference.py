#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Scoped access to ``the-mod.md``, the creative authority document.

The step instructions in ``agora.md`` cite the-mod.md rules ("apply
sections 2.1-2.4", "cover the Table C domain lenses"), but the model
only obeys rules it can read. This module slices the-mod.md into the
excerpts each step needs so the citing step's user message carries the
actual rule text without spending context budget on the whole document.

``the-mod.md`` ships as package data alongside ``agora.md``. Every
accessor fails loudly when its heading or marker is missing, so a
restructure of the-mod.md breaks the test suite instead of silently
dropping rules from the prompts.
"""

from __future__ import annotations

import functools
import importlib.resources
import re

_HEADING_RE = re.compile(r"^(#{2,4})\s+(?P<title>.+?)\s*$")


@functools.cache
def _document() -> str:
    resource = importlib.resources.files("agora").joinpath("the-mod.md")
    return resource.read_text(encoding="utf-8")


def _section(title: str) -> str:
    """Return heading plus body for the heading whose text is ``title``.

    The slice runs from the heading line to the line before the next
    heading of the same or higher level, so ``### 2. The Heat Check``
    keeps its ``**2.1 ...**`` bold blocks but stops at ``### 3.``.
    """
    lines = _document().splitlines()
    start: int | None = None
    level = 0
    for index, line in enumerate(lines):
        match = _HEADING_RE.match(line)
        if not match:
            continue
        if start is None:
            if match.group("title") == title:
                start = index
                level = len(match.group(1))
        elif len(match.group(1)) <= level:
            return "\n".join(lines[start:index]).strip()
    if start is None:
        raise KeyError(f"the-mod.md has no heading titled {title!r}.")
    return "\n".join(lines[start:]).strip()


def _block(section_title: str, start_marker: str, end_marker: str) -> str:
    """Return the ``start_marker``..``end_marker`` slice of a section body."""
    body = _section(section_title)
    try:
        start = body.index(start_marker)
        end = body.index(end_marker, start)
    except ValueError as exc:
        raise KeyError(
            f"the-mod.md section {section_title!r} has no"
            f" {start_marker!r}..{end_marker!r} block."
        ) from exc
    return body[start:end].strip()


def _bundle(*excerpts: str) -> str:
    return "\n\n---\n\n".join(excerpts)


def _paper_type_rules() -> str:
    return _block("2. The Heat Check", "**2.1b Paper type.**", "**2.1c")


def _process_document_rules() -> str:
    return _block(
        "2. The Heat Check",
        "**2.1d Process document classification.**",
        "**2.1e",
    )


def _anchor_priority_rules() -> str:
    return _block("1. Read the Paper", "- **1.4d Anchor priority routing.**", "- **1.4e")


def _table_c_domains() -> str:
    return _block("7. Long Path - Signal", "**Table C: Domain**", "**Table D")


def smell_test_excerpts() -> str:
    """Rules Step 1 (Smell Test) is asked to apply.

    Section 1 carries the two-pass read and the 1.3/1.4 anchor filters
    (including 1.4d anchor priority routing). The 2.1b and 2.1d blocks
    carry the paper-type taxonomy and the process-document special
    path, which Step 1 needs because it classifies the paper.
    """
    return _bundle(
        _section("1. Read the Paper"),
        _paper_type_rules(),
        _process_document_rules(),
    )


def calibrate_excerpts() -> str:
    """Rules Step 3 (Calibrate) is asked to apply.

    Section 2 carries the heat/interest tiers, floors, and multipliers
    (2.1-2.4). Section 4 carries the comment-count formula and the
    encounter scaling by interest.
    """
    return _bundle(
        _section("2. The Heat Check"),
        _section("4. Thread Architecture"),
    )


def submission_excerpts() -> str:
    """Rules Step 4 (Submission) is asked to apply: section 3."""
    return _section("3. The Submission Post")


def skeleton_excerpts() -> str:
    """Rules Step 5 (Skeleton) is asked to apply.

    Section 4 carries nesting/depth structure, section 5b the mod
    action scaling, section 6 the noise palette, Table C the domain
    lenses signal slots must cover, and 1.4d the rule that
    inconsistency anchors get the teaser slot.
    """
    return _bundle(
        _section("4. Thread Architecture"),
        _section("5b. Mod Presence"),
        _section("6. Short Path - Noise"),
        _table_c_domains(),
        _anchor_priority_rules(),
    )


def encounters_excerpts() -> str:
    """Rules Step 6 (Encounters) is asked to apply: section 11."""
    return _section("11. The Encounter")
