#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Stage 3: hypothesis catalog and scoring."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from pipeline.classifier_backends import (
    ClassifierBackend,
    MultiLabelClassifierBackend,
    NliCrossEncoderBackend,
)
from pipeline.nli_batch import score_entailment_pairs
from assay.paper_routing.sections import line_section_map, section_for_sentence
from assay.paper_routing.nli_thresholds import (
    _ROUTING_NLI_THRESHOLD_FALLBACK as _ROUTING_NLI_THRESHOLD,
    load_nli_hypothesis_thresholds,
)
from assay.paper_routing.seqcls_thresholds import (
    _ROUTING_SEQCLS_THRESHOLD_FALLBACK,
    load_seqcls_hypothesis_thresholds,
)
from assay.paper_routing.sample import sample_sentences_with_summary
from assay.paper_routing.split import RawSentence, split_sentences
from assay.paper_routing.types import HypothesisAxis, SectionType, Sentence

_MIN_SENTENCE_CHARS = 20
_MAX_SENTENCES_PER_PAPER = 300
SAMPLING_METHOD = "prefix"

# D1 REFERENCES_LIBRARY_HEADER
_D1_RE = re.compile(r"<\s*[a-z_][a-z0-9_]*\s*>")
# D2 REFERENCES_LIBRARY_SECTION
_D2_RE = re.compile(r"\b\d{1,2}\.\d+(?:\.\d+)*\s+\[[\w.]+\]")
# D3 NAMES_STD_ENTITY
_D3_RE = re.compile(
    r"\bstd::|"
    r"\b\w+_v\b|\b\w+_t\b|"
    r"\b(is_same|is_convertible|tuple_size|decay_t|enable_if|type_traits)\b",
    re.IGNORECASE,
)
# D4 NAMESPACE_STD_MUTATION
_D4_RE = re.compile(
    r"(?i)\bnamespace\s+std\b|"
    r"\b(?:standard\s+)?library\b.{0,60}?\b(?:should|shall|must|will|needs?\s+to)\s+be\s+"
    r"(?:updated|modified|changed|extended|amended)\b|"
    r"\b(?:should|shall|must|will|needs?\s+to)\s+be\s+"
    r"(?:updated|modified|changed|extended|amended)\b.{0,60}?\b(?:standard\s+)?library\b"
)
# D8 REFERENCES_CORE_SECTION
_D8_RE = re.compile(
    r"\[(?:expr|dcl|class|stmt|decl|basic|conv|temp|cpp|lex)\.[\w.]+\]|"
    r"\b(?:[1-9]|1[0-6])\.\d+(?:\.\d+)*\s+\[",
    re.IGNORECASE,
)
# D9 NAMES_LANGUAGE_FEATURE
_D9_RE = re.compile(
    r"(?i)\b(concepts?|modules?|coroutines?|structured\s+bindings?|constexpr|"
    r"variable\s+templates?|ranges?|attributes?|lambdas?)\b",
)
# M1 PROPOSES_ADDITION
_M1_RE = re.compile(
    r"(?i)\b(proposal\s+to\s+add|we\s+propose|this\s+paper\s+introduces?|this\s+proposal\s+adds?)\b",
)
# M2 PROPOSES_MODIFICATION
_M2_RE = re.compile(
    r"(?i)\b(?:should|shall|must|will|needs?\s+to)\s+be\s+"
    r"(?:changed|modified|updated|revised|amended)\b|"
    r"\bwe\s+modify\b|"
    r"\bupdat(?:e|ed)\s+accordingly\b",
)
# M5 NAMING_CONVENTION
_M5_RE = re.compile(r"(?i)\b(_v\s+suffix|_t\s+suffix|naming\s+convention)\b")
# M6 COMPARATIVE_EVALUATION
_M6_RE = re.compile(r"(?i)\b(superior\s+to|compared\s+to|alternative\s+approach)\b")
# M7 USER_ERGONOMICS
_M7_RE = re.compile(
    r"(?i)\b(simple\s+to\s+learn|less\s+verbose|easier\s+to|unintuitive)\b",
)
# M9 PURE_EXTENSION_CLAIM
_M9_RE = re.compile(
    r"(?i)\b(pure\s+extension|no\s+breaking\s+changes?|backward\s+compatible)\b"
)
# M10 SCOPE_BOUNDARY
_M10_RE = re.compile(
    r"(?i)\b(does(?:n't| not)\s+(?:touch|affect)|limited\s+to|out\s+of\s+scope)\b",
)
# M13 PERFORMANCE_ARGUMENT
_M13_RE = re.compile(
    r"(?i)\b(zero\s+overhead|compile[- ]time\s+cost|no\s+runtime\s+penalty)\b",
)
# W1 NORMATIVE_SPECIFICATION
_W1_RE = re.compile(
    r"(?i)\b(shall\b|Effects:|Returns:|Mandates:|Preconditions:)\b",
)
# W2 WORDING_DIRECTIVE
_W2_RE = re.compile(
    r"(?i)\b(add\s+the\s+following|modify\s+paragraph|strike\b|insert\s+before)\b|(?:,\s*)?add:\s*$",
)
# W3 STABLE_NAME_EDIT
_W3_RE = re.compile(
    r"\b\d{1,2}\.\d+(?:\.\d+)*\s+\[[\w.]+\].*(?:modify|add)", re.IGNORECASE
)
# S3 BACKWARD_COMPATIBILITY
_S3_RE = re.compile(
    r"(?i)\b(does(?:n't| not)\s+affect\s+existing\s+user\s+code|migration\s+path)\b",
)
# S1 AUDIENCE_METADATA
_S1_RE = re.compile(r"(?i)\baudience:\s*")
# D5 REFERENCES_LWG_LEWG
_D5_RE = re.compile(
    r"(?i)\b(LWG|LEWG|Library\s+Evolution|library\s+evolution)\b|\bLWG\s+\d+",
)
# D6 REFERENCES_LIBRARY_CONCEPT
_D6_RE = re.compile(
    r"(?i)\b(Iterator|Allocator\s+model|Ranges|Container\s+requirements|named\s+requirement)\b",
)
# D7 REFERENCES_LIBRARY_CUSTOMIZATION
_D7_RE = re.compile(
    r"(?i)\b(customization\s+point|users?\s+may\s+specialize|customization\s+point\s+object)\b",
)
# D10 GRAMMAR_PRODUCTION
_D10_RE = re.compile(
    r"(?i)\b[a-z][a-z0-9]*(?:-[a-z0-9]+)+:\s*"
    r"|(?:^|\n)\s*[a-z][a-z0-9]*(?:-[a-z0-9]+)+\s*::="
    r"|\blambda-expression\b|\bassignment-expression\b",
)
# D11 OVERLOAD_RESOLUTION
_D11_RE = re.compile(
    r"(?i)\b(overload\s+resolution|argument-dependent\s+lookup|name\s+lookup|"
    r"candidate\s+set|ADL)\b",
)
# D12 TEMPLATE_INSTANTIATION
_D12_RE = re.compile(
    r"(?i)\b(template\s+(argument\s+deduction|instantiation)|substitution\s+failure|SFINAE)\b",
)
# D13 LIFETIME_SEMANTICS
_D13_RE = re.compile(
    r"(?i)\b(lifetime|storage\s+duration|temporary\s+materialization|destruction\s+order)\b",
)
# D14 REFERENCES_EWG_CWG
_D14_RE = re.compile(
    r"(?i)\b(EWG|CWG|Evolution\s+Working\s+Group|Core\s+Working\s+Group)\b|"
    r"\b(?:CWG|EWG)\s+\d+",
)
# D15 TYPE_SYSTEM_RULES
_D15_RE = re.compile(
    r"(?i)\b(implicit\s+conversion\s+sequence|decltype|type\s+deduction)\b",
)
# M3 PROPOSES_REMOVAL
_M3_RE = re.compile(
    r"(?i)\b(should\s+be\s+deprecated|propose\s+removing|proposes?\s+removing)\b",
)
# M4 DESIGN_RATIONALE
_M4_RE = re.compile(
    r"(?i)\b(for\s+consistency\s+with|for\s+several\s+reasons|because)\b",
)
# M8 API_SURFACE_DESCRIPTION
_M8_RE = re.compile(
    r"(?i)\b(the\s+function\s+takes|returns\s+a|template\s+parameter)\b",
)
# M11 IMPLEMENTATION_EVIDENCE
_M11_RE = re.compile(r"(?i)\b(successfully\s+compiled|implemented\s+in)\b")
# M12 EXISTING_PRACTICE
_M12_RE = re.compile(
    r"(?i)\b(existing\s+practice\s+in\s+Boost|other\s+languages\s+provide|widely\s+used)\b",
)
# W4 TABLE_MODIFICATION
_W4_RE = re.compile(r"(?i)\b(Table\s+\d+|modify\s+Table|add\s+a\s+row\s+to\s+Table)\b")
# W5 FEATURE_TEST_MACRO
_W5_RE = re.compile(r"(?i)__cpp|__has_cpp_attribute|feature-test\s+macro")
# S2 CROSS_REFERENCE_PAPER
_S2_RE = re.compile(r"\b[PND]\d{4}R\d+\b")
# S4 ABI_DISCUSSION
_S4_RE = re.compile(
    r"(?i)\b(ABI\s+break|binary\s+compatibility|layout\s+compatible)\b",
)
# S5 POLL_RESULT
_S5_RE = re.compile(
    r"(?i)\b(unanimous\s+consent|no\s+objection|poll\s+result|straw\s+poll|SF/F/N/A/SA)\b",
)


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


_LIB = HypothesisAxis.LIBRARY_DOMAIN
_LANG = HypothesisAxis.LANGUAGE_DOMAIN
_DES = HypothesisAxis.DESIGN_MODE
_WOR = HypothesisAxis.WORDING_MODE
_STR = HypothesisAxis.STRUCTURAL


CATALOG: tuple[Hypothesis, ...] = (
    Hypothesis(
        "D1",
        "REFERENCES_LIBRARY_HEADER",
        _LIB,
        regex=_D1_RE,
        nli_text="The sentence names a standard library header in angle brackets.",
    ),
    Hypothesis(
        "D2",
        "REFERENCES_LIBRARY_SECTION",
        _LIB,
        regex=_D2_RE,
        nli_text="The sentence cites a library clause number or stable name from the standard.",
    ),
    Hypothesis(
        "D3",
        "NAMES_STD_ENTITY",
        _LIB,
        regex=_D3_RE,
        nli_text=(
            "The sentence names a specific type, function, template, or constant "
            "that lives in the standard library."
        ),
    ),
    Hypothesis(
        "D4",
        "NAMESPACE_STD_MUTATION",
        _LIB,
        regex=_D4_RE,
        nli_text=(
            "The sentence explicitly discusses adding to or modifying entities "
            "in namespace std."
        ),
    ),
    Hypothesis(
        "D5",
        "REFERENCES_LWG_LEWG",
        _LIB,
        regex=_D5_RE,
        nli_text=(
            "The sentence references an LWG or LEWG issue, defect report, "
            "or prior library paper."
        ),
    ),
    Hypothesis(
        "D6",
        "REFERENCES_LIBRARY_CONCEPT",
        _LIB,
        regex=_D6_RE,
        nli_text=(
            "The sentence discusses a standard library concept or named requirement."
        ),
    ),
    Hypothesis(
        "D7",
        "REFERENCES_LIBRARY_CUSTOMIZATION",
        _LIB,
        regex=_D7_RE,
        nli_text=(
            "The sentence discusses customization points, ADL-based extension, "
            "or trait specialization in a library context."
        ),
    ),
    Hypothesis(
        "D8",
        "REFERENCES_CORE_SECTION",
        _LANG,
        regex=_D8_RE,
        nli_text="The sentence cites a core language clause number or stable name.",
    ),
    Hypothesis(
        "D9",
        "NAMES_LANGUAGE_FEATURE",
        _LANG,
        regex=_D9_RE,
        nli_text="The sentence names a core language feature by its recognized name.",
    ),
    Hypothesis(
        "D10",
        "GRAMMAR_PRODUCTION",
        _LANG,
        regex=_D10_RE,
        nli_text=(
            "The sentence contains or proposes a grammar production in BNF style."
        ),
    ),
    Hypothesis(
        "D11",
        "OVERLOAD_RESOLUTION",
        _LANG,
        regex=_D11_RE,
        nli_text=(
            "The sentence discusses overload resolution, ADL, or name lookup rules."
        ),
    ),
    Hypothesis(
        "D12",
        "TEMPLATE_INSTANTIATION",
        _LANG,
        regex=_D12_RE,
        nli_text=(
            "The sentence discusses template instantiation, specialization rules, or SFINAE."
        ),
    ),
    Hypothesis(
        "D13",
        "LIFETIME_SEMANTICS",
        _LANG,
        regex=_D13_RE,
        nli_text=(
            "The sentence discusses object lifetime, storage duration, or destruction order."
        ),
    ),
    Hypothesis(
        "D14",
        "REFERENCES_EWG_CWG",
        _LANG,
        regex=_D14_RE,
        nli_text=(
            "The sentence references an EWG or CWG issue, defect report, "
            "or prior language paper."
        ),
    ),
    Hypothesis(
        "D15",
        "TYPE_SYSTEM_RULES",
        _LANG,
        regex=_D15_RE,
        nli_text=(
            "The sentence discusses type deduction, conversion sequences, "
            "or type relationships as language rules."
        ),
    ),
    Hypothesis(
        "M1",
        "PROPOSES_ADDITION",
        _DES,
        regex=_M1_RE,
        nli_text="The sentence explicitly proposes adding new functionality to the standard.",
    ),
    Hypothesis(
        "M2",
        "PROPOSES_MODIFICATION",
        _DES,
        regex=_M2_RE,
        nli_text="The sentence proposes changing existing behavior or specification.",
    ),
    Hypothesis(
        "M3",
        "PROPOSES_REMOVAL",
        _DES,
        regex=_M3_RE,
        nli_text="The sentence proposes deprecating or removing something from the standard.",
    ),
    Hypothesis(
        "M4",
        "DESIGN_RATIONALE",
        _DES,
        regex=_M4_RE,
        nli_text="The sentence explains why a design choice was made.",
    ),
    Hypothesis(
        "M5",
        "NAMING_CONVENTION",
        _DES,
        regex=_M5_RE,
        nli_text="The sentence discusses naming patterns, suffixes, prefixes, or naming policy.",
    ),
    Hypothesis(
        "M6",
        "COMPARATIVE_EVALUATION",
        _DES,
        regex=_M6_RE,
        nli_text=(
            "The sentence compares two or more alternative designs, syntaxes, or API forms."
        ),
    ),
    Hypothesis(
        "M7",
        "USER_ERGONOMICS",
        _DES,
        regex=_M7_RE,
        nli_text=(
            "The sentence argues about developer experience, learnability, verbosity, "
            "or usability."
        ),
    ),
    Hypothesis(
        "M8",
        "API_SURFACE_DESCRIPTION",
        _DES,
        regex=_M8_RE,
        nli_text="The sentence describes the shape of a proposed interface or API.",
    ),
    Hypothesis(
        "M9",
        "PURE_EXTENSION_CLAIM",
        _DES,
        regex=_M9_RE,
        nli_text="The sentence claims the change is purely additive and non-breaking.",
    ),
    Hypothesis(
        "M10",
        "SCOPE_BOUNDARY",
        _DES,
        regex=_M10_RE,
        nli_text="The sentence bounds what the proposal does or does not affect.",
    ),
    Hypothesis(
        "M11",
        "IMPLEMENTATION_EVIDENCE",
        _DES,
        regex=_M11_RE,
        nli_text=(
            "The sentence reports implementation experience or successful compilation."
        ),
    ),
    Hypothesis(
        "M12",
        "EXISTING_PRACTICE",
        _DES,
        regex=_M12_RE,
        nli_text=(
            "The sentence appeals to existing practice in real-world codebases "
            "or other languages."
        ),
    ),
    Hypothesis(
        "M13",
        "PERFORMANCE_ARGUMENT",
        _DES,
        regex=_M13_RE,
        nli_text=(
            "The sentence argues about runtime or compile-time performance characteristics."
        ),
    ),
    Hypothesis(
        "W1",
        "NORMATIVE_SPECIFICATION",
        _WOR,
        regex=_W1_RE,
        nli_text="The sentence contains normative specification language.",
    ),
    Hypothesis(
        "W2",
        "WORDING_DIRECTIVE",
        _WOR,
        regex=_W2_RE,
        nli_text="The sentence instructs an editorial change to the standard text.",
    ),
    Hypothesis(
        "W3",
        "STABLE_NAME_EDIT",
        _WOR,
        regex=_W3_RE,
        nli_text="The sentence targets a specific stable name for textual modification.",
    ),
    Hypothesis(
        "W4",
        "TABLE_MODIFICATION",
        _WOR,
        regex=_W4_RE,
        nli_text="The sentence proposes changes to a table in the standard.",
    ),
    Hypothesis(
        "W5",
        "FEATURE_TEST_MACRO",
        _WOR,
        regex=_W5_RE,
        nli_text="The sentence proposes or modifies a feature-test macro.",
    ),
    Hypothesis(
        "S1",
        "AUDIENCE_METADATA",
        _STR,
        regex=_S1_RE,
        nli_text="The paper's metadata explicitly names a target audience.",
    ),
    Hypothesis(
        "S2",
        "CROSS_REFERENCE_PAPER",
        _STR,
        regex=_S2_RE,
        nli_text="The sentence references another WG21 paper by document number.",
    ),
    Hypothesis(
        "S3",
        "BACKWARD_COMPATIBILITY",
        _STR,
        regex=_S3_RE,
        nli_text="The sentence discusses backward compatibility or migration burden.",
    ),
    Hypothesis(
        "S4",
        "ABI_DISCUSSION",
        _STR,
        regex=_S4_RE,
        nli_text="The sentence discusses ABI stability or binary compatibility.",
    ),
    Hypothesis(
        "S5",
        "POLL_RESULT",
        _STR,
        regex=_S5_RE,
        nli_text="The sentence reports the result of a committee poll or straw poll.",
    ),
)

LIBRARY_DOMAIN = frozenset(h.id for h in CATALOG if h.axis is _LIB)
LANGUAGE_DOMAIN = frozenset(h.id for h in CATALOG if h.axis is _LANG)
DESIGN_MODE = frozenset(h.id for h in CATALOG if h.axis is _DES)
WORDING_MODE = frozenset(h.id for h in CATALOG if h.axis is _WOR)

# Shared with sustain.py's performance_sustained_count and features.py.
PERFORMANCE_ARGUMENT_ID = "M13"

_NLI_HYPOTHESES: tuple[Hypothesis, ...] = tuple(
    h for h in CATALOG if h.nli_text is not None
)

_CATALOG_IDS = frozenset(h.id for h in CATALOG)


def _classifier_sort_key(backend: ClassifierBackend) -> tuple[str, str]:
    model_id = getattr(backend, "model_id", "")
    return (type(backend).__name__, model_id)


def _rebuild_with_hits(
    sentences: list[Sentence],
    updated: dict[int, set[str]],
) -> None:
    for i, sent in enumerate(sentences):
        sentences[i] = Sentence(
            text=sent.text,
            section=sent.section,
            index=sent.index,
            hypothesis_hits=frozenset(updated[sent.index]),
        )


def _resolve_classifiers(
    classifiers: ClassifierBackend | Sequence[ClassifierBackend] | None,
) -> tuple[ClassifierBackend, ...]:
    if classifiers is None:
        return ()
    if isinstance(classifiers, ClassifierBackend):
        return (classifiers,)
    resolved = tuple(classifiers)
    for item in resolved:
        if not isinstance(item, ClassifierBackend):
            raise TypeError(
                "score_hypotheses classifiers sequence items must be "
                f"ClassifierBackend, got {type(item).__name__}",
            )
    return tuple(sorted(resolved, key=_classifier_sort_key))


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


def _build_filtered_sentences(
    raw_units: list[RawSentence],
    line_sections: list[SectionType],
) -> list[Sentence]:
    """Length-eligible units with empty hits and stable indices among kept rows."""
    sentences: list[Sentence] = []
    for raw in raw_units:
        if len(raw.text) < _MIN_SENTENCE_CHARS:
            continue
        sentences.append(
            Sentence(
                text=raw.text,
                section=section_for_sentence(raw, line_sections),
                index=len(sentences),
                hypothesis_hits=frozenset(),
            ),
        )
    return sentences


def _apply_regex_hits(sentences: list[Sentence]) -> list[Sentence]:
    return [
        Sentence(
            text=sent.text,
            section=sent.section,
            index=sent.index,
            hypothesis_hits=frozenset(get_hits_from_text(sent.text)),
        )
        for sent in sentences
    ]


def score_hypotheses(
    paper_md_or_sentences: str | list[str],
    *,
    audience: list[str] | None = None,
    classifiers: ClassifierBackend | Sequence[ClassifierBackend] | None = None,
    use_regex: bool = True,
    debug_log: list[str] | None = None,
) -> list[Sentence]:
    """Run Stage 1-3: split, section-detect, and score all hypotheses.

    Accepts either full paper markdown or a caller-provided sentence list.
    Markdown runs ``split_sentences`` and ``line_section_map`` so each unit
    inherits section context from headings. A sentence list skips splitting
    and assigns ``SectionType.PREAMBLE`` to every unit (no heading context).

    When ``use_regex`` is true (default), regex catalog hypotheses are scored
    via ``get_hits_from_text``. ``classifiers`` is an optional single backend
    or ordered sequence of backends (not the SERVICES.toml slot dict on
    ``StepContext``). Each backend adds hits on top:

    - ``NliCrossEncoderBackend``: every catalog hypothesis with ``nli_text``, in batch.
    - ``MultiLabelClassifierBackend``: fine-tuned multi-label head over the
      intersection of checkpoint labels and the catalog.

    ``audience`` is accepted for API symmetry with ``route_paper``; metadata
    bonus is applied later in aggregation, not here.
    """
    del audience  # reserved for call-site symmetry with route_paper

    resolved = _resolve_classifiers(classifiers)

    raw_units, line_sections = _raw_units_from_input(paper_md_or_sentences)

    filtered = _build_filtered_sentences(raw_units, line_sections)
    sentences, sample_summary = sample_sentences_with_summary(
        filtered,
        cap=_MAX_SENTENCES_PER_PAPER,
    )
    if sample_summary is not None and debug_log is not None:
        debug_log.append(sample_summary)

    if use_regex:
        sentences = _apply_regex_hits(sentences)

    for backend in resolved:
        if isinstance(backend, NliCrossEncoderBackend):
            _apply_nli_scores(sentences, backend, debug_log)
        elif isinstance(backend, MultiLabelClassifierBackend):
            _apply_seqcls_scores(sentences, backend, debug_log)
        else:
            raise TypeError(
                "score_hypotheses classifiers must be NliCrossEncoderBackend "
                f"or MultiLabelClassifierBackend, got {type(backend).__name__}",
            )

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

    _, scores = score_entailment_pairs(classifier, pairs)
    thresholds = load_nli_hypothesis_thresholds()

    if debug_log is not None:
        for i, ((premise, _), score) in enumerate(zip(pairs, scores, strict=True)):
            debug_log.append(
                f"- [{i}] entailment={score.get('entailment', 0):.4f} "
                f"hyp={pair_map[i][1]} text={premise[:120]!r}\n",
            )

    updated: dict[int, set[str]] = {s.index: set(s.hypothesis_hits) for s in sentences}
    for (sent_idx, hyp_id), score in zip(pair_map, scores, strict=True):
        threshold = thresholds.get(hyp_id, _ROUTING_NLI_THRESHOLD)
        if score.get("entailment", 0.0) >= threshold:
            updated[sent_idx].add(hyp_id)

    _rebuild_with_hits(sentences, updated)


def _apply_seqcls_scores(
    sentences: list[Sentence],
    classifier: MultiLabelClassifierBackend,
    debug_log: list[str] | None,
) -> None:
    candidate_labels = sorted(set(classifier.labels) & _CATALOG_IDS)
    if not candidate_labels or not sentences:
        return

    if debug_log is not None:
        debug_log.append("### paper-routing seqcls batch\n")
        debug_log.append(
            f"sentences: {len(sentences)} labels: {len(candidate_labels)}\n",
        )

    texts = [sent.text for sent in sentences]
    batch_scores = classifier.classify(
        texts,
        candidate_labels,
        multi_label=True,
    )
    thresholds = load_seqcls_hypothesis_thresholds()

    updated: dict[int, set[str]] = {s.index: set(s.hypothesis_hits) for s in sentences}
    for sent, scores in zip(sentences, batch_scores, strict=True):
        for hyp_id, score in scores.items():
            threshold = thresholds.get(hyp_id, _ROUTING_SEQCLS_THRESHOLD_FALLBACK)
            if score >= threshold:
                updated[sent.index].add(hyp_id)
            if debug_log is not None and score >= threshold:
                debug_log.append(
                    f"- hyp={hyp_id} score={score:.4f} threshold={threshold:.4f} "
                    f"text={sent.text[:120]!r}\n",
                )

    _rebuild_with_hits(sentences, updated)
