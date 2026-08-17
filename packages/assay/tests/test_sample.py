#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

from __future__ import annotations

from assay.paper_routing.sample import (
    _hamilton_quotas,
    _stride_indices,
    sample_sentences,
    sample_sentences_with_summary,
)
from assay.paper_routing.types import SectionType, Sentence


def _sent(
    section: SectionType,
    index: int,
    *,
    text: str = "x" * 25,
) -> Sentence:
    return Sentence(
        text=text,
        section=section,
        index=index,
        hypothesis_hits=frozenset(),
    )


def _section_block(section: SectionType, start: int, count: int) -> list[Sentence]:
    return [_sent(section, start + i) for i in range(count)]


def test_sample_identity_when_under_cap():
    sentences = _section_block(SectionType.DESIGN, 0, 50)
    kept = sample_sentences(sentences, cap=300)
    assert kept == sentences
    assert len(kept) == 50
    assert [s.index for s in kept] == list(range(50))


def test_short_paper_keeps_appendix():
    eligible = _section_block(SectionType.DESIGN, 0, 40)
    appendix = _section_block(SectionType.APPENDIX, 40, 10)
    sentences = eligible + appendix
    kept = sample_sentences(sentences, cap=300)
    assert len(kept) == 50
    assert any(s.section == SectionType.APPENDIX for s in kept)


def test_all_appendix_strides_full_list():
    sentences = _section_block(SectionType.APPENDIX, 0, 400)
    kept = sample_sentences(sentences, cap=300)
    assert len(kept) == 300
    assert all(s.section == SectionType.APPENDIX for s in kept)


def test_long_paper_drops_appendix_when_eligible_under_cap():
    eligible = _section_block(SectionType.DESIGN, 0, 250)
    appendix = _section_block(SectionType.APPENDIX, 250, 100)
    sentences = eligible + appendix
    kept = sample_sentences(sentences, cap=300)
    assert len(kept) == 250
    assert all(s.section != SectionType.APPENDIX for s in kept)


def test_hamilton_quotas_1920_fixture():
    counts = {
        SectionType.PREAMBLE: 80,
        SectionType.MOTIVATION: 120,
        SectionType.DESIGN: 400,
        SectionType.WORDING: 1200,
        SectionType.IMPACT: 80,
        SectionType.IMPLEMENTATION: 40,
    }
    quotas = _hamilton_quotas(counts, cap=300)
    assert quotas[SectionType.PREAMBLE] == 13
    assert quotas[SectionType.MOTIVATION] == 19
    assert quotas[SectionType.DESIGN] == 63
    assert quotas[SectionType.WORDING] == 187
    assert quotas[SectionType.IMPACT] == 12
    assert quotas[SectionType.IMPLEMENTATION] == 6
    assert sum(quotas.values()) == 300


def test_stride_indices_ten_four():
    assert _stride_indices(10, 4) == [0, 3, 6, 9]


def test_hamilton_tie_break_enum_order():
    counts = {
        SectionType.PREAMBLE: 10,
        SectionType.MOTIVATION: 10,
        SectionType.DESIGN: 0,
        SectionType.WORDING: 0,
        SectionType.IMPACT: 0,
        SectionType.IMPLEMENTATION: 0,
    }
    quotas = _hamilton_quotas(counts, cap=15)
    assert quotas[SectionType.PREAMBLE] == 8
    assert quotas[SectionType.MOTIVATION] == 7


def test_sample_output_sorted_by_index():
    sentences: list[Sentence] = []
    idx = 0
    for section, count in (
        (SectionType.WORDING, 500),
        (SectionType.DESIGN, 500),
    ):
        sentences.extend(_section_block(section, idx, count))
        idx += count
    kept = sample_sentences(sentences, cap=300)
    assert len(kept) == 300
    indices = [s.index for s in kept]
    assert indices == sorted(indices)


def test_sample_1920_fixture_total_kept():
    sentences: list[Sentence] = []
    idx = 0
    for section, count in (
        (SectionType.PREAMBLE, 80),
        (SectionType.MOTIVATION, 120),
        (SectionType.DESIGN, 400),
        (SectionType.WORDING, 1200),
        (SectionType.IMPACT, 80),
        (SectionType.IMPLEMENTATION, 40),
        (SectionType.APPENDIX, 80),
    ):
        sentences.extend(_section_block(section, idx, count))
        idx += count
    kept, summary = sample_sentences_with_summary(sentences, cap=300)
    assert len(kept) == 300
    assert summary is not None
    assert "300 of 1920" in summary
    assert all(s.section != SectionType.APPENDIX for s in kept)


def test_sample_summary_none_when_identity():
    sentences = _section_block(SectionType.DESIGN, 0, 10)
    _, summary = sample_sentences_with_summary(sentences, cap=300)
    assert summary is None
