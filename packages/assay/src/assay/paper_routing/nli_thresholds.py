#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Load per-label NLI decision thresholds from package data."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_ROUTING_NLI_THRESHOLD_FALLBACK = 0.9
_NLI_DATA_DIR = Path("data") / "nli"
_THRESHOLDS_REL = _NLI_DATA_DIR / "per_label_thresholds.json"


def _assay_package_root() -> Path:
    here = Path(__file__).resolve()
    src_layout = here.parents[3]
    if (src_layout / "data").is_dir():
        return src_layout
    return here.parents[1]


def thresholds_path() -> Path:
    return _assay_package_root() / _THRESHOLDS_REL


@lru_cache(maxsize=1)
def load_nli_hypothesis_thresholds() -> dict[str, float]:
    """Return per-label thresholds keyed by hypothesis id."""
    path = thresholds_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"nli per-label thresholds missing at {path}; "
            "expected packages/assay/data/nli/per_label_thresholds.json",
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


def nli_threshold_for_label(hyp_id: str) -> float:
    thresholds = load_nli_hypothesis_thresholds()
    return thresholds.get(hyp_id, _ROUTING_NLI_THRESHOLD_FALLBACK)
