# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
"""Shared helpers for paper-routing evaluation scripts."""

from __future__ import annotations

import os
from pathlib import Path

from pipeline.classifier_backends import ClassifierBackend, NliCrossEncoderBackend
from pipeline.services import (
    load_classifier,
    load_transformer_providers,
    resolve_transformer_provider,
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def assay_package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def golden_data_dir() -> Path:
    return assay_package_root() / "data" / "golden"


def paper_golden_path() -> Path:
    return golden_data_dir() / "paper_categories.jsonl"


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
    provider = None
    if cpu_only:
        providers, defaults = load_transformer_providers()
        provider = resolve_transformer_provider(
            providers,
            defaults,
            override="cpu-fp32",
        )
    return load_classifier(name, provider=provider)


def resolve_nli_classifier(name: str | None) -> NliCrossEncoderBackend | None:
    if name is None:
        return None
    backend = load_classifier(name)
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
