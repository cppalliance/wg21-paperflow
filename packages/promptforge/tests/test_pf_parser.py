#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the pipeline-document parser."""

from __future__ import annotations

import textwrap

import pytest

from promptforge.parser import Document


def _doc(text: str) -> Document:
    return Document(textwrap.dedent(text).lstrip("\n"))


def test_splits_h2_sections() -> None:
    doc = _doc(
        """
        ## Main

        Do the thing.

        ## Classify

        Decide the type.
        """
    )
    assert set(doc.sections) == {"Main", "Classify"}
    assert "Do the thing." in doc.section("Main").body
    assert "Decide the type." in doc.section("Classify").body


def test_preamble_is_text_before_first_h2() -> None:
    doc = _doc(
        """
        # Title

        An intro paragraph.

        ## Main

        Body.
        """
    )
    assert "An intro paragraph." in doc.preamble
    assert "# Title" in doc.preamble
    assert set(doc.sections) == {"Main"}


def test_h2_inside_fence_does_not_split() -> None:
    doc = _doc(
        """
        ## Main

        Here is an example document:

        ```text
        ## Not A Section
        more text
        ```

        Still Main.
        """
    )
    assert set(doc.sections) == {"Main"}
    assert "## Not A Section" in doc.section("Main").body


def test_extracts_lua_and_excludes_it_from_prose() -> None:
    doc = _doc(
        """
        ## Extract

        Extract every claim.

        ```lua
        model("qwen-14b")
        tools.add("read_chunk", "done")
        ```

        Call done when finished.
        """
    )
    section = doc.section("Extract")
    assert 'model("qwen-14b")' in section.lua
    assert 'tools.add' in section.lua
    assert "Extract every claim." in section.prose
    assert "Call done when finished." in section.prose
    assert "model(" not in section.prose
    assert "```" not in section.prose


def test_section_without_lua_has_none() -> None:
    doc = _doc(
        """
        ## Main

        Just prose, no config.
        """
    )
    section = doc.section("Main")
    assert section.lua is None
    assert section.prose == "Just prose, no config."


def test_non_lua_fence_is_preserved_in_prose() -> None:
    doc = _doc(
        """
        ## Report

        Use this template:

        ```markdown
        # Heading
        body
        ```
        """
    )
    prose = doc.section("Report").prose
    assert "```markdown" in prose
    assert "# Heading" in prose


def test_children_returns_h3_sections() -> None:
    doc = _doc(
        """
        ## Diagnostic Battery

        Intro line.

        ### Test 1

        First test body.

        ### Test 2

        Second test body.
        """
    )
    children = doc.children("## Diagnostic Battery")
    assert [c.name for c in children] == ["Test 1", "Test 2"]
    assert all(c.level == 3 for c in children)
    assert "First test body." in children[0].body
    assert "Second test body." in children[1].body


def test_h3_inside_fence_is_not_a_child() -> None:
    doc = _doc(
        """
        ## Battery

        ### Real Test

        body

        ```text
        ### Fake Test
        ```
        """
    )
    children = doc.children("Battery")
    assert [c.name for c in children] == ["Real Test"]


def test_extracts_tagged_block() -> None:
    doc = _doc(
        """
        ## Main

        Follow the block.

        <digest-task>
        Objective: strip the paper.
        Return the metadata.
        </digest-task>
        """
    )
    assert doc.has_block("digest-task")
    block = doc.block("digest-task")
    assert block == "Objective: strip the paper.\nReturn the metadata."


def test_block_preserves_inner_markdown_verbatim() -> None:
    doc = _doc(
        """
        ## Reference

        <evaluation-rules>
        ### The emit rule

        A criterion gets a section.

        ```markdown
        ## The GitHub Test
        example
        ```
        </evaluation-rules>
        """
    )
    # Inner headings must not have created top-level sections.
    assert set(doc.sections) == {"Reference"}
    block = doc.block("evaluation-rules")
    assert "### The emit rule" in block
    assert "## The GitHub Test" in block


def test_html_comment_and_img_are_not_blocks() -> None:
    doc = _doc(
        """
        <!-- a comment -->
        <img src="x.png" alt="y">

        ## Main

        Body.
        """
    )
    assert not doc.has_block("img")
    assert set(doc.sections) == {"Main"}


def test_ref_normalization() -> None:
    doc = _doc(
        """
        ## Main

        Body.
        """
    )
    assert doc.section("## Main") is doc.section("Main")
    assert doc.has_section("Main")
    assert doc.has_section("## Main")


def test_missing_section_and_block_raise() -> None:
    doc = _doc("## Main\n\nBody.\n")
    with pytest.raises(KeyError):
        doc.section("Nope")
    with pytest.raises(KeyError):
        doc.block("nope")


def test_from_path(tmp_path) -> None:
    p = tmp_path / "pipeline.md"
    p.write_text("## Main\n\nBody.\n", encoding="utf-8")
    doc = Document.from_path(p)
    assert doc.section("Main").prose == "Body."
