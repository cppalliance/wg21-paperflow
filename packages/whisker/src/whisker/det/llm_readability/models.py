#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Immutable models and vocabulary for the table-readability contract.

Every type here is a frozen dataclass over tuples and read-only mappings, so a
loaded contract, a resolved profile and a produced report cannot be mutated by
a consumer after the fact. The status vocabulary is deliberately five-valued:
``not_evaluated`` exists so an unchecked rule can never be mistaken for a
passed one, which is the whole point of a certification contract.

The models carry no I/O and no evaluation logic. Loading lives in
``contract.py`` and ``profile.py``, evaluation in ``validate.py``, rendering in
``report.py``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

__all__ = [
    "CERTIFICATION_STATUSES",
    "CERTIFICATION_STATUS_CERTIFIED",
    "CERTIFICATION_STATUS_PENDING",
    "CheckOutcome",
    "CodeDocumentFacts",
    "CodeUnit",
    "DOCUMENT_VERDICTS",
    "DocumentFacts",
    "FORMAT_HTML",
    "FORMAT_PIPE",
    "Finding",
    "KnownWeakness",
    "METHODS",
    "METHOD_CERTIFICATION",
    "METHOD_DETERMINISTIC",
    "METHOD_LLM",
    "METHOD_SOURCE_COMPARE",
    "ModelProfile",
    "NUMERIC_TIGHTEN_DIRECTIONS",
    "ProfileProbe",
    "RULE_STATUSES",
    "ResolvedContract",
    "Rule",
    "RuleOverride",
    "RuleResult",
    "SCOPES",
    "SCOPE_CERTIFICATION",
    "SCOPE_CHUNKING",
    "SCOPE_REPRESENTATION",
    "SCOPE_SOURCE_FIDELITY",
    "STATUSES_VIOLATION",
    "STATUS_FAIL",
    "STATUS_NOT_APPLICABLE",
    "STATUS_NOT_EVALUATED",
    "STATUS_PASS",
    "STATUS_REVIEW",
    "STRENGTHS",
    "STRENGTH_CONTEXTUAL",
    "STRENGTH_HARD",
    "TABLE_FORMATS",
    "THRESHOLD_KINDS",
    "THRESHOLD_KIND_NUMERIC",
    "THRESHOLD_KIND_TOKEN_SET",
    "TIGHTEN_DECREASE",
    "TIGHTEN_GROW_SET",
    "TIGHTEN_INCREASE",
    "TIGHTEN_SHRINK_SET",
    "TOKEN_SET_TIGHTEN_DIRECTIONS",
    "TableContract",
    "TableReadabilityReport",
    "TableUnit",
    "Threshold",
    "VERDICT_FAIL",
    "VERDICT_INCOMPLETE",
    "VERDICT_NOT_APPLICABLE",
    "VERDICT_PASS",
    "VERDICT_REVIEW",
]

# -- Per-rule status vocabulary ------------------------------------------------
# `not_evaluated` is load-bearing: a rule nobody checked must never aggregate
# as if it had passed.
STATUS_PASS = "pass"
STATUS_FAIL = "not-llm-readable"
STATUS_REVIEW = "review"
STATUS_NOT_APPLICABLE = "not_applicable"
STATUS_NOT_EVALUATED = "not_evaluated"
RULE_STATUSES = (
    STATUS_PASS,
    STATUS_FAIL,
    STATUS_REVIEW,
    STATUS_NOT_APPLICABLE,
    STATUS_NOT_EVALUATED,
)
# The statuses a violated rule may carry, i.e. the legal values of a rule's
# declared `failure_status`.
STATUSES_VIOLATION = (STATUS_FAIL, STATUS_REVIEW)

# -- Document-level verdict vocabulary -----------------------------------------
VERDICT_PASS = "pass"
VERDICT_FAIL = "not-llm-readable"
VERDICT_REVIEW = "review"
VERDICT_INCOMPLETE = "incomplete"
VERDICT_NOT_APPLICABLE = "not_applicable"
DOCUMENT_VERDICTS = (
    VERDICT_PASS,
    VERDICT_FAIL,
    VERDICT_REVIEW,
    VERDICT_INCOMPLETE,
    VERDICT_NOT_APPLICABLE,
)

# -- Rule strength -------------------------------------------------------------
STRENGTH_HARD = "HARD"
STRENGTH_CONTEXTUAL = "CONTEXTUAL"
STRENGTHS = (STRENGTH_HARD, STRENGTH_CONTEXTUAL)

# -- Rule scope ----------------------------------------------------------------
SCOPE_REPRESENTATION = "representation"
SCOPE_SOURCE_FIDELITY = "source_fidelity"
SCOPE_CHUNKING = "chunking"
SCOPE_CERTIFICATION = "certification"
SCOPES = (
    SCOPE_REPRESENTATION,
    SCOPE_SOURCE_FIDELITY,
    SCOPE_CHUNKING,
    SCOPE_CERTIFICATION,
)

# -- Method ownership ----------------------------------------------------------
# Which lane owns proving a rule. A rule whose method did not run is
# `not_evaluated`, never `pass`.
METHOD_DETERMINISTIC = "deterministic"
METHOD_SOURCE_COMPARE = "source_compare"
METHOD_LLM = "llm"
METHOD_CERTIFICATION = "certification"
METHODS = (
    METHOD_DETERMINISTIC,
    METHOD_SOURCE_COMPARE,
    METHOD_LLM,
    METHOD_CERTIFICATION,
)

# -- Threshold kinds and tightening directions ---------------------------------
THRESHOLD_KIND_NUMERIC = "numeric"
THRESHOLD_KIND_TOKEN_SET = "token_set"
THRESHOLD_KINDS = (THRESHOLD_KIND_NUMERIC, THRESHOLD_KIND_TOKEN_SET)

TIGHTEN_DECREASE = "decrease"
TIGHTEN_INCREASE = "increase"
TIGHTEN_SHRINK_SET = "shrink_set"
TIGHTEN_GROW_SET = "grow_set"
NUMERIC_TIGHTEN_DIRECTIONS = (TIGHTEN_DECREASE, TIGHTEN_INCREASE)
TOKEN_SET_TIGHTEN_DIRECTIONS = (TIGHTEN_SHRINK_SET, TIGHTEN_GROW_SET)

# -- Table formats -------------------------------------------------------------
FORMAT_PIPE = "pipe"
FORMAT_HTML = "html"
TABLE_FORMATS = (FORMAT_PIPE, FORMAT_HTML)

# -- Profile certification honesty marker --------------------------------------
CERTIFICATION_STATUS_PENDING = "pending"
CERTIFICATION_STATUS_CERTIFIED = "certified"
CERTIFICATION_STATUSES = (
    CERTIFICATION_STATUS_PENDING,
    CERTIFICATION_STATUS_CERTIFIED,
)


@dataclass(frozen=True, slots=True)
class Threshold:
    """One named tunable a rule depends on.

    ``tighten`` states which direction is stricter, so a profile override can
    be mechanically checked for strengthening instead of trusted.
    """

    name: str
    kind: str
    tighten: str
    unit: str
    rationale: str
    rules: tuple[str, ...]
    value: int | float | None = None
    values: tuple[str, ...] | None = None

    def rendered_value(self) -> str:
        if self.kind == THRESHOLD_KIND_TOKEN_SET:
            return ", ".join(sorted(self.values or ()))
        return f"{self.value}"


@dataclass(frozen=True, slots=True)
class Rule:
    """One normative rule, loaded verbatim from the contract data."""

    id: str
    title: str
    strength: str
    scope: str
    method: str
    applicability: str
    check_id: str
    failure_status: str
    requirement: str
    rationale: str
    llm_instruction: str
    evidence: tuple[str, ...]
    thresholds: tuple[str, ...]
    profile_requirements: tuple[str, ...] = ()
    profile_instructions: tuple[str, ...] = ()

    @property
    def is_hard(self) -> bool:
        return self.strength == STRENGTH_HARD


@dataclass(frozen=True, slots=True)
class TableContract:
    """The contract as loaded from a model's ``rules.toml``."""

    id: str
    version: str
    schema_version: int
    title: str
    authority: str
    rules: tuple[Rule, ...]
    thresholds: Mapping[str, Threshold]
    applicability: Mapping[str, str]
    hash: str

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return tuple(rule.id for rule in self.rules)

    def rule(self, rule_id: str) -> Rule:
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        raise KeyError(rule_id)


@dataclass(frozen=True, slots=True)
class ProfileProbe:
    """A model-specific probe a certification run must execute."""

    id: str
    rules: tuple[str, ...]
    description: str
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class KnownWeakness:
    """A measured or cited weakness of the profiled model."""

    id: str
    rules: tuple[str, ...]
    description: str
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuleOverride:
    """A profile's additive or strengthening change to one core rule.

    There is deliberately no field for disabling a rule, for lowering its
    strength, or for replacing its requirement, method, scope, applicability or
    check owner. The absence is the enforcement.
    """

    rule_id: str
    strength: str | None = None
    additional_requirement: str | None = None
    additional_llm_instruction: str | None = None


@dataclass(frozen=True, slots=True)
class ModelProfile:
    """A model profile layered over the universal contract."""

    id: str
    version: str
    schema_version: int
    display_name: str
    model_ids: tuple[str, ...]
    aliases: tuple[str, ...]
    services: tuple[str, ...]
    backend: str
    required_methods: tuple[str, ...]
    required_rules: tuple[str, ...]
    threshold_overrides: Mapping[str, int | float | tuple[str, ...]]
    rule_overrides: Mapping[str, RuleOverride]
    probes: tuple[ProfileProbe, ...]
    known_weaknesses: tuple[KnownWeakness, ...]
    evidence: tuple[str, ...]
    notes: str
    hash: str
    requires_core_contract_version: str = ""
    certification_status: str = ""

    @property
    def model_identity(self) -> str:
        return self.model_ids[0]


@dataclass(frozen=True, slots=True)
class ResolvedContract:
    """The universal contract, optionally merged with one model profile."""

    core: TableContract
    profile: ModelProfile | None
    rules: tuple[Rule, ...]
    thresholds: Mapping[str, Threshold]

    @property
    def core_version(self) -> str:
        return self.core.version

    @property
    def core_hash(self) -> str:
        return self.core.hash

    @property
    def profile_id(self) -> str | None:
        return self.profile.id if self.profile is not None else None

    @property
    def profile_version(self) -> str | None:
        return self.profile.version if self.profile is not None else None

    @property
    def profile_hash(self) -> str | None:
        return self.profile.hash if self.profile is not None else None

    @property
    def model_identity(self) -> str | None:
        return self.profile.model_identity if self.profile is not None else None

    def rule(self, rule_id: str) -> Rule:
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        raise KeyError(rule_id)


@dataclass(frozen=True, slots=True)
class TableUnit:
    """One table handed to the evaluator by a producing lane.

    The evaluator owns no parser. A lane supplies the units it managed to
    extract and leaves every field it could not determine at ``None``; an
    unknown field makes the depending check ``not_evaluated`` rather than
    passing it by omission.

    ``raw_rows`` is the verbatim row text without the separator line. It is
    required for the escape-sensitive checks, because a cell splitter that
    ignores escapes reproduces the very defect R6 forbids.
    """

    index: int
    fmt: str
    cells: tuple[tuple[str, ...], ...]
    raw_rows: tuple[str, ...] | None = None
    has_header: bool | None = None
    has_separator: bool | None = None
    spans_declared: bool | None = None
    caption_distance_lines: int | None = None
    continuation_of: int | None = None
    data_as_header: bool = False
    wrap_bleed: bool = False
    header_is_data: bool = False
    truncated_leak: bool = False
    row_merge: bool = False
    wrap_orphan: bool = False
    hyphen_glue: bool = False
    flattened_prose: bool = False
    wording_clause: bool = False
    trailing_row_leak: bool = False
    absorbed_prose_row: bool = False

    @property
    def locus(self) -> str:
        return f"{self.fmt} table {self.index + 1}"

    @property
    def row_count(self) -> int:
        return len(self.cells)

    @property
    def column_count(self) -> int:
        return max((len(row) for row in self.cells), default=0)

    @property
    def cell_count(self) -> int:
        return sum(len(row) for row in self.cells)


@dataclass(frozen=True, slots=True)
class CodeUnit:
    """One fenced code block handed to the codeblock evaluator.

    The evaluator owns no parser. A lane supplies the units it extracted
    and leaves every field it could not determine at its zero value; the
    depending check treats an absent field as ``not_evaluated``.
    """

    index: int
    lang: str
    body_lines: tuple[str, ...]
    fence_style: str

    @property
    def locus(self) -> str:
        tag = f" ({self.lang})" if self.lang else ""
        return f"fence {self.index + 1}{tag}"

    @property
    def is_empty(self) -> bool:
        return not any(line.strip() for line in self.body_lines)


@dataclass(frozen=True, slots=True)
class CodeDocumentFacts:
    """Document-level facts for codeblock rule applicability."""

    fence_count: int = 0
    source_available: bool = False


@dataclass(frozen=True, slots=True)
class DocumentFacts:
    """The document-level facts rule applicability is decided on."""

    table_count: int = 0
    pipe_table_count: int = 0
    html_table_count: int = 0
    max_columns: int = 0
    max_rows: int = 0
    max_cells: int = 0
    tables_with_empty_cells: int = 0
    source_available: bool = False
    chunking_evaluated: bool = False


@dataclass(frozen=True, slots=True)
class Finding:
    """One concrete piece of evidence for a rule's status."""

    rule_id: str
    locus: str
    message: str
    evidence: str = ""


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    """What a registered check returns for one rule."""

    status: str
    findings: tuple[Finding, ...] = ()
    reason: str = ""


@dataclass(frozen=True, slots=True)
class RuleResult:
    """The evaluated status of one rule for one document."""

    rule_id: str
    strength: str
    scope: str
    method: str
    check_id: str
    status: str
    reason: str = ""
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True, slots=True)
class TableReadabilityReport:
    """The auditable result of evaluating one document against the contract.

    Three verdicts are kept apart on purpose. ``document_deterministic_ok`` is
    what candidate markdown alone can establish. ``model_certified`` additionally
    requires a resolved profile, every method the profile demands, and no
    applicable HARD rule left failing or unevaluated. ``certified`` is an alias
    of ``model_certified`` and is never derivable from candidate markdown alone.
    """

    core_id: str
    core_version: str
    core_hash: str
    profile_id: str | None
    profile_version: str | None
    profile_hash: str | None
    model_identity: str | None
    methods_executed: tuple[str, ...]
    table_count: int
    vacuous: bool
    verdict: str
    document_deterministic_ok: bool
    model_certified: bool
    blocking_reasons: tuple[str, ...]
    results: tuple[RuleResult, ...]

    @property
    def certified(self) -> bool:
        return self.model_certified

    def result(self, rule_id: str) -> RuleResult:
        for item in self.results:
            if item.rule_id == rule_id:
                return item
        raise KeyError(rule_id)

    def statuses(self) -> Mapping[str, str]:
        return {item.rule_id: item.status for item in self.results}
