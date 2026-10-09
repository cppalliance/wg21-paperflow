#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Deterministic grounding of LLM-cited evidence spans.

Every ``EvidenceSpan`` the LLM quotes is verified post-hoc against the paper
markdown before it is trusted. A quote that cannot be located is dropped as
ungrounded. Library returns data; no writes, no LLM, no network.

The exact tier is a port of langextract's monotonic exact-occurrence DP
(``resolver.py``, Copyright Google LLC, Apache-2.0; see
``packages/whisker/THIRD_PARTY_NOTICES.md``): repeated evidence phrases map to
successive non-overlapping occurrences in model-output order instead of the
first substring hit, and every exact match carries its ``(start, end)`` char
interval in the raw markdown. langextract's looser LCS fuzzy tier (0.75 ratio,
1/3 density) is deliberately NOT ported: its own oracle test codifies gapped
wrong-span acceptance. Our fuzzy tier keeps ``EVIDENCE_FUZZY_FLOOR``.
"""

from __future__ import annotations

import bisect
import operator
import re
import unicodedata
from dataclasses import dataclass
from typing import NamedTuple

from rapidfuzz.fuzz import partial_ratio

from whisker.llm.constants import (
    EVIDENCE_FUZZY_FLOOR,
    EVIDENCE_MIN_FUZZY_CHARS,
    PAGE_QUOTE_MAX_DIFFS,
)
from whisker.llm.models import EvidenceSpan
from whisker.metrics import normalized_text

# Alignment statuses. "exact": the quote's token sequence was located at a
# concrete char interval by the monotonic DP and survived the post-alignment
# guard. "fuzzy": the quote is present by normalized substring or partial_ratio
# but has no single locatable interval.
GROUND_EXACT = "exact"
GROUND_FUZZY = "fuzzy"

CANDIDATE_PRESENT = "present_in_candidate"
CANDIDATE_NOT_FOUND = "candidate_not_found"
CANDIDATE_AMBIGUOUS = "ambiguous"

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
_MARKDOWN_BRACKETED_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]\([^)]+\)")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_EMPHASIS_EDGE_RE = re.compile(r"(?<!\w)[*_]+|[*_]+(?!\w)")
_FRONT_MATTER_LABEL_RE = re.compile(
    r"^\s*(?:date|document(?:\s+number)?|title|reply[- ]to|author|audience|intent)\s*:",
    re.IGNORECASE,
)
_TOC_QUOTE_RE = re.compile(
    r"^\s*(?:table\s+of\s+contents|contents)\s*:?\s*$",
    re.IGNORECASE,
)
_PAGE_FURNITURE_RE = re.compile(
    r"^\s*(?:[PDN]\d{4}(?:R\d+)?\s+)?(?:page\s+)?\d{1,4}\s*$",
    re.IGNORECASE,
)
_RUNNING_HEADER_RE = re.compile(
    r"^\s*[PDN]\d{4}(?:R\d+)?\s+.{1,120}$",
    re.IGNORECASE,
)
_TOC_ENTRY_RE = re.compile(r"^(?P<stem>.+\S)\s+\d{1,4}\s*$")
_CODE_OPERATOR_PATTERN = (
    r"<=>|<<=|>>=|->\*|::|->|\+\+|--|==|!=|<=|>=|&&|\|\||<<|>>|"
    r"\+=|-=|\*=|/=|%=|&=|\|=|\^=|//|[=<>+\-*/%&|^~]"
)
_CODE_OPERATOR_RE = re.compile(_CODE_OPERATOR_PATTERN)
_LATEX_SCRIPT_GROUP_RE = re.compile(r"([_^])\{([^{}]*)\}?")


@dataclass(frozen=True)
class GroundedSpan:
    """A verified evidence span plus where and how it grounded."""

    span: EvidenceSpan
    status: str
    # Char interval into the raw markdown (exact tier only; None for fuzzy).
    start: int | None = None
    end: int | None = None


@dataclass(frozen=True)
class CandidateEvidence:
    """Source-grounded quote classified against the candidate Markdown."""

    span: EvidenceSpan
    source_status: str
    candidate_status: str
    candidate_grounding: str | None = None
    candidate_start: int | None = None
    candidate_end: int | None = None


def _tokenize(text: str) -> list[tuple[str, int, int]]:
    """Lowercased word tokens with their (start, end) char offsets."""
    return [
        (m.group().lower(), m.start(), m.end()) for m in _TOKEN_RE.finditer(text)
    ]


def _find_token_occurrences(
    source: list[str], quote: list[str]
) -> list[int]:
    """Sorted start indices where ``quote`` occurs as a token subsequence run."""
    n, m = len(source), len(quote)
    if m == 0 or m > n:
        return []
    first = quote[0]
    return [
        i
        for i in range(n - m + 1)
        if source[i] == first and source[i : i + m] == quote
    ]


@dataclass(frozen=True)
class _ChainNode:
    """Backpointer node for one selected occurrence."""

    span_index: int
    start: int
    parent: _ChainNode | None


class _FrontierEntry(NamedTuple):
    """Pareto-optimal: no kept chain ends earlier with at least this weight."""

    end: int
    weight: int
    node: _ChainNode


def _select_monotonic_matches(
    occurrence_lists: list[list[int]],
    span_lengths: list[int],
) -> dict[int, int]:
    """Select exact-match occurrences maximizing total matched tokens.

    Port of langextract's ``_select_monotonic_matches`` (resolver.py,
    Apache-2.0). Chooses at most one occurrence per span, keeping selections
    in model-output order without overlap. Token-count weighting prefers
    longer quotes in contested regions; ties prefer the earliest-ending
    chain, so repeated mentions resolve to successive occurrences.

    Returns a dict mapping span index to its selected start token index.
    """
    # Frontier entries are strictly increasing in both end and weight.
    frontier: list[_FrontierEntry] = []
    frontier_end = operator.attrgetter("end")

    def best_ending_at_or_before(position: int) -> _FrontierEntry | None:
        idx = bisect.bisect_right(frontier, position, key=frontier_end)
        return frontier[idx - 1] if idx else None

    def insert_if_undominated(entry: _FrontierEntry) -> None:
        covering = best_ending_at_or_before(entry.end)
        if covering is not None and covering.weight >= entry.weight:
            return
        low = bisect.bisect_left(frontier, entry.end, key=frontier_end)
        # Evict entries ending at or after entry.end with no more weight;
        # they can never outscore entry as a predecessor.
        dominated_end = low
        while (
            dominated_end < len(frontier)
            and frontier[dominated_end].weight <= entry.weight
        ):
            dominated_end += 1
        frontier[low:dominated_end] = [entry]

    for span_index, (occurrences, length) in enumerate(
        zip(occurrence_lists, span_lengths, strict=True)
    ):
        if not occurrences or length == 0:
            continue
        # Candidates are computed against the pre-insert frontier so a span
        # cannot extend a chain that already contains it.
        candidates = []
        for start in occurrences:
            predecessor = best_ending_at_or_before(start)
            weight = length + (predecessor.weight if predecessor else 0)
            parent = predecessor.node if predecessor else None
            candidates.append(
                _FrontierEntry(
                    start + length,
                    weight,
                    _ChainNode(span_index, start, parent),
                )
            )
        for candidate in candidates:
            insert_if_undominated(candidate)

    if not frontier:
        return {}
    selection: dict[int, int] = {}
    node: _ChainNode | None = frontier[-1].node
    while node is not None:
        selection[node.span_index] = node.start
        node = node.parent
    return selection


def _semantic_punctuation_signature(text: str) -> tuple[str, ...]:
    """Return every Unicode punctuation/symbol code point in source order."""
    return tuple(
        char
        for char in text
        if unicodedata.category(char)[0] in {"P", "S"}
    )


def semantic_parity_holds(span: EvidenceSpan, candidate_slice: str) -> bool:
    """Require case and semantic punctuation parity for token-aligned hits."""
    if candidate_slice.count(" | ") >= 2:
        candidate_slice = candidate_slice.replace(" | ", " ")
    quote_surface = span.quote
    candidate_surface = candidate_slice
    if span.axis == "math":
        quote_surface = _LATEX_SCRIPT_GROUP_RE.sub(r"\1\2", quote_surface)
        candidate_surface = _LATEX_SCRIPT_GROUP_RE.sub(
            r"\1\2",
            candidate_surface,
        )
    quote_tokens = [match.group() for match in _TOKEN_RE.finditer(quote_surface)]
    candidate_tokens = [
        match.group() for match in _TOKEN_RE.finditer(candidate_surface)
    ]
    return (
        quote_tokens == candidate_tokens
        and _semantic_punctuation_signature(quote_surface)
        == _semantic_punctuation_signature(candidate_surface)
    )


def ground_spans(
    spans: list[EvidenceSpan],
    markdown: str,
) -> tuple[list[GroundedSpan], int]:
    """Verify each evidence span against the paper markdown.

    Three tiers, per span, in model-output order:

    1. **Exact** (monotonic DP): the quote's token sequence occurs in the
       markdown; repeated quotes map to successive non-overlapping
       occurrences. Yields a char interval, post-checked by the alignment
       guard (``markdown[start:end]`` must equal the quote after
       normalization).
    2. **Fuzzy substring**: the normalized quote is a substring of the
       normalized markdown (no locatable interval).
    3. **Fuzzy ratio**: rapidfuzz ``partial_ratio`` meets
       ``EVIDENCE_FUZZY_FLOOR``. Gated to quotes of at least
       ``EVIDENCE_MIN_FUZZY_CHARS`` normalized chars so a generic short
       phrase cannot clear the ratio against a whole document.

    Returns (grounded_spans, dropped_count).
    """
    if not spans:
        return [], 0

    md_tokens = _tokenize(markdown)
    source = [t[0] for t in md_tokens]
    quote_token_lists = [
        [t[0] for t in _tokenize(span.quote)] for span in spans
    ]
    selection = _select_monotonic_matches(
        [_find_token_occurrences(source, q) for q in quote_token_lists],
        [len(q) for q in quote_token_lists],
    )

    norm_md = normalized_text(markdown)
    grounded: list[GroundedSpan] = []
    dropped = 0

    for i, span in enumerate(spans):
        norm_quote = normalized_text(span.quote)
        if not norm_quote:
            dropped += 1
            continue

        if i in selection:
            start_tok = selection[i]
            n_tok = len(quote_token_lists[i])
            start = md_tokens[start_tok][1]
            token_end = md_tokens[start_tok + n_tok - 1][2]
            # Token intervals end at the last alphanumeric character. Preserve
            # trailing semantic punctuation/operators when the raw quote is an
            # exact substring at the aligned start (e.g. ``<cstdlib>`` or ``;``).
            end = (
                start + len(span.quote)
                if markdown.startswith(span.quote, start)
                else token_end
            )
            # Post-alignment guard: never emit an interval whose raw slice
            # does not normalize to the quote (the mitigation that keeps the
            # langextract wrong-span failure mode out of our port).
            if normalized_text(markdown[start:end]) == norm_quote:
                parity_holds = semantic_parity_holds(
                    span,
                    markdown[start:end],
                )
                grounded.append(
                    GroundedSpan(
                        span,
                        GROUND_EXACT if parity_holds else GROUND_FUZZY,
                        start if parity_holds else None,
                        end if parity_holds else None,
                    )
                )
                continue

        if norm_quote in norm_md:
            grounded.append(GroundedSpan(span, GROUND_FUZZY))
        elif (
            len(norm_quote) >= EVIDENCE_MIN_FUZZY_CHARS
            and partial_ratio(norm_quote, norm_md) / 100.0
            >= EVIDENCE_FUZZY_FLOOR
        ):
            grounded.append(GroundedSpan(span, GROUND_FUZZY))
        else:
            dropped += 1

    return grounded, dropped


def _markdown_semantic_surface(
    text: str,
    *,
    preserve_operators: bool = False,
) -> str:
    """Collapse presentation-only Markdown without erasing case or punctuation."""
    text = _MARKDOWN_IMAGE_RE.sub(r"\1", text)
    text = _MARKDOWN_BRACKETED_LINK_RE.sub(r"[\1]", text)
    text = _MARKDOWN_LINK_RE.sub(r"\1", text)
    text = _HTML_TAG_RE.sub(" ", text)
    if not preserve_operators:
        text = _EMPHASIS_EDGE_RE.sub("", text)
        text = text.replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def _markdown_content_surface(text: str) -> str:
    """Case-folded presentation-neutral surface for uncertain matching."""
    return _markdown_semantic_surface(text).casefold()


def _table_tokens_are_present(quote: str, markdown: str) -> bool:
    if "<table" not in markdown.casefold() and "|" not in markdown:
        return False
    quote_tokens = {token.casefold() for token, _, _ in _tokenize(quote)}
    candidate_tokens = {token.casefold() for token, _, _ in _tokenize(markdown)}
    return bool(quote_tokens) and quote_tokens <= candidate_tokens


def _math_folded_surface(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed.casefold() if char.isalnum())


def _front_matter_intent(markdown: str) -> str | None:
    """Return the canonical scalar intent from leading YAML front matter."""
    lines = markdown.lstrip().splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, separator, value = line.partition(":")
        if separator and key.strip().casefold() == "intent":
            return value.strip().strip("\"'")
    return None


def _canonical_metadata_case_match(
    span: EvidenceSpan,
    candidate_markdown: str,
) -> bool:
    """Allow case folding only for the categorical front-matter intent."""
    if span.axis != "structure":
        return False
    intent = _front_matter_intent(candidate_markdown)
    return bool(intent) and span.quote.strip().casefold() == intent.casefold()


def _consume_surface_occurrence(
    needle: str,
    haystack: str,
    consumed: list[tuple[int, int]],
) -> bool:
    """Reserve the first non-overlapping presentation-surface occurrence."""
    if not needle:
        return False
    start = haystack.find(needle)
    while start >= 0:
        end = start + len(needle)
        if all(
            end <= used_start or used_end <= start
            for used_start, used_end in consumed
        ):
            consumed.append((start, end))
            consumed.sort()
            return True
        start = haystack.find(needle, start + 1)
    return False


def classify_candidate_evidence(
    source_grounded: list[GroundedSpan],
    candidate_markdown: str,
) -> list[CandidateEvidence]:
    """Classify source-grounded missing claims against converted Markdown.

    This is deliberately asymmetric with source grounding. An exact candidate
    hit refutes a missing claim only when semantic operators survive in the raw
    interval. Fuzzy or sanctioned-format matches abstain. A miss is reported as
    ``candidate_not_found`` rather than overstated as proven absence.
    """
    if not source_grounded:
        return []

    spans = [grounded.span for grounded in source_grounded]
    candidate_grounded, _ = ground_spans(spans, candidate_markdown)
    candidate_by_span_id = {
        id(grounded.span): grounded for grounded in candidate_grounded
    }
    candidate_surface = _markdown_content_surface(candidate_markdown)
    has_front_matter = candidate_markdown.lstrip().startswith("---")
    consumed_surface_intervals: dict[
        tuple[bool, str],
        list[tuple[int, int]],
    ] = {}
    metadata_intent_consumed = False

    results: list[CandidateEvidence] = []
    for source in source_grounded:
        span = source.span
        candidate = candidate_by_span_id.get(id(span))
        preserve_operators = bool(_CODE_OPERATOR_RE.search(span.quote))
        quote_semantic_surface = _markdown_semantic_surface(
            span.quote,
            preserve_operators=preserve_operators,
        )
        candidate_semantic_surface = _markdown_semantic_surface(
            candidate_markdown,
            preserve_operators=preserve_operators,
        )
        quote_surface = _markdown_content_surface(span.quote)
        claim_identity = (preserve_operators, quote_semantic_surface)
        claim_consumed_intervals = consumed_surface_intervals.setdefault(
            claim_identity,
            [],
        )

        if candidate is not None and candidate.status == GROUND_EXACT:
            assert candidate.start is not None and candidate.end is not None
            candidate_slice = candidate_markdown[candidate.start:candidate.end]
            if semantic_parity_holds(span, candidate_slice):
                _consume_surface_occurrence(
                    quote_semantic_surface,
                    candidate_semantic_surface,
                    claim_consumed_intervals,
                )
                results.append(
                    CandidateEvidence(
                        span=span,
                        source_status=source.status,
                        candidate_status=CANDIDATE_PRESENT,
                        candidate_grounding=candidate.status,
                        candidate_start=candidate.start,
                        candidate_end=candidate.end,
                    )
                )
                continue

        if (
            quote_semantic_surface
            and quote_semantic_surface in candidate_semantic_surface
            and _consume_surface_occurrence(
                quote_semantic_surface,
                candidate_semantic_surface,
                claim_consumed_intervals,
            )
        ):
            results.append(
                CandidateEvidence(
                    span=span,
                    source_status=source.status,
                    candidate_status=CANDIDATE_PRESENT,
                    candidate_grounding=GROUND_EXACT,
                )
            )
            continue

        if (
            not metadata_intent_consumed
            and _canonical_metadata_case_match(span, candidate_markdown)
        ):
            metadata_intent_consumed = True
            results.append(
                CandidateEvidence(
                    span=span,
                    source_status=source.status,
                    candidate_status=CANDIDATE_PRESENT,
                    candidate_grounding=GROUND_EXACT,
                )
            )
            continue

        if quote_surface and quote_surface in candidate_surface:
            results.append(
                CandidateEvidence(
                    span=span,
                    source_status=source.status,
                    candidate_status=CANDIDATE_AMBIGUOUS,
                    candidate_grounding=(
                        candidate.status if candidate is not None else GROUND_FUZZY
                    ),
                )
            )
            continue

        if candidate is not None:
            results.append(
                CandidateEvidence(
                    span=span,
                    source_status=source.status,
                    candidate_status=CANDIDATE_AMBIGUOUS,
                    candidate_grounding=candidate.status,
                )
            )
            continue

        sanctioned = (
            has_front_matter and bool(_FRONT_MATTER_LABEL_RE.match(span.quote))
        ) or bool(
            _TOC_QUOTE_RE.match(span.quote)
            or _PAGE_FURNITURE_RE.match(span.quote)
            or _RUNNING_HEADER_RE.match(span.quote)
        )
        toc_entry = _TOC_ENTRY_RE.match(span.quote)
        toc_entry_ambiguous = bool(
            toc_entry
            and _markdown_content_surface(toc_entry.group("stem"))
            in candidate_surface
        )
        table_ambiguous = (
            span.axis == "tables"
            and _table_tokens_are_present(span.quote, candidate_markdown)
        )
        math_quote = _math_folded_surface(span.quote)
        math_ambiguous = (
            span.axis == "math"
            and bool(math_quote)
            and math_quote in _math_folded_surface(candidate_markdown)
        )
        results.append(
            CandidateEvidence(
                span=span,
                source_status=source.status,
                candidate_status=(
                    CANDIDATE_AMBIGUOUS
                    if (
                        sanctioned
                        or toc_entry_ambiguous
                        or table_ambiguous
                        or math_ambiguous
                    )
                    else CANDIDATE_NOT_FOUND
                ),
            )
        )

    return results


def ground_page_spans(
    spans: list[EvidenceSpan],
    page_text: str,
) -> tuple[list[GroundedSpan], int]:
    """Ground evidence spans against one page with honest provenance."""
    if not spans:
        return [], 0

    norm_page = normalized_text(page_text)
    grounded: list[GroundedSpan] = []
    dropped = 0
    for span in spans:
        norm_quote = normalized_text(span.quote)
        if not norm_quote:
            dropped += 1
            continue
        if len(norm_quote) <= PAGE_QUOTE_MAX_DIFFS:
            dropped += 1
            continue
        exact_grounded, _ = ground_spans([span], page_text)
        if exact_grounded and exact_grounded[0].status == GROUND_EXACT:
            grounded.append(GroundedSpan(span, GROUND_EXACT))
            continue
        threshold = 1.0 - PAGE_QUOTE_MAX_DIFFS / len(norm_quote)
        if partial_ratio(norm_quote, norm_page) / 100.0 >= threshold:
            grounded.append(GroundedSpan(span, GROUND_FUZZY))
        else:
            dropped += 1

    return grounded, dropped


def ground_page_quotes(quotes: list[str], page_text: str) -> tuple[list[str], int]:
    """Ground page-escalation quotes against ONE page's raw text.

    Unlike :func:`ground_spans` (whole-document grounding for the monolith
    judge), page-scoped quotes ground against just the flagged page: exact
    normalized substring, or the olmocr-bench length-relative fuzzy
    threshold ``1.0 - PAGE_QUOTE_MAX_DIFFS / len(quote)`` via rapidfuzz
    ``partial_ratio`` on normalized strings (a fixed char-diff budget divided
    by quote length, so short quotes stay strict and long quotes get
    proportionally more slack). A quote that cannot be located on the page
    is dropped as hallucinated or off-page.

    Returns ``(grounded_quotes, dropped_count)``.
    """
    spans = [
        EvidenceSpan(axis="structure", quote=quote, reason="missing from markdown")
        for quote in quotes
    ]
    grounded, dropped = ground_page_spans(spans, page_text)
    return [item.span.quote for item in grounded], dropped
