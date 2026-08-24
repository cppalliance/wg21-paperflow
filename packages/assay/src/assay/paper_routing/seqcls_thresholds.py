#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Load per-label seqcls decision thresholds from package data."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from assay.paper_routing.artifact_names import PER_LABEL_THRESHOLDS_FILE, SEQCLS_FAMILY_DIR

_ROUTING_SEQCLS_THRESHOLD_FALLBACK = 0.25
_THRESHOLDS_REL = SEQCLS_FAMILY_DIR / PER_LABEL_THRESHOLDS_FILE


def _assay_package_root() -> Path:
    here = Path(__file__).resolve()
    src_layout = here.parents[3]
    if (src_layout / "data").is_dir():
        return src_layout
    return here.parents[1]


def thresholds_path() -> Path:
    return _assay_package_root() / _THRESHOLDS_REL


@lru_cache(maxsize=1)
def load_seqcls_hypothesis_thresholds() -> dict[str, float]:
    """Return per-label thresholds keyed by hypothesis id."""
    path = thresholds_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"seqcls per-label thresholds missing at {path}; "
            f"expected packages/assay/{SEQCLS_FAMILY_DIR / PER_LABEL_THRESHOLDS_FILE}",
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected JSON object")
    out: dict[str, float] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, (int, float)):
            raise ValueError(f"{path}: invalid entry {key!r}: {value!r}")
        out[key] = float(value)
    return out


def seqcls_threshold_for_label(hyp_id: str) -> float:
    thresholds = load_seqcls_hypothesis_thresholds()
    return thresholds.get(hyp_id, _ROUTING_SEQCLS_THRESHOLD_FALLBACK)
