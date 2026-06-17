#
# Copyright (c) 2026 Luan Fonseca (luan@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for tomd.lib.wording_cleanup.

These tests use raw Markdown fixtures: the cleanup pass is deliberately
source-format-agnostic and runs after both PDF and HTML rendering, so
the right test inputs are strings, not Span objects.
"""

from textwrap import dedent

from tomd.lib.wording_cleanup import clean_wording_blocks


def _wrap(div_class: str, body: str) -> str:
    # Plain string concatenation rather than dedent + f-string: dedent
    # runs after substitution and trips on multi-line `body` values.
    return f":::{div_class}\n\n{body}\n\n:::\n"


def test_uniform_add_strips_ins_tags():
    md = _wrap("wording-add", "<ins>• added bullet</ins>")
    out = clean_wording_blocks(md)
    assert "<ins>" not in out
    assert "• added bullet" in out
    assert ":::wording-add" in out
    assert out.endswith(":::\n")


def test_uniform_remove_strips_del_tags():
    md = _wrap("wording-remove", "<del>obsolete clause</del>")
    out = clean_wording_blocks(md)
    assert "<del>" not in out
    assert "obsolete clause" in out


def test_mixed_add_keeps_inline_tags():
    md = _wrap(
        "wording-add",
        "context anchor <ins>added</ins> more context",
    )
    out = clean_wording_blocks(md)
    assert "<ins>added</ins>" in out


def test_neutral_wording_never_touched():
    md = _wrap(
        "wording",
        "before <del>old</del> middle <ins>new</ins> after",
    )
    out = clean_wording_blocks(md)
    assert "<del>old</del>" in out
    assert "<ins>new</ins>" in out


def test_contrarian_del_survives_uniform_add():
    # Make ins dominate clearly (>=95%) so the section is uniform-add,
    # then verify the lone <del> survives.
    big_ins = "A" * 200
    md = _wrap("wording-add", f"<ins>{big_ins}</ins> <del>x</del>")
    out = clean_wording_blocks(md)
    assert "<ins>" not in out
    assert "<del>x</del>" in out


def test_contrarian_ins_survives_uniform_remove():
    big_del = "B" * 200
    md = _wrap("wording-remove", f"<del>{big_del}</del> <ins>y</ins>")
    out = clean_wording_blocks(md)
    assert "<del>" not in out
    assert "<ins>y</ins>" in out


def test_idempotent():
    md = _wrap("wording-add", "<ins>uniform body</ins>")
    once = clean_wording_blocks(md)
    twice = clean_wording_blocks(once)
    assert once == twice


def test_multiline_ins_tag_handled():
    md = _wrap(
        "wording-add",
        "<ins>first line\nsecond line\nthird line</ins>",
    )
    out = clean_wording_blocks(md)
    assert "<ins>" not in out
    assert "first line" in out
    assert "second line" in out
    assert "third line" in out


def test_multiline_del_tag_handled():
    md = _wrap(
        "wording-remove",
        "<del>first line\nsecond line\nthird line</del>",
    )
    out = clean_wording_blocks(md)
    assert "<del>" not in out
    assert "first line" in out
    assert "second line" in out
    assert "third line" in out


def test_fenced_code_inside_div_untouched():
    # Code-promoted divs (from PDF emit) carry a ```cpp fence and no
    # inline tags. The pass must not break their structure and must not
    # mistake a `:::` line inside the fence (hypothetical) for the
    # terminator.
    md = dedent(
        """\
        :::wording-add

        ```cpp
        template<class T>
        concept foo = true;
        ```

        :::
        """
    )
    out = clean_wording_blocks(md)
    assert out == md


def test_multiple_divs_processed_independently():
    md = (
        _wrap("wording-add", "<ins>first add</ins>")
        + "\n"
        + _wrap("wording-remove", "<del>first remove</del>")
        + "\n"
        + _wrap(
            "wording-add",
            "context <ins>partial</ins> more context",
        )
    )
    out = clean_wording_blocks(md)
    assert "first add" in out
    assert "first remove" in out
    assert "<ins>partial</ins>" in out  # the mixed one keeps its tag
    # Uniform blocks lose theirs
    assert out.count("<ins>") == 1
    assert out.count("<del>") == 0


def test_non_wording_content_passthrough():
    md = dedent(
        """\
        # Heading

        Paragraph with <ins>raw inline</ins> tag outside any div.

        ```cpp
        int main() { return 0; }
        ```
        """
    )
    out = clean_wording_blocks(md)
    assert out == md


def test_unclosed_div_leaves_document_intact():
    md = dedent(
        """\
        :::wording-add

        <ins>orphan content with no terminator</ins>
        """
    )
    out = clean_wording_blocks(md)
    # Don't crash, don't silently drop the orphan section.
    assert "<ins>orphan content with no terminator</ins>" in out
    assert ":::wording-add" in out


def test_empty_div_passthrough():
    md = dedent(
        """\
        :::wording-add

        :::
        """
    )
    out = clean_wording_blocks(md)
    assert out == md
