"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from tomd.domain.mailing import MailingRecord

# Shape built by cli.orchestrator.convert_one_paper.
_META_FULL = {
    "paper_id": "P2583R3",
    "title": "Mailing Title",
    "authors": ["Mailing Author <mailing@example.com>", "Second Author <second@example.com>"],
    "target_group": "EWG",
    "subgroup": "EWG",
    "document_date": "2024-02-01",
    "intent": "ask",
    "url": "https://wg21.link/P2583R3",
}


def test_from_meta_empty_is_empty_record() -> None:
    assert MailingRecord.from_meta(None) == MailingRecord()
    assert MailingRecord.from_meta({}) == MailingRecord()


def test_from_meta_reads_fallback_fields_only() -> None:
    assert MailingRecord.from_meta(_META_FULL) == MailingRecord(
        paper_id="P2583R3",
        title="Mailing Title",
        authors=("Mailing Author <mailing@example.com>", "Second Author <second@example.com>"),
        audience="EWG",
        document_date="2024-02-01",
    )


def test_from_meta_none_values_read_as_empty() -> None:
    meta = {"paper_id": "P1", "authors": None, "title": None, "subgroup": None, "target_group": None}
    assert MailingRecord.from_meta(meta) == MailingRecord(paper_id="P1")


def test_from_meta_bare_author_string_is_one_name() -> None:
    assert MailingRecord.from_meta({"authors": "Alice <alice@example.com>"}).authors == (
        "Alice <alice@example.com>",
    )


def test_from_meta_audience_prefers_subgroup() -> None:
    assert MailingRecord.from_meta({"subgroup": "SG16", "target_group": "LEWG"}).audience == "SG16"


def test_from_meta_audience_from_target_group() -> None:
    assert MailingRecord.from_meta({"target_group": "LEWG"}).audience == "LEWG"


def test_from_meta_blank_subgroup_falls_through_to_target_group() -> None:
    assert MailingRecord.from_meta({"subgroup": "", "target_group": "LEWG"}).audience == "LEWG"
    assert MailingRecord.from_meta({"subgroup": "  ", "target_group": "LEWG"}).audience == "LEWG"
