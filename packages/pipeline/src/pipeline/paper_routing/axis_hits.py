#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Shared axis hit helpers for aggregation and sustained tests."""

from __future__ import annotations

from pipeline.paper_routing.hypotheses import (
    DESIGN_MODE,
    LANGUAGE_DOMAIN,
    LIBRARY_DOMAIN,
    WORDING_MODE,
)
from pipeline.paper_routing.types import Sentence

_LANGUAGE_CONTEXT_SUPPRESS = frozenset({"D9"})


def library_hits(hits: frozenset[str]) -> frozenset[str]:
    return hits & LIBRARY_DOMAIN


def language_hits(hits: frozenset[str]) -> frozenset[str]:
    """Language-domain hits with D9 suppressed when library domain co-fires."""
    lang = set(hits & LANGUAGE_DOMAIN)
    if hits & LIBRARY_DOMAIN:
        lang -= _LANGUAGE_CONTEXT_SUPPRESS
    return frozenset(lang)


def design_hits(hits: frozenset[str]) -> frozenset[str]:
    return hits & DESIGN_MODE


def wording_hits(hits: frozenset[str]) -> frozenset[str]:
    return hits & WORDING_MODE


def axis_density(
    section_sents: list[Sentence],
    axis_fn,
) -> float:
    if not section_sents:
        return 0.0
    count = sum(1 for s in section_sents if axis_fn(s.hypothesis_hits))
    return count / len(section_sents)
