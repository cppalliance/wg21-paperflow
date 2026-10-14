#
# Copyright (c) 2026 Sean Parsons
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Deterministic metadata/outline comparison replacing the LLM metadata check.

Pure function, no I/O, no async, no LLM. Compares source metadata (a PID,
title, and date extracted from raw source text) and a source heading outline
against the candidate Markdown's YAML front matter and ATX heading outline,
returning the same :class:`MetadataOutlineCheck` schema the LLM check
(``unit_judge.run_metadata_outline_check``) produces. Wired in behind a
shadow-mode env var (``TAPETUM_METADATA_SHADOW`` / ``TAPETUM_DET_METADATA``)
in ``pdf_judge.py`` and ``adjudicate.py``.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Literal

from whisker.llm.models import MetadataOutlineCheck, Verdict
from whisker.llm.source_router import (
    _is_sanctioned_toc_title,
    _text_key,
)
from whisker.llm.unit_judge import _candidate_structure_packet

__all__ = ["compare_metadata_outline"]

# PID pattern: P or N followed by digits, R and digits (e.g. P2583R3, N5044).
_PID_RE = re.compile(r"\b([PN]\d{3,5}R?\d*)\b", re.IGNORECASE)
# ISO date pattern.
_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

# A source-metadata line must exceed this length, both raw and with any PID/
# date stripped out, to be considered a candidate title line rather than a
# bare identifier/date line.
MIN_TITLE_LINE_CHARS = 10

# Token-set overlap floor for title comparison: matches if more than this
# fraction of either side's tokens appear on the other side.
TITLE_TOKEN_OVERLAP_FLOOR = 0.5

# Schema cap on heading_drift/missing_sections (MetadataOutlineCheck
# max_length=5); enforced here too so accumulation never overshoots it.
MAX_OUTLINE_ENTRIES = 5

# PDF outline noise floor: font-size-derived heading candidates include
# body text, abstract prose, and page chrome. Only flag missing sections
# when a meaningful fraction of outline titles are absent (LLM is lenient
# about noisy page-1 metadata; deterministic check must mirror that).
PDF_MISSING_FRACTION_FLOOR = 0.25

# Minimum word count for a PDF outline title to be considered a real
# heading candidate (filters single-word prose, page numbers, etc.)
PDF_MIN_TITLE_WORDS = 2

# Loose date formats attempted against the candidate YAML `date:` value when
# it is not already ISO 8601.
_CANDIDATE_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%B %d, %Y",
    "%d %B %Y",
    "%Y-%m",
)

_FRONT_MATTER_LINE_RE = re.compile(r"^([A-Za-z][\w-]*):\s*(.*)$")
_TRACKED_FRONT_MATTER_KEYS = frozenset({"document", "title", "date"})
# Leading section-number pattern stripped from heading text before key
# comparison: "1.", "1.2.3", "IV.", "A." prefixes.
_SECNO_RE = re.compile(
    r"^(?:\d+(?:\.\d+)*\.?|[IVXLCDM]+\.|[A-Z]\.)\s+",
    re.IGNORECASE,
)

_CANDIDATE_HEADING_RE = re.compile(r"^h(\d):\s*(.*)$")
_SOURCE_HTML_OUTLINE_RE = re.compile(r"^(h[1-6]):\s*(.*)$")
_PDF_SOURCE_OUTLINE_RE = re.compile(r"^page \d+, font [\d.]+:\s*(.*)$")


def _heading_key(text: str) -> str:
    """Normalize a heading: strip secno prefix, then apply _text_key."""
    return _text_key(_SECNO_RE.sub("", text).strip())


def _parse_front_matter_fields(front_matter_text: str) -> dict[str, str]:
    """Extract document/title/date scalar fields from candidate YAML text."""
    fields: dict[str, str] = {}
    for line in front_matter_text.splitlines():
        stripped = line.strip()
        if stripped in ("", "---"):
            continue
        match = _FRONT_MATTER_LINE_RE.match(stripped)
        if not match:
            continue
        key = match.group(1).strip().lower()
        if key not in _TRACKED_FRONT_MATTER_KEYS:
            continue
        value = match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fields[key] = value
    return fields


def _extract_source_pid(source_metadata: str) -> str | None:
    match = _PID_RE.search(source_metadata)
    return match.group(1) if match else None


def _extract_source_date(source_metadata: str) -> str | None:
    match = _ISO_DATE_RE.search(source_metadata)
    return match.group(1) if match else None


def _extract_source_title(source_metadata: str) -> str | None:
    """First substantial line that is not just a PID and/or date."""
    for line in source_metadata.splitlines():
        candidate = line.strip()
        if len(candidate) <= MIN_TITLE_LINE_CHARS:
            continue
        residual = _PID_RE.sub("", candidate)
        residual = _ISO_DATE_RE.sub("", residual)
        residual = residual.strip(" \t,;:-")
        if len(residual) <= MIN_TITLE_LINE_CHARS:
            continue
        return candidate
    return None


def _document_number_matches(
    source_pid: str | None, candidate_document: str | None
) -> bool:
    """Missing data on either side is not evidence of a mismatch."""
    if not source_pid or not candidate_document:
        return True
    return source_pid.strip().casefold() == candidate_document.strip().casefold()


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return {tok.casefold() for tok in _TOKEN_RE.findall(text)}


def _title_matches(source_title: str | None, candidate_title: str | None) -> bool:
    if not source_title:
        return True
    if not candidate_title:
        return False
    source_tokens = _tokenize(source_title)
    candidate_tokens = _tokenize(candidate_title)
    if not source_tokens or not candidate_tokens:
        return True
    overlap = source_tokens & candidate_tokens
    source_ratio = len(overlap) / len(source_tokens)
    candidate_ratio = len(overlap) / len(candidate_tokens)
    return (
        source_ratio > TITLE_TOKEN_OVERLAP_FLOOR
        or candidate_ratio > TITLE_TOKEN_OVERLAP_FLOOR
    )


def _parse_date_loose(value: str) -> date | None:
    value = value.strip()
    for fmt in _CANDIDATE_DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _date_matches(source_date: str | None, candidate_date_raw: str | None) -> bool:
    """Missing dates on either side are not a mismatch signal."""
    if not source_date or not candidate_date_raw:
        return True
    try:
        source_parsed = date.fromisoformat(source_date)
    except ValueError:
        return True
    candidate_parsed = _parse_date_loose(candidate_date_raw)
    if candidate_parsed is None:
        return True
    return source_parsed == candidate_parsed


def _parse_candidate_headings(candidate_headings: list[str]) -> list[tuple[int, str]]:
    parsed: list[tuple[int, str]] = []
    for entry in candidate_headings:
        match = _CANDIDATE_HEADING_RE.match(entry)
        if match:
            parsed.append((int(match.group(1)), match.group(2)))
    return parsed


def _parse_html_source_outline(source_outline: list[str]) -> list[tuple[str, str]]:
    parsed: list[tuple[str, str]] = []
    for entry in source_outline:
        match = _SOURCE_HTML_OUTLINE_RE.match(entry)
        if match:
            parsed.append((match.group(1), match.group(2)))
    return parsed


def _parse_pdf_source_titles(source_outline: list[str]) -> list[str]:
    titles: list[str] = []
    for entry in source_outline:
        match = _PDF_SOURCE_OUTLINE_RE.match(entry)
        if match:
            titles.append(match.group(1))
    return titles


def _candidate_heading_levels_by_key(
    candidate_headings: list[tuple[int, str]],
) -> dict[str, list[int]]:
    levels_by_key: dict[str, list[int]] = defaultdict(list)
    for level, title in candidate_headings:
        key = _heading_key(title)
        levels_by_key[key].append(level)
    return levels_by_key


def _compare_html_outline(
    source_pairs: list[tuple[str, str]],
    candidate_headings: list[tuple[int, str]],
) -> tuple[list[str], list[str]]:
    """Occurrence-aware heading match, mirroring source_router.route_html_units."""
    heading_drift: list[str] = []
    missing_sections: list[str] = []
    candidate_by_key = _candidate_heading_levels_by_key(candidate_headings)
    occurrence_counter: Counter[str] = Counter()

    for source_tag, source_title in source_pairs:
        if _is_sanctioned_toc_title(source_title):
            continue
        key = _heading_key(source_title)
        occurrence = occurrence_counter[key]
        occurrence_counter[key] += 1
        matches = candidate_by_key.get(key, [])
        if occurrence >= len(matches):
            if len(missing_sections) < MAX_OUTLINE_ENTRIES:
                missing_sections.append(f"{source_tag}: {source_title}")
            continue
        candidate_level = matches[occurrence]
        source_level = int(source_tag[1])
        if candidate_level != source_level and len(heading_drift) < MAX_OUTLINE_ENTRIES:
            heading_drift.append(
                f"{source_tag}:{source_title} -> h{candidate_level}:{source_title}"
            )

    return heading_drift, missing_sections


def _compare_pdf_outline(
    source_titles: list[str],
    candidate_headings: list[tuple[int, str]],
) -> list[str]:
    """PDF font-size-to-level mapping is noisy: presence-only, occurrence-aware.

    Font-size candidates include abstract prose, page chrome, and body text.
    Only flag missing sections when a meaningful fraction of candidates are
    absent, mirroring the LLM's lenience on noisy page-1 metadata.
    """
    candidate_by_key = _candidate_heading_levels_by_key(candidate_headings)
    occurrence_counter: Counter[str] = Counter()
    checked = 0
    all_missing: list[str] = []

    for title in source_titles:
        if _is_sanctioned_toc_title(title):
            continue
        if len(title.split()) < PDF_MIN_TITLE_WORDS:
            continue
        key = _heading_key(title)
        occurrence = occurrence_counter[key]
        occurrence_counter[key] += 1
        checked += 1
        matches = candidate_by_key.get(key, [])
        if occurrence >= len(matches):
            all_missing.append(f"pdf: {title}")

    if not checked or len(all_missing) / checked < PDF_MISSING_FRACTION_FLOOR:
        return []
    return all_missing[:MAX_OUTLINE_ENTRIES]


def _build_reasoning(
    document_number_matches: bool,
    title_matches: bool,
    headings_checked: int,
    drift_count: int,
) -> str:
    pid_part = "PID match" if document_number_matches else "PID mismatch"
    title_part = "title match" if title_matches else "title mismatch"
    return (
        f"Deterministic compare: {pid_part}, {title_part}, "
        f"{headings_checked} headings checked, {drift_count} drift found."
    )


def compare_metadata_outline(
    pid: str,
    source_metadata: str,
    source_outline: list[str],
    candidate_md: str,
    *,
    source_kind: Literal["pdf", "html"] = "pdf",
    html_outline: list[tuple[str, str]] | None = None,
) -> MetadataOutlineCheck:
    """Pure deterministic replacement for ``run_metadata_outline_check``.

    Compares source-extracted PID/title/date and heading outline against the
    candidate's YAML front matter and ATX headings. Never fails on missing
    data (a review signal at worst); only an explicit PID mismatch can fail.
    """
    del pid  # unused; kept for signature parity with the LLM check

    front_matter_text, candidate_heading_strings = _candidate_structure_packet(
        candidate_md
    )
    candidate_fields = _parse_front_matter_fields(front_matter_text)
    candidate_headings = _parse_candidate_headings(candidate_heading_strings)

    source_pid = _extract_source_pid(source_metadata)
    source_title = _extract_source_title(source_metadata)
    source_date = _extract_source_date(source_metadata)

    document_number_matches = _document_number_matches(
        source_pid, candidate_fields.get("document")
    )
    title_matches = _title_matches(source_title, candidate_fields.get("title"))
    date_matches = _date_matches(source_date, candidate_fields.get("date"))

    if source_kind == "html":
        source_pairs = (
            html_outline
            if html_outline is not None
            else _parse_html_source_outline(source_outline)
        )
        heading_drift, missing_sections = _compare_html_outline(
            source_pairs, candidate_headings
        )
    else:
        source_titles = _parse_pdf_source_titles(source_outline)
        heading_drift = []
        missing_sections = _compare_pdf_outline(source_titles, candidate_headings)

    if not document_number_matches:
        verdict: Verdict = "not-llm-readable"
    elif not title_matches or not date_matches or heading_drift or missing_sections:
        verdict = "review"
    else:
        verdict = "pass"

    reasoning = _build_reasoning(
        document_number_matches,
        title_matches,
        len(candidate_headings),
        len(heading_drift) + len(missing_sections),
    )

    return MetadataOutlineCheck(
        reasoning=reasoning,
        title_matches=title_matches,
        document_number_matches=document_number_matches,
        date_matches=date_matches,
        heading_drift=heading_drift[:MAX_OUTLINE_ENTRIES],
        missing_sections=missing_sections[:MAX_OUTLINE_ENTRIES],
        verdict=verdict,
    )
