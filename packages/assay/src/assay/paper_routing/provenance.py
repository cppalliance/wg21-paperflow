#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Train/serve provenance for learned routing aggregators."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import sklearn

from assay.paper_routing.hypotheses import (
    SAMPLING_METHOD,
    _MAX_SENTENCES_PER_PAPER,
)


def file_sha256(path: Path) -> str:
    """Return lowercase hex SHA-256 of ``path`` contents."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit_id() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def build_provenance_record(
    *,
    per_label_thresholds_path: Path,
    feature_names_path: Path,
    git_commit_id: str | None = None,
) -> dict[str, object]:
    """Build a provenance record for a freshly trained family artifact set."""
    return {
        "sklearn_version": sklearn.__version__,
        "sampling_cap": _MAX_SENTENCES_PER_PAPER,
        "sampling_method": SAMPLING_METHOD,
        "per_label_thresholds_sha256": file_sha256(per_label_thresholds_path),
        "feature_names_sha256": file_sha256(feature_names_path),
        "git_commit": git_commit_id if git_commit_id is not None else _git_commit_id(),
    }


def validate_provenance(
    record: dict[str, object],
    *,
    provenance_path: Path,
    per_label_thresholds_path: Path,
    feature_names_path: Path,
) -> None:
    """Raise ``ValueError`` when committed provenance does not match runtime inputs."""
    expected_sklearn = sklearn.__version__
    actual_sklearn = record.get("sklearn_version")
    if actual_sklearn != expected_sklearn:
        raise ValueError(
            f"{provenance_path}: sklearn_version {actual_sklearn!r} does not match "
            f"runtime {expected_sklearn!r}; retrain the aggregator under the locked env",
        )

    expected_cap = _MAX_SENTENCES_PER_PAPER
    actual_cap = record.get("sampling_cap")
    if actual_cap != expected_cap:
        raise ValueError(
            f"{provenance_path}: sampling_cap {actual_cap!r} does not match "
            f"runtime {expected_cap!r}; retrain or update sampling constants",
        )

    expected_method = SAMPLING_METHOD
    actual_method = record.get("sampling_method")
    if actual_method != expected_method:
        raise ValueError(
            f"{provenance_path}: sampling_method {actual_method!r} does not match "
            f"runtime {expected_method!r}; retrain or update sampling constants",
        )

    expected_thresholds_hash = file_sha256(per_label_thresholds_path)
    actual_thresholds_hash = record.get("per_label_thresholds_sha256")
    if actual_thresholds_hash != expected_thresholds_hash:
        raise ValueError(
            f"{provenance_path}: per_label_thresholds_sha256 does not match "
            f"{per_label_thresholds_path}; recalibrate thresholds or retrain",
        )

    expected_feature_hash = file_sha256(feature_names_path)
    actual_feature_hash = record.get("feature_names_sha256")
    if actual_feature_hash != expected_feature_hash:
        raise ValueError(
            f"{provenance_path}: feature_names_sha256 does not match "
            f"{feature_names_path}; retrain the aggregator",
        )
