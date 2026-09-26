"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from tomd.domain.metadata import PaperMetadata
from tomd.writers.markdown.front_matter import write_front_matter


def test_write_front_matter_canonical_order_and_quoting():
    meta = PaperMetadata(
        title="Sample Proposal",
        document="P1234R0",
        date="2026-03-01",
        intent="explore",
        audience=["LEWG", "SG1"],
        reply_to=["Author Name <author@example.com>"],
    )
    rendered = write_front_matter(meta)
    expected = (
        "---\n"
        'title: "Sample Proposal"\n'
        "document: P1234R0\n"
        "date: 2026-03-01\n"
        "intent: explore\n"
        "audience:\n"
        '  - "LEWG"\n'
        '  - "SG1"\n'
        "reply-to:\n"
        '  - "Author Name <author@example.com>"\n'
        "---"
    )
    assert rendered == expected


def test_write_front_matter_extra_keys_placement():
    meta = PaperMetadata(
        title="Extra Keys Test",
        document="P9999R1",
        date="2026-06-01",
        reply_to=["Dev <dev@test.org>"],
        extra={"project": "ISO C++", "issue": "42"},
    )
    rendered = write_front_matter(meta)
    lines = rendered.splitlines()
    assert lines[0] == "---"
    assert lines[-1] == "---"
    assert lines[-2] == '  - "Dev <dev@test.org>"'
    assert lines[-3] == "reply-to:"
    assert "project: ISO C++" in rendered
    assert "issue: 42" in rendered


def test_write_front_matter_intent_inference():
    meta_info = PaperMetadata(title="Info: Progress Report", document="P0001R0")
    assert "intent: info" in write_front_matter(meta_info)

    meta_ask = PaperMetadata(title="Ask: Direction on Networking", document="P0002R0")
    assert "intent: ask" in write_front_matter(meta_ask)


def test_write_front_matter_empty_returns_empty_string():
    assert write_front_matter(PaperMetadata()) == ""
    assert write_front_matter({}) == ""


def test_write_front_matter_dict_input():
    data = {
        "title": "Dict Paper",
        "document": "P5555R0",
        "date": "2026-01-15",
        "reply-to": ["Editor <ed@wg21.link>"],
    }
    rendered = write_front_matter(data)
    assert 'title: "Dict Paper"' in rendered
    assert "document: P5555R0" in rendered
    assert "date: 2026-01-15" in rendered
    assert '  - "Editor <ed@wg21.link>"' in rendered
