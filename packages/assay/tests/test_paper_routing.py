#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.classifier_backends import MultiLabelClassifierBackend, NliCrossEncoderBackend

from assay.paper_routing import RoutingGroup, route_paper
from assay.paper_routing.hypotheses import (
    CATALOG,
    Hypothesis,
    _CATALOG_IDS,
    _ROUTING_NLI_THRESHOLD,
    _resolve_classifiers,
    get_hits_from_text,
    score_hypotheses,
)
from assay.paper_routing.nli_thresholds import load_nli_hypothesis_thresholds
from assay.paper_routing.seqcls_thresholds import (
    _ROUTING_SEQCLS_THRESHOLD_FALLBACK as _ROUTING_SEQCLS_THRESHOLD,
    load_seqcls_hypothesis_thresholds,
)
from assay.paper_routing.split import split_sentences
from assay.paper_routing.headings import classify_routing_section
from assay.paper_routing.types import SectionType
from assay.paper_routing.aggregate import (
    _apply_domain_arbitration,
    _apply_metadata_bonus,
    aggregate_quadrant_scores,
)
from assay.paper_routing.sustain import min_sustained_threshold, sustained_counts
from assay.paper_routing.threshold import (
    ADMIN_MAX_SCORE_GATE,
    SECONDARY_MARGIN,
    THRESHOLD_CWG,
    THRESHOLD_EWG,
    THRESHOLD_LEWG,
    apply_thresholds,
)
from assay.paper_routing.aggregate import DOMAIN_ARBITRATION_MARGIN

_FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "routing"


def _read(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def test_n3854_routes_lewg():
    """N3854 is a library-design paper; LWG may not emit under argmax+margin
    because the design signal dominates the short excerpt."""
    result = route_paper(_read("n3854.md"), audience=["LEWG", "LWG"])
    assert "LEWG" in result.groups
    assert "EWG" not in result.groups
    assert "CWG" not in result.groups
    assert not result.is_administrative


def test_n5044_administrative():
    result = route_paper(_read("n5044_excerpt.md"), audience=["WG21"])
    assert result.groups == {}
    assert result.is_administrative


def test_stray_language_no_ewg():
    result = route_paper(_read("stray_language.md"), audience=["LEWG"])
    assert "EWG" not in result.groups
    assert "CWG" not in result.groups


def test_performance_focused_flag():
    result = route_paper(_read("performance_focused.md"))
    assert result.is_performance_focused is True


def test_route_without_classifier():
    result = route_paper(_read("n3854.md"))
    assert result.sentence_count > 0
    assert "LEWG" in result.groups


def test_determinism():
    md = _read("n3854.md")
    a = route_paper(md, audience=["LEWG", "LWG"])
    b = route_paper(md, audience=["LEWG", "LWG"])
    assert a == b


def test_code_block_is_single_sentence():
    md = "Prose before.\n\n```cpp\nint x = 1;\nint y = 2;\n```\n\nProse after."
    units = split_sentences(md)
    assert len(units) == 3
    assert "```" in units[1].text


def test_heading_section_mapping():
    assert classify_routing_section("Motivation and Scope") == SectionType.MOTIVATION
    assert classify_routing_section("Proposed Wording") == SectionType.WORDING
    assert classify_routing_section("References") == SectionType.APPENDIX
    assert classify_routing_section("Design Decisions") == SectionType.DESIGN
    assert classify_routing_section("Interface") == SectionType.DESIGN
    assert (
        classify_routing_section("Impact on the Standard") == SectionType.IMPACT
    )
    assert classify_routing_section("Compatibility") == SectionType.IMPACT
    assert classify_routing_section("ABI Considerations") == SectionType.IMPACT
    assert (
        classify_routing_section("Implementation Experience")
        == SectionType.IMPLEMENTATION
    )
    assert classify_routing_section("") == SectionType.PREAMBLE
    assert classify_routing_section("Abstract") == SectionType.PREAMBLE


def test_heading_bare_generic_token_fallback():
    """Bare, generic single-word headings still resolve to the expected
    section when no other category's specific vocabulary is present."""
    assert classify_routing_section("API") == SectionType.DESIGN
    assert classify_routing_section("Design") == SectionType.DESIGN
    assert classify_routing_section("Wording") == SectionType.WORDING
    assert classify_routing_section("Implementation") == SectionType.IMPLEMENTATION
    assert classify_routing_section("Design of this Document") == SectionType.PREAMBLE


def test_heading_cross_category_collision_favors_specific_phrase():
    """A heading mixing a generic token from one category (bare "API") with
    a specific phrase from another ("ABI Considerations") must resolve to
    the category owning the specific phrase, regardless of category check
    order. Regression test for the DESIGN/IMPACT check-order bug where
    ``\\bAPI\\b`` in the DESIGN pattern pre-empted IMPACT's more specific
    ``ABI Considerations`` match.
    """
    assert (
        classify_routing_section("API and ABI Considerations")
        == SectionType.IMPACT
    )
    assert (
        classify_routing_section("ABI Considerations and the API")
        == SectionType.IMPACT
    )


@pytest.mark.parametrize("hyp", CATALOG)
def test_hypothesis_catalog_ids_unique(hyp: Hypothesis):
    ids = [h.id for h in CATALOG]
    assert ids.count(hyp.id) == 1


@pytest.mark.parametrize("hyp", CATALOG)
def test_hypothesis_catalog_declares_regex_and_nli(hyp: Hypothesis):
    """Every catalog hypothesis has NLI text for batch scoring and a regex
    for the fast path. Both may be present; neither may be missing."""
    assert hyp.nli_text is not None
    assert hyp.regex is not None


def test_d10_does_not_match_prose_colon_labels():
    hyp = next(h for h in CATALOG if h.id == "D10")
    assert not hyp.matches_regex("Note: this is fine.")
    assert not hyp.matches_regex("Effects: Returns true if x holds a value.")
    assert not hyp.matches_regex("Author: Jane Doe")
    assert "D10" not in get_hits_from_text("Rationale: we chose this name.")


def test_d10_matches_bnf_nonterminal():
    hyp = next(h for h in CATALOG if h.id == "D10")
    assert hyp.matches_regex(
        "floating-literal:\nfractional-constant exponent-partopt",
    )
    assert hyp.matches_regex("preprocessing-token:\n  header-name")
    assert hyp.matches_regex("do-expression ::= do-initialization ':' expression")


def test_d1_matches_library_header():
    hyp = next(h for h in CATALOG if h.id == "D1")
    assert hyp.matches_regex("Use <type_traits> for trait queries.")
    assert not hyp.matches_regex("No headers here.")


def test_s1_declared_as_regex_in_catalog():
    """S1 must fire through its own catalog-declared regex, not a hardcoded
    special case in ``get_hits_from_text``."""
    hyp = next(h for h in CATALOG if h.id == "S1")
    assert hyp.regex is not None
    assert hyp.matches_regex("audience: LEWG, LWG")
    assert "S1" in get_hits_from_text("audience: SG1, LEWG")
    assert "S1" not in get_hits_from_text("No metadata here.")


def test_d4_generalizes_beyond_worked_example_wording():
    """D4 (NAMESPACE_STD_MUTATION) must fire on library-modification
    phrasing that is not a verbatim transcription of the N3854 worked
    example ("the C++17 Standard Library should be updated accordingly").
    """
    hyp = next(h for h in CATALOG if h.id == "D4")
    assert hyp.matches_regex(
        "The header files for the standard library must be modified to add the new "
        "annotations.",
    )
    assert hyp.matches_regex(
        "Existing library implementations will need to be updated to support this.",
    )
    assert not hyp.matches_regex("This sentence has nothing to do with the library.")


def test_m2_generalizes_beyond_worked_example_wording():
    """M2 (PROPOSES_MODIFICATION) must fire on modification phrasing that is
    not a verbatim transcription of the N3854 worked example ("updated
    accordingly").
    """
    hyp = next(h for h in CATALOG if h.id == "M2")
    assert hyp.matches_regex("The following signature should be changed to match.")
    assert hyp.matches_regex("This wording needs to be revised for clarity.")
    assert hyp.matches_regex("The reference implementation is updated accordingly.")
    assert not hyp.matches_regex("This sentence proposes nothing in particular.")


def test_sustained_min_floor():
    assert min_sustained_threshold(10) == 3
    assert min_sustained_threshold(500) == 10


def test_sustained_counts_gapped_indices_use_kept_list_adjacency():
    """After sampling, kept indices can be gapped; co-fire uses list adjacency."""
    from assay.paper_routing.types import Sentence

    sentences = [
        Sentence(
            "library header ref",
            SectionType.MOTIVATION,
            0,
            frozenset({"D1"}),
        ),
        Sentence(
            "proposes addition",
            SectionType.MOTIVATION,
            2,
            frozenset({"M1"}),
        ),
    ]
    counts = sustained_counts(sentences)
    assert counts[RoutingGroup.LEWG] == 2


def _zeroed_scores() -> dict[RoutingGroup, float]:
    return {g: 0.0 for g in RoutingGroup}


@pytest.mark.parametrize(
    ("audience", "expected"),
    [
        (
            ["LEWG"],
            {
                RoutingGroup.LEWG: 0.20,
                RoutingGroup.LWG: 0.10,
                RoutingGroup.EWG: 0.0,
                RoutingGroup.CWG: 0.0,
            },
        ),
        (
            ["LWG"],
            {
                RoutingGroup.LEWG: 0.15,
                RoutingGroup.LWG: 0.10,
                RoutingGroup.EWG: 0.0,
                RoutingGroup.CWG: 0.0,
            },
        ),
        (
            ["Library Evolution"],
            {
                RoutingGroup.LEWG: 0.20,
                RoutingGroup.LWG: 0.10,
                RoutingGroup.EWG: 0.0,
                RoutingGroup.CWG: 0.0,
            },
        ),
        (
            ["LEWG", "LWG"],
            {
                RoutingGroup.LEWG: 0.20,
                RoutingGroup.LWG: 0.10,
                RoutingGroup.EWG: 0.0,
                RoutingGroup.CWG: 0.0,
            },
        ),
        (
            ["EWG"],
            {
                RoutingGroup.LEWG: 0.0,
                RoutingGroup.LWG: 0.0,
                RoutingGroup.EWG: 0.20,
                RoutingGroup.CWG: 0.0,
            },
        ),
    ],
)
def test_metadata_bonus_audience_tokens(
    audience: list[str], expected: dict[RoutingGroup, float]
):
    scores = _zeroed_scores()
    _apply_metadata_bonus(scores, audience)
    assert scores == expected


_M4_NLI_TEXT = "The sentence explains why a design choice was made."
_NLI_ONLY_SENTENCE = (
    "The ergonomic tradeoff favors explicit syntax over implicit conversions."
)


class _StubNliClassifier(NliCrossEncoderBackend):
    def __init__(self, entailment: float, *, match_hypothesis: str | None = None) -> None:
        self._entailment = entailment
        self._match_hypothesis = match_hypothesis
        self.calls: list[list[tuple[str, str]]] = []

    def nli_entailment_pairs(
        self, pairs: list[tuple[str, str]]
    ) -> list[dict[str, float]]:
        self.calls.append(list(pairs))
        scores: list[dict[str, float]] = []
        for _premise, hypothesis in pairs:
            if self._match_hypothesis is None or hypothesis == self._match_hypothesis:
                e = self._entailment
            else:
                e = 0.0
            scores.append({"entailment": e, "neutral": 0.0, "contradiction": 0.0})
        return scores


def test_routing_nli_threshold_constant():
    assert _ROUTING_NLI_THRESHOLD == 0.9


def test_nli_hypothesis_thresholds_cover_full_catalog():
    thresholds = load_nli_hypothesis_thresholds()
    assert set(thresholds) == _CATALOG_IDS
    for threshold in thresholds.values():
        assert 0.0 < threshold <= 1.0


def test_score_hypotheses_nli_uses_per_label_threshold_not_flat_default(monkeypatch):
    # M4's patched cutoff is above the flat fallback (0.9): a score in
    # between proves per-label thresholds are consulted.
    monkeypatch.setattr(
        "assay.paper_routing.hypotheses.load_nli_hypothesis_thresholds",
        lambda: {"M4": 0.95},
    )
    sentence = _NLI_ONLY_SENTENCE
    classifier = _StubNliClassifier(0.91, match_hypothesis=_M4_NLI_TEXT)
    scored = score_hypotheses([sentence], classifiers=classifier)

    assert "M4" not in scored[0].hypothesis_hits


def test_score_hypotheses_nli_path_fires_on_high_entailment():
    sentence = _NLI_ONLY_SENTENCE
    assert get_hits_from_text(sentence) == set()

    classifier = _StubNliClassifier(0.99, match_hypothesis=_M4_NLI_TEXT)
    scored = score_hypotheses([sentence], classifiers=classifier)

    assert len(scored) == 1
    assert "M4" in scored[0].hypothesis_hits
    assert classifier.calls
    assert classifier.calls[0][0][0] == sentence


def test_score_hypotheses_nli_path_skips_low_entailment():
    sentence = _NLI_ONLY_SENTENCE
    classifier = _StubNliClassifier(0.1, match_hypothesis=_M4_NLI_TEXT)
    scored = score_hypotheses([sentence], classifiers=classifier)

    assert len(scored) == 1
    assert "M4" not in scored[0].hypothesis_hits


class _StubSeqclsClassifier(MultiLabelClassifierBackend):
    def __init__(self, scores_by_label: dict[str, float]) -> None:
        self._scores_by_label = scores_by_label
        self.model_id = "fake/seqcls"
        self.calls: list[tuple[list[str], list[str]]] = []

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(sorted(self._scores_by_label))

    def classify(
        self,
        texts: list[str],
        candidate_labels: list[str],
        *,
        multi_label: bool = True,
    ) -> list[dict[str, float]]:
        del multi_label
        self.calls.append((list(texts), list(candidate_labels)))
        row = {label: self._scores_by_label.get(label, 0.0) for label in candidate_labels}
        return [dict(row) for _ in texts]


def test_routing_seqcls_threshold_constant():
    assert _ROUTING_SEQCLS_THRESHOLD == 0.25


def test_seqcls_hypothesis_thresholds_cover_full_catalog():
    thresholds = load_seqcls_hypothesis_thresholds()
    assert set(thresholds) == _CATALOG_IDS
    for threshold in thresholds.values():
        assert 0.0 < threshold < 1.0


def test_score_hypotheses_seqcls_uses_per_label_threshold_not_flat_default():
    thresholds = load_seqcls_hypothesis_thresholds()
    # W4's calibrated threshold (0.5) is above the flat fallback (0.25): a
    # score in between proves per-label thresholds are consulted.
    assert thresholds["W4"] > _ROUTING_SEQCLS_THRESHOLD
    sentence = "Add a free function defined as follows to namespace std."
    classifier = _StubSeqclsClassifier({"W4": 0.3})
    scored = score_hypotheses(
        [sentence],
        use_regex=False,
        classifiers=[classifier],
    )

    assert "W4" not in scored[0].hypothesis_hits


def test_score_hypotheses_seqcls_path_fires_on_high_score():
    sentence = "We chose this approach because it minimizes template bloat."
    classifier = _StubSeqclsClassifier({"M4": 0.9})
    scored = score_hypotheses(
        [sentence],
        use_regex=False,
        classifiers=[classifier],
    )

    assert len(scored) == 1
    assert scored[0].hypothesis_hits == frozenset({"M4"})
    assert classifier.calls


def test_score_hypotheses_nli_only_skips_regex_hits():
    sentence = "We propose to add std::widget."
    assert get_hits_from_text(sentence) == {"D3", "M1"}

    classifier = _StubNliClassifier(0.1, match_hypothesis=_M4_NLI_TEXT)
    scored = score_hypotheses(
        [sentence],
        use_regex=False,
        classifiers=classifier,
    )

    assert scored[0].hypothesis_hits == frozenset()


def test_score_hypotheses_regex_nli_seqcls_union():
    sentence = "We propose to add std::widget."
    nli = _StubNliClassifier(0.99, match_hypothesis=_M4_NLI_TEXT)
    seqcls = _StubSeqclsClassifier({"W4": 0.9})
    scored = score_hypotheses(
        [sentence],
        use_regex=True,
        classifiers=[nli, seqcls],
    )

    hits = set(scored[0].hypothesis_hits)
    assert {"D3", "M1"}.issubset(hits)
    assert "M4" in hits
    assert "W4" in hits


def test_score_hypotheses_from_sentence_list_matches_regex_hits():
    sentences = [
        "We propose to add std::widget.",
        "Effects: returns a value.",
    ]
    scored = score_hypotheses(sentences)
    assert len(scored) == 2
    assert scored[0].text == sentences[0]
    assert scored[1].text == sentences[1]
    assert scored[0].section == SectionType.PREAMBLE
    assert scored[1].section == SectionType.PREAMBLE
    assert set(scored[0].hypothesis_hits) == get_hits_from_text(sentences[0])
    assert set(scored[1].hypothesis_hits) == get_hits_from_text(sentences[1])


def test_score_hypotheses_markdown_assigns_section_from_headings():
    md = "## Motivation section\n\nWe propose to add <vector> support."
    scored = score_hypotheses(md)
    assert len(scored) == 2
    assert scored[1].section == SectionType.MOTIVATION


def test_score_hypotheses_rejects_invalid_input_type():
    with pytest.raises(TypeError, match="expects str"):
        score_hypotheses(123)  # type: ignore[arg-type]


def test_score_hypotheses_rejects_non_string_list_items():
    with pytest.raises(TypeError, match="sentence list items must be str"):
        score_hypotheses(["ok", 1])  # type: ignore[list-item]


def test_threshold_requires_sustained_signal():
    from assay.paper_routing.types import Sentence

    sentences = [
        Sentence(
            "std::vector in <vector>",
            SectionType.MOTIVATION,
            0,
            frozenset({"D1", "M1"}),
        ),
        Sentence(
            "proposal to add more", SectionType.MOTIVATION, 1, frozenset({"M1", "D3"})
        ),
        Sentence(
            "library design rationale",
            SectionType.MOTIVATION,
            2,
            frozenset({"D3", "M6"}),
        ),
    ]
    scores = aggregate_quadrant_scores(sentences)
    groups, _ = apply_thresholds(scores, sentences)
    assert scores[RoutingGroup.LEWG] > THRESHOLD_LEWG
    assert RoutingGroup.LEWG in groups


def test_routing_group_threshold_constants():
    assert THRESHOLD_EWG == 0.35
    assert THRESHOLD_CWG == 0.18


class _MinimalClassifier(NliCrossEncoderBackend):
    def __init__(self, model_id: str) -> None:
        self.model_id = model_id

    def classify(self, texts, candidate_labels, *, multi_label=True):
        return []


def test_resolve_classifiers_single_backend():
    backend = _MinimalClassifier("z")
    assert _resolve_classifiers(backend) == (backend,)


def test_resolve_classifiers_sorts_sequence():
    b_a = _MinimalClassifier("a")
    b_z = _MinimalClassifier("z")
    resolved = _resolve_classifiers([b_z, b_a])
    assert resolved == (b_a, b_z)


def test_score_hypotheses_use_regex_false_skips_regex_hits():
    sentence = (
        "This paragraph is long enough to score but has no catalog regex signals."
    )
    scored = score_hypotheses([sentence], use_regex=False)
    assert scored[0].hypothesis_hits == frozenset()


def test_section_stratified_sampling_includes_wording_block():
    design_line = (
        "We propose adding std::widget to the standard library design section."
    )
    wording_line = (
        "Modify [namespace.std.foo] to add the following normative wording text."
    )
    lines = ["## Design"]
    lines.extend(design_line for _ in range(50))
    lines.append("## Proposed wording")
    lines.extend(wording_line for _ in range(400))
    md = "\n".join(lines)
    scored = score_hypotheses(md, use_regex=True, classifiers=None)
    assert len(scored) == 300
    wording = [s for s in scored if s.section == SectionType.WORDING]
    assert wording
    assert max(s.index for s in wording) > 100


class _StubSeqcls(MultiLabelClassifierBackend):
    def __init__(self) -> None:
        self.model_id = "fake/seqcls-routing"

    @property
    def labels(self) -> tuple[str, ...]:
        return ("M4",)

    def classify(
        self,
        texts: list[str],
        candidate_labels: list[str],
        *,
        multi_label: bool = True,
    ) -> list[dict[str, float]]:
        del multi_label
        row = {label: (0.99 if label == "M4" else 0.0) for label in candidate_labels}
        return [dict(row) for _ in texts]


def test_score_hypotheses_seqcls_merges_hits():
    sentence = _NLI_ONLY_SENTENCE
    scored = score_hypotheses([sentence], classifiers=_StubSeqcls())
    assert "M4" in scored[0].hypothesis_hits


# --- Tier A emission policy tests ---


def _make_sentences(count: int, *, hits: frozenset[str]) -> list:
    """Build a list of Sentence objects with the given hypothesis hits."""
    from assay.paper_routing.types import Sentence

    return [
        Sentence(f"sentence {i}", SectionType.MOTIVATION, i, hits)
        for i in range(count)
    ]


def test_apply_thresholds_emits_on_exact_threshold():
    sentences = _make_sentences(200, hits=frozenset({"D1", "M1"}))
    scores = {
        RoutingGroup.LEWG: THRESHOLD_LEWG,
        RoutingGroup.LWG: 0.0,
        RoutingGroup.EWG: 0.0,
        RoutingGroup.CWG: 0.0,
    }
    groups, _ = apply_thresholds(scores, sentences)
    assert RoutingGroup.LEWG in groups


def test_arbitration_before_bonus_keeps_near_language_domain():
    scores = {
        RoutingGroup.LEWG: 0.35,
        RoutingGroup.LWG: 0.0,
        RoutingGroup.EWG: 0.30,
        RoutingGroup.CWG: 0.0,
    }
    _apply_domain_arbitration(scores)
    _apply_metadata_bonus(scores, ["LEWG"])
    assert scores[RoutingGroup.EWG] == 0.30
    assert scores[RoutingGroup.LEWG] == pytest.approx(0.55)


def test_admin_gate_fires_on_low_scores():
    """When all quadrant scores are at or below ADMIN_MAX_SCORE_GATE, emit nothing."""
    sentences = _make_sentences(10, hits=frozenset())
    low_scores = {g: ADMIN_MAX_SCORE_GATE for g in RoutingGroup}
    groups, _ = apply_thresholds(low_scores, sentences)
    assert groups == {}


def test_admin_gate_does_not_fire_above_threshold():
    """When max score exceeds the admin gate, emission proceeds."""
    sentences = _make_sentences(200, hits=frozenset({"D1", "D3", "M1", "M2"}))
    high_scores = {
        RoutingGroup.LEWG: 0.50,
        RoutingGroup.LWG: 0.01,
        RoutingGroup.EWG: 0.01,
        RoutingGroup.CWG: 0.01,
    }
    groups, _ = apply_thresholds(high_scores, sentences)
    assert RoutingGroup.LEWG in groups


def test_argmax_margin_emits_only_primary_when_gap_large():
    """Secondary groups below SECONDARY_MARGIN from primary are not emitted."""
    sentences = _make_sentences(200, hits=frozenset({"D1", "D3", "M1", "M2"}))
    scores = {
        RoutingGroup.LEWG: 0.50,
        RoutingGroup.LWG: 0.50 - SECONDARY_MARGIN - 0.01,
        RoutingGroup.EWG: 0.50 - SECONDARY_MARGIN - 0.01,
        RoutingGroup.CWG: 0.01,
    }
    groups, _ = apply_thresholds(scores, sentences)
    assert RoutingGroup.LEWG in groups
    assert len(groups) == 1


def test_argmax_margin_emits_secondary_within_margin():
    """Secondary groups within SECONDARY_MARGIN of primary are emitted."""
    sentences = _make_sentences(200, hits=frozenset({"D1", "D3", "M1", "M2", "W1"}))
    scores = {
        RoutingGroup.LEWG: 0.50,
        RoutingGroup.LWG: 0.50 - SECONDARY_MARGIN + 0.01,
        RoutingGroup.EWG: 0.01,
        RoutingGroup.CWG: 0.01,
    }
    groups, _ = apply_thresholds(scores, sentences)
    assert RoutingGroup.LEWG in groups
    assert RoutingGroup.LWG in groups


def test_domain_arbitration_suppresses_weak_domain():
    """When one domain is much weaker, it should be zeroed by arbitration."""
    sentences = _make_sentences(100, hits=frozenset({"D1", "M1"}))
    scores = aggregate_quadrant_scores(sentences)
    lib_best = max(scores[RoutingGroup.LEWG], scores[RoutingGroup.LWG])
    lang_best = max(scores[RoutingGroup.EWG], scores[RoutingGroup.CWG])
    assert lib_best > lang_best + DOMAIN_ARBITRATION_MARGIN
    assert scores[RoutingGroup.EWG] == 0.0
    assert scores[RoutingGroup.CWG] == 0.0
