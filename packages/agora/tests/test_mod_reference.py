#
# Copyright (c) 2026 Glenn Siegman (glenn@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the-mod.md excerpt slicing (mod_reference)."""

from __future__ import annotations

import pytest

from agora import mod_reference


def test_document_loads_from_package_data():
    text = mod_reference._document()
    assert "# The Mod" in text
    assert "Table C: Domain" in text


def test_unknown_heading_raises():
    with pytest.raises(KeyError):
        mod_reference._section("99. No Such Section")


def test_missing_block_marker_raises():
    with pytest.raises(KeyError):
        mod_reference._block("2. The Heat Check", "**no such marker**", "**2.1e")


def test_section_stops_at_next_heading():
    body = mod_reference._section("2. The Heat Check")
    assert body.startswith("### 2. The Heat Check")
    assert "2.4 Interest tier" in body
    assert "The Submission Post" not in body


def test_smell_test_excerpts_carry_anchor_filters():
    text = mod_reference.smell_test_excerpts()
    assert "1.4c Falsification requirement" in text
    assert "1.4d Anchor priority routing" in text
    assert "2.1b Paper type" in text
    assert "2.1d Process document classification" in text


def test_calibrate_excerpts_carry_tiers_and_architecture():
    text = mod_reference.calibrate_excerpts()
    assert "2.1e Author gravity" in text
    assert "2.3 Heat tier" in text
    assert "2.4 Interest tier" in text
    assert "### 4. Thread Architecture" in text


def test_submission_excerpts_carry_update_thread_rules():
    text = mod_reference.submission_excerpts()
    assert text.startswith("### 3. The Submission Post")
    assert "Update-thread rules" in text


def test_skeleton_excerpts_carry_table_c_and_noise_palette():
    text = mod_reference.skeleton_excerpts()
    assert "Table C: Domain" in text
    assert "Committee process" in text
    assert "Stock phrases" in text
    assert "5b. Mod Presence" in text
    assert "1.4d Anchor priority routing" in text
    # Tables A/B/D are generation-phase material; the planner slice
    # must stop at Table C.
    assert "Table D" not in text
    assert "Table A: Voice" not in text


def test_encounters_excerpts_carry_shape_rules():
    text = mod_reference.encounters_excerpts()
    assert text.startswith("### 11. The Encounter")
    assert "Never more than 5 exchanges" in text
