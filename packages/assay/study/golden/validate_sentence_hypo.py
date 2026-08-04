#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Validate sentence-level hypothesis labels for paper routing classifier training."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from assay.paper_routing.hypotheses import CATALOG

ALLOWED_LABELS = frozenset(h.id for h in CATALOG)
REQUIRED_FIELDS = frozenset({"text", "labels"})
OPTIONAL_FIELDS = frozenset({"paper_id"})


def _golden_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "golden"


def _default_paths() -> tuple[Path, Path]:
    base = _golden_dir()
    return (
        base / "sentence_hypo_train.jsonl",
        base / "sentence_hypo_test.jsonl",
    )


def load_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{lineno}: expected JSON object")
        rows.append(row)
    return rows


def validate_rows(rows: list[dict[str, object]], *, path: Path) -> list[str]:
    errors: list[str] = []
    for lineno, row in enumerate(rows, start=1):
        prefix = f"{path.name}:{lineno}"
        keys = set(row.keys())
        missing = REQUIRED_FIELDS - keys
        if missing:
            errors.append(f"{prefix}: missing fields {sorted(missing)}")
            continue
        extra = keys - REQUIRED_FIELDS - OPTIONAL_FIELDS
        if extra:
            errors.append(f"{prefix}: unexpected fields {sorted(extra)}")
            continue

        text = row["text"]
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{prefix}: text must be a non-empty string")
            continue

        labels = row["labels"]
        if not isinstance(labels, list):
            errors.append(f"{prefix}: labels must be a JSON array")
            continue

        paper_id = row.get("paper_id")
        if paper_id is not None and (not isinstance(paper_id, str) or not paper_id.strip()):
            errors.append(f"{prefix}: paper_id must be a non-empty string when present")

        for label in labels:
            if not isinstance(label, str) or not label:
                errors.append(f"{prefix}: each label must be a non-empty string")
                break
            if label not in ALLOWED_LABELS:
                errors.append(f"{prefix}: unknown label {label!r}")

    return errors


def print_label_distribution(name: str, rows: list[dict[str, object]]) -> None:
    counts: Counter[str] = Counter()
    multi = 0
    for row in rows:
        labels = row.get("labels", [])
        if isinstance(labels, list) and len(labels) > 1:
            multi += 1
        if isinstance(labels, list):
            for label in labels:
                if isinstance(label, str):
                    counts[label] += 1
    print(f"=== {name} ({len(rows)} rows, {multi} multi-label) ===")
    for label in sorted(counts, key=lambda k: (-counts[k], k)):
        print(f"  {label}: {counts[label]}")
    print()


def check_train_test_overlap(
    train_rows: list[dict[str, object]],
    test_rows: list[dict[str, object]],
) -> None:
    train_texts = {row["text"] for row in train_rows if isinstance(row.get("text"), str)}
    test_texts = {row["text"] for row in test_rows if isinstance(row.get("text"), str)}
    overlap = train_texts & test_texts
    if overlap:
        print(
            f"WARNING: {len(overlap)} exact text strings appear in both train and test "
            "(often short/generic boilerplate; not a schema failure).",
        )
    else:
        print("No exact train/test text overlap.")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) == 0:
        train_path, test_path = _default_paths()
    elif len(args) == 2:
        train_path, test_path = Path(args[0]), Path(args[1])
    else:
        print(
            "Usage: validate_sentence_hypo.py [train.jsonl test.jsonl]",
            file=sys.stderr,
        )
        return 2

    all_errors: list[str] = []
    train_rows = load_rows(train_path)
    test_rows = load_rows(test_path)
    all_errors.extend(validate_rows(train_rows, path=train_path))
    all_errors.extend(validate_rows(test_rows, path=test_path))

    print_label_distribution("train", train_rows)
    print_label_distribution("test", test_rows)
    check_train_test_overlap(train_rows, test_rows)

    if all_errors:
        print("Schema errors:", file=sys.stderr)
        for err in all_errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    print("OK: sentence_hypo golden files passed schema validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
