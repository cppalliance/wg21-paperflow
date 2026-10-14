#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Offline tests for C10 identifier-line probes.

No live pod. Scoring, target pick, corruption, and the mocked run path
are what this file guards. Certification stays pending.
"""

from __future__ import annotations

from whisker.det.llm_readability.models import CodeUnit
from whisker.llm.code_probes import (
    CODE_PROBES_KIND,
    code_probes_to_dict,
    corrupt_identifier_on_line,
    pick_identifier_target,
    run_code_probes,
    score_corrupt_answer,
    score_identifier_answer,
)


def _unit(*lines: str, lang: str = "cpp") -> CodeUnit:
    return CodeUnit(
        index=0,
        lang=lang,
        body_lines=lines,
        fence_style="backtick",
    )


class TestPickAndCorrupt:
    def test_skips_keywords_and_picks_identifier(self):
        target = pick_identifier_target(
            _unit("constexpr int widget_factory() {", "  return 0;", "}")
        )
        assert target == (1, "widget_factory")

    def test_empty_or_keyword_only_is_none(self):
        assert pick_identifier_target(_unit("return 0;")) is None
        assert pick_identifier_target(_unit("")) is None

    def test_corrupt_reverses_only_the_target(self):
        unit = _unit("int widget_factory();", "int other_helper();")
        corrupted = corrupt_identifier_on_line(unit, 1, "widget_factory")
        assert corrupted.body_lines[0] == "int yrotcaf_tegdiw();"
        assert corrupted.body_lines[1] == "int other_helper();"


class TestScoring:
    def test_clean_requires_the_identifier(self):
        assert score_identifier_answer("The identifier is widget_factory", "widget_factory")
        assert not score_identifier_answer("NOT FOUND", "widget_factory")

    def test_corrupt_inverts_on_not_found(self):
        assert score_corrupt_answer("NOT FOUND", "widget_factory")
        assert score_corrupt_answer("that identifier does not appear", "widget_factory")

    def test_corrupt_does_not_invert_if_original_ident_returns(self):
        assert not score_corrupt_answer("widget_factory", "widget_factory")


class TestRunCodeProbesMocked:
    def test_no_eligible_fence_is_empty(self):
        result = run_code_probes(
            "P0000R0",
            (_unit("return 0;"),),
            base_url="http://example.invalid/v1",
            api_key="test-key",
        )
        assert result.units == []
        assert result.pass_count == 0

    def test_clean_plus_corrupt_invert_passes(self, monkeypatch):
        answers = iter(("widget_factory", "NOT FOUND"))

        def _fake_ask(*_args, **_kwargs):
            return next(answers), 3

        monkeypatch.setattr(
            "whisker.llm.code_probes._ask_pod", _fake_ask
        )
        result = run_code_probes(
            "P0000R0",
            (_unit("int widget_factory();"),),
            base_url="http://example.invalid/v1",
            api_key="test-key",
            model="deepseek-v4-pro",
        )
        assert len(result.units) == 1
        assert result.units[0].passed is True
        assert result.units[0].clean_passed is True
        assert result.units[0].corrupt_inverted is True
        payload = code_probes_to_dict(result)
        assert payload["kind"] == CODE_PROBES_KIND
        assert "certified" not in payload
        assert payload["pass_count"] == 1

    def test_corrupt_control_that_does_not_invert_is_skipped(self, monkeypatch):
        answers = iter(("widget_factory", "widget_factory"))

        def _fake_ask(*_args, **_kwargs):
            return next(answers), 3

        monkeypatch.setattr(
            "whisker.llm.code_probes._ask_pod", _fake_ask
        )
        result = run_code_probes(
            "P0000R0",
            (_unit("int widget_factory();"),),
            base_url="http://example.invalid/v1",
            api_key="test-key",
        )
        assert result.units[0].skipped is True
        assert result.units[0].passed is False
        assert result.units[0].skip_reason == "corrupt control did not invert"
        assert result.skip_count == 1
        assert result.pass_count == 0
