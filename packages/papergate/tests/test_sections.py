#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Section-level tests for papergate.md, driven by a scripted model.

Each section is tested in isolation with execute_section, so we test exactly
the prose and Lua that will run live - only the model is scripted.
"""

from __future__ import annotations

from pathlib import Path

import papergate
import pytest
from promptforge.errors import PreconditionError
from promptforge.inference import ScriptedModel, tool_call, turn
from promptforge.runtime import Runtime
from promptforge.store import MemStore
from promptforge.vfs import MemVFS

from papergate.tools import register_tools

_MD = str(Path(papergate.__file__).parent / "papergate.md")


def _runtime(model: ScriptedModel, **kwargs) -> Runtime:
    runtime = Runtime(_MD, model=model, **kwargs)
    register_tools(runtime)
    return runtime


def test_main_requires_a_paper() -> None:
    runtime = _runtime(ScriptedModel([]))
    with pytest.raises(PreconditionError):
        runtime.execute_section("## Main", params={})


def test_digest_classifies_and_strips(tmp_path) -> None:
    paper = tmp_path / "p0870r8.md"
    paper.write_text("Title: A Proposal\n\nThe rationale argues for widgets.", encoding="utf-8")
    model = ScriptedModel([
        turn(tool_call("fetch_paper", paper=str(paper))),
        turn(
            tool_call("create_file", path="rationale.md", content="stripped rationale"),
            tool_call("set_metadata", document="P0870R8", title="A Proposal",
                      authors="A. Author", classification="library", tier="large",
                      tier_justification="47 new names"),
            tool_call("done"),
        ),
    ])
    runtime = _runtime(model)
    out = runtime.execute_section("## Digest", params={"paper": str(paper)})
    assert out.ok
    assert runtime.store.get("metadata")["classification"] in {"library", "language", "both"}
    assert runtime.vfs.exists("rationale.md")


def test_digest_acquisition_failure_stops_clean() -> None:
    model = ScriptedModel([
        turn(tool_call("fetch_paper", paper="/no/such/paper.md")),
        turn(tool_call("acquisition_failed", reason="cannot resolve"), tool_call("done")),
    ])
    runtime = _runtime(model)
    out = runtime.execute_section("## Digest", params={"paper": "/no/such/paper.md"})
    assert out.ok  # a clean stop, metadata filed
    assert runtime.store.get("metadata")["status"].startswith("ACQUISITION FAILED")


def test_evaluate_emits_only_addressed_criteria() -> None:
    vfs = MemVFS()
    vfs.create("rationale.md", "document: P1\nclassification: library\n\nSection 3.1 argues interop.")
    store = MemStore({"metadata": {
        "document": "P1234R0", "title": "Widgets", "classification": "library",
        "tier": "large", "tier_justification": "47 names",
    }})
    model = ScriptedModel([
        turn(tool_call("read_file", path="rationale.md")),
        turn(
            tool_call("file_section", criterion="The GitHub Test", assessment="Section 3.1 argues it."),
            tool_call("file_missing", criterion="Reach Test", why="no source at this tier"),
            tool_call("write_report", path="out.md"),
            tool_call("done"),
        ),
    ])
    runtime = _runtime(model, vfs=vfs, store=store)
    out = runtime.execute_section(
        "## Evaluate", params={"rationale_path": "rationale.md", "output_path": "out.md"}
    )
    assert out.ok
    report = runtime.vfs.read("out.md")
    assert "## Missing From The Paper" in report
    # One H2 per addressed criterion, plus the single Missing section.
    assert report.count("## ") == runtime.store.count("sections") + 1
