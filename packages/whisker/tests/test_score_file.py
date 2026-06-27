#
# Copyright (c) 2026 Sean Parsons (sean.parsons@muckrack.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Tests for the whisker score-file subcommand."""
import json

from whisker.__main__ import main


MINIMAL_MD = """\
---
title: "Test"
document: P0001R0
---

## Abstract

Some content here.
"""

IDEAL_MD = """\
---
title: "Test"
document: P0001R0
---

## Abstract

Some content here.

## Motivation

More content.
"""


def test_score_file_gates_only(tmp_path):
    md = tmp_path / "p0001r0.md"
    md.write_text(MINIMAL_MD)
    rc = main(["score-file", "--md", str(md), "--json"])
    assert rc == 0


def test_score_file_json_output(tmp_path, capsys):
    md = tmp_path / "p0001r0.md"
    md.write_text(MINIMAL_MD)
    main(["score-file", "--md", str(md), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "pass"
    assert out["pid"] == "p0001r0"
    assert isinstance(out["gates"], list)
    assert all(g["passed"] for g in out["gates"])
    assert out["ref_nid"] is None  # no --ref given


def test_score_file_with_ref(tmp_path, capsys):
    md = tmp_path / "p0001r0.md"
    ref = tmp_path / "reference.md"
    md.write_text(MINIMAL_MD)
    ref.write_text(IDEAL_MD)
    main(["score-file", "--md", str(md), "--ref", str(ref), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["ref_nid"] is not None
    assert out["ref_teds"] is not None
    assert out["ref_mhs"] is not None
    assert out["content_recall"] is not None
    assert 0.0 <= out["ref_nid"] <= 1.0


def test_score_file_broken_front_matter_fails(tmp_path, capsys):
    md = tmp_path / "broken.md"
    md.write_text("no front matter at all\n\nsome body text\n")
    rc = main(["score-file", "--md", str(md), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 5  # EXIT_FAIL
    assert out["verdict"] == "fail"
    failed = [g["name"] for g in out["gates"] if not g["passed"]]
    assert "front_matter_valid" in failed


def test_score_file_missing_md_returns_error(tmp_path):
    rc = main(["score-file", "--md", str(tmp_path / "missing.md"), "--json"])
    assert rc == 1  # EXIT_ERROR


def test_score_file_hard_flags_sorted(tmp_path, capsys):
    md = tmp_path / "bad.md"
    md.write_text("no front matter\n")
    main(["score-file", "--md", str(md), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["hard_flags"] == sorted(out["hard_flags"])
