#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

from __future__ import annotations

from chatsmith.pack.prompt import parse_sections, parse_services


def test_parse_sections_splits_on_h2_headers() -> None:
    md = "# Title\n\npreamble\n\n## First\nalpha\nbeta\n\n## Second\ngamma\n"
    sections = parse_sections(md)
    assert set(sections) == {"First", "Second"}
    assert sections["First"] == "alpha\nbeta"
    assert sections["Second"] == "gamma"


def test_parse_sections_ignores_content_before_the_first_h2() -> None:
    # A leading H1 or preamble is not a section and must not appear as a key.
    md = "# Doc\nintro text\n## Only\nbody"
    assert list(parse_sections(md)) == ["Only"]


def test_parse_services_reads_bold_bullets_lowercased() -> None:
    body = "- **Default:** chatsmith-conversational\n- **fast:** chatsmith-fast\n"
    assert parse_services(body) == {
        "default": "chatsmith-conversational",
        "fast": "chatsmith-fast",
    }


def test_parse_services_ignores_non_bullet_lines() -> None:
    body = "intro prose\n- **default:** svc-a\nnot a bullet at all\n"
    assert parse_services(body) == {"default": "svc-a"}


def test_parse_services_empty_section_is_empty_map() -> None:
    assert parse_services("") == {}
