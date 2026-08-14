# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
"""
Evaluate ``route_paper()`` against ``data/golden/paper_categories.jsonl``.

Golden paper-level labels map content categories to expected routing groups:

| category            | group |
|---------------------|-------|
| library-design      | LEWG  |
| library-wording     | LWG   |
| language-evolution  | EWG   |
| language-wording    | CWG   |
| informational       | (none)|

Ablation modes (``--mode`` or ``--ablation-matrix``):

| Mode | use_regex | Classifiers | Aggregator |
|------|-----------|-------------|------------|
| regex | yes | none | hand |
| nli | no | nli-small | hand |
| seqcls | no | routing-tagger | hand |
| nli+seqcls | no | nli-small, routing-tagger | hand |
| regex+nli | yes | nli-small | hand |
| regex+seqcls | yes | routing-tagger | hand |
| regex+nli+seqcls | yes | nli-small, routing-tagger | hand |
| regex+nli+hgb | yes | nli-small | HGB (trained on regex+nli) |
| regex+seqcls+hgb | yes | routing-tagger | HGB (trained on regex+seqcls) |

HGB modes always include regex. The frozen aggregators were trained on
regex+classifier hypothesis hits; applying HGB without regex is a
train/serve mismatch.

Usage (from repo root):

  export WG21_DATA_DIR=/path/to/wg21-data
  uv run --directory packages/assay python scripts/eval_route_paper.py --ablation-matrix

  uv run --directory packages/assay python scripts/eval_route_paper.py \\
      --mode regex+nli --paperstore /path/to/paperstore --failures-only
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from assay.paper_routing import RoutingGroup, route_paper
from pipeline.classifier_backends import ClassifierBackend

from eval_common import (
    default_paperstore_dir,
    expected_groups,
    parse_audience_from_md,
    paper_golden_path,
    resolve_classifier,
)
from eval_metrics import MultilabelReport, prf_from_counts

logger = logging.getLogger(__name__)

_ALL_GROUPS = frozenset(RoutingGroup)

ABLATION_MODES: dict[str, tuple[bool, tuple[str, ...]]] = {
    "regex": (True, ()),
    "nli": (False, ("nli-small",)),
    "seqcls": (False, ("routing-tagger",)),
    "nli+seqcls": (False, ("nli-small", "routing-tagger")),
    "regex+nli": (True, ("nli-small",)),
    "regex+seqcls": (True, ("routing-tagger",)),
    "regex+nli+seqcls": (True, ("nli-small", "routing-tagger")),
    "regex+nli+hgb": (True, ("nli-small",)),
    "regex+seqcls+hgb": (True, ("routing-tagger",)),
    # Aliases: HGB was trained with regex on; these names still run regex.
    "nli+hgb": (True, ("nli-small",)),
    "seqcls+hgb": (True, ("routing-tagger",)),
}

_LEARNED_AGGREGATOR_MODES: frozenset[str] = frozenset(
    {
        "regex+nli+hgb",
        "regex+seqcls+hgb",
        "nli+hgb",
        "seqcls+hgb",
    }
)

# Default ablation-matrix sweep. Combined modes remain in ABLATION_MODES
# and can be selected with --mode; they are excluded here for runtime cost.
_ABLATION_ORDER: tuple[str, ...] = (
    "regex",
    "seqcls",
    "nli",
)


@dataclass(frozen=True)
class PaperGolden:
    paper_id: str
    title: str
    target_group: str
    categories: tuple[str, ...]
    confidence: str
    notes: str


@dataclass
class PaperEvalRow:
    paper_id: str
    title: str
    expected_groups: list[str]
    predicted_groups: list[str]
    target_group: str
    categories: list[str]
    exact_match: bool
    target_group_hit: bool | None
    missing_md: bool
    quadrant_scores: dict[str, float]
    sustained_counts: dict[str, int]
    is_administrative: bool
    is_performance_focused: bool
    sentence_count: int


@dataclass(frozen=True)
class AblationConfig:
    name: str
    use_regex: bool
    classifiers: tuple[ClassifierBackend, ...]
    use_learned_aggregator: bool = False


def _default_golden_path() -> Path:
    return paper_golden_path()


def _default_paperstore_dir() -> Path:
    return default_paperstore_dir()


def _load_golden(path: Path) -> list[PaperGolden]:
    rows: list[PaperGolden] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        raw = json.loads(line)
        rows.append(
            PaperGolden(
                paper_id=raw["paper_id"],
                title=raw.get("title", ""),
                target_group=raw.get("target_group", "NONE"),
                categories=tuple(raw.get("categories", [])),
                confidence=raw.get("confidence", ""),
                notes=raw.get("notes", ""),
            ),
        )
    if not rows:
        raise SystemExit(f"No golden rows in {path}")
    return rows


def _paper_md_path(paperstore: Path, paper_id: str) -> Path:
    return paperstore / f"{paper_id.lower()}.md"


def _resolve_ablation_config(
    mode: str,
    *,
    nli_classifier: str,
    seqcls_classifier: str,
    classifier_cache: dict[str, ClassifierBackend],
    cpu_classifiers: bool,
) -> AblationConfig:
    if mode not in ABLATION_MODES:
        raise SystemExit(
            f"Unknown mode {mode!r}. Choose from: {sorted(ABLATION_MODES)}",
        )
    use_regex, service_names = ABLATION_MODES[mode]
    resolved_names: list[str] = []
    for name in service_names:
        if name == "nli-small":
            resolved_names.append(nli_classifier)
        elif name == "routing-tagger":
            resolved_names.append(seqcls_classifier)
        else:
            resolved_names.append(name)

    backends: list[ClassifierBackend] = []
    for name in resolved_names:
        if name not in classifier_cache:
            classifier_cache[name] = resolve_classifier(
                name,
                cpu_only=cpu_classifiers,
            )
        backends.append(classifier_cache[name])

    return AblationConfig(
        name=mode,
        use_regex=use_regex,
        classifiers=tuple(backends),
        use_learned_aggregator=mode in _LEARNED_AGGREGATOR_MODES,
    )


def _evaluate_paper(
    golden: PaperGolden,
    *,
    paperstore: Path,
    use_audience: bool,
    config: AblationConfig,
) -> PaperEvalRow:
    md_path = _paper_md_path(paperstore, golden.paper_id)
    if not md_path.is_file():
        return PaperEvalRow(
            paper_id=golden.paper_id,
            title=golden.title,
            expected_groups=sorted(g.value for g in expected_groups(golden.categories)),
            predicted_groups=[],
            target_group=golden.target_group,
            categories=list(golden.categories),
            exact_match=False,
            target_group_hit=None,
            missing_md=True,
            quadrant_scores={},
            sustained_counts={},
            is_administrative=False,
            is_performance_focused=False,
            sentence_count=0,
        )

    md = md_path.read_text(encoding="utf-8")
    audience = parse_audience_from_md(md) if use_audience else None
    result = route_paper(
        md,
        audience=audience,
        classifiers=config.classifiers,
        use_regex=config.use_regex,
        use_learned_aggregator=config.use_learned_aggregator,
    )
    predicted = set(result.groups)
    expected = expected_groups(golden.categories)
    target_hit: bool | None
    if golden.target_group == "NONE":
        target_hit = None
    else:
        try:
            target = RoutingGroup(golden.target_group)
        except ValueError:
            target_hit = None
        else:
            target_hit = target in predicted

    return PaperEvalRow(
        paper_id=golden.paper_id,
        title=golden.title,
        expected_groups=sorted(g.value for g in expected),
        predicted_groups=sorted(g.value for g in predicted),
        target_group=golden.target_group,
        categories=list(golden.categories),
        exact_match=predicted == expected,
        target_group_hit=target_hit,
        missing_md=False,
        quadrant_scores={g.value: score for g, score in result.quadrant_scores.items()},
        sustained_counts={
            g.value: count for g, count in result.sustained_counts.items()
        },
        is_administrative=result.is_administrative,
        is_performance_focused=result.is_performance_focused,
        sentence_count=result.sentence_count,
    )


def _format_prf(label: str, scores) -> str:
    return (
        f"{label}: precision={scores.precision:.3f} "
        f"recall={scores.recall:.3f} f1={scores.f1:.3f} support={scores.support}"
    )


def _rows_to_payload(rows: Sequence[PaperEvalRow]) -> list[dict[str, object]]:
    return [
        {
            "paper_id": row.paper_id,
            "title": row.title,
            "expected_groups": row.expected_groups,
            "predicted_groups": row.predicted_groups,
            "target_group": row.target_group,
            "categories": row.categories,
            "exact_match": row.exact_match,
            "target_group_hit": row.target_group_hit,
            "missing_md": row.missing_md,
            "quadrant_scores": row.quadrant_scores,
            "sustained_counts": row.sustained_counts,
            "is_administrative": row.is_administrative,
            "is_performance_focused": row.is_performance_focused,
            "sentence_count": row.sentence_count,
        }
        for row in rows
    ]


def _summarize_rows(rows: list[PaperEvalRow]) -> dict[str, object]:
    evaluated = [row for row in rows if not row.missing_md]
    missing = [row for row in rows if row.missing_md]
    report = MultilabelReport()
    admin_total = 0
    admin_correct = 0
    primary_total = 0
    primary_correct = 0
    cardinality_hist: dict[int, int] = {}
    for row in evaluated:
        report.add_item(
            set(row.expected_groups),
            set(row.predicted_groups),
            label_universe={g.value for g in _ALL_GROUPS},
        )
        if row.categories == ["informational"]:
            admin_total += 1
            if row.is_administrative:
                admin_correct += 1

        # Primary accuracy: among single-group papers, did we get that group?
        if len(row.expected_groups) == 1:
            primary_total += 1
            if row.expected_groups[0] in row.predicted_groups:
                primary_correct += 1

        # Predicted cardinality histogram
        n_pred = len(row.predicted_groups)
        cardinality_hist[n_pred] = cardinality_hist.get(n_pred, 0) + 1

    micro = report.micro_prf()
    macro = report.macro_prf()
    target_rows = [row for row in evaluated if row.target_group_hit is not None]
    target_hits = sum(1 for row in target_rows if row.target_group_hit)

    return {
        "papers_in_golden": len(rows),
        "papers_evaluated": len(evaluated),
        "papers_missing_md": len(missing),
        "exact_match": report.exact_match,
        "exact_match_rate": report.exact_match_rate(),
        "micro": asdict(micro),
        "macro": asdict(macro),
        "target_group_recall": (
            target_hits / len(target_rows) if target_rows else None
        ),
        "target_group_hits": target_hits,
        "target_group_total": len(target_rows),
        "admin_accuracy": (admin_correct / admin_total if admin_total else None),
        "admin_correct": admin_correct,
        "admin_total": admin_total,
        "primary_accuracy": (
            primary_correct / primary_total if primary_total else None
        ),
        "primary_correct": primary_correct,
        "primary_total": primary_total,
        "cardinality_histogram": dict(sorted(cardinality_hist.items())),
        "per_group": {
            label: asdict(prf_from_counts(counts))
            for label, counts in sorted(report.per_label.items())
            if prf_from_counts(counts).support > 0 or counts.tp > 0
        },
    }


def _print_summary(rows: list[PaperEvalRow], *, mode: str | None = None) -> None:
    summary = _summarize_rows(rows)
    prefix = f"[{mode}] " if mode else ""
    print(f"{prefix}Papers in golden: {summary['papers_in_golden']}")
    print(f"{prefix}Papers evaluated: {summary['papers_evaluated']}")
    print(f"{prefix}Papers missing markdown: {summary['papers_missing_md']}")
    print(
        f"{prefix}Exact set match: {summary['exact_match']}/"
        f"{summary['papers_evaluated']} "
        f"({summary['exact_match_rate']:.1%})",
    )
    if summary["primary_total"]:
        print(
            f"{prefix}Primary accuracy (single-group papers): "
            f"{summary['primary_correct']}/{summary['primary_total']} "
            f"({summary['primary_accuracy']:.1%})",
        )
    micro = summary["micro"]
    macro = summary["macro"]
    print(
        f"{prefix}Micro: precision={micro['precision']:.3f} "
        f"recall={micro['recall']:.3f} f1={micro['f1']:.3f}",
    )
    print(
        f"{prefix}Macro: precision={macro['precision']:.3f} "
        f"recall={macro['recall']:.3f} f1={macro['f1']:.3f}",
    )
    if summary["target_group_total"]:
        print(
            f"{prefix}Index target_group recall: "
            f"{summary['target_group_hits']}/{summary['target_group_total']} "
            f"({summary['target_group_recall']:.1%})",
        )
    if summary["admin_total"]:
        print(
            f"{prefix}Administrative accuracy: "
            f"{summary['admin_correct']}/{summary['admin_total']} "
            f"({summary['admin_accuracy']:.1%})",
        )
    cardinality = summary.get("cardinality_histogram", {})
    if cardinality:
        hist_str = " | ".join(f"{k}:{v}" for k, v in sorted(cardinality.items()))
        print(f"{prefix}Predicted cardinality: {hist_str}")
    print()
    print(f"{prefix}Per-group metrics:")
    per_group = summary["per_group"]
    assert isinstance(per_group, dict)
    for label in sorted(per_group):
        scores = per_group[label]
        print(
            f"  {label}: precision={scores['precision']:.3f} "
            f"recall={scores['recall']:.3f} f1={scores['f1']:.3f} "
            f"support={scores['support']}",
        )


def _render_ablation_markdown(
    summaries: list[dict[str, object]],
    *,
    golden_path: Path,
    paperstore: Path,
) -> str:
    lines = [
        "# Paper routing ablation matrix",
        "",
        f"- Golden: `{golden_path}`",
        f"- Paperstore: `{paperstore}`",
        "",
        "| Mode | Exact match | Primary acc | Micro F1 | Macro F1 | Target recall | Admin accuracy | Elapsed (s) |",
        "|------|-------------|-------------|----------|----------|---------------|----------------|-------------|",
    ]
    for row in summaries:
        mode = str(row["mode"])
        exact = row["exact_match_rate"]
        primary = row.get("primary_accuracy")
        micro_f1 = row["micro_f1"]
        macro_f1 = row["macro_f1"]
        target = row["target_group_recall"]
        admin = row["admin_accuracy"]
        elapsed = row["elapsed_seconds"]
        lines.append(
            f"| {mode} | {exact:.1%} | {_fmt_optional_pct(primary)} | "
            f"{micro_f1:.3f} | {macro_f1:.3f} | "
            f"{_fmt_optional_pct(target)} | {_fmt_optional_pct(admin)} | {elapsed:.1f} |",
        )
    return "\n".join(lines) + "\n"


def _fmt_optional_pct(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.1%}"


def _run_mode(
    mode: str,
    *,
    golden_rows: list[PaperGolden],
    paperstore: Path,
    use_audience: bool,
    nli_classifier: str,
    seqcls_classifier: str,
    classifier_cache: dict[str, ClassifierBackend],
    cpu_classifiers: bool,
) -> tuple[list[PaperEvalRow], dict[str, object], float]:
    config = _resolve_ablation_config(
        mode,
        nli_classifier=nli_classifier,
        seqcls_classifier=seqcls_classifier,
        classifier_cache=classifier_cache,
        cpu_classifiers=cpu_classifiers,
    )
    logger.info(
        "Evaluating mode %s (use_regex=%s, classifiers=%d)",
        mode,
        config.use_regex,
        len(config.classifiers),
    )
    started = time.perf_counter()
    rows = [
        _evaluate_paper(
            row,
            paperstore=paperstore,
            use_audience=use_audience,
            config=config,
        )
        for row in golden_rows
    ]
    elapsed = time.perf_counter() - started
    summary = _summary_from_rows(rows, mode=mode, elapsed=elapsed)
    logger.info("Mode %s finished in %.1fs", mode, elapsed)
    return rows, summary, elapsed


def _summary_from_rows(
    rows: list[PaperEvalRow], *, mode: str, elapsed: float = 0.0
) -> dict[str, object]:
    summary = _summarize_rows(rows)
    summary["mode"] = mode
    summary["elapsed_seconds"] = elapsed
    summary["micro_f1"] = summary["micro"]["f1"]
    summary["macro_f1"] = summary["macro"]["f1"]
    summary.setdefault("primary_accuracy", None)
    return summary


def _rows_from_payload(payload: list[dict[str, object]]) -> list[PaperEvalRow]:
    rows: list[PaperEvalRow] = []
    for item in payload:
        rows.append(
            PaperEvalRow(
                paper_id=str(item["paper_id"]),
                title=str(item.get("title", "")),
                expected_groups=list(item.get("expected_groups", [])),
                predicted_groups=list(item.get("predicted_groups", [])),
                target_group=str(item.get("target_group", "NONE")),
                categories=list(item.get("categories", [])),
                exact_match=bool(item.get("exact_match")),
                target_group_hit=item.get("target_group_hit"),
                missing_md=bool(item.get("missing_md")),
                quadrant_scores=dict(item.get("quadrant_scores", {})),
                sustained_counts=dict(item.get("sustained_counts", {})),
                is_administrative=bool(item.get("is_administrative")),
                is_performance_focused=bool(item.get("is_performance_focused")),
                sentence_count=int(item.get("sentence_count", 0)),
            ),
        )
    return rows


def _summarize_output_dir(output_dir: Path) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for mode in _ABLATION_ORDER:
        mode_path = output_dir / f"{mode}.json"
        if not mode_path.is_file():
            logger.warning("Skipping missing mode artifact: %s", mode_path)
            continue
        payload = json.loads(mode_path.read_text(encoding="utf-8"))
        rows = _rows_from_payload(payload)
        summaries.append(_summary_from_rows(rows, mode=mode))
    return summaries


def _write_ablation_artifacts(
    summaries: list[dict[str, object]],
    *,
    output_dir: Path,
    golden_path: Path,
    paperstore: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "ablation_summary.json"
    summary_path.write_text(
        json.dumps(summaries, indent=2) + "\n",
        encoding="utf-8",
    )
    md_path = output_dir / "ablation_summary.md"
    md_path.write_text(
        _render_ablation_markdown(
            summaries,
            golden_path=golden_path,
            paperstore=paperstore,
        ),
        encoding="utf-8",
    )
    logger.info("Wrote %s", summary_path)
    logger.info("Wrote %s", md_path)
    print(md_path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--golden",
        type=Path,
        default=_default_golden_path(),
        help="Path to data/golden/paper_categories.jsonl",
    )
    parser.add_argument(
        "--paperstore",
        type=Path,
        default=None,
        help="Directory with {paper_id}.md files (default: $WG21_DATA_DIR/paperstore)",
    )
    parser.add_argument(
        "--no-audience",
        action="store_true",
        help="Do not pass front-matter audience into route_paper()",
    )
    parser.add_argument(
        "--mode",
        default="seqcls",
        choices=sorted(ABLATION_MODES),
        help="Single ablation mode (default: regex when not using --ablation-matrix)",
    )
    parser.add_argument(
        "--ablation-matrix",
        action="store_true",
        help="Run all six ablation modes and write comparison summary",
    )
    parser.add_argument(
        "--nli-classifier",
        default="nli-small",
        metavar="NAME",
        help="NLI classifier service name from SERVICES.toml",
    )
    parser.add_argument(
        "--seqcls-classifier",
        default="routing-tagger",
        metavar="NAME",
        help="Seqcls classifier service name from SERVICES.toml",
    )
    parser.add_argument(
        "--classifier",
        default=None,
        metavar="NAME",
        help="Deprecated alias for --nli-classifier in single-mode regex+nli runs",
    )
    parser.add_argument(
        "--no-classifier",
        action="store_true",
        help="Deprecated alias for --mode regex",
    )
    parser.add_argument(
        "--summarize-dir",
        type=Path,
        default=None,
        help="Build ablation_summary from existing per-mode JSON in this directory",
    )
    parser.add_argument(
        "--cpu-classifiers",
        action="store_true",
        help="Run ML classifiers on CPU (avoids GPU OOM when loading multiple models)",
    )
    parser.add_argument(
        "--failures-only",
        action="store_true",
        help="Print only papers whose predicted groups differ from golden categories",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write per-paper JSON report to this path (single mode only)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for per-mode JSON and ablation summary (--ablation-matrix)",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        metavar="ID",
        help="Evaluate only this paper (repeatable)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    golden_rows = _load_golden(args.golden)
    if args.paper_id:
        wanted = {pid.upper() for pid in args.paper_id}
        golden_rows = [row for row in golden_rows if row.paper_id in wanted]
        if not golden_rows:
            raise SystemExit(f"No golden rows matched --paper-id {sorted(wanted)}")

    paperstore = args.paperstore or _default_paperstore_dir()

    if args.summarize_dir is not None:
        summaries = _summarize_output_dir(args.summarize_dir)
        if not summaries:
            raise SystemExit(f"No mode JSON files found in {args.summarize_dir}")
        _write_ablation_artifacts(
            summaries,
            output_dir=args.summarize_dir,
            golden_path=args.golden,
            paperstore=paperstore,
        )
        return 0

    if not paperstore.is_dir():
        raise SystemExit(f"Paperstore directory not found: {paperstore}")

    nli_classifier = args.nli_classifier
    if args.classifier is not None:
        nli_classifier = args.classifier

    classifier_cache: dict[str, ClassifierBackend] = {}

    if args.ablation_matrix:
        modes = list(_ABLATION_ORDER)
    elif args.mode is None:
        if args.no_classifier:
            modes = ["regex"]
        else:
            modes = ["regex+nli"]
    else:
        modes = [args.mode]
    summaries: list[dict[str, object]] = []
    output_dir = args.output_dir or Path("data/eval_ablation")
    output_dir.mkdir(parents=True, exist_ok=True)
    for mode in modes:
        rows, summary, _elapsed = _run_mode(
            mode,
            golden_rows=golden_rows,
            paperstore=paperstore,
            use_audience=not args.no_audience,
            nli_classifier=nli_classifier,
            seqcls_classifier=args.seqcls_classifier,
            classifier_cache=classifier_cache,
            cpu_classifiers=args.cpu_classifiers,
        )
        summaries.append(summary)
        mode_path = output_dir / f"{mode}.json"
        mode_path.write_text(
            json.dumps(_rows_to_payload(rows), indent=2) + "\n",
            encoding="utf-8",
        )
        logger.info("Wrote %s", mode_path)

    _write_ablation_artifacts(
        summaries,
        output_dir=output_dir,
        golden_path=args.golden,
        paperstore=paperstore,
    )
    missing = int(summaries[0]["papers_missing_md"])
    return 2 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
