#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Rendering for the table-readability certification report.

Both renderers are pure functions of the report: no clock, no environment, no
unordered iteration, so two runs on the same report produce the same bytes and a
diff between two runs is a real change. Persistence belongs to a caller.

The rendered surface always carries the contract version and hash, and on a
model run the profile id, version and hash, because a verdict without the
identity of the rules that produced it is not auditable.
"""

from __future__ import annotations

from whisker.det.llm_readability.models import (
    RULE_STATUSES,
    STATUS_FAIL,
    STATUS_NOT_APPLICABLE,
    STATUS_NOT_EVALUATED,
    STATUS_PASS,
    STATUS_REVIEW,
    TableReadabilityReport,
)

__all__ = ["render_markdown", "report_to_dict", "status_counts"]

_REPORT_KIND = "whisker-table-readability"
_REPORT_SCHEMA_VERSION = 1


def status_counts(report: TableReadabilityReport) -> dict[str, int]:
    """Return the per-status rule counts, keyed in the vocabulary's own order."""
    counts = {status: 0 for status in RULE_STATUSES}
    for item in report.results:
        counts[item.status] += 1
    return counts


def report_to_dict(report: TableReadabilityReport) -> dict[str, object]:
    """Return a JSON-able, stably ordered view of the report."""
    return {
        "kind": _REPORT_KIND,
        "schema_version": _REPORT_SCHEMA_VERSION,
        "contract_id": report.core_id,
        "contract_version": report.core_version,
        "contract_hash": report.core_hash,
        "profile_id": report.profile_id,
        "profile_version": report.profile_version,
        "profile_hash": report.profile_hash,
        "model_identity": report.model_identity,
        "methods_executed": list(report.methods_executed),
        "table_count": report.table_count,
        "vacuous": report.vacuous,
        "verdict": report.verdict,
        "document_deterministic_ok": report.document_deterministic_ok,
        "model_certified": report.model_certified,
        "certified": report.certified,
        "blocking_reasons": list(report.blocking_reasons),
        "status_counts": status_counts(report),
        "rules": [
            {
                "id": item.rule_id,
                "strength": item.strength,
                "scope": item.scope,
                "method": item.method,
                "check_id": item.check_id,
                "status": item.status,
                "reason": item.reason,
                "findings": [
                    {
                        "locus": finding.locus,
                        "message": finding.message,
                        "evidence": finding.evidence,
                    }
                    for finding in item.findings
                ],
            }
            for item in report.results
        ],
    }


_STATUS_MARKS = {
    STATUS_PASS: "pass",
    STATUS_FAIL: "FAIL",
    STATUS_REVIEW: "review",
    STATUS_NOT_APPLICABLE: "n/a",
    STATUS_NOT_EVALUATED: "unevaluated",
}


def render_markdown(report: TableReadabilityReport) -> str:
    """Render the report as markdown for a human reviewer."""
    out: list[str] = ["# Table-readability certification", ""]
    out.append(f"- verdict: {report.verdict}")
    out.append(f"- tables: {report.table_count}")
    if report.vacuous:
        out.append("- vacuous: no table content, so nothing was certified")
    out.append(f"- deterministic ok: {_yes_no(report.document_deterministic_ok)}")
    out.append(f"- model certified: {_yes_no(report.model_certified)}")
    out.append(f"- contract: {report.core_id} v{report.core_version}")
    out.append(f"- contract hash: sha256:{report.core_hash}")
    if report.profile_id is None:
        out.append("- model profile: none (universal rules only)")
    else:
        out.append(f"- model profile: {report.profile_id} v{report.profile_version}")
        out.append(f"- profile hash: sha256:{report.profile_hash}")
        out.append(f"- model identity: {report.model_identity}")
    out.append(f"- methods executed: {', '.join(report.methods_executed) or 'none'}")
    out.append("")

    if report.blocking_reasons:
        out.append("## Blocking model certification")
        out.append("")
        for reason in report.blocking_reasons:
            out.append(f"- {reason}")
        out.append("")

    out.append("## Rules")
    out.append("")
    out.append("| Rule | Strength | Proven by | Status | Detail |")
    out.append("|---|---|---|---|---|")
    for item in report.results:
        detail = item.reason
        if item.findings:
            detail = f"{len(item.findings)} finding(s)"
        out.append(
            f"| {item.rule_id} | {item.strength} | {item.method} "
            f"| {_STATUS_MARKS[item.status]} | {detail} |"
        )
    out.append("")

    findings_present = any(item.findings for item in report.results)
    if findings_present:
        out.append("## Findings")
        out.append("")
        for item in report.results:
            for finding in item.findings:
                evidence = f" `{finding.evidence}`" if finding.evidence else ""
                out.append(
                    f"- **{item.rule_id}** {finding.locus}: {finding.message}{evidence}"
                )
        out.append("")
    return "\n".join(out)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
