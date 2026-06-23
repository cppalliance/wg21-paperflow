#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Run-level report rendering for a batch of whisker verdicts.

Pure functions: they turn a list of ``WhiskerResult`` into a JSON-serializable
dict and a human-readable Markdown leaderboard. The CLI persists them; nothing
here writes to disk. Output is deterministic (results sorted by pid).
"""

from __future__ import annotations

import re
from collections import Counter

from whisker import constants as C
from whisker.score import VERDICT_FAIL, VERDICT_PASS, VERDICT_REVIEW, WhiskerResult

__all__ = ["build_report", "render_report_md", "render_summary"]

_VERDICTS = (VERDICT_PASS, VERDICT_REVIEW, VERDICT_FAIL)
_MARK = {VERDICT_PASS: "PASS", VERDICT_REVIEW: "REVIEW", VERDICT_FAIL: "FAIL"}

# ANSI colors, applied only when the caller passes color=True (a real tty).
# The render functions stay deterministic: with color=False the output is plain
# text, so tests assert on stable strings and piped output carries no escapes.
_RESET = "\033[0m"
_BOLD = "\033[1m"
_ANSI = {VERDICT_FAIL: "\033[31m", VERDICT_REVIEW: "\033[33m", VERDICT_PASS: "\033[32m"}
_PID_WIDTH = 10


def _counts(results: list[WhiskerResult]) -> dict[str, int]:
    return {v: sum(1 for r in results if r.verdict == v) for v in _VERDICTS}


def _paint(text: str, code: str, color: bool) -> str:
    return f"{code}{text}{_RESET}" if color else text


def _flags_text(r: WhiskerResult) -> str:
    """One-line reason string: hard flags first, then soft, sorted, stable."""
    return "; ".join(sorted(r.hard_flags) + sorted(r.soft_flags)) or "clean"


def _region_lines(regions: list[dict], label: str) -> list[str]:
    """Indented region-detail lines for verbose output."""
    if not regions:
        return []
    lines = [f"      {label}:"]
    for reg in regions[:C.REGION_DETAIL_CAP]:
        sample = reg["sample"][:C.REGION_SNIPPET_CHARS]
        if reg["page"] is not None:
            lines.append(f'      p.{reg["page"]}: "{sample}"')
        else:
            lines.append(f'      "{sample}"')
    return lines


def _item_line(r: WhiskerResult, color: bool) -> str:
    """A single worst-offender line: pid, headline metrics, then the reason.

    When the reference oracle ran, the cross-converter agreement (nid/teds/mhs)
    leads the line. Without a reference, the content gate leads: ``uni`` is the
    order-invariant token-set recall that drives the verdict, ``cov`` is the
    shingle (reading-order) proxy shown for context only.
    """
    if r.ref_overall is not None:
        head = (
            f"  {r.pid.ljust(_PID_WIDTH)} "
            f"ovr={r.ref_overall:.3f} nid={r.ref_nid:.3f} "
            f"teds={r.ref_teds:.3f} mhs={r.ref_mhs:.3f}"
        )
    else:
        head = (
            f"  {r.pid.ljust(_PID_WIDTH)} "
            f"uni={r.unigram_coverage:.3f} cov={r.coverage:.3f} "
            f"drift={r.drift:.3f} qa={r.qa_score}"
        )
    return _paint(head, _ANSI[r.verdict], color) + f"  {_flags_text(r)}"


def build_report(results: list[WhiskerResult]) -> dict:
    """Assemble the JSON report payload from a batch of results."""
    ordered = sorted(results, key=lambda r: r.pid)
    return {
        "schema_version": C.WHISKER_SCHEMA_VERSION,
        "count": len(ordered),
        "counts": _counts(ordered),
        "results": [r.to_dict() for r in ordered],
    }


def render_report_md(results: list[WhiskerResult]) -> str:
    """Render a Markdown leaderboard. Deterministic, sorted by pid."""
    ordered = sorted(results, key=lambda r: r.pid)
    counts = _counts(ordered)
    lines = [
        "# whisker report",
        "",
        (f"{len(ordered)} scored: {counts[VERDICT_PASS]} pass, "
         f"{counts[VERDICT_REVIEW]} review, {counts[VERDICT_FAIL]} fail"),
        "",
        "| PID | verdict | overall | nid | teds | mhs | unigram | coverage | drift | qa | regions | flags |",
        "|-----|---------|--------:|----:|-----:|----:|--------:|---------:|------:|---:|--------:|-------|",
    ]

    def _cell(v: float | None) -> str:
        return f"{v:.3f}" if v is not None else "-"

    for r in ordered:
        flags = "; ".join(sorted(r.hard_flags) + sorted(r.soft_flags)) or "-"
        lines.append(
            f"| {r.pid} | {_MARK[r.verdict]} | {_cell(r.ref_overall)} | {_cell(r.ref_nid)} "
            f"| {_cell(r.ref_teds)} | {_cell(r.ref_mhs)} | {r.unigram_coverage:.3f} "
            f"| {r.coverage:.3f} | {r.drift:.3f} "
            f"| {r.qa_score} | {r.missing_region_count}+{r.extra_region_count} "
            f"| {flags} |"
        )
    region_papers = [r for r in ordered if r.missing_regions or r.extra_regions]
    if region_papers:
        lines.append("")
        lines.append("## Region detail")
        lines.append("")
        for r in region_papers:
            lines.append(f"### {r.pid}")
            lines.append("")
            for label, regions in (("missing", r.missing_regions), ("extra", r.extra_regions)):
                for reg in regions:
                    sample = reg["sample"][:C.REGION_SNIPPET_CHARS]
                    if reg["page"] is not None:
                        lines.append(f'- {label} p.{reg["page"]}: "{sample}"')
                    else:
                        lines.append(f'- {label}: "{sample}"')
            lines.append("")

    lines.append("")
    return "\n".join(lines)


def _worst_first(results: list[WhiskerResult], verdict: str) -> list[WhiskerResult]:
    """Items of one verdict, worst first, pid as a stable tiebreak.

    Leads with ``unigram_coverage``, the order-invariant content gate that
    actually drives hard fails, so the genuinely broken papers surface at the
    top. ``ref_overall`` (cross-converter agreement) is ADVISORY, never the
    verdict driver, so it is only a tiebreak: ranking by it would push real
    content fails below mere oracle disagreement. None (the --no-reference path)
    sorts as 1.0 so it never out-prioritizes a measured low coverage.
    """
    bucket = [r for r in results if r.verdict == verdict]
    return sorted(
        bucket,
        key=lambda r: (
            r.unigram_coverage,
            r.ref_overall if r.ref_overall is not None else 1.0,
            r.pid,
        ),
    )


def _section(
    results: list[WhiskerResult],
    verdict: str,
    *,
    color: bool,
    cap: int | None,
    report_path: str | None,
    verbose: bool = False,
) -> list[str]:
    items = _worst_first(results, verdict)
    if not items:
        return []
    header = _paint(f"{verdict} ({len(items)})", _BOLD + _ANSI[verdict], color)
    lines = ["", header]
    shown = items if cap is None else items[:cap]
    for r in shown:
        lines.append(_item_line(r, color))
        if verbose:
            lines.extend(_region_lines(r.missing_regions, "missing"))
            lines.extend(_region_lines(r.extra_regions, "extra"))
    hidden = len(items) - len(shown)
    if hidden > 0:
        where = f" (see {report_path})" if report_path else ""
        lines.append(f"  ... and {hidden} more{where}")
    return lines


# Flag strings embed the tripped value ("coverage 0.538 < 0.85"). For a rollup
# the value is noise: we want the category ("coverage <") so identical reasons
# aggregate the way ruff counts by rule code, not by message.
_FLAG_NUM_RE = re.compile(r"\b\d+(?:\.\d+)?\b")


def _flag_category(flag: str) -> str:
    """Collapse a flag to its value-free category for aggregation.

    Gate flags keep ``gate:<name>`` (drop the per-paper detail). Threshold flags
    drop the numbers and normalize the "(s)" plural, so "8 misaligned region(s)"
    and "2 misaligned region(s)" both become "misaligned regions".
    """
    if flag.startswith("gate:"):
        return ":".join(flag.split(":")[:2])
    stripped = _FLAG_NUM_RE.sub("", flag).replace("(s)", "s")
    return " ".join(stripped.split())


def _flag_rollup(results: list[WhiskerResult]) -> list[str]:
    """ruff --statistics style: flag categories, by tier, counted, sorted."""
    hard: Counter[str] = Counter()
    soft: Counter[str] = Counter()
    for r in results:
        hard.update(_flag_category(f) for f in r.hard_flags)
        soft.update(_flag_category(f) for f in r.soft_flags)
    if not hard and not soft:
        return []
    lines = ["", "flag rollup"]
    for tier, counter in (("hard", hard), ("soft", soft)):
        for flag, n in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"  {str(n).rjust(4)}  {tier}  {flag}")
    return lines


def _footer(
    counts: dict[str, int],
    scored: int,
    *,
    errored: int,
    skipped: int,
    elapsed: float | None,
    color: bool,
) -> str:
    parts = [
        f"{counts[VERDICT_FAIL]} failed",
        f"{counts[VERDICT_REVIEW]} review",
        f"{counts[VERDICT_PASS]} passed",
    ]
    if errored:
        parts.append(f"{errored} errored")
    scope = f"{scored} scored"
    if skipped:
        scope += f", {skipped} skipped"
    body = ", ".join(parts) + f" ({scope})"
    if elapsed is not None:
        body += f" in {elapsed:.1f}s"
    worst = (
        VERDICT_FAIL if counts[VERDICT_FAIL]
        else VERDICT_REVIEW if counts[VERDICT_REVIEW]
        else VERDICT_PASS
    )
    return _paint(f"=== {body} ===", _BOLD + _ANSI[worst], color)


def render_summary(
    results: list[WhiskerResult],
    *,
    elapsed: float | None = None,
    errored: int = 0,
    skipped: int = 0,
    report_path: str | None = None,
    color: bool = False,
    verbose: bool = False,
    quiet: bool = False,
    stats: bool = False,
    cap: int = C.SUMMARY_SECTION_CAP,
) -> str:
    """Human terminal summary for a batch, modeled on pytest/ruff/eslint.

    Default: the fail section then the review section (worst first by content
    gate, capped), an optional flag rollup, and a one-line footer. Passes hidden;
    they live in the count. ``verbose`` lifts the cap and adds the pass section;
    ``quiet`` collapses everything to the footer. ``color`` adds ANSI (tty only).
    Deterministic for a fixed ``elapsed`` (sorted sections, sorted flags).
    """
    counts = _counts(results)
    footer = _footer(
        counts, len(results),
        errored=errored, skipped=skipped, elapsed=elapsed, color=color,
    )
    if quiet:
        return footer

    section_cap = None if verbose else cap
    lines: list[str] = []
    verdicts = (VERDICT_FAIL, VERDICT_REVIEW)
    if verbose:
        verdicts = (VERDICT_FAIL, VERDICT_REVIEW, VERDICT_PASS)
    for verdict in verdicts:
        lines.extend(
            _section(results, verdict, color=color, cap=section_cap,
                     report_path=report_path, verbose=verbose)
        )
    if stats:
        lines.extend(_flag_rollup(results))
    lines.append("")
    lines.append(footer)
    return "\n".join(lines)
