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
from assay.paper_routing.split import RawSentence, split_sentences
from assay.paper_routing.types import HypothesisAxis, SectionType, Sentence

_ROUTING_NLI_THRESHOLD = 0.6
_MIN_SENTENCE_CHARS = 20
_MAX_SENTENCES_PER_PAPER = 3000

# Fallback for any catalog label absent from _SEQCLS_HYPOTHESIS_THRESHOLDS
# below (should not happen for the current 38-label catalog; kept as a
# defensive default if the catalog grows before the next calibration pass).
_ROUTING_SEQCLS_THRESHOLD = 0.25

# Per-label decision thresholds for the fine-tuned MultiLabelClassifierBackend
# head, replacing a single flat cutoff. A flat threshold (this was 0.25)
# applies one operating point to every label regardless of how rare or how
# separable it is; per-label calibration lets rare/hard labels use a much
# lower cutoff (e.g. D4, D7) without forcing well-separated frequent labels
# (e.g. S2, W2) into the same regime.
#
# In-repo sentence labels for training/eval:
# packages/assay/data/golden/sentence_hypo_{train,test}.jsonl.
#
# These per-label cutoffs were calibrated from out-of-fold probabilities on a
# machine-local corpus (often derived from that golden set) using tooling under
# data/routing_tagger/ (k-fold split, train/predict, per-label F1 sweep). That
# directory is not checked into this repo. After regenerating
# per_label_thresholds.json locally, copy values here.
_SEQCLS_HYPOTHESIS_THRESHOLDS: dict[str, float] = {
    "D1": 0.2217,
    "D2": 0.4863,
    "D3": 0.6133,
    "D4": 0.0293,
    "D5": 0.3613,
    "D6": 0.0942,
    "D7": 0.0461,
    "D8": 0.4688,
    "D9": 0.1729,
    "D10": 0.5,
    "D11": 0.0815,
    "D12": 0.3828,
    "D13": 0.0601,
    "D14": 0.5391,
    "D15": 0.2910,
    "M1": 0.1025,
    "M2": 0.5664,
    "M3": 0.0306,
    "M4": 0.2178,
    "M5": 0.0549,
    "M6": 0.1699,
    "M7": 0.1445,
    "M8": 0.3633,
    "M9": 0.1895,
    "M10": 0.0325,
    "M11": 0.1348,
    "M12": 0.1797,
    "M13": 0.0352,
    "W1": 0.4570,
    "W2": 0.6875,
    "W3": 0.4863,
    "W4": 0.1416,
    "W5": 0.1035,
    "S1": 0.2490,
    "S2": 0.2295,
    "S3": 0.1934,
    "S4": 0.1177,
    "S5": 0.1465,
}

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
_D5_RE = re.compile(
    r"(?i)\b(LWG|LEWG|Library\s+Evolution|library\s+evolution)\b|\bLWG\s+\d+",
)
_D6_RE = re.compile(
    r"(?i)\b(Iterator|Allocator\s+model|Ranges|Container\s+requirements|named\s+requirement)\b",
)
_D7_RE = re.compile(
    r"(?i)\b(customization\s+point|users?\s+may\s+specialize|customization\s+point\s+object)\b",
)
_D10_RE = re.compile(
    r"(?i)\b[a-z][a-z0-9]*(?:-[a-z0-9]+)+:\s*"
    r"|(?:^|\n)\s*[a-z][a-z0-9]*(?:-[a-z0-9]+)+\s*::="
    r"|\blambda-expression\b|\bassignment-expression\b",
)
_D11_RE = re.compile(
    r"(?i)\b(overload\s+resolution|argument-dependent\s+lookup|name\s+lookup|"
    r"candidate\s+set|ADL)\b",
)
_D12_RE = re.compile(
    r"(?i)\b(template\s+(argument\s+deduction|instantiation)|substitution\s+failure|SFINAE)\b",
)
_D13_RE = re.compile(
    r"(?i)\b(lifetime|storage\s+duration|temporary\s+materialization|destruction\s+order)\b",
)
_D14_RE = re.compile(
    r"(?i)\b(EWG|CWG|Evolution\s+Working\s+Group|Core\s+Working\s+Group)\b|"
    r"\b(?:CWG|EWG)\s+\d+",
)
_D15_RE = re.compile(
    r"(?i)\b(implicit\s+conversion\s+sequence|decltype|type\s+deduction)\b",
)
_M3_RE = re.compile(
    r"(?i)\b(should\s+be\s+deprecated|propose\s+removing|proposes?\s+removing)\b",
)
_M4_RE = re.compile(
    r"(?i)\b(for\s+consistency\s+with|for\s+several\s+reasons|because)\b",
)
_M8_RE = re.compile(
    r"(?i)\b(the\s+function\s+takes|returns\s+a|template\s+parameter)\b",
)
_M11_RE = re.compile(r"(?i)\b(successfully\s+compiled|implemented\s+in)\b")
_M12_RE = re.compile(
    r"(?i)\b(existing\s+practice\s+in\s+Boost|other\s+languages\s+provide|widely\s+used)\b",
)
_W4_RE = re.compile(r"(?i)\b(Table\s+\d+|modify\s+Table|add\s+a\s+row\s+to\s+Table)\b")
_W5_RE = re.compile(r"(?i)__cpp|__has_cpp_attribute|feature-test\s+macro")
_S2_RE = re.compile(r"\b[PND]\d{4}R\d+\b")
_S4_RE = re.compile(
    r"(?i)\b(ABI\s+break|binary\s+compatibility|layout\s+compatible)\b",
)
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
    _h(
        "D1",
        "REFERENCES_LIBRARY_HEADER",
        _LIB,
        regex=_D1_RE,
        nli_text="The sentence names a standard library header in angle brackets.",
    ),
    _h(
        "D2",
        "REFERENCES_LIBRARY_SECTION",
        _LIB,
        regex=_D2_RE,
        nli_text="The sentence cites a library clause number or stable name from the standard.",
    ),
    _h(
        "D3",
        "NAMES_STD_ENTITY",
        _LIB,
        regex=_D3_RE,
        nli_text=(
            "The sentence names a specific type, function, template, or constant "
            "that lives in the standard library."
        ),
    ),
    _h(
        "D4",
        "NAMESPACE_STD_MUTATION",
        _LIB,
        regex=_D4_RE,
        nli_text=(
            "The sentence explicitly discusses adding to or modifying entities "
            "in namespace std."
        ),
    ),
    _h(
        "D5",
        "REFERENCES_LWG_LEWG",
        _LIB,
        regex=_D5_RE,
        nli_text=(
            "The sentence references an LWG or LEWG issue, defect report, "
            "or prior library paper."
        ),
    ),
    _h(
        "D6",
        "REFERENCES_LIBRARY_CONCEPT",
        _LIB,
        regex=_D6_RE,
        nli_text=(
            "The sentence discusses a standard library concept or named requirement."
        ),
    ),
    _h(
        "D7",
        "REFERENCES_LIBRARY_CUSTOMIZATION",
        _LIB,
        regex=_D7_RE,
        nli_text=(
            "The sentence discusses customization points, ADL-based extension, "
            "or trait specialization in a library context."
        ),
    ),
    _h(
        "D8",
        "REFERENCES_CORE_SECTION",
        _LANG,
        regex=_D8_RE,
        nli_text="The sentence cites a core language clause number or stable name.",
    ),
    _h(
        "D9",
        "NAMES_LANGUAGE_FEATURE",
        _LANG,
        regex=_D9_RE,
        nli_text="The sentence names a core language feature by its recognized name.",
    ),
    _h(
        "D10",
        "GRAMMAR_PRODUCTION",
        _LANG,
        regex=_D10_RE,
        nli_text=(
            "The sentence contains or proposes a grammar production in BNF style."
        ),
    ),
    _h(
        "D11",
        "OVERLOAD_RESOLUTION",
        _LANG,
        regex=_D11_RE,
        nli_text=(
            "The sentence discusses overload resolution, ADL, or name lookup rules."
        ),
    ),
    _h(
        "D12",
        "TEMPLATE_INSTANTIATION",
        _LANG,
        regex=_D12_RE,
        nli_text=(
            "The sentence discusses template instantiation, specialization rules, or SFINAE."
        ),
    ),
    _h(
        "D13",
        "LIFETIME_SEMANTICS",
        _LANG,
        regex=_D13_RE,
        nli_text=(
            "The sentence discusses object lifetime, storage duration, or destruction order."
        ),
    ),
    _h(
        "D14",
        "REFERENCES_EWG_CWG",
        _LANG,
        regex=_D14_RE,
        nli_text=(
            "The sentence references an EWG or CWG issue, defect report, "
            "or prior language paper."
        ),
    ),
    _h(
        "D15",
        "TYPE_SYSTEM_RULES",
        _LANG,
        regex=_D15_RE,
        nli_text=(
            "The sentence discusses type deduction, conversion sequences, "
            "or type relationships as language rules."
        ),
    ),
    _h(
        "M1",
        "PROPOSES_ADDITION",
        _DES,
        regex=_M1_RE,
        nli_text="The sentence explicitly proposes adding new functionality to the standard.",
    ),
    _h(
        "M2",
        "PROPOSES_MODIFICATION",
        _DES,
        regex=_M2_RE,
        nli_text="The sentence proposes changing existing behavior or specification.",
    ),
    _h(
        "M3",
        "PROPOSES_REMOVAL",
        _DES,
        regex=_M3_RE,
        nli_text="The sentence proposes deprecating or removing something from the standard.",
    ),
    _h(
        "M4",
        "DESIGN_RATIONALE",
        _DES,
        regex=_M4_RE,
        nli_text="The sentence explains why a design choice was made.",
    ),
    _h(
        "M5",
        "NAMING_CONVENTION",
        _DES,
        regex=_M5_RE,
        nli_text="The sentence discusses naming patterns, suffixes, prefixes, or naming policy.",
    ),
    _h(
        "M6",
        "COMPARATIVE_EVALUATION",
        _DES,
        regex=_M6_RE,
        nli_text=(
            "The sentence compares two or more alternative designs, syntaxes, or API forms."
        ),
    ),
    _h(
        "M7",
        "USER_ERGONOMICS",
        _DES,
        regex=_M7_RE,
        nli_text=(
            "The sentence argues about developer experience, learnability, verbosity, "
            "or usability."
        ),
    ),
    _h(
        "M8",
        "API_SURFACE_DESCRIPTION",
        _DES,
        regex=_M8_RE,
        nli_text="The sentence describes the shape of a proposed interface or API.",
    ),
    _h(
        "M9",
        "PURE_EXTENSION_CLAIM",
        _DES,
        regex=_M9_RE,
        nli_text="The sentence claims the change is purely additive and non-breaking.",
    ),
    _h(
        "M10",
        "SCOPE_BOUNDARY",
        _DES,
        regex=_M10_RE,
        nli_text="The sentence bounds what the proposal does or does not affect.",
    ),
    _h(
        "M11",
        "IMPLEMENTATION_EVIDENCE",
        _DES,
        regex=_M11_RE,
        nli_text=(
            "The sentence reports implementation experience or successful compilation."
        ),
    ),
    _h(
        "M12",
        "EXISTING_PRACTICE",
        _DES,
        regex=_M12_RE,
        nli_text=(
            "The sentence appeals to existing practice in real-world codebases "
            "or other languages."
        ),
    ),
    _h(
        "M13",
        "PERFORMANCE_ARGUMENT",
        _DES,
        regex=_M13_RE,
        nli_text=(
            "The sentence argues about runtime or compile-time performance characteristics."
        ),
    ),
    _h(
        "W1",
        "NORMATIVE_SPECIFICATION",
        _WOR,
        regex=_W1_RE,
        nli_text="The sentence contains normative specification language.",
    ),
    _h(
        "W2",
        "WORDING_DIRECTIVE",
        _WOR,
        regex=_W2_RE,
        nli_text="The sentence instructs an editorial change to the standard text.",
    ),
    _h(
        "W3",
        "STABLE_NAME_EDIT",
        _WOR,
        regex=_W3_RE,
        nli_text="The sentence targets a specific stable name for textual modification.",
    ),
    _h(
        "W4",
        "TABLE_MODIFICATION",
        _WOR,
        regex=_W4_RE,
        nli_text="The sentence proposes changes to a table in the standard.",
    ),
    _h(
        "W5",
        "FEATURE_TEST_MACRO",
        _WOR,
        regex=_W5_RE,
        nli_text="The sentence proposes or modifies a feature-test macro.",
    ),
    _h(
        "S1",
        "AUDIENCE_METADATA",
        _STR,
        regex=_S1_RE,
        nli_text="The paper's metadata explicitly names a target audience.",
    ),
    _h(
        "S2",
        "CROSS_REFERENCE_PAPER",
        _STR,
        regex=_S2_RE,
        nli_text="The sentence references another WG21 paper by document number.",
    ),
    _h(
        "S3",
        "BACKWARD_COMPATIBILITY",
        _STR,
        regex=_S3_RE,
        nli_text="The sentence discusses backward compatibility or migration burden.",
    ),
    _h(
        "S4",
        "ABI_DISCUSSION",
        _STR,
        regex=_S4_RE,
        nli_text="The sentence discusses ABI stability or binary compatibility.",
    ),
    _h(
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

    sentences: list[Sentence] = []
    for idx, raw in enumerate(raw_units):
        if len(raw.text) < _MIN_SENTENCE_CHARS:
            continue
        if len(sentences) > _MAX_SENTENCES_PER_PAPER:
            break

        hits = get_hits_from_text(raw.text) if use_regex else set()
        sentences.append(
            Sentence(
                text=raw.text,
                section=section_for_sentence(raw, line_sections),
                index=idx,
                hypothesis_hits=frozenset(hits),
            ),
        )

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

    updated: dict[int, set[str]] = {s.index: set(s.hypothesis_hits) for s in sentences}
    for sent, scores in zip(sentences, batch_scores, strict=True):
        for hyp_id, score in scores.items():
            threshold = _SEQCLS_HYPOTHESIS_THRESHOLDS.get(
                hyp_id, _ROUTING_SEQCLS_THRESHOLD
            )
            if score >= threshold:
                updated[sent.index].add(hyp_id)
            if debug_log is not None and score >= threshold:
                debug_log.append(
                    f"- hyp={hyp_id} score={score:.4f} threshold={threshold:.4f} "
                    f"text={sent.text[:120]!r}\n",
                )

    _rebuild_with_hits(sentences, updated)
