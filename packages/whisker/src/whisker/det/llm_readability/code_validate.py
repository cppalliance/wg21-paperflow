#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Deterministic checks and evaluation for the codeblock-readability contract.

Parallel to ``validate.py`` for tables. The two modules share the same model
types (``Rule``, ``ResolvedContract``, ``TableReadabilityReport``) but carry
separate applicability predicates, document-facts constructors and check
registries. This module must not import from ``validate.py``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence

from whisker.det.llm_readability.contract import ContractSchemaError
from whisker.det.llm_readability.models import (
    METHOD_DETERMINISTIC,
    METHODS,
    STATUS_FAIL,
    STATUS_NOT_APPLICABLE,
    STATUS_NOT_EVALUATED,
    STATUS_PASS,
    STATUS_REVIEW,
    STRENGTH_HARD,
    VERDICT_FAIL,
    VERDICT_INCOMPLETE,
    VERDICT_NOT_APPLICABLE,
    VERDICT_PASS,
    VERDICT_REVIEW,
    CheckOutcome,
    CodeDocumentFacts,
    CodeUnit,
    Finding,
    ResolvedContract,
    Rule,
    RuleResult,
    TableReadabilityReport,
    Threshold,
)

__all__ = [
    "CODE_APPLICABILITY_PREDICATES",
    "CodeCheckContext",
    "DETERMINISTIC_CODE_CHECKS",
    "code_document_facts",
    "code_units_from_markdown",
    "code_units_with_spans",
    "default_code_registry",
    "evaluate_code",
]

# -- fence parser --------------------------------------------------------------

_FENCE_OPEN_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")

_SPEC_ELEMENT_PREFIXES = (
    "Mandates:",
    "Preconditions:",
    "Effects:",
    "Returns:",
    "Throws:",
    "Complexity:",
    "Remarks:",
    "Ensures:",
)

_BOX_DRAWING_RE = re.compile(
    r"[│┤├┼─┬┴┐┘┌└╔╗╚╝║═╠╣╦╩╬]{3,}"
    r"|"
    r"[|+\-]{5,}"
)

# -- calibration constants (additive only, see llm/calibration/codeblocks/CODEBLOCK-CALIBRATION.md)

_SURVIVAL_KEYWORDS = frozenset({"constexpr", "consteval", "requires", "concept"})
_MICRO_FENCE_MAX_BODY_LINES = 2
_MICRO_FENCE_RUN_MIN = 3
_LETTERED_HEADING_RE = re.compile(r"^[A-Z]\.\s{1,4}\S")
_STABLE_NAME_BRACKET_RE = re.compile(r"\[[a-z][a-z0-9_.]+\]\s*$")
_FALSE_WORDING_COMMENT_RE = re.compile(r"<(?:ins|del)>\s*//")
_ELLIPSIS_ONLY_RE = re.compile(r"^\s*\.\.\.\s*$")


def _iter_code_units(
    text: str,
) -> Iterable[tuple[CodeUnit, int, int]]:
    """Yield ``(CodeUnit, start_line, end_line)`` for every fenced code block.

    *start_line* is the 0-based index of the opening fence; *end_line* is
    the 0-based index of the closing fence (or the last body line when
    the fence is unclosed).
    """
    lines = text.split("\n")
    idx = 0
    unit_index = 0
    while idx < len(lines):
        match = _FENCE_OPEN_RE.match(lines[idx])
        if match:
            fence_char = match.group(2)[0]
            fence_len = len(match.group(2))
            info = match.group(3).strip()
            lang = info.split()[0] if info else ""
            if fence_char == "`" and "`" in lang:
                lang = ""
            fence_style = "backtick" if fence_char == "`" else "tilde"
            close_re = re.compile(
                r"^ {0,3}" + re.escape(fence_char) + r"{" + str(fence_len) + r",}\s*$"
            )
            start_line = idx
            body_lines: list[str] = []
            idx += 1
            while idx < len(lines):
                if close_re.match(lines[idx]):
                    break
                body_lines.append(lines[idx])
                idx += 1
            end_line = idx if idx < len(lines) else idx - 1
            yield (
                CodeUnit(
                    index=unit_index,
                    lang=lang,
                    body_lines=tuple(body_lines),
                    fence_style=fence_style,
                ),
                start_line,
                end_line,
            )
            unit_index += 1
        idx += 1


def code_units_from_markdown(text: str) -> tuple[CodeUnit, ...]:
    """Parse fenced code blocks from markdown text into :class:`CodeUnit` s."""
    return tuple(unit for unit, _, _ in _iter_code_units(text))


def code_units_with_spans(
    text: str,
) -> tuple[tuple[CodeUnit, int, int], ...]:
    """Like :func:`code_units_from_markdown` but includes line offsets.

    Returns ``((CodeUnit, start_line, end_line), ...)`` where both line
    numbers are 0-based indices into the ``text.split("\\n")`` list.
    *start_line* is the opening fence, *end_line* the closing fence.
    """
    return tuple(_iter_code_units(text))


# -- document facts and applicability ------------------------------------------

CodeApplicabilityPredicate = Callable[
    [CodeDocumentFacts, Mapping[str, Threshold]], bool
]


def code_document_facts(
    units: Sequence[CodeUnit],
    *,
    source_available: bool = False,
) -> CodeDocumentFacts:
    return CodeDocumentFacts(
        fence_count=len(units),
        source_available=source_available,
    )


def _any_code_fence(
    facts: CodeDocumentFacts, _: Mapping[str, Threshold]
) -> bool:
    return facts.fence_count > 0


def _any_document(
    facts: CodeDocumentFacts, _: Mapping[str, Threshold]
) -> bool:
    return True


def _source_compare(
    facts: CodeDocumentFacts, _: Mapping[str, Threshold]
) -> bool:
    return facts.source_available


CODE_APPLICABILITY_PREDICATES: Mapping[str, CodeApplicabilityPredicate] = {
    "any_code_fence": _any_code_fence,
    "any_document": _any_document,
    "source_compare": _source_compare,
}

# -- check context and type alias ----------------------------------------------

CodeCheck = Callable[["CodeCheckContext"], CheckOutcome]


class CodeCheckContext:
    """All data a deterministic codeblock check receives."""

    __slots__ = ("rule", "units", "facts", "resolved", "markdown_text")

    def __init__(
        self,
        *,
        rule: Rule,
        units: tuple[CodeUnit, ...],
        facts: CodeDocumentFacts,
        resolved: ResolvedContract,
        markdown_text: str,
    ) -> None:
        self.rule = rule
        self.units = units
        self.facts = facts
        self.resolved = resolved
        self.markdown_text = markdown_text


# -- deterministic checks ------------------------------------------------------


def _listing_split_findings(units: tuple[CodeUnit, ...]) -> list[Finding]:
    """Detect listing-split patterns: ellipsis-only fences, lone survival
    keywords as their own fence, and runs of micro-fences that suggest a
    single listing was fragmented.

    Evidence: HEAD p0533r9 lines 198-220 (``...`` fence, lone ``constexpr``
    fence, ``frexp`` in its own fence after the split).
    """
    findings: list[Finding] = []
    for unit in units:
        non_blank = [ln for ln in unit.body_lines if ln.strip()]
        if len(non_blank) == 1 and _ELLIPSIS_ONLY_RE.match(non_blank[0]):
            findings.append(
                Finding(
                    rule_id="C1",
                    locus=unit.locus,
                    message="fence body is only '...'; likely a split listing",
                )
            )
            continue
        if (
            len(non_blank) == 1
            and non_blank[0].strip() in _SURVIVAL_KEYWORDS
        ):
            findings.append(
                Finding(
                    rule_id="C1",
                    locus=unit.locus,
                    message=(
                        f"fence body is a lone survival keyword "
                        f"'{non_blank[0].strip()}'; likely a split listing"
                    ),
                )
            )
    run_start = 0
    while run_start < len(units):
        run_len = 1
        while run_start + run_len < len(units):
            candidate = units[run_start + run_len]
            prev = units[run_start + run_len - 1]
            non_blank_prev = [ln for ln in prev.body_lines if ln.strip()]
            non_blank_cand = [ln for ln in candidate.body_lines if ln.strip()]
            if (
                len(non_blank_prev) <= _MICRO_FENCE_MAX_BODY_LINES
                and len(non_blank_cand) <= _MICRO_FENCE_MAX_BODY_LINES
                and candidate.index == prev.index + 1
            ):
                run_len += 1
            else:
                break
        if run_len >= _MICRO_FENCE_RUN_MIN:
            first = units[run_start]
            findings.append(
                Finding(
                    rule_id="C1",
                    locus=first.locus,
                    message=(
                        f"{run_len} adjacent micro-fences "
                        f"(<=2 body lines each); likely a fragmented listing"
                    ),
                )
            )
        run_start += max(run_len, 1)
    return findings


def _check_listing_is_fenced(ctx: CodeCheckContext) -> CheckOutcome:
    """C1: detect listing-split fragments from candidate markdown alone.

    Full completeness (are all listings fenced?) requires source comparison.
    The candidate-side check catches ellipsis-only fences, lone survival
    keywords, and runs of micro-fences.
    """
    findings = _listing_split_findings(ctx.units)
    if findings:
        return CheckOutcome(status=STATUS_FAIL, findings=tuple(findings))
    return CheckOutcome(status=STATUS_PASS)


def _check_empty_fence(ctx: CodeCheckContext) -> CheckOutcome:
    """C2: fail if any fence body is empty or whitespace-only."""
    findings: list[Finding] = []
    for unit in ctx.units:
        if unit.is_empty:
            findings.append(
                Finding(
                    rule_id="C2",
                    locus=unit.locus,
                    message="fence body is empty or whitespace-only",
                )
            )
    if findings:
        return CheckOutcome(status=STATUS_FAIL, findings=tuple(findings))
    return CheckOutcome(status=STATUS_PASS)


def _false_wording_on_comment_findings(
    units: tuple[CodeUnit, ...],
) -> list[Finding]:
    """Detect ``<ins>`` or ``<del>`` tags wrapping only a ``//`` comment
    inside a code fence, which is a false positive from wording-change
    tracking (the comment is code, not prose).

    Evidence: BASE p2040r0 lines 34-37 (``<ins>// ko</ins>``).
    """
    findings: list[Finding] = []
    for unit in units:
        for line in unit.body_lines:
            stripped = line.strip()
            if _FALSE_WORDING_COMMENT_RE.search(stripped):
                findings.append(
                    Finding(
                        rule_id="C6",
                        locus=unit.locus,
                        message=(
                            f"<ins>/<del> wraps only a // comment "
                            f"inside fence: {stripped[:80]!r}"
                        ),
                    )
                )
    return findings


def _check_wording_in_fence(ctx: CodeCheckContext) -> CheckOutcome:
    """C6: fail if leftover ``:::wording*`` divs exist, or if ``<ins>/<del>``
    tags wrap only a ``//`` comment inside a code fence."""
    findings: list[Finding] = []
    for line_no, line in enumerate(ctx.markdown_text.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith(":::wording"):
            findings.append(
                Finding(
                    rule_id="C6",
                    locus=f"line {line_no}",
                    message=f"leftover wording div: {stripped!r}",
                )
            )
    findings.extend(_false_wording_on_comment_findings(ctx.units))
    if findings:
        return CheckOutcome(status=STATUS_FAIL, findings=tuple(findings))
    return CheckOutcome(status=STATUS_PASS)


def _heading_in_fence_findings(unit: CodeUnit) -> list[Finding]:
    """Detect a section heading swallowed into a code fence.

    Fires when the first non-blank fence line is a lettered heading
    (``F.  Modifications to ...``) or ends with a stable-name bracket
    (``[cmath.syn]``).

    Evidence: BASE p0533r9 line 206 (``F.  Modifications to "Header
    <cmath> synopsis" [cmath.syn]`` inside a ``cpp`` fence).
    """
    findings: list[Finding] = []
    for line in unit.body_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _LETTERED_HEADING_RE.match(stripped):
            findings.append(
                Finding(
                    rule_id="C7",
                    locus=unit.locus,
                    message=(
                        f"lettered heading inside fence body: "
                        f"{stripped[:60]!r}"
                    ),
                )
            )
        elif _STABLE_NAME_BRACKET_RE.search(stripped):
            findings.append(
                Finding(
                    rule_id="C7",
                    locus=unit.locus,
                    message=(
                        f"prose with stable-name bracket inside fence: "
                        f"{stripped[:60]!r}"
                    ),
                )
            )
        break
    return findings


def _check_font_is_not_kind(ctx: CodeCheckContext) -> CheckOutcome:
    """C7: fail if a fence body contains spec-element prefixes, a heading
    swallowed into the fence, or pure prose."""
    findings: list[Finding] = []
    for unit in ctx.units:
        if not unit.body_lines:
            continue
        first_non_blank = ""
        for line in unit.body_lines:
            if line.strip():
                first_non_blank = line.strip()
                break
        spec_hit = False
        for prefix in _SPEC_ELEMENT_PREFIXES:
            if first_non_blank.startswith(prefix):
                findings.append(
                    Finding(
                        rule_id="C7",
                        locus=unit.locus,
                        message=f"spec-element prefix {prefix!r} inside fence body",
                    )
                )
                spec_hit = True
                break
        if not spec_hit:
            findings.extend(_heading_in_fence_findings(unit))
    if findings:
        return CheckOutcome(status=STATUS_FAIL, findings=tuple(findings))
    return CheckOutcome(status=STATUS_PASS)


def _check_cell_listing_excluded(ctx: CodeCheckContext) -> CheckOutcome:
    """C8: always passes; cell listings are table R11 territory."""
    return CheckOutcome(status=STATUS_PASS)


def _check_diagram_not_cpp(ctx: CodeCheckContext) -> CheckOutcome:
    """C9: review if a ``cpp``-tagged fence contains box-drawing or ASCII art."""
    findings: list[Finding] = []
    for unit in ctx.units:
        if unit.lang != "cpp":
            continue
        body = "\n".join(unit.body_lines)
        if _BOX_DRAWING_RE.search(body):
            findings.append(
                Finding(
                    rule_id="C9",
                    locus=unit.locus,
                    message="fence tagged cpp contains ASCII art or box-drawing",
                )
            )
    if findings:
        return CheckOutcome(status=STATUS_REVIEW, findings=tuple(findings))
    return CheckOutcome(status=STATUS_PASS)


DETERMINISTIC_CODE_CHECKS: Mapping[str, CodeCheck] = {
    "listing_is_fenced": _check_listing_is_fenced,
    "empty_fence": _check_empty_fence,
    "wording_in_fence": _check_wording_in_fence,
    "font_is_not_kind": _check_font_is_not_kind,
    "cell_listing_excluded": _check_cell_listing_excluded,
    "diagram_not_cpp": _check_diagram_not_cpp,
}


def default_code_registry() -> dict[str, CodeCheck]:
    """Return a mutable copy of the built-in deterministic code checks."""
    return dict(DETERMINISTIC_CODE_CHECKS)


# -- evaluation engine ---------------------------------------------------------


def _normalize_methods(
    methods_executed: Iterable[str],
) -> tuple[str, ...]:
    methods = tuple(sorted(set(methods_executed)))
    for method in methods:
        if method not in METHODS:
            raise ValueError(f"unknown evaluation method {method!r}")
    return methods


def _evaluate_rule(
    rule: Rule,
    *,
    ctx_units: tuple[CodeUnit, ...],
    facts: CodeDocumentFacts,
    resolved: ResolvedContract,
    methods_executed: tuple[str, ...],
    registry: Mapping[str, CodeCheck],
    markdown_text: str,
) -> RuleResult:
    if rule.method not in methods_executed:
        return RuleResult(
            rule_id=rule.id,
            strength=rule.strength,
            scope=rule.scope,
            method=rule.method,
            check_id=rule.check_id,
            status=STATUS_NOT_EVALUATED,
            reason=f"method {rule.method!r} not executed",
        )
    predicate = CODE_APPLICABILITY_PREDICATES.get(rule.applicability)
    if predicate is None or not predicate(facts, resolved.thresholds):
        return RuleResult(
            rule_id=rule.id,
            strength=rule.strength,
            scope=rule.scope,
            method=rule.method,
            check_id=rule.check_id,
            status=STATUS_NOT_APPLICABLE,
        )
    check = registry.get(rule.check_id)
    if check is None:
        return RuleResult(
            rule_id=rule.id,
            strength=rule.strength,
            scope=rule.scope,
            method=rule.method,
            check_id=rule.check_id,
            status=STATUS_NOT_EVALUATED,
            reason=f"no check registered for {rule.check_id!r}",
        )
    ctx = CodeCheckContext(
        rule=rule,
        units=ctx_units,
        facts=facts,
        resolved=resolved,
        markdown_text=markdown_text,
    )
    outcome = check(ctx)
    allowed = {STATUS_PASS, rule.failure_status}
    if outcome.status not in allowed:
        raise ContractSchemaError(
            f"check {rule.check_id!r} returned status {outcome.status!r} for "
            f"rule {rule.id!r}, which does not allow it "
            f"(allowed: {', '.join(sorted(allowed))})"
        )
    return RuleResult(
        rule_id=rule.id,
        strength=rule.strength,
        scope=rule.scope,
        method=rule.method,
        check_id=rule.check_id,
        status=outcome.status,
        reason=outcome.reason,
        findings=outcome.findings,
    )


def _verdict(results: tuple[RuleResult, ...], *, vacuous: bool) -> str:
    if vacuous:
        return VERDICT_NOT_APPLICABLE
    statuses = {item.status for item in results}
    if STATUS_FAIL in statuses:
        return VERDICT_FAIL
    if STATUS_NOT_EVALUATED in statuses:
        return VERDICT_INCOMPLETE
    if STATUS_REVIEW in statuses:
        return VERDICT_REVIEW
    return VERDICT_PASS


def _deterministic_ok(results: tuple[RuleResult, ...], *, vacuous: bool) -> bool:
    if vacuous:
        return False
    for item in results:
        if item.method != METHOD_DETERMINISTIC:
            continue
        if item.status in (STATUS_FAIL, STATUS_NOT_EVALUATED):
            return False
    return True


def _blocking_reasons(
    results: tuple[RuleResult, ...],
    *,
    resolved: ResolvedContract,
    methods_executed: tuple[str, ...],
    vacuous: bool,
) -> tuple[str, ...]:
    if vacuous:
        return ("vacuous",)
    reasons: list[str] = []
    profile = resolved.profile
    if profile is not None:
        for method in profile.required_methods:
            if method not in methods_executed:
                reasons.append(f"required_method_not_executed:{method}")
        for rule_id in profile.required_rules:
            for item in results:
                if item.rule_id == rule_id and item.status == STATUS_NOT_EVALUATED:
                    reasons.append(f"required_rule_not_evaluated:{rule_id}")
    for item in results:
        if item.status == STATUS_FAIL:
            reasons.append(f"rule_fail:{item.rule_id}")
        elif item.status == STATUS_REVIEW:
            reasons.append(f"rule_review:{item.rule_id}")
        elif item.status == STATUS_NOT_EVALUATED and item.strength == STRENGTH_HARD:
            reasons.append(f"hard_rule_not_evaluated:{item.rule_id}")
    return tuple(sorted(set(reasons)))


def evaluate_code(
    resolved: ResolvedContract,
    units: Sequence[CodeUnit],
    *,
    methods_executed: Iterable[str] = (METHOD_DETERMINISTIC,),
    source_available: bool = False,
    registry: Mapping[str, CodeCheck] | None = None,
    markdown_text: str = "",
) -> TableReadabilityReport:
    """Evaluate one document against the codeblock contract.

    Returns a :class:`TableReadabilityReport` where ``table_count`` holds the
    fence count, keeping the report type shared across constructs.
    """
    _validate_applicability_coverage(resolved)
    methods = _normalize_methods(methods_executed)
    checks = registry if registry is not None else DETERMINISTIC_CODE_CHECKS
    ordered_units = tuple(units)
    facts = code_document_facts(ordered_units, source_available=source_available)
    vacuous = facts.fence_count == 0
    results = tuple(
        _evaluate_rule(
            rule,
            ctx_units=ordered_units,
            facts=facts,
            resolved=resolved,
            methods_executed=methods,
            registry=checks,
            markdown_text=markdown_text,
        )
        for rule in resolved.rules
    )
    verdict = _verdict(results, vacuous=vacuous)
    blocking = _blocking_reasons(
        results,
        resolved=resolved,
        methods_executed=methods,
        vacuous=vacuous,
    )
    return TableReadabilityReport(
        core_id=resolved.core.id,
        core_version=resolved.core_version,
        core_hash=resolved.core_hash,
        profile_id=resolved.profile_id,
        profile_version=resolved.profile_version,
        profile_hash=resolved.profile_hash,
        model_identity=resolved.model_identity,
        methods_executed=methods,
        table_count=facts.fence_count,
        vacuous=vacuous,
        verdict=verdict,
        document_deterministic_ok=_deterministic_ok(results, vacuous=vacuous),
        model_certified=not blocking,
        blocking_reasons=blocking,
        results=results,
    )


def _validate_applicability_coverage(resolved: ResolvedContract) -> None:
    """Fail closed if the contract declares an applicability key with no predicate."""
    implemented = set(CODE_APPLICABILITY_PREDICATES)
    declared = set(resolved.core.applicability)
    missing = sorted(declared - implemented)
    if missing:
        raise ContractSchemaError(
            f"codeblock contract declares applicability predicates with no "
            f"implementation: {', '.join(missing)}"
        )
