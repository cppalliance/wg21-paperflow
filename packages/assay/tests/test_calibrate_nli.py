#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from calibrate_nli_thresholds import calibrate  # noqa: E402


def test_calibrate_nli_keeps_default_when_support_low() -> None:
    rows = [
        {"probs": {"W1": 0.99}, "labels": ["W1"]},
        {"probs": {"W1": 0.01}, "labels": []},
    ]
    result = calibrate(rows)["W1"]
    assert result.threshold == 0.9
    assert result.calibrated is False
    assert result.support == 1


def test_calibrate_nli_raises_threshold_when_negatives_sit_below_it() -> None:
    rows: list[dict[str, object]] = []
    for _ in range(30):
        rows.append({"probs": {"W1": 0.95}, "labels": ["W1"]})
    for _ in range(30):
        rows.append({"probs": {"W1": 0.92}, "labels": []})
    result = calibrate(rows)["W1"]
    assert result.threshold > 0.9
    assert result.calibrated is True
    assert result.support == 30
