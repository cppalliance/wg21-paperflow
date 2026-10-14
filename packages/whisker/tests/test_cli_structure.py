#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Architecture guards for the extracted command-line implementation."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest import mock

import pytest
import whisker.__main__ as entry
from whisker import cli_common
from whisker.det import cli as det_cli
from whisker.llm import cli as llm_cli

_MAX_ENTRYPOINT_LINES = 125
_MAX_MAIN_LINES = 45
_VERB_NAMES = {
    "bench_main",
    "calibrate_main",
    "check_facts_main",
    "corpus_main",
    "delta_main",
    "facts_main",
    "golden_main",
    "guard_main",
    "score_file_main",
    "score_main",
}
_ROUTE_CASES = [
    pytest.param(["bench", "sentinel"], "bench_main", ["sentinel"], id="bench"),
    pytest.param(
        ["calibrate", "sentinel"],
        "calibrate_main",
        ["sentinel"],
        id="calibrate",
    ),
    pytest.param(
        ["check-facts", "sentinel"],
        "check_facts_main",
        ["sentinel"],
        id="check-facts",
    ),
    pytest.param(["corpus", "sentinel"], "corpus_main", ["sentinel"], id="corpus"),
    pytest.param(["delta", "sentinel"], "delta_main", ["sentinel"], id="delta"),
    pytest.param(["facts", "sentinel"], "facts_main", ["sentinel"], id="facts"),
    pytest.param(["golden", "sentinel"], "golden_main", ["sentinel"], id="golden"),
    pytest.param(["guard", "sentinel"], "guard_main", ["sentinel"], id="guard"),
    pytest.param(
        ["score-file", "sentinel"],
        "score_file_main",
        ["sentinel"],
        id="score-file",
    ),
    pytest.param(
        ["P0001R0", "--no-write"],
        "score_main",
        ["P0001R0", "--no-write"],
        id="default-score",
    ),
]
_RETIRED_SHARED_HELPERS = {
    "_open_backend",
    "_render_progress",
    "_verdict_exit_code",
}


def test_main_module_is_a_slim_dispatcher():
    source = Path(entry.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    defined = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    main_node = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )

    assert defined == {"main"}
    assert len(source.splitlines()) <= _MAX_ENTRYPOINT_LINES
    assert main_node.end_lineno is not None
    assert main_node.end_lineno - main_node.lineno + 1 <= _MAX_MAIN_LINES
    assert not (_VERB_NAMES & set(vars(entry)))


def test_deterministic_cli_owns_every_verb():
    assert all(callable(getattr(det_cli, name)) for name in _VERB_NAMES)
    assert {case.values[1] for case in _ROUTE_CASES} == _VERB_NAMES
    # The verbs are the module's public dispatch API: __all__ must list
    # exactly them, so a rename or a new verb cannot leave __all__ stale.
    assert set(det_cli.__all__) == _VERB_NAMES


@pytest.mark.parametrize(("argv", "handler_name", "handler_argv"), _ROUTE_CASES)
def test_main_dispatches_every_deterministic_route(
    argv: list[str],
    handler_name: str,
    handler_argv: list[str],
):
    sentinel = object()
    with mock.patch.object(det_cli, handler_name, return_value=sentinel) as handler:
        assert entry.main(argv) is sentinel

    handler.assert_called_once_with(handler_argv)


def test_deterministic_verbs_have_one_definition():
    source_root = Path(entry.__file__).parent
    definitions = {name: [] for name in _VERB_NAMES}
    for path in sorted(source_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in definitions:
                    definitions[node.name].append(path)

    expected_path = Path(det_cli.__file__)
    assert definitions == {name: [expected_path] for name in _VERB_NAMES}


def test_retired_private_shared_helpers_have_no_definitions_or_consumers():
    source_root = Path(entry.__file__).parent
    offenders = []
    for path in sorted(source_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            name = None
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
            elif isinstance(node, ast.Name):
                name = node.id
            elif isinstance(node, ast.Attribute):
                name = node.attr
            elif isinstance(node, ast.alias):
                name = node.asname or node.name.rsplit(".", 1)[-1]
            if name in _RETIRED_SHARED_HELPERS:
                offenders.append(f"{path.relative_to(source_root)}:{node.lineno}:{name}")

    assert offenders == []


def test_cli_common_owns_shared_helpers():
    assert det_cli.render_progress is cli_common.render_progress
    assert det_cli.open_backend is cli_common.open_backend
    assert det_cli.verdict_exit_code is cli_common.verdict_exit_code
    assert llm_cli.render_progress is cli_common.render_progress
