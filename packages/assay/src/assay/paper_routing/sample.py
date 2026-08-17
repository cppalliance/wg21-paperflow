#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Section-stratified sentence sampling for paper routing."""

from __future__ import annotations

from collections.abc import Sequence

from assay.paper_routing.types import SectionType, Sentence

_ELIGIBLE_SECTIONS: tuple[SectionType, ...] = tuple(
    section for section in SectionType if section is not SectionType.APPENDIX
)


def _hamilton_quotas(
    section_counts: dict[SectionType, int],
    *,
    cap: int,
) -> dict[SectionType, int]:
    """Largest-remainder allocation; ties break by ``SectionType`` enum order."""
    n = sum(section_counts.get(section, 0) for section in _ELIGIBLE_SECTIONS)
    if n == 0:
        return {section: 0 for section in _ELIGIBLE_SECTIONS}

    quotas: dict[SectionType, int] = {}
    remainders: list[tuple[float, SectionType]] = []
    allocated = 0
    for section in _ELIGIBLE_SECTIONS:
        n_s = section_counts.get(section, 0)
        if n_s == 0:
            quotas[section] = 0
            continue
        raw = cap * n_s / n
        floor = int(raw)
        quotas[section] = floor
        allocated += floor
        remainders.append((raw - floor, section))

    extra = cap - allocated
    remainders.sort(key=lambda item: (-item[0], _ELIGIBLE_SECTIONS.index(item[1])))
    for i in range(extra):
        section = remainders[i][1]
        quotas[section] += 1

    for section in _ELIGIBLE_SECTIONS:
        n_s = section_counts.get(section, 0)
        quotas[section] = min(quotas[section], n_s)

    return quotas


def _stride_indices(n_s: int, k: int) -> list[int]:
    """Evenly spaced positions in ``0..n_s-1``; exactly ``k`` picks when ``k <= n_s``."""
    if k <= 0:
        return []
    if k == 1:
        return [0]
    if k >= n_s:
        return list(range(n_s))
    return [i * (n_s - 1) // (k - 1) for i in range(k)]


def _stride_pick(section_sents: list[Sentence], k: int) -> list[Sentence]:
    if k <= 0 or not section_sents:
        return []
    positions = _stride_indices(len(section_sents), k)
    return [section_sents[pos] for pos in positions]


def _group_by_section(sentences: Sequence[Sentence]) -> dict[SectionType, list[Sentence]]:
    grouped: dict[SectionType, list[Sentence]] = {section: [] for section in SectionType}
    for sent in sentences:
        grouped[sent.section].append(sent)
    return grouped


def _format_summary(
    *,
    source_n: int,
    kept_n: int,
    quotas: dict[SectionType, int],
) -> str:
    parts = [
        f"{section.value} {quotas[section]}"
        for section in _ELIGIBLE_SECTIONS
        if quotas.get(section, 0) > 0
    ]
    return f"[routing] sampled {kept_n} of {source_n}: {', '.join(parts)}\n"


def sample_sentences_with_summary(
    sentences: Sequence[Sentence],
    *,
    cap: int,
) -> tuple[list[Sentence], str | None]:
    """Return kept sentences and an optional one-line debug summary."""
    if cap <= 0:
        return [], None
    if len(sentences) <= cap:
        return list(sentences), None

    grouped = _group_by_section(sentences)
    eligible = [
        sent
        for sent in sentences
        if sent.section is not SectionType.APPENDIX
    ]
    if not eligible:
        kept = _stride_pick(list(sentences), cap)
        kept.sort(key=lambda s: s.index)
        summary = (
            f"[routing] sampled {len(kept)} of {len(sentences)} "
            "(appendix-only stride)\n"
        )
        return kept, summary

    if len(eligible) <= cap:
        kept = sorted(eligible, key=lambda s: s.index)
        return kept, None

    section_counts = {
        section: len(grouped[section]) for section in _ELIGIBLE_SECTIONS
    }
    quotas = _hamilton_quotas(section_counts, cap=cap)
    picked: list[Sentence] = []
    for section in _ELIGIBLE_SECTIONS:
        picked.extend(_stride_pick(grouped[section], quotas[section]))
    picked.sort(key=lambda s: s.index)
    summary = _format_summary(
        source_n=len(eligible),
        kept_n=len(picked),
        quotas=quotas,
    )
    return picked, summary


def sample_sentences(
    sentences: Sequence[Sentence],
    *,
    cap: int,
) -> list[Sentence]:
    """Section-stratified stride sample; at most ``cap`` sentences."""
    kept, _ = sample_sentences_with_summary(sentences, cap=cap)
    return kept
