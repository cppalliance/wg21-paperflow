#
# Copyright (c) 2026 Rob Beeston (rob@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""The page-tables resolver (cli.page_tables) and its convert wiring. No test calls the API."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import fitz

from cli.page_tables import PageTablesClient, cache_key, make_page_tables, parse_answer, resolve
from paperstore.testing import store  # noqa: F401  (pytest fixture)
from tomd.lib.pdf.page_tables import page_table_requests

_REPLY = '{"tables": [{"rows": [["a", "b"]], "continues_from_previous_page": false, "continues_on_next_page": false}]}'


class _Stream:
    def __init__(self, msg):
        self.msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.msg


class _FakeMessages:
    def __init__(self, reply, stop="end_turn"):
        self.reply, self.stop, self.calls = reply, stop, []

    def stream(self, **kw):
        self.calls.append(kw)
        return _Stream(SimpleNamespace(stop_reason=self.stop,
                                       content=[SimpleNamespace(type="text", text=self.reply)]))


def _client(reply=_REPLY, stop="end_turn"):
    fake = SimpleNamespace(messages=_FakeMessages(reply, stop))
    return PageTablesClient(model="test-model", client=fake), fake.messages


def _pdf(tmp_path: Path, pages=2) -> Path:
    doc = fitz.open()
    for i in range(pages):
        doc.new_page(width=612, height=792).insert_text((72, 100), f"page {i}")
    path = tmp_path / "x.pdf"
    doc.save(str(path))
    return path


def test_parse_answer_keeps_tables_and_rejects_bad_json():
    assert parse_answer(_REPLY)["tables"][0]["rows"] == [["a", "b"]]
    assert parse_answer('{"tables": "x"}') is None
    assert parse_answer("not json") is None


def test_ask_sends_the_page_image_with_a_schema():
    client, msgs = _client()
    assert client.ask(b"\x89PNGfake")["tables"][0]["rows"] == [["a", "b"]]
    kw = msgs.calls[0]
    assert kw["model"] == "test-model"
    content = kw["messages"][0]["content"]
    assert content[0]["type"] == "image" and content[-1]["type"] == "text"
    assert "tables" in kw["output_config"]["format"]["schema"]["properties"]


def test_a_refusal_or_error_gives_no_answer():
    client, _ = _client(stop="refusal")
    assert client.ask(b"png") is None

    class _Boom:
        def stream(self, **kw):
            raise RuntimeError("network")
    assert PageTablesClient(model="m", client=SimpleNamespace(messages=_Boom())).ask(b"png") is None


def test_resolve_uses_the_cache_and_asks_only_on_a_miss(tmp_path):
    pdf = _pdf(tmp_path)
    with fitz.open(str(pdf)) as doc:
        ids = [r["id"] for r in page_table_requests(doc)]
    client, msgs = _client()
    cache = {cache_key("test-model", ids[0]): {"tables": []}}
    answers = resolve(pdf, cache, client)
    assert answers[ids[0]] == {"tables": []} and answers[ids[1]]["tables"][0]["rows"] == [["a", "b"]]
    assert len(msgs.calls) == 1 and cache_key("test-model", ids[1]) in cache
    # cache mode never calls the model
    assert resolve(pdf, {}, None) == {}


def test_make_page_tables_is_none_when_off():
    assert make_page_tables("off", {}, None) is None
    assert make_page_tables("cache", None, None) is None
    assert callable(make_page_tables("cache", {}, None))


def test_run_convert_live_persists_new_answers_and_off_passes_none(store, tmp_path, monkeypatch):
    from cli import jobs
    from cli.models import ConvertResult
    pid = "P1234R0"
    store.upsert_year("2026", [{"paper_id": pid, "title": "Sample"}])
    store.put_source(pid, b"%PDF-1.4 stub", suffix=".pdf")
    old = {"test-model/old": {"tables": []}}
    store.write_intermediate(pid, "pagetables", old)
    pdf = _pdf(tmp_path, pages=1)
    client, msgs = _client()
    monkeypatch.setattr("cli.jobs.PageTablesClient", lambda: client)
    seen = {}

    def _stub(_paper, page_tables=None, **_kw):
        seen["page_tables"] = page_tables
        if page_tables is not None:
            seen["answers"] = page_tables(pdf)
        return ConvertResult(paper_id=pid, markdown="# S\n", prompts=None, intent="", title="S", status="ok")

    monkeypatch.setattr("cli.jobs.convert_one_paper", _stub)
    asyncio.run(jobs.run_convert([pid], store, force=True, concurrency=1, page_tables="live"))
    assert len(seen["answers"]) == 1 and len(msgs.calls) == 1
    saved = store.read_intermediate(pid, "pagetables")
    assert saved["test-model/old"] == {"tables": []} and len(saved) == 2

    seen.clear()
    asyncio.run(jobs.run_convert([pid], store, force=True, concurrency=1))
    assert seen["page_tables"] is None
