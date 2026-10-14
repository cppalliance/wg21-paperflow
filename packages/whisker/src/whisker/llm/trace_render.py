#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Pure renderers for tapetum_llm ``--trace`` transcripts.

No LLM, no I/O. The HTML/text lane feeds :func:`render_text_trace` through
``pipeline.runner.dispatch``; the PDF lane feeds :func:`render_pdf_trace`
from the CLI ``finally`` after ``judge_pdf_extraction``.
"""

from __future__ import annotations

from typing import Any

_QUOTE_LEN = 60
_SECONDS_PER_MINUTE = 60
_TEXT_STEP_NAMES = ("Select", "Triage", "Adjudicate", "Decide")
_TEXT_PHASES_BY_STEP: tuple[tuple[str, ...], ...] = (
    (),
    ("metadata", "triage"),
    ("adjudicate",),
    ("metadata", "unit_checks", "table_compare", "readability"),
)
# Progress-dict keys shared with ``pdf_judge._set_progress`` (single owner here).
PHASE_STARTED_KEY = "_phase_started"
DONE_PHASE = "done"
_PDF_STEPS: tuple[tuple[tuple[str, ...], int, str], ...] = (
    (("extract",), 1, "Extract"),
    (("page_screen",), 2, "Screen"),
    (("monolith",), 3, "Monolith"),
    (("metadata", "metadata_short_circuit"), 4, "Metadata"),
    (("escalations",), 5, "Escalations"),
    (("unit_checks",), 6, "Unit checks"),
    (("code_boundary",), 7, "Code boundary"),
    (("readability",), 8, "Readability probes"),
)


def _format_duration(seconds: float) -> str:
    """Match assay ``render_trace``: seconds under 60, minutes otherwise."""
    if seconds < _SECONDS_PER_MINUTE:
        return f"{seconds:.1f}s"
    return f"{seconds / _SECONDS_PER_MINUTE:.1f}m"


def _quote(text: str) -> str:
    text = text.replace("\n", " ").strip()
    if len(text) > _QUOTE_LEN:
        return f'"{text[:_QUOTE_LEN]}..."'
    return f'"{text}"'


def _duration_suffix(seconds: float | None) -> str:
    if seconds is None:
        return ""
    return f" ({_format_duration(seconds)})"


def _step_duration(step_metrics: list, index: int) -> float | None:
    if index < len(step_metrics):
        return float(step_metrics[index].duration_s)
    return None


def _append_phases(
    lines: list[str],
    durations: dict[str, float],
    names: tuple[str, ...],
) -> None:
    present = [(name, durations[name]) for name in names if name in durations]
    if not present:
        return
    lines.append("### Phases")
    lines.append("")
    for name, seconds in present:
        lines.append(f"- {name}: {_format_duration(seconds)}")
    lines.append("")


def _adjudication_summary(label: str, adj: Any) -> list[str]:
    if adj is None:
        return [f"- {label}: none", ""]
    lines = [
        f"- {label}: {getattr(adj, 'verdict', 'none')} "
        f"(confidence={getattr(adj, 'confidence', 0.0):.2f}, "
        f"worst_axis={getattr(adj, 'worst_axis', '')})",
        "",
    ]
    findings = list(getattr(adj, "axis_findings", []) or [])
    lines.append(f"### Axis findings ({len(findings)})")
    lines.append("")
    for finding in findings:
        axis = getattr(finding, "axis", "")
        verdict = getattr(finding, "verdict", "")
        severity = getattr(finding, "severity", "")
        note = getattr(finding, "note", "")
        qualifier = f"{verdict}"
        if severity:
            qualifier += f", {severity}"
        extra = f" {_quote(note)}" if note else ""
        lines.append(f"- {axis} [{qualifier}]{extra}")
    lines.append("")
    spans = list(getattr(adj, "evidence_spans", []) or [])
    lines.append(f"### Evidence ({len(spans)})")
    lines.append("")
    for span in spans:
        quote = getattr(span, "quote", "")
        axis = getattr(span, "axis", "")
        lines.append(f"- {_quote(quote)} [{axis}]")
    lines.append("")
    return lines


def _metadata_summary(check: Any) -> list[str]:
    if check is None:
        return ["- metadata_outline_check: none", ""]
    verdict = getattr(check, "verdict", None)
    if verdict is None and isinstance(check, dict):
        verdict = check.get("verdict", "")
        title = check.get("title_matches")
        document = check.get("document_number_matches")
        date = check.get("date_matches")
        drift = check.get("heading_drift") or []
        missing = check.get("missing_sections") or []
    else:
        title = getattr(check, "title_matches", None)
        document = getattr(check, "document_number_matches", None)
        date = getattr(check, "date_matches", None)
        drift = list(getattr(check, "heading_drift", []) or [])
        missing = list(getattr(check, "missing_sections", []) or [])
    lines = [
        f"- metadata_outline_check: {verdict}",
        f"- title_matches: {title}",
        f"- document_number_matches: {document}",
        f"- date_matches: {date}",
        "",
        f"### Heading drift ({len(drift)})",
        "",
    ]
    for item in drift:
        lines.append(f"- {_quote(str(item))}")
    lines.append("")
    lines.append(f"### Missing sections ({len(missing)})")
    lines.append("")
    for item in missing:
        lines.append(f"- {_quote(str(item))}")
    lines.append("")
    return lines


def _id_list_section(title: str, ids: list[str]) -> list[str]:
    lines = [f"### {title} ({len(ids)})", ""]
    for item in ids:
        lines.append(f"- {item}")
    lines.append("")
    return lines


def render_text_trace(state, step: int, *, step_metrics: list) -> str:
    """Render the HTML/text-lane trace through the last completed step."""
    last = max(0, min(int(step), len(_TEXT_STEP_NAMES) - 1))
    durations = dict(getattr(state, "phase_durations", {}) or {})
    lines: list[str] = []

    for index in range(last + 1):
        name = _TEXT_STEP_NAMES[index]
        lines.append(
            f"## Step {index} ({name})"
            f"{_duration_suffix(_step_duration(step_metrics, index))}"
        )
        lines.append("")

        if index == 0:
            paper_md = getattr(state, "paper_md", "") or ""
            lines.append(f"- paper_md: {len(paper_md)} chars")
            signals = getattr(state, "whisker_signals", {}) or {}
            keys = sorted(signals)
            lines.append(f"- whisker_signals: {len(keys)} keys")
            if "verdict" in signals:
                lines.append(f"- whisker_verdict: {signals.get('verdict')}")
            lines.append("")
            if keys:
                lines.append(f"### Whisker signal keys ({len(keys)})")
                lines.append("")
                for key in keys:
                    lines.append(f"- {key}")
                lines.append("")

        elif index == 1:
            lines.extend(_adjudication_summary("tier1", getattr(state, "tier1", None)))
            lines.append(f"- chunked: {bool(getattr(state, 'chunked', False))}")
            lines.append(f"- partial: {bool(getattr(state, 'partial', False))}")
            lines.append("")
            lines.extend(
                _metadata_summary(getattr(state, "metadata_outline_check", None))
            )

        elif index == 2:
            lines.extend(_adjudication_summary("tier2", getattr(state, "tier2", None)))
            signals = list(getattr(state, "escalation_signals", []) or [])
            lines.append(f"### Escalation signals ({len(signals)})")
            lines.append("")
            for signal in signals:
                lines.append(f"- {signal}")
            lines.append("")

        else:
            unit_result = getattr(state, "unit_result", None)
            if unit_result is None:
                lines.append("- unit_result: none")
                lines.append("")
            else:
                lines.append(f"- unit_result: {unit_result.verdict}")
                lines.append(
                    f"- coverage_complete: {unit_result.coverage_complete}"
                )
                lines.append("")
                lines.extend(
                    _id_list_section(
                        "Unit results checked",
                        list(unit_result.checked_unit_ids),
                    )
                )
                lines.extend(
                    _id_list_section(
                        "Unit results failed",
                        list(unit_result.failed_unit_ids),
                    )
                )
                unchecked = list(unit_result.unchecked_unit_ids)
                lines.extend(_id_list_section("Unit results unchecked", unchecked))
                unit_rows = list(unit_result.unit_results)
                lines.append(f"### Unit results ({len(unit_rows)})")
                lines.append("")
                for row in unit_rows:
                    unit_id = row.get("unit_id", "")
                    verdict = row.get("verdict", "")
                    lines.append(f"- {unit_id} [{verdict}]")
                lines.append("")
                evidence = [
                    disposition
                    for row in unit_rows
                    for disposition in row.get("evidence_dispositions", [])
                ]
                lines.append(f"### Evidence ({len(evidence)})")
                lines.append("")
                for disposition in evidence:
                    quote = disposition.get("quote", "")
                    status = disposition.get("candidate_status", "")
                    lines.append(f"- {_quote(str(quote))} [{status}]")
                lines.append("")

            risks = list(getattr(state, "risk_signals", []) or [])
            lines.append(f"### Risk signals ({len(risks)})")
            lines.append("")
            for risk in risks:
                unit_id = getattr(risk, "unit_id", "")
                signal_type = getattr(risk, "signal_type", "")
                severity = getattr(risk, "severity", "")
                detail = getattr(risk, "detail", "")
                extra = f" {_quote(detail)}" if detail else ""
                lines.append(f"- {unit_id} [{signal_type}, {severity}]{extra}")
            lines.append("")

            table = getattr(state, "table_compare_result", {}) or {}
            if not table:
                lines.append("- table_compare_result: none")
                lines.append("")
            else:
                lines.append(
                    "- table_compare_result: "
                    f"source={table.get('total_source_tables', 0)}, "
                    f"candidate={table.get('total_candidate_tables', 0)}, "
                    f"matched={table.get('matched_tables', 0)}, "
                    f"cell_diffs={table.get('cell_diff_count', 0)}, "
                    f"grid_unreliable={table.get('grid_unreliable', False)}"
                )
                lines.append("")
                diffs = list(table.get("cell_diffs") or [])
                lines.append(f"### Table cell diffs ({len(diffs)})")
                lines.append("")
                for diff in diffs:
                    lines.append(
                        f"- page {diff.get('page')} "
                        f"({diff.get('row')},{diff.get('col')}) "
                        f"[{diff.get('diff_type')}]"
                    )
                lines.append("")

            selection = list(getattr(state, "unit_selection", []) or [])
            lines.append(f"### Unit selection ({len(selection)})")
            lines.append("")
            for entry in selection:
                if isinstance(entry, dict):
                    unit_id = entry.get("unit_id", "")
                    status = entry.get("status", entry.get("verdict", ""))
                    lines.append(f"- {unit_id} [{status}]" if status else f"- {unit_id}")
                else:
                    lines.append(f"- {entry}")
            lines.append("")
            lines.extend(
                _metadata_summary(getattr(state, "metadata_outline_check", None))
            )
            result = getattr(state, "_result", None)
            if result is None:
                lines.append("- result: none")
                lines.append("")
            else:
                lines.append(
                    f"- result: {result.suggested_verdict} "
                    f"(confidence={result.confidence:.2f}, "
                    f"status={result.status}, escalated={result.escalated})"
                )
                lines.append(f"- ungrounded_dropped: {result.ungrounded_dropped}")
                lines.append("")
                grounded = list(result.grounded_evidence)
                lines.append(f"### Evidence ({len(grounded)})")
                lines.append("")
                for item in grounded:
                    quote = item.get("quote", "")
                    status = item.get("status", "")
                    lines.append(f"- {_quote(str(quote))} [{status}]")
                lines.append("")

        _append_phases(lines, durations, _TEXT_PHASES_BY_STEP[index])

    return "\n".join(lines).rstrip() + "\n"


def _reached_phases(progress: dict) -> set[str]:
    durations = progress.get("phase_durations") or {}
    reached = {name for name in durations if name != DONE_PHASE}
    current = progress.get("phase")
    if current and current not in {DONE_PHASE, PHASE_STARTED_KEY}:
        reached.add(current)
    return reached


def _phase_duration(progress: dict, names: tuple[str, ...]) -> float | None:
    durations = progress.get("phase_durations") or {}
    total = sum(float(durations[name]) for name in names if name in durations)
    if total:
        return total
    return None


def _flagged_page_count(result: Any) -> int:
    screen = getattr(result, "page_screen", []) or []
    return sum(1 for entry in screen if getattr(entry, "flagged", False))


def _coverage_ids(result: Any, key: str) -> list[str]:
    coverage = getattr(result, "unit_coverage", {}) or {}
    selection = getattr(result, "unit_selection", {}) or {}
    raw = coverage.get(key)
    if raw is None and isinstance(selection, dict):
        alias = {
            "checked_unit_ids": "checked",
            "unchecked_unit_ids": "unchecked",
            "failed_unit_ids": "failed",
            "required_unit_ids": "required",
        }.get(key, key)
        raw = selection.get(alias)
    return [str(item) for item in (raw or [])]


def render_pdf_trace(
    pid: str,
    progress: dict,
    result,
    error: BaseException | None,
) -> str:
    """Render the PDF-lane trace from progress plus the folded result or error."""
    del pid
    progress = dict(progress or {})
    progress.pop(PHASE_STARTED_KEY, None)
    reached = _reached_phases(progress)
    lines: list[str] = []

    for names, number, title in _PDF_STEPS:
        if not reached.intersection(names):
            continue
        lines.append(
            f"## Step {number} ({title})"
            f"{_duration_suffix(_phase_duration(progress, names))}"
        )
        lines.append("")

        if number == 1:
            page_count = progress.get("page_count")
            if result is not None:
                page_count = result.page_count
            if page_count is not None:
                lines.append(f"- page_count: {page_count}")
            if result is not None:
                lines.append(f"- text_nid: {result.text_nid:.4f}")
                lines.append(f"- content_recall: {result.content_recall:.4f}")
            lines.append("")

        elif number == 2:
            if result is not None:
                flagged = _flagged_page_count(result)
                lines.append(f"- page_screen flagged: {flagged}")
                lines.append(f"- page_screen pages: {len(result.page_screen)}")
            lines.append("")

        elif number == 3:
            if result is not None:
                grounded = [
                    item
                    for item in (result.evidence_verification or [])
                    if item.get("candidate_status") != "source_ungrounded"
                ]
                lines.append(f"- verdict: {result.verdict}")
                lines.append(f"- confidence: {result.confidence:.2f}")
                lines.append(f"- missing_content: {len(result.missing_content)}")
                lines.append(f"- grounded: {len(grounded)}")
                lines.append(f"- dropped: {result.ungrounded_dropped}")
            lines.append("")

        elif number == 4:
            short = "metadata_short_circuit" in reached
            if result is not None:
                meta = result.metadata_outline_check or {}
                lines.append(f"- metadata verdict: {meta.get('verdict', '')}")
            lines.append(f"- short-circuit: {'yes' if short else 'no'}")
            lines.append("")

        elif number == 5:
            if result is not None:
                lines.append(
                    f"- page_escalations: {len(result.page_escalations)}"
                )
            lines.append("")

        elif number == 6:
            required = list(progress.get("required_unit_ids") or [])
            checked = list(progress.get("checked_unit_ids") or [])
            if result is not None:
                if not required:
                    required = _coverage_ids(result, "required_unit_ids")
                if not checked:
                    checked = _coverage_ids(result, "checked_unit_ids")
                unchecked = _coverage_ids(result, "unchecked_unit_ids")
                failed = _coverage_ids(result, "failed_unit_ids")
            else:
                unchecked = []
                failed = []
            lines.append(f"- required: {len(required)}")
            lines.append(f"- checked: {len(checked)}")
            lines.append(f"- unchecked: {len(unchecked)}")
            lines.append(f"- failed: {len(failed)}")
            lines.append("")
            lines.extend(_id_list_section("Required unit ids", required))
            lines.extend(_id_list_section("Checked unit ids", checked))
            lines.extend(_id_list_section("Unchecked unit ids", unchecked))
            lines.extend(_id_list_section("Failed unit ids", failed))

        elif number == 7:
            if result is not None:
                lines.append(f"- code_boundary: {len(result.code_boundary)}")
            lines.append("")

        else:
            if result is not None:
                readability = result.llm_readability or {}
                dumps = readability.get("unit_dumps") or {}
                probes = readability.get("code_probes") or {}
                lines.append(f"- unit_dumps: {len(dumps.get('units') or [])}")
                lines.append(f"- code_probes: {len(probes.get('units') or [])}")
            lines.append("")

        _append_phases(
            lines,
            progress.get("phase_durations") or {},
            names,
        )

    if result is not None:
        duration = _phase_duration(
            progress,
            tuple(
                name
                for names, _number, _title in _PDF_STEPS
                for name in names
            ),
        )
        lines.append("## Result")
        lines.append("")
        lines.append(f"- verdict: {result.verdict}")
        lines.append(f"- confidence: {result.confidence:.2f}")
        lines.append("- status: ok")
        if duration is not None:
            lines.append(f"- duration: {_format_duration(duration)}")
        lines.append(f"- page_count: {result.page_count}")
        lines.append(f"- text_nid: {result.text_nid:.4f}")
        lines.append(f"- content_recall: {result.content_recall:.4f}")
        lines.append(f"- missing_content: {len(result.missing_content)}")
        lines.append(f"- ungrounded_dropped: {result.ungrounded_dropped}")
        lines.append(f"- page_screen flagged: {_flagged_page_count(result)}")
        lines.append(f"- page_escalations: {len(result.page_escalations)}")
        lines.append(f"- risk_signals: {len(result.risk_signals)}")
        lines.append(f"- defect_groups: {len(result.defect_groups)}")
        lines.append(f"- unit_checks: {len(result.unit_checks)}")
        meta = result.metadata_outline_check or {}
        lines.append(f"- metadata verdict: {meta.get('verdict', '')}")
        coverage = result.unit_coverage or {}
        lines.append(
            f"- coverage_complete: {coverage.get('coverage_complete', '')}"
        )
        lines.append(f"- all_pages_requested: {result.all_pages_requested}")
        lines.append(f"- toc_leak_hits: {len(result.toc_leak_hits)}")
        lines.append(f"- code_boundary: {len(result.code_boundary)}")
        lines.append(f"- ideal_pending: {result.ideal_pending}")
        if result.ideal_verification is not None:
            lines.append(
                f"- ideal_verification: {result.ideal_verification.verdict}"
            )
        lines.append("")
        lines.extend(
            _id_list_section(
                "Checked unit ids",
                _coverage_ids(result, "checked_unit_ids"),
            )
        )
        lines.extend(
            _id_list_section(
                "Unchecked unit ids",
                _coverage_ids(result, "unchecked_unit_ids"),
            )
        )
        lines.extend(
            _id_list_section(
                "Failed unit ids",
                _coverage_ids(result, "failed_unit_ids"),
            )
        )
    else:
        lines.append("## Error")
        lines.append("")
        if error is None:
            lines.append("- type: unknown")
            lines.append("- message: lane failed with no result")
        else:
            lines.append(f"- type: {type(error).__name__}")
            lines.append(f"- message: {error}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
