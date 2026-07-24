#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""End-to-end PaperGate run on a scripted model (offline, deterministic)."""

from __future__ import annotations

from promptforge.inference import ScriptedModel, tool_call, turn

from papergate.run import build_runtime


def test_full_pipeline_end_to_end(tmp_path) -> None:
    paper = tmp_path / "p0870r8.md"
    paper.write_text("Title: A Proposal\n\nSection 3.1 argues for widgets.", encoding="utf-8")

    # Queue is the interleaved order of model calls across Main and its subagents.
    model = ScriptedModel([
        # Main: delegate to Digest.
        turn(tool_call("task", section="## Digest", params={"paper": str(paper)})),
        # Digest: fetch, then strip + classify + done.
        turn(tool_call("fetch_paper", paper=str(paper))),
        turn(
            tool_call("create_file", path="rationale.md", content="Section 3.1 argues interop."),
            tool_call("set_metadata", document="P0870R8", title="A Proposal",
                      authors="A. Author", classification="library", tier="large",
                      tier_justification="47 new names"),
            tool_call("done"),
        ),
        # Main: delegate to Evaluate.
        turn(tool_call("task", section="## Evaluate",
                       params={"rationale_path": "rationale.md", "output_path": "out.md"})),
        # Evaluate: read, then file + write + done.
        turn(tool_call("read_file", path="rationale.md")),
        turn(
            tool_call("file_section", criterion="The GitHub Test", assessment="Section 3.1 argues it."),
            tool_call("file_missing", criterion="Standardization Penalty", why="never priced at large tier"),
            tool_call("write_report", path="out.md"),
            tool_call("done"),
        ),
        # Main: read the report, present, done.
        turn(
            tool_call("read_file", path="out.md"),
            tool_call("present", summary="A library proposal at large tier; the case is half made.", path="out.md"),
            tool_call("done"),
        ),
    ])

    runtime = build_runtime(model=model)
    result = runtime.execute(params={"paper": str(paper), "output_path": "out.md"})

    assert result.ok
    assert result.vfs.exists("out.md")
    report = result.vfs.read("out.md")
    assert "## The GitHub Test" in report
    assert "## Missing From The Paper" in report
    # PaperGate reports whether the case is made; it never decides belonging.
    assert "hire" not in result.presented.lower()
    assert result.store.get("metadata")["classification"] == "library"
