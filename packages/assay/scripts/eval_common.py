# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
"""Shared helpers for paper-routing evaluation scripts."""

from __future__ import annotations

import os
import re
from pathlib import Path

from pipeline.classifier_backends import ClassifierBackend, NliCrossEncoderBackend
from pipeline.markdown import front_matter_end_index
from pipeline.services import resolve_classifiers

from assay.paper_routing import RoutingGroup

CATEGORY_TO_GROUP: dict[str, RoutingGroup] = {
    "library-design": RoutingGroup.LEWG,
    "library-wording": RoutingGroup.LWG,
    "language-evolution": RoutingGroup.EWG,
    "language-wording": RoutingGroup.CWG,
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def assay_package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def golden_data_dir() -> Path:
    return assay_package_root() / "data" / "golden"


def paper_golden_train_path() -> Path:
    return golden_data_dir() / "paper_categories_train.jsonl"


def paper_golden_test_path() -> Path:
    return golden_data_dir() / "paper_categories_test.jsonl"


def sentence_golden_dir() -> Path:
    return golden_data_dir() / "sentence_golden"


def default_paperstore_dir() -> Path:
    data_dir = os.environ.get("WG21_DATA_DIR")
    if not data_dir:
        raise SystemExit(
            "WG21_DATA_DIR is not set and --paperstore was not provided.",
        )
    return Path(data_dir) / "paperstore"


def resolve_classifier(
    name: str,
    *,
    cpu_only: bool = False,
) -> ClassifierBackend:
    """Load one ``[classifiers.NAME]`` inventory entry for offline eval scripts."""
    resolved = resolve_classifiers(
        {"_": name},
        provider_override="cpu-fp32" if cpu_only else None,
    )
    return resolved["_"]


def resolve_nli_classifier(name: str | None) -> NliCrossEncoderBackend | None:
    if name is None:
        return None
    backend = resolve_classifier(name)
    if not isinstance(backend, NliCrossEncoderBackend):
        raise SystemExit(
            "NLI scoring requires NliCrossEncoderBackend, "
            f"got {type(backend).__name__} ({name})",
        )
    return backend


def classifier_label(
    name: str | None,
    backend: ClassifierBackend | None,
) -> str | None:
    if backend is None:
        return None
    return name or "selector default"


def expected_groups(categories: list[str] | tuple[str, ...]) -> set[RoutingGroup]:
    """Map golden content categories to expected review groups.

    ``informational`` papers expect no group. Any other unrecognized category
    is a golden-data bug, not a silently-dropped label: raise loudly.
    """
    expected: set[RoutingGroup] = set()
    for category in categories:
        if category == "informational":
            continue
        group = CATEGORY_TO_GROUP.get(category)
        if group is None:
            raise ValueError(f"Unknown category {category!r}")
        expected.add(group)
    return expected


def parse_audience_from_md(md: str) -> list[str]:
    """Extract front-matter ``audience:`` values from paper markdown."""
    lines = md.splitlines()
    end = front_matter_end_index(lines)
    if end == 0:
        return []
    audience_values: list[str] = []
    for line in lines[1:end]:
        match = re.match(r"^audience:\s*(.+)$", line.strip(), re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).strip().strip('"').strip("'")
        if value:
            audience_values.append(value)
    return audience_values
