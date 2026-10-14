#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Three-lane merged report: deterministic + LLM + fusion.

Renders ``report-merged.md`` and ``report-merged.json`` from existing sidecars,
plus a one-line terminal summary per paper and a footer with merged counts and
lane coverage. Also appends a merged-rollup line to the tapetum-inspect header.

Library returns strings/dicts; the CLI persists. Pure and deterministic.
"""

from __future__ import annotations

import html
import json
import math
from pathlib import Path

from whisker.det.score import VERDICT_FAIL, VERDICT_PASS, VERDICT_REVIEW
from whisker.llm.constants import MAX_IDEAL_DISCREPANCIES
from whisker.llm.models import parse_ideal_verification

__all__ = [
    "build_merged_json",
    "render_merged_report_md",
    "render_terminal_fusion_line",
    "render_terminal_fusion_footer",
]

_VERDICT_TIER = {VERDICT_FAIL: 0, VERDICT_REVIEW: 1, VERDICT_PASS: 2}


def _safe_float(value: object, default: float | None = None) -> float | None:
    """Return a finite float for untrusted report data."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _bounded_ideal_count(value: object) -> int:
    """Clamp an untrusted compact count to the shared schema bound."""
    if not isinstance(value, int) or isinstance(value, bool):
        return 0
    return min(max(value, 0), MAX_IDEAL_DISCREPANCIES)


def _verdict(value: object, default: str = "?") -> str:
    """Return a recognized verdict from untrusted report data."""
    return value if isinstance(value, str) and value in _VERDICT_TIER else default


def _sort_key(row: dict) -> tuple[int, float, str]:
    """Worst-merged-first: merged tier asc, then unigram asc, then PID."""
    merged = _verdict(row.get("merged"), VERDICT_REVIEW)
    uni = _safe_float(row.get("unigram"), 0.0) or 0.0
    pid = str(row.get("pid", ""))
    return (_VERDICT_TIER.get(merged, 1), uni, pid)


def _is_replayed(tap: dict | None, run_started_at: str | None) -> bool | None:
    """True when *tap* is a warm-skip carryover from a previous run.

    ``None`` when there is no tapetum data at all (not applicable). When
    ``run_started_at`` is ``None`` (no evaluation happened in this
    invocation, e.g. ``--fuse-only``), every present tapetum result is
    definitionally a replay. Otherwise a result is a replay when its
    ``evaluated_at`` (set only on an actual evaluation, B2) is missing or
    predates the current run: ISO 8601 UTC timestamps compare correctly as
    plain strings when produced with a consistent format (``_utc_now_iso``).
    """
    if tap is None:
        return None
    if run_started_at is None:
        return True
    evaluated_at = tap.get("evaluated_at")
    if not isinstance(evaluated_at, str) or not evaluated_at:
        return True
    return evaluated_at < run_started_at


def build_merged_json(
    whisker_sidecars: list[dict],
    tapetum_sidecars: dict[str, dict],
    *,
    run_started_at: str | None = None,
) -> list[dict]:
    """Build the merged report data from whisker + tapetum sidecar pairs.

    ``tapetum_sidecars`` is keyed by PID (uppercase). Returns a sorted list
    of row dicts ready for JSON serialization or markdown rendering.
    ``run_started_at`` is the current run's start timestamp, used to derive
    the ``replayed`` warm-skip marker per row (see ``_is_replayed``).
    """
    rows: list[dict] = []
    for raw_wsc in whisker_sidecars:
        wsc = raw_wsc if isinstance(raw_wsc, dict) else {}
        pid = str(wsc.get("pid", ""))
        raw_tap = tapetum_sidecars.get(pid.upper())
        tap = raw_tap if isinstance(raw_tap, dict) else None
        raw_fusion = (tap or {}).get("fusion")
        fusion = raw_fusion if isinstance(raw_fusion, dict) else None
        ideal_verification = parse_ideal_verification(
            (tap or {}).get("ideal_verification")
        )
        confidence = _safe_float((tap or {}).get("confidence"))
        unigram = _safe_float(wsc.get("unigram_coverage"), 0.0) or 0.0
        overall = _safe_float(wsc.get("ref_overall"))
        ideal_overall = _safe_float(wsc.get("ideal_overall"))
        det = _verdict(wsc.get("verdict"))
        llm = _verdict((tap or {}).get("suggested_verdict"), "-")
        merged = _verdict(
            fusion.get("combined_verdict") if fusion else None,
            det,
        )

        row: dict = {
            "pid": pid,
            "det": det,
            "llm": llm,
            "merged": merged,
            "delta": _delta_symbol(det, merged if fusion else None),
            "conf": round(confidence, 2) if confidence is not None else None,
            "unigram": round(unigram, 4),
            "overall": round(overall, 4) if overall is not None else None,
            "ideal": (
                round(ideal_overall, 4) if ideal_overall is not None else None
            ),
            "ideal_verdict": (
                ideal_verification.verdict if ideal_verification else None
            ),
            "ideal_discrepancy_count": (
                len(ideal_verification.discrepancies)
                if ideal_verification
                else 0
            ),
            "flags": _compact_flags(wsc),
            "rule": (
                fusion.get("combined_rule", "")
                if fusion and isinstance(fusion.get("combined_rule", ""), str)
                else ""
            ),
            "class": _classify_cosmetic(tap) if tap else "",
            "replayed": _is_replayed(tap, run_started_at),
        }
        rows.append(row)

    rows.sort(key=_sort_key)
    return rows


def _delta_symbol(det: str | None, merged: str | None) -> str:
    """Arrow showing the direction of the fusion delta."""
    if det is None or merged is None or det == merged:
        return "="
    dt = _VERDICT_TIER.get(det, 1)
    mt = _VERDICT_TIER.get(merged, 1)
    if mt > dt:
        return "\u2191"  # up arrow: upgrade
    return "\u2193"  # down arrow: downgrade


def _classify_cosmetic(tap: dict) -> str:
    """Return ``"cosmetic"`` when the LLM's only non-pass axis is structure/minor."""
    if tap.get("suggested_verdict") != VERDICT_REVIEW:
        return ""
    findings = tap.get("axis_findings", [])
    if not isinstance(findings, list) or not findings:
        return ""
    nonpass = [
        finding
        for finding in findings
        if isinstance(finding, dict) and finding.get("verdict") != VERDICT_PASS
    ]
    if not nonpass:
        return ""
    if all(
        f.get("axis") == "structure" and f.get("severity") == "minor"
        for f in nonpass
    ):
        return "cosmetic"
    return ""


def _compact_flags(wsc: dict) -> str:
    hard = wsc.get("hard_flags", [])
    soft = wsc.get("soft_flags", [])
    if not isinstance(hard, list):
        hard = []
    if not isinstance(soft, list):
        soft = []
    parts = [f"H:{f}" for f in hard] + [f"S:{f}" for f in soft]
    return ", ".join(parts) if parts else ""


def render_merged_report_md(rows: list[dict]) -> str:
    """Render ``report-merged.md`` from the merged row data."""
    lines: list[str] = [
        "# Merged Report (Deterministic + LLM Fusion)",
        "",
        "Advisory only: the whisker verdict on record is never changed by fusion.",
        "",
    ]

    # Summary counts
    counts: dict[str, int] = {}
    for r in rows:
        v = r.get("merged", "?")
        if not isinstance(v, str):
            v = "?"
        counts[v] = counts.get(v, 0) + 1
    coverage = sum(1 for r in rows if r.get("llm") != "-")
    replayed_count = sum(1 for r in rows if r.get("replayed") is True)
    lines += [
        f"- papers: {len(rows)}",
        f"- LLM coverage: {coverage}/{len(rows)}",
        f"- merged: {counts.get('pass', 0)} pass, {counts.get('review', 0)} review, {counts.get('not-llm-readable', 0)} fail",
        f"- warm replay (fingerprint-skip carryover): {replayed_count}/{coverage}",
        "",
    ]

    cosmetic_count = sum(1 for r in rows if r.get("class") == "cosmetic")
    if cosmetic_count:
        lines.append(
            f"- cosmetic (structure-only minor): {cosmetic_count} "
            f"(fast-track review candidates)"
        )
        lines.append("")

    # Table
    lines += [
        "| PID | det | llm | merged | delta | conf | unigram | overall | ideal | ideal verify | ideal discrepancies | class | replay | flags |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        conf = _safe_float(r.get("conf"))
        overall = _safe_float(r.get("overall"))
        ideal = _safe_float(r.get("ideal"))
        unigram = _safe_float(r.get("unigram"), 0.0) or 0.0
        conf_str = f"{conf:.2f}" if conf is not None else "-"
        overall_str = f"{overall:.4f}" if overall is not None else "-"
        ideal_str = f"{ideal:.4f}" if ideal is not None else "-"
        ideal_verdict = r.get("ideal_verdict") or "-"
        ideal_discrepancies = _bounded_ideal_count(
            r.get("ideal_discrepancy_count")
        )
        cls = r.get("class", "")
        replay_cell = "warm" if r.get("replayed") is True else "-"
        lines.append(
            f"| {_cell(r.get('pid', ''))} | {_cell(r.get('det', '?'))} "
            f"| {_cell(r.get('llm', '-'))} | {_cell(r.get('merged', '?'))} "
            f"| {_cell(r.get('delta', '='))} | {conf_str} | {unigram:.4f} "
            f"| {overall_str} | {ideal_str} | {_cell(ideal_verdict)} "
            f"| {ideal_discrepancies} | {_cell(cls)} | {_cell(replay_cell)} "
            f"| {_cell(r.get('flags', ''))} |"
        )
    lines.append("")
    return "\n".join(lines)


def _cell(text: object) -> str:
    escaped = html.escape(str(text), quote=False)
    escaped = escaped.replace("\\", "\\\\")
    for marker in ("`", "*", "_", "[", "]"):
        escaped = escaped.replace(marker, f"\\{marker}")
    return escaped.replace("|", "\\|").replace("\n", " ").strip()


def render_terminal_fusion_line(
    pid: str,
    det: str,
    llm: str,
    merged: str,
    conf: float,
    rule: str,
) -> str:
    """One-line terminal summary for a single paper's fusion result."""
    return f"  det:{det.upper()} llm:{llm.upper()}({conf:.2f}) -> merged:{merged.upper()} [{rule}]"


def render_terminal_fusion_footer(rows: list[dict]) -> str:
    """Footer with merged counts and lane coverage for the terminal."""
    counts: dict[str, int] = {}
    for r in rows:
        v = r.get("merged", "?")
        counts[v] = counts.get(v, 0) + 1
    coverage = sum(1 for r in rows if r.get("llm") != "-")
    rule_counts: dict[str, int] = {}
    for r in rows:
        rule = r.get("rule", "")
        if rule:
            rule_counts[rule] = rule_counts.get(rule, 0) + 1

    cosmetic = sum(1 for r in rows if r.get("class") == "cosmetic")

    parts = [
        f"=== merged: {counts.get('pass', 0)} pass, "
        f"{counts.get('review', 0)} review, "
        f"{counts.get('not-llm-readable', 0)} fail "
        f"(LLM coverage {coverage}/{len(rows)})",
    ]
    if rule_counts:
        rule_str = ", ".join(f"{k}={v}" for k, v in sorted(rule_counts.items()))
        parts.append(f"    rules: {rule_str}")
    if cosmetic:
        parts.append(f"    cosmetic (fast-track): {cosmetic}")
    return " ===\n".join(parts) + " ==="


def persist_merged_report(
    rows: list[dict],
    out_dir: Path,
) -> tuple[Path, Path]:
    """Write ``report-merged.md`` and ``report-merged.json`` to *out_dir*."""
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / "report-merged.md"
    md_path.write_text(render_merged_report_md(rows), encoding="utf-8")

    json_path = out_dir / "report-merged.json"
    json_path.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return md_path, json_path
