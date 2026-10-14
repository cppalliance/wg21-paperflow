#
# Copyright (c) 2026 Sean Parsons (seanpatrick2013@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Tests for the whisker check-facts subcommand."""
import json
import subprocess
import sys

from whisker.__main__ import main

GOOD_MD = """\
---
title: "Test"
document: P0001R0
---

## Abstract

The as-if rule applies here.

## References
"""

FACTS_JSONL = """\
{"type": "present", "text": "as-if rule", "checked": "verified"}
{"type": "present", "text": "References", "checked": "verified"}
"""

ANCHORS_JSON = """\
{
  "pid": "p0001r0",
  "surface": "raw",
  "must_contain": ["as-if rule"],
  "must_not_contain": [],
  "ordered": [],
  "patterns": []
}
"""


def test_check_facts_all_pass(tmp_path, capsys):
    md = tmp_path / "p0001r0.md"
    facts = tmp_path / "p0001r0.facts.jsonl"
    md.write_text(GOOD_MD)
    facts.write_text(FACTS_JSONL)
    rc = main(["check-facts", "--md", str(md), "--facts", str(facts), "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "pass"


def test_check_facts_fails_absent_text(tmp_path, capsys):
    md = tmp_path / "p0001r0.md"
    facts = tmp_path / "p0001r0.facts.jsonl"
    md.write_text(GOOD_MD)
    facts.write_text('{"type": "present", "text": "MISSING TEXT", "checked": "verified"}\n')
    rc = main(["check-facts", "--md", str(md), "--facts", str(facts), "--json"])
    assert rc == 5  # EXIT_FAIL
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "not-llm-readable"


def test_check_facts_anchors_pass(tmp_path, capsys):
    md = tmp_path / "p0001r0.md"
    anchors = tmp_path / "p0001r0.anchors.json"
    md.write_text(GOOD_MD)
    anchors.write_text(ANCHORS_JSON)
    rc = main(["check-facts", "--md", str(md), "--anchors", str(anchors), "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "pass"


def test_check_facts_missing_md_returns_error(tmp_path):
    rc = main(["check-facts", "--md", str(tmp_path / "missing.md"), "--json"])
    assert rc == 1  # EXIT_ERROR


def test_check_facts_json_structure(tmp_path, capsys):
    md = tmp_path / "p0001r0.md"
    facts = tmp_path / "p0001r0.facts.jsonl"
    md.write_text(GOOD_MD)
    facts.write_text(FACTS_JSONL)
    main(["check-facts", "--md", str(md), "--facts", str(facts), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert "pid" in out
    assert "verdict" in out
    assert "facts" in out
    assert out["facts"] is not None
    assert "anchors" in out
    assert out["anchors"] is None  # no --anchors given


def test_check_facts_module_subprocess_json(tmp_path):
    md = tmp_path / "p0001r0.md"
    facts = tmp_path / "p0001r0.facts.jsonl"
    md.write_text(GOOD_MD, encoding="utf-8")
    facts.write_text(FACTS_JSONL, encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "whisker",
            "check-facts",
            "--md",
            str(md),
            "--facts",
            str(facts),
            "--json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["pid"] == "p0001r0"
    assert payload["verdict"] == "pass"
