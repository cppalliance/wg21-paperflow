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

from calibrate_seqcls_thresholds import best_threshold_for_label  # noqa: E402


def test_best_threshold_regression_guard() -> None:
    probs = [0.9, 0.1, 0.8, 0.2, 0.85]
    golds = [True, False, True, False, True]
    result = best_threshold_for_label(probs, golds, min_support=1)
    assert 0.0 < result.threshold < 1.0
    assert result.support == 3
