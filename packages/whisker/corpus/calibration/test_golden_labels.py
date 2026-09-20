#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

import sys
from pathlib import Path

from whisker.golden_ideals import IdealPanel

_CALIBRATION_DIR = Path(__file__).resolve().parent
if str(_CALIBRATION_DIR) not in sys.path:
    sys.path.insert(0, str(_CALIBRATION_DIR))

from golden_labels import (  # noqa: E402
    GOLDEN_LABEL_BAD,
    GOLDEN_LABEL_GOOD,
    GOLDEN_LABEL_REVIEW,
    GOLDEN_RECALL_BAD_EDGE,
    GOLDEN_RECALL_GOOD_EDGE,
    GoldenLabel,
    label_from_ideal_panel,
)


def _panel(recall, nid=0.5, **structural):
    """Build an IdealPanel with a given recall/nid and optional structural axes.

    Structural axes default to None (ineligible); overridable per test to
    prove they never influence the label.
    """
    defaults = {
        "teds": None,
        "mhs": None,
        "block_agreement": None,
        "structural_parity": None,
        "heading_level_parity": None,
    }
    defaults.update(structural)
    return IdealPanel(nid=nid, recall=recall, overall=nid, **defaults)


# -- threshold behavior --------------------------------------------------------

def test_high_recall_is_good():
    result = label_from_ideal_panel(_panel(recall=0.95))
    assert result.label == GOLDEN_LABEL_GOOD


def test_good_edge_is_inclusive_good():
    # recall == GOLDEN_RECALL_GOOD_EDGE (0.90) exactly must be "good" (>=).
    result = label_from_ideal_panel(_panel(recall=GOLDEN_RECALL_GOOD_EDGE))
    assert result.label == GOLDEN_LABEL_GOOD


def test_just_under_good_edge_is_review():
    result = label_from_ideal_panel(_panel(recall=0.8999))
    assert result.label == GOLDEN_LABEL_REVIEW


def test_bad_edge_is_review_not_bad():
    # recall == GOLDEN_RECALL_BAD_EDGE (0.70) exactly must be "review", since
    # the bad comparison is strict (<), not "bad".
    result = label_from_ideal_panel(_panel(recall=GOLDEN_RECALL_BAD_EDGE))
    assert result.label == GOLDEN_LABEL_REVIEW


def test_just_under_bad_edge_is_bad():
    result = label_from_ideal_panel(_panel(recall=0.6999))
    assert result.label == GOLDEN_LABEL_BAD


# -- regression anchors on real measured recall values -------------------------

def test_p1068r11_markitdown_recall_is_bad():
    result = label_from_ideal_panel(_panel(recall=0.261))
    assert result.label == GOLDEN_LABEL_BAD


def test_p0533r9_tomd_recall_is_review():
    result = label_from_ideal_panel(_panel(recall=0.839))
    assert result.label == GOLDEN_LABEL_REVIEW


def test_p3411r5_p4182r0_tomd_recall_is_good():
    result = label_from_ideal_panel(_panel(recall=1.000))
    assert result.label == GOLDEN_LABEL_GOOD


# -- determinism ---------------------------------------------------------------

def test_label_is_deterministic_across_repeated_calls():
    panel = _panel(recall=0.75)
    first = label_from_ideal_panel(panel)
    second = label_from_ideal_panel(panel)
    assert first == second


# -- construct validity: structural axes must NEVER influence the label -------

def test_identical_recall_with_opposite_structural_axes_yields_same_label():
    # Negative control. This test exists to catch accidental coupling to the
    # structural axes (teds/mhs/block_agreement/structural_parity/
    # heading_level_parity): two panels share the SAME recall (0.50, clearly
    # in the "bad" band) but have maximally opposite structural scores (all
    # perfect vs all zero/None). If the label ever starts consulting a
    # structural axis, this test must fail.
    perfect_structure = _panel(
        recall=0.50,
        teds=1.0,
        mhs=1.0,
        block_agreement=1.0,
        structural_parity=1.0,
        heading_level_parity=1.0,
    )
    broken_structure = _panel(
        recall=0.50,
        teds=0.0,
        mhs=0.0,
        block_agreement=0.0,
        structural_parity=None,
        heading_level_parity=None,
    )
    result_perfect = label_from_ideal_panel(perfect_structure)
    result_broken = label_from_ideal_panel(broken_structure)
    assert result_perfect.label == GOLDEN_LABEL_BAD
    assert result_broken.label == GOLDEN_LABEL_BAD
    assert result_perfect.label == result_broken.label


def test_nid_does_not_influence_label_but_is_carried_as_evidence():
    # Same recall (good band), two very different nid values: the label must
    # stay identical, but the GoldenLabel.nid field must reflect whichever
    # nid was actually passed in (companion evidence, not decision input).
    low_nid = label_from_ideal_panel(_panel(recall=0.95, nid=0.1))
    high_nid = label_from_ideal_panel(_panel(recall=0.95, nid=0.99))
    assert low_nid.label == GOLDEN_LABEL_GOOD
    assert high_nid.label == GOLDEN_LABEL_GOOD
    assert low_nid.label == high_nid.label
    assert low_nid.nid == 0.1
    assert high_nid.nid == 0.99


# -- field fidelity --------------------------------------------------------------

def test_result_recall_matches_input_recall_exactly():
    result = label_from_ideal_panel(_panel(recall=0.8231))
    assert result.recall == 0.8231


def test_golden_label_is_a_frozen_dataclass_instance():
    result = label_from_ideal_panel(_panel(recall=0.95))
    assert isinstance(result, GoldenLabel)
