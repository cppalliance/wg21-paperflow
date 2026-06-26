# Copyright (c) 2026 C++ Alliance, Inc.
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Tests for shared YAML front matter parse/format round-trip."""

from tomd.lib.metadata_yaml.format import (
    format_front_matter,
    parse_front_matter,
    strip_front_matter,
)

_P2583R0_FRONT_MATTER = """\
---
title: "Symmetric Transfer and Sender Composition"
document: P2583R0
date: 2026-02-22
audience: LEWG
reply-to:
  - "Mungo Gill <mungo.gill@me.com>"
  - "Vinnie Falco <vinnie.falco@gmail.com>"
---
"""


def test_quoted_title_stripped():
    parsed = parse_front_matter(_P2583R0_FRONT_MATTER + "\n## Abstract\n")
    assert parsed["title"] == "Symmetric Transfer and Sender Composition"
    assert '"' not in parsed["title"]


def test_reply_to_list():
    parsed = parse_front_matter(_P2583R0_FRONT_MATTER)
    reply_to = parsed["reply-to"]
    assert isinstance(reply_to, list)
    assert len(reply_to) == 2
    assert reply_to[0] == "Mungo Gill <mungo.gill@me.com>"
    assert reply_to[1] == "Vinnie Falco <vinnie.falco@gmail.com>"


def test_format_round_trip():
    meta = {
        "title": "Why Span Is Not Enough",
        "document": "P4036R0",
        "date": "2026-02-28",
        "intent": "info",
        "audience": "LEWG",
        "reply-to": ["Vinnie Falco <vinnie.falco@gmail.com>"],
    }
    md = format_front_matter(meta) + "\n\n## Abstract\n"
    assert parse_front_matter(md) == meta


def test_opener_trailing_space():
    md = (
        "--- \n"
        'title: "Spaced Opener"\n'
        "document: P0001R0\n"
        "---\n\n"
        "Body text.\n"
    )
    parsed = parse_front_matter(md)
    assert parsed["title"] == "Spaced Opener"
    assert parsed["document"] == "P0001R0"


def test_strip_front_matter():
    md = _P2583R0_FRONT_MATTER + "\nBody text here.\n"
    body = strip_front_matter(md)
    assert "title:" not in body
    assert "reply-to:" not in body
    assert "Body text here." in body
