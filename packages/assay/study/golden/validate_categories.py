#
# Copyright (c) 2026 Leo Chen (leo.chen0412@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Validate golden paper category labels for assay routing classifier eval."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from itertools import combinations
from pathlib import Path
from typing import Literal

MIN_ENTRIES_TRAIN = 200
MIN_PER_PRIMARY_ANY_TRAIN = 30

MIN_ENTRIES_TEST = 80
MIN_PRIMARY_TEST = {
    "library-design": 28,
    "language-evolution": 18,
    "language-wording": 12,
    "informational": 13,
    "library-wording": 8,
}
PROPORTION_TOLERANCE_PP = 5.0

PRIMARY_CATEGORIES = frozenset(
    {
        "library-design",
        "library-wording",
        "language-evolution",
        "language-wording",
    }
)
SKIP_CATEGORIES = frozenset({"informational"})
ALLOWED_CATEGORIES = PRIMARY_CATEGORIES | SKIP_CATEGORIES
ALLOWED_CONFIDENCE = frozenset({"high", "medium"})
ALLOWED_TARGET_GROUPS = frozenset({"LEWG", "LWG", "EWG", "CWG", "NONE"})
TARGET_GROUP_PRIMARY_CATEGORY = {
    "LEWG": "library-design",
    "LWG": "library-wording",
    "EWG": "language-evolution",
    "CWG": "language-wording",
    "NONE": "informational",
}
REJECTED_CATEGORIES = frozenset(
    {
        "language-design",
        "procedural",
        "core-wording",
    }
)

REQUIRED_FIELDS = frozenset(
    {
        "paper_id",
        "title",
        "target_group",
        "categories",
        "confidence",
        "notes",
    }
)

Profile = Literal["train", "test"]


def _golden_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "golden"


def train_path() -> Path:
    return _golden_dir() / "paper_categories_train.jsonl"


def test_path() -> Path:
    return _golden_dir() / "paper_categories_test.jsonl"


def load_entries(path: Path) -> list[dict]:
    entries: list[dict] = []
    for lineno, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
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

        if entry["target_group"] not in ALLOWED_TARGET_GROUPS:
            errors.append(
                f"{prefix}: invalid target_group {entry['target_group']!r}",
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

        if len(categories) != len(set(categories)):
            errors.append(f"{prefix}: duplicate categories {categories!r}")

        if categories[1:] != sorted(categories[1:]):
            errors.append(
                f"{prefix}: categories after the first must be sorted "
                f"(got {categories!r})",
            )

        if "informational" in categories and len(categories) > 1:
            errors.append(
                f"{prefix}: informational cannot co-occur with primary categories",
            )

        target_group = entry["target_group"]
        if target_group in TARGET_GROUP_PRIMARY_CATEGORY:
            expected = TARGET_GROUP_PRIMARY_CATEGORY[target_group]
            if categories[0] != expected:
                errors.append(
                    f"{prefix}: first category {categories[0]!r} does not match "
                    f"target_group {target_group!r} (expected {expected!r})",
                )

        extra = set(entry.keys()) - REQUIRED_FIELDS
        if extra:
            errors.append(f"{prefix}: unexpected fields {sorted(extra)}")

    return errors


def _primary_counts(entries: list[dict]) -> Counter[str]:
    return Counter(entry["categories"][0] for entry in entries)


def _paper_ids(entries: list[dict]) -> set[str]:
    return {
        entry["paper_id"] for entry in entries if "paper_id" in entry
    }


def print_distribution(entries: list[dict]) -> None:
    label_counts: Counter[str] = Counter()
    high_counts: Counter[str] = Counter()
    primary_counts = _primary_counts(entries)
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
            for pair in combinations(
                sorted(c for c in cats if c in PRIMARY_CATEGORIES), 2
            ):
                overlap[pair] += 1

    print(f"Total entries: {len(entries)}")
    print()
    print("Primary category counts (categories[0]):")
    for cat in sorted(primary_counts):
        print(f"  {cat}: {primary_counts[cat]}")
    print()
    print("Per-label counts (any category + informational):")
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


def print_train_test_proportion_notes(
    test_entries: list[dict],
    train_entries: list[dict],
) -> None:
    if not test_entries or not train_entries:
        return

    train_primary = _primary_counts(train_entries)
    test_primary = _primary_counts(test_entries)
    categories = sorted(set(train_primary) | set(test_primary))

    for cat in categories:
        train_pct = 100.0 * train_primary[cat] / len(train_entries)
        test_pct = 100.0 * test_primary[cat] / len(test_entries)
        delta = test_pct - train_pct
        if abs(delta) > PROPORTION_TOLERANCE_PP:
            print(
                f"NOTE: {cat} primary proportion differs from train by "
                f"{delta:+.1f}pp (train {train_pct:.1f}%, test {test_pct:.1f}%)",
            )


def acceptance_errors(entries: list[dict], profile: Profile) -> list[str]:
    errors: list[str] = []

    if profile == "test":
        if len(entries) < MIN_ENTRIES_TEST:
            errors.append(f"entry count {len(entries)} < {MIN_ENTRIES_TEST}")

        primary_counts = _primary_counts(entries)
        for cat, minimum in sorted(MIN_PRIMARY_TEST.items()):
            count = primary_counts[cat]
            if count < minimum:
                errors.append(
                    f"{cat} (primary): {count} papers < {minimum}",
                )
        return errors

    if len(entries) < MIN_ENTRIES_TRAIN:
        errors.append(f"entry count {len(entries)} < {MIN_ENTRIES_TRAIN}")

    per_primary: Counter[str] = Counter()
    high_per_primary: Counter[str] = Counter()
    for entry in entries:
        for cat in set(entry["categories"]):
            if cat in PRIMARY_CATEGORIES:
                per_primary[cat] += 1
                if entry["confidence"] == "high":
                    high_per_primary[cat] += 1

    for cat in sorted(PRIMARY_CATEGORIES):
        if per_primary[cat] < MIN_PER_PRIMARY_ANY_TRAIN:
            errors.append(
                f"{cat}: {per_primary[cat]} papers < {MIN_PER_PRIMARY_ANY_TRAIN}",
            )
        if high_per_primary[cat] < MIN_PER_PRIMARY_ANY_TRAIN:
            print(
                f"NOTE: {cat} has {high_per_primary[cat]} high-confidence "
                f"labels (< {MIN_PER_PRIMARY_ANY_TRAIN}); "
                f"total labels={per_primary[cat]}",
            )

    return errors


def disjointness_errors(
    train_entries: list[dict],
    test_entries: list[dict],
) -> list[str]:
    overlap = sorted(_paper_ids(train_entries) & _paper_ids(test_entries))
    if overlap:
        return [f"train/test paper_id overlap: {overlap}"]
    return []


def validate_entries(
    entries: list[dict],
    *,
    profile: Profile,
    label: str,
    train_entries: list[dict] | None = None,
) -> list[str]:
    errors: list[str] = []

    schema_errors = validate_schema(entries)
    if schema_errors:
        errors.extend(f"{label}: {err}" for err in schema_errors)
        return errors

    print(f"=== {label} ===")
    print()
    print_distribution(entries)
    print()

    if profile == "test" and train_entries is not None:
        print_train_test_proportion_notes(entries, train_entries)
        print()

    gate_errors = acceptance_errors(entries, profile)
    if gate_errors:
        errors.extend(f"{label}: {err}" for err in gate_errors)
        return errors

    print(f"{label}: validation passed.")
    print()
    return errors


def validate_file(
    path: Path,
    *,
    profile: Profile,
    train_entries: list[dict] | None = None,
) -> tuple[list[dict], list[str]]:
    if not path.is_file():
        return [], [f"{path.name}: file not found"]

    try:
        entries = load_entries(path)
    except ValueError as exc:
        return [], [f"{path.name}: {exc}"]

    label = path.name
    errors = validate_entries(
        entries,
        profile=profile,
        label=label,
        train_entries=train_entries,
    )
    return entries, errors


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate golden paper category labels.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--train",
        action="store_true",
        help="validate the training golden only",
    )
    group.add_argument(
        "--test",
        action="store_true",
        help="validate the test golden only",
    )
    return parser.parse_args(list(argv))


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    if args.train:
        _, errors = validate_file(train_path(), profile="train")
    elif args.test:
        train_entries: list[dict] | None = None
        train_file = train_path()
        if train_file.is_file():
            try:
                loaded = load_entries(train_file)
            except ValueError:
                loaded = None
            else:
                if validate_schema(loaded):
                    loaded = None
            train_entries = loaded
        _, errors = validate_file(
            test_path(),
            profile="test",
            train_entries=train_entries,
        )
    else:
        train_entries, train_errors = validate_file(
            train_path(),
            profile="train",
        )
        test_entries, test_errors = validate_file(
            test_path(),
            profile="test",
            train_entries=train_entries if not train_errors else None,
        )
        errors = train_errors + test_errors
        errors += disjointness_errors(train_entries, test_entries)
        if not errors:
            print("Train and test paper_id sets are disjoint.")

    if errors:
        print("Validation failures:", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    print("Validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
