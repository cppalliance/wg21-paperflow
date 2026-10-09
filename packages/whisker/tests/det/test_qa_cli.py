"""Tests for the whisker QA CLI verbs (migrated from tomd.cli)."""

import json
import shutil
from pathlib import Path

import pytest
from whisker.det.qa_cli import _DEFAULT_GOLDEN, qa_main

_GOLDEN = Path(__file__).resolve().parents[3] / "tomd" / "tests" / "fixtures" / "golden"


def test_default_golden_dir_resolves_to_tomd_fixtures():
    # Every other test in this file passes --golden-dir explicitly, so a broken
    # default would stay invisible here while breaking every real invocation.
    # It did: the migration off tomd left the parents[] index one level short.
    assert _DEFAULT_GOLDEN == _GOLDEN
    assert (_DEFAULT_GOLDEN / "ideals").is_dir()
    assert (_DEFAULT_GOLDEN / "baselines.json").is_file()

requires_source = pytest.mark.skipif(
    not (_GOLDEN / "sources" / "p4228r0.html").is_file(),
    reason="sources/p4228r0.html not staged",
)


@requires_source
def test_cli_score_prints_table_and_returns_zero(capsys):
    rc = qa_main(["--golden-dir", str(_GOLDEN), "score", "P4228R0"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "heading" in out and "frontmatter" in out


@requires_source
def test_cli_score_json_is_parseable(capsys):
    rc = qa_main(["--golden-dir", str(_GOLDEN), "score", "p4228r0", "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "p4228r0" in data


@requires_source
def test_cli_issue_prints_draft(capsys):
    rc = qa_main(["--golden-dir", str(_GOLDEN), "issue", "p4228r0"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "tomd:" in out and "heading" in out.lower()


@requires_source
def test_cli_issue_create_calls_gh(monkeypatch, capsys):
    import subprocess

    import whisker.det.qa_cli as cli

    calls = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        result = subprocess.CompletedProcess(cmd, 0)
        result.stdout = "https://github.com/owner/repo/issues/99\n"
        result.stderr = ""
        return result

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    rc = qa_main(["--golden-dir", str(_GOLDEN), "issue", "p4228r0", "--create"])
    assert rc == 0
    gh_calls = [cmd for cmd in calls if cmd and "gh" in cmd[0]]
    assert gh_calls, "gh should have been called at least once"
    assert all("--title" in cmd for cmd in gh_calls)
    assert "https://github.com" in capsys.readouterr().out


@requires_source
def test_cli_issue_create_gh_missing_reports_error(monkeypatch, capsys):
    import whisker.det.qa_cli as cli

    def fake_run(_cmd, **_kwargs):
        raise FileNotFoundError("gh not found")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    rc = qa_main(["--golden-dir", str(_GOLDEN), "issue", "p4228r0", "--create"])
    assert rc == 1
    assert "gh not found" in capsys.readouterr().err


def test_cli_generate_seeds_from_tomd(tmp_path):
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "p9999r0.html").write_text(
        "<html><body><h1>Title</h1><p>Body.</p></body></html>", encoding="utf-8")
    rc = qa_main(["--golden-dir", str(tmp_path), "generate", "P9999R0"])
    assert rc == 0
    assert (tmp_path / "ideals" / "p9999r0.md").is_file()


def test_cli_score_unknown_paper_returns_nonzero(capsys):
    rc = qa_main(["--golden-dir", str(_GOLDEN), "score", "nope9999"])
    assert rc != 0
    assert "nope9999" in capsys.readouterr().err


def _stage(tmp_path):
    (tmp_path / "sources").mkdir(exist_ok=True)
    (tmp_path / "ideals").mkdir(exist_ok=True)
    shutil.copy(_GOLDEN / "ideals" / "p4228r0.md", tmp_path / "ideals" / "p4228r0.md")
    shutil.copy(_GOLDEN / "sources" / "p4228r0.html", tmp_path / "sources" / "p4228r0.html")
    return tmp_path / "baselines.json"


@requires_source
def test_cli_rebless_refuses_lower_without_force(tmp_path):
    manifest = _stage(tmp_path)
    manifest.write_text(json.dumps({"p4228r0": {"heading": 1.0}}) + "\n", encoding="utf-8")
    rc = qa_main(["--golden-dir", str(tmp_path), "rebless", "p4228r0"])
    assert rc != 0
    assert json.loads(manifest.read_text())["p4228r0"]["heading"] == 1.0


@requires_source
def test_cli_rebless_force_lowers(tmp_path):
    manifest = _stage(tmp_path)
    manifest.write_text(json.dumps({"p4228r0": {"heading": 1.0}}) + "\n", encoding="utf-8")
    rc = qa_main(["--golden-dir", str(tmp_path), "rebless", "p4228r0", "--force"])
    assert rc == 0
    assert json.loads(manifest.read_text())["p4228r0"]["heading"] == pytest.approx(round(2 / 3, 2))


def test_cli_add_stages_source(tmp_path):
    src = tmp_path / "in.html"
    src.write_text("<html></html>", encoding="utf-8")
    dest_dir = tmp_path / "golden"
    dest_dir.mkdir()
    rc = qa_main(["--golden-dir", str(dest_dir), "add", "p9999r0", str(src)])
    assert rc == 0
    assert (dest_dir / "sources" / "p9999r0.html").is_file()


def test_cli_add_reuses_existing_source(tmp_path, capsys):
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "p9999r0.html").write_text("<html></html>", encoding="utf-8")
    rc = qa_main(["--golden-dir", str(tmp_path), "add", "p9999r0"])
    assert rc == 0
    assert "already staged" in capsys.readouterr().out


def test_cli_add_no_source_fails_closed(tmp_path, capsys):
    rc = qa_main(["--golden-dir", str(tmp_path), "add", "p9999r0"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "no local source and no staged source" in err
    assert "whisker qa add p9999r0" in err
