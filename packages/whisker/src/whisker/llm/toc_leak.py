#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Unpaired TOC-leak detector for the advisory LLM-lane clamp.

Two hit shapes the pairwise ``no_toc_leak`` gate misses when the body
heading is absent: a WG21 heading with ``[stable-name]`` plus a trailing
page number, and a cluster of page-suffixed headings. Not wired into
``run_gates``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from whisker.gates import iter_body_lines, split_front_matter

__all__ = [
    "MIN_CLUSTER_RUN",
    "TocLeakHit",
    "clamp_toc_leak",
    "detect_unpaired_toc_leak",
    "toc_leak_tag",
]

_HEADING_RE = re.compile(r"^#{1,6}\s+(\S.*)$")
_PAGE_SUFFIX_RE = re.compile(r"^(?P<stem>.*\S)\s+\d{1,4}$")
_WG21_RE = re.compile(r"^\d+(?:\.\d+)*\s+.+?\s+\[[\w.]+\]\s+\d{1,4}$")

MIN_CLUSTER_RUN = 3  # aligned with tomd.lib.toc.MIN_TOC_RUN
_MAX_CLUSTER_BODY_LINES = 2  # little body between page-suffixed headings


@dataclass(frozen=True)
class TocLeakHit:
    kind: str  # "wg21_shape" or "cluster"
    heading: str


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def detect_unpaired_toc_leak(md: str) -> list[TocLeakHit]:
    """Return unpaired TOC-leak hits. Fenced code is skipped."""
    _, body = split_front_matter(md)
    hits: list[TocLeakHit] = []
    seen: set[str] = set()
    run: list[tuple[str, str]] = []
    gap = 0

    def flush() -> None:
        nonlocal run, gap
        stems = {stem for stem, _ in run}
        if len(run) >= MIN_CLUSTER_RUN and len(stems) >= MIN_CLUSTER_RUN:
            for _, heading in run:
                if heading not in seen:
                    hits.append(TocLeakHit("cluster", heading))
                    seen.add(heading)
        run = []
        gap = 0

    for line, kind in iter_body_lines(body):
        if kind != "text":
            flush()
            continue
        stripped = line.strip()
        m = _HEADING_RE.match(stripped)
        if m is None:
            if stripped:
                gap += 1
            continue
        heading = _norm(m.group(1))
        if _WG21_RE.match(heading) and heading not in seen:
            seen.add(heading)
            hits.append(TocLeakHit("wg21_shape", heading))
        pm = _PAGE_SUFFIX_RE.match(heading)
        if pm is None or gap > _MAX_CLUSTER_BODY_LINES:
            flush()
        if pm is None:
            continue
        run.append((pm.group("stem"), heading))
        gap = 0
    flush()
    return hits


def clamp_toc_leak(
    verdict: str,
    hits: list[TocLeakHit] | list[str],
    severity: str = "none",
) -> tuple[str, str]:
    """If *hits*, force at least review + major. Never upgrades to fail."""
    if not hits:
        return verdict, severity
    if verdict == "pass":
        verdict = "review"
    if severity in ("none", "minor"):
        severity = "major"
    return verdict, severity


def toc_leak_tag(heading: str) -> str:
    return f" [toc_leak_unpaired: {heading!r}]"
