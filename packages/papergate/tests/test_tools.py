#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for PaperGate domain tools."""

from __future__ import annotations

from promptforge.inference import ScriptedModel
from promptforge.runtime import Runtime

from papergate.tools import fetch_paper, register_tools

_MD = "## Main\n\nx\n\n```lua\ntools.add(\"done\")\n```\n"


def _runtime() -> Runtime:
    runtime = Runtime(_MD, model=ScriptedModel([]))
    register_tools(runtime)
    return runtime


def test_fetch_paper_reads_local_file(tmp_path) -> None:
    paper = tmp_path / "p1234.md"
    paper.write_text("Title: Widgets\n\nThe rationale.", encoding="utf-8")
    text = fetch_paper(str(paper))
    assert "The rationale." in text


def test_fetch_paper_failure_is_reported_offline() -> None:
    result = fetch_paper("/no/such/paper.md")
    assert result.startswith("ACQUISITION FAILED")


def test_set_metadata_files_identity() -> None:
    rt = _runtime()
    rt.registry.dispatch("set_metadata", {
        "document": "P0870R8",
        "title": "A Proposal",
        "authors": "A. Author",
        "classification": "library",
        "tier": "large",
        "tier_justification": "47 new names",
    })
    meta = rt.store.get("metadata")
    assert meta["classification"] == "library"
    assert meta["tier"] == "large"


def test_set_metadata_rejects_bad_enum() -> None:
    rt = _runtime()
    out = rt.registry.dispatch("set_metadata", {
        "document": "P1", "title": "t", "authors": "a",
        "classification": "nonsense", "tier": "large", "tier_justification": "x",
    })
    assert out.startswith("ERROR:")
    assert not rt.store.exists("metadata")


def test_acquisition_failed_files_status() -> None:
    rt = _runtime()
    rt.registry.dispatch("acquisition_failed", {"reason": "dead link"})
    assert rt.store.get("metadata")["status"].startswith("ACQUISITION FAILED")


def test_file_section_and_missing_accumulate() -> None:
    rt = _runtime()
    rt.registry.dispatch("file_section", {"criterion": "GitHub Test", "assessment": "shown"})
    rt.registry.dispatch("file_missing", {"criterion": "Reach", "why": "no source"})
    assert rt.store.count("sections") == 1
    assert rt.store.count("missing") == 1


def test_write_report_renders_sections_and_missing() -> None:
    rt = _runtime()
    rt.registry.dispatch("set_metadata", {
        "document": "P1234R0", "title": "Widgets", "authors": "A",
        "classification": "library", "tier": "medium", "tier_justification": "18 names",
    })
    rt.registry.dispatch("file_section", {"criterion": "The GitHub Test", "assessment": "Section 3.1 argues it."})
    rt.registry.dispatch("file_section", {"criterion": "Coordination Problem", "assessment": "Section 3.2 documents it."})
    rt.registry.dispatch("file_missing", {"criterion": "Standardization Penalty", "why": "never priced"})
    rt.registry.dispatch("write_report", {"path": "out.md"})

    report = rt.vfs.read("out.md")
    assert report.startswith("# P1234R0 Widgets")
    assert "## The GitHub Test" in report
    assert "## Coordination Problem" in report
    assert "## Missing From The Paper" in report
    # One H2 per addressed criterion, plus the single Missing section.
    assert report.count("## ") == rt.store.count("sections") + 1
    assert rt.store.get("report_path") == "out.md"


def test_write_report_without_missing() -> None:
    rt = _runtime()
    rt.registry.dispatch("set_metadata", {
        "document": "P1", "title": "T", "authors": "A",
        "classification": "library", "tier": "trivial", "tier_justification": "one line",
    })
    rt.registry.dispatch("file_section", {"criterion": "GitHub Test", "assessment": "ok"})
    rt.registry.dispatch("write_report", {"path": "r.md"})
    report = rt.vfs.read("r.md")
    assert "addresses the applicable criteria" in report
