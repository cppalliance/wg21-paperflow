#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from pathlib import Path
from types import SimpleNamespace

from whisker.det.score import VERDICT_PASS, VERDICT_REVIEW, score_markdown
from whisker.golden_ideals import (
    IDEAL_STATUS_ABSENT,
    IDEAL_STATUS_PRESENT,
    IDEAL_STATUS_UNAVAILABLE,
    find_ideals_dir,
    ideal_path,
    list_ideal_stems,
    resolve_ideal,
    score_against_ideal,
)

_CLEAN_MD = """---
title: "A Paper"
document: P1234R0
---

## Introduction

This is a faithful paragraph of prose that the source also contains.

## Design

More prose describing the design in plain words.
"""

# Shares almost no words with _CLEAN_MD: nid lands well below NID_FLOOR.
_DIVERGENT_MD = "## Totally\n\nDifferent alien words sharing nothing alike zzz qqq.\n" * 3


def _content(coverage):
    return SimpleNamespace(
        source_format="pdf",
        coverage=coverage,
        drift=0.0,
        unigram_coverage=coverage,
        unigram_drift=0.0,
        missing_regions=(),
        extra_regions=(),
    )


# -- discovery ---------------------------------------------------------------

def test_find_ideals_dir_locates_repo_fixture():
    # whisker's own source lives inside the workspace checkout, so walking up
    # from golden_ideals.py must find tomd's committed ideals directory.
    found = find_ideals_dir()
    assert found is not None
    assert found.name == "ideals"
    assert (found.parent.name, found.parent.parent.name) == ("golden", "fixtures")


def test_p4020_ideal_is_discovered_case_insensitively():
    found = find_ideals_dir()

    assert found is not None
    resolved = ideal_path("P4020R0", found)
    assert resolved is not None
    assert resolved.stem.lower() == "p4020r0"


def test_find_ideals_dir_returns_none_outside_any_repo(tmp_path, monkeypatch):
    # With cwd outside a checkout the source-file walk still wins; simulate a
    # world with no ideals by pointing the relpath at a name that never exists.
    import whisker.golden_ideals as gi

    monkeypatch.setattr(gi, "_IDEALS_RELPATH", Path("no-such-dir-xyz"))
    assert gi.find_ideals_dir(start=tmp_path) is None


def test_ideal_path_is_case_insensitive_on_pid(tmp_path):
    (tmp_path / "p1234r0.md").write_text("x", encoding="utf-8")
    assert ideal_path("P1234R0", tmp_path) == tmp_path / "p1234r0.md"
    assert ideal_path(" p1234r0 ", tmp_path) == tmp_path / "p1234r0.md"
    assert ideal_path("P9999R9", tmp_path) is None


def test_ideal_path_matches_uppercase_filename(tmp_path):
    # An ideal accidentally committed with uppercase casing must still resolve
    # on case-sensitive filesystems (the lookup scans stems, not literal paths).
    (tmp_path / "P5678R0.md").write_text("x", encoding="utf-8")
    assert ideal_path("p5678r0", tmp_path) == tmp_path / "P5678R0.md"
    assert list_ideal_stems(tmp_path) == ["p5678r0"]


def test_list_ideal_stems_sorted(tmp_path):
    for name in ("p4228r0.md", "cwg1.md", "p4182r0.md", "notes.txt"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    assert list_ideal_stems(tmp_path) == ["cwg1", "p4182r0", "p4228r0"]


# -- availability status (M1 audit: unavailable vs absent) -------------------

def test_resolve_ideal_unavailable_when_dir_missing():
    # No ideals_dir at all (e.g. an installed wheel with no workspace checkout
    # on disk): the lane cannot be evaluated, distinct from "evaluated, found
    # nothing".
    md, status = resolve_ideal("P1234R0", None)
    assert md is None
    assert status == IDEAL_STATUS_UNAVAILABLE


def test_resolve_ideal_absent_when_pid_missing(tmp_path):
    # ideals_dir exists and is reachable, but this pid has no ideal file yet.
    md, status = resolve_ideal("P9999R9", tmp_path)
    assert md is None
    assert status == IDEAL_STATUS_ABSENT


def test_resolve_ideal_present_when_file_exists(tmp_path):
    (tmp_path / "p1234r0.md").write_text("hello ideal", encoding="utf-8")
    md, status = resolve_ideal("P1234R0", tmp_path)
    assert md == "hello ideal"
    assert status == IDEAL_STATUS_PRESENT


# -- panel metrics -----------------------------------------------------------

def test_identical_ideal_scores_perfect_panel():
    # _CLEAN_MD has headings but no tables: teds is ineligible (None), never a
    # synthetic 1.0, and overall averages only the eligible axes.
    panel = score_against_ideal(_CLEAN_MD, _CLEAN_MD)
    assert panel.nid == 1.0
    assert panel.teds is None
    assert panel.mhs == 1.0
    assert panel.recall == 1.0
    assert panel.overall == 1.0


def test_divergent_ideal_scores_low_nid_and_recall():
    panel = score_against_ideal(_CLEAN_MD, _DIVERGENT_MD)
    assert panel.nid < 0.5
    assert panel.recall < 0.5


def test_missing_table_drops_teds_only():
    ideal = _CLEAN_MD + "\n| a | b |\n| --- | --- |\n| 1 | 2 |\n"
    panel = score_against_ideal(_CLEAN_MD, ideal)
    assert panel.teds is not None and panel.teds < 1.0
    assert panel.mhs == 1.0


def test_tableless_headingless_ideal_yields_none_axes():
    # Null-eligibility: a plain-prose ideal exercises neither tables nor
    # headings, so overall must equal nid alone (no inflation toward 1.0).
    prose = "Just one paragraph of plain prose without structure.\n"
    panel = score_against_ideal(prose, prose)
    assert panel.teds is None and panel.mhs is None
    assert panel.overall == panel.nid == 1.0


# -- verdict integration (ADVISORY overlay, mirrors the oracle contract) ------

def test_identical_ideal_rides_along_without_flags():
    r = score_markdown(
        "P1234R0", _CLEAN_MD, content=_content(0.98), ideal_md=_CLEAN_MD,
    )
    assert r.verdict == VERDICT_PASS
    assert r.ideal_nid == 1.0
    assert r.ideal_overall == 1.0
    # ideal_md given with no explicit status -> PRESENT (scores are real).
    assert r.ideal_status == IDEAL_STATUS_PRESENT
    assert not r.hard_flags and not r.soft_flags


def test_divergent_ideal_is_advisory_review_never_fail():
    # Ground truth disagrees but content/gates are healthy: the ideal raises
    # review flags only. It must NEVER hard-fail the paper.
    r = score_markdown(
        "P1234R0", _CLEAN_MD, content=_content(0.98), ideal_md=_DIVERGENT_MD,
    )
    assert r.verdict == VERDICT_REVIEW
    assert any(f.startswith("ideal nid") and "advisory" in f for f in r.soft_flags)
    assert any(f.startswith("ideal recall") and "advisory" in f for f in r.soft_flags)
    assert not r.hard_flags


def test_no_ideal_leaves_fields_none():
    r = score_markdown("P1234R0", _CLEAN_MD, content=_content(0.98))
    assert r.ideal_overall is None and r.ideal_nid is None
    # No ideal_md and no explicit status: score_markdown cannot tell
    # "unreachable" from "reachable but absent" on its own, so it defaults to
    # the conservative UNAVAILABLE (see score_markdown docstring).
    assert r.ideal_status == IDEAL_STATUS_UNAVAILABLE
    d = r.to_dict()
    for key in ("ideal_nid", "ideal_teds", "ideal_mhs", "ideal_recall", "ideal_overall"):
        assert d[key] is None
    assert d["ideal_status"] == IDEAL_STATUS_UNAVAILABLE


def test_score_markdown_ideal_status_absent_explicit():
    # Simulates score_paper's ABSENT resolution: an ideals_dir was reachable
    # but this pid had no file, so the caller passes IDEAL_STATUS_ABSENT
    # explicitly even though ideal_md is None.
    r = score_markdown(
        "P1234R0", _CLEAN_MD, content=_content(0.98),
        ideal_status=IDEAL_STATUS_ABSENT,
    )
    assert r.ideal_status == IDEAL_STATUS_ABSENT
    assert r.ideal_overall is None and r.ideal_nid is None


def test_sidecar_carries_rounded_ideal_fields():
    r = score_markdown(
        "P1234R0", _CLEAN_MD, content=_content(0.98), ideal_md=_CLEAN_MD,
    )
    d = r.to_dict()
    assert d["ideal_overall"] == 1.0
    assert d["ideal_recall"] == 1.0
    assert d["ideal_status"] == IDEAL_STATUS_PRESENT


# -- report rendering ----------------------------------------------------------

def test_report_md_renders_ideal_column_and_section():
    from whisker.det.report import render_report_md, render_summary

    with_ideal = score_markdown(
        "P0001R0", _CLEAN_MD, content=_content(0.98), ideal_md=_CLEAN_MD,
    )
    without = score_markdown("P0002R0", _CLEAN_MD, content=_content(0.98))
    md = render_report_md([with_ideal, without])
    assert "| ideal |" in md
    assert "## Golden ideals" in md
    # Only the ideal-backed paper appears in the detail section.
    section = md.split("## Golden ideals", 1)[1]
    assert "P0001R0" in section and "P0002R0" not in section

    # Terminal summary appends idl= for ideal-backed papers only (verbose shows
    # pass lines too).
    summary = render_summary([with_ideal, without], elapsed=0.0, verbose=True)
    assert "idl=1.000" in summary


def test_report_md_distinguishes_unavailable_from_absent():
    from whisker.det.report import render_report_md

    # UNAVAILABLE (no ideals checkout reachable) and ABSENT (checkout reachable,
    # this paper has none) both leave ideal_overall None, but the leaderboard's
    # "ideal" column must render them differently so a reader does not confuse
    # "cannot tell you" with "checked, no ideal for this paper".
    unavailable = score_markdown(
        "P0001R0", _CLEAN_MD, content=_content(0.98),
        ideal_status=IDEAL_STATUS_UNAVAILABLE,
    )
    absent = score_markdown(
        "P0002R0", _CLEAN_MD, content=_content(0.98),
        ideal_status=IDEAL_STATUS_ABSENT,
    )
    md = render_report_md([unavailable, absent])
    rows = {line.split("|")[1].strip(): line for line in md.splitlines() if "| P000" in line}
    assert "unavailable" in rows["P0001R0"]
    assert "unavailable" not in rows["P0002R0"]
