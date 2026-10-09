#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Human-readable side-by-side inspection report for the tapetum_llm lane.

Joins a whisker sidecar (deterministic verdict + signals) with a tapetum
sidecar (advisory LLM adjudication) into one Markdown report an operator can
eyeball, no ground truth required. The point is to SEE conversion quality:
where the LLM agrees with whisker, where it differs, and the grounded evidence
behind each call.

Library returns strings; the CLI persists. Pure and deterministic: output is a
function of the input pairs in the order given (the CLI sorts by PID).
"""

from __future__ import annotations

import html
import math

from whisker.llm.models import parse_ideal_verification

__all__ = ["format_paper_section", "format_report"]

# Whisker numeric/structural signals worth showing next to the LLM's call.
_SIGNAL_KEYS = (
    "unigram_coverage",
    "coverage",
    "lossy_table_count",
    "table_parse_errors",
    "mojibake_count",
)

_CANDIDATE_STATUS_LABELS = {
    "present_in_candidate": "refuted: present in candidate",
    "candidate_not_found": "candidate text not located (not proof of absence)",
    "ambiguous": "abstained: ambiguous",
}


def _fmt_flags(flags: object) -> str:
    if isinstance(flags, list) and flags:
        return ", ".join(str(f) for f in flags)
    return "none"


def _cell(text: object) -> str:
    """Escape untrusted HTML and Markdown table-active characters."""
    escaped = html.escape(str(text), quote=False)
    escaped = escaped.replace("\\", "\\\\")
    for marker in ("`", "*", "_", "[", "]"):
        escaped = escaped.replace(marker, f"\\{marker}")
    return escaped.replace("|", "\\|").replace("\n", " ").strip()


def _safe_float(value: object, default: float = 0.0) -> float:
    """Return a finite float for untrusted sidecar data."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _dict_list(value: object) -> list[dict]:
    """Keep only mapping entries from an untrusted sidecar list."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _truncated(value: object, limit: int) -> str:
    """Return a bounded string for untrusted narrative fields."""
    return str(value if value is not None else "")[:limit]


def _page_unit_id(page: int) -> str:
    return f"page:{page}"


def _page_ids_from_list(ids: object) -> list[str]:
    """Return ``page:N`` ids from an untrusted list, preserving order."""
    if not isinstance(ids, list):
        return []
    return [
        str(uid)
        for uid in ids
        if isinstance(uid, str) and uid.startswith("page:")
    ]


def _findings_count_for_unit(
    unit_id: str,
    defect_groups: list[dict],
    unit_results: list[dict],
) -> int:
    """Count defect groups for *unit_id*, else defects on that unit_result."""
    group_hits = sum(
        1 for group in defect_groups if group.get("source_unit") == unit_id
    )
    if group_hits:
        return group_hits
    total = 0
    for result in unit_results:
        if result.get("unit_id") != unit_id:
            continue
        defects = result.get("defects", [])
        if isinstance(defects, list):
            total += len(defects)
    return total


def _format_llm_readability(block: dict) -> list[str]:
    """Render the versioned table-readability sidecar block."""
    core_id = block.get("contract_id") or block.get("core_id") or "?"
    core_ver = block.get("contract_version") or block.get("core_version") or "?"
    core_hash = block.get("contract_hash") or block.get("core_hash") or ""
    profile_id = block.get("profile_id") or "none"
    profile_ver = block.get("profile_version") or ""
    profile_hash = block.get("profile_hash") or ""
    certified = block.get("model_certified", block.get("certified", False))
    lines = [
        "**Table readability:**",
        f"- contract: `{core_id}` v{core_ver}"
        + (f" sha256:{core_hash}" if core_hash else ""),
        f"- profile: `{profile_id}`"
        + (f" v{profile_ver}" if profile_ver else "")
        + (f" sha256:{profile_hash}" if profile_hash else ""),
        f"- verdict: `{block.get('verdict', '?')}`  "
        f"certified: `{'yes' if certified else 'no'}`",
    ]
    reasons = block.get("blocking_reasons") or []
    if isinstance(reasons, list) and reasons:
        lines.append(f"- blocking: {', '.join(str(r) for r in reasons)}")
    rules = block.get("rules") or []
    if isinstance(rules, list) and rules:
        lines += [
            "",
            "| rule | status | strength | method |",
            "|---|---|---|---|",
        ]
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            lines.append(
                f"| {_cell(rule.get('id', '?'))} "
                f"| {_cell(rule.get('status', '?'))} "
                f"| {_cell(rule.get('strength', ''))} "
                f"| {_cell(rule.get('method', ''))} |"
            )
    dump_lines = _format_unit_dumps(block.get("unit_dumps"))
    if dump_lines:
        lines += dump_lines
    code_block = block.get("code_readability")
    if isinstance(code_block, dict) and code_block:
        lines += [""] + _format_code_readability(code_block)
    probe_lines = _format_code_probes(block.get("code_probes"))
    if probe_lines:
        lines += probe_lines
    lines.append("")
    return lines


def _format_code_readability(block: dict) -> list[str]:
    """Render the versioned codeblock-readability sidecar."""
    core_id = block.get("contract_id") or block.get("core_id") or "?"
    core_ver = block.get("contract_version") or block.get("core_version") or "?"
    core_hash = block.get("contract_hash") or block.get("core_hash") or ""
    certified = block.get("model_certified", block.get("certified", False))
    lines = [
        "**Codeblock readability:**",
        f"- contract: `{core_id}` v{core_ver}"
        + (f" sha256:{core_hash}" if core_hash else ""),
        f"- verdict: `{block.get('verdict', '?')}`  "
        f"certified: `{'yes' if certified else 'no'}`",
    ]
    reasons = block.get("blocking_reasons") or []
    if isinstance(reasons, list) and reasons:
        lines.append(f"- blocking: {', '.join(str(r) for r in reasons)}")
    rules = block.get("rules") or []
    if isinstance(rules, list) and rules:
        lines += [
            "",
            "| rule | status | strength | method |",
            "|---|---|---|---|",
        ]
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            lines.append(
                f"| {_cell(rule.get('id', '?'))} "
                f"| {_cell(rule.get('status', '?'))} "
                f"| {_cell(rule.get('strength', ''))} "
                f"| {_cell(rule.get('method', ''))} |"
            )
    return lines


def _format_code_probes(probes: object) -> list[str]:
    """Render identifier-line probes as evidence, never as certification."""
    if not isinstance(probes, dict) or not probes:
        return []
    units = probes.get("units") or []
    if not isinstance(units, list):
        return []
    model = probes.get("model") or "?"
    lines = [
        "",
        "**Code identifier probes (evidence, not certification):**",
        f"- model: `{model}`  "
        f"pass={probes.get('pass_count', 0)}  "
        f"fail={probes.get('fail_count', 0)}  "
        f"skip={probes.get('skip_count', 0)}",
    ]
    if units:
        lines += [
            "",
            "| fence | ident | line | result |",
            "|---|---|---|---|",
        ]
        for unit in units:
            if not isinstance(unit, dict):
                continue
            if unit.get("skipped"):
                result = "SKIP"
            elif unit.get("error"):
                result = "ERROR"
            elif unit.get("passed"):
                result = "PASS"
            else:
                result = "FAIL"
            lines.append(
                f"| C{_cell(unit.get('unit_index', '?'))} "
                f"| {_cell(unit.get('identifier', '?'))} "
                f"| {_cell(unit.get('line', '?'))} "
                f"| {_cell(result)} |"
            )
    return lines


def _format_unit_dumps(dumps: object) -> list[str]:
    """Render per-unit count-dumps as evidence, never as certification."""
    if not isinstance(dumps, dict) or not dumps:
        return []
    if dumps.get("kind") == "whisker-table-readability":
        return []
    units = dumps.get("units") or []
    if not isinstance(units, list):
        return []
    model = dumps.get("model") or "?"
    n_pass = 0
    n_fail = 0
    n_skip = 0
    n_defect = 0
    n_abstain = 0
    rendered_rows: list[str] = []
    for unit in units:
        if not isinstance(unit, dict):
            continue
        index = unit.get("unit_index", "?")
        classification = unit.get("classification", "?")
        probe = unit.get("probe") if isinstance(unit.get("probe"), dict) else {}
        if probe.get("skipped"):
            result = "SKIP"
            n_skip += 1
        elif probe.get("error"):
            result = "ERROR"
            n_fail += 1
        elif probe.get("defect_confirmed"):
            result = "DEFECT"
            n_defect += 1
        elif probe.get("passed"):
            result = "PASS"
            n_pass += 1
        elif classification != "aligned":
            # A det-flagged unit whose defect hypothesis was neither confirmed
            # by source, typed answer nor grid ("abstain: typed did not
            # confirm, grid=unreliable"). The lane withholds a verdict; it
            # did not fail. Sidecar semantics (passed / defect_confirmed /
            # fail_count) are unchanged; only the label differs (#425).
            result = "ABSTAIN"
            n_abstain += 1
        else:
            result = "FAIL"
            n_fail += 1
        rendered_rows.append(
            f"| T{_cell(index)} "
            f"| {_cell(classification)} "
            f"| {_cell(result)} |"
        )
    summary_parts = [f"pass={n_pass}", f"fail={n_fail}", f"skip={n_skip}"]
    if n_abstain:
        summary_parts.insert(1, f"abstain={n_abstain}")
    if n_defect:
        summary_parts.insert(1, f"defect={n_defect}")
    lines = [
        "",
        "**Table unit dumps (evidence, not certification):**",
        f"- model: `{model}`  " + "  ".join(summary_parts),
    ]
    if rendered_rows:
        lines += [
            "",
            "| unit | class | result |",
            "|---|---|---|",
        ]
        lines += rendered_rows
    return lines


def _format_page_coverage(tapetum: dict) -> list[str]:
    """Render the PDF Page coverage section, or [] when fields are absent.

    Old sidecars without ``page_count`` / ``unit_coverage.mode`` /
    ``all_pages_requested`` produce no section (exact prior rendering).
    """
    page_count = tapetum.get("page_count")
    unit_coverage = tapetum.get("unit_coverage", {})
    if not isinstance(unit_coverage, dict):
        unit_coverage = {}
    mode = unit_coverage.get("mode")
    has_all_pages_flag = "all_pages_requested" in tapetum
    if not (
        isinstance(page_count, int)
        or isinstance(mode, str)
        or has_all_pages_flag
    ):
        return []

    unit_selection = tapetum.get("unit_selection", {})
    if not isinstance(unit_selection, dict):
        unit_selection = {}

    checked_raw = unit_selection.get("checked")
    if not isinstance(checked_raw, list):
        checked_raw = unit_coverage.get("checked_unit_ids", [])
    unchecked_raw = unit_selection.get("unchecked")
    if not isinstance(unchecked_raw, list):
        unchecked_raw = unit_coverage.get("unchecked_unit_ids", [])
    failed_raw = unit_selection.get("failed")
    if not isinstance(failed_raw, list):
        failed_raw = unit_coverage.get("failed_unit_ids", [])
    required_raw = unit_selection.get("required")
    if not isinstance(required_raw, list):
        required_raw = []

    checked_ids = _page_ids_from_list(checked_raw)
    unchecked_ids = _page_ids_from_list(unchecked_raw)
    failed_ids = _page_ids_from_list(failed_raw)
    checked_set = set(checked_ids)
    unchecked_set = set(unchecked_ids)
    failed_set = set(failed_ids)

    mode_label = mode if isinstance(mode, str) and mode else (
        "all_pages" if tapetum.get("all_pages_requested") else "routed"
    )
    k = len(checked_ids)

    page_screen_by_page: dict[int, dict] = {}
    for entry in _dict_list(tapetum.get("page_screen")):
        page_num = entry.get("page")
        if isinstance(page_num, int):
            page_screen_by_page[page_num] = entry

    # N = physical page count when present; live v8 sidecars omitted the
    # top-level key, so fall back to required unit ids, then page_screen.
    if isinstance(page_count, int) and page_count > 0:
        n = page_count
    else:
        required_ids = _page_ids_from_list(required_raw)
        n = len(required_ids) if required_ids else len(page_screen_by_page)
    if n == 0 and k > 0:
        n = k

    defect_groups = _dict_list(tapetum.get("defect_groups"))
    # pdf_judge persists unit_results under the sidecar key unit_checks.
    unit_results = _dict_list(tapetum.get("unit_checks"))
    if not unit_results:
        unit_results = _dict_list(tapetum.get("unit_results"))

    lines: list[str] = [
        "**Page coverage:**",
        f"Pages checked: {k}/{n} (mode: {mode_label})",
        "",
        "| page | tokens | recall | screen flagged | unit check | findings |",
        "|---|---|---|---|---|---|",
    ]

    pages_to_render = n if n > 0 else max(
        (entry.get("page", 0) for entry in page_screen_by_page.values()
         if isinstance(entry.get("page"), int)),
        default=0,
    )
    for page_num in range(1, pages_to_render + 1):
        unit_id = _page_unit_id(page_num)
        screen = page_screen_by_page.get(page_num, {})
        tokens = screen.get("tokens", "-")
        recall = screen.get("recall")
        if isinstance(recall, (int, float)):
            recall_cell = f"{_safe_float(recall):.2f}"
        else:
            recall_cell = "-"
        flagged = screen.get("flagged")
        if flagged is True:
            flagged_cell = "yes"
        elif flagged is False:
            flagged_cell = "no"
        else:
            flagged_cell = "-"
        if unit_id in failed_set:
            unit_check = "failed"
        elif unit_id in unchecked_set:
            unit_check = "unchecked"
        elif unit_id in checked_set:
            unit_check = "checked"
        else:
            unit_check = "none"
        findings = _findings_count_for_unit(
            unit_id, defect_groups, unit_results
        )
        lines.append(
            f"| {_cell(page_num)} "
            f"| {_cell(tokens)} "
            f"| {_cell(recall_cell)} "
            f"| {_cell(flagged_cell)} "
            f"| {_cell(unit_check)} "
            f"| {_cell(findings)} |"
        )
    lines.append("")

    if unchecked_ids or failed_ids:
        warning_parts: list[str] = []
        if unchecked_ids:
            warning_parts.append(
                "unchecked: " + ", ".join(unchecked_ids)
            )
        if failed_ids:
            warning_parts.append(
                "failed: " + ", ".join(failed_ids)
            )
        lines += [
            f"**Warning:** incomplete page coverage "
            f"({'; '.join(warning_parts)})",
            "",
        ]

    all_checked = (
        n > 0
        and k == n
        and not unchecked_ids
        and not failed_ids
    )
    # Zero verified findings: no defect groups attributable to the run.
    all_pages_mode = (
        mode_label == "all_pages" or bool(tapetum.get("all_pages_requested"))
    )
    if all_pages_mode and all_checked and not defect_groups:
        lines += [
            "all pages checked, no additional findings (advisory)",
            "",
        ]

    return lines


def format_paper_section(whisker: dict, tapetum: dict | None) -> str:
    """Render one paper's whisker-vs-advisory comparison as Markdown."""
    whisker = whisker if isinstance(whisker, dict) else {}
    tapetum = tapetum if isinstance(tapetum, dict) else None
    pid = whisker.get("pid") or (tapetum or {}).get("pid", "?")
    w_verdict = whisker.get("verdict", "?")
    lines: list[str] = [f"## {pid}", ""]

    if tapetum is None:
        lines += [f"- **whisker:** `{w_verdict}` (no advisory result)", ""]
        return "\n".join(lines)

    t_verdict = tapetum.get("suggested_verdict", "?")
    agree = "agree" if t_verdict == w_verdict else "DIFFERS"
    conf = _safe_float(tapetum.get("confidence"))
    escalated = bool(tapetum.get("escalated", False))
    if escalated:
        tier_line = f"yes, deep={tapetum.get('tier2_model')}"
    else:
        tier_line = f"no, fast={tapetum.get('tier1_model')}"

    sig = " ".join(f"{k}={whisker.get(k, '?')}" for k in _SIGNAL_KEYS)
    lines += [
        f"- **whisker:** `{w_verdict}`  ->  **tapetum:** `{t_verdict}` "
        f"({agree}, confidence {conf:.2f} — self-reported, uncalibrated)",
        f"- **escalated:** {tier_line}",
        "",
        f"**Whisker signals:** {sig}",
        f"**Whisker flags:** soft=[{_fmt_flags(whisker.get('soft_flags'))}] "
        f"hard=[{_fmt_flags(whisker.get('hard_flags'))}]",
        "",
    ]

    ideal_verification = parse_ideal_verification(
        tapetum.get("ideal_verification")
    )
    if ideal_verification is not None:
        discrepancies = ideal_verification.discrepancies
        count = len(discrepancies)
        noun = "discrepancy" if count == 1 else "discrepancies"
        lines += [
            f"**Ideal verification:** `{ideal_verification.verdict}` "
            f"({count} {noun})",
            "",
            "The tomd ideal is structural ground truth; the source remains the "
            "factual authority when they differ.",
            "",
        ]
        if discrepancies:
            lines += [
                "| axis | severity | candidate quote | ideal quote | explanation |",
                "|---|---|---|---|---|",
            ]
            for discrepancy in discrepancies:
                lines.append(
                    f"| {_cell(discrepancy.axis)} "
                    f"| {_cell(discrepancy.severity)} "
                    f"| {_cell(discrepancy.candidate_quote)} "
                    f"| {_cell(discrepancy.ideal_quote)} "
                    f"| {_cell(discrepancy.explanation)} |"
                )
            lines.append("")
    else:
        lines += ["**Ideal verification:** not available", ""]

    findings = _dict_list(tapetum.get("axis_findings"))
    if findings:
        lines += [
            "**LLM per-axis findings:**",
            "",
            "| axis | verdict | severity | note |",
            "|---|---|---|---|",
        ]
        for af in findings:
            lines.append(
                f"| {_cell(af.get('axis', '?'))} | {_cell(af.get('verdict', '?'))} "
                f"| {_cell(af.get('severity', '?'))} | {_cell(af.get('note', ''))} |"
            )
        lines.append("")

    concern = tapetum.get("primary_concern", "")
    if concern:
        lines += [f"**Primary concern:** {concern}", ""]

    metadata_check = tapetum.get("metadata_outline_check", {})
    if not isinstance(metadata_check, dict):
        metadata_check = {}
    if metadata_check:
        lines += [
            "**Metadata/outline check:** "
            f"`{metadata_check.get('verdict', '?')}`; "
            f"title={metadata_check.get('title_matches', '?')}, "
            f"document={metadata_check.get('document_number_matches', '?')}, "
            f"date={metadata_check.get('date_matches', '?')}",
            f"- heading drift: {_fmt_flags(metadata_check.get('heading_drift'))}",
            f"- missing sections: {_fmt_flags(metadata_check.get('missing_sections'))}",
            "",
        ]

    unit_coverage = tapetum.get("unit_coverage", {})
    if not isinstance(unit_coverage, dict):
        unit_coverage = {}
    if unit_coverage:
        checked = unit_coverage.get("checked_unit_ids", [])
        unchecked = unit_coverage.get("unchecked_unit_ids", [])
        failed = unit_coverage.get("failed_unit_ids", [])
        checked = checked if isinstance(checked, list) else []
        unchecked = unchecked if isinstance(unchecked, list) else []
        failed = failed if isinstance(failed, list) else []
        coverage_complete = unit_coverage.get("coverage_complete", False)
        lines += [
            "**Unit coverage:** "
            f"complete={coverage_complete}, "
            f"checked={len(checked)}, unchecked={len(unchecked)}, "
            f"failed={len(failed)}",
        ]
        if checked:
            lines.append(f"- checked: {', '.join(str(u) for u in checked)}")
        if unchecked:
            lines.append(
                f"- **unchecked (routed but not inspected):** "
                f"{', '.join(str(u) for u in unchecked)}"
            )
        if failed:
            lines.append(
                f"- **failed (LLM call error):** "
                f"{', '.join(str(u) for u in failed)}"
            )
        lines.append("")

    table_block = tapetum.get("llm_readability") or tapetum.get("table_readability") or tapetum.get("table_contract")
    if isinstance(table_block, dict) and table_block:
        lines += _format_llm_readability(table_block)
    elif isinstance(tapetum.get("unit_dumps"), dict):
        dump_lines = _format_unit_dumps(tapetum.get("unit_dumps"))
        if dump_lines:
            lines += dump_lines
            lines.append("")

    page_coverage_lines = _format_page_coverage(tapetum)
    if page_coverage_lines:
        lines += page_coverage_lines

    # Fusion subreason (distinguish coverage-cap from defect-detection).
    # tapetum_verdict is read from the fusion block itself, the record fusion
    # actually decided against, rather than re-deriving it from the top-level
    # suggested_verdict rendered earlier in this section (E32: a human reading
    # only this line must still see the primary tapetum verdict beside merged).
    fusion = tapetum.get("fusion", {})
    if isinstance(fusion, dict) and fusion:
        combined_rule = fusion.get("combined_rule", "")
        combined_verdict = fusion.get("combined_verdict", "")
        fusion_tapetum_verdict = fusion.get("tapetum_verdict", "?")
        if combined_rule:
            rule_label = combined_rule.replace("_", " ")
            lines += [
                f"**Fusion verdict:** `{combined_verdict}` "
                f"(tapetum: `{fusion_tapetum_verdict}`, rule: {rule_label})",
                "",
            ]

    code_boundary = _dict_list(tapetum.get("code_boundary"))
    if code_boundary:
        total_findings = sum(
            len(cb.get("findings", [])) for cb in code_boundary
        )
        non_clean = sum(
            1 for cb in code_boundary
            for f in (cb.get("findings") or [])
            if isinstance(f, dict) and f.get("kind") != "clean"
        )
        lines += [
            f"**Code boundary ({len(code_boundary)} unit(s), "
            f"{total_findings} finding(s), {non_clean} defect(s)):**",
            "",
            "| unit | verdict | kind | rule | candidate quote |",
            "|---|---|---|---|---|",
        ]
        for cb in code_boundary:
            page = cb.get("page", "?")
            cb_verdict = cb.get("verdict", "?")
            for finding in (cb.get("findings") or []):
                if not isinstance(finding, dict):
                    continue
                lines.append(
                    f"| {_cell(page)} "
                    f"| {_cell(cb_verdict)} "
                    f"| {_cell(finding.get('kind', '?'))} "
                    f"| {_cell(finding.get('rule_id', ''))} "
                    f"| {_cell(_truncated(finding.get('candidate_quote'), 80))} |"
                )
        lines.append("")

    defect_groups = _dict_list(tapetum.get("defect_groups"))
    if defect_groups:
        lines += [
            f"**Defect groups ({len(defect_groups)}):**",
            "",
            "| type | unit | llm_count | verified | status | severity | example |",
            "|---|---|---|---|---|---|---|",
        ]
        for group in defect_groups:
            cv = group.get("count_verification", {})
            if not isinstance(cv, dict):
                cv = {}
            count_status = cv.get("count_status", "unverified")
            verified_count = group.get("verified_count")
            if verified_count is None:
                verified_count = "-"
            lines.append(
                f"| {_cell(group.get('defect_type', '?'))} "
                f"| {_cell(group.get('source_unit', '?'))} "
                f"| {_cell(group.get('affected_count', '?'))} "
                f"| {_cell(verified_count)} "
                f"| {_cell(count_status)} "
                f"| {_cell(group.get('severity', '?'))} "
                f"| {_cell(_truncated(group.get('source_quote'), 60))} |"
            )
        lines.append("")

    risk_signals = _dict_list(tapetum.get("risk_signals"))
    if risk_signals:
        lines += [
            f"**Risk signals ({len(risk_signals)}):**",
            "",
        ]
        for sig in risk_signals[:5]:
            lines.append(
                f"- [{sig.get('severity', '?')}] {sig.get('unit_id', '?')}: "
                f"{sig.get('signal_type', '?')} — "
                f"{_truncated(sig.get('detail'), 80)}"
            )
        if len(risk_signals) > 5:
            lines.append(f"- ... and {len(risk_signals) - 5} more")
        lines.append("")

    dispositions = _dict_list(tapetum.get("evidence_dispositions"))
    if dispositions:
        summary = tapetum.get("evidence_summary", {})
        if not isinstance(summary, dict):
            summary = {}
        lines += [
            "**Candidate evidence verification:** "
            f"{summary.get('present_in_candidate', 0)} refuted, "
            f"{summary.get('candidate_not_found', 0)} not located, "
            f"{summary.get('ambiguous', 0)} abstained, "
            f"{summary.get('source_ungrounded', 0)} source-ungrounded",
            "",
            "| source | candidate | page | quote |",
            "|---|---|---|---|",
        ]
        for entry in dispositions:
            candidate_status = entry.get("candidate_status", "?")
            candidate_label = (
                _CANDIDATE_STATUS_LABELS.get(
                    candidate_status,
                    candidate_status,
                )
                if isinstance(candidate_status, str)
                else str(candidate_status)
            )
            lines.append(
                f"| {_cell(entry.get('source_status', '?'))} "
                f"| {_cell(candidate_label)} "
                f"| {_cell(entry.get('page') or '-')} "
                f"| {_cell(entry.get('quote', ''))} |"
            )
        lines.append("")

    grounded = _dict_list(tapetum.get("grounded_evidence"))
    dropped = tapetum.get("ungrounded_dropped", 0)
    lines.append(
        f"**Grounded evidence ({len(grounded)} kept, {dropped} dropped):**"
    )
    if grounded:
        lines.append("")
        for entry in grounded:
            quote = str(entry.get("quote", "")).replace("\n", " ")
            status = entry.get("candidate_status", entry.get("status", "?"))
            start = entry.get("candidate_start", entry.get("start"))
            end = entry.get("candidate_end", entry.get("end"))
            where = f"exact at chars {start}-{end}" if start is not None else status
            lines.append(f"- [{where}] {quote!r}")
    lines.append("")

    reasoning = tapetum.get("reasoning", "")
    if reasoning:
        lines += ["**LLM reasoning (unverified narrative):**", "", str(reasoning), ""]

    return "\n".join(lines)


def format_report(pairs: list[tuple[dict, dict | None]]) -> str:
    """Render a full inspection report over many papers.

    ``pairs`` is ``[(whisker_dict, tapetum_dict_or_None), ...]``. The caller
    orders them (by PID for determinism).
    """
    total = len(pairs)
    adjudicated = sum(1 for _, t in pairs if t is not None)
    differs = sum(
        1
        for w, t in pairs
        if isinstance(t, dict)
        and t.get("suggested_verdict")
        != (w.get("verdict") if isinstance(w, dict) else None)
    )
    merged_counts: dict[str, int] = {}
    merged_differs = 0
    fused = 0
    for w, t in pairs:
        fusion = t.get("fusion") if isinstance(t, dict) else None
        if not isinstance(fusion, dict) or not fusion:
            continue
        fused += 1
        mv = fusion.get("combined_verdict", "?")
        if mv not in ("pass", "review", "not-llm-readable"):
            mv = "?"
        merged_counts[mv] = merged_counts.get(mv, 0) + 1
        if mv != (w.get("verdict") if isinstance(w, dict) else None):
            merged_differs += 1

    header = [
        "# tapetum_llm inspection report",
        "",
        "Advisory only: the whisker verdict on record is never changed. This "
        "report joins each paper's deterministic whisker result with the LLM's "
        "second opinion so conversion quality can be eyeballed without ground "
        "truth.",
        "",
        f"- papers: {total}",
        f"- adjudicated: {adjudicated}",
        f"- advisory differs from whisker: {differs}",
    ]
    if fused:
        header.append(
            f"- merged rollup ({fused} fused): "
            f"{merged_counts.get('pass', 0)} pass, "
            f"{merged_counts.get('review', 0)} review, "
            f"{merged_counts.get('not-llm-readable', 0)} fail "
            f"({merged_differs} differ from det)"
        )
    header += ["", "---", ""]
    body = "\n".join(format_paper_section(w, t) for w, t in pairs)
    return "\n".join(header) + body
