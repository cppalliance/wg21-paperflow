#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""C-CAL: mechanical guard against a partial or inconsistent calibration promotion.

whisker's coverage gate edges (``UNIGRAM_COVERAGE_FAIL_EDGE`` /
``UNIGRAM_COVERAGE_REVIEW_EDGE`` in ``constants.py``) are PROVISIONAL today. A
future ``whisker calibrate`` run may fit real edges and a human may promote
them: commit the fitted artifact at the canonical path below AND update the
two numeric constants AND update the PROVISIONAL docstring/comment language,
all together. This module is the trip-wire that catches a PARTIAL or WRONG
promotion:

- the artifact is committed but ``constants.py`` disagrees with it (typo,
  stale artifact, promoted the wrong edge's fitted value, forgot to drop the
  PROVISIONAL language), or
- the artifact itself should never have been promoted (``edge_ordering_ok``
  is ``False``, the holdout FPR blew through its target ceiling under the
  max-tpr-at-fpr method, or the artifact's ``schema_version`` is stale).

The canonical, committed location for a promoted artifact is
``packages/whisker/corpus/calibration/thresholds.json``. It does not exist
yet (no real calibration has been run: see
``packages/whisker/corpus/calibration/PROTOCOL.md``), which is the correct
state today.

``_check_calibration_consistency`` is a pure helper (artifact dict + the two
live constant values in, a list of violation messages out) so both the
real-repo-state test and the synthetic unit tests exercise the exact same
logic.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from whisker import constants as C
from whisker.det.calibrate import (
    CALIBRATION_ARTIFACT_SCHEMA_VERSION,
    DEFAULT_TARGET_FPR_FAIL_EDGE,
    DEFAULT_TARGET_FPR_REVIEW_EDGE,
    calibrate_threshold_with_holdout,
)

_WHISKER_PKG = Path(__file__).resolve().parents[2]
_CONSTANTS_PY = _WHISKER_PKG / "src" / "whisker" / "constants.py"
_THRESHOLDS_JSON = _WHISKER_PKG / "corpus" / "calibration" / "thresholds.json"

# calibrate.py's method-name string constants (``_METHOD_AT_FPR`` /
# ``_METHOD_YOUDEN``) are module-private and not part of ``__all__``; mirrored
# here as literals, same convention as test_calibrate.py's own assertions
# (e.g. ``fit.method == "max_tpr_at_fpr"``).
_METHOD_AT_FPR = "max_tpr_at_fpr"
_METHOD_YOUDEN = "youden_j"

_FAIL_EDGE_KEY = "unigram_coverage_fail_edge"
_REVIEW_EDGE_KEY = "unigram_coverage_review_edge"

_CEILINGS = {
    _FAIL_EDGE_KEY: DEFAULT_TARGET_FPR_FAIL_EDGE,
    _REVIEW_EDGE_KEY: DEFAULT_TARGET_FPR_REVIEW_EDGE,
}


def _check_calibration_consistency(
    artifact: dict, fail_edge: float, review_edge: float
) -> list[str]:
    """Return consistency-violation messages for a promoted calibration artifact.

    ``artifact`` is a parsed calibration JSON payload shaped like
    ``calibrate_main``'s output (``schema_version``, ``edge_ordering_ok``,
    ``fitted.<edge>`` = a ``HoldoutCalibrationResult.to_dict()`` OR ``None``,
    ``not_fit_reason.<edge>`` = the exception text for a ``None`` fit).
    ``fail_edge``/``review_edge`` are the LIVE values of
    ``whisker.constants.UNIGRAM_COVERAGE_FAIL_EDGE`` /
    ``UNIGRAM_COVERAGE_REVIEW_EDGE`` to check the artifact against.

    Returns an empty list iff the artifact is internally valid (ordering,
    schema) AND numerically consistent with the two live constants. Every
    entry is a human-actionable message: what disagreed, and what to
    reconcile.

    A GENUINE partial promotion -- ``fitted.<key>`` explicitly ``None`` AND a
    non-empty ``not_fit_reason.<key>`` explaining why -- is NOT a violation:
    that edge is honestly documented as structurally unfittable (see
    ``calibrate.py``'s ``InsufficientCalibrationDataError`` and PROTOCOL.md
    section 13). A ``fitted.<key>`` that is missing ENTIRELY (the key absent
    from the dict) with no accompanying ``not_fit_reason`` remains a
    violation: that is the "silently forgot to write this edge" case this
    guard exists to catch, distinct from "deliberately, documentedly did not
    fit this edge."
    """
    violations: list[str] = []
    live_values = {_FAIL_EDGE_KEY: fail_edge, _REVIEW_EDGE_KEY: review_edge}

    schema_version = artifact.get("schema_version")
    if schema_version != CALIBRATION_ARTIFACT_SCHEMA_VERSION:
        violations.append(
            f"artifact schema_version={schema_version!r} does not match the current "
            f"whisker.det.calibrate.CALIBRATION_ARTIFACT_SCHEMA_VERSION="
            f"{CALIBRATION_ARTIFACT_SCHEMA_VERSION!r}. Re-run `whisker calibrate` with the "
            "current calibrator and regenerate the artifact before promoting it."
        )

    fitted = artifact.get("fitted", {})
    not_fit_reason = artifact.get("not_fit_reason", {})
    fitted_edges: dict[str, dict] = {}
    for key, live_value in live_values.items():
        if key not in fitted:
            violations.append(
                f"artifact fitted.{key!r} is missing entirely; cannot check it against "
                f"the live whisker.constants value {live_value!r}. If this edge was "
                "deliberately not fit (InsufficientCalibrationDataError), it must still "
                f"appear as fitted.{key!r}=None alongside a non-empty "
                f"not_fit_reason.{key!r} explaining why."
            )
            continue

        edge_fit = fitted[key]
        if edge_fit is None:
            reason = not_fit_reason.get(key)
            if isinstance(reason, str) and reason.strip():
                # A genuine, documented non-fit: nothing to check numerically
                # for this edge, and this is NOT a violation.
                continue
            violations.append(
                f"artifact fitted.{key!r} is None but not_fit_reason.{key!r} is missing "
                "or empty. A None fit must always be paired with a non-empty explanation "
                "of why that edge could not be fitted; otherwise this is indistinguishable "
                "from a silently forgotten edge."
            )
            continue

        fitted_edges[key] = edge_fit

        try:
            chosen_threshold = edge_fit["calibration"]["chosen"]["threshold"]
        except (KeyError, TypeError) as exc:
            violations.append(
                f"artifact fitted.{key}.calibration.chosen.threshold is missing or malformed "
                f"({exc!r}); expected the HoldoutCalibrationResult.to_dict() shape."
            )
            continue

        if chosen_threshold != live_value:
            violations.append(
                f"artifact fitted.{key}.calibration.chosen.threshold={chosen_threshold!r} "
                f"does not equal the live constant ({live_value!r}). The promoter copied the "
                "wrong number, promoted the wrong edge's fitted value, or constants.py is "
                "stale relative to the committed artifact (or vice versa). Reconcile the two "
                "so the constant is an exact copy of the artifact's chosen threshold."
            )

        try:
            method = edge_fit["calibration"]["method"]
        except (KeyError, TypeError) as exc:
            violations.append(
                f"artifact fitted.{key}.calibration.method is missing or malformed ({exc!r})."
            )
            continue

        if method not in (_METHOD_AT_FPR, _METHOD_YOUDEN):
            violations.append(
                f"artifact fitted.{key}.calibration.method={method!r} is not a recognized "
                f"calibration method (expected {_METHOD_AT_FPR!r} or {_METHOD_YOUDEN!r})."
            )
            continue

        try:
            holdout_fpr = edge_fit["holdout"]["fpr"]
        except (KeyError, TypeError) as exc:
            violations.append(
                f"artifact fitted.{key}.holdout.fpr is missing or malformed ({exc!r})."
            )
            continue

        if method == _METHOD_AT_FPR:
            ceiling = _CEILINGS[key]
            if holdout_fpr > ceiling:
                violations.append(
                    f"artifact fitted.{key} used method={_METHOD_AT_FPR!r} but its holdout "
                    f"fpr={holdout_fpr!r} exceeds the target ceiling {ceiling!r}. The "
                    "max-tpr-at-fpr method is only trustworthy when the calibration-split "
                    "ceiling generalizes to holdout; a breach here means the fit does not "
                    "hold up and must not be promoted as-is."
                )
        # method == _METHOD_YOUDEN: exceeding the ceiling is calibrate.py's documented,
        # expected escape hatch (module docstring: "falling back to the Youden-J
        # maximizer when no threshold meets the ceiling"), so no ceiling assertion here.
        # The `method not in (...)` check above already guarantees this branch's use of
        # Youden is recorded on the artifact, which is what keeps the escape hatch
        # auditable rather than a silent bypass.

    # edge_ordering_ok is only DEFINED when both edges actually fitted; with a
    # genuine partial promotion (one edge documented-not-fit) there is nothing
    # to compare, and `calibrate_main` correctly emits `None` for it, which
    # must NOT be flagged as a violation.
    if len(fitted_edges) == len(live_values):
        edge_ordering_ok = artifact.get("edge_ordering_ok")
        if edge_ordering_ok is not True:
            violations.append(
                f"artifact edge_ordering_ok={edge_ordering_ok!r}, expected True when both "
                "edges are fitted. A fitted fail edge above the review edge is an "
                "inverted, meaningless band and must never be promoted as-is (see "
                "det.cli.calibrate_main's warning on this condition)."
            )

    return violations


def _read_constants_source() -> str:
    return _CONSTANTS_PY.read_text(encoding="utf-8")


def _coverage_edge_comment_block(source: str) -> dict[str, str]:
    """The two INDIVIDUALLY-marked coverage-edge comment blocks, one per constant.

    Each edge carries its own "# FAIL_EDGE: ..." / "# REVIEW_EDGE: ..." marker
    line directly above its constant in constants.py (see the block comment
    there), so a genuine partial promotion -- one edge calibrated, the other
    still provisional -- can be checked independently PER EDGE instead of as
    one glued-together PROVISIONAL flag shared by both. Scoped narrowly to
    each marker's own lines (not the whole shared rationale block above them,
    and not the whole file) so a stray mention of "PROVISIONAL" elsewhere in
    constants.py (e.g. the benchmark-floor section, intentionally still
    provisional per this task's scope) can never mask a promotion of either
    unigram coverage edge specifically.

    Returns ``{"not-llm-readable": <block text>, "review": <block text>}``, each spanning
    from its own marker line through its own constant's assignment line.
    """
    markers = {
        "not-llm-readable": ("# FAIL_EDGE:", "UNIGRAM_COVERAGE_FAIL_EDGE"),
        "review": ("# REVIEW_EDGE:", "UNIGRAM_COVERAGE_REVIEW_EDGE"),
    }
    blocks: dict[str, str] = {}
    for name, (start_marker, end_marker) in markers.items():
        start = source.index(start_marker)
        end = source.index(end_marker, start)
        end = source.index("\n", end) + 1
        blocks[name] = source[start:end]
    return blocks


# -- Case 1: today's baseline / general "no silent partial promotion" guard --


_EDGE_KEY_BY_BLOCK_NAME = {"not-llm-readable": _FAIL_EDGE_KEY, "review": _REVIEW_EDGE_KEY}


def test_artifact_presence_and_provisional_language_stay_in_lockstep():
    """PER EDGE: an edge's PROVISIONAL marker survives iff that edge was never fitted.

    No artifact committed => BOTH edges' comment blocks still say PROVISIONAL,
    unconditionally (today's baseline state). If an artifact IS committed, a
    real partial promotion is now a valid state (see PROTOCOL.md section 13:
    the fail edge is structurally unfittable on this corpus while the review
    edge is not), so the check degrades to PER EDGE: an edge whose
    ``fitted.<key>`` is present (not ``None``) in the committed artifact must
    have DROPPED its own PROVISIONAL marker (a genuine promotion happened for
    THAT edge); an edge whose ``fitted.<key>`` is ``None`` (a documented
    non-fit) must have KEPT its own PROVISIONAL marker. What this test alone
    catches is a PARTIAL DOCUMENTATION mismatch on a single edge: that edge's
    fit landed without its own docstring update, or its docstring was
    "cleaned up" to drop PROVISIONAL without a real fit for THAT edge ever
    landing.
    """
    blocks = _coverage_edge_comment_block(_read_constants_source())

    if not _THRESHOLDS_JSON.exists():
        for block_name, block in blocks.items():
            assert "PROVISIONAL" in block, (
                f"No {_THRESHOLDS_JSON} exists, but the {block_name} edge's comment "
                f"block in {_CONSTANTS_PY} already dropped PROVISIONAL. A promotion "
                "must be backed by a committed calibration artifact for that edge."
            )
        return

    artifact = json.loads(_THRESHOLDS_JSON.read_text(encoding="utf-8"))
    fitted = artifact.get("fitted", {})
    for block_name, block in blocks.items():
        edge_key = _EDGE_KEY_BY_BLOCK_NAME[block_name]
        was_fitted = fitted.get(edge_key) is not None
        still_provisional = "PROVISIONAL" in block

        assert was_fitted != still_provisional, (
            f"Inconsistent promotion state for {edge_key}: fitted={was_fitted!r} in "
            f"{_THRESHOLDS_JSON}, but its comment block in {_CONSTANTS_PY} still says "
            f"PROVISIONAL={still_provisional!r}. A promotion must be all-or-nothing PER "
            "EDGE: commit the calibration artifact's fit for this edge AND remove the "
            "PROVISIONAL language from this edge's own comment block, in the same "
            "change. Reconcile by either restoring PROVISIONAL (if this edge's fit was "
            "removed/never real) or updating this edge's docstring (if it is a "
            "genuine, valid promotion)."
        )


# -- Case 2: conditional deep-consistency check, gated on the artifact existing --


@pytest.mark.skipif(
    not _THRESHOLDS_JSON.exists(),
    reason=f"no promoted calibration artifact at {_THRESHOLDS_JSON} yet",
)
def test_committed_artifact_matches_live_constants():
    artifact = json.loads(_THRESHOLDS_JSON.read_text(encoding="utf-8"))

    violations = _check_calibration_consistency(
        artifact, C.UNIGRAM_COVERAGE_FAIL_EDGE, C.UNIGRAM_COVERAGE_REVIEW_EDGE
    )
    assert not violations, (
        f"{_THRESHOLDS_JSON} is inconsistent with the live constants in constants.py:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )

    blocks = _coverage_edge_comment_block(_read_constants_source())
    fitted = artifact.get("fitted", {})
    for block_name, block in blocks.items():
        edge_key = _EDGE_KEY_BY_BLOCK_NAME[block_name]
        was_fitted = fitted.get(edge_key) is not None
        still_provisional = "PROVISIONAL" in block
        if was_fitted:
            assert not still_provisional, (
                f"{_THRESHOLDS_JSON} has a real fit for {edge_key}, but its comment "
                f"block in {_CONSTANTS_PY} still contains the word PROVISIONAL. "
                "Promotion requires updating that edge's documentation, not just its "
                "numeric constant: rewrite that edge's comment block to describe the "
                "calibrated, non-provisional state."
            )
        else:
            assert still_provisional, (
                f"{_THRESHOLDS_JSON} documents {edge_key} as NOT fitted "
                f"(fitted.{edge_key} is None), but its comment block in "
                f"{_CONSTANTS_PY} dropped the word PROVISIONAL. An edge that was "
                "never actually fitted must keep its PROVISIONAL marker."
            )


# -- Case 3: synthetic unit tests for `_check_calibration_consistency` itself --


def _synthetic_edge_fit(name: str, *, target_fpr: float):
    """A real ``HoldoutCalibrationResult`` on cleanly separable synthetic data.

    Guarantees the shape used below is exactly what ``calibrate.py`` produces
    (never hand-typed), while keeping the numbers predictable: bad papers
    cluster at 0.50, good papers at 0.95, both splits identical, so the fit is
    perfectly separable and deterministic across calibration and holdout.
    """
    calibration = [(0.50, True, "calibration")] * 5 + [(0.95, False, "calibration")] * 5
    holdout = [(0.50, True, "holdout")] * 5 + [(0.95, False, "holdout")] * 5
    return calibrate_threshold_with_holdout(
        calibration + holdout, name=name, target_fpr=target_fpr
    )


def _fake_consistent_artifact() -> tuple[dict, float, float]:
    """A fake artifact dict, built from real fits, that is fully self-consistent."""
    fail_fit = _synthetic_edge_fit(_FAIL_EDGE_KEY, target_fpr=DEFAULT_TARGET_FPR_FAIL_EDGE)
    review_fit = _synthetic_edge_fit(_REVIEW_EDGE_KEY, target_fpr=DEFAULT_TARGET_FPR_REVIEW_EDGE)
    fail_edge = fail_fit.calibration.chosen.threshold
    review_edge = review_fit.calibration.chosen.threshold
    artifact = {
        "schema_version": CALIBRATION_ARTIFACT_SCHEMA_VERSION,
        "kind": "whisker-calibration",
        "n": 20,
        "edge_ordering_ok": fail_edge <= review_edge,
        "fitted": {
            _FAIL_EDGE_KEY: fail_fit.to_dict(),
            _REVIEW_EDGE_KEY: review_fit.to_dict(),
        },
    }
    return artifact, fail_edge, review_edge


def test_consistent_artifact_has_no_violations():
    artifact, fail_edge, review_edge = _fake_consistent_artifact()
    assert _check_calibration_consistency(artifact, fail_edge, review_edge) == []


def test_mismatched_fail_edge_value_is_flagged():
    artifact, fail_edge, review_edge = _fake_consistent_artifact()
    wrong_fail_edge = fail_edge + 0.01  # simulate a typo / stale promotion

    violations = _check_calibration_consistency(artifact, wrong_fail_edge, review_edge)

    assert violations, "expected a violation for a mismatched fail-edge constant"
    assert any(
        _FAIL_EDGE_KEY in v and "does not equal" in v for v in violations
    ), violations


def test_inverted_edge_ordering_is_flagged():
    artifact, fail_edge, review_edge = _fake_consistent_artifact()
    artifact["edge_ordering_ok"] = False

    violations = _check_calibration_consistency(artifact, fail_edge, review_edge)

    assert violations, "expected a violation for edge_ordering_ok=False"
    assert any("edge_ordering_ok" in v for v in violations), violations


def test_wrong_schema_version_is_flagged():
    artifact, fail_edge, review_edge = _fake_consistent_artifact()
    artifact["schema_version"] = CALIBRATION_ARTIFACT_SCHEMA_VERSION + 1

    violations = _check_calibration_consistency(artifact, fail_edge, review_edge)

    assert violations, "expected a violation for a schema_version mismatch"
    assert any("schema_version" in v for v in violations), violations


def test_holdout_fpr_ceiling_breach_under_at_fpr_method_is_flagged():
    """A drifted holdout set: the calibration-split fit satisfies its own ceiling,
    but the SAME frozen threshold blows the ceiling on holdout data drawn from an
    overlapping distribution. This is exactly the real-world drift the ceiling
    check exists to catch, and it must not slip through as "method matched, so
    it's fine"."""
    calibration = [(0.50, True, "calibration")] * 5 + [(0.95, False, "calibration")] * 5
    holdout = [(0.50, True, "holdout")] * 5 + [(0.60, False, "holdout")] * 5
    fail_fit = calibrate_threshold_with_holdout(
        calibration + holdout, name=_FAIL_EDGE_KEY, target_fpr=DEFAULT_TARGET_FPR_FAIL_EDGE
    )
    assert fail_fit.calibration.method == _METHOD_AT_FPR  # sanity: exercising the right branch
    assert fail_fit.holdout.fpr > DEFAULT_TARGET_FPR_FAIL_EDGE  # sanity: the breach is real

    review_fit = _synthetic_edge_fit(_REVIEW_EDGE_KEY, target_fpr=DEFAULT_TARGET_FPR_REVIEW_EDGE)
    fail_edge = fail_fit.calibration.chosen.threshold
    review_edge = review_fit.calibration.chosen.threshold
    artifact = {
        "schema_version": CALIBRATION_ARTIFACT_SCHEMA_VERSION,
        "edge_ordering_ok": fail_edge <= review_edge,
        "fitted": {
            _FAIL_EDGE_KEY: fail_fit.to_dict(),
            _REVIEW_EDGE_KEY: review_fit.to_dict(),
        },
    }

    violations = _check_calibration_consistency(artifact, fail_edge, review_edge)

    assert violations, "expected a violation for a holdout FPR ceiling breach"
    assert any("exceeds the target ceiling" in v for v in violations), violations


def test_youden_fallback_is_exempt_from_the_fpr_ceiling_but_stays_auditable():
    """The Youden-J fallback is calibrate.py's documented escape hatch for when no
    threshold meets the FPR ceiling on the calibration split; exceeding the
    ceiling under THAT method is expected, not a violation.

    Note: at any valid ``target_fpr >= 0`` the smallest candidate threshold always
    yields ``tpr=fpr=0`` (nothing is flagged), which is always <= any non-negative
    ceiling; empirically (and by inspection of ``calibrate_threshold``) this makes
    the ``feasible`` list non-empty in every real invocation, so
    ``calibrate_threshold_with_holdout`` never actually SELECTS the Youden branch
    through its public API. To test the guard's exemption logic regardless, this
    overrides the ``method``/holdout-``fpr`` fields on a real, correctly-shaped
    ``to_dict()`` output rather than hand-typing a fake shape from scratch.
    """
    artifact, fail_edge, review_edge = _fake_consistent_artifact()
    artifact["fitted"][_FAIL_EDGE_KEY]["calibration"]["method"] = _METHOD_YOUDEN
    artifact["fitted"][_FAIL_EDGE_KEY]["holdout"]["fpr"] = 0.9  # far over the 0.05 ceiling

    violations = _check_calibration_consistency(artifact, fail_edge, review_edge)

    assert violations == [], (
        "a Youden-fallback fit must not be flagged for exceeding the FPR ceiling: " + str(violations)
    )


# -- Case 4: genuine partial promotion (one edge fitted, one documented non-fit) --


def test_documented_partial_fit_has_no_violations():
    """A genuine partial promotion: only the review edge fitted, the fail edge
    explicitly documented as unfittable (PROTOCOL.md section 13's finding).
    ``edge_ordering_ok`` is correctly ``None`` (nothing to compare). This must
    be a fully valid, zero-violation state -- the entire point of this task.
    """
    review_fit = _synthetic_edge_fit(_REVIEW_EDGE_KEY, target_fpr=DEFAULT_TARGET_FPR_REVIEW_EDGE)
    review_edge = review_fit.calibration.chosen.threshold
    fail_edge = 0.85  # live constant stays untouched; nothing to compare it against

    artifact = {
        "schema_version": CALIBRATION_ARTIFACT_SCHEMA_VERSION,
        "kind": "whisker-calibration",
        "n": 10,
        "edge_ordering_ok": None,
        "fitted": {
            _FAIL_EDGE_KEY: None,
            _REVIEW_EDGE_KEY: review_fit.to_dict(),
        },
        "not_fit_reason": {
            _FAIL_EDGE_KEY: (
                "calibration split has only 2 positive (bad) example(s); need at "
                "least 5 per class per split"
            ),
        },
    }

    assert _check_calibration_consistency(artifact, fail_edge, review_edge) == []


def test_missing_fitted_key_without_not_fit_reason_is_still_flagged():
    """Regression guard: an edge whose ``fitted.<key>`` is missing ENTIRELY (no
    key at all, not even an explicit ``None``) and carries no ``not_fit_reason``
    must remain a violation. This is the "silently forgot to write this edge"
    case, distinct from the deliberately-documented non-fit in the test above,
    and the previous (pre-partial-promotion) behavior must not regress.
    """
    review_fit = _synthetic_edge_fit(_REVIEW_EDGE_KEY, target_fpr=DEFAULT_TARGET_FPR_REVIEW_EDGE)
    review_edge = review_fit.calibration.chosen.threshold
    fail_edge = 0.85

    artifact = {
        "schema_version": CALIBRATION_ARTIFACT_SCHEMA_VERSION,
        "kind": "whisker-calibration",
        "n": 10,
        "edge_ordering_ok": None,
        "fitted": {
            # _FAIL_EDGE_KEY intentionally absent entirely, and no
            # not_fit_reason entry either.
            _REVIEW_EDGE_KEY: review_fit.to_dict(),
        },
    }

    violations = _check_calibration_consistency(artifact, fail_edge, review_edge)

    assert violations, "expected a violation for a silently missing fitted key"
    assert any(
        _FAIL_EDGE_KEY in v and "missing entirely" in v for v in violations
    ), violations


def test_none_fit_without_not_fit_reason_is_flagged():
    """An explicit ``None`` fit with NO explanation is also a violation: the
    ``not_fit_reason`` pairing is mandatory, not optional, for a documented
    non-fit to be trusted.
    """
    review_fit = _synthetic_edge_fit(_REVIEW_EDGE_KEY, target_fpr=DEFAULT_TARGET_FPR_REVIEW_EDGE)
    review_edge = review_fit.calibration.chosen.threshold
    fail_edge = 0.85

    artifact = {
        "schema_version": CALIBRATION_ARTIFACT_SCHEMA_VERSION,
        "edge_ordering_ok": None,
        "fitted": {
            _FAIL_EDGE_KEY: None,
            _REVIEW_EDGE_KEY: review_fit.to_dict(),
        },
        "not_fit_reason": {},  # empty: no explanation recorded
    }

    violations = _check_calibration_consistency(artifact, fail_edge, review_edge)

    assert violations, "expected a violation for a None fit with no recorded reason"
    assert any(_FAIL_EDGE_KEY in v and "missing or empty" in v for v in violations), violations


def test_edge_ordering_ok_none_is_not_flagged_when_one_edge_is_unfit():
    """The pre-existing ``edge_ordering_ok is not True`` check must NOT fire when
    one edge is a documented non-fit (``edge_ordering_ok`` correctly ``None``
    in that case): there is nothing to order, so ``None`` is the right answer,
    not a violation.
    """
    review_fit = _synthetic_edge_fit(_REVIEW_EDGE_KEY, target_fpr=DEFAULT_TARGET_FPR_REVIEW_EDGE)
    review_edge = review_fit.calibration.chosen.threshold
    fail_edge = 0.85

    artifact = {
        "schema_version": CALIBRATION_ARTIFACT_SCHEMA_VERSION,
        "edge_ordering_ok": None,
        "fitted": {
            _FAIL_EDGE_KEY: None,
            _REVIEW_EDGE_KEY: review_fit.to_dict(),
        },
        "not_fit_reason": {_FAIL_EDGE_KEY: "structurally unfittable on this corpus"},
    }

    violations = _check_calibration_consistency(artifact, fail_edge, review_edge)

    assert not any("edge_ordering_ok" in v for v in violations), violations
