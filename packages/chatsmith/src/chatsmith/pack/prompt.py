#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""A tiny, self-contained parser for a pack's ``prompt.md``.

Kept independent of wg21-paperflow's ``pipeline`` so the pack (and offline tests)
load with no LLM dependency. The prompt file uses the same ``## Section`` +
``- **key:** value`` conventions as paperflow pipeline prompts, so the same file
also parses cleanly there.
"""

from __future__ import annotations

import re


def parse_sections(markdown: str) -> dict[str, str]:
    """Split a markdown doc into ``{H2 header text: body}`` (order-preserving)."""
    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = line[3:].strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


_BULLET_RE = re.compile(r"\s*-\s*\*\*(?P<key>[^:*]+):\*\*\s*(?P<value>.+?)\s*$")


def parse_services(section: str) -> dict[str, str]:
    """Parse ``- **name:** service`` bullets into ``{logical_name: service_name}``."""
    out: dict[str, str] = {}
    for line in section.splitlines():
        match = _BULLET_RE.match(line)
        if match:
            out[match.group("key").strip().lower()] = match.group("value").strip()
    return out
