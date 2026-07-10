#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Stage 3: hypothesis catalog and scoring."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pipeline.classifier_backends import ClassifierBackend, NliCrossEncoderBackend
from pipeline.nli_batch import score_entailment_pairs
from assay.paper_routing.sections import line_section_map, section_for_sentence
from assay.paper_routing.split import RawSentence, split_sentences
from assay.paper_routing.types import HypothesisAxis, SectionType, Sentence

_ROUTING_NLI_THRESHOLD = 0.3

_D1_RE = re.compile(r"<\s*[a-z_][a-z0-9_]*\s*>")
_D2_RE = re.compile(r"\b\d{1,2}\.\d+(?:\.\d+)*\s+\[[\w.]+\]")
_D3_RE = re.compile(
    r"\bstd::|"
    r"\b\w+_v\b|\b\w+_t\b|"
    r"\b(is_same|is_convertible|tuple_size|decay_t|enable_if|type_traits)\b",
    re.IGNORECASE,
)
_D4_RE = re.compile(
    r"(?i)\bnamespace\s+std\b|"
    r"\b(?:standard\s+)?library\b.{0,60}?\b(?:should|shall|must|will|needs?\s+to)\s+be\s+"
    r"(?:updated|modified|changed|extended|amended)\b|"
    r"\b(?:should|shall|must|will|needs?\s+to)\s+be\s+"
    r"(?:updated|modified|changed|extended|amended)\b.{0,60}?\b(?:standard\s+)?library\b"
)
_D8_RE = re.compile(
    r"\[(?:expr|dcl|class|stmt|decl|basic|conv|temp|cpp|lex)\.[\w.]+\]|"
    r"\b(?:[1-9]|1[0-6])\.\d+(?:\.\d+)*\s+\[",
    re.IGNORECASE,
)
_D9_RE = re.compile(
    r"(?i)\b(concepts?|modules?|coroutines?|structured\s+bindings?|constexpr|"
    r"variable\s+templates?|ranges?|attributes?|lambdas?)\b",
)
_M1_RE = re.compile(
    r"(?i)\b(proposal\s+to\s+add|we\s+propose|this\s+paper\s+introduces?|this\s+proposal\s+adds?)\b",
)
_M2_RE = re.compile(
    r"(?i)\b(?:should|shall|must|will|needs?\s+to)\s+be\s+"
    r"(?:changed|modified|updated|revised|amended)\b|"
    r"\bwe\s+modify\b|"
    r"\bupdat(?:e|ed)\s+accordingly\b",
)
_M5_RE = re.compile(r"(?i)\b(_v\s+suffix|_t\s+suffix|naming\s+convention)\b")
_M6_RE = re.compile(r"(?i)\b(superior\s+to|compared\s+to|alternative\s+approach)\b")
_M7_RE = re.compile(
    r"(?i)\b(simple\s+to\s+learn|less\s+verbose|easier\s+to|unintuitive)\b",
)
_M9_RE = re.compile(
    r"(?i)\b(pure\s+extension|no\s+breaking\s+changes?|backward\s+compatible)\b"
)
_M10_RE = re.compile(
    r"(?i)\b(does(?:n't| not)\s+(?:touch|affect)|limited\s+to|out\s+of\s+scope)\b",
)
_M13_RE = re.compile(
    r"(?i)\b(zero\s+overhead|compile[- ]time\s+cost|no\s+runtime\s+penalty)\b",
)
_W1_RE = re.compile(
    r"(?i)\b(shall\b|Effects:|Returns:|Mandates:|Preconditions:)\b",
)
_W2_RE = re.compile(
    r"(?i)\b(add\s+the\s+following|modify\s+paragraph|strike\b|insert\s+before)\b|(?:,\s*)?add:\s*$",
)
_W3_RE = re.compile(
    r"\b\d{1,2}\.\d+(?:\.\d+)*\s+\[[\w.]+\].*(?:modify|add)", re.IGNORECASE
)
_S3_RE = re.compile(
    r"(?i)\b(does(?:n't| not)\s+affect\s+existing\s+user\s+code|migration\s+path)\b",
)
_S1_RE = re.compile(r"(?i)\baudience:\s*")


@dataclass(frozen=True)
class Hypothesis:
    """One binary routing hypothesis."""

    id: str
    name: str
    axis: HypothesisAxis
    regex: re.Pattern[str] | None
    nli_text: str | None

    def matches_regex(self, sentence: str) -> bool:
        return self.regex is not None and self.regex.search(sentence) is not None


def _h(
    hid: str,
    name: str,
    axis: HypothesisAxis,
    *,
    regex: re.Pattern[str] | None = None,
    nli_text: str | None = None,
) -> Hypothesis:
    return Hypothesis(id=hid, name=name, axis=axis, regex=regex, nli_text=nli_text)


_LIB = HypothesisAxis.LIBRARY_DOMAIN
_LANG = HypothesisAxis.LANGUAGE_DOMAIN
_DES = HypothesisAxis.DESIGN_MODE
_WOR = HypothesisAxis.WORDING_MODE
_STR = HypothesisAxis.STRUCTURAL


CATALOG: tuple[Hypothesis, ...] = (
    _h("D1", "REFERENCES_LIBRARY_HEADER", _LIB, regex=_D1_RE),
    _h("D2", "REFERENCES_LIBRARY_SECTION", _LIB, regex=_D2_RE),
    _h("D3", "NAMES_STD_ENTITY", _LIB, regex=_D3_RE),
    _h("D4", "NAMESPACE_STD_MUTATION", _LIB, regex=_D4_RE),
    _h(
        "D5",
        "REFERENCES_LWG_LEWG",
        _LIB,
        nli_text="The sentence references an LWG or LEWG issue, defect report, or prior library paper.",
    ),
    _h(
        "D6",
        "REFERENCES_LIBRARY_CONCEPT",
        _LIB,
        nli_text="The sentence discusses a standard library concept or named requirement.",
    ),
    _h(
        "D7",
        "REFERENCES_LIBRARY_CUSTOMIZATION",
        _LIB,
        nli_text="The sentence discusses customization points, ADL-based extension, or trait specialization.",
    ),
    _h("D8", "REFERENCES_CORE_SECTION", _LANG, regex=_D8_RE),
    _h("D9", "NAMES_LANGUAGE_FEATURE", _LANG, regex=_D9_RE),
    _h(
        "D10",
        "GRAMMAR_PRODUCTION",
        _LANG,
        nli_text="The sentence contains or proposes a grammar production in BNF style.",
    ),
    _h(
        "D11",
        "OVERLOAD_RESOLUTION",
        _LANG,
        nli_text="The sentence discusses overload resolution, ADL, or name lookup rules.",
    ),
    _h(
        "D12",
        "TEMPLATE_INSTANTIATION",
        _LANG,
        nli_text="The sentence discusses template instantiation, specialization rules, or SFINAE.",
    ),
    _h(
        "D13",
        "LIFETIME_SEMANTICS",
        _LANG,
        nli_text="The sentence discusses object lifetime, storage duration, or destruction order.",
    ),
    _h(
        "D14",
        "REFERENCES_EWG_CWG",
        _LANG,
        nli_text="The sentence references an EWG or CWG issue, defect report, or prior language paper.",
    ),
    _h(
        "D15",
        "TYPE_SYSTEM_RULES",
        _LANG,
        nli_text="The sentence discusses type deduction, conversion sequences, or type relationships.",
    ),
    _h("M1", "PROPOSES_ADDITION", _DES, regex=_M1_RE),
    _h("M2", "PROPOSES_MODIFICATION", _DES, regex=_M2_RE),
    _h(
        "M3",
        "PROPOSES_REMOVAL",
        _DES,
        nli_text="The sentence proposes deprecating or removing something from the standard.",
    ),
    _h(
        "M4",
        "DESIGN_RATIONALE",
        _DES,
        nli_text="The sentence explains why a design choice was made.",
    ),
    _h("M5", "NAMING_CONVENTION", _DES, regex=_M5_RE),
    _h("M6", "COMPARATIVE_EVALUATION", _DES, regex=_M6_RE),
    _h("M7", "USER_ERGONOMICS", _DES, regex=_M7_RE),
    _h(
        "M8",
        "API_SURFACE_DESCRIPTION",
        _DES,
        nli_text="The sentence describes the shape of a proposed interface or API.",
    ),
    _h("M9", "PURE_EXTENSION_CLAIM", _DES, regex=_M9_RE),
    _h("M10", "SCOPE_BOUNDARY", _DES, regex=_M10_RE),
    _h(
        "M11",
        "IMPLEMENTATION_EVIDENCE",
        _DES,
        nli_text="The sentence reports implementation experience or successful compilation.",
    ),
    _h(
        "M12",
        "EXISTING_PRACTICE",
        _DES,
        nli_text="The sentence appeals to existing practice in real-world codebases or other languages.",
    ),
    _h("M13", "PERFORMANCE_ARGUMENT", _DES, regex=_M13_RE),
    _h("W1", "NORMATIVE_SPECIFICATION", _WOR, regex=_W1_RE),
    _h("W2", "WORDING_DIRECTIVE", _WOR, regex=_W2_RE),
    _h("W3", "STABLE_NAME_EDIT", _WOR, regex=_W3_RE),
    _h(
        "W4",
        "TABLE_MODIFICATION",
        _WOR,
        nli_text="The sentence proposes changes to a table in the standard.",
    ),
    _h(
        "W5",
        "FEATURE_TEST_MACRO",
        _WOR,
        nli_text="The sentence proposes or modifies a feature-test macro.",
    ),
    _h("S1", "AUDIENCE_METADATA", _STR, regex=_S1_RE),
    _h(
        "S2",
        "CROSS_REFERENCE_PAPER",
        _STR,
        nli_text="The sentence references another WG21 paper by document number.",
    ),
    _h("S3", "BACKWARD_COMPATIBILITY", _STR, regex=_S3_RE),
    _h(
        "S4",
        "ABI_DISCUSSION",
        _STR,
        nli_text="The sentence discusses ABI stability or binary compatibility.",
    ),
    _h(
        "S5",
        "POLL_RESULT",
        _STR,
        nli_text="The sentence reports the result of a committee poll or straw poll.",
    ),
)

LIBRARY_DOMAIN = frozenset(h.id for h in CATALOG if h.axis is _LIB)
LANGUAGE_DOMAIN = frozenset(h.id for h in CATALOG if h.axis is _LANG)
DESIGN_MODE = frozenset(h.id for h in CATALOG if h.axis is _DES)
WORDING_MODE = frozenset(h.id for h in CATALOG if h.axis is _WOR)

_NLI_HYPOTHESES: tuple[Hypothesis, ...] = tuple(
    h for h in CATALOG if h.nli_text is not None and h.regex is None
)


def get_hits_from_text(text: str) -> set[str]:
    hits: set[str] = set()
    for hyp in CATALOG:
        if hyp.regex is not None and hyp.regex.search(text) is not None:
            hits.add(hyp.id)
    return hits


def _raw_units_from_input(
    paper_md_or_sentences: str | list[str],
) -> tuple[list[RawSentence], list[SectionType]]:
    """Normalize markdown or a pre-split sentence list into routable units."""
    if isinstance(paper_md_or_sentences, str):
        return (
            split_sentences(paper_md_or_sentences),
            line_section_map(paper_md_or_sentences),
        )

    if isinstance(paper_md_or_sentences, list):
        raw_units: list[RawSentence] = []
        for idx, item in enumerate(paper_md_or_sentences):
            if not isinstance(item, str):
                raise TypeError(
                    "score_hypotheses sentence list items must be str, "
                    f"got {type(item).__name__} at index {idx}",
                )
            raw_units.append(RawSentence(item, 0))
        return raw_units, []

    raise TypeError(
        "score_hypotheses expects str (markdown) or list[str] (sentences), "
        f"got {type(paper_md_or_sentences).__name__}",
    )


def score_hypotheses(
    paper_md_or_sentences: str | list[str],
    *,
    audience: list[str] | None = None,
    classifier: ClassifierBackend | None = None,
    debug_log: list[str] | None = None,
) -> list[Sentence]:
    """Run Stage 1-3: split, section-detect, and score all hypotheses.

    Accepts either full paper markdown or a caller-provided sentence list.
    Markdown runs ``split_sentences`` and ``line_section_map`` so each unit
    inherits section context from headings. A sentence list skips splitting
    and assigns ``SectionType.PREAMBLE`` to every unit (no heading context).

    Regex hits are always applied. When ``classifier`` is an
    ``NliCrossEncoderBackend``, NLI-only catalog hypotheses are scored in
    batch and merged into ``hypothesis_hits``.

    ``audience`` is accepted for API symmetry with ``route_paper``; metadata
    bonus is applied later in aggregation, not here.
    """
    del audience  # reserved for call-site symmetry with route_paper

    raw_units, line_sections = _raw_units_from_input(paper_md_or_sentences)

    sentences: list[Sentence] = []
    for idx, raw in enumerate(raw_units):
        sentences.append(
            Sentence(
                text=raw.text,
                section=section_for_sentence(raw, line_sections),
                index=idx,
                hypothesis_hits=frozenset(get_hits_from_text(raw.text)),
            ),
        )

    if classifier is not None and isinstance(classifier, NliCrossEncoderBackend):
        _apply_nli_scores(sentences, classifier, debug_log)

    return sentences


def _apply_nli_scores(
    sentences: list[Sentence],
    classifier: NliCrossEncoderBackend,
    debug_log: list[str] | None,
) -> None:
    pairs: list[tuple[str, str]] = []
    pair_map: list[tuple[int, str]] = []
    for sent in sentences:
        for hyp in _NLI_HYPOTHESES:
            assert hyp.nli_text is not None
            pairs.append((sent.text, hyp.nli_text))
            pair_map.append((sent.index, hyp.id))

    if not pairs:
        return

    if debug_log is not None:
        debug_log.append("### paper-routing NLI batch\n")
        debug_log.append(f"pairs: {len(pairs)}\n")

    fired, scores = score_entailment_pairs(
        classifier,
        pairs,
        threshold=_ROUTING_NLI_THRESHOLD,
    )

    if debug_log is not None:
        for i, ((premise, _), score) in enumerate(zip(pairs, scores, strict=True)):
            debug_log.append(
                f"- [{i}] entailment={score.get('entailment', 0):.4f} "
                f"hyp={pair_map[i][1]} text={premise[:120]!r}\n",
            )

    updated: dict[int, set[str]] = {s.index: set(s.hypothesis_hits) for s in sentences}
    for (sent_idx, hyp_id), hit in zip(pair_map, fired, strict=True):
        if hit:
            updated[sent_idx].add(hyp_id)

    for i, sent in enumerate(sentences):
        sentences[i] = Sentence(
            text=sent.text,
            section=sent.section,
            index=sent.index,
            hypothesis_hits=frozenset(updated[sent.index]),
        )
