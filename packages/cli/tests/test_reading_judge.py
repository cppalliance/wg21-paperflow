#
# Copyright (c) 2026 Rob Beeston (rob@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""The reading-judge resolver (cli.reading_judge) and its convert wiring. No test calls the API."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import fitz

from cli.reading_judge import JudgeClient, cache_key, make_judge, parse_answer, resolve
from paperstore.testing import store  # noqa: F401  (pytest fixture)


def _req(rid="abc", n=2):
    return {"id": rid, "pieces": [[0, [10.0, 10.0, 200.0, 100.0]]],
            "readings": [[["a", "b"]], [["a b", ""]]][:n], "sources": ["grid", "rules"][:n], "today": 0}


class _FakeMessages:
    def __init__(self, reply, stop="end_turn"):
        self.reply, self.stop, self.calls = reply, stop, []

    def create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(stop_reason=self.stop,
                               content=[SimpleNamespace(type="text", text=self.reply)])


def _client(reply, stop="end_turn"):
    fake = SimpleNamespace(messages=_FakeMessages(reply, stop))
    return JudgeClient(model="test-model", client=fake), fake.messages


def _pdf(tmp_path: Path) -> Path:
    doc = fitz.open()
    doc.new_page(width=612, height=792)
    path = tmp_path / "x.pdf"
    doc.save(str(path))
    return path


def test_parse_answer_maps_the_letter_and_rejects_bad_json():
    assert parse_answer('{"pick": "B", "confidence": "high", "why": "x"}', ["A", "B"]) == \
        {"pick": 1, "confidence": "high", "why": "x"}
    assert parse_answer('{"pick": "C", "confidence": "high"}', ["A", "B"]) is None
    assert parse_answer('{"pick": "A", "confidence": "sure"}', ["A", "B"]) is None
    assert parse_answer("not json", ["A", "B"]) is None


def test_ask_sends_crops_and_lettered_readings_with_a_schema():
    client, msgs = _client('{"pick": "B", "confidence": "medium", "why": "rows"}')
    ans = client.ask([b"\x89PNGfake"], _req())
    assert ans == {"pick": 1, "confidence": "medium", "why": "rows"}
    kw = msgs.calls[0]
    assert kw["model"] == "test-model"
    content = kw["messages"][0]["content"]
    assert content[0]["type"] == "image" and content[-1]["type"] == "text"
    assert "### Reading B" in content[-1]["text"]
    assert kw["output_config"]["format"]["schema"]["properties"]["pick"]["enum"] == ["A", "B"]


def test_a_refusal_or_error_gives_no_answer():
    client, _ = _client("{}", stop="refusal")
    assert client.ask([b"png"], _req()) is None

    class _Boom:
        def create(self, **kw):
            raise RuntimeError("network")
    assert JudgeClient(model="m", client=SimpleNamespace(messages=_Boom())).ask([b"png"], _req()) is None


def test_resolve_uses_the_cache_and_asks_only_on_a_miss(tmp_path):
    pdf = _pdf(tmp_path)
    client, msgs = _client('{"pick": "B", "confidence": "high", "why": "w"}')
    cache = {cache_key("test-model", _req("hit")): {"pick": 0, "confidence": "low", "why": ""}}
    answers = resolve(pdf, [_req("hit"), _req("miss")], cache, client)
    assert answers["hit"]["confidence"] == "low"
    assert answers["miss"] == {"pick": 1, "confidence": "high", "why": "w"}
    assert len(msgs.calls) == 1 and cache_key("test-model", _req("miss")) in cache
    # cache mode never calls the model
    assert resolve(pdf, [_req("other")], {}, None) == {}


def test_make_judge_is_none_when_off():
    assert make_judge("off", {}, None) is None
    assert make_judge("cache", None, None) is None
    assert callable(make_judge("cache", {}, None))


def test_run_convert_live_persists_new_answers_and_off_passes_no_judge(store, tmp_path, monkeypatch):
    from cli import jobs
    from cli.models import ConvertResult
    pid = "P1234R0"
    store.upsert_year("2026", [{"paper_id": pid, "title": "Sample"}])
    store.put_source(pid, b"%PDF-1.4 stub", suffix=".pdf")
    old = {"test-model/old": {"pick": 0, "confidence": "high", "why": ""}}
    store.write_intermediate(pid, "judge", old)
    pdf = _pdf(tmp_path)
    client, msgs = _client('{"pick": "B", "confidence": "high", "why": "w"}')
    monkeypatch.setattr("cli.jobs.JudgeClient", lambda: client)
    seen = {}

    def _stub(_paper, judge=None, **_kw):
        seen["judge"] = judge
        if judge is not None:
            seen["answers"] = judge(pdf, [_req("old"), _req("new")])
        return ConvertResult(paper_id=pid, markdown="# S\n", prompts=None, intent="", title="S", status="ok")

    monkeypatch.setattr("cli.jobs.convert_one_paper", _stub)
    asyncio.run(jobs.run_convert([pid], store, force=True, concurrency=1, judge_tables="live"))
    assert set(seen["answers"]) == {"old", "new"} and len(msgs.calls) == 1
    assert store.read_intermediate(pid, "judge") == {**old, "test-model/new": {"pick": 1, "confidence": "high", "why": "w"}}

    seen.clear()
    asyncio.run(jobs.run_convert([pid], store, force=True, concurrency=1))
    assert seen["judge"] is None
