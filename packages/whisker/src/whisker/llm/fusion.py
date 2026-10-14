#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Deterministic + LLM fusion: pure function merging both sidecar verdicts.

The fusion is a pure function: two dicts in (whisker sidecar, tapetum sidecar),
one ``FusionResult`` out. No I/O, no LLM calls, unit-testable at zero cost.
The merged verdict is **advisory**: it never replaces the deterministic whisker
verdict and never appears in ``whisker --gate`` exit codes.

The asymmetric fusion matrix (from the 25-persona research, Reports 13+19+20):

- tapetum absent / error / confidence-0-stub -> merged = det, whisker_only.
- det=fail: stays fail (whisker_fail_locked), EXCEPT heading-monotone-only fail
  + LLM pass/review -> merged review (llm_rescue_heading; never pass).
- det=review (only soft flags) + LLM pass (grounded, conf >= floor) -> merged
  pass (llm_clear_soft_review); guardrail: no upgrade when ref_nid < floor.
- det=pass + LLM fail(major via axis_findings severity) -> merged review
  (llm_escalate_major); merged never goes to fail when det is not fail.
- det=pass + LLM review, or LLM fail without a major axis -> merged review
  (llm_review_cap): a deterministic pass is never reported next to a
  non-pass primary tapetum verdict with no cap at all.
- schema-v6 source-aware metadata review/fail, accepted high/critical defect
  groups, or incomplete unit coverage cap a non-fail merge at review without
  consulting confidence. Refuted, ambiguous, or unverified claims do not demote.
- a separate ideal-verifier ``review`` caps a non-fail merge at review; ``agree``
  never promotes. Deterministic ``ideal `` soft flags also block LLM clear.
- Otherwise: merged = det (agree or whisker_only).
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from whisker.det.score import VERDICT_FAIL, VERDICT_PASS, VERDICT_REVIEW
from whisker.llm.constants import (
    FUSION_REF_NID_FLOOR,
    FUSION_RULE_AGREE,
    FUSION_RULE_CLEAR_BLOCKED_IDEAL_FLAG,
    FUSION_RULE_CLEAR_BLOCKED_MISSING_REGION,
    FUSION_RULE_IDEAL_REVIEW_CAP,
    FUSION_RULE_LLM_CLEAR_SOFT_REVIEW,
    FUSION_RULE_LLM_ESCALATE_MAJOR,
    FUSION_RULE_LLM_RESCUE_HEADING,
    FUSION_RULE_LLM_REVIEW_CAP,
    FUSION_RULE_SOURCE_AWARE_REVIEW_CAP,
    FUSION_RULE_WHISKER_FAIL_LOCKED,
    FUSION_RULE_WHISKER_ONLY,
    FUSION_SCHEMA_VERSION,
    IDEAL_SOFT_FLAG_PREFIX,
    SEVERITY_MAJOR,
)
from whisker.llm.grounding import CANDIDATE_NOT_FOUND, GROUND_EXACT
from whisker.llm.models import parse_ideal_verification

__all__ = ["FusionResult", "fuse_verdicts"]

_SOURCE_AWARE_REVIEW_SEVERITIES = frozenset({"high", "critical"})
_SIDECAR_VERDICTS = frozenset({VERDICT_PASS, VERDICT_REVIEW, VERDICT_FAIL})


@dataclass(frozen=True)
class FusionResult:
    """Immutable result of fusing deterministic + LLM verdicts."""

    combined_verdict: str
    combined_rule: str
    whisker_verdict: str
    tapetum_verdict: str
    tapetum_available: bool
    tapetum_confidence: float
    whisker_fingerprint: str
    ideal_verdict: str | None = None
    ideal_discrepancy_count: int = 0
    fusion_schema_version: int = FUSION_SCHEMA_VERSION
    advisory: bool = True

    def to_dict(self) -> dict:
        """Deterministic, JSON-serializable view."""
        return {
            "combined_verdict": self.combined_verdict,
            "combined_rule": self.combined_rule,
            "whisker_verdict": self.whisker_verdict,
            "tapetum_verdict": self.tapetum_verdict,
            "tapetum_available": self.tapetum_available,
            "tapetum_confidence": round(self.tapetum_confidence, 4),
            "whisker_fingerprint": self.whisker_fingerprint,
            "ideal_verdict": self.ideal_verdict,
            "ideal_discrepancy_count": self.ideal_discrepancy_count,
            "fusion_schema_version": self.fusion_schema_version,
            "advisory": self.advisory,
        }


def _whisker_fingerprint(whisker: dict) -> str:
    """Stable hash of the deterministic sidecar payload for staleness detection."""
    canonical = json.dumps(whisker, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _finite_float(value: object) -> float | None:
    """Parse a finite JSON numeric value without raising."""
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _validate_whisker_sidecar(value: object) -> dict | None:
    """Return a core-shape-valid deterministic sidecar object."""
    if not isinstance(value, dict):
        return None
    pid = value.get("pid")
    verdict = value.get("verdict")
    if not isinstance(pid, str) or not pid:
        return None
    if not isinstance(verdict, str) or verdict not in (*_SIDECAR_VERDICTS, "?"):
        return None
    return value


def _validate_tapetum_sidecar(value: object) -> dict | None:
    """Validate required advisory fields and sanitize optional fingerprint."""
    if not isinstance(value, dict):
        return None
    pid = value.get("pid")
    if not isinstance(pid, str) or not pid:
        return None

    sanitized = dict(value)
    if "fingerprint" in sanitized and not isinstance(
        sanitized["fingerprint"], dict
    ):
        sanitized.pop("fingerprint")

    if sanitized.get("status") == "error":
        return sanitized
    suggested = sanitized.get("suggested_verdict")
    if not isinstance(suggested, str) or suggested not in _SIDECAR_VERDICTS:
        return None
    confidence = _finite_float(sanitized.get("confidence"))
    if confidence is None:
        return None
    sanitized["confidence"] = confidence
    return sanitized


def _tapetum_is_usable(tapetum: dict | None) -> bool:
    """False when the tapetum sidecar is absent, errored, or a confidence-0 stub."""
    if tapetum is None:
        return False
    if tapetum.get("status") == "error":
        return False
    if _has_source_aware_data(tapetum):
        return True
    if tapetum.get("confidence", 0.0) == 0.0 and not tapetum.get("axis_findings"):
        return False
    return True


def _has_source_aware_data(tapetum: dict) -> bool:
    """True for schema-v6 or shape-compatible HTML/PDF source-aware sidecars."""
    schema_version = tapetum.get("schema_version", 0)
    return (
        (
            isinstance(schema_version, int)
            and not isinstance(schema_version, bool)
            and schema_version >= 6
        )
        or "metadata_outline_check" in tapetum
        or "unit_coverage" in tapetum
        or "defect_groups" in tapetum
    )


def _source_aware_requires_review(tapetum: dict) -> bool:
    """Fail-closed review cap for verified or incomplete source-aware evidence."""
    if not _has_source_aware_data(tapetum):
        return False

    metadata = tapetum.get("metadata_outline_check")
    if not isinstance(metadata, dict) or metadata.get("verdict") != VERDICT_PASS:
        return True

    coverage = tapetum.get("unit_coverage")
    if not isinstance(coverage, dict) or coverage.get("coverage_complete") is not True:
        return True
    if coverage.get("unchecked_unit_ids") or coverage.get("failed_unit_ids"):
        return True

    # All-pages sidecars must prove a non-empty required set with no gaps.
    # Absent/false all_pages_requested keeps legacy/routed/text behavior.
    if tapetum.get("all_pages_requested"):
        selection = tapetum.get("unit_selection")
        if not isinstance(selection, dict):
            return True
        required = selection.get("required") or []
        unchecked = selection.get("unchecked") or []
        failed = selection.get("failed") or []
        if not required or unchecked or failed:
            return True

    accepted_defects = _accepted_unit_defects(tapetum)
    accepted_dispositions = _accepted_flat_dispositions(tapetum)
    for group in tapetum.get("defect_groups", []):
        if group.get("severity") not in _SOURCE_AWARE_REVIEW_SEVERITIES:
            continue
        verification = group.get("count_verification", {})
        verified_count = group.get("verified_count")
        if (
            verification.get("count_status") == "verified"
            and isinstance(verified_count, (int, float))
            and verified_count > 0
        ):
            return True
        if _group_matches_accepted_defect(group, accepted_defects):
            return True
        if _group_matches_accepted_disposition(group, accepted_dispositions):
            return True

    return False


def _is_accepted_disposition(disposition: dict) -> bool:
    """True only for exact source evidence verified absent from the candidate."""
    return (
        disposition.get("source_status") == GROUND_EXACT
        and disposition.get("candidate_status") == CANDIDATE_NOT_FOUND
    )


def _accepted_unit_defects(tapetum: dict) -> list[dict]:
    """Return unit defects carrying unit_judge's explicit acceptance disposition."""
    return [
        defect
        for unit_check in tapetum.get("unit_checks", [])
        for defect in unit_check.get("defects", [])
        if defect.get("severity") in _SOURCE_AWARE_REVIEW_SEVERITIES
        and _is_accepted_disposition(defect.get("evidence_disposition", {}))
    ]


def _accepted_flat_dispositions(tapetum: dict) -> list[dict]:
    """Return accepted flattened unit evidence from HTML/PDF sidecars."""
    return [
        disposition
        for disposition in tapetum.get("evidence_dispositions", [])
        if disposition.get("unit_id")
        and _is_accepted_disposition(disposition)
    ]


def _group_quotes(group: dict) -> set[str]:
    """Quotes identifying the accepted claims aggregated into one defect group."""
    return {
        quote
        for quote in [group.get("source_quote", ""), *group.get("examples", [])]
        if quote
    }


def _group_matches_accepted_defect(group: dict, accepted: list[dict]) -> bool:
    """Match an aggregate group to its accepted nested unit-check claim."""
    quotes = _group_quotes(group)
    return any(
        defect.get("defect_type") == group.get("defect_type")
        and defect.get("source_quote") in quotes
        for defect in accepted
    )


def _group_matches_accepted_disposition(
    group: dict,
    accepted: list[dict],
) -> bool:
    """Match an aggregate group to a flattened unit disposition by quote."""
    quotes = _group_quotes(group)
    return any(
        any(
            quote == disposition.get("quote")
            or quote.startswith(disposition.get("quote", ""))
            for quote in quotes
        )
        for disposition in accepted
        if disposition.get("quote")
    )


def _has_major_axis_fail(tapetum: dict) -> bool:
    """True when at least one axis finding is fail+major (severity-fold on raw findings)."""
    for af in tapetum.get("axis_findings", []):
        if af.get("verdict") == VERDICT_FAIL and af.get("severity") == SEVERITY_MAJOR:
            return True
    return False


def _has_any_axis_fail(tapetum: dict) -> bool:
    """True when at least one axis finding has verdict=fail at any severity."""
    for af in tapetum.get("axis_findings", []):
        if af.get("verdict") == VERDICT_FAIL:
            return True
    return False


def _is_heading_only_fail(whisker: dict) -> bool:
    """True when the deterministic hard flags are exclusively heading_monotone.

    Match on the gate NAME prefix, never on the whole flag string: gate details
    quote document text, and e.g. a no_toc_leak detail like "duplicate heading
    '1. introduction' ..." would substring-match "heading" and wrongly qualify
    a TOC-leak fail for the rescue path.
    """
    hard = whisker.get("hard_flags", [])
    if not hard:
        return False
    return all(f.startswith("gate:heading_monotone") for f in hard)


def _has_only_soft_flags(whisker: dict) -> bool:
    """True when the deterministic verdict is driven entirely by soft flags."""
    return bool(whisker.get("soft_flags")) and not whisker.get("hard_flags")


def _has_ideal_soft_flag(whisker: dict) -> bool:
    """True when deterministic golden-ideal scoring requested review."""
    return any(
        isinstance(flag, str) and flag.startswith(IDEAL_SOFT_FLAG_PREFIX)
        for flag in whisker.get("soft_flags", [])
    )


def _ideal_summary(tapetum: dict | None) -> tuple[str | None, int]:
    """Return compact verifier status, accepting old sidecars with no ideal data."""
    verification = parse_ideal_verification(
        (tapetum or {}).get("ideal_verification")
    )
    if verification is None:
        return None, 0
    return verification.verdict, len(verification.discrepancies)


def fuse_verdicts(whisker: dict, tapetum: dict | None) -> FusionResult:
    """Fuse a whisker sidecar dict with an optional tapetum sidecar dict.

    Pure function: no I/O, no side effects. The combined verdict is advisory
    and never replaces the deterministic verdict.
    """
    validated_whisker = _validate_whisker_sidecar(whisker)
    if validated_whisker is None:
        whisker = {"pid": "", "verdict": "?"}
    else:
        whisker = validated_whisker
    tapetum = _validate_tapetum_sidecar(tapetum)

    det = whisker.get("verdict", VERDICT_REVIEW)
    fingerprint = _whisker_fingerprint(whisker)
    ideal_verdict, ideal_discrepancy_count = _ideal_summary(tapetum)

    if not _tapetum_is_usable(tapetum):
        return FusionResult(
            combined_verdict=det,
            combined_rule=FUSION_RULE_WHISKER_ONLY,
            whisker_verdict=det,
            tapetum_verdict=tapetum.get("suggested_verdict", "") if tapetum else "",
            tapetum_available=False,
            tapetum_confidence=0.0,
            whisker_fingerprint=fingerprint,
            ideal_verdict=ideal_verdict,
            ideal_discrepancy_count=ideal_discrepancy_count,
        )

    assert tapetum is not None  # guaranteed by _tapetum_is_usable
    llm = tapetum.get("suggested_verdict", VERDICT_REVIEW)
    conf = tapetum["confidence"]

    # det=fail branch
    if det == VERDICT_FAIL:
        # Rescue: heading-monotone-only fail + LLM says pass or review
        if _is_heading_only_fail(whisker) and llm in (VERDICT_PASS, VERDICT_REVIEW):
            return FusionResult(
                combined_verdict=VERDICT_REVIEW,
                combined_rule=FUSION_RULE_LLM_RESCUE_HEADING,
                whisker_verdict=det,
                tapetum_verdict=llm,
                tapetum_available=True,
                tapetum_confidence=conf,
                whisker_fingerprint=fingerprint,
                ideal_verdict=ideal_verdict,
                ideal_discrepancy_count=ideal_discrepancy_count,
            )
        # All other fails: locked
        return FusionResult(
            combined_verdict=VERDICT_FAIL,
            combined_rule=FUSION_RULE_WHISKER_FAIL_LOCKED,
            whisker_verdict=det,
            tapetum_verdict=llm,
            tapetum_available=True,
            tapetum_confidence=conf,
            whisker_fingerprint=fingerprint,
            ideal_verdict=ideal_verdict,
            ideal_discrepancy_count=ideal_discrepancy_count,
        )

    if det in (VERDICT_PASS, VERDICT_REVIEW) and _source_aware_requires_review(
        tapetum
    ):
        return FusionResult(
            combined_verdict=VERDICT_REVIEW,
            combined_rule=FUSION_RULE_SOURCE_AWARE_REVIEW_CAP,
            whisker_verdict=det,
            tapetum_verdict=llm,
            tapetum_available=True,
            tapetum_confidence=conf,
            whisker_fingerprint=fingerprint,
            ideal_verdict=ideal_verdict,
            ideal_discrepancy_count=ideal_discrepancy_count,
        )

    if ideal_verdict == "review" or tapetum.get("ideal_pending"):
        return FusionResult(
            combined_verdict=VERDICT_REVIEW,
            combined_rule=FUSION_RULE_IDEAL_REVIEW_CAP,
            whisker_verdict=det,
            tapetum_verdict=llm,
            tapetum_available=True,
            tapetum_confidence=conf,
            whisker_fingerprint=fingerprint,
            ideal_verdict=ideal_verdict,
            ideal_discrepancy_count=ideal_discrepancy_count,
        )

    # det=review branch
    if det == VERDICT_REVIEW:
        # Block clear when the deterministic lane detected missing source regions.
        # The LLM cannot verify content absence (it only sees the markdown), so
        # upgrading to pass is structurally unsafe for this signal class.
        if (
            _has_only_soft_flags(whisker)
            and llm == VERDICT_PASS
            and whisker.get("missing_region_count", 0) > 0
        ):
            return FusionResult(
                combined_verdict=VERDICT_REVIEW,
                combined_rule=FUSION_RULE_CLEAR_BLOCKED_MISSING_REGION,
                whisker_verdict=det,
                tapetum_verdict=llm,
                tapetum_available=True,
                tapetum_confidence=conf,
                whisker_fingerprint=fingerprint,
                ideal_verdict=ideal_verdict,
                ideal_discrepancy_count=ideal_discrepancy_count,
            )

        if (
            _has_only_soft_flags(whisker)
            and _has_ideal_soft_flag(whisker)
            and llm == VERDICT_PASS
        ):
            return FusionResult(
                combined_verdict=VERDICT_REVIEW,
                combined_rule=FUSION_RULE_CLEAR_BLOCKED_IDEAL_FLAG,
                whisker_verdict=det,
                tapetum_verdict=llm,
                tapetum_available=True,
                tapetum_confidence=conf,
                whisker_fingerprint=fingerprint,
                ideal_verdict=ideal_verdict,
                ideal_discrepancy_count=ideal_discrepancy_count,
            )

        # Clear: soft-flags only + LLM pass + guardrail.
        # Self-reported confidence is anti-calibrated and removed from the
        # decision path. The clear fires on derived signals: the LLM said
        # pass, axis findings contain no fail, and evidence was not entirely
        # dropped. The ref_nid floor remains as a deterministic guardrail.
        if (
            _has_only_soft_flags(whisker)
            and llm == VERDICT_PASS
            and not _has_any_axis_fail(tapetum)
            and whisker.get("ref_nid") is not None
            and whisker.get("ref_nid", 0.0) >= FUSION_REF_NID_FLOOR
        ):
            return FusionResult(
                combined_verdict=VERDICT_PASS,
                combined_rule=FUSION_RULE_LLM_CLEAR_SOFT_REVIEW,
                whisker_verdict=det,
                tapetum_verdict=llm,
                tapetum_available=True,
                tapetum_confidence=conf,
                whisker_fingerprint=fingerprint,
                ideal_verdict=ideal_verdict,
                ideal_discrepancy_count=ideal_discrepancy_count,
            )
        # Also clear if ref_nid is not available (no reference scoring)
        # but LLM says pass with no axis fails and only soft flags
        if (
            _has_only_soft_flags(whisker)
            and llm == VERDICT_PASS
            and not _has_any_axis_fail(tapetum)
        ):
            ref_nid = whisker.get("ref_nid")
            if ref_nid is None:
                return FusionResult(
                    combined_verdict=VERDICT_PASS,
                    combined_rule=FUSION_RULE_LLM_CLEAR_SOFT_REVIEW,
                    whisker_verdict=det,
                    tapetum_verdict=llm,
                    tapetum_available=True,
                    tapetum_confidence=conf,
                    whisker_fingerprint=fingerprint,
                    ideal_verdict=ideal_verdict,
                    ideal_discrepancy_count=ideal_discrepancy_count,
                )

    # det=pass branch
    if det == VERDICT_PASS:
        # Escalate: LLM found a major axis fail
        if llm == VERDICT_FAIL and _has_major_axis_fail(tapetum):
            return FusionResult(
                combined_verdict=VERDICT_REVIEW,
                combined_rule=FUSION_RULE_LLM_ESCALATE_MAJOR,
                whisker_verdict=det,
                tapetum_verdict=llm,
                tapetum_available=True,
                tapetum_confidence=conf,
                whisker_fingerprint=fingerprint,
                ideal_verdict=ideal_verdict,
                ideal_discrepancy_count=ideal_discrepancy_count,
            )
        # Cap: the primary tapetum verdict itself disagrees with a clean det
        # pass (review, or a fail whose axis findings never reached major).
        # Every more specific cap above (source-aware, ideal, escalate-major)
        # has already had its chance to fire and report a better reason;
        # this is only the residual catch for what they leave behind.
        if llm != VERDICT_PASS:
            return FusionResult(
                combined_verdict=VERDICT_REVIEW,
                combined_rule=FUSION_RULE_LLM_REVIEW_CAP,
                whisker_verdict=det,
                tapetum_verdict=llm,
                tapetum_available=True,
                tapetum_confidence=conf,
                whisker_fingerprint=fingerprint,
                ideal_verdict=ideal_verdict,
                ideal_discrepancy_count=ideal_discrepancy_count,
            )

    # Default: agree (verdicts match) or no applicable rule (keep det)
    rule = FUSION_RULE_AGREE if det == llm else FUSION_RULE_WHISKER_ONLY
    return FusionResult(
        combined_verdict=det,
        combined_rule=rule,
        whisker_verdict=det,
        tapetum_verdict=llm,
        tapetum_available=True,
        tapetum_confidence=conf,
        whisker_fingerprint=fingerprint,
        ideal_verdict=ideal_verdict,
        ideal_discrepancy_count=ideal_discrepancy_count,
    )
