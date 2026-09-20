#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Domain models for the tapetum_llm advisory lane.

Two layers:

- :class:`Adjudication` / :class:`EvidenceSpan` / :class:`AxisFinding` are the
  LLM ``output_type`` (pydantic, constrained decoding). Field order matters:
  ``reasoning`` comes first so the model deliberates before committing a verdict
  (auditable CoT), and the schema carries >= 5 fields, the stability floor
  measured in ``MODELS.md`` for constrained-decoding determinism.
- :class:`TapetumResult` is the library return value. The cascade returns it;
  only the CLI persists it. Deterministic ``to_dict`` (sorted, rounded).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from whisker.llm.constants import (
    MAX_IDEAL_DISCREPANCIES,
    MAX_IDEAL_EXPLANATION_CHARS,
    MAX_IDEAL_QUOTE_CHARS,
    MAX_MISSING_QUOTES,
)

Verdict = Literal["pass", "not-llm-readable", "review"]

FidelityAxis = Literal[
    "wording",
    "code",
    "stable_names",
    "tables",
    "xrefs",
    "math",
    "structure",
]

IdealVerificationAxis = Literal[
    "frontmatter",
    "headings",
    "lists",
    "code",
    "tables",
    "wording",
    "structure",
]

__all__ = [
    "Adjudication",
    "AxisFinding",
    "CODE_BOUNDARY_MAX_FINDINGS",
    "CODE_BOUNDARY_MAX_TOKENS",
    "CodeBoundaryFinding",
    "CodeBoundaryJudgment",
    "CodeBoundaryKind",
    "DefectFinding",
    "EvidenceSpan",
    "FidelityAxis",
    "IdealDiscrepancy",
    "IdealVerification",
    "IdealVerificationAxis",
    "MetadataOutlineCheck",
    "PageJudgment",
    "TapetumResult",
    "UNIT_CLEAR_CONFIDENCE_FLOOR",
    "UNIT_CLEAR_MAX_TOKENS",
    "UNIT_DEFECTS_MAX_TOKENS",
    "UnitCheck",
    "UnitCheckClear",
    "UnitCheckDefects",
    "Verdict",
    "parse_ideal_verification",
    "to_unit_check",
]


class IdealDiscrepancy(BaseModel):
    """One structural divergence between candidate and blessed ideal."""

    axis: IdealVerificationAxis
    candidate_quote: str = Field(
        min_length=1,
        max_length=MAX_IDEAL_QUOTE_CHARS,
        description="Verbatim excerpt from the candidate Markdown.",
    )
    ideal_quote: str = Field(
        min_length=1,
        max_length=MAX_IDEAL_QUOTE_CHARS,
        description="Verbatim excerpt from the human-blessed ideal Markdown.",
    )
    severity: Literal["minor", "major"]
    explanation: str = Field(
        min_length=1,
        max_length=MAX_IDEAL_EXPLANATION_CHARS,
        description="Concise explanation of the structural divergence.",
    )

    @field_validator("candidate_quote", "ideal_quote", "explanation")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        """Reject whitespace-only text without changing verbatim content."""
        if not value.strip():
            raise ValueError("ideal discrepancy text must not be blank")
        return value


class IdealVerification(BaseModel):
    """Structured result of comparing candidate Markdown with a blessed ideal."""

    verdict: Literal["agree", "review"]
    discrepancies: list[IdealDiscrepancy] = Field(
        default_factory=list,
        max_length=MAX_IDEAL_DISCREPANCIES,
    )

    @model_validator(mode="after")
    def verdict_matches_discrepancies(self) -> IdealVerification:
        """Reject agreement with discrepancies and review without evidence."""
        if (self.verdict == "agree") != (not self.discrepancies):
            raise ValueError(
                "ideal verdict must be agree exactly when discrepancies are empty"
            )
        return self


def parse_ideal_verification(value: object) -> IdealVerification | None:
    """Validate an untrusted sidecar field or return neutral absence."""
    try:
        return IdealVerification.model_validate(value)
    except (TypeError, ValidationError):
        return None


class EvidenceSpan(BaseModel):
    """A verbatim quote from the paper markdown backing the verdict.

    ``quote`` must be an exact substring of the converted markdown so it can be
    grounded (located) deterministically; an ungrounded quote is dropped, the
    langextract ``char_interval is None`` reject signal.
    """

    axis: FidelityAxis
    quote: str = Field(
        description="Verbatim excerpt, at most 20 words."
    )
    reason: str = Field(
        description="Why this quote matters, at most 15 words."
    )


class AxisFinding(BaseModel):
    """Per-axis fidelity finding from the LLM adjudicator."""

    axis: FidelityAxis
    verdict: Verdict
    severity: Literal["none", "minor", "major"]
    note: str = Field(
        description="At most 12 words: the deciding observation for this axis."
    )


class Adjudication(BaseModel):
    """Multi-axis conversion-fidelity adjudication (advisory).

    ``reasoning`` comes first so the model deliberates before committing.
    ``verdict`` is the overall == worst axis verdict. The lane never turns
    low confidence into a pass/fail.
    """

    reasoning: str = Field(
        description="At most 60 words: what was checked, deciding finding."
    )
    axis_findings: list[AxisFinding] = Field(default_factory=list)
    worst_axis: FidelityAxis
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_spans: list[EvidenceSpan] = Field(
        default_factory=list,
        description="At most 3 verbatim quotes, most important first.",
    )
    primary_concern: str = Field(
        description="Single most important defect in at most 15 words, "
        "or 'none' if clean."
    )


class PageJudgment(BaseModel):
    """Structured output for one scoped page-escalation call (D6).

    Answers a narrower question than :class:`Adjudication`/``PdfJudgment``:
    is content-bearing text from THIS ONE flagged page absent from the
    markdown? The prompt inherits the monolith judge's full conversion
    contract (YAML front matter, TOC removal, figure text, reflow/
    dehyphenation), so the model's role here is presence-scoped confirmation
    of a deterministic screen flag, not open-ended absence detection.
    """

    content_missing: bool = Field(
        description="True if content-bearing text from this page is "
        "genuinely absent from the markdown; false if nothing is missing "
        "or everything that looks missing is sanctioned conversion "
        "behavior (YAML front matter, TOC, furniture, figure text)."
    )
    missing_content: list[str] = Field(
        default_factory=list,
        max_length=MAX_MISSING_QUOTES,
        description="Verbatim quotes from THIS page's raw text that are "
        "absent from the markdown, most important first. Empty if nothing "
        "is missing.",
    )
    reasoning: str = Field(
        description="At most 60 words: what was checked, deciding finding."
    )
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def missing_flag_matches_quotes(self) -> PageJudgment:
        """Reject contradictory page claims so structured retries can repair them."""
        if self.content_missing != bool(self.missing_content):
            raise ValueError(
                "content_missing must be true exactly when missing_content "
                "contains at least one quote"
            )
        return self


CodeBoundaryKind = Literal[
    "heading_in_fence",
    "listing_split",
    "prose_in_fence",
    "code_as_prose",
    "false_wording_on_comment",
    "clean",
]

CODE_BOUNDARY_MAX_FINDINGS = 3
"""Cap on findings per fence-scoped code-boundary call. One fence typically
yields one finding; the small margin accommodates a defect + clean combo."""

CODE_BOUNDARY_MAX_TOKENS = 1024
"""Token budget for the code-boundary judge (defect-detailed, not the full
unit-check budget)."""


class CodeBoundaryFinding(BaseModel):
    """One code-boundary defect (or clean attestation) with grounded quotes.

    ``candidate_quote`` must be an exact substring of the candidate markdown
    so it can be grounded deterministically (same contract as EvidenceSpan).
    """

    kind: CodeBoundaryKind
    verdict: Verdict
    candidate_quote: str = Field(
        min_length=1,
        max_length=200,
        description="Verbatim excerpt from the candidate markdown showing "
        "the boundary defect (or clean fence). Must be an exact substring. "
        "Keep short: one line or small fragment, at most 200 characters.",
    )
    source_quote: str = Field(
        default="",
        max_length=200,
        description="Optional verbatim excerpt from the source text for "
        "comparison. Empty when not applicable.",
    )
    rule_id: str = Field(
        description="Which codeblock readability rule is violated or "
        "satisfied: C1, C2, C4, C5, C6, C7, C9, C10, or 'none'.",
    )
    reasoning: str = Field(
        description="At most 15 words: why this is a boundary defect or clean.",
    )


class CodeBoundaryJudgment(BaseModel):
    """Structured code-boundary judgment for one fence (D6, >= 5 fields).

    Requires at least one finding: an empty list is a validation retry
    (``ModelRetry``). Use ``kind='clean'`` when the fence has no boundary
    defects.
    """

    reasoning: str = Field(
        description="At most 40 words: what was checked, deciding finding.",
    )
    page: str = Field(
        description="The unit checked, e.g. 'fence:3' or 'page:7'.",
    )
    findings: list[CodeBoundaryFinding] = Field(
        max_length=CODE_BOUNDARY_MAX_FINDINGS,
        description="At least one finding required. Use kind='clean' when "
        "no boundary defects exist.",
    )
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def must_have_findings(self) -> CodeBoundaryJudgment:
        """Require at least one finding; empty is a retry, not a pass."""
        if not self.findings:
            raise ValueError(
                "at least one finding required; use kind='clean' for fences "
                "with no boundary defects"
            )
        return self

    @model_validator(mode="after")
    def verdict_matches_findings(self) -> CodeBoundaryJudgment:
        """A pass verdict requires only clean findings."""
        non_clean = [f for f in self.findings if f.kind != "clean"]
        if self.verdict == "pass" and non_clean:
            raise ValueError(
                "pass verdict requires only clean findings"
            )
        if self.verdict != "pass" and not non_clean:
            raise ValueError(
                "non-pass verdict requires at least one non-clean finding"
            )
        return self


class DefectFinding(BaseModel):
    """One defect group found by the unit-based judge."""

    defect_type: str = Field(
        description="Category: qualifier_omission, heading_drift, content_omission, "
        "table_corruption, table_flattened, punctuation_loss, entity_artifact, "
        "toc_leak, code_loss"
    )
    source_unit: str = Field(
        description="Which unit(s) contain this defect: 'page:3', "
        "'section:Abstract', 'pages:5-12'"
    )
    source_quote: str = Field(
        description="One representative verbatim quote from the source (max 25 words)."
    )
    candidate_location: str = Field(
        default="",
        description="Where in the candidate this should appear (empty if entirely absent)."
    )
    affected_count: int = Field(
        ge=1,
        description="How many instances of this defect exist across the paper."
    )
    severity: Literal["low", "medium", "high", "critical"] = Field(
        description="low=cosmetic, medium=minor info loss, high=significant loss, "
        "critical=substantial content missing or corrupted"
    )
    reasoning: str = Field(
        description="At most 20 words: why this is a defect."
    )


class MetadataOutlineCheck(BaseModel):
    """Structured comparison of front-matter and heading outline."""

    reasoning: str = Field(
        description="At most 40 words: what was compared."
    )
    title_matches: bool
    document_number_matches: bool
    date_matches: bool
    heading_drift: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Heading-level mismatches: 'h2:Abstract -> ###:Abstract' format."
    )
    missing_sections: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Source headings not found in candidate at any level."
    )
    verdict: Verdict

    @model_validator(mode="after")
    def pass_requires_no_mismatch(self) -> MetadataOutlineCheck:
        """Reject a clean verdict paired with an explicit mismatch."""
        has_mismatch = (
            not self.title_matches
            or not self.document_number_matches
            or not self.date_matches
            or bool(self.heading_drift)
            or bool(self.missing_sections)
        )
        if self.verdict == "pass" and has_mismatch:
            raise ValueError("metadata/outline pass cannot contain mismatches")
        return self


class UnitCheck(BaseModel):
    """Structured unit-based fidelity check for one risky region."""

    reasoning: str = Field(
        description="At most 40 words: what was compared."
    )
    unit_id: str = Field(
        description="The unit checked: 'page:5' or 'section:Motivation'"
    )
    defects: list[DefectFinding] = Field(
        default_factory=list,
        max_length=5,
        description="Defects found in this unit (max 5, most important first)."
    )
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def verdict_matches_defects(self) -> UnitCheck:
        """Reject pass-with-defects and non-pass-without-defects."""
        if (self.verdict == "pass") != (not self.defects):
            raise ValueError("unit verdict must be pass exactly when defects are empty")
        return self


# Named constants for max_tokens caps on verdict-first bifurcation
UNIT_CLEAR_MAX_TOKENS = 128
UNIT_DEFECTS_MAX_TOKENS = 768
# Confidence floor below which a UnitCheckClear is escalated to Defects
UNIT_CLEAR_CONFIDENCE_FLOOR = 0.85


class UnitCheckClear(BaseModel):
    """Pass-path micro-schema: no defects, verdict locked to pass."""

    unit_id: str = Field(
        description="The unit checked: 'page:5' or 'section:Motivation'"
    )
    verdict: Literal["pass"] = Field(
        description="Clear path only; non-pass routes to UnitCheckDefects."
    )
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(
        default="",
        description="Optional; at most 10 words. Empty on clean pass preferred.",
    )

    @model_validator(mode="after")
    def pass_is_clean(self) -> UnitCheckClear:
        if self.verdict != "pass":
            raise ValueError("UnitCheckClear requires verdict pass")
        return self


class UnitCheckDefects(BaseModel):
    """Full defect path for non-pass units."""

    unit_id: str = Field(
        description="The unit checked: 'page:5' or 'section:Motivation'"
    )
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(
        description="At most 40 words: what was compared."
    )
    defects: list[DefectFinding] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def verdict_matches_defects(self) -> UnitCheckDefects:
        has = bool(self.defects)
        if self.verdict == "pass" and has:
            raise ValueError("pass verdict must have no defects")
        if self.verdict == "not-llm-readable" and not has:
            raise ValueError("fail verdict must have defects")
        return self


def to_unit_check(clear: UnitCheckClear) -> UnitCheck:
    """Map a UnitCheckClear to the persistence-compatible UnitCheck shape."""
    return UnitCheck(
        reasoning=clear.reasoning or "unit matches",
        unit_id=clear.unit_id,
        defects=[],
        verdict="pass",
        confidence=clear.confidence,
    )


@dataclass
class TapetumResult:
    """Advisory adjudication of one candidate paper. Library returns; CLI persists.

    ``grounded_evidence`` entries are dicts with keys ``quote``, ``status``
    (``"exact"`` or ``"fuzzy"``), and ``start``/``end`` (char interval into the
    raw markdown for exact grounding; ``None`` for fuzzy). ``escalation_signals``
    names the derived uncertainty signals that fired the tier-2 escalation
    (empty when the tier-1 verdict stood).
    """

    pid: str
    whisker_verdict: str
    suggested_verdict: str
    confidence: float
    escalated: bool
    tier1_model: str
    tier2_model: str | None
    axis_findings: list[dict] = field(default_factory=list)
    grounded_evidence: list[dict] = field(default_factory=list)
    evidence_dispositions: list[dict] = field(default_factory=list)
    evidence_summary: dict[str, int] = field(default_factory=dict)
    ungrounded_dropped: int = 0
    escalation_signals: list[str] = field(default_factory=list)
    primary_concern: str = ""
    reasoning: str = ""
    # "ok" for a successful adjudication, "error" when the pipeline failed and
    # this is a fallback stub. Distinguishes a real review from a pipeline error
    # so fusion can treat them differently.
    status: str = "ok"
    # Source-aware unit check results (v6+, HTML and PDF paths)
    risk_signals: list[dict] = field(default_factory=list)
    defect_groups: list[dict] = field(default_factory=list)
    unit_checks: list[dict] = field(default_factory=list)
    metadata_outline_check: dict = field(default_factory=dict)
    unit_coverage: dict = field(default_factory=dict)
    unit_selection: list[dict] = field(default_factory=list)
    table_compare: dict = field(default_factory=dict)
    llm_readability: dict = field(default_factory=dict)
    ideal_verification: IdealVerification | None = None
    ideal_pending: bool = False
    code_boundary: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Deterministic, JSON-serializable view (sorted spans, rounded floats)."""
        result = {
            "pid": self.pid,
            "status": self.status,
            "whisker_verdict": self.whisker_verdict,
            "suggested_verdict": self.suggested_verdict,
            "confidence": round(self.confidence, 4),
            "escalated": self.escalated,
            "escalation_signals": sorted(self.escalation_signals),
            "tier1_model": self.tier1_model,
            "tier2_model": self.tier2_model,
            "axis_findings": sorted(
                self.axis_findings, key=lambda d: d.get("axis", "")
            ),
            "grounded_evidence": sorted(
                self.grounded_evidence,
                key=lambda d: (d.get("quote", ""), d.get("start") or -1),
            ),
            "evidence_dispositions": sorted(
                self.evidence_dispositions,
                key=lambda d: (
                    d.get("unit_id", ""),
                    d.get("quote", ""),
                    d.get("candidate_status", ""),
                ),
            ),
            "evidence_summary": self.evidence_summary,
            "ungrounded_dropped": self.ungrounded_dropped,
            "primary_concern": self.primary_concern,
            "reasoning": self.reasoning,
            "metadata_outline_check": self.metadata_outline_check,
            "unit_coverage": self.unit_coverage,
            "advisory": True,
            # v9: adds evaluated_at (B2 warm marker, cli.py._persist_result),
            # set only on an actual evaluation, never on a fingerprint skip.
            "schema_version": 9,
        }
        if self.risk_signals:
            result["risk_signals"] = self.risk_signals
        if self.defect_groups:
            result["defect_groups"] = self.defect_groups
        if self.unit_checks:
            result["unit_checks"] = self.unit_checks
        if self.unit_selection:
            result["unit_selection"] = self.unit_selection
        if self.table_compare:
            result["table_compare"] = self.table_compare
        if self.llm_readability:
            result["llm_readability"] = self.llm_readability
        if self.ideal_verification is not None:
            result["ideal_verification"] = self.ideal_verification.model_dump()
        if self.ideal_pending:
            result["ideal_pending"] = True
        if self.code_boundary:
            result["code_boundary"] = self.code_boundary
        return result
