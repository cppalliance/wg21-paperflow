#
# Copyright (c) 2026 Luan Fonseca (luan@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for tomd.lib.wording_cleanup.

These tests use rendered-Markdown fixtures: the helper is deliberately
source-format-agnostic and is called by both the PDF emitter and the HTML
renderer, so the right test inputs are strings, not Span objects. The
wording class is passed in rather than parsed from a ``:::`` fence, which
tomd no longer emits.
"""

from textwrap import dedent

from tomd.lib.wording_cleanup import strip_redundant_tags


def test_uniform_add_strips_ins_tags():
    out = strip_redundant_tags("wording-add", "<ins>• added bullet</ins>")
    assert "<ins>" not in out
    assert out == "• added bullet"


def test_uniform_remove_strips_del_tags():
    out = strip_redundant_tags("wording-remove", "<del>obsolete clause</del>")
    assert "<del>" not in out
    assert out == "obsolete clause"


def test_mixed_add_keeps_inline_tags():
    body = "context anchor <ins>added</ins> more context"
    out = strip_redundant_tags("wording-add", body)
    assert "<ins>added</ins>" in out
    assert out == body


def test_neutral_wording_never_touched():
    body = "before <del>old</del> middle <ins>new</ins> after"
    out = strip_redundant_tags("wording", body)
    assert out == body


def test_unknown_class_never_touched():
    body = "<ins>everything</ins>"
    assert strip_redundant_tags("paragraph", body) == body


def test_contrarian_del_survives_uniform_add():
    # Make ins dominate clearly (>=95%) so the section is uniform-add,
    # then verify the lone <del> survives.
    big_ins = "A" * 200
    out = strip_redundant_tags(
        "wording-add", f"<ins>{big_ins}</ins> <del>x</del>")
    assert "<ins>" not in out
    assert "<del>x</del>" in out


def test_contrarian_ins_survives_uniform_remove():
    big_del = "B" * 200
    out = strip_redundant_tags(
        "wording-remove", f"<del>{big_del}</del> <ins>y</ins>")
    assert "<del>" not in out
    assert "<ins>y</ins>" in out


def test_idempotent():
    body = "<ins>uniform body</ins>"
    once = strip_redundant_tags("wording-add", body)
    twice = strip_redundant_tags("wording-add", once)
    assert once == twice


def test_multiline_ins_tag_handled():
    out = strip_redundant_tags(
        "wording-add", "<ins>first line\nsecond line\nthird line</ins>")
    assert "<ins>" not in out
    assert out == "first line\nsecond line\nthird line"


def test_multiline_del_tag_handled():
    out = strip_redundant_tags(
        "wording-remove", "<del>first line\nsecond line\nthird line</del>")
    assert "<del>" not in out
    assert out == "first line\nsecond line\nthird line"


def test_fenced_code_untouched():
    # Code-promoted sections (from PDF emit) carry a ```cpp fence and no
    # inline tags, so there is nothing redundant to strip.
    md = dedent(
        """\
        ```cpp
        template<class T>
        concept foo = true;
        ```"""
    )
    assert strip_redundant_tags("wording-add", md) == md


def test_untagged_body_passthrough():
    body = "Plain wording prose with no inline tags at all."
    assert strip_redundant_tags("wording-add", body) == body


def test_empty_body_passthrough():
    assert strip_redundant_tags("wording-add", "") == ""
