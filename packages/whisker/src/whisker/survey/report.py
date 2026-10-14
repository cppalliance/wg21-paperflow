#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Report generation for whisker survey monthly runs.

Renders per-run report sets: survey-<name>.json (machine-readable) and
survey-<name>.md (human-readable). The Aussagegrenzen and case-study language
from the implementation plan is baked into the template.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

# Display names used in the limitations paragraph. The registry uses lowercase
# keys; the prose needs the competitor the reader actually compared.
_COMPETITOR_PROSE_NAMES: dict[str, str] = {
    "marker": "Marker",
    "tesseract": "Tesseract",
}

_TESSERACT_OCR_NOTE = (
    " Tesseract markdown is OCR running text produced by rasterizing each PDF "
    "page; it is not a structured WG21 converter."
)


def aussagegrenzen_text(competitor_name: str) -> str:
    """Return the limitations paragraph for *competitor_name*."""
    label = _COMPETITOR_PROSE_NAMES.get(competitor_name, competitor_name)
    extra = _TESSERACT_OCR_NOTE if competitor_name == "tesseract" else ""
    return (
        "This report is an explorative case study over five short WG21 PDFs. "
        "It may state what was better or worse on these papers and these structures. "
        "It may NOT claim general superiority of tomd or "
        f"{label}, a population-wide "
        "error rate, or general Whisker reliability. CPU-only runtimes are properties "
        f"of this test environment, not general {label} performance."
        f"{extra}"
    )


# Backward-compatible default (Marker was the only competitor when this string
# was first committed). Prefer ``aussagegrenzen_text`` for new reports.
AUSSAGEGRENZEN_TEXT = aussagegrenzen_text("marker")

CASE_STUDY_PREAMBLE = (
    "The following results are an explorative Fallstudie (case study) comparing "
    "PDF-to-Markdown conversion quality on a frozen, adjudicated corpus of five "
    "short WG21 committee papers. All measurements are deterministic and "
    "LLM-free; no subagents are invoked during a monthly run."
)


# ---------------------------------------------------------------------------
# Report data model
# ---------------------------------------------------------------------------


def build_report_json(
    *,
    competitor_name: str,
    competitor_version: str,
    corpus_version: int,
    timestamp: str,
    lane1: dict[str, Any],
    lane2: dict[str, Any],
    lane3: dict[str, Any],
    lane2_aggregate: dict[str, Any],
) -> dict[str, Any]:
    """Build the JSON report structure."""
    return {
        "schema_version": 1,
        "kind": "whisker-survey-report",
        "competitor": competitor_name,
        "competitor_version": competitor_version,
        "corpus_version": corpus_version,
        "timestamp": timestamp,
        "aussagegrenzen": aussagegrenzen_text(competitor_name),
        "lane1_stability": lane1,
        "lane2_fidelity": lane2,
        "lane2_aggregate": lane2_aggregate,
        "lane3_comprehension": lane3,
    }


def render_report_md(
    report: dict[str, Any],
) -> str:
    """Render a human-readable Markdown report from the JSON structure."""
    lines: list[str] = []

    lines.append(f"# Survey Report: {report['competitor']} v{report['competitor_version']}")
    lines.append("")
    lines.append(f"**Corpus version:** {report['corpus_version']}")
    lines.append(f"**Generated:** {report['timestamp']}")
    lines.append("")

    lines.append("## Preamble")
    lines.append("")
    lines.append(CASE_STUDY_PREAMBLE)
    lines.append("")

    # Lane 1
    lines.append("## Lane 1: Stability (run-a vs run-b)")
    lines.append("")
    lane1 = report.get("lane1_stability", {})
    for config, results in lane1.items():
        lines.append(f"### {config}")
        lines.append("")
        if isinstance(results, list):
            for r in results:
                status = "STABLE" if r.get("stable") else "UNSTABLE"
                lines.append(f"- {r.get('pid', '?')}: {status}")
        lines.append("")

    # Lane 2
    lines.append("## Lane 2: Fidelity (candidate vs ideal)")
    lines.append("")
    lane2 = report.get("lane2_fidelity", {})
    agg = report.get("lane2_aggregate", {})
    for config, results in lane2.items():
        lines.append(f"### {config}")
        lines.append("")
        if isinstance(results, list):
            lines.append("| PID | NID | TEDS | MHS | Overall | Content Recall |")
            lines.append("|-----|-----|------|-----|---------|----------------|")
            for r in results:
                if r is not None:
                    lines.append(
                        f"| {r.get('pid', '?')} "
                        f"| {_fmt(r.get('nid'))} "
                        f"| {_fmt(r.get('teds'))} "
                        f"| {_fmt(r.get('mhs'))} "
                        f"| {_fmt(r.get('overall'))} "
                        f"| {_fmt(r.get('content_recall'))} |"
                    )
        lines.append("")

    if agg:
        lines.append("### Aggregate (paper macro-mean)")
        lines.append("")
        for config, agg_data in agg.items():
            if isinstance(agg_data, dict):
                lines.append(f"**{config}:** overall={_fmt(agg_data.get('overall'))}")
        lines.append("")

    # Lane 3
    lines.append("## Lane 3: Comprehension (verified facts)")
    lines.append("")
    lane3 = report.get("lane3_comprehension", {})
    for config, results in lane3.items():
        lines.append(f"### {config}")
        lines.append("")
        if isinstance(results, list):
            for r in results:
                if r is not None:
                    verdict = r.get("verdict", "?")
                    verified = r.get("verified_count", 0)
                    passed = r.get("passed", 0)
                    lines.append(
                        f"- {r.get('pid', '?')}: {verdict} "
                        f"({passed}/{verified} verified facts passed)"
                    )
        lines.append("")

    # Aussagegrenzen
    lines.append("## Aussagegrenzen (Limitations)")
    lines.append("")
    lines.append(AUSSAGEGRENZEN_TEXT)
    lines.append("")

    return "\n".join(lines)


def _fmt(val: float | None) -> str:
    """Format a float for display, or '-' for None."""
    if val is None:
        return "-"
    return f"{val:.4f}"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def write_report(
    report: dict[str, Any],
    out_dir: Path,
    competitor_name: str,
) -> tuple[Path, Path]:
    """Write JSON and Markdown reports. Returns (json_path, md_path)."""
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"survey-{competitor_name}.json"
    md_path = out_dir / f"survey-{competitor_name}.md"

    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_report_md(report), encoding="utf-8")

    log.info("Wrote survey report: %s, %s", json_path, md_path)
    return json_path, md_path


def default_report_dir(bench_root: Path) -> Path:
    """Return the default report output directory, ``reports/YYYY-MM``.

    Reports are published beside each other rather than buried in the run bundle
    that produced them, so a reader can find the current one without knowing a run
    ID. The bundle under ``runs/`` keeps the evidence.
    """
    now = datetime.now(timezone.utc)
    return bench_root / "reports" / now.strftime("%Y-%m")
