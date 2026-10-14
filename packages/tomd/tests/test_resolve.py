#
# Copyright (c) 2026 Sean Parsons (seanpatrick2013@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Oracle tests: ``resolve_metadata`` against legacy ``api._normalize_front_matter``."""

import logging
from dataclasses import fields
from typing import Any

import pytest

from tomd.api import _normalize_front_matter
from tomd.domain.metadata import PaperMetadata
from tomd.lib.metadata_yaml.format import (
    FRONT_MATTER_RE,
    format_front_matter,
    parse_front_matter,
)
from tomd.resolve import _FALLBACK_KEY_MAP, MailingRecord, resolve_metadata

_BODY = "## Introduction\n\nBody text.\n"

_PARSED_FULL: dict[str, Any] = {
    "title": "Paper Title",
    "document": "P2583R3",
    "date": "2024-01-15",
    "intent": "info",
    "audience": "SG1, LEWG",
    "reply-to": ["Author Name <author@example.com>"],
}

# Shape built by cli.orchestrator.convert_one_paper.
_MAILING_FULL: dict[str, Any] = {
    "paper_id": "P2583R3",
    "title": "Mailing Title",
    "authors": ["Mailing Author <mailing@example.com>", "Second Author <second@example.com>"],
    "target_group": "EWG",
    "subgroup": "EWG",
    "document_date": "2024-02-01",
    "intent": "ask",
    "url": "https://wg21.link/P2583R3",
}


def _md(front: dict[str, Any] | None) -> str:
    """Return converter-shaped Markdown: canonical front matter, blank line, body."""
    if not front:
        return _BODY
    return f"{format_front_matter(front)}\n\n{_BODY}"


def _without(data: dict[str, Any], key: str) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k != key}


def _front_matter_block(md: str) -> str:
    match = FRONT_MATTER_RE.match(md)
    return match.group(0).rstrip() if match else ""


def _legacy(md: str, meta: dict[str, Any] | None) -> str:
    return _front_matter_block(_normalize_front_matter(md, meta))


def _resolved(md: str, meta: dict[str, Any] | None) -> str:
    parsed = PaperMetadata.from_dict(parse_front_matter(md))
    return format_front_matter(resolve_metadata(parsed, MailingRecord.from_meta(meta)).to_dict())


_ORACLE_CASES = [
    pytest.param(_PARSED_FULL, _MAILING_FULL, id="all-present-nothing-overridden"),
    pytest.param(
        {**_PARSED_FULL, "document": "P2583R2"},
        _MAILING_FULL,
        id="all-present-document-overridden",
    ),
    *(
        pytest.param(_without(_PARSED_FULL, key), _MAILING_FULL, id=f"missing-{key}")
        for key in _PARSED_FULL
    ),
    *(
        pytest.param(_without(_PARSED_FULL, key), None, id=f"missing-{key}-no-mailing")
        for key in _PARSED_FULL
    ),
    pytest.param(
        {**_PARSED_FULL, "document": "D2583R3"},
        _MAILING_FULL,
        id="d-number-overridden-by-paper-id",
    ),
    pytest.param(
        {"title": "Agenda", "document": "N5022"},
        {"paper_id": "N5034"},
        id="n-number-overridden-by-paper-id",
    ),
    pytest.param(
        {**_PARSED_FULL, "document": "D2583R3"},
        {**_MAILING_FULL, "paper_id": ""},
        id="d-number-kept-when-paper-id-empty",
    ),
    pytest.param(
        {**_PARSED_FULL, "reply-to": ["Alice Smith", "Bob Jones"]},
        _MAILING_FULL,
        id="reply-to-names-only-replaced-by-authors",
    ),
    pytest.param(
        {**_PARSED_FULL, "reply-to": ["Alice Smith", "Bob <bob@example.com>"]},
        _MAILING_FULL,
        id="reply-to-with-one-email-kept",
    ),
    pytest.param(
        {**_PARSED_FULL, "reply-to": ["Alice Smith"]},
        {**_MAILING_FULL, "authors": []},
        id="reply-to-names-only-kept-when-authors-empty",
    ),
    pytest.param(
        {**_PARSED_FULL, "reply-to": "Alice <alice@example.com>"},
        _MAILING_FULL,
        id="reply-to-scalar-sanitized-to-list",
    ),
    pytest.param(
        {**_PARSED_FULL, "reply-to": ["Abstract of the paper"]},
        _MAILING_FULL,
        id="reply-to-non-author-dropped-then-filled",
    ),
    pytest.param(
        {**_PARSED_FULL, "reply-to": ["Alice <<alice@example.com>>"]},
        None,
        id="reply-to-double-angle-sanitized",
    ),
    pytest.param(
        _without(_PARSED_FULL, "audience"),
        {"subgroup": "SG16", "target_group": "LEWG"},
        id="audience-subgroup-wins-over-target-group",
    ),
    pytest.param(
        _without(_PARSED_FULL, "audience"),
        {"subgroup": "SG16"},
        id="audience-from-subgroup",
    ),
    pytest.param(
        _without(_PARSED_FULL, "audience"),
        {"target_group": "LEWG"},
        id="audience-from-target-group",
    ),
    pytest.param(
        _without(_PARSED_FULL, "audience"),
        {"subgroup": "", "target_group": "LEWG"},
        id="audience-empty-subgroup-falls-through",
    ),
    pytest.param(
        {"title": "T"},
        {
            "paper_id": "",
            "title": "",
            "authors": [],
            "target_group": "",
            "subgroup": "",
            "document_date": "",
        },
        id="empty-mailing-values",
    ),
    pytest.param(
        {"title": "T"},
        {
            "paper_id": None,
            "title": None,
            "authors": None,
            "target_group": None,
            "subgroup": None,
            "document_date": None,
        },
        id="none-mailing-values",
    ),
    pytest.param({"title": "T"}, {"intent": "ask", "url": "u"}, id="mailing-without-fallback-keys"),
    pytest.param(_PARSED_FULL, {}, id="empty-mailing-dict"),
    pytest.param(_PARSED_FULL, None, id="no-mailing"),
    pytest.param(None, _MAILING_FULL, id="no-parsed-front-matter"),
    pytest.param(None, {"title": "Info: Progress", "paper_id": "P0001R0"}, id="no-parsed-intent-inferred"),
    pytest.param(None, None, id="no-parsed-no-mailing"),
    pytest.param(None, {}, id="no-parsed-empty-mailing"),
    pytest.param(
        {"title": "Ask: Direction", "document": "P0002R0"},
        None,
        id="intent-inferred-from-title",
    ),
    pytest.param(
        {"title": "Real Title Document: P1234R0 Date: 2024-01-01", "document": "P1234R0"},
        _MAILING_FULL,
        id="title-label-leak-sanitized",
    ),
    pytest.param(
        {"title": "std :: execution  Senders", "document": "P2300R10"},
        None,
        id="title-scope-operator-normalized",
    ),
    pytest.param(
        {**_PARSED_FULL, "custom": "value", "project": "ISO C++"},
        _MAILING_FULL,
        id="unknown-keys-preserved-in-order",
    ),
    pytest.param(
        {**_PARSED_FULL, "audience": ["SG1", "LEWG"]},
        _MAILING_FULL,
        id="audience-list-kept",
    ),
    pytest.param(
        {"title": 'Quotes "and" backslash \\ text', "document": "P0003R0"},
        None,
        id="title-yaml-escaping-round-trip",
    ),
    # A blank value counts as missing: never emitted, filled from the mailing.
    pytest.param({"title": "", "document": "P0004R0"}, _MAILING_FULL, id="empty-title-filled"),
    pytest.param({"title": "", "document": "P0004R0"}, None, id="empty-title-no-mailing"),
    pytest.param({"title": ""}, None, id="empty-title-only"),
    pytest.param(
        {"title": "Title: Date: 2024", "document": "P0004R0"},
        _MAILING_FULL,
        id="title-sanitized-to-empty-filled",
    ),
    pytest.param(
        {"title": "Document Number: Date: 2024-01-01", "document": "P0004R0"},
        None,
        id="title-sanitized-to-empty-no-mailing",
    ),
    pytest.param({"document": "P0004R0"}, {"title": "   "}, id="whitespace-mailing-title-not-filled"),
    pytest.param(
        _without(_PARSED_FULL, "audience"),
        {"subgroup": "  ", "target_group": "LEWG"},
        id="audience-whitespace-subgroup-falls-through",
    ),
    pytest.param(
        _without(_PARSED_FULL, "reply-to"),
        {"authors": ["", "Alice <alice@example.com>"]},
        id="authors-blank-item-dropped",
    ),
    pytest.param(
        _without(_PARSED_FULL, "reply-to"),
        {"authors": ["", "  "]},
        id="authors-all-blank-not-filled",
    ),
]


@pytest.mark.parametrize(("parsed", "meta"), _ORACLE_CASES)
def test_resolve_matches_legacy_normalize(
    parsed: dict[str, Any] | None,
    meta: dict[str, Any] | None,
) -> None:
    md = _md(parsed)
    assert _resolved(md, meta) == _legacy(md, meta)


def test_resolve_logs_date_fallback(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="tomd.resolve"):
        resolved = resolve_metadata(PaperMetadata(title="T"), MailingRecord(document_date="2024-02-01"))
    assert resolved.date == "2024-02-01"
    assert "Date fallback from mailing (document_date='2024-02-01')" in caplog.text


def test_resolve_does_not_log_when_source_has_date(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="tomd.resolve"):
        resolve_metadata(PaperMetadata(date="2024-01-15"), MailingRecord(document_date="2024-02-01"))
    assert "Date fallback" not in caplog.text


def test_resolve_does_not_mutate_inputs() -> None:
    parsed = PaperMetadata(title="T", document="D0001R0", reply_to=["Alice"])
    mailing = MailingRecord(paper_id="P0001R0", authors=("Bob <bob@example.com>",))
    resolved = resolve_metadata(parsed, mailing)
    assert resolved.document == "P0001R0"
    assert resolved.reply_to == ["Bob <bob@example.com>"]
    assert parsed == PaperMetadata(title="T", document="D0001R0", reply_to=["Alice"])
    assert resolved is not parsed


def test_mailing_record_from_meta_empty_is_none() -> None:
    assert MailingRecord.from_meta(None) is None
    assert MailingRecord.from_meta({}) is None


def test_mailing_record_from_meta_reads_fallback_fields_only() -> None:
    assert MailingRecord.from_meta(_MAILING_FULL) == MailingRecord(
        paper_id="P2583R3",
        title="Mailing Title",
        authors=("Mailing Author <mailing@example.com>", "Second Author <second@example.com>"),
        target_group="EWG",
        subgroup="EWG",
        document_date="2024-02-01",
    )


def test_mailing_record_from_meta_normalizes_missing_and_none() -> None:
    assert MailingRecord.from_meta({"paper_id": "P1", "authors": None, "title": None}) == MailingRecord(
        paper_id="P1"
    )


def test_resolve_fills_title_that_sanitizes_to_empty() -> None:
    resolved = resolve_metadata(PaperMetadata(title="Title: Date: 2024"), MailingRecord(title="Mailing Title"))
    assert resolved.title == "Mailing Title"


def test_mailing_record_from_meta_bare_author_string_is_one_name() -> None:
    record = MailingRecord.from_meta({"authors": "Alice <alice@example.com>"})
    assert record is not None
    assert record.authors == ("Alice <alice@example.com>",)


def test_mailing_record_fields_are_exactly_the_fallback_sources() -> None:
    assert {f.name for f in fields(MailingRecord)} == set(_FALLBACK_KEY_MAP)
