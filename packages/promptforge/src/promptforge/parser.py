#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Parse a pipeline markdown file into an addressable structure.

The document is the program. This module turns it into:

- H2 sections (``## Name``), the primary addressable procedures.
- H3 children (``### Name``) of a section, for fan-out.
- Tagged blocks (``<tag>...</tag>``), shipped verbatim by reference.
- The optional ``lua`` fence inside a section, which configures it.

Splitting is fence-aware: a heading inside a ```` ``` ```` code fence never
starts a new section. Only H2 boundaries split the document; there is no
``---`` zone convention, because in PromptForge the whole file is the program.
Block extraction scans the whole file independently of section boundaries, so
reference blocks may sit after the executed sections without their inner
markdown headings splitting anything.

The H2 splitter descends from ``pipeline.markdown.sections`` and the
heading-tree idea from ``assay.chunker``; both are adapted here rather than
imported because PromptForge needs H3 children and tag blocks that neither
existing module exposes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_H2_RE = re.compile(r"^##\s+(.+?)\s*$")
_H3_RE = re.compile(r"^###\s+(.+?)\s*$")
_LUA_FENCE_OPEN_RE = re.compile(r"^```lua\b", re.IGNORECASE)
# Paired lowercase-tag blocks only, so <img ...> and <!-- --> never match.
_BLOCK_RE = re.compile(r"<([a-z][a-z0-9-]*)>(.*?)</\1>", re.DOTALL)


def _is_fence(line: str) -> bool:
    return line.lstrip().startswith("```")


@dataclass(frozen=True)
class Section:
    """One addressable section: a heading plus its raw body.

    ``prose`` is what the model reads (the body minus the lua fence);
    ``lua`` is what the runtime reads to configure the section.
    """

    name: str
    level: int
    body: str

    @property
    def prose(self) -> str:
        return _strip_lua_fence(self.body).strip()

    @property
    def lua(self) -> str | None:
        return _extract_lua(self.body)


class Document:
    """A parsed pipeline markdown document."""

    def __init__(self, text: str) -> None:
        self._preamble, self._sections = _split_h2(text)
        self._blocks = {
            m.group(1): m.group(2).strip("\n") for m in _BLOCK_RE.finditer(text)
        }

    @classmethod
    def from_path(cls, path: str | Path) -> "Document":
        return cls(Path(path).read_text(encoding="utf-8"))

    @property
    def preamble(self) -> str:
        return self._preamble

    @property
    def sections(self) -> dict[str, Section]:
        return dict(self._sections)

    def has_section(self, ref: str) -> bool:
        return _norm_ref(ref) in self._sections

    def section(self, ref: str) -> Section:
        key = _norm_ref(ref)
        try:
            return self._sections[key]
        except KeyError:
            raise KeyError(
                f"no section '{key}'. Available: {sorted(self._sections)}"
            ) from None

    def children(self, ref: str) -> list[Section]:
        return _split_h3(self.section(ref).body)

    def has_block(self, tag: str) -> bool:
        return tag in self._blocks

    def block(self, tag: str) -> str:
        try:
            return self._blocks[tag]
        except KeyError:
            raise KeyError(
                f"no block <{tag}>. Available: {sorted(self._blocks)}"
            ) from None


def _norm_ref(ref: str) -> str:
    """Accept both ``## Main`` and ``Main`` as a section reference."""
    return ref.lstrip("#").strip()


def _split_h2(text: str) -> tuple[str, dict[str, Section]]:
    """Return ``(preamble, sections)`` splitting on fence-aware H2 boundaries."""
    preamble: list[str] = []
    sections: dict[str, Section] = {}
    name: str | None = None
    body: list[str] = []
    in_fence = False

    def flush() -> None:
        if name is not None:
            sections[name] = Section(name, 2, "\n".join(body).strip("\n"))

    for line in text.splitlines():
        if _is_fence(line):
            in_fence = not in_fence
            (body if name is not None else preamble).append(line)
            continue
        if not in_fence:
            m = _H2_RE.match(line)
            if m:
                flush()
                name = m.group(1).strip()
                body = []
                continue
        (body if name is not None else preamble).append(line)

    flush()
    return "\n".join(preamble).strip("\n"), sections


def _split_h3(body: str) -> list[Section]:
    """Return the fence-aware H3 children found in a section body."""
    children: list[Section] = []
    name: str | None = None
    lines: list[str] = []
    in_fence = False

    def flush() -> None:
        if name is not None:
            children.append(Section(name, 3, "\n".join(lines).strip("\n")))

    for line in body.splitlines():
        if _is_fence(line):
            in_fence = not in_fence
            if name is not None:
                lines.append(line)
            continue
        if not in_fence:
            m = _H3_RE.match(line)
            if m:
                flush()
                name = m.group(1).strip()
                lines = []
                continue
        if name is not None:
            lines.append(line)

    flush()
    return children


def _extract_lua(body: str) -> str | None:
    """Return the contents of the first ``lua`` fence, or None."""
    collecting = False
    out: list[str] = []
    for line in body.splitlines():
        if not collecting:
            if _LUA_FENCE_OPEN_RE.match(line.lstrip()):
                collecting = True
            continue
        if _is_fence(line):
            return "\n".join(out)
        out.append(line)
    return None


def _strip_lua_fence(body: str) -> str:
    """Return the body with any ``lua`` fenced block removed."""
    out: list[str] = []
    skipping = False
    for line in body.splitlines():
        if not skipping and _LUA_FENCE_OPEN_RE.match(line.lstrip()):
            skipping = True
            continue
        if skipping:
            if _is_fence(line):
                skipping = False
            continue
        out.append(line)
    return "\n".join(out)
