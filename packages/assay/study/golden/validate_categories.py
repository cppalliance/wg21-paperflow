#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Validate golden paper category labels for assay routing classifier eval."""

from __future__ import annotations

import json
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

MIN_ENTRIES = 200
MIN_PER_PRIMARY = 30

PRIMARY_CATEGORIES = frozenset({
    "library-design",
    "library-wording",
    "language-evolution",
    "language-wording",
})
SKIP_CATEGORIES = frozenset({"informational"})
ALLOWED_CATEGORIES = PRIMARY_CATEGORIES | SKIP_CATEGORIES
ALLOWED_CONFIDENCE = frozenset({"high", "medium"})
REJECTED_CATEGORIES = frozenset({
    "language-design",
    "procedural",
    "core-wording",
})

GROUP_TO_CATEGORY = {
    "LEWG": "library-design",
    "LWG": "library-wording",
    "EWG": "language-evolution",
    "CWG": "language-wording",
}

REQUIRED_FIELDS = frozenset({
    "paper_id",
    "title",
    "target_group",
    "categories",
    "confidence",
    "notes",
})


def _default_jsonl_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "golden" / "paper_categories.jsonl"


def _expected_categories_from_target_groups(target_groups: list[str]) -> list[str]:
    return sorted({
        GROUP_TO_CATEGORY[g]
        for g in target_groups
        if g in GROUP_TO_CATEGORY
    })


def load_entries(path: Path) -> list[dict]:
    entries: list[dict] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {lineno}: invalid JSON: {exc}") from exc
        if not isinstance(entry, dict):
            raise ValueError(f"line {lineno}: expected JSON object")
        entries.append(entry)
    return entries


def validate_schema(entries: list[dict]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()

    for i, entry in enumerate(entries, start=1):
        prefix = f"entry {i} ({entry.get('paper_id', '?')})"

        missing = REQUIRED_FIELDS - entry.keys()
        if missing:
            errors.append(f"{prefix}: missing fields {sorted(missing)}")
            continue

        paper_id = entry["paper_id"]
        if paper_id in seen_ids:
            errors.append(f"{prefix}: duplicate paper_id {paper_id!r}")
        seen_ids.add(paper_id)

        if entry["confidence"] not in ALLOWED_CONFIDENCE:
            errors.append(
                f"{prefix}: invalid confidence {entry['confidence']!r}",
            )

        categories = entry["categories"]
        if not isinstance(categories, list) or not categories:
            errors.append(f"{prefix}: categories must be a non-empty list")
            continue

        for cat in categories:
            if cat in REJECTED_CATEGORIES:
                errors.append(f"{prefix}: rejected category {cat!r}")
            elif cat not in ALLOWED_CATEGORIES:
                errors.append(f"{prefix}: unknown category {cat!r}")

        if "target_groups" in entry:
            tgs = entry["target_groups"]
            if not isinstance(tgs, list):
                errors.append(f"{prefix}: target_groups must be a list")
            else:
                expected = _expected_categories_from_target_groups(tgs)
                actual = sorted(categories)
                if actual != expected:
                    errors.append(
                        f"{prefix}: categories {actual} != "
                        f"target_groups map {expected}",
                    )

    return errors


def print_distribution(entries: list[dict]) -> None:
    label_counts: Counter[str] = Counter()
    high_counts: Counter[str] = Counter()
    target_group_counts: Counter[str] = Counter()
    multi_label = 0
    overlap: Counter[tuple[str, str]] = Counter()

    for entry in entries:
        cats = entry["categories"]
        conf = entry["confidence"]
        for cat in cats:
            label_counts[cat] += 1
            if conf == "high" and cat in PRIMARY_CATEGORIES:
                high_counts[cat] += 1

        if len(cats) > 1 and "informational" not in cats:
            multi_label += 1
            for pair in combinations(sorted(c for c in cats if c in PRIMARY_CATEGORIES), 2):
                overlap[pair] += 1

        if "informational" not in cats:
            target_group_counts[entry["target_group"]] += 1

    print(f"Total entries: {len(entries)}")
    print()
    print("Per-label counts (primary + informational):")
    for cat in sorted(label_counts):
        print(f"  {cat}: {label_counts[cat]}")
    print()
    print("Per-label high-confidence counts (primary only):")
    for cat in sorted(PRIMARY_CATEGORIES):
        print(f"  {cat}: {high_counts[cat]}")
    print()
    print(f"Multi-label papers (non-informational): {multi_label}")
    if overlap:
        print("Overlap matrix (pair counts):")
        for pair, count in sorted(overlap.items()):
            print(f"  {pair[0]} + {pair[1]}: {count}")
    print()
    print("target_group histogram (non-informational):")
    for group, count in target_group_counts.most_common():
        print(f"  {group}: {count}")


def acceptance_errors(entries: list[dict]) -> list[str]:
    errors: list[str] = []
    if len(entries) < MIN_ENTRIES:
        errors.append(f"entry count {len(entries)} < {MIN_ENTRIES}")

    per_primary: Counter[str] = Counter()
    high_per_primary: Counter[str] = Counter()
    for entry in entries:
        for cat in entry["categories"]:
            if cat in PRIMARY_CATEGORIES:
                per_primary[cat] += 1
                if entry["confidence"] == "high":
                    high_per_primary[cat] += 1

    for cat in sorted(PRIMARY_CATEGORIES):
        if per_primary[cat] < MIN_PER_PRIMARY:
            errors.append(
                f"{cat}: {per_primary[cat]} papers < {MIN_PER_PRIMARY}",
            )
        if high_per_primary[cat] < MIN_PER_PRIMARY:
            print(
                f"NOTE: {cat} has {high_per_primary[cat]} high-confidence "
                f"labels (< {MIN_PER_PRIMARY}); total labels={per_primary[cat]}",
            )

    return errors


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    path = Path(args[0]) if args else _default_jsonl_path()

    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1

    try:
        entries = load_entries(path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    schema_errors = validate_schema(entries)
    if schema_errors:
        print("Schema errors:", file=sys.stderr)
        for err in schema_errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    print_distribution(entries)
    print()

    gate_errors = acceptance_errors(entries)
    if gate_errors:
        print("Acceptance failures:", file=sys.stderr)
        for err in gate_errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    print("Validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
