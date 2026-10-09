#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the interactive whisker menu.

Verifies dispatch mapping, non-TTY regression, tapetum-llm availability
detection, the warm/cold/preview mode mapping, and the post-result pause.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest import mock

import pytest
from rich.console import Console
from whisker.menu import (
    _DISPATCH,
    MENU_ITEMS,
    _count_corpus_files,
    _find_default_corpus,
    _has_tapetum_llm,
    _pause,
    _prompt_tapetum_advanced,
    _prompt_tapetum_mode,
    _prompt_tapetum_scope,
)


def _capture_console() -> tuple[Console, StringIO]:
    """A console whose output can be asserted on."""
    buf = StringIO()
    return Console(file=buf, force_terminal=True, width=100), buf


class TestDispatchMapping:
    """Every numbered menu item must have a dispatch handler."""

    def test_all_items_have_handlers(self):
        menu_nums = {item[0] for item in MENU_ITEMS}
        dispatch_nums = set(_DISPATCH.keys())
        assert menu_nums == dispatch_nums, (
            f"Menu/dispatch mismatch: menu={menu_nums}, dispatch={dispatch_nums}"
        )

    def test_all_handlers_are_callable(self):
        for num, handler in _DISPATCH.items():
            assert callable(handler), f"Handler for option {num} is not callable"


class TestNonTTYRegression:
    """Bare ``whisker`` without TTY must not launch the menu."""

    @pytest.mark.parametrize("flag", ["-h", "--help"])
    def test_top_level_help_lists_all_commands(self, flag, capsys):
        """Top-level help must expose every routed command and return success."""
        from whisker.__main__ import main

        rc = main([flag])
        out = capsys.readouterr().out

        assert rc == 0
        for command in (
            "bench",
            "guard",
            "golden",
            "facts",
            "calibrate",
            "score-file",
            "check-facts",
            "corpus",
        ):
            assert f"whisker {command}" in out

    def test_main_reconfigures_stdout_as_utf8(self):
        """Windows consoles must not fail on non-ASCII paper titles."""
        from whisker.__main__ import main

        with (
            mock.patch("sys.stdout") as mock_stdout,
            mock.patch("whisker.det.cli.score_main", return_value=0),
        ):
            main(["--all"])

        mock_stdout.reconfigure.assert_called_once_with(
            encoding="utf-8", errors="replace"
        )

    def test_no_args_non_tty_skips_menu(self):
        """When stdin is not a TTY, main() should fall through to score_main."""
        from whisker.__main__ import main

        with (
            mock.patch("sys.stdin") as mock_stdin,
            mock.patch("sys.stdout") as mock_stdout,
            mock.patch("whisker.det.cli.score_main", return_value=0) as score_mock,
        ):
            mock_stdin.isatty.return_value = False
            mock_stdout.isatty.return_value = False

            rc = main([])
            score_mock.assert_called_once_with([])
            assert rc == 0

    def test_with_args_skips_menu_even_in_tty(self):
        """Explicit args always skip the menu, even in a TTY."""
        from whisker.__main__ import main

        with (
            mock.patch("sys.stdin") as mock_stdin,
            mock.patch("sys.stdout") as mock_stdout,
            mock.patch("whisker.det.cli.score_main", return_value=0) as score_mock,
        ):
            mock_stdin.isatty.return_value = True
            mock_stdout.isatty.return_value = True

            rc = main(["--all"])
            score_mock.assert_called_once_with(["--all"])
            assert rc == 0


class TestTapetumDetection:
    """tapetum-llm availability check must not raise."""

    def test_tapetum_available(self):
        result = _has_tapetum_llm()
        assert isinstance(result, bool)

    def test_tapetum_missing_returns_false(self):
        with mock.patch.dict("sys.modules", {"whisker.llm.cli": None}):
            with mock.patch("importlib.import_module", side_effect=ImportError("mocked")):
                assert _has_tapetum_llm() is False


class TestMenuDispatch:
    """Menu actions dispatch to the correct handlers with expected args."""

    def test_option_1_calls_score_main(self):
        from whisker.menu import _run_score

        with mock.patch("whisker.menu._prompt_pids", return_value=["--all"]):
            with mock.patch("whisker.menu._prompt_reference", return_value=[]):
                with mock.patch("whisker.menu.score_main", return_value=0) as sm:
                    from rich.console import Console
                    console = Console(file=open("NUL", "w"))
                    try:
                        rc = _run_score(console)
                    finally:
                        console.file.close()
                    sm.assert_called_once_with(["--all"])
                    assert rc == 0

    def test_option_3_without_tapetum_shows_hint(self):
        from whisker.menu import _run_llm_only

        with mock.patch("whisker.menu._has_tapetum_llm", return_value=False):
            from io import StringIO

            from rich.console import Console

            buf = StringIO()
            console = Console(file=buf, force_terminal=True)
            rc = _run_llm_only(console)
            assert rc == 1
            assert "tapetum-llm" in buf.getvalue().lower() or "uv sync" in buf.getvalue()

    def test_option_5_no_workspace(self):
        from whisker.menu import _show_last_report

        with mock.patch.dict("os.environ", {}, clear=True):
            from io import StringIO

            from rich.console import Console

            buf = StringIO()
            console = Console(file=buf, force_terminal=True)
            rc = _show_last_report(console)
            assert rc == 1


class TestFindDefaultCorpus:
    """Auto-discovery of the committed whisker corpus directory."""

    def test_finds_committed_corpus(self):
        """Running from inside the repo checkout must find packages/whisker/corpus."""
        result = _find_default_corpus()
        assert result is not None
        assert result.is_dir()
        assert result.name == "corpus"

    def test_start_override(self, tmp_path):
        """An explicit start that leads nowhere returns None."""
        result = _find_default_corpus(start=tmp_path)
        # Walk-up from __file__ still finds it in a checkout, but the start
        # path itself does not contribute. Verify we still get a result from
        # the __file__ walk-up (this test runs inside the checkout).
        assert result is not None

    def test_no_corpus_returns_none(self, tmp_path, monkeypatch):
        """When neither __file__ parents nor cwd lead to the corpus, return None."""
        monkeypatch.setattr("whisker.menu.Path.__file__", str(tmp_path / "fake.py"), raising=False)
        # Patch __file__ is tricky; instead we test with a synthetic relpath
        # that cannot exist.
        from whisker import menu as m
        orig = m._CORPUS_RELPATH
        m._CORPUS_RELPATH = Path("nonexistent") / "dir" / "path"
        try:
            result = _find_default_corpus(start=tmp_path)
            assert result is None
        finally:
            m._CORPUS_RELPATH = orig


class TestCountCorpusFiles:
    """Counting reference files by type in a corpus directory."""

    def test_counts_real_corpus(self):
        """The committed corpus has known file types."""
        corpus = _find_default_corpus()
        if corpus is None:
            pytest.skip("not running in a checkout")
        counts = _count_corpus_files(corpus)
        assert counts["expected"] >= 1, "committed corpus must have .expected.md files"
        assert counts["facts"] >= 1, "committed corpus must have .facts.jsonl files"
        assert isinstance(counts["gt"], int)

    def test_empty_dir(self, tmp_path):
        counts = _count_corpus_files(tmp_path)
        assert counts == {"expected": 0, "facts": 0, "gt": 0}

    def test_mixed_files(self, tmp_path):
        (tmp_path / "P0001R0.expected.md").write_text("x")
        (tmp_path / "P0001R0.facts.jsonl").write_text("x")
        (tmp_path / "P0002R0.gt.md").write_text("x")
        (tmp_path / "P0003R0.gt.md").write_text("x")
        (tmp_path / "readme.txt").write_text("noise")
        counts = _count_corpus_files(tmp_path)
        assert counts == {"expected": 1, "facts": 1, "gt": 2}


class TestTapetumModePrompt:
    """warm/cold/preview must map to the flags the LLM CLI understands."""

    @pytest.mark.parametrize(
        ("mode", "expected"),
        [
            ("warm", ["--inspect"]),
            ("cold", ["--force", "--inspect"]),
            ("preview", ["--would-skip"]),
        ],
    )
    def test_mode_maps_to_flags(self, mode, expected):
        console, _ = _capture_console()
        with mock.patch("whisker.menu.Prompt.ask", return_value=mode):
            assert _prompt_tapetum_mode(console) == expected

    def test_preview_gets_no_inspect(self):
        """Preview returns before adjudicating, so an inspection report is moot."""
        console, _ = _capture_console()
        with mock.patch("whisker.menu.Prompt.ask", return_value="preview"):
            assert "--inspect" not in _prompt_tapetum_mode(console)

    def test_every_mode_is_explained_before_the_prompt(self):
        """The operator must be able to read what warm and cold mean."""
        console, buf = _capture_console()
        with mock.patch("whisker.menu.Prompt.ask", return_value="warm"):
            _prompt_tapetum_mode(console)
        out = buf.getvalue()
        for name in ("warm", "cold", "preview"):
            assert name in out, f"mode {name} is unexplained"
        assert "changed" in out, "warm must say what it skips"
        assert "cache" in out, "cold must say what it ignores"


class TestTapetumScopePrompt:
    """Scope forks first, and only the full-corpus arm has a warm/cold choice."""

    def test_all_scope_asks_for_a_mode(self):
        console, _ = _capture_console()
        with mock.patch("whisker.menu.Prompt.ask", side_effect=["all", "cold"]):
            assert _prompt_tapetum_scope(console) == ["--force", "--inspect"]

    def test_candidates_scope_skips_the_mode_prompt(self):
        """--force is ignored with --review-all, so offering it would be a lie."""
        console, _ = _capture_console()
        with mock.patch("whisker.menu.Prompt.ask", return_value="candidates") as ask:
            assert _prompt_tapetum_scope(console) == ["--review-all", "--inspect"]
            assert ask.call_count == 1


class TestTapetumAdvancedPrompt:
    """Diagnostics sit behind one gate so the common path is a single Enter."""

    def test_declined_gate_asks_nothing_further(self):
        console, _ = _capture_console()
        with mock.patch("whisker.menu.Prompt.ask", return_value="n") as ask:
            assert _prompt_tapetum_advanced(console) == []
            assert ask.call_count == 1, "declining must not fall into the ladder"

    def test_accepted_gate_collects_selected_flags(self):
        console, _ = _capture_console()
        with mock.patch("whisker.menu.Prompt.ask", side_effect=["y", "y", "n", "y"]):
            assert _prompt_tapetum_advanced(console) == ["--retry-errors", "--trace"]

    def test_accepted_gate_may_still_select_nothing(self):
        console, _ = _capture_console()
        with mock.patch("whisker.menu.Prompt.ask", side_effect=["y", "n", "n", "n"]):
            assert _prompt_tapetum_advanced(console) == []


class TestPause:
    """A result must survive on screen without hanging a headless run."""

    def test_pause_waits_once(self):
        console, _ = _capture_console()
        with mock.patch("whisker.menu.Prompt.ask", return_value="") as ask:
            _pause(console)
            assert ask.call_count == 1

    @pytest.mark.parametrize("exc", [EOFError, KeyboardInterrupt])
    def test_pause_survives_absent_stdin(self, exc):
        """A closed or piped stdin must fall through, not raise out of the loop."""
        console, _ = _capture_console()
        with mock.patch("whisker.menu.Prompt.ask", side_effect=exc):
            _pause(console)
