#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the generic library tools."""

from __future__ import annotations

from promptforge.inference import ScriptedModel
from promptforge.runtime import Runtime

_MD = "## Main\n\nx\n\n```lua\ntools.add(\"done\")\n```\n"


def _runtime(**kwargs) -> Runtime:
    return Runtime(_MD, model=ScriptedModel([]), **kwargs)


def test_create_and_read_file() -> None:
    rt = _runtime()
    assert rt.registry.dispatch("create_file", {"path": "a.md", "content": "hi"})
    assert rt.vfs.read("a.md") == "hi"
    assert rt.registry.dispatch("read_file", {"path": "a.md"}) == "hi"


def test_append_file() -> None:
    rt = _runtime()
    rt.registry.dispatch("append_file", {"path": "log.md", "content": "a"})
    rt.registry.dispatch("append_file", {"path": "log.md", "content": "b"})
    assert rt.vfs.read("log.md") == "ab"


def test_delete_file() -> None:
    rt = _runtime()
    rt.registry.dispatch("create_file", {"path": "a.md", "content": "x"})
    rt.registry.dispatch("delete_file", {"path": "a.md"})
    assert not rt.vfs.exists("a.md")


def test_read_missing_file_is_error_string() -> None:
    rt = _runtime()
    assert rt.registry.dispatch("read_file", {"path": "nope.md"}).startswith("ERROR:")


def test_present_records_on_run() -> None:
    rt = _runtime()
    rt.registry.dispatch("present", {"summary": "the case is half made", "path": "out.md"})
    assert rt.ctx.presented == "the case is half made"
    assert rt.ctx.extras["presented_path"] == "out.md"


def test_ask_user_uses_callback() -> None:
    rt = _runtime(ask_fn=lambda q: f"answer to {q}")
    assert rt.registry.dispatch("ask_user", {"question": "ready?"}) == "answer to ready?"


def test_ask_user_unattended_default() -> None:
    rt = _runtime()
    assert "unattended" in rt.registry.dispatch("ask_user", {"question": "ready?"}).lower()
