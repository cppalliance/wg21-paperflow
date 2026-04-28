#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Core data models for paperlint.

The discovery/gate side (``Evidence``, ``Finding``, ``GatedFinding``)
and the deliverable side (``Evaluation`` with ``OutputFinding`` / ``Reference``,
``MailingIndex`` with ``RoomEntry`` / ``IndexPaperEntry`` / ``FailureEntry``)
together describe every JSON contract in ``DESIGN.md`` (repo root).

``Paper`` is the canonical in-memory representation of a row in the ``papers``
table. ``ConvertResult`` is the output of a single tomd conversion pass.

Use :func:`to_dict` when serializing so unset optional fields are omitted
rather than rendered as ``null``.
"""

from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "1"


@dataclass
class Evidence:
    location: str
    quote: str
    verified: bool = False
    extracted_char_start: int | None = None
    extracted_char_end: int | None = None


@dataclass
class Finding:
    number: int
    title: str
    category: str
    defect: str
    correction: str
    axiom: str
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class GatedFinding:
    finding: Finding
    verdict: str  # PASS | REJECT | REFER
    reason: str


@dataclass
class PaperMeta:
    paper: str
    title: str
    authors: list[str]
    target_group: str
    source_file: str
    run_timestamp: str
    model: str
    intent: str = ""

    @classmethod
    def from_dict(cls, raw: dict) -> "PaperMeta":
        authors = raw.get("authors") or []
        if isinstance(authors, str):
            import json as _json
            try:
                authors = _json.loads(authors)
            except Exception:
                authors = [a.strip() for a in authors.split(",") if a.strip()]
        return cls(
            paper=raw.get("paper") or raw.get("paper_id") or "",
            title=raw.get("title") or "",
            authors=list(authors),
            target_group=raw.get("target_group") or raw.get("subgroup") or "",
            source_file=raw.get("source_file") or "",
            run_timestamp=raw.get("run_timestamp") or "",
            model=raw.get("model") or "",
            intent=raw.get("intent") or "",
        )


@dataclass
class Paper:
    """Canonical in-memory representation of a WG21 paper.

    Maps to a row in the ``papers`` SQLite table. Used as the input type
    passed to conversion and evaluation workers; workers never access
    the storage backend directly.

    Field semantics:

    * ``year`` — 4-digit year string (``"2026"``). Mailings are bucketed
      by year only; the monthly mailing granularity is not exposed.
    * ``audience`` — target subgroup name (``"LEWG"``, ``"SG16"``).
    * ``intent`` — ``"ask"`` | ``"info"`` | ``""`` (unknown). Derived from
      the mailing title prefix (``"Ask:"`` / ``"Info:"``), confirmed or
      overridden by the paper's own YAML front matter after tomd conversion.
    * ``source_file`` — local filesystem path to the staged PDF or HTML.
      Empty string means not yet downloaded.
    * ``markdown_path`` — local filesystem path to the converted ``.md``.
      Empty string means not yet converted.
    """
    document_id: str
    year: str
    title: str
    authors: list[str]
    mailing_date: str
    document_date: str
    audience: str
    intent: str
    url: str
    source_file: str
    markdown_path: str


@dataclass
class ConvertResult:
    """Output of a single tomd conversion pass for one paper.

    Returned by :func:`paperlint.orchestrator.convert_one_paper`. The
    worker performs no I/O beyond reading the source file; the main
    coroutine persists ``markdown`` and ``prompts`` through the storage
    backend.
    """
    paper_id: str
    markdown: str
    prompts: list[str] | None
    intent: str
    title: str
    status: str         # "ok" | "error"
    error: str = ""


@dataclass
class Reference:
    """One reference entry in ``evaluation.references[]``.

    ``extracted_char_*`` are absent when quote verification fell back to
    whitespace-normalized matching without a recoverable offset, so they are
    optional rather than required.
    """
    number: int
    location: str
    quote: str
    verified: bool
    extracted_char_start: int | None = None
    extracted_char_end: int | None = None


@dataclass
class OutputFinding:
    """One finding in ``evaluation.findings[]`` — the deliverable shape.

    Distinct from :class:`Finding` (the discovery shape): the deliverable
    drops ``axiom`` / ``title`` / ``evidence`` and carries integer refs into
    the sibling ``references[]`` list.
    """
    location: str
    description: str
    category: str
    correction: str
    references: list[int] = field(default_factory=list)


@dataclass
class Evaluation:
    """Top-level shape of ``evaluation.json``.

    ``pipeline_status`` is ``complete`` on the happy path, ``failed`` for the
    pre-analysis skeleton, or ``partial`` when analysis raises after metadata
    is available. The four ``failure_*`` fields are populated only on the
    ``partial`` path; :func:`to_dict` omits them when ``None`` so the wire
    format matches the pre-refactor dict construction.
    """
    schema_version: str
    paperlint_sha: str
    prompt_hash: str
    source_url: str
    pipeline_status: str
    paper: str
    title: str
    authors: list[str]
    audience: str
    generated: str
    model: str
    findings_discovered: int
    findings_passed: int
    findings_rejected: int
    summary: str
    findings: list[OutputFinding] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    failure_stage: str | None = None
    failure_type: str | None = None
    failure_message: str | None = None
    failure_traceback: str | None = None


@dataclass
class RoomEntry:
    papers: list[str] = field(default_factory=list)
    total_findings: int = 0


@dataclass
class IndexPaperEntry:
    paper: str
    title: str
    audience: str
    findings_passed: int
    findings_discovered: int


@dataclass
class FailureEntry:
    """One entry in ``index.failed_papers[]``.

    ``paper`` is always set; every other field is populated conditionally
    (e.g. ``error`` for pre-analysis exceptions, the ``failure_*`` trio for
    ``partial`` pipeline status). :func:`to_dict` drops unset fields.
    """
    paper: str
    error: str | None = None
    pipeline_status: str | None = None
    summary: str | None = None
    failure_stage: str | None = None
    failure_type: str | None = None
    failure_message: str | None = None
    failure_traceback: str | None = None


@dataclass
class MailingIndex:
    schema_version: str
    paperlint_sha: str
    prompt_hash: str
    year: str
    generated: str
    total_papers: int
    succeeded: int
    failed: int
    partial: int
    rooms: dict[str, RoomEntry] = field(default_factory=dict)
    papers: list[IndexPaperEntry] = field(default_factory=list)
    failed_papers: list[FailureEntry] | None = None


def _strip_none(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_none(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_none(v) for v in obj]
    return obj


def to_dict(obj: Any, *, omit_none: bool = True) -> Any:
    """Serialize a dataclass (or container of dataclasses) to plain dicts.

    Thin wrapper over :func:`dataclasses.asdict` that filters ``None`` values
    when ``omit_none=True`` (the default). This matches the existing on-the-wire
    convention where optional failure fields are absent rather than ``null``.
    """
    raw = asdict(obj)
    return _strip_none(raw) if omit_none else raw
