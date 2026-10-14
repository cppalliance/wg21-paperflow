"""Structural golden gate: tomd output must not regress below committed baselines.

Compares tomd's conversion against BLESSED IDEAL goldens (`<stem>.ideal.md`),
not snapshots of tomd's own output. Each baseline in baselines.json is the
current distance from tomd to the ideal; the gate fails if any axis drops
below it. Byte-exact snapshot fidelity is covered separately by
test_pdf_golden and test_html_golden.
"""

import json
from pathlib import Path

import pytest
from whisker.det.golden_qa import find_source, is_unedited_seed, score_stem

_GOLDEN = Path(__file__).resolve().parents[3] / "tomd" / "tests" / "fixtures" / "golden"
_BASELINES = json.loads((_GOLDEN / "baselines.json").read_text(encoding="utf-8"))

_EPSILON = 1e-9


@pytest.mark.parametrize("stem", sorted(_BASELINES))
def test_tomd_meets_golden_baseline(stem: str):
    try:
        scores = score_stem(stem, _GOLDEN)
    except FileNotFoundError:
        pytest.skip(f"missing source for {stem}")
    baseline = _BASELINES[stem]
    regressions = {
        axis: (scores[axis], base)
        for axis, base in baseline.items()
        if scores[axis] < base - _EPSILON
    }
    assert not regressions, (
        f"{stem} regressed below baseline: "
        + "; ".join(f"{ax}: {got:.4f} < {base:.4f}"
                    for ax, (got, base) in regressions.items())
    )


@pytest.mark.parametrize("stem", sorted(_BASELINES))
def test_ideal_is_corrected_not_raw_seed(stem: str):
    if find_source(stem, _GOLDEN) is None:
        pytest.skip(f"missing source for {stem}")
    assert not is_unedited_seed(stem, _GOLDEN), (
        f"{stem}: ideal is byte-identical to tomd's conversion (an uncorrected "
        "seed). Correct its structure against the source, then rebless."
    )
