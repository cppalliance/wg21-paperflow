"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

import pytest

from tomd.domain.metadata import PaperMetadata
from tomd.lib.metadata_yaml.format import format_front_matter
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


def test_write_front_matter_matches_format_front_matter():
    meta = PaperMetadata(
        title="Plain Title",
        document="P1234R0",
        date="2026-03-01",
        intent="explore",
        audience=["LEWG", "SG1"],
        reply_to=["A <a@example.com>", "B <b@example.com>"],
        extra={"project": "ISO C++"},
    )
    assert write_front_matter(meta) == format_front_matter(meta.to_dict())


def test_write_front_matter_title_scope_operator_spacing_literal():
    meta = PaperMetadata(title="std :: execution  Senders", document="P2300R10")
    assert write_front_matter(meta) == (
        "---\n"
        'title: "std::execution Senders"\n'
        "document: P2300R10\n"
        "---"
    )


def test_write_front_matter_info_intent_inference_literal():
    meta = PaperMetadata(title="Info: Progress Report", document="P0001R0")
    assert write_front_matter(meta) == (
        "---\n"
        'title: "Info: Progress Report"\n'
        "document: P0001R0\n"
        "intent: info\n"
        "---"
    )


def test_write_front_matter_list_reply_to_and_extra_keys_literal():
    meta = PaperMetadata(
        title="Extras",
        document="P9999R1",
        reply_to=["A <a@example.com>", "B <b@example.com>"],
        extra={"project": "ISO C++", "issue": "42"},
    )
    assert write_front_matter(meta) == (
        "---\n"
        'title: "Extras"\n'
        "document: P9999R1\n"
        "project: ISO C++\n"
        "issue: 42\n"
        "reply-to:\n"
        '  - "A <a@example.com>"\n'
        '  - "B <b@example.com>"\n'
        "---"
    )


_BLANK_VALUE_CASES = [
    pytest.param({"reply-to": ["a", ""]}, 'reply-to:\n  - "a"', id="blank-list-item"),
    pytest.param({"reply-to": ["a", "  "]}, 'reply-to:\n  - "a"', id="whitespace-list-item"),
    pytest.param({"reply-to": [""]}, None, id="all-blank-list"),
    pytest.param({"reply-to": ()}, None, id="empty-tuple"),
    pytest.param({"intent": "  "}, None, id="whitespace-scalar"),
    pytest.param({"project": "  "}, None, id="whitespace-extra-scalar"),
    pytest.param({"audience": ("LEWG", "SG1")}, 'audience:\n  - "LEWG"\n  - "SG1"', id="tuple"),
    pytest.param({"project": ("a", "")}, 'project:\n  - "a"', id="tuple-extra-blank-item"),
]


def _expected_with_blank_case(fragment: str | None) -> str:
    head = '---\ntitle: "T"\n'
    return head + (fragment + "\n" if fragment else "") + "---"


@pytest.mark.parametrize(("fields", "fragment"), _BLANK_VALUE_CASES)
def test_write_front_matter_blank_values_metadata_input(fields, fragment):
    extra = {k: v for k, v in fields.items() if k not in {"audience", "reply-to", "intent"}}
    kwargs = {k.replace("-", "_"): v for k, v in fields.items() if k in {"audience", "reply-to", "intent"}}
    meta = PaperMetadata(title="T", extra=extra, **kwargs)
    assert write_front_matter(meta) == _expected_with_blank_case(fragment)
